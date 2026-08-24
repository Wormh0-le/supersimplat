const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectGeneratedViewController,
    findKeyViewIdCollisions
} = require('../.test-dist/src/ai-select/generated-view-controller.js');
const {
    aiSelectImageInstancePromptSynthesisPolicyDigest,
    aiSelectImageInstancePromptSynthesisPolicyVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    createImageInstanceMaskResult,
    createImageInstancePromptArtifact
} = require('../.test-dist/src/ai-select/image-instance-mask.js');
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
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');
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
    stableIds: new Uint32Array([1]),
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

const pngBase64 = (width, height, seed = 0) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    scanlines[1] = typeof seed === 'string' ? seed.charCodeAt(0) : seed;
    return Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]).toString('base64');
};

const pngDigest = (width, height, seed) =>
    sha256Digest(
        new Uint8Array(Buffer.from(pngBase64(width, height, seed), 'base64'))
    );

const rgbDigest = (letter) => pngDigest(64, 48, letter);

const pngBase64ForDigest = (width, height, digest) => {
    for (let seed = 0; seed <= 255; seed += 1) {
        const encoded = pngBase64(width, height, seed);
        if (
            sha256Digest(new Uint8Array(Buffer.from(encoded, 'base64'))) ===
            digest
        ) {
            return encoded;
        }
    }
    throw new Error('Test RGB digest was not created from the fixture PNG.');
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
            request.cameraBinding.projection.height,
            'a'
        ),
        digest: rgbDigest('a'),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
    rendererId: 'gsplat',
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    runtimeBuildId:
        'sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f',
    renderWorkingSetToken:
        request.snapshot.contentDigest ?? `sha256:${'f'.repeat(64)}`,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds ?? [1],
        Number
    ).sort((left, right) => left - right)
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
    let effectiveDependency = dependency();
    const anchorController = new AISelectAnchorController({
        renderer: {
            renderAnchor: async (request) => anchorRenderResponseFor(request)
        }
    });
    const confirmation = createConfirmationStub();
    const maskRegistry = new MaskAnnotationRegistry();
    const evidenceRegistry = new PerViewEvidenceRegistry();
    const dirtyState = new AISelectDirtyStateTracker();
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
    const promptSynthesizer = {
        calls: [],
        responseFactory: undefined,
        synthesizeGeneratedViewPrompt(request) {
            this.calls.push(request);
            return Promise.resolve(
                this.responseFactory?.(request) ?? promptResponseFor(request)
            );
        }
    };
    const maskProvider = {
        calls: [],
        deferreds: [],
        infer(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const reviewProvider = {
        calls: [],
        assessmentOverrides: undefined,
        reviewImageInstanceMask(request) {
            this.calls.push(request);
            return Promise.resolve(
                reviewResponseFor(request, this.assessmentOverrides)
            );
        }
    };
    const imageInstanceRuntimeBinding = {
        adapterId: 'sam3-image',
        modelManifestDigest: 'manifest-digest-1',
        runtimeDigest: rgbDigest('7'),
        companionInstanceId: 'companion-1',
        adapterCapabilityDigest: rgbDigest('6')
    };
    const controller = new AISelectGeneratedViewController({
        anchor: anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        dirtyState,
        geometryHints,
        planner,
        renderer: viewRenderer,
        promptSynthesizer,
        maskProvider,
        reviewProvider,
        getImageInstanceRuntimeBinding: () => imageInstanceRuntimeBinding,
        supportsGeneratedViews: options.supportsGeneratedViews ?? (() => true)
    });
    return {
        anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        dirtyState,
        geometryHints,
        planner,
        viewRenderer,
        promptSynthesizer,
        maskProvider,
        reviewProvider,
        imageInstanceRuntimeBinding,
        controller,
        getEffectiveDependency: () => effectiveDependency,
        setEffectiveDependency: (value) => {
            effectiveDependency = value;
        }
    };
};

const startAnchor = async (harness) => {
    await harness.anchorController.start({
        target: target(),
        dependencyToken: dependency(),
        getCurrentDependencyToken: () => harness.getEffectiveDependency(),
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
    schemaVersion: 2,
    targetContextId: request.requestBinding.targetContextId,
    anchorCameraBindingDigest: request.anchorCameraBindingDigest,
    anchorRgbDigest: request.anchorRgbDigest,
    anchorStableMaskDigest: request.anchorStableMask.digest,
    geometryPolicyDigest: rgbDigest('e'),
    centerWorld: [1, 2, 3],
    extentWorld: [0.5, 0.5, 0.5],
    visiblePoints: [
        [1, 2, 3],
        [4, 5, 6],
        [1, 2, 4],
        [4, 5, 7]
    ],
    quality: 'usable',
    reasons: [],
    promptSupport: 'usable',
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
    plannedKeyView(`key-view-${batchOrdinal}-1`, 101 + batchOrdinal * 10),
    plannedKeyView(`key-view-${batchOrdinal}-2`, 102 + batchOrdinal * 10, {
        quality: 'failed',
        reasons: ['insufficientVisibility']
    }),
    plannedKeyView(`key-view-${batchOrdinal}-3`, 103 + batchOrdinal * 10, {
        quality: 'failed',
        reasons: ['projectedSizeTooSmall']
    })
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
        artifactDigest: sha256Digest(
            new TextEncoder().encode(request.planAttemptId)
        )
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
        pngBase64: pngBase64ForDigest(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height,
            digest
        ),
        digest,
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
    rendererId: 'gsplat',
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    runtimeBuildId:
        'sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f',
    renderWorkingSetToken:
        request.snapshot.contentDigest ?? `sha256:${'f'.repeat(64)}`,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds ?? [1],
        Number
    ).sort((left, right) => left - right)
});

const promptResponseFor = (request, overrides = {}) => {
    const prompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: request.requestBinding.targetContextId,
        contextRevision: request.requestBinding.contextRevision,
        viewId: request.viewId,
        rgbDigest: request.rgb.digest,
        cameraBindingDigest: request.viewCameraBindingDigest,
        targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
        localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        promptSynthesisPolicyDigest:
            aiSelectImageInstancePromptSynthesisPolicyDigest,
        positivePoints: [{ xPx: 4, yPx: 4 }],
        negativePoints: [],
        positiveBox: { x0Px: 3, y0Px: 3, x1Px: 8, y1Px: 8 },
        multimaskOutput: false
    });
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        viewId: request.viewId,
        viewCameraBindingDigest: request.viewCameraBindingDigest,
        rgbDigest: request.rgb.digest,
        targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
        localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        modelManifestDigest: request.modelManifestDigest,
        runtimeDigest: request.runtimeDigest,
        companionInstanceId: request.companionInstanceId,
        promptSynthesisAttemptId: request.promptSynthesisAttemptId,
        promptSynthesisPolicyVersion:
            aiSelectImageInstancePromptSynthesisPolicyVersion,
        status: 'ready',
        diagnostics: ['projected-support:1'],
        prompt,
        ...overrides
    };
};

const limitedPromptResponseFor = (request) => {
    const { prompt, ...response } = promptResponseFor(request);
    return {
        ...response,
        status: 'limited',
        diagnostics: ['sparse-projectable-support']
    };
};

const maskResponseFor = (request) => {
    const mask = bitsetArtifact(64, 48, [
        [4, 4],
        [5, 4],
        [6, 4]
    ]);
    return createImageInstanceMaskResult({
        schemaVersion: 1,
        requestIdentity: request.identity,
        masks: [mask],
        modelScores: [0.9],
        diagnostics: { outcome: 'available' }
    });
};

const reviewResponseFor = (request, assessmentOverrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    viewId: request.viewId,
    rgbDigest: request.rgb.digest,
    promptArtifactDigest: request.prompt.artifactDigest,
    inferenceResultDigest: request.inferenceResultDigest,
    chosenMaskDigest: request.chosenMask.digest,
    reviewAttemptId: request.reviewAttemptId,
    reviewPolicyVersion: 'local-view-assessment/v2',
    assessment: {
        status: 'review',
        primaryReason: 'severely-fragmented',
        reasons: ['severely-fragmented'],
        actionableReasons: ['severely-fragmented'],
        policyVersion: 'local-view-assessment/v2',
        inputIdentity: {
            rgbDigest: request.rgb.digest,
            stableMaskDigest: request.chosenMask.digest,
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
    }
});

/** Resolve the pending render and Route B acquisition of one View. */
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
    assert.equal(state.geometryHint.artifactDigest, rgbDigest('f'));
    assert.equal(state.geometryHint.quality, 'usable');
    assert.equal(state.keyViewPlans.length, 1);
    assert.equal(
        state.keyViewPlans[0].planAttemptId,
        'local-key-view-plan-attempt-1'
    );
    assert.equal(state.keyViewPlans[0].orderedViews.length, 4);
    assert.equal(state.views.length, 4);
    assert.equal(state.views[0].viewId, 'key-view-0-0');
    assert.equal(state.views[0].source, 'auto-generated');
    assert.equal(state.views[0].planQuality, 'usable');
    assert.deepEqual(state.views[0].planReasons, []);
});

test('creation ordinals survive controller source regrouping while initial planning is pending', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    assert.equal(harness.planner.calls.length, 1);

    const userViewId = harness.controller.addUserView(cameraBinding());
    assert.equal(harness.controller.state.views[0].creationOrdinal, 1);
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0])
    );
    await flush();

    const creationOrder = Object.fromEntries(
        harness.controller.state.views.map((entry) => [
            entry.viewId,
            entry.creationOrdinal
        ])
    );
    assert.deepEqual(creationOrder, {
        'key-view-0-0': 2,
        'key-view-0-1': 3,
        'key-view-0-2': 4,
        'key-view-0-3': 5,
        [userViewId]: 1
    });
});

test('a partial plan keeps failed slots inspectable without rendering them Ready', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness, [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-1', 101, {
            quality: 'failed',
            reasons: ['insufficientVisibility']
        }),
        plannedKeyView('key-view-0-2', 102, {
            quality: 'failed',
            reasons: ['projectedSizeTooSmall']
        }),
        plannedKeyView('key-view-0-3', 103, {
            quality: 'failed',
            reasons: ['targetOutsideClipping']
        })
    ]);

    const failed = harness.controller.state.views.find(
        (view) => view.viewId === 'key-view-0-1'
    );
    assert.equal(failed.renderStatus, 'failed');
    assert.equal(failed.rgb, undefined);
    assert.equal(failed.participation, 'excluded');
    assert.deepEqual(failed.planReasons, ['insufficientVisibility']);
    assert.deepEqual(
        harness.viewRenderer.calls.map((request) => request.viewId),
        ['key-view-0-0']
    );
});

test('a Generated AIView publishes RGB Ready while its Route B Mask is still Generating', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness, [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-1', 101, {
            quality: 'limited',
            reasons: ['reducedVisibility']
        }),
        plannedKeyView('key-view-0-2', 102, {
            quality: 'failed',
            reasons: ['insufficientVisibility']
        }),
        plannedKeyView('key-view-0-3', 103, {
            quality: 'failed',
            reasons: ['projectedSizeTooSmall']
        })
    ]);

    let views = harness.controller.state.views;
    assert.equal(views.length, 4);
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
    // Progressive publication: RGB Ready + Prompt Ready + Mask Generating +
    // Evidence Not Requested is a legal state; the View never waits for its
    // Mask.
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].rgbDigest, rgbDigest('b'));
    assert.equal(views[0].promptStatus, 'ready');
    assert.equal(
        views[0].maskStatus,
        'generating',
        views[0].promptErrorMessage ?? views[0].maskErrorMessage
    );
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
    assert.equal(views.length, 4);
    assert.ok(views.slice(0, 2).every((view) => view.renderStatus === 'ready'));
    assert.ok(
        views.slice(0, 2).every((view) => view.maskStatus === 'ready'),
        JSON.stringify(
            views.map((view) => ({
                viewId: view.viewId,
                promptStatus: view.promptStatus,
                maskStatus: view.maskStatus,
                maskErrorMessage: view.maskErrorMessage
            }))
        )
    );

    const stable = harness.maskRegistry.viewState(
        'key-view-0-0',
        rgbDigest('b')
    ).stableMask;
    assert.ok(stable);
    assert.equal(stable.maskId, views[0].stableMaskId);
    assert.equal(stable.source, 'single-frame-sam');
    assert.equal(stable.status, 'auto-review');
    assert.equal(stable.createdFromRgbDigest, rgbDigest('b'));

    // The Image Instance request carries exact authoritative Generated View
    // RGB, while Prompt synthesis carries the geometry and local-plan binding.
    const maskRequest = harness.maskProvider.calls[0];
    assert.equal(
        views[0].prompt?.artifactDigest,
        maskRequest.prompt.artifactDigest
    );
    assert.equal(maskRequest.identity.viewId, 'key-view-0-0');
    assert.equal(maskRequest.rgb.rgbDigest, rgbDigest('b'));
    assert.ok(maskRequest.rgb.artifact);
    assert.equal(maskRequest.prompt.multimaskOutput, false);
    assert.ok(maskRequest.prompt.positiveBox);
    assert.equal(harness.promptSynthesizer.calls[0].viewId, 'key-view-0-0');
    assert.equal(
        harness.promptSynthesizer.calls[0].targetGeometryHint.artifactDigest,
        rgbDigest('f')
    );

    // Publishing the Stable Mask marks Evidence missing/dirty only; no Lift.
    assert.equal(views[0].evidenceStatus, 'not-requested');
    assert.equal(views[0].assessment.status, 'review');
    assert.deepEqual(views[0].assessment.reasons, ['severely-fragmented']);
    assert.equal(views[0].maskQuality, 'auto-review');
    assert.equal(views[0].participation, 'excluded');
    assert.deepEqual(harness.controller.state.dirtyState, {
        targetGeometryDirty: false,
        localKeyViewPlanDirty: false,
        promptDirtyViewIds: [],
        maskInferenceDirtyViewIds: [],
        evidenceDirtyViewIds: ['key-view-0-0', 'key-view-0-1'],
        liftDirty: true,
        candidateStale: true
    });
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
    harness.reviewProvider.assessmentOverrides = {
        status: 'good',
        primaryReason: undefined,
        reasons: [],
        actionableReasons: []
    };
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.source, 'auto-generated');
    assert.equal(view.maskQuality, 'auto-good');
    assert.equal(view.participation, 'included');
});

test('Assessment Failed publishes no automatic Stable Mask and remains Excluded', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.reviewProvider.assessmentOverrides = {
        status: 'failed',
        primaryReason: undefined,
        reasons: [],
        actionableReasons: [],
        diagnostics: undefined
    };
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'failed');
    assert.equal(view.stableMaskId, undefined);
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

    harness.dirtyState.reset();
    harness.controller.setViewParticipation('key-view-0-0', 'excluded');
    assert.equal(harness.controller.state.views[0].participation, 'excluded');
    assert.equal(
        harness.controller.state.views[0].maskQuality,
        'user-confirmed'
    );
    assert.equal(harness.controller.state.dirtyState.liftDirty, true);
    assert.equal(harness.controller.state.dirtyState.candidateStale, true);
});

test('a failed Participation mutation preserves Participation and Candidate state', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    harness.dirtyState.reset();
    const before = harness.controller.state;
    assert.equal(before.views[0].participation, 'excluded');
    assert.throws(() =>
        harness.controller.setViewParticipation('key-view-0-0', 'included')
    );
    const after = harness.controller.state;
    assert.equal(after.views[0].participation, 'excluded');
    assert.deepEqual(after.dirtyState, before.dirtyState);
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
    harness.reviewProvider.assessmentOverrides = {
        status: 'good',
        primaryReason: undefined,
        reasons: [],
        actionableReasons: []
    };
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.views[0].participation, 'included');

    harness.maskRegistry.publishAutoStable({
        viewId: 'key-view-0-0',
        rgbDigest: rgbDigest('b'),
        artifact: bitsetArtifact(64, 48, [[20, 20]]),
        source: 'single-frame-sam',
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
    assert.equal(harness.controller.state.views.length, 4);
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
    assert.equal(harness.controller.state.views.length, 4);
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
    assert.equal(harness.controller.state.views.length, 4);
});

test('suspension preserves Generated View state, rejects late work, and resumes with a fresh binding', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    const staleHintRequest = harness.geometryHints.calls[0];
    const originalRevision = staleHintRequest.requestBinding.contextRevision;

    harness.setEffectiveDependency(
        dependency({ geometryToken: 'geometry-v2' })
    );
    harness.anchorController.synchronizeTargetDependency();

    assert.equal(harness.anchorController.state.context.lifecycle, 'suspended');
    assert.equal(harness.controller.state.plannerStatus, 'planning');
    assert.throws(
        () => harness.controller.addUserView(cameraBinding()),
        /suspended/i
    );

    harness.setEffectiveDependency(dependency());
    harness.anchorController.synchronizeTargetDependency();
    const resumedRevision = harness.anchorController.state.context.revision;
    const viewId = harness.controller.addUserView(cameraBinding());

    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(staleHintRequest)
    );
    await flush();

    assert.equal(harness.planner.calls.length, 0);
    assert.equal(harness.viewRenderer.calls.length, 1);
    assert.equal(harness.controller.state.views[0].viewId, viewId);
    assert.equal(
        harness.viewRenderer.calls[0].requestBinding.contextRevision,
        resumedRevision
    );
    assert.ok(resumedRevision > originalRevision);
});

test('Restart disposes target-local Generated View and Mask state', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await completeTwoViews(harness);
    assert.equal(harness.controller.state.views.length, 4);

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
