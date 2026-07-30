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
    decodeMaskArtifact,
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    createPromptAdapterCapabilities
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    SelectionServiceTransportError
} = require('../.test-dist/src/selection-service-readiness.js');
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

const rankingFeatures = (relations = [], modelScore) => ({
    promptConsistency: {
        positivePointsSatisfied: true,
        negativePointsSatisfied: true
    },
    eligible: true,
    areaFraction: 1 / (64 * 48),
    boundingBox: { x0Px: 2, y0Px: 2, x1Px: 2, y1Px: 2 },
    connectedComponentCount: 1,
    positivePointComponentIds: [0],
    positivePointBoundaryDistances: [1],
    pairwiseRelations: relations,
    boundaryContactFraction: 0,
    compactness: Math.PI / 4,
    boxFillRatios: [],
    boxSpillRatios: [],
    promptMaskOverlap: 1,
    optionalSupportSanity: {
        participated: false,
        changedDecision: false
    },
    ...(modelScore === undefined ? {} : { modelScore })
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
    })),
    ...request.promptState.maskConstraints.map((prompt) => ({
        promptId: prompt.promptId,
        family: 'mask-constraint',
        polarity: prompt.polarity,
        satisfied: true,
        constraintCoverageFraction: 1,
        candidateCoverageFraction: 1
    }))
];

const maskResponseFor = (request, overrides = {}) => {
    const artifact =
        overrides.mask ?? bitsetArtifact(request.rgb.width, request.rgb.height);
    const promptDiagnostics = promptDiagnosticsFor(request);
    const proposals = overrides.proposals ?? [
        {
            proposalId: 'proposal-0',
            mask: artifact,
            sourceIndex: 0,
            promptConsistency: {
                positivePointsSatisfied: true,
                negativePointsSatisfied: true
            },
            ...(request.promptState.boxes.length === 0 &&
            request.promptState.maskConstraints.length === 0
                ? {}
                : { promptDiagnostics }),
            rankingFeatures: rankingFeatures()
        }
    ];
    const proposalPayload = {
        schemaVersion: 2,
        viewId: request.viewId,
        rgbDigest: request.rgb.digest,
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
    const proposalDecision =
        overrides.proposalDecision ??
        (proposalSet.proposals.length === 0
            ? {
                  schemaVersion: 1,
                  viewId: request.viewId,
                  rgbDigest: request.rgb.digest,
                  promptStateDigest: request.promptState.digest,
                  proposalSetDigest: proposalSet.digest,
                  rankingPolicyVersion: anchorMaskRankingPolicyVersion,
                  status: 'unavailable',
                  alternativeProposalIds: [],
                  reasons: [{ code: 'prompt-conflict', proposalIds: [] }]
              }
            : {
                  schemaVersion: 1,
                  viewId: request.viewId,
                  rgbDigest: request.rgb.digest,
                  promptStateDigest: request.promptState.digest,
                  proposalSetDigest: proposalSet.digest,
                  rankingPolicyVersion: anchorMaskRankingPolicyVersion,
                  status: 'selected',
                  selectedProposalId: proposalSet.proposals[0].proposalId,
                  alternativeProposalIds: [proposalSet.proposals[0].proposalId],
                  reasons: []
              });
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
        rgbDigest: request.rgb.digest,
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

const emptyProposalResponseFor = (request) => {
    const payload = {
        schemaVersion: 2,
        viewId: request.viewId,
        rgbDigest: request.rgb.digest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposals: []
    };
    return maskResponseFor(request, {
        proposalSet: {
            ...payload,
            digest: autoMaskProposalSetDigest(payload)
        }
    });
};

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
        produceMaskProposals:
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
        ...(options.promptCapabilities === undefined
            ? {}
            : {
                  getPromptAdapterCapabilities: () => options.promptCapabilities
              }),
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

const acceptSuggestedProposal = (mask) => {
    const proposalId = mask.state.proposalDecision?.selectedProposalId;
    assert.ok(proposalId);
    mask.acceptProposal(proposalId);
};

test('a prompt change automatically requests single-frame SAM feedback', async () => {
    const { mask, maskRequests } = await setup();
    assert.equal(maskRequests.length, 0);
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(maskRequests.length, 1);
    const request = maskRequests[0];
    assert.equal(request.viewId, 'anchor-view');
    assert.equal(request.promptState.points.length, 1);
    assert.equal(request.promptState.points[0].polarity, 'include');
    assert.ok(request.proposalAttemptId.length > 0);
    assert.equal(request.rgb.digest, `sha256:${'a'.repeat(64)}`);
    assert.equal(mask.state.proposalStatus, 'selected');
    assert.equal(mask.state.editingMask, null);
    acceptSuggestedProposal(mask);
    assert.equal(mask.state.editingMask.source, 'single-frame-sam');
    assert.equal(mask.state.editingMask.status, 'draft');
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.evidence.status, 'not-requested');
});

const richPromptCapabilities = createPromptAdapterCapabilities({
    points: true,
    negativePoints: true,
    boxes: true,
    negativeBoxes: true,
    maskInput: true,
    negativeMaskConstraints: true,
    text: true,
    negativeText: true,
    multiCandidateOutput: true,
    compilerPolicyVersion: 'test-rich-prompt-compiler/v1',
    unsupportedPromptReasons: {}
});

test('each new prompt serializes SAM attempts and resubmits the latest prompt set', async () => {
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
    // One in-flight SAM attempt per view: the Companion's single operation
    // slot never sees concurrent attempts from rapid prompting.
    assert.equal(maskRequests.length, 1);
    // The superseded first response is stale and must not publish.
    const staleMask = bitsetArtifact(64, 48, [[40, 40]]);
    gate.resolve(maskResponseFor(maskRequests[0], { mask: staleMask }));
    await first;
    await second;
    // Once the slot settles, the latest full prompt set resubmits as a new
    // attempt and is the one that publishes.
    assert.equal(maskRequests.length, 2);
    assert.deepEqual(
        maskRequests[1].promptState.points.map((prompt) => [
            prompt.xPx,
            prompt.yPx
        ]),
        [
            [10, 12],
            [20, 22]
        ]
    );
    assert.notEqual(
        maskRequests[1].proposalAttemptId,
        maskRequests[0].proposalAttemptId
    );
    acceptSuggestedProposal(mask);
    const editing = mask.state.editingMask;
    assert.equal(editing.prompts.length, 2);
    assert.notEqual(editing.artifact.digest, staleMask.digest);
    assert.equal(mask.state.requestStatus, 'idle');
});

test('a failed in-flight attempt still resubmits the latest prompt set once', async () => {
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return maskRequests.length === 1
                ? Promise.reject(new Error('transient SAM failure'))
                : Promise.resolve(maskResponseFor(request));
        }
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    await mask.addPrompt({ xPx: 20, yPx: 22, polarity: 'exclude' });
    assert.equal(maskRequests.length, 2);
    assert.deepEqual(
        maskRequests[1].promptState.points.map((prompt) => [
            prompt.xPx,
            prompt.yPx
        ]),
        [
            [10, 12],
            [20, 22]
        ]
    );
    acceptSuggestedProposal(mask);
    assert.equal(mask.state.editingMask.prompts.length, 2);
    assert.equal(mask.state.requestStatus, 'idle');
});

test('a single prompt with no concurrency never resubmits', async () => {
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return Promise.resolve(maskResponseFor(request));
        }
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(maskRequests.length, 1);
    assert.equal(mask.state.requestStatus, 'idle');
});

test('SAM output never silently overwrites the Stable Mask', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
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

test('stale inference cannot replace a newer committed local gesture', async () => {
    const gate = deferred();
    const maskRequests = [];
    const { mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return gate.promise;
        }
    });
    const pending = mask.addPrompt({
        xPx: 10,
        yPx: 12,
        polarity: 'include'
    });
    mask.applyBrushGesture({
        mode: 'add',
        radiusPx: 2,
        samples: [
            { xPx: 8, yPx: 8 },
            { xPx: 24, yPx: 24 }
        ]
    });
    const localGesture = mask.state.editingMask;

    gate.resolve(maskResponseFor(maskRequests[0]));
    await pending;

    assert.equal(mask.state.editingMask.maskId, localGesture.maskId);
    assert.equal(
        mask.state.editingMask.artifact.digest,
        localGesture.artifact.digest
    );
});

test('a brush stroke on a SAM Editing Mask creates a hybrid local revision', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
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
    acceptSuggestedProposal(mask);
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
    acceptSuggestedProposal(mask);
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
    assert.equal(mask.state.failureKind, 'maskProposalFailed');
    assert.equal(mask.state.errorMessage, 'SAM failed.');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');

    await mask.retryMaskRequest();
    assert.equal(maskRequests.length, 2);
    // An explicit Retry mints a new attempt identity for the same prompt set.
    assert.notEqual(
        maskRequests[1].proposalAttemptId,
        maskRequests[0].proposalAttemptId
    );
    assert.equal(mask.state.requestStatus, 'idle');
    acceptSuggestedProposal(mask);
    assert.equal(mask.state.editingMask.source, 'single-frame-sam');
});

test('an invalid SAM response binding fails the request, not the View', async () => {
    const { anchor, mask } = await setup({
        produceMask: (request) =>
            Promise.resolve(
                maskResponseFor(request, { proposalAttemptId: 'stale-attempt' })
            )
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.failureKind, 'maskProposalFailed');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('a structurally invalid SAM response fails the request, not the View', async () => {
    const { anchor, mask } = await setup({
        produceMask: () => Promise.resolve({ status: 'complete' })
    });
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.failureKind, 'maskArtifactInvalid');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('a Companion incompleteMaskSet error is classified as an invalid artifact', async () => {
    const { mask } = await setup({
        produceMask: () =>
            Promise.reject(
                new SelectionServiceTransportError(
                    'http',
                    'The Selection Service Companion returned HTTP 409.',
                    {
                        status: 409,
                        serviceCode: 'incompleteMaskSet',
                        serviceMessage: 'Invalid bounded alternative.'
                    }
                )
            )
    });

    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });

    assert.equal(mask.state.requestStatus, 'failed');
    assert.equal(mask.state.failureKind, 'maskArtifactInvalid');
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
    acceptSuggestedProposal(mask);
    mask.confirmEditingMask();
    assert.ok(mask.state.stableMask);
    await anchor.restart(input());
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.prompts.length, 0);
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.evidence.status, 'not-requested');
});

test('Restart logically cancels an in-flight proposal and discards its late result', async () => {
    const gate = deferred();
    const maskRequests = [];
    const { anchor, mask } = await setup({
        produceMask: (request) => {
            maskRequests.push(request);
            return gate.promise;
        }
    });
    const pending = mask.addPrompt({
        xPx: 10,
        yPx: 12,
        polarity: 'include'
    });

    await anchor.restart(input());
    gate.resolve(maskResponseFor(maskRequests[0]));
    await pending;

    assert.equal(mask.state.promptState.revision, 0);
    assert.equal(mask.state.proposalSet, null);
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.requestStatus, 'idle');
});

test('a new Anchor RGB identity resets prompts and Mask currency', async () => {
    const { anchor, mask, setRgbDigest } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
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

test('Restore Auto restores only an accepted Mask for the exact Prompt identity', async () => {
    const { mask } = await setup();
    assert.equal(mask.state.canRestoreAuto, false);
    assert.throws(() => mask.restoreAutoMask());
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
    const auto = mask.state.editingMask;
    mask.clearEditingMask();
    assert.equal(mask.state.canRestoreAuto, true);
    mask.restoreAutoMask();
    assert.equal(mask.state.editingMask.maskId, auto.maskId);
    // The current draft already is the latest auto Mask: nothing to restore.
    assert.equal(mask.state.canRestoreAuto, false);
    mask.clearEditingMask();
    await mask.addPrompt({ xPx: 20, yPx: 20, polarity: 'exclude' });
    assert.equal(mask.state.canRestoreAuto, false);
    assert.throws(() => mask.restoreAutoMask());
    mask.undoPromptEdit();
    assert.equal(mask.state.canRestoreAuto, true);
    mask.restoreAutoMask();
    assert.equal(mask.state.editingMask.maskId, auto.maskId);
});

test('mask-local Undo/Redo walks Editing history without touching the Stable Mask', async () => {
    const { mask } = await setup();
    assert.equal(mask.state.canUndo, false);
    assert.equal(mask.state.canRedo, false);
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
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
    acceptSuggestedProposal(mask);
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
    acceptSuggestedProposal(mask);
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
    acceptSuggestedProposal(mask);
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

test('unsupported prompt families are rejected before transport', async () => {
    const { mask, maskRequests } = await setup();
    await assert.rejects(
        mask.addBoxPrompt({
            x0Px: 1,
            y0Px: 1,
            x1Px: 10,
            y1Px: 10,
            polarity: 'include'
        }),
        /does not support positive-box/
    );
    await assert.rejects(
        mask.addTextPrompt({ text: 'chair', polarity: 'include' }),
        /does not support positive-text/
    );
    assert.equal(maskRequests.length, 0);
    assert.equal(mask.state.promptState.boxes.length, 0);
    assert.equal(mask.state.promptState.textPrompts.length, 0);
});

test('Box and Prompt Brush revise PromptState without editing pixels', async () => {
    const { mask, maskRequests } = await setup({
        promptCapabilities: richPromptCapabilities
    });
    await mask.addBoxPrompt({
        x0Px: 20,
        y0Px: 20,
        x1Px: 4,
        y1Px: 5,
        polarity: 'exclude'
    });
    assert.equal(mask.state.promptState.boxes.length, 1);
    assert.deepEqual(
        [
            mask.state.promptState.boxes[0].x0Px,
            mask.state.promptState.boxes[0].y0Px,
            mask.state.promptState.boxes[0].x1Px,
            mask.state.promptState.boxes[0].y1Px
        ],
        [4, 5, 20, 20]
    );
    assert.equal(mask.state.editingMask, null);

    await mask.addPromptBrushConstraint(
        [
            {
                xPx: 8,
                yPx: 9,
                radiusPx: 2,
                mode: 'add'
            }
        ],
        'include'
    );
    assert.equal(maskRequests.length, 2);
    assert.equal(mask.state.promptState.maskConstraints.length, 1);
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.stableMask, null);
    assert.equal(mask.state.evidence.status, 'not-requested');
});

test('Paint changes Editing Mask without rewriting PromptState', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
    const promptDigest = mask.state.promptState.digest;
    const promptRevision = mask.state.promptState.revision;

    mask.applyBrushStroke({
        xPx: 20,
        yPx: 20,
        radiusPx: 2,
        mode: 'add'
    });

    assert.equal(mask.state.promptState.digest, promptDigest);
    assert.equal(mask.state.promptState.revision, promptRevision);
    assert.equal(mask.state.editingMask.source, 'hybrid');
});

test('one rapid curved Paint gesture is continuous and one Mask Undo unit', async () => {
    const { mask } = await setup();
    const promptDigest = mask.state.promptState.digest;

    mask.applyBrushGesture({
        mode: 'add',
        radiusPx: 1,
        samples: [
            { xPx: 4, yPx: 4 },
            { xPx: 20, yPx: 4 },
            { xPx: 20, yPx: 20 },
            { xPx: 36, yPx: 20 }
        ]
    });

    const painted = decodeMaskArtifact(mask.state.editingMask.artifact);
    const isPainted = (x, y) =>
        (painted[(y * 64 + x) >> 3] & (1 << ((y * 64 + x) % 8))) !== 0;
    for (let x = 4; x <= 20; x += 1) {
        assert.equal(isPainted(x, 4), true, `horizontal gap at ${x},4`);
    }
    for (let y = 4; y <= 20; y += 1) {
        assert.equal(isPainted(20, y), true, `vertical gap at 20,${y}`);
    }
    for (let x = 20; x <= 36; x += 1) {
        assert.equal(isPainted(x, 20), true, `horizontal gap at ${x},20`);
    }
    assert.equal(mask.state.promptState.digest, promptDigest);

    mask.undoMaskEdit();
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.canUndo, false);
    assert.equal(mask.state.promptState.digest, promptDigest);

    mask.redoMaskEdit();
    assert.deepEqual(
        decodeMaskArtifact(mask.state.editingMask.artifact),
        painted
    );
});

test('Paint and Erase gestures never revise PromptState', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    const promptDigest = mask.state.promptState.digest;
    const promptRevision = mask.state.promptState.revision;

    for (const mode of ['add', 'erase']) {
        mask.applyBrushGesture({
            mode,
            radiusPx: 2,
            samples: [
                { xPx: 8, yPx: 8 },
                { xPx: 16, yPx: 16 }
            ]
        });
        assert.equal(mask.state.promptState.digest, promptDigest);
        assert.equal(mask.state.promptState.revision, promptRevision);
    }
});

test('Prompt Undo and Mask Undo are independent histories', async () => {
    const { mask } = await setup({
        promptCapabilities: richPromptCapabilities
    });
    await mask.addBoxPrompt({
        x0Px: 1,
        y0Px: 1,
        x1Px: 10,
        y1Px: 10,
        polarity: 'include'
    });
    const promptDigest = mask.state.promptState.digest;
    mask.applyBrushStroke({
        xPx: 20,
        yPx: 20,
        radiusPx: 1,
        mode: 'add'
    });
    const editingId = mask.state.editingMask.maskId;

    mask.undoPromptEdit();
    assert.notEqual(mask.state.promptState.digest, promptDigest);
    assert.equal(mask.state.editingMask.maskId, editingId);

    mask.undoMaskEdit();
    assert.equal(mask.state.editingMask, null);
    assert.equal(mask.state.promptState.boxes.length, 0);
    mask.redoPromptEdit();
    assert.equal(mask.state.promptState.digest, promptDigest);
    assert.equal(mask.state.editingMask, null);
});

test('Clear Prompts preserves the Stable Mask and current Evidence', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    mask.evidenceRegistry.markReady(
        {
            viewId: 'anchor-view',
            rgbDigest: stable.createdFromRgbDigest,
            stableMaskDigest: stable.artifact.digest,
            evidencePolicyDigest: aiSelectEvidencePolicyVersion
        },
        'evidence-1'
    );

    mask.clearPrompts();

    assert.equal(mask.state.promptState.points.length, 0);
    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    assert.equal(mask.state.evidence.status, 'ready');
});

test('unconfirmed Prompt and proposal work leaves Stable Mask and Evidence current', async () => {
    const { mask } = await setup();
    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    acceptSuggestedProposal(mask);
    mask.confirmEditingMask();
    const stable = mask.state.stableMask;
    const identity = {
        viewId: 'anchor-view',
        rgbDigest: stable.createdFromRgbDigest,
        stableMaskDigest: stable.artifact.digest,
        evidencePolicyDigest: aiSelectEvidencePolicyVersion
    };
    mask.evidenceRegistry.markReady(identity, 'evidence-1');

    await mask.addPrompt({ xPx: 20, yPx: 20, polarity: 'exclude' });

    assert.equal(mask.state.stableMask.maskId, stable.maskId);
    assert.equal(mask.state.evidence.status, 'ready');
});

test('no-candidate output is proposal unavailable, not render or technical failure', async () => {
    const { anchor, mask } = await setup({
        produceMask: (request) =>
            Promise.resolve(emptyProposalResponseFor(request))
    });

    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });

    assert.equal(mask.state.proposalStatus, 'unavailable');
    assert.equal(mask.state.requestStatus, 'idle');
    assert.equal(mask.state.editingMask, null);
    assert.equal(anchor.state.anchor.renderStatus, 'ready');
});

test('published proposal state is isolated from later transport-object mutation', async () => {
    let transportResponse;
    const { mask } = await setup({
        produceMask: (request) => {
            transportResponse = maskResponseFor(request);
            return Promise.resolve(transportResponse);
        }
    });

    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });
    transportResponse.proposalDecision.status = 'unavailable';
    transportResponse.proposalSet.proposals[0].rankingFeatures.eligible = false;

    assert.equal(mask.state.proposalDecision.status, 'selected');
    assert.equal(
        mask.state.proposalSet.proposals[0].rankingFeatures.eligible,
        true
    );
    assert.equal(Object.isFrozen(mask.state.proposalDecision), true);
    assert.equal(
        Object.isFrozen(mask.state.proposalSet.proposals[0].rankingFeatures),
        true
    );
});

test('explicit acceptance rejects proposals excluded by the bound decision', async () => {
    const { mask } = await setup({
        produceMask: (request) => {
            const base = maskResponseFor(request);
            const eligible = {
                ...base.proposalSet.proposals[0],
                rankingFeatures: {
                    ...base.proposalSet.proposals[0].rankingFeatures,
                    pairwiseRelations: [
                        {
                            proposalId: 'proposal-1',
                            intersectionOverUnion: 1,
                            areaRatio: 1,
                            containment: 'none',
                            materiallyDistinct: false
                        }
                    ]
                }
            };
            const ineligibleFacts = {
                positivePointsSatisfied: false,
                negativePointsSatisfied: true
            };
            const ineligible = {
                ...eligible,
                proposalId: 'proposal-1',
                sourceIndex: 1,
                promptConsistency: ineligibleFacts,
                rankingFeatures: {
                    ...eligible.rankingFeatures,
                    promptConsistency: ineligibleFacts,
                    eligible: false,
                    pairwiseRelations: [
                        {
                            proposalId: 'proposal-0',
                            intersectionOverUnion: 1,
                            areaRatio: 1,
                            containment: 'none',
                            materiallyDistinct: false
                        }
                    ]
                }
            };
            const proposalPayload = {
                ...base.proposalSet,
                proposals: [eligible, ineligible]
            };
            delete proposalPayload.digest;
            const proposalSet = {
                ...proposalPayload,
                digest: autoMaskProposalSetDigest(proposalPayload)
            };
            return Promise.resolve({
                ...base,
                proposalSet,
                proposalDecision: {
                    ...base.proposalDecision,
                    proposalSetDigest: proposalSet.digest
                }
            });
        }
    });

    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });

    assert.throws(() => mask.acceptProposal('proposal-1'), /ineligible/);
    mask.acceptProposal('proposal-0');
    assert.equal(mask.state.acceptedProposalId, 'proposal-0');
});

test('an ambiguous proposal set preserves alternatives until explicit acceptance', async () => {
    const firstMask = bitsetArtifact(64, 48, [[10, 12]]);
    const secondMask = bitsetArtifact(64, 48, [
        [10, 12],
        [11, 12],
        [10, 13]
    ]);
    const proposals = [
        {
            proposalId: 'proposal-0',
            mask: firstMask,
            sourceIndex: 0,
            modelScore: 0.91,
            modelScoreSemantics: 'adapter-local score',
            promptConsistency: {
                positivePointsSatisfied: true,
                negativePointsSatisfied: true
            },
            rankingFeatures: rankingFeatures(
                [
                    {
                        proposalId: 'proposal-1',
                        intersectionOverUnion: 1 / 3,
                        areaRatio: 3,
                        containment: 'contained-by',
                        materiallyDistinct: true
                    }
                ],
                0.91
            )
        },
        {
            proposalId: 'proposal-1',
            mask: secondMask,
            sourceIndex: 1,
            modelScore: 0.89,
            modelScoreSemantics: 'adapter-local score',
            promptConsistency: {
                positivePointsSatisfied: true,
                negativePointsSatisfied: true
            },
            rankingFeatures: rankingFeatures(
                [
                    {
                        proposalId: 'proposal-0',
                        intersectionOverUnion: 1 / 3,
                        areaRatio: 3,
                        containment: 'contains',
                        materiallyDistinct: true
                    }
                ],
                0.89
            )
        }
    ];
    const { mask } = await setup({
        promptCapabilities: richPromptCapabilities,
        produceMask: (request) => {
            const response = maskResponseFor(request, { proposals });
            response.proposalDecision = {
                schemaVersion: 1,
                viewId: request.viewId,
                rgbDigest: request.rgb.digest,
                promptStateDigest: request.promptState.digest,
                proposalSetDigest: response.proposalSet.digest,
                rankingPolicyVersion: anchorMaskRankingPolicyVersion,
                status: 'ambiguous',
                selectedProposalId: 'proposal-0',
                alternativeProposalIds: ['proposal-0', 'proposal-1'],
                reasons: [
                    {
                        code: 'nested-part-vs-whole',
                        proposalIds: ['proposal-0', 'proposal-1']
                    }
                ]
            };
            return Promise.resolve(response);
        }
    });

    await mask.addPrompt({ xPx: 10, yPx: 12, polarity: 'include' });

    assert.equal(mask.state.proposalStatus, 'ambiguous');
    assert.equal(mask.state.editingMask, null);
    assert.equal(
        mask.state.proposalDecision.reasons[0].code,
        'nested-part-vs-whole'
    );

    mask.acceptProposal('proposal-1');

    assert.equal(mask.state.acceptedProposalId, 'proposal-1');
    assert.equal(mask.state.editingMask.artifact.digest, secondMask.digest);
    assert.equal(mask.state.stableMask, null);
});
