const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectGeneratedViewController
} = require('../.test-dist/src/ai-select/generated-view-controller.js');
const {
    aiSelectImageInstancePromptSynthesisPolicyDigest,
    aiSelectImageInstancePromptSynthesisPolicyVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    createImageInstancePromptArtifact
} = require('../.test-dist/src/ai-select/image-instance-mask.js');
const {
    aiSelectLocalKeyViewPlannerVersion
} = require('../.test-dist/src/ai-select/local-key-view-plan.js');
const {
    aiSelectTargetGeometryPolicyVersion
} = require('../.test-dist/src/ai-select/target-geometry-hint.js');
const {
    cameraBindingDigest,
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    PerViewEvidenceRegistry
} = require('../.test-dist/src/ai-select/evidence-state.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    autoMaskProposalSetDigest,
    anchorMaskRankingPolicyVersion
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    adaptMaskProposalEnvelope
} = require('../.test-dist/src/ai-select/mask-service.js');
const {
    MaskAnnotationRegistry
} = require('../.test-dist/src/ai-select/mask-registry.js');
const {
    createEmptyPromptState,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');
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

/** A distinct pose/intrinsics so identity preservation is observable. */
const shiftedCameraBinding = () => {
    const binding = captureEditorCameraBinding(editorCamera(), 7);
    return Object.freeze({
        ...binding,
        cameraToWorld: Object.freeze(
            binding.cameraToWorld.map((value, index) =>
                index === 3 ? value + 5 : value
            )
        )
    });
};

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

const bitsetArtifact = (width, height, foreground = [[4, 4]]) => {
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

const goodReview = (overrides = {}) => ({
    status: 'good',
    reasons: [],
    actionableReasons: [],
    policyVersion: aiSelectViewAssessmentPolicyVersion,
    diagnostics: {
        framePixels: 64 * 48,
        foregroundPixels: 1,
        boundaryPixels: 0,
        boundaryContactRatio: 0,
        connectedComponents: 1,
        largestComponentRatio: 1,
        promptPointCount: 1,
        promptViolationCount: 0,
        boxSpillPixels: null,
        boxSpillRatio: null
    },
    ...overrides
});

const promptDiagnosticsFor = (request) => [
    ...request.promptState.points.map((prompt) => ({
        promptId: prompt.promptId,
        family: 'point',
        polarity: prompt.polarity,
        satisfied: true
    })),
    ...request.promptState.boxes.map((prompt) => ({
        promptId: prompt.promptId,
        family: 'box',
        polarity: prompt.polarity,
        satisfied: true,
        constraintCoverageFraction: 1,
        candidateCoverageFraction: 1
    }))
];

const promptConsistency = () => ({
    positivePointsSatisfied: true,
    negativePointsSatisfied: true,
    positiveBoxesSatisfied: true
});

const rankingFeatures = () => ({
    promptConsistency: promptConsistency(),
    eligible: true,
    areaFraction: 1 / (64 * 48),
    connectedComponentCount: 1
});

const maskResponseFor = (request, overrides = {}) => {
    const artifact =
        overrides.mask ?? bitsetArtifact(request.rgbWidth, request.rgbHeight);
    const promptDiagnostics = promptDiagnosticsFor(request);
    const proposals = overrides.proposals ?? [
        {
            proposalId: 'proposal-0',
            mask: artifact,
            sourceIndex: 0,
            promptConsistency: promptConsistency(),
            ...(request.promptState.boxes.length === 0
                ? {}
                : { promptDiagnostics }),
            rankingFeatures: rankingFeatures(),
            review: goodReview()
        }
    ];
    const proposalPayload = {
        schemaVersion: 4,
        viewId: request.viewId,
        rgbDigest: request.rgbDigest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposals
    };
    const proposalSet = overrides.proposalSet ?? {
        ...proposalPayload,
        digest: autoMaskProposalSetDigest(proposalPayload)
    };
    const proposalDecision = overrides.proposalDecision ?? {
        schemaVersion: 2,
        viewId: request.viewId,
        rgbDigest: request.rgbDigest,
        promptStateDigest: request.promptState.digest,
        proposalSetDigest: proposalSet.digest,
        rankingPolicyVersion: anchorMaskRankingPolicyVersion,
        status: 'selected',
        selectedProposalId: proposalSet.proposals[0].proposalId,
        alternativeProposalIds: [proposalSet.proposals[0].proposalId]
    };
    const {
        mask: ignoredMask,
        proposals: ignoredProposals,
        proposalDecision: ignoredDecision,
        ...responseOverrides
    } = overrides;
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        cameraBindingDigest: request.cameraBindingDigest,
        rgbDigest: request.rgbDigest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        rankingPolicyVersion: request.rankingPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposalSet,
        proposalDecision,
        ...responseOverrides
    };
};

const createHarness = () => {
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
    const promptSynthesizer = {
        calls: [],
        synthesizeGeneratedViewPrompt(request) {
            this.calls.push(request);
            const prompt = createImageInstancePromptArtifact({
                schemaVersion: 1,
                targetContextId: request.requestBinding.targetContextId,
                contextRevision: request.requestBinding.contextRevision,
                viewId: request.viewId,
                rgbDigest: request.rgb.digest,
                cameraBindingDigest: request.viewCameraBindingDigest,
                targetGeometryHintDigest:
                    request.targetGeometryHint.artifactDigest,
                localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
                adapterCapabilityDigest: request.adapterCapabilityDigest,
                promptSynthesisPolicyDigest:
                    aiSelectImageInstancePromptSynthesisPolicyDigest,
                positivePoints: [{ xPx: 4, yPx: 4 }],
                negativePoints: [],
                multimaskOutput: false
            });
            return Promise.resolve({
                requestBinding: request.requestBinding,
                targetSplatId: request.target.splatId,
                viewId: request.viewId,
                viewCameraBindingDigest: request.viewCameraBindingDigest,
                rgbDigest: request.rgb.digest,
                targetGeometryHintDigest:
                    request.targetGeometryHint.artifactDigest,
                localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
                adapterCapabilityDigest: request.adapterCapabilityDigest,
                modelManifestDigest: request.modelManifestDigest,
                runtimeDigest: request.runtimeDigest,
                companionInstanceId: request.companionInstanceId,
                promptSynthesisAttemptId: request.promptSynthesisAttemptId,
                promptSynthesisPolicyVersion:
                    aiSelectImageInstancePromptSynthesisPolicyVersion,
                status: 'ready',
                diagnostics: [],
                prompt
            });
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
        reviewImageInstanceMask(request) {
            this.calls.push(request);
            return Promise.reject(new Error('not needed in user-view tests'));
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
        geometryHints,
        planner,
        renderer: viewRenderer,
        promptSynthesizer,
        maskProvider,
        reviewProvider,
        getImageInstanceRuntimeBinding: () => imageInstanceRuntimeBinding
    });
    return {
        anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        geometryHints,
        planner,
        viewRenderer,
        promptSynthesizer,
        maskProvider,
        reviewProvider,
        imageInstanceRuntimeBinding,
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

const hintResponseFor = (request) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    geometryAttemptId: request.geometryAttemptId,
    geometryPolicyVersion: aiSelectTargetGeometryPolicyVersion,
    hint: {
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
        artifactDigest: rgbDigest('f')
    }
});

const plannedKeyView = (viewId, revision) => ({
    viewId,
    cameraBinding: Object.freeze({ ...cameraBinding(), revision }),
    quality: 'usable',
    reasons: []
});

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
        orderedViews: views ?? [plannedKeyView('key-view-0-0', 100)],
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
    assert.equal(
        harness.controller.state.plannerStatus,
        'active',
        harness.controller.state.plannerErrorMessage
    );
};

/**
 * The serial pipeline queue runs planner-owned renders first; fail them so
 * the queue is free for user View renders in these focused tests.
 */
const failPendingPlannedRenders = async (harness) => {
    while (harness.viewRenderer.deferreds.length > 0) {
        harness.viewRenderer.deferreds
            .shift()
            .reject(new Error('planner view render not under test'));
        await flush();
    }
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
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

const viewById = (harness, viewId) =>
    harness.controller.state.views.find((view) => view.viewId === viewId);

/** Add one user View and resolve its authoritative render to RGB Ready. */
const addReadyUserView = async (harness, binding = cameraBinding()) => {
    const viewId = harness.controller.addUserView(binding);
    await flush();
    const request = harness.viewRenderer.calls.at(-1);
    assert.equal(request.viewId, viewId);
    harness.viewRenderer.deferreds
        .at(-1)
        .resolve(viewRenderResponseFor(request));
    await flush();
    return viewId;
};

test('adding a user View requires the confirmed Current Target Context', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    assert.throws(() => harness.controller.addUserView(cameraBinding()));
});

test('Use Current View creates a pending user View bound to the exact CameraBinding', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const binding = shiftedCameraBinding();
    const viewId = harness.controller.addUserView(binding);
    const view = viewById(harness, viewId);
    assert.ok(view);
    assert.equal(view.source, 'user-added');
    assert.equal(view.renderStatus, 'pending');
    assert.equal(view.participation, 'excluded');
    assert.equal(view.maskStatus, 'none');
    assert.equal(view.promptStatus, 'none');
    // The new View is selected so its frustum and surface follow the action.
    assert.equal(harness.controller.state.selectedViewId, viewId);
    // CameraBinding identity is preserved exactly (pose, intrinsics, clipping).
    assert.deepEqual(view.cameraBinding, binding);
    await flush();
    const request = harness.viewRenderer.calls.at(-1);
    assert.equal(request.viewId, viewId);
    assert.deepEqual(request.cameraBinding, binding);
    assert.equal(
        cameraBindingDigest(request.cameraBinding),
        cameraBindingDigest(binding)
    );
});

test('a user View reaches RGB Ready with no Mask and Evidence Not Requested', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    const view = viewById(harness, viewId);
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.rgbDigest, rgbDigest('b'));
    assert.equal(view.maskStatus, 'none');
    assert.equal(view.promptStatus, 'none');
    assert.equal(view.evidenceStatus, 'not-requested');
    assert.equal(view.participation, 'excluded');
    // The Route-B planner pipeline never runs for a user-owned View.
    assert.equal(
        harness.promptSynthesizer.calls.filter((call) => call.viewId === viewId)
            .length,
        0
    );
    assert.equal(harness.maskProvider.calls.length, 0);
});

test('user View render failure preserves the record and a true Retry reruns the render', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = harness.controller.addUserView(cameraBinding());
    await flush();
    harness.viewRenderer.deferreds
        .at(-1)
        .reject(new Error('companion capacity'));
    await flush();
    let view = viewById(harness, viewId);
    assert.equal(view.renderStatus, 'failed');
    assert.match(view.renderErrorMessage, /companion capacity/);

    harness.controller.retryViewRender(viewId);
    await flush();
    const retryRequest = harness.viewRenderer.calls.at(-1);
    assert.equal(retryRequest.viewId, viewId);
    assert.notEqual(
        retryRequest.renderAttemptId,
        harness.viewRenderer.calls.at(-2).renderAttemptId
    );
    harness.viewRenderer.deferreds
        .at(-1)
        .resolve(viewRenderResponseFor(retryRequest));
    await flush();
    view = viewById(harness, viewId);
    assert.equal(view.renderStatus, 'ready');
});

test('adding a user View never resumes stopped local generation', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);
    harness.controller.stopGeneration();
    assert.equal(harness.controller.state.generationStopped, true);
    const planCalls = harness.planner.calls.length;

    await addReadyUserView(harness);
    assert.equal(harness.controller.state.generationStopped, true);
    assert.equal(harness.planner.calls.length, planCalls);
});

test('Regenerate Auto Views preserves user-owned Views and their artifacts', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness, [plannedKeyView('key-view-0-0', 100)]);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    // Publish a user-confirmed Stable Mask on the user View.
    const rgb = viewById(harness, viewId).rgb;
    harness.maskRegistry.applyBrushGesture({
        viewId,
        rgbDigest: rgb.digest,
        strokes: [{ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' }],
        width: rgb.width,
        height: rgb.height
    });
    harness.maskRegistry.confirm(viewId, rgb.digest);
    harness.controller.noteUserViewStablePublication(viewId);
    assert.equal(viewById(harness, viewId).participation, 'included');

    harness.controller.regenerateViews();
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1], [
            plannedKeyView('key-view-0-1', 110)
        ])
    );
    await flush();

    const view = viewById(harness, viewId);
    assert.ok(view);
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.rgbDigest, rgb.digest);
    assert.equal(view.participation, 'included');
    assert.equal(viewById(harness, 'key-view-0-0'), undefined);
    assert.ok(viewById(harness, 'key-view-0-1'));
});

test('user View identities never collide with later additions', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const first = harness.controller.addUserView(cameraBinding());
    const second = harness.controller.addUserView(cameraBinding());
    assert.notEqual(first, second);
    assert.ok(viewById(harness, first));
    assert.ok(viewById(harness, second));
});

test('a planned View reusing a user-owned View identity fails closed', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    harness.controller.regenerateViews();
    await flush();
    harness.planner.deferreds[1].resolve(
        planResponseFor(harness.planner.calls[1], [plannedKeyView(viewId, 120)])
    );
    await flush();
    // The batch was rejected; the user-owned View survives untouched.
    assert.ok(harness.controller.state.plannerErrorMessage);
    assert.ok(viewById(harness, viewId));
});

test('user View Mask requests bind the exact run, View, RGB and Camera identity', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const binding = shiftedCameraBinding();
    const viewId = await addReadyUserView(harness, binding);
    const view = viewById(harness, viewId);

    let promptState = createEmptyPromptState(viewId, view.rgb.digest);
    promptState = revisePromptState(promptState, {
        points: [
            Object.freeze({
                promptId: 'prompt-1',
                xPx: 4,
                yPx: 4,
                polarity: 'include'
            })
        ]
    });

    const request = harness.controller.createUserViewMaskRequest(
        viewId,
        promptState,
        'user-view-attempt-1',
        'manifest-digest-1',
        harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
        'auto-mask-proposal/v1',
        { includeRgbArtifact: true }
    );
    assert.ok(request);
    assert.equal(request.viewId, viewId);
    assert.equal(request.sceneId, snapshot.sceneId);
    assert.equal(request.sceneVersion, snapshot.sceneVersion);
    assert.equal(request.rgbDigest, view.rgb.digest);
    assert.equal(request.rgbWidth, view.rgb.width);
    assert.equal(request.rgbHeight, view.rgb.height);
    assert.equal(request.cameraBindingDigest, cameraBindingDigest(binding));
    assert.equal(request.rgb?.digest, view.rgb.digest);
    assert.equal(request.rgb?.pngBase64, view.rgb.pngBase64);
    assert.equal(request.proposalAttemptId, 'user-view-attempt-1');
    assert.equal(
        request.requestBinding.targetContextId,
        harness.anchorController.state.context.targetContextId
    );
    // The RGB artifact may be omitted only when this digest already shipped.
    const followUp = harness.controller.createUserViewMaskRequest(
        viewId,
        promptState,
        'user-view-attempt-2',
        'manifest-digest-1',
        harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
        'auto-mask-proposal/v1',
        { includeRgbArtifact: false }
    );
    assert.ok(followUp);
    assert.equal(followUp.rgb, undefined);
    assert.equal(followUp.rgbDigest, view.rgb.digest);
});

test('user View Mask requests are null for superseded or foreign identities', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const binding = cameraBinding();
    const viewId = harness.controller.addUserView(binding);
    await flush();

    // Not yet RGB Ready: no request.
    let promptState = createEmptyPromptState(viewId, rgbDigest('b'));
    assert.equal(
        harness.controller.createUserViewMaskRequest(
            viewId,
            promptState,
            'attempt-1',
            'manifest-digest-1',
            harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
            'auto-mask-proposal/v1',
            { includeRgbArtifact: true }
        ),
        null
    );

    harness.viewRenderer.deferreds
        .at(-1)
        .resolve(viewRenderResponseFor(harness.viewRenderer.calls.at(-1)));
    await flush();

    // A PromptState bound to another View or RGB is rejected.
    assert.equal(
        harness.controller.createUserViewMaskRequest(
            viewId,
            createEmptyPromptState('anchor-view', rgbDigest('b')),
            'attempt-2',
            'manifest-digest-1',
            harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
            'auto-mask-proposal/v1',
            { includeRgbArtifact: true }
        ),
        null
    );
    assert.equal(
        harness.controller.createUserViewMaskRequest(
            viewId,
            createEmptyPromptState(viewId, rgbDigest('c')),
            'attempt-3',
            'manifest-digest-1',
            harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
            'auto-mask-proposal/v1',
            { includeRgbArtifact: true }
        ),
        null
    );
});

test('user View Mask responses pass only with the exact current binding', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    const view = viewById(harness, viewId);
    let promptState = createEmptyPromptState(viewId, view.rgb.digest);
    promptState = revisePromptState(promptState, {
        points: [
            Object.freeze({
                promptId: 'prompt-1',
                xPx: 4,
                yPx: 4,
                polarity: 'include'
            })
        ]
    });
    const request = harness.controller.createUserViewMaskRequest(
        viewId,
        promptState,
        'attempt-1',
        'manifest-digest-1',
        harness.imageInstanceRuntimeBinding.adapterCapabilityDigest,
        'auto-mask-proposal/v1',
        { includeRgbArtifact: true }
    );

    const response = adaptMaskProposalEnvelope(
        maskResponseFor(request),
        request
    );
    assert.equal(
        harness.controller.acceptsUserViewMaskResponse(response, request),
        true
    );
    // A stale RGB identity echo is rejected.
    assert.equal(
        harness.controller.acceptsUserViewMaskResponse(
            { ...response, rgbDigest: rgbDigest('c') },
            request
        ),
        false
    );
    // A foreign View identity echo is rejected.
    assert.equal(
        harness.controller.acceptsUserViewMaskResponse(
            { ...response, viewId: 'anchor-view' },
            request
        ),
        false
    );
});

test('Stable Mask publication applies the User Confirmed Participation default without lifting', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    const rgb = viewById(harness, viewId).rgb;
    harness.maskRegistry.applyBrushGesture({
        viewId,
        rgbDigest: rgb.digest,
        strokes: [{ xPx: 4, yPx: 4, radiusPx: 2, mode: 'add' }],
        width: rgb.width,
        height: rgb.height
    });
    harness.maskRegistry.confirm(viewId, rgb.digest);
    harness.controller.noteUserViewStablePublication(viewId);

    const view = viewById(harness, viewId);
    assert.equal(view.maskStatus, 'ready');
    assert.equal(view.maskQuality, 'user-confirmed');
    assert.equal(view.participation, 'included');
    assert.ok(view.stableMaskId);
    // Publication dirties Evidence by identity only; nothing lifts.
    assert.equal(view.evidenceStatus, 'not-requested');
});

test('user View exclusion is an explicit Participation decision', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    await confirmAnchor(harness);
    await driveToActive(harness);
    await failPendingPlannedRenders(harness);

    const viewId = await addReadyUserView(harness);
    harness.controller.setViewParticipation(viewId, 'excluded');
    assert.equal(viewById(harness, viewId).participation, 'excluded');
});
