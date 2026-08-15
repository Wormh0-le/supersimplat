const assert = require('node:assert/strict');
const test = require('node:test');

const {
    isAIViewMaskRequest,
    isMaskResultResponse,
    isPreviousPredictionLogitsRef,
    maskResponseMatchesRequest
} = require('../.test-dist/src/ai-select/mask-service.js');
const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest,
    autoMaskProposalPolicyVersion
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    previousPredictionLogitsRefDigest
} = require('../.test-dist/src/ai-select/previous-logits-ref.js');
const {
    createEmptyPromptState,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');
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

const rgbArtifact = () => ({
    pngBase64: 'aGVsbG8=',
    digest: digest('a'),
    width: 8,
    height: 8
});

const logitsRefPayload = () => ({
    schemaVersion: 1,
    companionInstanceId: 'companion-instance-1',
    stateId: 'logits-state-1',
    targetContextId: 'ai-target-context-1',
    viewId: 'anchor-view',
    rgbDigest: digest('a'),
    sourceInferenceAttemptId: 'proposal-attempt-6',
    sourceCandidateId: 'proposal-0',
    adapterRuntimeDigest: digest('9'),
    shape: [1, 288, 288],
    dtype: 'float32',
    dataDigest: digest('8')
});

const logitsRef = (overrides = {}) => {
    const payload = { ...logitsRefPayload(), ...overrides };
    return {
        ...payload,
        refDigest: previousPredictionLogitsRefDigest(payload)
    };
};

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
    rgbDigest: digest('a'),
    rgbWidth: 8,
    rgbHeight: 8,
    rgb: rgbArtifact(),
    promptState: promptState(),
    modelManifestDigest: 'modelscope-facebook-sam3-image-616acbee',
    adapterCapabilityDigest: digest('d'),
    proposalPolicyVersion: autoMaskProposalPolicyVersion,
    rankingPolicyVersion: anchorMaskRankingPolicyVersion,
    proposalAttemptId: 'proposal-attempt-7',
    ...overrides
});

const promptConsistency = () => ({
    positivePointsSatisfied: true,
    negativePointsSatisfied: true,
    positiveBoxesSatisfied: true
});

const goodReview = () => ({
    status: 'good',
    reasons: [],
    actionableReasons: [],
    policyVersion: aiSelectViewAssessmentPolicyVersion,
    diagnostics: {
        framePixels: 64,
        foregroundPixels: 2,
        boundaryPixels: 0,
        boundaryContactRatio: 0,
        connectedComponents: 2,
        largestComponentRatio: 0.5,
        promptPointCount: 1,
        promptViolationCount: 0,
        boxSpillPixels: null,
        boxSpillRatio: null
    }
});

const proposalSetFor = (req, overrides = {}) => {
    const payload = {
        schemaVersion: 4,
        viewId: req.viewId,
        rgbDigest: req.rgbDigest,
        promptStateDigest: req.promptState.digest,
        modelManifestDigest: req.modelManifestDigest,
        adapterCapabilityDigest: req.adapterCapabilityDigest,
        proposalPolicyVersion: req.proposalPolicyVersion,
        proposalAttemptId: req.proposalAttemptId,
        proposals: [
            {
                proposalId: 'proposal-0',
                sourceIndex: 0,
                mask: bitsetArtifact(req.rgbWidth, req.rgbHeight, 0b101),
                modelScore: 2.5,
                modelScoreSemantics: 'adapter-local score',
                promptConsistency: promptConsistency(),
                rankingFeatures: {
                    promptConsistency: promptConsistency(),
                    eligible: true,
                    areaFraction: 2 / 64,
                    connectedComponentCount: 2,
                    modelScore: 2.5
                },
                review: goodReview()
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
        rgbDigest: req.rgbDigest,
        promptStateDigest: req.promptState.digest,
        modelManifestDigest: req.modelManifestDigest,
        adapterCapabilityDigest: req.adapterCapabilityDigest,
        proposalPolicyVersion: req.proposalPolicyVersion,
        rankingPolicyVersion: req.rankingPolicyVersion,
        proposalAttemptId: req.proposalAttemptId,
        proposalSet,
        proposalDecision: {
            schemaVersion: 2,
            viewId: req.viewId,
            rgbDigest: req.rgbDigest,
            promptStateDigest: req.promptState.digest,
            proposalSetDigest: proposalSet.digest,
            rankingPolicyVersion: req.rankingPolicyVersion,
            status: 'selected',
            selectedProposalId: 'proposal-0',
            alternativeProposalIds: ['proposal-0']
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

test('responses match on RGB digest, not on RGB artifact presence', () => {
    const req = request({ rgb: undefined });
    assert.ok(isAIViewMaskRequest(req));
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
    assert.ok(!isAIViewMaskRequest(request({ rgbWidth: 0 })));
    assert.ok(!isAIViewMaskRequest(request({ rgbHeight: -1 })));
    assert.ok(!isAIViewMaskRequest(request({ rgbDigest: 'not-a-digest' })));
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
    // An inlined artifact must agree with the request RGB identity.
    assert.ok(
        !isAIViewMaskRequest(
            request({ rgb: { ...rgbArtifact(), digest: digest('b') } })
        )
    );
    assert.ok(
        !isAIViewMaskRequest(request({ rgb: { ...rgbArtifact(), width: 9 } }))
    );
    const mismatchedTarget = request();
    mismatchedTarget.target = { splatId: 'other-splat' };
    assert.ok(!isAIViewMaskRequest(mismatchedTarget));
});

test('a previous-logits reference is structural, digest-bound, and lineage-bound', () => {
    const ref = logitsRef();
    assert.ok(isPreviousPredictionLogitsRef(ref));
    assert.ok(isAIViewMaskRequest(request({ previousLogitsRef: ref })));

    // A tampered payload invalidates the recomputed refDigest.
    assert.ok(!isPreviousPredictionLogitsRef({ ...ref, stateId: 'other' }));
    // Extra keys (for example raw tensor bytes) fail closed.
    assert.ok(!isPreviousPredictionLogitsRef({ ...ref, logitsBase64: 'AAAA' }));
    // The ref must bind the exact request View/RGB/target lineage.
    assert.ok(
        !isAIViewMaskRequest(
            request({ previousLogitsRef: logitsRef({ viewId: 'view-2' }) })
        )
    );
    assert.ok(
        !isAIViewMaskRequest(
            request({
                previousLogitsRef: logitsRef({ rgbDigest: digest('b') })
            })
        )
    );
    assert.ok(
        !isAIViewMaskRequest(
            request({
                previousLogitsRef: logitsRef({
                    targetContextId: 'ai-target-context-2'
                })
            })
        )
    );
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
        req.rgbWidth,
        req.rgbHeight,
        0b111
    ).data;
    assert.ok(!isMaskResultResponse(responseFor(req, { proposalSet })));
    assert.ok(!isMaskResultResponse({ status: 'maskProposalError' }));
});

test('a Box prompt request requires per-family candidate diagnostics', () => {
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

test('the single-result candidate bound is enforced fail-closed for every prompt', () => {
    const candidateFor = (req, index, promptDiagnostics) => ({
        proposalId: `proposal-${index}`,
        sourceIndex: index,
        mask: bitsetArtifact(req.rgbWidth, req.rgbHeight, 0b101),
        modelScore: 1 - index * 0.1,
        promptConsistency: promptConsistency(),
        ...(promptDiagnostics === undefined ? {} : { promptDiagnostics }),
        rankingFeatures: {
            promptConsistency: promptConsistency(),
            eligible: true,
            areaFraction: 2 / 64,
            connectedComponentCount: 2,
            modelScore: 1 - index * 0.1
        },
        review: goodReview()
    });
    const responseWithCandidates = (req, proposals) => {
        const payload = {
            ...proposalSetFor(req),
            proposals
        };
        delete payload.digest;
        const proposalSet = {
            ...payload,
            digest: autoMaskProposalSetDigest(payload)
        };
        return responseFor(req, {
            proposalSet,
            proposalDecision: {
                schemaVersion: 2,
                viewId: req.viewId,
                rgbDigest: req.rgbDigest,
                promptStateDigest: req.promptState.digest,
                proposalSetDigest: proposalSet.digest,
                rankingPolicyVersion: req.rankingPolicyVersion,
                status: proposals.length > 1 ? 'ambiguous' : 'selected',
                selectedProposalId: 'proposal-0',
                alternativeProposalIds: proposals.map(
                    (proposal) => proposal.proposalId
                )
            }
        });
    };

    // One include Point publishes one result; two fail at the wire boundary.
    const pointReq = request();
    const oneCandidate = responseWithCandidates(pointReq, [
        candidateFor(pointReq, 0)
    ]);
    assert.ok(isMaskResultResponse(oneCandidate));
    assert.ok(maskResponseMatchesRequest(oneCandidate, pointReq));
    const twoPointCandidates = responseWithCandidates(
        pointReq,
        [0, 1].map((index) => candidateFor(pointReq, index))
    );
    assert.ok(!isMaskResultResponse(twoPointCandidates));
    assert.ok(!maskResponseMatchesRequest(twoPointCandidates, pointReq));

    // A Box prompt forces single-mask mode: two candidates fail closed even
    // though the response is otherwise structurally valid and fully bound.
    const boxReq = request({
        promptState: revisePromptState(promptState(), {
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
        })
    });
    const boxDiagnostics = [
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
            satisfied: true
        }
    ];
    const twoBoxCandidates = responseWithCandidates(
        boxReq,
        [0, 1].map((index) => candidateFor(boxReq, index, boxDiagnostics))
    );
    assert.ok(!isMaskResultResponse(twoBoxCandidates));
    assert.ok(!maskResponseMatchesRequest(twoBoxCandidates, boxReq));

    // A refinement attempt also forces single-mask mode.
    const refinedReq = request({ previousLogitsRef: logitsRef() });
    const twoRefinedCandidates = responseWithCandidates(
        refinedReq,
        [0, 1].map((index) => candidateFor(refinedReq, index))
    );
    assert.ok(!isMaskResultResponse(twoRefinedCandidates));
    assert.ok(!maskResponseMatchesRequest(twoRefinedCandidates, refinedReq));
});
