const assert = require('node:assert/strict');
const test = require('node:test');

const {
    isAIViewMaskRequest,
    isMaskResultResponse,
    maskResponseMatchesRequest
} = require('../.test-dist/src/ai-select/mask-service.js');
const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    createEmptyPromptState,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const bitsetArtifact = (width, height, firstByte) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    bytes[0] = firstByte;
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return {
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    };
};

const promptState = () =>
    revisePromptState(createEmptyPromptState('anchor-view', digest('a')), {
        points: [
            {
                promptId: 'p-1',
                xPx: 2,
                yPx: 2,
                polarity: 'include'
            }
        ]
    });

const request = (overrides = {}) => ({
    requestBinding: {
        targetContextId: 'ai-target-context-1',
        contextRevision: 3,
        dependencyToken: {
            splatId: 'editor-splat:1',
            renderStateToken: 'render-v1',
            geometryToken: 'geometry-v1',
            gaussianIdentityToken: 'gaussians-v1',
            worldTransformToken: 'transform-v1'
        }
    },
    target: { splatId: 'editor-splat:1' },
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    viewId: 'anchor-view',
    cameraBindingDigest: digest('e'),
    rgb: {
        pngBase64: 'aGVsbG8=',
        digest: digest('a'),
        width: 8,
        height: 8
    },
    promptState: promptState(),
    modelManifestDigest: 'modelscope-facebook-sam31-616acbee',
    adapterCapabilityDigest: digest('d'),
    proposalPolicyVersion: 'auto-mask-proposals/bounded-source-order-v1',
    rankingPolicyVersion: anchorMaskRankingPolicyVersion,
    proposalAttemptId: 'proposal-attempt-7',
    ...overrides
});

const proposalSetFor = (req, overrides = {}) => {
    const payload = {
        schemaVersion: 2,
        viewId: req.viewId,
        rgbDigest: req.rgb.digest,
        promptStateDigest: req.promptState.digest,
        modelManifestDigest: req.modelManifestDigest,
        adapterCapabilityDigest: req.adapterCapabilityDigest,
        proposalPolicyVersion: req.proposalPolicyVersion,
        proposalAttemptId: req.proposalAttemptId,
        proposals: [
            {
                proposalId: 'proposal-0',
                sourceIndex: 0,
                mask: bitsetArtifact(req.rgb.width, req.rgb.height, 0b101),
                modelScore: 2.5,
                modelScoreSemantics: 'adapter-local score',
                promptConsistency: {
                    positivePointsSatisfied: true,
                    negativePointsSatisfied: true
                },
                rankingFeatures: {
                    promptConsistency: {
                        positivePointsSatisfied: true,
                        negativePointsSatisfied: true
                    },
                    eligible: true,
                    areaFraction: 2 / 64,
                    boundingBox: {
                        x0Px: 0,
                        y0Px: 0,
                        x1Px: 2,
                        y1Px: 0
                    },
                    connectedComponentCount: 2,
                    positivePointComponentIds: [0],
                    positivePointBoundaryDistances: [1],
                    pairwiseRelations: [],
                    boundaryContactFraction: 0.25,
                    compactness: 0.2,
                    boxFillRatios: [],
                    boxSpillRatios: [],
                    promptMaskOverlap: 1,
                    optionalSupportSanity: {
                        participated: false,
                        changedDecision: false
                    },
                    modelScore: 2.5
                }
            }
        ],
        ...overrides
    };
    return { ...payload, digest: autoMaskProposalSetDigest(payload) };
};

const responseFor = (req, overrides = {}) => {
    const proposalSet = overrides.proposalSet ?? proposalSetFor(req);
    return {
        requestBinding: req.requestBinding,
        targetSplatId: req.target.splatId,
        sceneId: req.sceneId,
        sceneVersion: req.sceneVersion,
        viewId: req.viewId,
        cameraBindingDigest: req.cameraBindingDigest,
        rgbDigest: req.rgb.digest,
        promptStateDigest: req.promptState.digest,
        modelManifestDigest: req.modelManifestDigest,
        adapterCapabilityDigest: req.adapterCapabilityDigest,
        proposalPolicyVersion: req.proposalPolicyVersion,
        rankingPolicyVersion: req.rankingPolicyVersion,
        proposalAttemptId: req.proposalAttemptId,
        proposalSet,
        proposalDecision: {
            schemaVersion: 1,
            viewId: req.viewId,
            rgbDigest: req.rgb.digest,
            promptStateDigest: req.promptState.digest,
            proposalSetDigest: proposalSet.digest,
            rankingPolicyVersion: req.rankingPolicyVersion,
            status: 'selected',
            selectedProposalId: 'proposal-0',
            alternativeProposalIds: ['proposal-0'],
            reasons: []
        },
        ...overrides
    };
};

test('a complete bound proposal response matches its request', () => {
    const req = request();
    const response = responseFor(req);
    assert.ok(isMaskResultResponse(response));
    assert.ok(maskResponseMatchesRequest(response, req));
});

test('the request requires exact RGB, PromptState, capability, policy, and attempt identity', () => {
    assert.ok(isAIViewMaskRequest(request()));
    assert.ok(!isAIViewMaskRequest(request({ proposalAttemptId: '' })));
    assert.ok(!isAIViewMaskRequest(request({ adapterCapabilityDigest: '' })));
    assert.ok(!isAIViewMaskRequest(request({ modelManifestDigest: '' })));
    assert.ok(!isAIViewMaskRequest(request({ rankingPolicyVersion: '' })));
    assert.ok(
        !isAIViewMaskRequest(
            request({
                promptState: {
                    ...promptState(),
                    rgbDigest: digest('b')
                }
            })
        )
    );
    const mismatchedTarget = request();
    mismatchedTarget.target = { splatId: 'other-splat' };
    assert.ok(!isAIViewMaskRequest(mismatchedTarget));
});

test('stale, corrupt, or partial proposal responses are rejected', () => {
    const req = request();
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { rgbDigest: digest('b') }),
            req
        )
    );
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, {
                proposalAttemptId: 'proposal-attempt-8'
            }),
            req
        )
    );
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { adapterCapabilityDigest: digest('c') }),
            req
        )
    );
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { rankingPolicyVersion: 'stale-ranking/v0' }),
            req
        )
    );
    assert.ok(
        !isMaskResultResponse(
            responseFor(req, {
                proposalDecision: {
                    ...responseFor(req).proposalDecision,
                    proposalSetDigest: digest('f')
                }
            })
        )
    );
    const wrongRevision = responseFor(req);
    wrongRevision.requestBinding = {
        ...req.requestBinding,
        contextRevision: 4
    };
    assert.ok(!maskResponseMatchesRequest(wrongRevision, req));
    const proposalSet = proposalSetFor(req);
    proposalSet.proposals[0].mask.data = bitsetArtifact(
        req.rgb.width,
        req.rgb.height,
        0b111
    ).data;
    assert.ok(!isMaskResultResponse(responseFor(req, { proposalSet })));
    assert.ok(!isMaskResultResponse({ status: 'maskProposalError' }));
});

test('a visual Prompt request requires per-family candidate diagnostics', () => {
    const base = promptState();
    const visualPromptState = revisePromptState(base, {
        boxes: [
            {
                promptId: 'box-1',
                polarity: 'include',
                x0Px: 1,
                y0Px: 1,
                x1Px: 3,
                y1Px: 3
            }
        ]
    });
    const req = request({ promptState: visualPromptState });

    assert.ok(isAIViewMaskRequest(req));
    assert.ok(!maskResponseMatchesRequest(responseFor(req), req));

    const proposalSet = proposalSetFor(req);
    proposalSet.proposals[0].promptConsistency = {
        ...proposalSet.proposals[0].promptConsistency,
        positiveBoxesSatisfied: true
    };
    proposalSet.proposals[0].rankingFeatures.promptConsistency = {
        ...proposalSet.proposals[0].rankingFeatures.promptConsistency,
        positiveBoxesSatisfied: true
    };
    proposalSet.proposals[0].promptDiagnostics = [
        {
            promptId: 'p-1',
            family: 'point',
            polarity: 'include',
            satisfied: true
        },
        {
            promptId: 'box-1',
            family: 'box',
            polarity: 'include',
            satisfied: true,
            constraintCoverageFraction: 0.75,
            candidateCoverageFraction: 0.5
        }
    ];
    proposalSet.digest = autoMaskProposalSetDigest({
        ...proposalSet,
        digest: undefined
    });
    assert.ok(
        maskResponseMatchesRequest(responseFor(req, { proposalSet }), req)
    );

    proposalSet.proposals[0].promptDiagnostics[1].satisfied = false;
    proposalSet.digest = autoMaskProposalSetDigest({
        ...proposalSet,
        digest: undefined
    });
    assert.ok(
        !maskResponseMatchesRequest(responseFor(req, { proposalSet }), req)
    );
});
