const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectGeneratedViewController,
    findKeyViewIdCollisions,
    planRegenerateMerge
} = require('../.test-dist/src/ai-select/generated-view-controller.js');
const {
    aiSelectGeneratedViewMaskPolicyVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    aiSelectLocalKeyViewPlannerVersion
} = require('../.test-dist/src/ai-select/local-key-view-plan.js');
const {
    aiSelectTargetGeometryPolicyVersion
} = require('../.test-dist/src/ai-select/target-geometry-hint.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    PerViewEvidenceRegistry
} = require('../.test-dist/src/ai-select/evidence-state.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    MaskAnnotationRegistry
} = require('../.test-dist/src/ai-select/mask-registry.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const target = () => ({ splatId: 'editor-splat:1' });

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

const rgbDigest = (letter) => `sha256:${letter.repeat(64)}`;

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

const bitsetArtifact = (width, height, foreground) => {
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

const anchorStableMaskAnnotation = (digest) =>
    Object.freeze({
        maskId: 'mask-anchor-stable',
        viewId: 'anchor-view',
        source: 'single-frame-sam',
        status: 'user-confirmed',
        artifact: bitsetArtifact(64, 48, [
            [4, 4],
            [5, 4]
        ]),
        createdFromRgbDigest: digest
    });

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const flush = () => new Promise((resolve) => setImmediate(resolve));

const anchorRenderResponseFor = (request) => ({
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
        digest: rgbDigest('a'),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

/** A controllable confirmation seam with the exact subscribe/state contract. */
const createConfirmationStub = () => {
    const listeners = new Set();
    let state = Object.freeze({
        validation: null,
        validationStatus: 'idle',
        confirmedAnchor: null
    });
    const publish = () => listeners.forEach((listener) => listener(state));
    return {
        get state() {
            return state;
        },
        subscribe(listener) {
            listeners.add(listener);
            listener(state);
            return () => listeners.delete(listener);
        },
        confirm(confirmedAnchor) {
            state = Object.freeze({ ...state, confirmedAnchor });
            publish();
        },
        adjust() {
            state = Object.freeze({ ...state, confirmedAnchor: null });
            publish();
        }
    };
};

const confirmedAnchorFor = (anchorController, overrides = {}) => {
    const { context, anchor } = anchorController.state;
    assert.ok(context && anchor?.renderStatus === 'ready' && anchor.rgb);
    return Object.freeze({
        targetContextId: context.targetContextId,
        contextRevision: context.revision,
        cameraBinding: anchor.cameraBinding,
        rgbDigest: anchor.rgb.digest,
        stableMask: anchorStableMaskAnnotation(anchor.rgb.digest),
        maskEvidencePolicyVersion: 'evidence-policy/pnv-v0',
        dependencyToken: context.dependencyToken,
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
        ...overrides
    });
};

const createHarness = (options = {}) => {
    const anchorController = new AISelectAnchorController({
        renderer: {
            renderAnchor: async (request) => anchorRenderResponseFor(request)
        }
    });
    const confirmation = createConfirmationStub();
    const maskRegistry = new MaskAnnotationRegistry();
    const evidenceRegistry = new PerViewEvidenceRegistry();
    const geometryHints = {
        calls: [],
        deferreds: [],
        produceTargetGeometryHint(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const planner = {
        calls: [],
        deferreds: [],
        planLocalKeyViews(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const viewRenderer = {
        calls: [],
        deferreds: [],
        renderView(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const maskProvider = {
        calls: [],
        deferreds: [],
        produceGeneratedViewMask(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const controller = new AISelectGeneratedViewController({
        anchor: anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        geometryHints,
        planner,
        renderer: viewRenderer,
        maskProvider,
        getModelManifestDigest: () => 'manifest-digest-1',
        supportsGeneratedViews: options.supportsGeneratedViews ?? (() => true)
    });
    return {
        anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        geometryHints,
        planner,
        viewRenderer,
        maskProvider,
        controller
    };
};

const startAnchor = async (harness) => {
    await harness.anchorController.start({
        target: target(),
        dependencyToken: dependency(),
        getCurrentDependencyToken: () => dependency(),
        snapshot,
        cameraBinding: cameraBinding()
    });
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');
};

const confirmAnchor = async (harness) => {
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    assert.equal(harness.geometryHints.calls.length, 1);
};

const hintArtifactFor = (request, overrides = {}) => ({
    schemaVersion: 1,
    targetContextId: request.requestBinding.targetContextId,
    anchorCameraBindingDigest: request.anchorCameraBindingDigest,
    anchorRgbDigest: request.anchorRgbDigest,
    anchorStableMaskDigest: request.anchorStableMask.digest,
    geometryPolicyDigest: rgbDigest('e'),
    centerWorld: [1, 2, 3],
    extentWorld: [0.5, 0.5, 0.5],
    visiblePoints: [[1, 2, 3]],
    quality: 'usable',
    reasons: [],
    artifactDigest: rgbDigest('f'),
    ...overrides
});

const hintResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    geometryAttemptId: request.geometryAttemptId,
    geometryPolicyVersion: aiSelectTargetGeometryPolicyVersion,
    hint: hintArtifactFor(request),
    ...overrides
});

const plannedKeyView = (viewId, revision, overrides = {}) => ({
    viewId,
    cameraBinding: Object.freeze({ ...cameraBinding(), revision }),
    quality: 'usable',
    reasons: [],
    ...overrides
});

const defaultViewsForBatch = (batchOrdinal) => [
    plannedKeyView(`key-view-${batchOrdinal}-0`, 100 + batchOrdinal * 10),
    plannedKeyView(`key-view-${batchOrdinal}-1`, 101 + batchOrdinal * 10)
];

const planResponseFor = (request, views) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    planAttemptId: request.planAttemptId,
    batchOrdinal: request.batchOrdinal,
    localViewPolicyVersion: aiSelectLocalKeyViewPlannerVersion,
    plan: {
        schemaVersion: 1,
        targetContextId: request.requestBinding.targetContextId,
        anchorStableMaskDigest: request.anchorStableMaskDigest,
        targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
        localViewPolicyDigest: rgbDigest('9'),
        orderedViews: views ?? defaultViewsForBatch(request.batchOrdinal),
        planAttemptId: request.planAttemptId,
        artifactDigest: rgbDigest('8')
    }
});

/** Resolve the pending hint and the pending plan batch 0 into 'active'. */
const driveToActive = async (harness, views) => {
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 1);
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0], views)
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'active');
};

const viewRenderResponseFor = (request, digest = rgbDigest('b')) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    renderAttemptId: request.renderAttemptId,
    viewId: request.viewId,
    cameraBinding: request.cameraBinding,
    rgb: {
        pngBase64: pngBase64(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height
        ),
        digest,
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

const maskResponseFor = (request, assessmentOverrides = {}) => {
    const mask = bitsetArtifact(64, 48, [
        [4, 4],
        [5, 4],
        [6, 4]
    ]);
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        maskAttemptId: request.maskAttemptId,
        rgbDigest: request.rgb.digest,
        anchorRgbDigest: request.anchor.rgbDigest,
        mask,
        maskSource: 'propagated',
        maskPropagation: {
            policyVersion: aiSelectGeneratedViewMaskPolicyVersion,
            projectedSupportCount: 9,
            promptCount: 3
        },
        assessment: {
            status: 'review',
            primaryReason: 'severely-fragmented',
            reasons: ['severely-fragmented'],
            actionableReasons: ['severely-fragmented'],
            policyVersion: 'local-view-assessment/v2',
            inputIdentity: {
                rgbDigest: request.rgb.digest,
                stableMaskDigest: mask.digest,
                assessmentPolicyVersion: 'local-view-assessment/v2'
            },
            diagnostics: {
                framePixels: 3072,
                foregroundPixels: 40,
                boundaryPixels: 0,
                boundaryContactRatio: 0,
                connectedComponents: 2,
                largestComponentRatio: 0.5,
                promptPointCount: 3,
                promptViolationCount: 0,
                boxSpillPixels: null,
                boxSpillRatio: null
            },
            ...assessmentOverrides
        },
        modelManifestDigest: request.modelManifestDigest
    };
};

/** Resolve the pending render and Mask of one View to full completion. */
const completeView = async (harness, renderIndex, digest) => {
    harness.viewRenderer.deferreds[renderIndex].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[renderIndex], digest)
    );
    await flush();
    harness.maskProvider.deferreds[
        harness.maskProvider.deferreds.length - 1
    ].resolve(
        maskResponseFor(
            harness.maskProvider.calls[harness.maskProvider.calls.length - 1]
        )
    );
    await flush();
};

/** Drive the whole happy path to two fully published Generated Views. */
const completeTwoViews = async (harness) => {
    await driveToActive(harness);
    assert.equal(harness.viewRenderer.calls.length, 1);
    await completeView(harness, 0, rgbDigest('b'));
    assert.equal(harness.viewRenderer.calls.length, 2);
    await completeView(harness, 1, rgbDigest('d'));
};

test('Confirm Anchor derives the Target Geometry Hint and plans the first bounded local batch', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.geometryHints.calls.length, 0);

    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();

    // The hint request runs first; planning waits for the bound hint.
    assert.equal(harness.controller.state.plannerStatus, 'planning');
    assert.equal(harness.geometryHints.calls.length, 1);
    assert.equal(harness.planner.calls.length, 0);
    const hintRequest = harness.geometryHints.calls[0];
    const context = harness.anchorController.state.context;
    assert.equal(
        hintRequest.requestBinding.targetContextId,
        context.targetContextId
    );
    assert.equal(hintRequest.requestBinding.contextRevision, context.revision);
    assert.deepEqual(hintRequest.requestBinding.dependencyToken, dependency());
    assert.equal(hintRequest.target.splatId, 'editor-splat:1');
    assert.equal(hintRequest.sceneId, snapshot.sceneId);
    assert.equal(hintRequest.sceneVersion, snapshot.sceneVersion);
    assert.equal(hintRequest.snapshot.sceneId, snapshot.sceneId);
    assert.equal(
        hintRequest.geometryAttemptId,
        'target-geometry-hint-attempt-1'
    );
    assert.match(
        hintRequest.anchorCameraBindingDigest,
        /^sha256:[a-f0-9]{64}$/
    );
    assert.equal(hintRequest.anchorRgbDigest, rgbDigest('a'));
    assert.equal(hintRequest.anchorStableMask.encoding, maskBitsetEncoding);
    assert.equal(
        hintRequest.geometryPolicyVersion,
        aiSelectTargetGeometryPolicyVersion
    );

    harness.geometryHints.deferreds[0].resolve(hintResponseFor(hintRequest));
    await flush();

    assert.equal(harness.planner.calls.length, 1);
    const planRequest = harness.planner.calls[0];
    assert.equal(planRequest.batchOrdinal, 0);
    assert.equal(planRequest.planAttemptId, 'local-key-view-plan-attempt-1');
    assert.equal(planRequest.targetGeometryHint.artifactDigest, rgbDigest('f'));
    assert.equal(
        planRequest.anchorStableMaskDigest,
        hintRequest.anchorStableMask.digest
    );
    assert.equal(planRequest.anchorRgbDigest, rgbDigest('a'));
    assert.equal(
        planRequest.anchorCameraBindingDigest,
        hintRequest.anchorCameraBindingDigest
    );
    assert.equal(
        planRequest.localViewPolicyVersion,
        aiSelectLocalKeyViewPlannerVersion
    );
    // The plan route is pure CPU on the hint: no scene payload crosses it.
    assert.equal(planRequest.snapshot, undefined);

    harness.planner.deferreds[0].resolve(planResponseFor(planRequest));
    await flush();

    const state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.equal(state.generationStopped, false);
    assert.equal(state.geometryHint.artifactDigest, rgbDigest('f'));
    assert.equal(state.geometryHint.quality, 'usable');
    assert.equal(state.keyViewPlans.length, 1);
    assert.equal(
        state.keyViewPlans[0].planAttemptId,
        'local-key-view-plan-attempt-1'
    );
    assert.equal(state.keyViewPlans[0].orderedViews.length, 2);
    assert.equal(state.views.length, 2);
    assert.equal(state.views[0].viewId, 'key-view-0-0');
    assert.equal(state.views[0].source, 'auto-generated');
    assert.equal(state.views[0].planQuality, 'usable');
    assert.deepEqual(state.views[0].planReasons, []);
});

test('a Generated AIView publishes RGB Ready while its Mask is still Generating', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness, [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-1', 101, {
            quality: 'limited',
            reasons: ['reducedVisibility']
        })
    ]);

    let views = harness.controller.state.views;
    assert.equal(views.length, 2);
    assert.equal(views[0].renderStatus, 'rendering');
    assert.equal(views[1].renderStatus, 'pending');
    // Planner diagnostics are per-View hints, never Mask or Evidence state.
    assert.equal(views[1].planQuality, 'limited');
    assert.deepEqual(views[1].planReasons, ['reducedVisibility']);

    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();

    views = harness.controller.state.views;
    // Progressive publication: RGB Ready + Mask Generating + Evidence Not
    // Requested is a legal state; the View never waits for its Mask.
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].rgbDigest, rgbDigest('b'));
    assert.equal(views[0].maskStatus, 'generating');
    assert.equal(views[0].evidenceStatus, 'not-requested');
    assert.equal(views[0].source, 'auto-generated');
    assert.equal(views[0].participation, 'excluded');
    assert.equal(views[1].renderStatus, 'pending');
    // The render request bound the exact planned CameraBinding and view id.
    assert.equal(harness.viewRenderer.calls[0].viewId, 'key-view-0-0');
    assert.deepEqual(
        harness.viewRenderer.calls[0].cameraBinding,
        plannedKeyView('key-view-0-0', 100).cameraBinding
    );

    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();
    views = harness.controller.state.views;
    assert.equal(views[0].maskStatus, 'ready');
    assert.ok(views[0].stableMaskId);
});

test('a successful automatic Mask atomically publishes an auto Stable Mask bound to the View RGB', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    const views = harness.controller.state.views;
    assert.equal(views.length, 2);
    assert.ok(views.every((view) => view.renderStatus === 'ready'));
    assert.ok(views.every((view) => view.maskStatus === 'ready'));

    const stable = harness.maskRegistry.viewState(
        'key-view-0-0',
        rgbDigest('b')
    ).stableMask;
    assert.ok(stable);
    assert.equal(stable.maskId, views[0].stableMaskId);
    assert.equal(stable.source, 'propagated');
    assert.equal(stable.status, 'auto-review');
    assert.equal(stable.createdFromRgbDigest, rgbDigest('b'));

    // The mask request bound the Generated View RGB, its exact CameraBinding,
    // and the confirmed Anchor Camera/RGB/Stable-Mask identity.
    const maskRequest = harness.maskProvider.calls[0];
    assert.equal(maskRequest.viewId, 'key-view-0-0');
    assert.equal(maskRequest.rgb.digest, rgbDigest('b'));
    assert.equal(maskRequest.anchor.rgbDigest, rgbDigest('a'));
    assert.equal(maskRequest.anchor.stableMask.encoding, maskBitsetEncoding);
    assert.deepEqual(
        maskRequest.anchor.cameraBinding,
        harness.anchorController.state.anchor.cameraBinding
    );

    // Publishing the Stable Mask marks Evidence missing/dirty only; no Lift.
    assert.equal(views[0].evidenceStatus, 'not-requested');
    assert.equal(views[0].assessment.status, 'review');
    assert.deepEqual(views[0].assessment.reasons, ['severely-fragmented']);
    assert.equal(views[0].maskQuality, 'auto-review');
    assert.equal(views[0].participation, 'excluded');
});

test('Auto Good defaults Included while View source remains non-authoritative', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0], {
            status: 'good',
            primaryReason: undefined,
            reasons: [],
            actionableReasons: []
        })
    );
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.source, 'auto-generated');
    assert.equal(view.maskQuality, 'auto-good');
    assert.equal(view.participation, 'included');
});

test('Assessment Failed preserves the Stable Mask but remains Excluded without reasons', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    const response = maskResponseFor(harness.maskProvider.calls[0], {
        status: 'failed',
        primaryReason: undefined,
        reasons: [],
        actionableReasons: [],
        diagnostics: undefined
    });
    harness.maskProvider.deferreds[0].resolve(response);
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'ready');
    assert.ok(view.stableMaskId);
    assert.equal(view.assessment.status, 'failed');
    assert.deepEqual(view.assessment.reasons, []);
    assert.equal(view.maskQuality, 'failed');
    assert.equal(view.participation, 'excluded');
});

test('Confirm Review as-is publishes User Confirmed authority and Included participation', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    harness.controller.confirmReviewAsIs('key-view-0-0');

    const view = harness.controller.state.views[0];
    assert.equal(view.assessment, undefined);
    assert.equal(view.maskQuality, 'user-confirmed');
    assert.equal(view.participation, 'included');
    const stable = harness.maskRegistry.viewState(
        'key-view-0-0',
        rgbDigest('b')
    ).stableMask;
    assert.equal(stable.status, 'user-confirmed');

    harness.controller.setViewParticipation('key-view-0-0', 'excluded');
    assert.equal(harness.controller.state.views[0].participation, 'excluded');
    assert.equal(
        harness.controller.state.views[0].maskQuality,
        'user-confirmed'
    );
});

test('a replacement Stable Mask hides assessment reasons bound to the previous revision', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0], {
            status: 'good',
            primaryReason: undefined,
            reasons: [],
            actionableReasons: []
        })
    );
    await flush();
    assert.equal(harness.controller.state.views[0].participation, 'included');

    harness.maskRegistry.publishAutoStable({
        viewId: 'key-view-0-0',
        rgbDigest: rgbDigest('b'),
        artifact: bitsetArtifact(64, 48, [[20, 20]]),
        source: 'propagated',
        status: 'auto-review'
    });

    const view = harness.controller.state.views[0];
    assert.equal(view.assessment, undefined);
    assert.equal(view.maskQuality, 'auto-review');
    assert.equal(view.participation, 'excluded');
});

test('Mask failure keeps the AIView, RGB, and frustum binding: RGB Ready + Mask Failed', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].reject(new Error('SAM exploded'));
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'failed');
    assert.match(view.maskErrorMessage, /SAM exploded/);
    assert.equal(view.rgbDigest, rgbDigest('b'));
    assert.equal(view.stableMaskId, undefined);
    assert.equal(view.participation, 'excluded');
    assert.equal(view.maskQuality, 'failed');

    harness.viewRenderer.deferreds[1].reject(new Error('skip second view'));
    await flush();
    harness.controller.retryViewMask('key-view-0-0');
    await flush();
    assert.equal(harness.maskProvider.calls.length, 2);
    assert.notEqual(
        harness.maskProvider.calls[1].maskAttemptId,
        harness.maskProvider.calls[0].maskAttemptId
    );
    assert.equal(harness.controller.state.views[0].maskStatus, 'generating');
});

test('Render failure preserves a distinct failed View record; completed Views survive', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);

    // First view completes fully.
    await completeView(harness, 0, rgbDigest('b'));
    // Second view render fails.
    harness.viewRenderer.deferreds[1].reject(new Error('GPU OOM'));
    await flush();

    const views = harness.controller.state.views;
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].maskStatus, 'ready');
    assert.equal(views[1].renderStatus, 'failed');
    assert.match(views[1].renderErrorMessage, /GPU OOM/);
    assert.equal(views[1].maskStatus, 'none');
    assert.equal(views[1].rgbDigest, undefined);
});

test('a true Render Retry creates a new attempt for the same CameraBinding and actually re-renders', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].reject(new Error('transient'));
    await flush();

    // The failed first View does not block the second View's pipeline.
    harness.viewRenderer.deferreds[1].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[1], rgbDigest('d'))
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    const failed = harness.controller.state.views[0];
    assert.equal(failed.renderStatus, 'failed');
    const firstAttemptId = harness.viewRenderer.calls[0].renderAttemptId;

    harness.controller.retryViewRender('key-view-0-0');
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 3);
    const retryRequest = harness.viewRenderer.calls[2];
    assert.equal(retryRequest.viewId, 'key-view-0-0');
    assert.notEqual(retryRequest.renderAttemptId, firstAttemptId);
    assert.deepEqual(
        retryRequest.cameraBinding,
        harness.viewRenderer.calls[0].cameraBinding
    );

    harness.viewRenderer.deferreds[2].resolve(
        viewRenderResponseFor(retryRequest)
    );
    await flush();
    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'generating');
});

test('a hint failure fails planning closed, preserves the Anchor, and exposes a true Retry', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].reject(new Error('geometry exploded'));
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /geometry exploded/
    );
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.controller.state.keyViewPlans.length, 0);
    // The confirmed Anchor survives every planning failure (§24).
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');

    harness.controller.retryPlanning();
    await flush();
    assert.equal(harness.geometryHints.calls.length, 2);
    assert.equal(
        harness.geometryHints.calls[1].geometryAttemptId,
        'target-geometry-hint-attempt-2'
    );
    harness.geometryHints.deferreds[1].resolve(
        hintResponseFor(harness.geometryHints.calls[1])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 1);
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'active');
    assert.equal(harness.controller.state.views.length, 2);
});

test('an invalid or stale hint response fails planning closed', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0], {
            geometryAttemptId: 'forged-attempt'
        })
    );
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /invalid or stale Target Geometry Hint binding/
    );
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');
});

test('an initial plan failure fails planning closed and preserves the Anchor', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 1);
    harness.planner.deferreds[0].reject(new Error('planner exploded'));
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /planner exploded/
    );
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.keyViewPlans.length, 0);
    // The bound hint and the confirmed Anchor survive a plan failure (§24).
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');

    // A true planning Retry re-runs the full hint + plan pipeline with new
    // attempt identities.
    harness.controller.retryPlanning();
    await flush();
    assert.equal(harness.geometryHints.calls.length, 2);
    assert.notEqual(
        harness.geometryHints.calls[1].geometryAttemptId,
        harness.geometryHints.calls[0].geometryAttemptId
    );
    harness.geometryHints.deferreds[1].resolve(
        hintResponseFor(harness.geometryHints.calls[1])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    assert.notEqual(
        harness.planner.calls[1].planAttemptId,
        harness.planner.calls[0].planAttemptId
    );
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'active');
    assert.equal(harness.controller.state.views.length, 2);
});

test('an invalid or stale initial plan response fails planning closed', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    const stale = planResponseFor(harness.planner.calls[0]);
    stale.planAttemptId = 'forged-attempt';
    harness.planner.deferreds[0].resolve(stale);
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /invalid or stale local Key-View plan binding/
    );
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');
});

test('Stop preserves completed Views while queued pending renders skip and stay pending', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness, [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-1', 101),
        plannedKeyView('key-view-0-2', 102)
    ]);

    await completeView(harness, 0, rgbDigest('b'));
    // The second View is in flight when generation stops.
    assert.equal(harness.viewRenderer.calls.length, 2);
    harness.controller.stopGeneration();
    assert.equal(harness.controller.state.generationStopped, true);
    assert.equal(harness.controller.state.plannerStatus, 'active');
    assert.throws(() => harness.controller.stopGeneration());

    // An in-flight identity-bound result may still publish; the queued third
    // View's render step skips while stopped and the View stays pending.
    await completeView(harness, 1, rgbDigest('d'));
    await flush();

    const views = harness.controller.state.views;
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].maskStatus, 'ready');
    assert.equal(views[1].renderStatus, 'ready');
    assert.equal(views[1].maskStatus, 'ready');
    assert.equal(views[2].renderStatus, 'pending');
    assert.equal(views[2].rgbDigest, undefined);
    assert.equal(harness.viewRenderer.calls.length, 2);
    assert.equal(harness.controller.state.generationStopped, true);
});

test('a true Render Retry still runs while generation is stopped', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].reject(new Error('transient'));
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 2);

    harness.controller.stopGeneration();
    // The second View was already in flight: its result still publishes.
    await completeView(harness, 1, rgbDigest('d'));

    let views = harness.controller.state.views;
    assert.equal(views[0].renderStatus, 'failed');
    assert.equal(views[1].renderStatus, 'ready');
    assert.equal(harness.viewRenderer.calls.length, 2);

    // An explicit user Retry is not a queued pipeline step: it always
    // re-executes the render path, even while stopped.
    const firstAttemptId = harness.viewRenderer.calls[0].renderAttemptId;
    harness.controller.retryViewRender('key-view-0-0');
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 3);
    assert.equal(harness.viewRenderer.calls[2].viewId, 'key-view-0-0');
    assert.notEqual(
        harness.viewRenderer.calls[2].renderAttemptId,
        firstAttemptId
    );

    await completeView(harness, 2, rgbDigest('b'));
    views = harness.controller.state.views;
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].maskStatus, 'ready');
    assert.equal(harness.controller.state.generationStopped, true);
});

test('Generate More appends a bounded batch without dirtying completed Views', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);
    const completedMaskId = harness.controller.state.views[0].stableMaskId;

    harness.controller.generateMoreViews();
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    const moreRequest = harness.planner.calls[1];
    assert.equal(moreRequest.batchOrdinal, 1);
    assert.notEqual(
        moreRequest.planAttemptId,
        harness.planner.calls[0].planAttemptId
    );
    // Generate More replans from the same bound Target Geometry Hint.
    assert.equal(moreRequest.targetGeometryHint.artifactDigest, rgbDigest('f'));

    harness.planner.deferreds[1].resolve(planResponseFor(moreRequest));
    await flush();

    const state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.equal(state.plannerErrorMessage, undefined);
    assert.equal(state.views.length, 4);
    // Completed Views never move: identity, RGB, Mask, and Participation are
    // exactly what the first batch published.
    assert.equal(state.views[0].viewId, 'key-view-0-0');
    assert.equal(state.views[0].renderStatus, 'ready');
    assert.equal(state.views[0].rgbDigest, rgbDigest('b'));
    assert.equal(state.views[0].maskStatus, 'ready');
    assert.equal(state.views[0].stableMaskId, completedMaskId);
    assert.equal(state.views[1].viewId, 'key-view-0-1');
    assert.equal(state.views[1].renderStatus, 'ready');
    assert.equal(state.views[1].rgbDigest, rgbDigest('d'));
    assert.equal(state.views[1].maskStatus, 'ready');
    // The new batch appends and the accepted plan list grows in order.
    assert.equal(state.views[2].viewId, 'key-view-1-0');
    assert.equal(state.views[3].viewId, 'key-view-1-1');
    assert.equal(state.keyViewPlans.length, 2);
    assert.equal(
        state.keyViewPlans[1].planAttemptId,
        moreRequest.planAttemptId
    );
    assert.deepEqual(
        state.keyViewPlans[1].orderedViews.map((view) => view.viewId),
        ['key-view-1-0', 'key-view-1-1']
    );
    // Only the new Views enter the render pipeline.
    assert.equal(harness.viewRenderer.calls.length, 3);
    assert.equal(harness.viewRenderer.calls[2].viewId, 'key-view-1-0');

    await completeView(harness, 2, rgbDigest('1'));
    assert.equal(harness.viewRenderer.calls.length, 4);
    await completeView(harness, 3, rgbDigest('2'));
    const views = harness.controller.state.views;
    assert.ok(views.every((view) => view.renderStatus === 'ready'));
    assert.ok(views.every((view) => view.maskStatus === 'ready'));
});

test('Generate More clears Stop and re-enqueues pending Views', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);

    harness.controller.stopGeneration();
    // The first View was in flight and still publishes; the second View's
    // queued render skips and stays pending.
    await completeView(harness, 0, rgbDigest('b'));
    assert.equal(harness.viewRenderer.calls.length, 1);
    assert.equal(harness.controller.state.views[1].renderStatus, 'pending');

    harness.controller.generateMoreViews();
    await flush();
    assert.equal(harness.controller.state.generationStopped, false);
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1])
    );
    await flush();

    assert.equal(harness.controller.state.views.length, 4);
    // The pending View left behind by Stop renders before the new batch.
    assert.equal(harness.viewRenderer.calls.length, 2);
    assert.equal(harness.viewRenderer.calls[1].viewId, 'key-view-0-1');
    assert.equal(harness.controller.state.views[1].renderStatus, 'rendering');
});

test('Generate More fails closed on View identity collision', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    harness.controller.generateMoreViews();
    await flush();
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1], [
            plannedKeyView('key-view-0-0', 200)
        ])
    );
    await flush();

    let state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.match(
        state.plannerErrorMessage,
        /reused View identity key-view-0-0/
    );
    assert.equal(state.views.length, 2);
    assert.equal(state.views[0].rgbDigest, rgbDigest('b'));
    assert.equal(state.views[1].rgbDigest, rgbDigest('d'));
    assert.equal(state.keyViewPlans.length, 1);
    assert.equal(harness.viewRenderer.calls.length, 2);

    // A collision consumes no batch ordinal: the next success plans the same
    // ordinal with a new attempt and clears the diagnostic.
    harness.controller.generateMoreViews();
    await flush();
    assert.equal(harness.planner.calls.length, 3);
    assert.equal(harness.planner.calls[2].batchOrdinal, 1);
    harness.planner.deferreds[2].resolve(
        planResponseFor(harness.planner.calls[2])
    );
    await flush();
    state = harness.controller.state;
    assert.equal(state.plannerErrorMessage, undefined);
    assert.equal(state.views.length, 4);
    assert.equal(state.keyViewPlans.length, 2);
});

test('Generate More keeps the planner active with a diagnostic when the batch fails', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    harness.controller.generateMoreViews();
    await flush();
    harness.planner.deferreds[1].reject(
        new Error('planExhausted: no further bounded local Key-View batch')
    );
    await flush();

    let state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.match(state.plannerErrorMessage, /planExhausted/);
    assert.equal(state.views.length, 2);
    assert.ok(
        state.views.every(
            (view) =>
                view.renderStatus === 'ready' && view.maskStatus === 'ready'
        )
    );
    assert.equal(state.keyViewPlans.length, 1);

    // The next success clears the diagnostic.
    harness.controller.generateMoreViews();
    await flush();
    harness.planner.deferreds[2].resolve(
        planResponseFor(harness.planner.calls[2])
    );
    await flush();
    state = harness.controller.state;
    assert.equal(state.plannerErrorMessage, undefined);
    assert.equal(state.views.length, 4);
});

test('Regenerate preserves identical View identities and disposes dropped planner-owned Views', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);
    const keptMaskId = harness.controller.state.views[0].stableMaskId;
    harness.controller.selectView('key-view-0-1');

    harness.controller.regenerateViews();
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    const replan = harness.planner.calls[1];
    // Regenerate replans batch 0 with the same bound hint and a new attempt.
    assert.equal(replan.batchOrdinal, 0);
    assert.equal(replan.planAttemptId, 'local-key-view-plan-attempt-2');
    assert.equal(replan.targetGeometryHint.artifactDigest, rgbDigest('f'));

    harness.planner.deferreds[1].resolve(
        planResponseFor(replan, [
            plannedKeyView('key-view-0-0', 100),
            plannedKeyView('key-view-0-7', 107)
        ])
    );
    await flush();

    const state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.equal(state.views.length, 2);
    // The identical View identity keeps its completed RGB/Mask artifacts and
    // is never re-rendered.
    assert.equal(state.views[0].viewId, 'key-view-0-0');
    assert.equal(state.views[0].renderStatus, 'ready');
    assert.equal(state.views[0].rgbDigest, rgbDigest('b'));
    assert.equal(state.views[0].maskStatus, 'ready');
    assert.equal(state.views[0].stableMaskId, keptMaskId);
    assert.ok(
        harness.maskRegistry.viewState('key-view-0-0', rgbDigest('b'))
            .stableMask
    );
    // The dropped planner-owned View is disposed with its Mask; a disposed
    // selection clears.
    assert.equal(state.views[1].viewId, 'key-view-0-7');
    assert.equal(state.views[1].renderStatus, 'rendering');
    assert.equal(
        harness.maskRegistry.viewState('key-view-0-1', rgbDigest('d'))
            .stableMask,
        null
    );
    assert.equal(state.selectedViewId, null);
    // The accepted batch replaces the plan list and resets the ordinal.
    assert.equal(state.keyViewPlans.length, 1);
    assert.equal(
        state.keyViewPlans[0].planAttemptId,
        'local-key-view-plan-attempt-2'
    );
    assert.equal(harness.viewRenderer.calls.length, 3);
    assert.equal(harness.viewRenderer.calls[2].viewId, 'key-view-0-7');

    // The regenerated View renders through the normal pipeline.
    await completeView(harness, 2, rgbDigest('1'));
    assert.equal(harness.controller.state.views[1].renderStatus, 'ready');
    // The ordinal reset makes the next Generate More plan batch 1.
    harness.controller.generateMoreViews();
    await flush();
    assert.equal(harness.planner.calls.length, 3);
    assert.equal(harness.planner.calls[2].batchOrdinal, 1);
    harness.planner.deferreds[2].reject(new Error('done'));
    await flush();
});

test('Regenerate keeps every current View when replanning fails', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);
    harness.controller.selectView('key-view-0-0');

    harness.controller.regenerateViews();
    await flush();
    harness.planner.deferreds[1].reject(
        new Error('plannerFailure: zero accepted Views in batch')
    );
    await flush();

    const state = harness.controller.state;
    assert.equal(state.plannerStatus, 'active');
    assert.match(state.plannerErrorMessage, /plannerFailure/);
    assert.equal(state.views.length, 2);
    assert.equal(state.views[0].rgbDigest, rgbDigest('b'));
    assert.equal(state.views[0].maskStatus, 'ready');
    assert.equal(state.views[1].rgbDigest, rgbDigest('d'));
    assert.equal(state.keyViewPlans.length, 1);
    assert.equal(state.selectedViewId, 'key-view-0-0');
    assert.ok(
        harness.maskRegistry.viewState('key-view-0-1', rgbDigest('d'))
            .stableMask
    );
    assert.equal(harness.viewRenderer.calls.length, 2);
});

test('a late Generate More batch from a disposed run is discarded', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    harness.controller.generateMoreViews();
    await flush();
    assert.equal(harness.planner.calls.length, 2);

    harness.confirmation.adjust();
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.controller.state.keyViewPlans.length, 0);

    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.viewRenderer.calls.length, 2);
});

test('a late Regenerate batch from a disposed run is discarded', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    harness.controller.regenerateViews();
    await flush();
    assert.equal(harness.planner.calls.length, 2);

    harness.confirmation.adjust();
    await flush();
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.viewRenderer.calls.length, 2);
});

test('Adjust Anchor disposes every Generated View and discards late results', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);

    // The first View is mid-render when the Anchor confirmation is discarded.
    harness.confirmation.adjust();
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.controller.state.keyViewPlans.length, 0);

    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(
        harness.maskRegistry.viewState('key-view-0-0', rgbDigest('b'))
            .stableMask,
        null
    );
});

test('a late hint or plan response with an obsolete Anchor identity is discarded', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);

    // Adjust and re-confirm: the obsolete run's in-flight hint result is
    // discarded by run identity, then the replacement run plans again.
    harness.confirmation.adjust();
    await flush();
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    assert.equal(harness.geometryHints.calls.length, 1);

    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    assert.equal(harness.geometryHints.calls.length, 2);
    assert.equal(harness.planner.calls.length, 0);
    assert.equal(harness.controller.state.views.length, 0);

    harness.geometryHints.deferreds[1].resolve(
        hintResponseFor(harness.geometryHints.calls[1])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 1);
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'active');
    assert.equal(harness.controller.state.views.length, 2);
});

test('Restart disposes target-local Generated View and Mask state', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);
    assert.equal(harness.controller.state.views.length, 2);

    harness.confirmation.adjust();
    await harness.anchorController.restart({
        target: target(),
        dependencyToken: dependency(),
        getCurrentDependencyToken: () => dependency(),
        snapshot,
        cameraBinding: cameraBinding()
    });
    await flush();

    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.geometryHint, null);
    assert.equal(harness.controller.state.keyViewPlans.length, 0);
    assert.equal(harness.controller.state.generationStopped, false);
    assert.equal(
        harness.maskRegistry.viewState('key-view-0-0', rgbDigest('b'))
            .stableMask,
        null
    );
});

test('an unsupported Companion fails planning closed with an actionable diagnostic', async () => {
    const harness = createHarness({
        supportsGeneratedViews: () => false
    });
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();

    assert.equal(harness.geometryHints.calls.length, 0);
    assert.equal(harness.planner.calls.length, 0);
    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /does not advertise Target Geometry and local Key-View planning/
    );
});

test('View selection is explicit and read-only; unknown views are rejected', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);

    assert.equal(harness.controller.state.selectedViewId, null);
    harness.controller.selectView('key-view-0-1');
    assert.equal(harness.controller.state.selectedViewId, 'key-view-0-1');
    assert.ok(
        harness.controller.state.views.find(
            (view) => view.viewId === 'key-view-0-1'
        ).selected
    );
    harness.controller.selectView(null);
    assert.equal(harness.controller.state.selectedViewId, null);
    assert.throws(() => harness.controller.selectView('key-view-9-9'));
});

test('planner lifecycle commands require an active run', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    assert.throws(() => harness.controller.stopGeneration());
    assert.throws(() => harness.controller.generateMoreViews());
    assert.throws(() => harness.controller.regenerateViews());
    assert.throws(() => harness.controller.retryPlanning());

    await confirmAnchor(harness);
    // Planning has not produced a bound hint yet.
    assert.throws(() => harness.controller.generateMoreViews());
    assert.throws(() => harness.controller.regenerateViews());
    assert.throws(() => harness.controller.stopGeneration());
});

test('findKeyViewIdCollisions detects existing and intra-batch duplicates', () => {
    assert.deepEqual(
        findKeyViewIdCollisions(
            [{ viewId: 'key-view-0-0' }],
            [{ viewId: 'key-view-1-0' }]
        ),
        []
    );
    // A new batch may never reuse an existing View identity.
    assert.deepEqual(
        findKeyViewIdCollisions(
            [{ viewId: 'key-view-0-0' }, { viewId: 'user-view-1' }],
            [{ viewId: 'user-view-1' }]
        ),
        ['user-view-1']
    );
    assert.deepEqual(
        findKeyViewIdCollisions(
            [],
            [{ viewId: 'key-view-1-0' }, { viewId: 'key-view-1-0' }]
        ),
        ['key-view-1-0']
    );
    assert.deepEqual(
        findKeyViewIdCollisions(
            [{ viewId: 'key-view-0-0' }],
            [
                { viewId: 'key-view-1-0' },
                { viewId: 'key-view-0-0' },
                { viewId: 'key-view-1-0' }
            ]
        ),
        ['key-view-0-0', 'key-view-1-0']
    );
});

const existingView = (viewId, source, revision) => ({
    viewId,
    source,
    cameraBinding: Object.freeze({ ...cameraBinding(), revision })
});

test('planRegenerateMerge preserves identical identities and partitions drops and additions', () => {
    const existing = [
        existingView('key-view-0-0', 'auto-generated', 100),
        existingView('key-view-0-1', 'auto-generated', 101),
        existingView('user-view-1', 'user-added', 200)
    ];
    const merge = planRegenerateMerge(existing, [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-9', 109)
    ]);
    // The identical identity (viewId + CameraBinding) is kept untouched.
    assert.deepEqual(
        merge.preserved.map((view) => view.viewId),
        ['key-view-0-0']
    );
    // Dropped planner-owned Views are disposed; user-owned Views never are.
    assert.deepEqual(merge.disposedViewIds, ['key-view-0-1']);
    assert.deepEqual(
        merge.added.map((view) => view.viewId),
        ['key-view-0-9']
    );
    assert.deepEqual(merge.conflictingViewIds, []);

    // A reused viewId with a changed CameraBinding is a replacement, not a
    // preservation.
    const changed = planRegenerateMerge(existing, [
        plannedKeyView('key-view-0-0', 300)
    ]);
    assert.deepEqual(changed.preserved, []);
    assert.deepEqual(changed.disposedViewIds, ['key-view-0-0', 'key-view-0-1']);
    assert.deepEqual(
        changed.added.map((view) => view.viewId),
        ['key-view-0-0']
    );
});

test('planRegenerateMerge fails closed on user-owned and duplicate identity conflicts', () => {
    const existing = [
        existingView('key-view-0-0', 'auto-generated', 100),
        existingView('user-view-1', 'user-added', 200)
    ];
    // A planned View may never take over a user-owned identity.
    const userConflict = planRegenerateMerge(existing, [
        plannedKeyView('user-view-1', 200)
    ]);
    assert.deepEqual(userConflict.conflictingViewIds, ['user-view-1']);
    assert.deepEqual(userConflict.added, []);

    // Duplicate identities inside one batch conflict after the first.
    const duplicates = planRegenerateMerge(existing, [
        plannedKeyView('key-view-0-9', 109),
        plannedKeyView('key-view-0-9', 110)
    ]);
    assert.deepEqual(duplicates.conflictingViewIds, ['key-view-0-9']);
    assert.deepEqual(
        duplicates.added.map((view) => view.viewId),
        ['key-view-0-9']
    );
});
