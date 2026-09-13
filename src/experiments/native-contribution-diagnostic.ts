import { probeNativeTrace } from './native-contribution-probe';
import { cacheColor, classifySupport, compactSupport as legacyCompactSupport, compareTraceIdentity, CONTRIBUTION_LIMITS, halfToFloat, runContribution, runContributionTiled, type CacheSnapshot, type Contributor, type ROI, type TiledContributionOptions } from './native-contribution-reference';
import { compactSupport, type SupportStorageOptions } from './native-contribution-support';

// Chosen from A native RGB/mask only, before running any new B/C comparison.
const A_TRACE_PIXELS = [
    { pixel: [434, 516], reason: 'apple interior near stem' },
    { pixel: [446, 528], reason: 'red flesh interior' },
    { pixel: [414, 520], reason: 'left silhouette boundary' },
    { pixel: [434, 540], reason: 'bottom mask boundary' },
    { pixel: [434, 550], reason: 'table below apple / reported trailing contamination' },
    { pixel: [459, 536], reason: 'table next to right silhouette' },
    { pixel: [409, 547], reason: 'local table lower left' }
] as const;

// Fixed from A RGB/Mask geometry, before any plate support or B/C result.
// Bounding-box fractions, rounded to pixels; every sample is retained if a gate fails.
const plateTracePixels = (frame: ContributionFrame) => {
    const { mask, snapshot: { width, height } } = frame;
    let x0 = width, y0 = height, x1 = -1, y1 = -1;
    for (let p = 0; p < mask.length; p++) {
        if (!mask[p]) continue;
        x0 = Math.min(x0, p % width); x1 = Math.max(x1, p % width);
        y0 = Math.min(y0, Math.floor(p / width)); y1 = Math.max(y1, Math.floor(p / width));
    }
    if (x1 < 0) throw new Error('Empty plate Mask');
    const stencil: [number, number, string][] = [
        [0.2, 0.35, 'white plate interior left of cookies'],
        [0.5, 0.92, 'thin lower plate rim'],
        [0.57, 0.32, 'upper cookie occlusion hole'],
        [0.34, 0.67, 'lower cookie occlusion hole'],
        [0.5, 1.08, 'table below plate contact'],
        [-0.07, 0.5, 'table outside left silhouette'],
        [0.87, 0.58, 'thin boundary beside cookie exclusion seam']
    ];
    return stencil.map(([u, v, reason]) => ({
        pixel: [Math.round(x0 + u * (x1 - x0)), Math.round(y0 + v * (y1 - y0))] as const,
        reason: `${reason}; fixed bbox fraction (${u},${v}), rounded; A RGB/Mask only`
    }));
};

type ContributionFrame = { snapshot: CacheSnapshot; nativeHalf: Uint16Array; rgb: Uint8Array; mask: Uint8Array };

// Exact round-to-nearest-even binary16 storage model, not a new renderer.
const roundHalf = (value: number) => {
    if (value === 0) return 0;
    const step = 2 ** Math.max(-24, Math.floor(Math.log2(Math.abs(value))) - 10);
    const units = value / step;
    const low = Math.floor(units);
    return (units - low === 0.5 ? low + low % 2 : Math.round(units)) * step;
};

const blendTrace = (snapshot: CacheSnapshot, contributors: Contributor[]) => {
    const rgba = [0, 0, 0, 0];
    // Reverse the recorded near-to-far trace back to actual draw order.
    for (let i = contributors.length - 1; i >= 0; i--) {
        const { id, alpha } = contributors[i];
        const entry = id - snapshot.instanceBase + snapshot.entryBase;
        const color = cacheColor(snapshot.cacheA[entry * 4 + 2]);
        for (let c = 0; c < 4; c++) rgba[c] = roundHalf((c === 3 ? 1 : color[c]) * alpha + rgba[c] * (1 - alpha));
    }
    return rgba;
};

const traceContribution = async (frame: ContributionFrame, device: GPUDevice, points: readonly { pixel: readonly [number, number]; reason: string }[] = A_TRACE_PIXELS, checkHidden = points === A_TRACE_PIXELS) => {
    const start = performance.now();
    let hiddenLayerCheck: (Awaited<ReturnType<typeof probeNativeTrace>> & { passed: boolean }) | null = null;
    if (checkHidden) {
        const synthetic: CacheSnapshot = { cacheA: new Uint32Array([0, 0x3f800000, 1023 << 10, 0x3c00, 0, 0x3f800000, 1023, 0x3c00]),
            cacheB: new Uint32Array([0x803c00, 0xff3c00]),
            order: new Uint32Array([0, 1]),
            count: 2,
            entryBase: 0,
            instanceBase: 0,
            sourceRows: new Uint32Array([30, 80]),
            width: 1,
            height: 1 };
        const check = await probeNativeTrace(device, [{ pixel: [0, 0], contributors: [] }], 1, 1, synthetic);
        const fragments = check.results[0].fragments;
        hiddenLayerCheck = { passed: fragments.length === 2 && fragments[0].id === 0 && fragments[0].rgba[3] > 0 && fragments[1].id === 1 && fragments[1].rgba[3] === 1, ...check };
        if (!hiddenLayerCheck.passed) throw new Error('Independent GPU collector omitted a fully occluded contributor');
    }
    const samples = points.map(({ pixel: [x, y], reason }) => {
        const r = runContribution(frame.snapshot, { x, y, width: 1, height: 1 }, frame.mask, [[x, y]]);
        const { contributors } = r.traces[0];
        const offset = (y * frame.snapshot.width + x) * 4;
        const native = Array.from(frame.nativeHalf.subarray(offset, offset + 4), halfToFloat);
        const native8 = Array.from(frame.rgb.subarray(offset, offset + 4));
        const ideal = Array.from(r.rgba);
        const storageModel = blendTrace(frame.snapshot, contributors);
        const maxIdealError = Math.max(...ideal.map((v, c) => Math.abs(v - native[c])));
        const maxStorageError = Math.max(...storageModel.map((v, c) => Math.abs(v - native[c])));
        const maxByteError = Math.max(...storageModel.map((v, c) => Math.abs(Math.round(Math.max(0, Math.min(1, v)) * 255) - native8[c])));
        return { pixel: [x, y],
            reason,
            native,
            native8,
            ideal,
            storageModel,
            maxIdealError,
            maxStorageError,
            maxByteError,
            conservationError: Math.abs(r.total[0] + r.finalT[0] - 1),
            finalT: r.finalT[0],
            summary: r.summary,
            contributors: contributors.map((c) => {
                const entry = c.id - frame.snapshot.instanceBase + frame.snapshot.entryBase;
                return { ...c, cache: [...frame.snapshot.cacheA.subarray(entry * 4, entry * 4 + 4), frame.snapshot.cacheB[entry]] };
            }) };
    });
    const degenerateIds = samples[0].summary.degenerateEntries;
    const degenerateProbe = degenerateIds.length ? await probeNativeTrace(device, [{ pixel: [0, 0],
        fullFrame: true,
        contributors: degenerateIds.map((id) => {
            const entry = id - frame.snapshot.instanceBase + frame.snapshot.entryBase;
            return { id, alpha: 0, drawSlot: frame.snapshot.order.indexOf(entry), cache: [...frame.snapshot.cacheA.subarray(entry * 4, entry * 4 + 4), frame.snapshot.cacheB[entry]] };
        }) }], frame.snapshot.width, frame.snapshot.height) : null;
    // A fragment write always includes strictly positive gamma-encoded RGB.
    // Zero storage after a full-viewport replay demonstrates no fragment invocation.
    const degenerateNoFragments = !degenerateProbe || degenerateProbe.results[0].fragments.every(f => f.rgba.every(v => v === 0));
    const probe = await probeNativeTrace(device, samples, frame.snapshot.width, frame.snapshot.height, frame.snapshot);
    const comparison = probe.results.map((gpu, i) => {
        const sample = samples[i];
        const byId = new Map(sample.contributors.map(c => [c.id, c]));
        const identity = compareTraceIdentity(sample.contributors, gpu.fragments.slice().reverse());
        let T = 1, maxAlphaError = 0, maxWeightError = 0;
        const fragments = gpu.fragments.slice().reverse().map((c) => {
            const cpu = byId.get(c.id);
            const alpha = c.rgba[3], w = alpha * T;
            const incomingT = T;
            T *= 1 - alpha;
            if (cpu) {
                maxAlphaError = Math.max(maxAlphaError, Math.abs(alpha - cpu.alpha));
                maxWeightError = Math.max(maxWeightError, Math.abs(w - cpu.w));
            }
            return { ...c, sourceRow: frame.snapshot.sourceRows[c.id], alpha, T: incomingT, w };
        });
        const half = gpu.half.map(halfToFloat);
        const replayError = Math.max(...half.map((v, c) => Math.abs(v - sample.native[c])));
        const cpuByteError = Math.max(...sample.ideal.map((v, c) => Math.abs(Math.round(Math.max(0, Math.min(1, v)) * 255) - sample.native8[c])));
        return { pixel: sample.pixel, ...identity, half, replayError, cpuByteError, maxAlphaError, maxWeightError, fragments, finalT: T };
    });
    // No relaxation of the original .002 output tolerance: the real GPU blend
    // replay replaces an inadequate idealized half-storage model. Also bound the
    // CPU producer against independently rasterized alpha/w, to avoid qualifying
    // a correct replay with an incorrect ROI producer. 1/1024 is one half ULP
    // at unity; RGBA8 may differ by at most one code. All errors are reported.
    const tolerance = { rgba16f: 0.002, rgba8Codes: 1, alphaAndWeight: 1 / 1024, conservation: 1e-12 };
    const passed = comparison.every(s => s.drawOrderMatches && s.replayError <= tolerance.rgba16f && s.cpuByteError <= tolerance.rgba8Codes &&
        s.maxAlphaError <= tolerance.alphaAndWeight && s.maxWeightError <= tolerance.alphaAndWeight) &&
        samples.every(s => s.contributors.length > 0 && s.conservationError <= tolerance.conservation) && degenerateNoFragments;
    return { passed, tolerance, hiddenLayerCheck, samples, comparison, degenerateProbe, degenerateNoFragments, probeCost: probe.cost, elapsedMs: performance.now() - start, implementation: 'CPU cache reference, 8-bit raster grid; independent full-live-payload GPU fragment/blend oracle; no alpha gate or truncation' };
};

const maskROI = (mask: Uint8Array, width: number, height: number): ROI => {
    let x0 = width, y0 = height, x1 = -1, y1 = -1;
    for (let i = 0; i < mask.length; i++) {
        if (!mask[i]) continue;
        x0 = Math.min(x0, i % width); x1 = Math.max(x1, i % width);
        y0 = Math.min(y0, Math.floor(i / width)); y1 = Math.max(y1, Math.floor(i / width));
    }
    if (x1 < 0) throw new Error('Empty target mask');
    // Fixed A-chosen local margin, never full-screen negative evidence.
    x0 = Math.max(0, x0 - 16); y0 = Math.max(0, y0 - 16);
    x1 = Math.min(width - 1, x1 + 16); y1 = Math.min(height - 1, y1 + 16);
    return { x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1 };
};

export { A_TRACE_PIXELS, plateTracePixels, traceContribution, maskROI, roundHalf, blendTrace };
export type { ContributionFrame };

const regressionTracePixels = (frame: ContributionFrame) => {
    const { x, y, width, height } = maskROI(frame.mask, frame.snapshot.width, frame.snapshot.height);
    const cx = x + Math.floor(width / 2), cy = y + Math.floor(height / 2);
    return [[cx, cy], [x + 16, cy], [x + width - 17, cy], [cx, y + height - 17], [cx, y + height - 7]].map(pixel => ({ pixel: pixel as [number, number], reason: 'fixed ROI-relative numerical regression stencil; not selection/tuning evidence' }));
};
export { regressionTracePixels };

type ContributionAnalysis = Awaited<ReturnType<typeof analyzeContribution>>;

type AnalysisOptions = TiledContributionOptions & { output?: 'support' | 'metrics'; supportStorage?: SupportStorageOptions };
const analyzeContribution = async (frame: ContributionFrame, sets: readonly (readonly number[])[] = [], options: AnalysisOptions = {}) => {
    const { width, height } = frame.snapshot;
    const roi = maskROI(frame.mask, width, height);
    const current = () => {
        if (options.signal?.aborted) throw new Error('Contribution incomplete: cancelled');
        if (options.isCurrent && !options.isCurrent()) throw new Error('Contribution incomplete: stale target');
    };
    current();
    if (options.output !== undefined && !['support', 'metrics'].includes(options.output)) throw new Error('Invalid contribution output');
    const tiled = roi.width * roi.height > CONTRIBUTION_LIMITS.pixels || options.limits !== undefined;
    const result = tiled ? await runContributionTiled(frame.snapshot, roi, frame.mask, [], { ...options, selectionSets: sets }) :
        runContribution(frame.snapshot, roi, frame.mask, [], { selectionSets: sets });
    current();
    // Metrics still traverse every contributor and denominator, but own no fusion output.
    const supportStarted = performance.now();
    const support = options.output === 'metrics' ? undefined : compactSupport(result.stats, {
        ...options.supportStorage,
        // M1's retained winner list is bounded by ROI pixels, not support IDs.
        retainedBytes: (options.supportStorage?.retainedBytes ?? 0) + result.winnerIds.length * 8,
        signal: options.signal,
        isCurrent: options.isCurrent
    });
    const supportCopyMs = support ? performance.now() - supportStarted : 0;
    const metrics = sets.map((_, index) => {
        let target = 0, targetSelected = 0, negative = 0, negativeSelected = 0;
        for (let p = 0; p < result.total.length; p++) {
            const x = roi.x + p % roi.width, y = roi.y + Math.floor(p / roi.width);
            if (frame.mask[y * width + x]) {
                target += result.total[p]; targetSelected += result.selectedSums[index][p];
            }
            if (result.regions[p] === 2) {
                negative += result.total[p]; negativeSelected += result.selectedSums[index][p];
            }
        }
        return { target, targetSelected, targetRatio: target ? targetSelected / target : null, negative, negativeSelected, negativeRatio: negative ? negativeSelected / negative : null };
    });
    let conservationError = 0, maxRGBA8Error = 0, meanRGBA8Error = 0;
    for (let p = 0; p < result.total.length; p++) {
        conservationError = Math.max(conservationError, Math.abs(result.total[p] + result.finalT[p] - 1));
        const x = roi.x + p % roi.width, y = roi.y + Math.floor(p / roi.width);
        for (let c = 0; c < 4; c++) {
            const error = Math.abs(Math.round(Math.max(0, Math.min(1, result.rgba[p * 4 + c])) * 255) - frame.rgb[(y * width + x) * 4 + c]);
            maxRGBA8Error = Math.max(maxRGBA8Error, error); meanRGBA8Error += error;
        }
    }
    meanRGBA8Error /= result.total.length * 4;
    const qImages = result.selectedSums.map((values) => {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        const image = new ImageData(width, height);
        for (let p = 0; p < width * height; p++) image.data[p * 4 + 3] = 255;
        for (let p = 0; p < values.length; p++) {
            const x = roi.x + p % roi.width, y = roi.y + Math.floor(p / roi.width);
            const value = Math.round(Math.min(1, values[p]) * 255);
            image.data.set([value, value, value, 255], (y * width + x) * 4);
        }
        canvas.getContext('2d').putImageData(image, 0, 0);
        return canvas.toDataURL();
    });
    current();
    const winnerIds = support ? Object.freeze(Array.from(new Set(Array.from(result.winnerIds).filter(id => id >= 0))).sort((a, b) => a - b)) : undefined;
    return Object.freeze({ roi, support, winnerIds, supportBytes: support?.byteLength ?? 0, supportCopyMs, metrics, qImages, summary: result.summary, conservationError, maxRGBA8Error, meanRGBA8Error });
};

// Verification-only: retained two results are explicitly additional oracle memory.
const checkTiledContribution = async (frame: ContributionFrame, sets: readonly (readonly number[])[], isCurrent: () => boolean) => {
    const roi = maskROI(frame.mask, frame.snapshot.width, frame.snapshot.height);
    const monolithic = roi.width * roi.height <= CONTRIBUTION_LIMITS.pixels;
    const mono = monolithic ? runContribution(frame.snapshot, roi, frame.mask, [], { selectionSets: sets }) :
        await runContributionTiled(frame.snapshot, roi, frame.mask, [], { selectionSets: sets, isCurrent });
    const tilePixels = roi.width * Math.max(1, Math.min(Math.floor(roi.height / 3), Math.floor(CONTRIBUTION_LIMITS.pixels / roi.width)));
    const tiled = await runContributionTiled(frame.snapshot, roi, frame.mask, [], { selectionSets: sets, isCurrent, limits: { tilePixels } });
    const errors: Record<string, number> = {};
    const compare = (name: string, a: ArrayLike<number>, b: ArrayLike<number>) => {
        if (a.length !== b.length) throw new Error('Tiled comparison shape mismatch');
        let max = 0;
        for (let i = 0; i < a.length; i++) max = Math.max(max, Math.abs(a[i] - b[i]));
        errors[name] = max;
    };
    for (const key of ['regions', 'total', 'finalT', 'rgba', 'winnerIds'] as const) compare(key, mono[key], tiled[key]);
    for (const key of ['positive', 'negative', 'visible', 'target', 'touched'] as const) compare(key, mono.stats[key], tiled.stats[key]);
    mono.selectedSums.forEach((sum, i) => compare(`Q${i}`, sum, tiled.selectedSums[i]));
    let classificationDifferences = 0;
    for (let id = 0; id < mono.stats.positive.length; id++) {
        const a = classifySupport([{ positive: mono.stats.positive[id], negative: mono.stats.negative[id] }]);
        const b = classifySupport([{ positive: tiled.stats.positive[id], negative: tiled.stats.negative[id] }]);
        if (a.status !== b.status || a.conflict !== b.conflict) classificationDifferences++;
    }
    return { passed: Object.values(errors).every(error => error === 0) && classificationDifferences === 0, referenceMode: monolithic ? 'monolithic' : 'default-tiles', tolerance: 0, errors, classificationDifferences, mono: mono.summary, tiled: tiled.summary, additionalOracleTypedBytes: mono.summary.typedArrayBytes + tiled.summary.typedArrayBytes };
};
export { checkTiledContribution };

export { analyzeContribution };
export type { ContributionAnalysis };

// Verification-only on a borrowed frozen apple snapshot: old object rows vs columns,
// then support output vs metrics-only. No store publication and no native recapture.
export const checkStorageContribution = async (frame: ContributionFrame, sets: readonly (readonly number[])[], isCurrent: () => boolean) => {
    const roi = maskROI(frame.mask, frame.snapshot.width, frame.snapshot.height);
    const raw = runContribution(frame.snapshot, roi, frame.mask, [], { selectionSets: sets });
    const legacy = legacyCompactSupport(raw.stats);
    const table = compactSupport(raw.stats, { isCurrent });
    let rawDifferences = 0, classificationDifferences = 0;
    for (let i = 0; i < legacy.length; i++) {
        const row = table.row(i), old = legacy[i];
        if (Object.keys(old).some(key => row[key as keyof typeof row] !== old[key as keyof typeof old])) rawDifferences++;
        if (JSON.stringify(classifySupport([row])) !== JSON.stringify(classifySupport([old]))) classificationDifferences++;
    }
    const full = await analyzeContribution(frame, sets, { isCurrent });
    const metrics = await analyzeContribution(frame, sets, { output: 'metrics', supportStorage: { byteLimit: 0 }, isCurrent });
    const outputEqual = ['roi', 'metrics', 'qImages', 'conservationError', 'maxRGBA8Error', 'meanRGBA8Error'].every(key => JSON.stringify(full[key as keyof typeof full]) === JSON.stringify(metrics[key as keyof typeof metrics]));
    return { passed: legacy.length === table.length && rawDifferences === 0 && classificationDifferences === 0 && outputEqual && !metrics.support && !metrics.winnerIds,
        rawDifferences,
        classificationDifferences,
        outputEqual,
        rows: table.length,
        columnBytes: table.byteLength,
        metricsSupportBytes: metrics.supportBytes,
        additionalOracleTypedBytes: raw.summary.typedArrayBytes + Math.max(full.summary.typedArrayBytes, metrics.summary.typedArrayBytes) + table.byteLength + full.supportBytes,
        legacyObjectsAndPNGBytes: 'unmeasured; verification only' };
};
