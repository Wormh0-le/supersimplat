const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectMaskController
} = require('../.test-dist/src/ai-select/mask-controller.js');
const {
    aiSelectEvidencePolicyVersion
} = require('../.test-dist/src/ai-select/evidence-state.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const target = (splatId = 'editor-splat:1') => ({ splatId });

const snapshot = {
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1'
    }
};

const editorCamera = () => ({
    targetSize: { width: 64, height: 48 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
    }
});

const cameraBinding = () => captureEditorCameraBinding(editorCamera());

const pngCrc32 = (bytes) => {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
};

const pngChunk = (type, data) => {
    const typeBytes = Buffer.from(type, 'ascii');
    const payload = Buffer.concat([typeBytes, data]);
    const length = Buffer.alloc(4);
    const checksum = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    checksum.writeUInt32BE(pngCrc32(payload));
    return Buffer.concat([length, payload, checksum]);
};

const pngBase64 = (width, height) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    return Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]).toString('base64');
};

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const input = (overrides = {}) => ({
    target: target(),
    dependencyToken: dependency(),
    getCurrentDependencyToken: () => dependency(),
    snapshot,
    cameraBinding: cameraBinding(),
    ...overrides
});

const bitsetArtifact = (width, height, foreground = [[2, 2]]) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    for (const [x, y] of foreground) {
        const index = y * width + x;
        bytes[index >> 3] |= 1 << (index % 8);
    }
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    });
};

const maskResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    viewId: request.viewId,
    maskAttemptId: request.maskAttemptId,
    rgbDigest: request.rgb.digest,
    mask: bitsetArtifact(request.rgb.width, request.rgb.height),
    maskSource: 'single-frame-sam',
    modelManifestDigest: request.modelManifestDigest,
    ...overrides
});

const setup = async (options = {}) => {
    let rgbDigest = options.rgbDigest ?? `sha256:${'a'.repeat(64)}`;
    const renderRequests = [];
    const renderer = {
        renderAnchor: (request) => {
            renderRequests.push(request);
            return Promise.resolve({
                requestBinding: request.requestBinding,
                targetSplatId: request.target.splatId,
                sceneId: request.snapshot.sceneId,
                sceneVersion: request.snapshot.sceneVersion,
                renderConfigVersion: 'supersplat-effective-rgb-v1',
                renderAttemptId: request.renderAttemptId,
                viewId: 'anchor-view',
                cameraBinding: request.cameraBinding,
                rgb: {
                    pngBase64: pngBase64(
                        request.cameraBinding.projection.width,
                        request.cameraBinding.projection.height
                    ),
                    digest: rgbDigest,
                    width: request.cameraBinding.projection.width,
                    height: request.cameraBinding.projection.height
                },
                rgbRendererVersion: 'gsplat-rgb/v1',
                rendererId: 'gsplat'
            });
        }
    };
    const maskRequests = [];
    const maskProvider = {
        produceMask:
            options.produceMask ??
            ((request) => {
                maskRequests.push(request);
                return Promise.resolve(maskResponseFor(request));
            })
    };
    const anchor = new AISelectAnchorController({ renderer });
    await anchor.start(input());
    const mask = new AISelectMaskController({
        anchor,
        maskProvider,
        getModelManifestDigest: () =>
            'modelManifestDigest' in options
                ? options.modelManifestDigest
                : 'manifest-digest-1',
        ...(options.isAnchorLocked === undefined
            ? {}
            : { isAnchorLocked: options.isAnchorLocked })
    });
    return {
        anchor,
        mask,
        maskRequests,
        renderRequests,
        setRgbDigest: (digest) => {
            rgbDigest = digest;
        }
    };
};

test('a prompt change automatically requests single-frame SAM feedback', async () => {
    const { mask, maskRequests } = await setup();
    assert.equal(maskRequests.length, 0);
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(maskRequests.length, 1);
    const request = maskRequests[0];
    assert.equal(request.viewId, 'anchor-view');
    assert.equal(request.prompts.length, 1);
    assert.equal(request.prompts[0].polarity, 'include');
    assert.ok(request.maskAttemptId.length > 0);
    assert.equal(request.rgb.digest, `sha256:${'a'.repeat(64)}`);
    assert.equal(mask.state.editingMask.source, 'single-frame-sam');
    assert.equal(mask.state.editingMask.status, 'draft');
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.evidence.status, 'not-requested');
});

test('each new prompt submits the full prompt set as the latest-only request', async () => {
    const gate = deferred();
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            if (maskRequests.length === 1) {
                return gate.promise;
            }
            return Promise.resolve(maskResponseFor(request));
        }
    });
    const first = mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const second = mask.addPrompt({ xPx: 20, yPx: 22, polarity: 'exclude' });
    assert.equal(maskRequests.length, 2);
    assert.deepEqual(
        maskRequests[1].prompts.map((prompt) => [prompt.xPx, prompt.yPx]),
        [
            [10, 12],
            [20, 22]
        ]
    );
    // The superseded first response is stale and must not publish.
    const staleMask = bitsetArtifact(64, 48, [[40, 40]]);
    gate.resolve(maskResponseFor(maskRequests[0], { mask: staleMask }));
    await first;
    await second;
    const editing = mask.state.editingMask;
    assert.equal(editing.prompts.length, 2);
    assert.notEqual(editing.artifact.digest, staleMask.digest);
    assert.equal(mask.state.requestStatus, 'idle');
});

test('SAM output never silently overwrites the Stable Mask', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    assert.equal(stable.status, 'user-confirmed');
    await mask.addPrompt({ xPx: 30, yPx: 30, polarity: 'exclude' });
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    assert.notEqual(mask.state.editingMask.maskId, stable.maskId);
});

test('a brush stroke updates the Editing Mask locally and supersedes in-flight SAM', async () => {
    const gate = deferred();
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return gate.promise;
        }
    });
    const pending = mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.applyBrushStroke({ xPx: 8, yPx: 8, radiusPx: 2, mode: 'add' });
    const brushed = mask.state.editingMask;
    assert.equal(brushed.source, 'manual');
    assert.equal(mask.state.requestStatus, 'idle');
    gate.resolve(maskResponseFor(maskRequests[0]));
    await pending;
    // The late SAM response must not clobber the local brush edit.
    assert.equal(mask.state.editingMask.maskId, brushed.maskId);
});

test('a brush stroke on a SAM Editing Mask creates a hybrid local revision', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const sam = mask.state.editingMask;
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    const hybrid = mask.state.editingMask;
    assert.equal(hybrid.source, 'hybrid');
    assert.equal(hybrid.parentMaskId, sam.maskId);
    assert.notEqual(hybrid.artifact.digest, sam.artifact.digest);
});

test('Confirm Mask atomically publishes the Editing Mask as a new Stable revision', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const editing = mask.state.editingMask;
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    assert.equal(stable.status, 'user-confirmed');
    assert.equal(stable.source, 'single-frame-sam');
    assert.equal(stable.parentMaskId, editing.maskId);
    assert.equal(stable.artifact.digest, editing.artifact.digest);
    assert.equal(stable.createdFromRgbDigest, `sha256:${'a'.repeat(64)}`);
    assert.equal(mask.state.editingMask.maskId, editing.maskId);
});

test('Confirm Mask invalidates dependent Evidence only at publication', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.confirmEditingMask();
    const firstStable = mask.state.stableMask;
    mask.evidenceRegistry.markReady({
        viewId: 'anchor-view',
        rgbDigest: firstStable.createdFromRgbDigest,
        stableMaskDigest: firstStable.artifact.digest,
        evidencePolicyDigest: aiSelectEvidencePolicyVersion
    });
    // Before the next Confirm, the previous Stable Mask and Evidence stay current.
    assert.equal(mask.state.evidence.status, 'ready');
    mask.applyBrushStroke({ xPx: 20, yPx: 20, radiusPx: 2, mode: 'add' });
    assert.equal(mask.state.evidence.status, 'ready');
    mask.confirmEditingMask();
    assert.equal(mask.state.evidence.status, 'stale');
    assert.notEqual(mask.state.stableMask.maskId, firstStable.maskId);
    assert.equal(mask.state.editingMask.source, 'hybrid');
});

test('a fully manual mask uses the same publication contract as SAM output', async () => {
    const { mask } = await setup();
    mask.applyBrushStroke({ xPx: 8, yPx: 8, radiusPx: 2, mode: 'add' });
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    assert.equal(stable.source, 'manual');
    assert.equal(stable.status, 'user-confirmed');
});

test('Mask failure keeps the RGB Ready view and permits retry and manual recovery', async () => {
    let failures = 0;
    const maskRequests = [];
    const { anchor, mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            if (failures < 1) {
                failures += 1;
                return Promise.reject(new Error('SAM failed.'));
            }
            return Promise.resolve(maskResponseFor(request));
        }
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.errorMessage, 'SAM failed.');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');

    await mask.retryMaskRequest();
    assert.equal(maskRequests.length, 2);
    // An explicit Retry mints a new attempt identity for the same prompt set.
    assert.notEqual(
        maskRequests[1].maskAttemptId,
        maskRequests[0].maskAttemptId
    );
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.editingMask.source, 'single-frame-sam');
});

test('an invalid SAM response binding fails the request, not the View', async () => {
    const { anchor, mask } = await setup({
        produceMask: (request) =>
            Promise.resolve(
                maskResponseFor(request, { maskAttemptId: 'stale-attempt' })
            )
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('a structurally invalid SAM response fails the request, not the View', async () => {
    const { anchor, mask } = await setup({
        produceMask: () => Promise.resolve({ status: 'complete' })
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('a missing Model Manifest reports a Mask failure without touching RGB', async () => {
    const { anchor, mask } = await setup({ modelManifestDigest: null });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.match(mask.state.errorMessage, /Model Manifest/);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('Restart Current Target disposes all target-local Mask state', async () => {
    const { anchor, mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.confirmEditingMask();
    assert.ok(mask.state.stableMask);
    await anchor.restart(input());
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.prompts.length, 0);
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.evidence.status, 'not-requested');
});

test('a new Anchor RGB identity resets prompts and Mask currency', async () => {
    const { anchor, mask, setRgbDigest } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.confirmEditingMask();
    assert.ok(mask.state.stableMask);

    setRgbDigest(`sha256:${'b'.repeat(64)}`);
    anchor.updateAnchorCameraPose([
        1, 0, 0, 9, 0, 1, 0, 9, 0, 0, 1, 9, 0, 0, 0, 1
    ]);
    await anchor.renderFinalPreview();
    assert.equal(mask.state.prompts.length, 0);
    // Old Mask versions are retained but never attach to changed RGB.
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.stableMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('prompt and brush validation requires an RGB Ready Anchor', async () => {
    const { anchor, mask } = await setup();
    await assert.rejects(
        mask.addPrompt({ xPx: 100, yPx: 12, polarity: 'include' })
    );
    await assert.rejects(
        mask.addPrompt({ xPx: 1.5, yPx: 12, polarity: 'include' })
    );
    anchor.exit();
    await assert.rejects(
        mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' })
    );
    assert.throws(() =>
        mask.applyBrushStroke({ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' })
    );
    assert.throws(() => mask.confirmEditingMask());
});

test('Clear replaces only the Editing Mask and supersedes in-flight SAM', async () => {
    const gate = deferred();
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return gate.promise;
        }
    });
    const pending = mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.clearEditingMask();
    const cleared = mask.state.editingMask;
    assert.equal(cleared.source, 'manual');
    assert.equal(cleared.status, 'draft');
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.hasUnconfirmedChanges, true);
    gate.resolve(maskResponseFor(maskRequests[0]));
    await pending;
    // The late SAM response must not clobber the cleared draft.
    assert.equal(mask.state.editingMask.maskId, cleared.maskId);
    // A Stable Mask from an earlier Confirm survives Clear.
    mask.applyBrushStroke({ xPx: 8, yPx: 8, radiusPx: 2, mode: 'add' });
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    mask.clearEditingMask();
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    assert.notEqual(mask.state.editingMask.maskId, stable.maskId);
});

test('Restore Auto restores the latest valid SAM Mask and is disabled when none exists', async () => {
    const { mask } = await setup();
    assert.equal(mask.state.canRestoreAuto, false);
    assert.throws(() => mask.restoreAutoMask());
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const auto = mask.state.editingMask;
    mask.clearEditingMask();
    assert.equal(mask.state.canRestoreAuto, true);
    mask.restoreAutoMask();
    assert.equal(mask.state.editingMask.maskId, auto.maskId);
    // The current draft already is the latest auto Mask: nothing to restore.
    assert.equal(mask.state.canRestoreAuto, false);
});

test('mask-local Undo/Redo walks Editing history without touching the Stable Mask', async () => {
    const { mask } = await setup();
    assert.equal(mask.state.canUndo, false);
    assert.equal(mask.state.canRedo, false);
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const sam = mask.state.editingMask;
    assert.equal(mask.state.canUndo, true);
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    const hybrid = mask.state.editingMask;

    mask.undoMaskEdit();
    assert.equal(mask.state.editingMask.maskId, sam.maskId);
    assert.equal(mask.state.canRedo, true);
    mask.undoMaskEdit();
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.canUndo, false);
    mask.redoMaskEdit();
    assert.equal(mask.state.editingMask.maskId, sam.maskId);
    mask.redoMaskEdit();
    assert.equal(mask.state.editingMask.maskId, hybrid.maskId);
    assert.equal(mask.state.canRedo, false);
    assert.equal(mask.state.stableMask, null);
});

test('a new local edit clears the Redo stack and branches from the restored draft', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const sam = mask.state.editingMask;
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    mask.undoMaskEdit();
    assert.equal(mask.state.canRedo, true);
    mask.applyBrushStroke({ xPx: 40, yPx: 40, radiusPx: 1, mode: 'erase' });
    assert.equal(mask.state.canRedo, false);
    assert.equal(mask.state.editingMask.parentMaskId, sam.maskId);
});

test('a confirmed Stable Mask is not an Undo step; Undo walks the draft chain', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const sam = mask.state.editingMask;
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    mask.undoMaskEdit();
    assert.equal(mask.state.editingMask.maskId, sam.maskId);
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
});

test('a new Anchor RGB identity resets mask-local Undo/Redo and Restore Auto', async () => {
    const { anchor, mask, setRgbDigest } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.applyBrushStroke({ xPx: 30, yPx: 30, radiusPx: 2, mode: 'add' });
    assert.equal(mask.state.canUndo, true);

    setRgbDigest(`sha256:${'b'.repeat(64)}`);
    anchor.updateAnchorCameraPose([
        1, 0, 0, 9, 0, 1, 0, 9, 0, 0, 1, 9, 0, 0, 0, 1
    ]);
    await anchor.renderFinalPreview();
    assert.equal(mask.state.canUndo, false);
    assert.equal(mask.state.canRedo, false);
    assert.equal(mask.state.canRestoreAuto, false);
    assert.equal(mask.state.hasUnconfirmedChanges, false);
});

test('a locked confirmed Anchor rejects every Mask mutation', async () => {
    let locked = false;
    const { mask } = await setup({ isAnchorLocked: () => locked });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    mask.confirmEditingMask();
    locked = true;
    await assert.rejects(
        mask.addPrompt({ xPx: 20, yPx: 20, polarity: 'include' })
    );
    assert.throws(() =>
        mask.applyBrushStroke({ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' })
    );
    assert.throws(() => mask.clearEditingMask());
    assert.throws(() => mask.restoreAutoMask());
    assert.throws(() => mask.undoMaskEdit());
    assert.throws(() => mask.redoMaskEdit());
    assert.throws(() => mask.confirmEditingMask());
    await assert.rejects(mask.retryMaskRequest());
    locked = false;
    mask.applyBrushStroke({ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' });
    assert.equal(mask.state.editingMask.source, 'hybrid');
});
