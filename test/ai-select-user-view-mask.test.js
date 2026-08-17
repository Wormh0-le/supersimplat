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
    MaskAnnotationRegistry
} = require('../.test-dist/src/ai-select/mask-registry.js');
const {
    adaptMaskProposalEnvelope
} = require('../.test-dist/src/ai-select/mask-service.js');
const {
    previousPredictionLogitsRefDigest
} = require('../.test-dist/src/ai-select/previous-logits-ref.js');
const {
    createPromptAdapterCapabilities
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    AISelectUserViewMaskController
} = require('../.test-dist/src/ai-select/user-view-mask-controller.js');
const {
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = () => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1'
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
    rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
    rendererId: 'gsplat',
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    runtimeBuildId:
        'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4',
    renderWorkingSetToken:
        request.snapshot.contentDigest ?? `sha256:${'f'.repeat(64)}`,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds ?? [1],
        Number
    ).sort((left, right) => left - right)
});

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

const confirmedAnchorFor = (anchorController) => {
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
        sceneVersion: snapshot.sceneVersion
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

const logitsRefFor = (request, candidateId = 'proposal-0') => {
    const payload = {
        schemaVersion: 1,
        companionInstanceId: 'companion-1',
        stateId: `logits-state-${request.proposalAttemptId}`,
        targetContextId: request.requestBinding.targetContextId,
        viewId: request.viewId,
        rgbDigest: request.rgbDigest,
        sourceInferenceAttemptId: request.proposalAttemptId,
        sourceCandidateId: candidateId,
        adapterRuntimeDigest: rgbDigest('5'),
        shape: [1, 288, 288],
        dtype: 'float32',
        dataDigest: rgbDigest('4')
    };
    return {
        ...payload,
        refDigest: previousPredictionLogitsRefDigest(payload)
    };
};

const proposalFor = (request, index, options = {}) => ({
    proposalId: `proposal-${index}`,
    mask: bitsetArtifact(request.rgbWidth, request.rgbHeight, [[4 + index, 4]]),
    sourceIndex: index,
    promptConsistency: promptConsistency(),
    ...(request.promptState.boxes.length === 0
        ? {}
        : { promptDiagnostics: promptDiagnosticsFor(request) }),
    rankingFeatures: rankingFeatures(),
    review: goodReview(),
    ...(options.withLogitsRef === true
        ? { logitsRef: logitsRefFor(request, `proposal-${index}`) }
        : {})
});

const maskResponseFor = (request, overrides = {}) => {
    const proposals = overrides.proposals ?? [proposalFor(request, 0)];
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
    const proposalSet = {
        ...proposalPayload,
        digest: autoMaskProposalSetDigest(proposalPayload)
    };
    const proposalDecision =
        proposals.length > 1
            ? {
                  schemaVersion: 2,
                  viewId: request.viewId,
                  rgbDigest: request.rgbDigest,
                  promptStateDigest: request.promptState.digest,
                  proposalSetDigest: proposalSet.digest,
                  rankingPolicyVersion: anchorMaskRankingPolicyVersion,
                  status: 'ambiguous',
                  selectedProposalId: proposals[0].proposalId,
                  alternativeProposalIds: proposals.map(
                      (proposal) => proposal.proposalId
                  )
              }
            : {
                  schemaVersion: 2,
                  viewId: request.viewId,
                  rgbDigest: request.rgbDigest,
                  promptStateDigest: request.promptState.digest,
                  proposalSetDigest: proposalSet.digest,
                  rankingPolicyVersion: anchorMaskRankingPolicyVersion,
                  status: 'selected',
                  selectedProposalId: proposals[0].proposalId,
                  alternativeProposalIds: [proposals[0].proposalId]
              };
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
        proposalDecision
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
    const routeBMaskProvider = {
        infer() {
            return Promise.reject(new Error('Route B not under test'));
        }
    };
    const reviewProvider = {
        reviewImageInstanceMask() {
            return Promise.reject(new Error('Route B not under test'));
        }
    };
    const proposalProvider = {
        calls: [],
        deferreds: [],
        produceMask(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise.then((response) =>
                adaptMaskProposalEnvelope(response, request)
            );
        }
    };
    const promptCapabilities = createPromptAdapterCapabilities({
        positivePoints: true,
        negativePoints: true,
        positiveInstanceBox: true,
        previousLogitsRefinement: true,
        singlePointMultimask: false,
        compilerPolicyVersion: 'point-mask-compiler/v1'
    });
    const imageInstanceRuntimeBinding = {
        adapterId: 'sam3-image',
        modelManifestDigest: 'manifest-digest-1',
        runtimeDigest: rgbDigest('7'),
        companionInstanceId: 'companion-1',
        adapterCapabilityDigest: promptCapabilities.capabilityDigest
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
        maskProvider: routeBMaskProvider,
        reviewProvider,
        getImageInstanceRuntimeBinding: () => imageInstanceRuntimeBinding
    });
    const userMasks = new AISelectUserViewMaskController({
        generatedViews: controller,
        maskProvider: proposalProvider,
        maskRegistry,
        evidenceRegistry,
        getModelManifestDigest: () => 'manifest-digest-1',
        getPromptAdapterCapabilities: () => promptCapabilities
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
        proposalProvider,
        promptCapabilities,
        controller,
        userMasks
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
        orderedViews: views ?? [
            plannedKeyView('key-view-0-0', 100),
            ...[1, 2, 3].map((index) => ({
                ...plannedKeyView(`key-view-0-${index}`, 100 + index),
                quality: 'failed',
                reasons: ['insufficientVisibility']
            }))
        ],
        planAttemptId: request.planAttemptId,
        artifactDigest: sha256Digest(
            new TextEncoder().encode(request.planAttemptId)
        )
    }
});

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
        'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4',
    renderWorkingSetToken:
        request.snapshot.contentDigest ?? `sha256:${'f'.repeat(64)}`,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds ?? [1],
        Number
    ).sort((left, right) => left - right)
});

/** Confirm the Anchor and reach planner 'active' with no live View renders. */
const driveToActive = async (harness) => {
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'active');
    // The serial pipeline runs planner-owned renders first; fail them so the
    // queue is free for user View work in these focused tests.
    while (harness.viewRenderer.deferreds.length > 0) {
        harness.viewRenderer.deferreds
            .shift()
            .reject(new Error('planner view render not under test'));
        await flush();
    }
};

/** Add one user View and resolve its authoritative render to RGB Ready. */
const addReadyUserView = async (harness) => {
    const viewId = harness.controller.addUserView(cameraBinding());
    await flush();
    const request = harness.viewRenderer.calls.at(-1);
    assert.equal(request.viewId, viewId);
    harness.viewRenderer.deferreds
        .at(-1)
        .resolve(viewRenderResponseFor(request));
    await flush();
    return viewId;
};

/** Resolve one planner-owned View far enough to exercise its editor surface. */
const addReadyGeneratedView = async (harness) => {
    await startAnchor(harness);
    await confirmAnchor(harness);
    harness.geometryHints.deferreds[0].resolve(
        hintResponseFor(harness.geometryHints.calls[0])
    );
    await flush();
    harness.planner.deferreds[0].resolve(
        planResponseFor(harness.planner.calls[0])
    );
    await flush();
    const request = harness.viewRenderer.calls[0];
    assert.ok(request);
    harness.viewRenderer.deferreds[0].resolve(viewRenderResponseFor(request));
    await flush();
    const view = viewById(harness, request.viewId);
    assert.equal(view?.renderStatus, 'ready');
    return request.viewId;
};

const viewById = (harness, viewId) =>
    harness.controller.state.views.find((view) => view.viewId === viewId);

test('an RGB Ready user View exposes a No-Mask session bound to its RGB', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);

    const session = harness.userMasks.sessionFor(viewId);
    assert.ok(session);
    const state = session.state;
    assert.equal(state.viewId, viewId);
    assert.equal(state.stableMask, null);
    assert.equal(state.editingMask, null);
    assert.equal(state.requestStatus, 'idle');
    assert.equal(state.evidence.status, 'not-requested');
    assert.ok(state.promptState);
    assert.equal(state.promptState.viewId, viewId);
    assert.equal(state.promptState.rgbDigest, rgbDigest('b'));
    assert.equal(state.promptState.points.length, 0);
});

test('View A draft survives browsing View B and returning to View A', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewA = await addReadyUserView(harness);
    const viewB = await addReadyUserView(harness);
    const sessionA = harness.userMasks.sessionFor(viewA);
    assert.ok(sessionA);
    sessionA.applyBrushGesture({
        mode: 'add',
        radiusPx: 2,
        samples: [{ xPx: 5, yPx: 5 }]
    });
    const editingMaskId = sessionA.state.editingMask?.maskId;
    assert.ok(editingMaskId);
    assert.equal(sessionA.state.stableMask, null);

    harness.controller.selectView(viewA);
    harness.controller.selectView(viewB);
    harness.controller.selectView(viewA);

    assert.equal(sessionA.state.editingMask?.maskId, editingMaskId);
    assert.equal(sessionA.state.stableMask, null);
    assert.equal(sessionA.state.hasUnconfirmedChanges, true);
});

test('an automatic Generated View can be corrected through the same Mask session', async () => {
    const harness = createHarness();
    const viewId = await addReadyGeneratedView(harness);
    const view = viewById(harness, viewId);
    assert.equal(view?.rgbDigest, rgbDigest('b'));

    // This models an automatic Stable Mask already published by Route B. A
    // later editor session must retain it, offer brush correction, and then
    // publish the replacement as User Confirmed rather than treating the
    // planner-owned View as read-only.
    harness.maskRegistry.publishAutoStable({
        viewId,
        rgbDigest: rgbDigest('b'),
        artifact: bitsetArtifact(64, 48, [[4, 4]]),
        source: 'single-frame-sam',
        status: 'auto-good'
    });
    // Attach after the automatic publication as a fresh Dock would. This
    // catches an initialization bug where session setup disposed the current
    // automatic Stable Mask before the user could correct it.
    const lateSessions = new AISelectUserViewMaskController({
        generatedViews: harness.controller,
        maskProvider: harness.proposalProvider,
        maskRegistry: harness.maskRegistry,
        evidenceRegistry: harness.evidenceRegistry,
        getModelManifestDigest: () => 'manifest-digest-1',
        getPromptAdapterCapabilities: () => harness.promptCapabilities
    });
    const session = lateSessions.sessionFor(viewId);
    assert.ok(session);
    assert.equal(session.state.stableMask?.status, 'auto-good');

    session.applyBrushGesture({
        mode: 'add',
        radiusPx: 2,
        samples: [{ xPx: 8, yPx: 8 }]
    });
    assert.ok(session.state.editingMask);
    session.confirmEditingMask();

    const corrected = viewById(harness, viewId);
    assert.equal(session.state.stableMask?.status, 'user-confirmed');
    assert.equal(corrected?.maskQuality, 'user-confirmed');
    assert.equal(corrected?.participation, 'included');
    assert.ok(
        harness.controller.state.dirtyState.evidenceDirtyViewIds.includes(
            viewId
        )
    );
});

test('one Point auto-generates one editable Mask with exact RGB on first ship', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    const pending = session.addPrompt({ xPx: 4, yPx: 4, polarity: 'include' });
    await flush();
    assert.equal(harness.proposalProvider.calls.length, 1);
    const request = harness.proposalProvider.calls[0];
    assert.equal(request.viewId, viewId);
    assert.equal(request.promptState.points.length, 1);
    // The exact authoritative RGB bytes cross on the first use of the digest.
    assert.equal(request.rgb?.digest, rgbDigest('b'));
    assert.ok(request.rgb?.pngBase64.length > 0);
    assert.equal(session.state.requestStatus, 'pending');

    harness.proposalProvider.deferreds[0].resolve(
        maskResponseFor(request, {
            proposals: [proposalFor(request, 0, { withLogitsRef: true })]
        })
    );
    await pending;
    const state = session.state;
    assert.equal(state.requestStatus, 'idle');
    assert.equal(state.automaticMaskStatus, 'editing');
    assert.ok(state.editingMask);
    // The sole result's opaque ref is the refinement lineage.
    const followUp = session.addPrompt({
        xPx: 8,
        yPx: 8,
        polarity: 'exclude'
    });
    await flush();
    const refinement = harness.proposalProvider.calls[1];
    // The digest already shipped: the artifact is omitted, identity remains.
    assert.equal(refinement.rgb, undefined);
    assert.equal(refinement.rgbDigest, rgbDigest('b'));
    assert.ok(refinement.previousLogitsRef);
    assert.equal(refinement.previousLogitsRef.viewId, viewId);
    assert.equal(refinement.previousLogitsRef.rgbDigest, rgbDigest('b'));
    assert.equal(
        refinement.previousLogitsRef.targetContextId,
        harness.anchorController.state.context.targetContextId
    );
    harness.proposalProvider.deferreds[1].resolve(maskResponseFor(refinement));
    await followUp;
    assert.ok(session.state.editingMask);
    session.applyBrushStroke({
        xPx: 12,
        yPx: 12,
        radiusPx: 1,
        mode: 'add'
    });
    assert.ok(session.state.editingMask);
});

test('Box/multiple-Point prompts require exactly one result', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    const pending = session.addBoxPrompt({
        x0Px: 2,
        y0Px: 2,
        x1Px: 10,
        y1Px: 10
    });
    await flush();
    const request = harness.proposalProvider.calls[0];
    // A Box program may not return multiple results; the editor fails
    // closed rather than trusting the wire.
    harness.proposalProvider.deferreds[0].resolve(
        maskResponseFor(request, {
            proposals: [0, 1].map((index) => proposalFor(request, index))
        })
    );
    await pending;
    assert.equal(session.state.requestStatus, 'failed');

    // A changed Prompt starts a new normal attempt and one result is adopted.
    const changedPrompt = session.addPrompt({
        xPx: 12,
        yPx: 12,
        polarity: 'include'
    });
    await flush();
    const changedRequest = harness.proposalProvider.calls[1];
    harness.proposalProvider.deferreds[1].resolve(
        maskResponseFor(changedRequest)
    );
    await changedPrompt;
    assert.equal(session.state.requestStatus, 'idle');
    assert.equal(session.state.automaticMaskStatus, 'editing');
    assert.ok(session.state.editingMask);
});

test('automatic adoption and Confirm publish the Stable Mask with User Confirmed Participation', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    const pending = session.addPrompt({ xPx: 4, yPx: 4, polarity: 'include' });
    await flush();
    harness.proposalProvider.deferreds[0].resolve(
        maskResponseFor(harness.proposalProvider.calls[0])
    );
    await pending;

    assert.ok(session.state.editingMask);
    assert.equal(session.state.automaticMaskStatus, 'editing');
    // Unpublished Editing state never touches the View's Stable surface.
    assert.equal(viewById(harness, viewId).stableMaskId, undefined);

    session.confirmEditingMask();
    const stable = session.state.stableMask;
    assert.ok(stable);
    assert.equal(stable.status, 'user-confirmed');
    const view = viewById(harness, viewId);
    assert.equal(view.stableMaskId, stable.maskId);
    assert.equal(view.maskQuality, 'user-confirmed');
    assert.equal(view.participation, 'included');
    assert.equal(view.maskStatus, 'ready');
    // Publication dirties Evidence by identity only; nothing lifts.
    assert.equal(view.evidenceStatus, 'not-requested');
    assert.ok(
        harness.controller.state.dirtyState.evidenceDirtyViewIds.includes(
            viewId
        )
    );
    assert.equal(harness.controller.state.dirtyState.liftDirty, true);
    assert.equal(harness.controller.state.dirtyState.candidateStale, true);
});

test('Paint/Erase author a manual Mask without entering inference', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    session.applyBrushGesture({
        mode: 'add',
        radiusPx: 2,
        samples: [
            { xPx: 4, yPx: 4 },
            { xPx: 6, yPx: 6 }
        ]
    });
    const editing = session.state.editingMask;
    assert.ok(editing);
    assert.equal(editing.source, 'manual');
    assert.equal(harness.proposalProvider.calls.length, 0);

    session.confirmEditingMask();
    assert.equal(session.state.stableMask?.status, 'user-confirmed');
    assert.equal(viewById(harness, viewId).participation, 'included');
});

test('a Mask technical failure preserves View, RGB and prior Stable Mask across a changed Prompt', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    // Publish an initial Stable Mask through Manual Draw.
    session.applyBrushGesture({
        mode: 'add',
        radiusPx: 2,
        samples: [{ xPx: 4, yPx: 4 }]
    });
    session.confirmEditingMask();
    const stableMaskId = session.state.stableMask?.maskId;
    assert.ok(stableMaskId);

    const pending = session.addPrompt({ xPx: 8, yPx: 8, polarity: 'include' });
    await flush();
    harness.proposalProvider.deferreds[0].reject(new Error('companion OOM'));
    await pending;
    assert.equal(session.state.requestStatus, 'failed');
    assert.match(session.state.errorMessage, /companion OOM/);
    // View, RGB and the prior Stable Mask survive the failure.
    const view = viewById(harness, viewId);
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.rgbDigest, rgbDigest('b'));
    assert.equal(session.state.stableMask?.maskId, stableMaskId);

    const changedPrompt = session.addPrompt({
        xPx: 10,
        yPx: 10,
        polarity: 'exclude'
    });
    await flush();
    harness.proposalProvider.deferreds[1].resolve(
        maskResponseFor(harness.proposalProvider.calls[1])
    );
    await changedPrompt;
    assert.equal(session.state.requestStatus, 'idle');
    assert.equal(session.state.stableMask?.maskId, stableMaskId);
});

test('a Companion Instance change re-ships RGB and drops the refinement ref', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    const pending = session.addPrompt({ xPx: 4, yPx: 4, polarity: 'include' });
    await flush();
    harness.proposalProvider.deferreds[0].resolve(
        maskResponseFor(harness.proposalProvider.calls[0], {
            proposals: [
                proposalFor(harness.proposalProvider.calls[0], 0, {
                    withLogitsRef: true
                })
            ]
        })
    );
    await pending;

    harness.userMasks.handleCompanionInstanceChanged();
    const followUp = session.addPrompt({
        xPx: 6,
        yPx: 6,
        polarity: 'include'
    });
    await flush();
    const request = harness.proposalProvider.calls[1];
    // The new Instance has no RGB cache and no logits state for this digest.
    assert.equal(request.rgb?.digest, rgbDigest('b'));
    assert.equal(request.previousLogitsRef, undefined);
    harness.proposalProvider.deferreds[1].resolve(maskResponseFor(request));
    await followUp;
});

test('a local edit supersedes the in-flight SAM attempt and resubmits the latest prompt set', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    const session = harness.userMasks.sessionFor(viewId);

    const first = session.addPrompt({ xPx: 4, yPx: 4, polarity: 'include' });
    await flush();
    // A second prompt while the first attempt is in flight supersedes it.
    const second = session.addPrompt({
        xPx: 8,
        yPx: 8,
        polarity: 'include'
    });
    await flush();
    // The late first response is discarded and the latest set resubmits.
    harness.proposalProvider.deferreds[0].resolve(
        maskResponseFor(harness.proposalProvider.calls[0])
    );
    await first;
    await flush();
    assert.equal(harness.proposalProvider.calls.length, 2);
    assert.equal(
        harness.proposalProvider.calls[1].promptState.points.length,
        2
    );
    harness.proposalProvider.deferreds[1].resolve(
        maskResponseFor(harness.proposalProvider.calls[1])
    );
    await second;
    await flush();
    assert.equal(session.state.requestStatus, 'idle');
    assert.equal(session.state.promptState.points.length, 2);
});

test('sessions are pruned when their View leaves the run', async () => {
    const harness = createHarness();
    await driveToActive(harness);
    const viewId = await addReadyUserView(harness);
    assert.ok(harness.userMasks.sessionFor(viewId));

    harness.confirmation.adjust();
    await flush();
    assert.equal(harness.userMasks.sessionFor(viewId), null);
    assert.equal(viewById(harness, viewId), undefined);
});
