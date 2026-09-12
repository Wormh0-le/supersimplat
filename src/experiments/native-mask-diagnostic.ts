import { Color, Mat4, Quat, Vec3 } from 'playcanvas';

import { ElementType } from '../element';
import { MappedReadFileSystem, PermutedChunkSource } from '../io';
import type { Scene } from '../scene';
import type { Splat } from '../splat';
import { analyzeContribution, checkTiledContribution, plateTracePixels, regressionTracePixels, traceContribution, type ContributionFrame, type ContributionAnalysis, type SupportRow } from './native-contribution-diagnostic';
import { classifySupport, SUPPORT_POLICY, SUPPORT_RULE, type TiledContributionOptions } from './native-contribution-reference';
import { checkNativeIdentity } from './native-mask-identity-check';
import { maskInputs, taskId, type MaskInput, type TaskId } from './native-mask-target';

type Role = 'A' | 'B' | 'C';
type View = {
    role: Role;
    camera: {
        width: number; height: number; intrinsicsPINHOLE: number[];
        quaternionWXYZ: number[]; translation: number[];
    };
    annotations: { taskId: string; sha256?: string }[];
};
type ContributionSnapshot = Awaited<ReturnType<Scene['projectedSplatRenderer']['readDiagnosticSnapshot']>>;
type Frame = { rgb: Uint8Array; ids: number[]; mask: Uint8Array; png: string; alignment: string;
    snapshot?: ContributionSnapshot; nativeHalf?: Uint16Array };
const method = 'native-alpha-gated-frontmost-id-hit/v1';
// Frozen on A before B/C: a 3.7%-opacity foreground ellipse wins every apple
// pixel at native threshold 0. This excludes translucent winners,
// and consequently cannot qualify transparent objects or exact contribution.
const alphaThreshold = 0.1;
const sha256 = async (bytes: Uint8Array) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>)))
.map(v => v.toString(16).padStart(2, '0')).join('');

const canvasOf = (bytes: Uint8Array, width: number, height: number) => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(bytes), width, height), 0, 0);
    return canvas;
};

// COLMAP w2c (+Y down,+Z forward) -> PlayCanvas c2w (+Y up,-Z forward).
const cameraPose = (view: View, model: Mat4) => {
    const [w, x, y, z] = view.camera.quaternionWXYZ;
    const cv = new Mat4().setTRS(new Vec3(...view.camera.translation), new Quat(x, y, z, w), Vec3.ONE);
    const flip = new Mat4().setScale(1, -1, -1);
    const world = new Mat4().mul2(model, cv.invert().mul(flip));
    return { position: world.getTranslation(), rotation: new Quat().setFromMat4(world) };
};

const projection = (view: View, near: number, far: number, result: Mat4) => {
    const { width, height, intrinsicsPINHOLE: [fx, fy, cx, cy] } = view.camera;
    const d = result.data;
    d.fill(0);
    d[0] = 2 * fx / width;
    d[5] = 2 * fy / height;
    d[8] = 1 - 2 * cx / width;
    d[9] = 2 * cy / height - 1;
    d[10] = -(far + near) / (far - near);
    d[11] = -1;
    d[14] = -2 * far * near / (far - near);
};

const nextFrame = (scene: Scene) => new Promise<void>((resolve, reject) => {
    const handles: { frame?: { off: () => void } } = {};
    const timer = setTimeout(() => {
        handles.frame.off(); reject(new Error('Native frame timed out after 60s'));
    }, 60000);
    handles.frame = scene.events.on('postrender', () => {
        clearTimeout(timer); handles.frame.off(); resolve();
    });
    scene.lockedRender = true;
    scene.forceRender = true;
});

// Explicit opt-in console harness. No model inference, publication or Native Selection writes.
const registerNativeMaskDiagnostic = (scene: Scene) => {
    let splat: Splat;
    let views: View[];
    let base: string;
    let manifest: any;
    let target: TaskId = 'easy-apple';
    let inputs: readonly MaskInput[];
    let generation = 0;
    let busy = false;
    let initialModel: Float32Array;
    let displayedIds: number[] | null = null;
    const frames = new Map<Role, Frame>();
    const reviews = new Map<Role, string>();
    const candidates = new Map<'A' | 'B', number[]>();
    const contributionViews = new Map<'A' | 'B', ContributionAnalysis>();
    let contributionFrozen = false;
    const report: any = { method,
        alphaThreshold,
        protocol: 'custom development oracle masks',
        userConfirmed: false,
        fusion: 'A union B; no negatives, weights or P/N/V',
        captures: {},
        mappings: {},
        reviews: {},
        renderedOverlays: [],
        failures: [] };

    const invalidateContribution = (role: Role) => {
        const affected = role === 'A' ? ['A', 'B', 'C'] : role === 'B' ? ['B', 'C'] : ['C'];
        for (const view of affected) {
            if (report.contributionChecks) delete report.contributionChecks[view];
            if (report.contributions) delete report.contributions[view];
        }
        if (role === 'A') {
            contributionViews.clear(); contributionFrozen = false;
            delete report.contributionTrace; delete report.contributionFreeze;
        } else if (role === 'B') contributionViews.delete('B');
        if (role !== 'C') delete report.contributionPositions;
        for (const key of Object.keys(report.contributionEvaluations ?? {})) {
            if (role === 'A' || key.startsWith('C.') || (role === 'B' && (key.startsWith('B.') || key.endsWith('.AB')))) {
                delete report.contributionEvaluations[key];
            }
        }
    };

    const invalidate = () => {
        generation++;
        report.status = 'invalidated';
        report.generation = generation;
        frames.clear(); reviews.clear(); candidates.clear();
        report.captures = {}; report.mappings = {}; report.reviews = {}; report.renderedOverlays = [];
        delete report.counterexamples; delete report.unionInstances;
        invalidateContribution('A');
        displayedIds = null;
        if (splat) scene.projectedSplatRenderer.setDiagnosticOverlay(splat, null);
    };
    const changedSplat = (changed: Splat) => {
        if (changed === splat) invalidate();
    };
    for (const event of ['splat.stateChanged', 'splat.replaced', 'splat.positionsChanged', 'splat.moved', 'splat.visibility']) {
        scene.events.on(event, changedSplat);
    }
    scene.events.on('pivot.started', invalidate);
    scene.events.on('scene.elementRemoved', invalidate);

    const checkScene = () => {
        if (!splat || !manifest) throw new Error('Load the fixed Teatime input first');
        const all = scene.getElementsByType(ElementType.splat) as Splat[];
        if (all.length !== 1 || all[0] !== splat || !splat.visible || splat.numLocked || splat.instances.count !== manifest.modelSource.gaussianCount) {
            throw new Error('Diagnostic requires one complete, visible, unlocked Teatime layer; multi-layer picking loses occluders');
        }
        if (initialModel.some((v, i) => splat.entity.getWorldTransform().data[i] !== v) ||
            splat.instances.sourceRow.some((row, i) => row !== i) ||
            splat.instances.palette.some(value => value !== 0)) {
            throw new Error('Scene geometry/appearance edited; original camera/Mask binding invalid. Reload the fixed input');
        }
    };
    const serial = async <T>(fn: () => Promise<T>) => {
        if (busy) throw new Error('Diagnostic is busy');
        busy = true;
        try {
            return await scene.commandQueue.enqueue(fn);
        } finally {
            busy = false;
        }
    };

    const capture = (role: Role, ids: number[] | null = null, contribution = false) => serial(async () => {
        checkScene();
        if (role === 'B' && !candidates.has('A')) throw new Error('Run A-only before B');
        if (role === 'C' && !candidates.has('B')) throw new Error('Freeze A+B before C inspection');
        if (contribution && role !== 'A' && !contributionFrozen) throw new Error('Freeze A contribution rule before B/C capture');
        if (contribution && role === 'C' && !contributionViews.has('B')) throw new Error('Freeze A+B contribution support before C');
        const view = views.find(v => v.role === role);
        if (!view) throw new Error('Unknown view');
        const epoch = generation;
        const capturedTarget = target;
        const input = inputs.find(m => m.role === role && m.task === capturedTarget);
        const { camera } = scene;
        const { width, height, intrinsicsPINHOLE: [fx] } = view.camera;
        const saved = {
            pose: camera.poseOverride,
            projection: camera.camera.calculateProjection,
            ortho: camera.ortho,
            fov: camera.fov,
            tone: camera.tonemapping,
            overlays: camera.renderOverlays,
            locked: scene.lockedRenderMode,
            world: scene.worldLayer.enabled,
            gizmos: scene.gizmoLayer.enabled,
            centers: scene.centersLayer.enabled,
            bands: scene.events.invoke('view.bands'),
            minPixelSize: scene.events.invoke('view.minPixelSize'),
            exposure: scene.app.scene.exposure,
            footprint: scene.events.invoke('selection.footprint'),
            background: scene.events.invoke('bgClr').clone()
        };
        const flags = splat.instances.flags.slice();
        if (contribution && (ids || splat.instances.numSelected || scene.events.invoke('colorPanel.pending'))) {
            throw new Error('Contribution capture requires raw appearance and no native selection or pending grade');
        }
        let snapshot: ContributionSnapshot;
        let nativeHalf: Uint16Array;
        const start = performance.now();
        try {
            scene.lockedRenderMode = true;
            camera.ortho = false;
            camera.tonemapping = 'linear';
            camera.renderOverlays = false;
            scene.worldLayer.enabled = false;
            scene.gizmoLayer.enabled = false;
            scene.centersLayer.enabled = false;
            scene.events.fire('view.setBands', 3);
            scene.events.fire('view.setMinPixelSize', 0);
            scene.app.scene.exposure = 1;
            scene.events.fire('setBgClr', new Color(0, 0, 0, 1));
            scene.events.fire('selection.setFootprint', 1);
            const pose = cameraPose(view, splat.entity.getWorldTransform());
            camera.setPoseOverride({ ...pose, fov: 2 * Math.atan(width / (2 * fx)) * 180 / Math.PI, near: 0.01, far: 1000 });
            camera.camera.calculateProjection = result => projection(view, 0.01, 1000, result);
            camera.startOffscreenMode(width, height);
            scene.projectedSplatRenderer.setDiagnosticOverlay(splat, ids);
            await nextFrame(scene);
            const rgb = new Uint8Array(width * height * 4);
            // Enqueue cache, exact order, RGBA16F and RGBA8 copies in the same
            // JS turn, before picker re-projects. No asynchronous frame can mix them.
            const snapshotRead = contribution ? scene.projectedSplatRenderer.readDiagnosticSnapshot(splat) : null;
            const halfRead = contribution ? camera.mainTarget.colorBuffer.read(0, 0, width, height, { immediate: true }) : null;
            scene.dataProcessor.copyRt(camera.mainTarget, camera.workTarget);
            const rgbRead = camera.workTarget.colorBuffer.read(0, 0, width, height, { renderTarget: camera.workTarget, data: rgb, immediate: true });
            const values = await Promise.all([snapshotRead, halfRead, rgbRead]);
            snapshot = values[0];
            nativeHalf = values[1] as Uint16Array;
            camera.pickPrep(splat, 'set', alphaThreshold);
            const picked = await camera.pickRect(0, 0, 1, 1);
            const baselinePicks = new Map<number, number[]>();
            if (role === 'A' && !ids) {
                for (const threshold of [0, 1 / 255]) {
                    camera.pickPrep(splat, 'set', threshold);
                    baselinePicks.set(threshold, await camera.pickRect(0, 0, 1, 1));
                }
            }
            if (picked.length !== width * height) throw new Error('ID target dimensions differ from RGB/Mask');
            if (flags.some((value, i) => splat.instances.flags[i] !== value)) throw new Error('Native Selection changed during capture');
            if (epoch !== generation) throw new Error('Scene changed during capture; evidence rejected');
            const png = canvasOf(rgb, width, height).toDataURL();
            const record = { camera: view.camera,
                width,
                height,
                elapsedMs: performance.now() - start,
                rgbSHA256: await sha256(rgb),
                idSHA256: await sha256(new Uint8Array(new Uint32Array(picked).buffer)),
                nativeSelectionUnchanged: true,
                modelMatrix: Array.from(splat.entity.getWorldTransform().data),
                render: 'WebGPU sorted alpha blend, SH3, linear tone mapping, exposure=1, black background, minPixelSize=0, footprint=1, near=.01 far=1000',
                taskId: capturedTarget,
                inputMask: input.path,
                overlayInstances: ids?.length ?? 0 };
            if (epoch !== generation) throw new Error('Scene changed during capture; evidence rejected');
            if (ids) {
                report.renderedOverlays.push({ ...record, role, instanceIds: ids });
                return { png, record };
            }

            // C is fetched only after fusion has been frozen, and never enters map().
            const response = await fetch(new URL(input.path, base));
            if (!response.ok) throw new Error('Mask fetch failed');
            const bytes = new Uint8Array(await response.arrayBuffer());
            if (await sha256(bytes) !== input.sha256) throw new Error('Source Mask hash mismatch');
            const bitmap = await createImageBitmap(new Blob([bytes]));
            if (bitmap.width !== width || bitmap.height !== height) throw new Error('Mask dimensions differ; no automatic resizing');
            const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
            const ctx = canvas.getContext('2d'); ctx.drawImage(bitmap, 0, 0); bitmap.close();
            const rgba = ctx.getImageData(0, 0, width, height).data;
            const mask = new Uint8Array(width * height);
            for (let i = 0; i < mask.length; i++) {
                const value = rgba[4 * i];
                if ((value !== 0 && value !== 255) || rgba[4 * i + 1] !== value || rgba[4 * i + 2] !== value || rgba[4 * i + 3] !== 255) throw new Error('Mask must be opaque binary grayscale');
                mask[i] = value;
            }
            const marked = rgb.slice();
            for (let i = 0; i < mask.length; i++) {
                if (!mask[i]) continue;
                const boundary = i % width === 0 || i % width === width - 1 || !mask[i - 1] || !mask[i + 1] || !mask[i - width] || !mask[i + width];
                if (boundary) marked.set([255, 0, 230, 255], i * 4);
            }
            const alignment = canvasOf(marked, width, height).toDataURL();
            const maskSHA256 = await sha256(bytes);
            if (epoch !== generation) throw new Error('Scene changed during Mask decoding; evidence rejected');
            invalidateContribution(role);
            // Every new input capture needs its own review. A invalidates B/C;
            // C inspection cannot change either input or the frozen union.
            if (role !== 'C') {
                for (const affected of role === 'A' ? ['A', 'B'] as const : ['B'] as const) {
                    reviews.delete(affected); candidates.delete(affected);
                }
                if (role === 'A') frames.delete('B');
                frames.delete('C');
                displayedIds = candidates.get('A') ?? null;
            }
            frames.set(role, { rgb, ids: picked, mask, png, alignment, snapshot, nativeHalf });
            report.captures[role] = { ...record, maskSHA256 };
            if (baselinePicks.size) {
                report.counterexamples = Array.from(baselinePicks, ([threshold, values]) => {
                    const winners = new Set<number>();
                    let maskPixels = 0;
                    for (let i = 0; i < mask.length; i++) {
                        if (mask[i]) {
                            maskPixels++;
                            if (values[i] !== 0xffffffff) winners.add(values[i]);
                        }
                    }
                    return { threshold,
                        maskPixels,
                        instances: winners.size,
                        sourceRows: Array.from(winners, id => splat.instances.sourceRow[id]) };
                });
            }
            report.status = role === 'C' ? 'A+B frozen; C inspection only' : `${role} awaiting alignment review`;
            return { png, alignment, record: report.captures[role] };
        } finally {
            camera.setPoseOverride(saved.pose);
            camera.camera.calculateProjection = saved.projection;
            camera.fov = saved.fov; camera.ortho = saved.ortho; camera.tonemapping = saved.tone;
            camera.endOffscreenMode(); camera.renderOverlays = saved.overlays;
            scene.worldLayer.enabled = saved.world;
            scene.gizmoLayer.enabled = saved.gizmos;
            scene.centersLayer.enabled = saved.centers;
            scene.events.fire('view.setBands', saved.bands);
            scene.events.fire('view.setMinPixelSize', saved.minPixelSize);
            scene.app.scene.exposure = saved.exposure;
            scene.lockedRenderMode = saved.locked;
            scene.events.fire('setBgClr', saved.background);
            scene.events.fire('selection.setFootprint', saved.footprint);
            scene.projectedSplatRenderer.setDiagnosticOverlay(splat, displayedIds);
            scene.forceRender = true;
        }
    });

    const contributionSelection = (name: 'M0' | 'M1' | 'M2', mode: 'A' | 'AB') => {
        checkScene();
        if (!['M0', 'M1', 'M2'].includes(name) || !['A', 'AB'].includes(mode) || !contributionViews.has('A') ||
            (mode === 'AB' && !contributionViews.has('B'))) throw new Error('Only completed A / A+B contribution comparisons may select');
        const views = [contributionViews.get('A'), ...(mode === 'AB' ? [contributionViews.get('B')] : [])];
        const perId = new Map<number, SupportRow[]>();
        for (const view of views) {
            for (const row of view.rows) {
                if (!perId.has(row.id)) perId.set(row.id, []);
                perId.get(row.id).push(row);
            }
        }
        const classifications = Array.from(perId, ([id, rows]) => ({ id, ...classifySupport(rows) }));
        const baselineIds = Array.from(new Set([...(candidates.get('A') ?? []), ...(mode === 'AB' ? candidates.get('B') ?? [] : [])]));
        const ids = name === 'M0' ? baselineIds : name === 'M1' ? Array.from(new Set(views.flatMap(v => v.winnerIds))) : classifications.filter(r => r.selected).map(r => r.id);
        return { ids: ids.sort((a, b) => a - b), conflicts: classifications.filter(r => r.conflict).map(r => r.id), unknown: classifications.filter(r => r.status === 'unknown').map(r => r.id) };
    };

    const api = {
        load(bundleURL: string, plyURL: string) {
            return serial(async () => {
                if (splat || scene.getElementsByType(ElementType.splat).length) throw new Error('Start in an empty document');
                base = new URL(bundleURL, location.href).href;
                const manifestBytes = new Uint8Array(await (await fetch(new URL('benchmark.json', base))).arrayBuffer());
                const manifestSHA256 = await sha256(manifestBytes);
                if (manifestSHA256 !== '75bf0a7ccdb2d108b114600c8c02e9a6bab28f332117059ad27580227193bf75') throw new Error('Benchmark differs from pinned merged preparation');
                manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
                if (manifest.schema !== 'ai-select-teatime-preparation/v1' || manifest.scene !== 'LERF-Mask/teatime') throw new Error('Unexpected benchmark');
                views = manifest.views;
                const bundleBytes = new Uint8Array(await (await fetch(new URL('bundle-report.json', base))).arrayBuffer());
                inputs = maskInputs(JSON.parse(new TextDecoder().decode(bundleBytes)));
                const bundleSHA256 = await sha256(bundleBytes);
                for (const input of inputs) {
                    const sourceHash = views.find(v => v.role === input.role)?.annotations.find(a => a.taskId === input.task)?.sha256;
                    if (sourceHash && input.sha256 !== sourceHash) throw new Error('Bundle Mask differs from pinned source annotation');
                }
                const response = await fetch(new URL(plyURL, location.href));
                if (!response.ok) throw new Error('PLY fetch failed');
                const blob = await response.blob();
                const plySHA256 = await sha256(new Uint8Array(await blob.arrayBuffer()));
                if (blob.size !== manifest.modelSource.plyBytes || plySHA256 !== manifest.modelSource.gaussianPlySHA256) throw new Error('Actual PLY bytes do not match pinned source');
                const files = new MappedReadFileSystem();
                files.addFile('teatime.ply', blob);
                splat = await scene.assetLoader.load('teatime.ply', files, false, true);
                if (splat.resource.source instanceof PermutedChunkSource) throw new Error('Unexpected source reordering');
                initialModel = splat.entity.getWorldTransform().data.slice();
                await scene.add(splat);
                checkScene();
                if (splat.instances.sourceRow.some((row, i) => row !== i)) throw new Error('Imported instance/source row mismatch');
                report.input = { plySHA256,
                    manifestSHA256,
                    bundleSHA256,
                    masks: inputs,
                    preparationCommit: '4265d862a81dd6f1895746d106425b19b8316ca6',
                    layerUid: splat.uid,
                    actualBytesHashedInBrowser: blob.size,
                    count: splat.instances.count,
                    sourceRow: 'skipReorder=true; instanceSource[row] = original PLY row on this import',
                    training: manifest.modelSource.trainingCaveat,
                    ignored: manifest.modelSource.forbiddenSelectionInputs };
                report.adapter = scene.graphicsDevice.deviceType;
                report.taskId = target;
                return report.input;
            });
        },
        setTarget(value: unknown) {
            checkScene();
            const next = taskId(value);
            if (next === target) return target;
            // Synchronous invalidation is allowed while a readback/evaluator is pending.
            invalidate();
            target = next; report.taskId = target; report.failures = [];
            return target;
        },
        cancel: invalidate,
        releaseSnapshot(role: Role) {
            if (busy) throw new Error('Diagnostic is busy');
            const frame = frames.get(role);
            if (frame) {
                delete frame.snapshot; delete frame.nativeHalf;
            }
        },
        capture,
        support(role: 'A' | 'B') {
            const result = contributionViews.get(role);
            if (!result) throw new Error('No complete support for view');
            return result;
        },
        analyze(role: 'A' | 'B', limits?: TiledContributionOptions['limits']) {
            return serial(async () => {
                checkScene();
                if (!['A', 'B'].includes(role) || !reviews.has(role) || !candidates.has(role) || !report.contributionChecks?.[role]?.passed ||
                    (role === 'B' && !contributionFrozen)) throw new Error('Trace must pass; use reviewed A/B only, with A rule frozen before B');
                const frame = frames.get(role);
                if (!frame?.snapshot || !frame.nativeHalf) throw new Error('Recapture with contribution=true');
                const epoch = generation;
                const result = await analyzeContribution(frame as ContributionFrame, [], { limits, isCurrent: () => epoch === generation });
                if (epoch !== generation) throw new Error('Scene changed during contribution analysis');
                contributionViews.set(role, result);
                report.contributions ??= {};
                report.contributions[role] = { ...result, snapshotCost: frame.snapshot.cost, rgbSHA256: report.captures[role].rgbSHA256 };
                return result;
            });
        },
        checkTiling(role: 'A' | 'B') {
            return serial(async () => {
                checkScene();
                const frame = frames.get(role), epoch = generation;
                if (!frame?.snapshot || !report.contributionChecks?.[role]?.passed) throw new Error('No qualified snapshot');
                const sets = ['M0', 'M2'].map(name => contributionSelection(name as 'M0' | 'M2', 'A').ids);
                return await checkTiledContribution(frame as ContributionFrame, sets, () => epoch === generation);
            });
        },
        freezeContribution() {
            checkScene();
            if (busy || !contributionViews.has('A') || frames.has('B') || frames.has('C')) throw new Error('Freeze after A analysis and before B/C');
            contributionFrozen = true;
            report.contributionFreeze = { policy: SUPPORT_POLICY, rule: SUPPORT_RULE, roiMargin: 16, observationWeights: [1, 1], protocol: 'ROI-local native contribution support; not Direct Evidence P/N/V', aRGB: report.captures.A.rgbSHA256 };
            return report.contributionFreeze;
        },
        contributionIds(name: 'M0' | 'M1' | 'M2', mode: 'A' | 'AB') {
            if (busy) throw new Error('Diagnostic is busy');
            return contributionSelection(name, mode);
        },
        evaluateContribution(role: Role, mode: 'A' | 'AB', names: ('M0' | 'M1' | 'M2')[] = ['M0', 'M1', 'M2']) {
            return serial(async () => {
                checkScene();
                if (!['A', 'B', 'C'].includes(role) || !report.contributionChecks?.[role]?.passed) throw new Error('No qualified contribution capture');
                const frame = frames.get(role), epoch = generation;
                if (!frame?.snapshot || !frame.nativeHalf) throw new Error('Capture contribution snapshot first');
                if (!names.length || names[0] !== 'M0' || new Set(names).size !== names.length) throw new Error('Comparison requires distinct methods with M0 baseline');
                const methods = names.map(name => ({ name, ...contributionSelection(name, mode) }));
                const result = await analyzeContribution(frame as ContributionFrame, methods.map(m => m.ids), { isCurrent: () => epoch === generation });
                if (epoch !== generation) throw new Error('Scene changed during contribution evaluation');
                const baseline = new Set(methods[0].ids);
                const comparison = methods.map((m, i) => {
                    const selected = new Set(m.ids);
                    return { ...m, metrics: result.metrics[i], added: m.ids.filter(id => !baseline.has(id)), removed: methods[0].ids.filter(id => !selected.has(id)) };
                });
                report.contributionEvaluations ??= {};
                report.contributionEvaluations[`${role}.${mode}`] = { comparison, roi: result.roi, summary: result.summary, maxRGBA8Error: result.maxRGBA8Error, meanRGBA8Error: result.meanRGBA8Error, conservationError: result.conservationError };
                // Q uses full original-scene T; no selected-only re-render.
                return { ...report.contributionEvaluations[`${role}.${mode}`], qImages: result.qImages };
            });
        },
        contributionPositions() {
            return serial(async () => {
                checkScene();
                const epoch = generation;
                const ids = Array.from(new Set(Array.from(contributionViews.values()).flatMap(v => v.rows.map(r => r.id)))).sort((a, b) => a - b);
                if (ids.length > 20000) throw new Error('Contribution positions incomplete: row capacity');
                const rows = Uint32Array.from(ids, id => splat.instances.sourceRow[id]);
                const { resource } = splat;
                const position = resource.sourcePool.acquire('position', resource.source.meta.layouts.position, rows.length);
                try {
                    await resource.source.read({ indices: rows, indexOffset: 0, count: rows.length, position });
                    if (epoch !== generation) throw new Error('Scene changed during contribution positions');
                    const xyz = new Float32Array(position.data, 0, rows.length * 3);
                    const values = ids.map((id, i) => ({ id, sourceRow: rows[i], sourcePosition: Array.from(xyz.subarray(i * 3, i * 3 + 3)), worldPosition: splat.entity.getWorldTransform().transformPoint(new Vec3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2])).toArray() }));
                    report.contributionPositions = values;
                    return values;
                } finally {
                    position.release();
                }
            });
        },
        trace(role: Role = 'A') {
            return serial(async () => {
                checkScene();
                const epoch = generation;
                const frame = frames.get(role);
                if (!frame?.snapshot || !frame.nativeHalf) throw new Error('Capture untinted contribution frame first');
                const points = role === 'A' ? (target === 'medium-plate' ? plateTracePixels(frame as ContributionFrame) : undefined) : regressionTracePixels(frame as ContributionFrame);
                const result = await traceContribution(frame as ContributionFrame, (scene.graphicsDevice as any).wgpu, points, role === 'A');
                if (epoch !== generation) throw new Error('Scene changed during contribution trace');
                report.contributionChecks ??= {};
                report.contributionChecks[role] = result;
                if (role === 'A') report.contributionTrace = result;
                return result;
            });
        },
        review(role: 'A' | 'B', note: string) {
            if (busy || !frames.has(role) || !note.trim() || (role !== 'A' && role !== 'B')) throw new Error('Capture and inspect A/B alignment first');
            reviews.set(role, note);
            report.reviews[role] = { taskId: target, maskSHA256: report.captures[role].maskSHA256, note, status: 'development visual review; not User Confirmed', rgbSHA256: report.captures[role].rgbSHA256 };
        },
        map(role: 'A' | 'B') {
            checkScene();
            if (busy || (role !== 'A' && role !== 'B') || !reviews.has(role)) throw new Error('Only reviewed A/B may be mapped');
            const frame = frames.get(role);
            const found = new Set<number>();
            let misses = 0;
            for (let i = 0; i < frame.mask.length; i++) {
                if (!frame.mask[i]) continue;
                const id = frame.ids[i];
                if (id === 0xffffffff) {
                    misses++; continue;
                }
                if (id >= splat.instances.count) throw new Error('Pick ID outside instance list');
                found.add(id);
            }
            const ids = Array.from(found).sort((a, b) => a - b);
            candidates.set(role, ids);
            const union = api.ids('AB');
            displayedIds = union;
            scene.projectedSplatRenderer.setDiagnosticOverlay(splat, union);
            report.status = candidates.has('B') ? 'A+B frozen' : 'A-only';
            report.mappings[role] = { instances: ids.length,
                maskPixelsWithoutWinner: misses,
                sourceRows: ids.map(id => splat.instances.sourceRow[id]),
                instanceIds: ids };
            report.unionInstances = union.length;
            return { instances: ids.length, union: union.length, misses };
        },
        ids(mode: 'A' | 'AB') {
            return Array.from(new Set([...(candidates.get('A') ?? []), ...(mode === 'AB' ? candidates.get('B') ?? [] : [])])).sort((a, b) => a - b);
        },
        overlay(mode: 'A' | 'AB' | 'off') {
            if (busy) throw new Error('Diagnostic is busy');
            displayedIds = mode === 'off' ? null : api.ids(mode);
            scene.projectedSplatRenderer.setDiagnosticOverlay(splat, displayedIds);
        },
        focus() {
            return serial(async () => {
                checkScene();
                const ids = api.ids('AB');
                if (!ids.length) throw new Error('Map A first');
                const { resource } = splat;
                const rows = Uint32Array.from(ids, id => splat.instances.sourceRow[id]);
                const position = resource.sourcePool.acquire('position', resource.source.meta.layouts.position, rows.length);
                try {
                    await resource.source.read({ indices: rows, indexOffset: 0, count: rows.length, position });
                    const xyz = new Float32Array(position.data, 0, rows.length * 3);
                    const median = (axis: number) => Array.from(ids, (_, i) => xyz[i * 3 + axis]).sort((a, b) => a - b)[Math.floor(ids.length / 2)];
                    const target = splat.entity.getWorldTransform().transformPoint(new Vec3(median(0), median(1), median(2)));
                    const eye = cameraPose(views[0], splat.entity.getWorldTransform()).position.sub(target).mulScalar(0.25).add(target);
                    scene.camera.setPose(eye, target, 0);
                    scene.forceRender = true;
                } finally {
                    position.release();
                }
            });
        },
        report() {
            return structuredClone(report);
        },
        async checkIdentity() {
            if (busy) throw new Error('Diagnostic is busy');
            busy = true;
            try {
                const result = await checkNativeIdentity(scene, splat);
                report.identity = result;
                return result;
            } finally {
                busy = false;
            }
        },
        splat() {
            return splat;
        }
    };
    scene.events.function('nativeMaskDiagnostic', () => api);
};

export { registerNativeMaskDiagnostic };
