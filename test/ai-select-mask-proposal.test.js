const assert = require('node:assert/strict');
const test = require('node:test');

const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalPolicyVersion,
    autoMaskProposalSetDigest,
    defaultPreviewProposalOrder,
    isAutoMaskProposalSet,
    isProposalDecision,
    maximumAutoMaskProposalCount,
    proposalIdentityDigest
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

const digest = (character) => `sha256:${character.repeat(64)}`;

test('proposal identity canonicalizes browser numbers by binary64 value', () => {
    assert.equal(
        proposalIdentityDigest({
            integer: 1,
            negativeZero: -0,
            smallExponent: 1e-7,
            fixed: 1e-5,
            large: 1e20,
            values: [0.1, -2]
        }),
        'sha256:a64229f647814d4cff1565284ed59b3cba0fd8ea7001249fc11f20da65163e58'
    );
});

const mask = {
    encoding: 'bitset-lsb-v1',
    width: 1,
    height: 1,
    data: 'AQ==',
    digest: 'sha256:4bf5122f344554c53bde2ebb8cd2b7e3d1600ad631c385a5d7cce23c7785459a'
};

const promptConsistency = () => ({
    positivePointsSatisfied: true,
    negativePointsSatisfied: true,
    positiveBoxesSatisfied: true
});

// The slimmed 07A feature record: prompt facts, eligibility, and the geometry
// the decision and candidate UI consume. Nothing else survives validation.
const rankingFeatures = {
    promptConsistency: promptConsistency(),
    eligible: true,
    areaFraction: 1,
    connectedComponentCount: 1,
    modelScore: 2.5
};

const reviewDiagnostics = (overrides = {}) => ({
    framePixels: 1,
    foregroundPixels: 1,
    boundaryPixels: 0,
    boundaryContactRatio: 0,
    connectedComponents: 1,
    largestComponentRatio: 1,
    promptPointCount: 1,
    promptViolationCount: 0,
    boxSpillPixels: null,
    boxSpillRatio: null,
    ...overrides
});

const goodReview = () => ({
    status: 'good',
    reasons: [],
    actionableReasons: [],
    policyVersion: aiSelectViewAssessmentPolicyVersion,
    diagnostics: reviewDiagnostics()
});

const logitsRef = () => {
    const payload = {
        schemaVersion: 1,
        companionInstanceId: 'companion-instance-1',
        stateId: 'logits-state-1',
        targetContextId: 'ai-target-context-1',
        viewId: 'anchor-view',
        rgbDigest: digest('a'),
        sourceInferenceAttemptId: 'proposal-attempt-0',
        sourceCandidateId: 'proposal-0',
        adapterRuntimeDigest: digest('9'),
        shape: [1, 288, 288],
        dtype: 'float32',
        dataDigest: digest('8')
    };
    return {
        ...payload,
        refDigest: previousPredictionLogitsRefDigest(payload)
    };
};

const proposalSet = () => {
    const value = {
        schemaVersion: 4,
        viewId: 'anchor-view',
        rgbDigest: digest('a'),
        promptStateDigest: digest('b'),
        modelManifestDigest: digest('c'),
        adapterCapabilityDigest: digest('d'),
        proposalPolicyVersion: autoMaskProposalPolicyVersion,
        proposalAttemptId: 'proposal-attempt-1',
        proposals: [
            {
                proposalId: 'proposal-0',
                mask,
                sourceIndex: 0,
                modelScore: 2.5,
                modelScoreSemantics: 'adapter-local logit',
                promptConsistency: promptConsistency(),
                rankingFeatures,
                review: goodReview(),
                logitsRef: logitsRef()
            }
        ]
    };
    return { ...value, digest: autoMaskProposalSetDigest(value) };
};

const withProposal = (value, proposal) => {
    const payload = {
        ...value,
        proposals: [proposal]
    };
    delete payload.digest;
    return {
        ...payload,
        digest: autoMaskProposalSetDigest(payload)
    };
};

const proposalFor = (sourceIndex, overrides = {}) => ({
    proposalId: `proposal-${sourceIndex}`,
    mask,
    sourceIndex,
    promptConsistency: promptConsistency(),
    rankingFeatures: {
        promptConsistency: promptConsistency(),
        eligible: true,
        areaFraction: 1,
        connectedComponentCount: 1
    },
    review: goodReview(),
    ...overrides
});

const withScore = (proposal, modelScore) => ({
    ...proposal,
    modelScore,
    rankingFeatures: { ...proposal.rankingFeatures, modelScore }
});

const withProposals = (base, proposals) => {
    const payload = { ...base, proposals };
    delete payload.digest;
    return { ...payload, digest: autoMaskProposalSetDigest(payload) };
};

const decisionFor = (set, overrides = {}) => ({
    schemaVersion: 2,
    viewId: set.viewId,
    rgbDigest: set.rgbDigest,
    promptStateDigest: set.promptStateDigest,
    proposalSetDigest: set.digest,
    rankingPolicyVersion: anchorMaskRankingPolicyVersion,
    status: 'selected',
    selectedProposalId: 'proposal-0',
    alternativeProposalIds: ['proposal-0'],
    ...overrides
});

test('policy identities rotate to the 07A per-candidate Review contract', () => {
    assert.equal(
        autoMaskProposalPolicyVersion,
        'auto-mask-proposals/bounded-source-order-v2'
    );
    assert.equal(anchorMaskRankingPolicyVersion, 'anchor-mask-ranking/v3');
});

test('a v4 bounded proposal set preserves score semantics and exact identity', () => {
    const value = proposalSet();
    assert.equal(isAutoMaskProposalSet(value), true);
    assert.equal(value.proposals[0].modelScoreSemantics, 'adapter-local logit');
    assert.equal(
        isAutoMaskProposalSet({ ...value, proposalAttemptId: 'stale-attempt' }),
        false
    );
    // A v3 proposal set identity fails closed on the v4 schema.
    assert.equal(isAutoMaskProposalSet({ ...value, schemaVersion: 3 }), false);
});

test('the removed v1 ranking machinery fails closed', () => {
    const value = proposalSet();
    const proposal = value.proposals[0];
    for (const removed of [
        { boundingBox: { x0Px: 0, y0Px: 0, x1Px: 0, y1Px: 0 } },
        { positivePointComponentIds: [0] },
        { positivePointBoundaryDistances: [1] },
        { pairwiseRelations: [] },
        { boundaryContactFraction: 1 },
        { compactness: Math.PI / 4 },
        { boxFillRatios: [] },
        { boxSpillRatios: [] },
        { promptMaskOverlap: 1 },
        {
            optionalSupportSanity: {
                participated: false,
                changedDecision: false
            }
        }
    ]) {
        assert.equal(
            isAutoMaskProposalSet(
                withProposal(value, {
                    ...proposal,
                    rankingFeatures: {
                        ...proposal.rankingFeatures,
                        ...removed
                    }
                })
            ),
            false,
            Object.keys(removed)[0]
        );
    }
});

test('every proposal carries an evidence-backed per-candidate Mask Review', () => {
    const value = proposalSet();
    const proposal = value.proposals[0];
    // The Review record is required.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, { ...proposal, review: undefined })
        ),
        false
    );
    // A genuine evidence-backed Review is accepted: 200 foreground pixels in
    // 4 components with a 50% largest component leaves 100 disconnected
    // pixels, well past the fragmentation thresholds.
    const evidenceBackedReview = {
        status: 'review',
        primaryReason: 'severely-fragmented',
        reasons: ['severely-fragmented'],
        actionableReasons: ['severely-fragmented'],
        policyVersion: aiSelectViewAssessmentPolicyVersion,
        diagnostics: reviewDiagnostics({
            framePixels: 3072,
            foregroundPixels: 200,
            connectedComponents: 4,
            largestComponentRatio: 0.5
        })
    };
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, { ...proposal, review: evidenceBackedReview })
        ),
        true
    );
    // The same claim against a healthy single-component Mask is fabricated.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                review: {
                    ...evidenceBackedReview,
                    diagnostics: reviewDiagnostics()
                }
            })
        ),
        false
    );
    // A fabricated reason without any diagnostics is fabricated twice over.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                review: {
                    ...evidenceBackedReview,
                    diagnostics: undefined
                }
            })
        ),
        false
    );
});

test('a candidate contradicting a prompt fact or a failed Review is never eligible', () => {
    const value = proposalSet();
    const proposal = value.proposals[0];
    const falseFacts = {
        positivePointsSatisfied: false,
        negativePointsSatisfied: true,
        positiveBoxesSatisfied: true
    };
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                promptConsistency: falseFacts,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    promptConsistency: falseFacts,
                    eligible: true
                }
            })
        ),
        false
    );
    // The same candidate declared ineligible is a valid diagnostic record.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                promptConsistency: falseFacts,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    promptConsistency: falseFacts,
                    eligible: false
                }
            })
        ),
        true
    );
    const failedReview = {
        status: 'failed',
        reasons: [],
        actionableReasons: [],
        policyVersion: aiSelectViewAssessmentPolicyVersion
    };
    // A failed Mask Review is never eligible.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    eligible: true
                },
                review: failedReview
            })
        ),
        false
    );
    // A failed, ineligible candidate stays in the set for diagnostics.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    eligible: false
                },
                review: failedReview
            })
        ),
        true
    );
});

test('proposal-set diagnostics are digest-bound and closed to unknown keys', () => {
    const base = proposalSet();
    const payload = { ...base, diagnostics: { refinementFallback: true } };
    delete payload.digest;
    const value = { ...payload, digest: autoMaskProposalSetDigest(payload) };
    assert.equal(isAutoMaskProposalSet(value), true);
    // Flipping the flag without re-binding the set digest fails closed.
    assert.equal(
        isAutoMaskProposalSet({
            ...value,
            diagnostics: { refinementFallback: false }
        }),
        false
    );
    // Unknown diagnostics keys fail closed even with a recomputed digest.
    const unknownPayload = {
        ...payload,
        diagnostics: { refinementFallback: true, confidence: 0.9 }
    };
    assert.equal(
        isAutoMaskProposalSet({
            ...unknownPayload,
            digest: autoMaskProposalSetDigest(unknownPayload)
        }),
        false
    );
});

test('per-candidate logits references are opaque and digest-bound', () => {
    const value = proposalSet();
    assert.equal(isAutoMaskProposalSet(value), true);
    // The ref is optional per candidate (undefined keys are not bound).
    const withoutRef = withProposal(value, {
        ...value.proposals[0],
        logitsRef: undefined
    });
    assert.equal(isAutoMaskProposalSet(withoutRef), true);
    // A tampered ref (raw bytes smuggled in, or a stale digest) fails closed.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...value.proposals[0],
                logitsRef: { ...logitsRef(), stateId: 'other-state' }
            })
        ),
        false
    );
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...value.proposals[0],
                logitsRef: { ...logitsRef(), logitsBase64: 'AAAA' }
            })
        ),
        false
    );
});

test('the single-result policy bounds every prompt shape and refinement', () => {
    const singlePoint = revisePromptState(
        createEmptyPromptState('anchor-view', digest('a')),
        {
            points: [{ promptId: 'p-1', polarity: 'include', xPx: 1, yPx: 1 }]
        }
    );
    // Point, Box, mixed, and refinement programs all expose one result.
    assert.equal(maximumAutoMaskProposalCount(singlePoint, false), 1);
    assert.equal(maximumAutoMaskProposalCount(singlePoint, true), 1);
    // A negative Point or multiple Points force single-mask mode.
    const mixed = revisePromptState(singlePoint, {
        points: [
            ...singlePoint.points,
            { promptId: 'p-2', polarity: 'exclude', xPx: 2, yPx: 2 }
        ]
    });
    assert.equal(maximumAutoMaskProposalCount(mixed, false), 1);
    const singleNegative = revisePromptState(
        createEmptyPromptState('anchor-view', digest('a')),
        {
            points: [{ promptId: 'p-1', polarity: 'exclude', xPx: 1, yPx: 1 }]
        }
    );
    assert.equal(maximumAutoMaskProposalCount(singleNegative, false), 1);
    // A Box forces single-mask mode.
    const withBox = revisePromptState(singlePoint, {
        boxes: [
            {
                promptId: 'box-1',
                polarity: 'include',
                x0Px: 0,
                y0Px: 0,
                x1Px: 3,
                y1Px: 3
            }
        ]
    });
    assert.equal(maximumAutoMaskProposalCount(withBox, false), 1);
});

test('defaultPreviewProposalOrder is score-descending with source-index ties', () => {
    const first = withScore(proposalFor(0), 0.5);
    const unscored = proposalFor(1);
    const tied = withScore(proposalFor(2), 0.5);
    assert.deepEqual(
        defaultPreviewProposalOrder([unscored, tied, first]).map(
            (proposal) => proposal.proposalId
        ),
        // Equal scores break by ascending sourceIndex; absent scores sort last.
        ['proposal-0', 'proposal-2', 'proposal-1']
    );
});

test('the v2 decision carries no ranking reason codes and binds the exact set', () => {
    const proposals = proposalSet();
    const decision = decisionFor(proposals);
    assert.equal(isProposalDecision(decision, proposals), true);
    // Structured ranking reasons are deleted from the v2 decision.
    assert.equal(
        isProposalDecision({ ...decision, reasons: [] }, proposals),
        false
    );
    assert.equal(
        isProposalDecision({ ...decision, schemaVersion: 1 }, proposals),
        false
    );
    assert.equal(
        isProposalDecision(
            { ...decision, rankingPolicyVersion: 'anchor-mask-ranking/v2' },
            proposals
        ),
        false
    );
    assert.equal(
        isProposalDecision(
            { ...decision, proposalSetDigest: digest('f') },
            proposals
        ),
        false
    );
});

test('the default preview is the highest raw model score, never set order', () => {
    const low = withScore(proposalFor(0), 0.5);
    const high = withScore(proposalFor(1), 0.9);
    const proposals = withProposals(proposalSet(), [low, high]);
    const decision = decisionFor(proposals, {
        status: 'ambiguous',
        selectedProposalId: 'proposal-1',
        alternativeProposalIds: ['proposal-1', 'proposal-0']
    });
    assert.equal(isProposalDecision(decision, proposals), true);
    // Set order is not the preview order.
    assert.equal(
        isProposalDecision(
            {
                ...decision,
                selectedProposalId: 'proposal-0',
                alternativeProposalIds: ['proposal-0', 'proposal-1']
            },
            proposals
        ),
        false
    );
    // The default preview is never auto-confirmed into a single selection.
    assert.equal(
        isProposalDecision({ ...decision, status: 'selected' }, proposals),
        false
    );
});

test('a ProposalDecision cannot advertise a prompt-ineligible proposal', () => {
    const falseFacts = {
        positivePointsSatisfied: false,
        negativePointsSatisfied: true,
        positiveBoxesSatisfied: true
    };
    const eligible = withScore(proposalFor(0), 0.9);
    const ineligible = proposalFor(1, {
        promptConsistency: falseFacts,
        rankingFeatures: {
            promptConsistency: falseFacts,
            eligible: false,
            areaFraction: 1,
            connectedComponentCount: 1
        }
    });
    const proposals = withProposals(proposalSet(), [eligible, ineligible]);
    // Only the eligible candidate may be advertised.
    const decision = decisionFor(proposals, {
        status: 'selected',
        selectedProposalId: 'proposal-0',
        alternativeProposalIds: ['proposal-0']
    });
    assert.equal(isProposalDecision(decision, proposals), true);
    assert.equal(
        isProposalDecision(
            {
                ...decision,
                status: 'ambiguous',
                alternativeProposalIds: ['proposal-0', 'proposal-1']
            },
            proposals
        ),
        false
    );
    assert.equal(
        isProposalDecision(
            {
                ...decision,
                selectedProposalId: 'proposal-1',
                alternativeProposalIds: ['proposal-1']
            },
            proposals
        ),
        false
    );
});

test('decision status is coupled to the eligible alternatives', () => {
    // Unavailable: no eligible candidate, no selection.
    const empty = withProposals(proposalSet(), []);
    const unavailable = decisionFor(empty, {
        status: 'unavailable',
        selectedProposalId: undefined,
        alternativeProposalIds: []
    });
    assert.equal(isProposalDecision(unavailable, empty), true);
    assert.equal(
        isProposalDecision(
            { ...unavailable, selectedProposalId: 'proposal-0' },
            empty
        ),
        false
    );
    // Selected: exactly one eligible candidate and it is the preview.
    const single = proposalSet();
    assert.equal(isProposalDecision(decisionFor(single), single), true);
    assert.equal(
        isProposalDecision(
            decisionFor(single, {
                status: 'unavailable',
                selectedProposalId: undefined,
                alternativeProposalIds: []
            }),
            single
        ),
        false
    );
    // Ambiguous: two or more eligible candidates, previewing the top score.
    const pair = withProposals(proposalSet(), [
        withScore(proposalFor(0), 0.9),
        withScore(proposalFor(1), 0.5)
    ]);
    assert.equal(
        isProposalDecision(
            decisionFor(pair, {
                status: 'ambiguous',
                selectedProposalId: 'proposal-0',
                alternativeProposalIds: ['proposal-0', 'proposal-1']
            }),
            pair
        ),
        true
    );
    assert.equal(
        isProposalDecision(
            decisionFor(pair, {
                status: 'unavailable',
                selectedProposalId: undefined,
                alternativeProposalIds: []
            }),
            pair
        ),
        false
    );
});

test('proposal sets reject duplicate source identity and invalid truncation', () => {
    const value = proposalSet();
    const duplicate = {
        ...value,
        proposals: [
            value.proposals[0],
            { ...value.proposals[0], proposalId: 'proposal-1' }
        ]
    };
    assert.equal(isAutoMaskProposalSet(duplicate), false);
    assert.equal(
        isAutoMaskProposalSet({
            ...value,
            truncation: {
                originalCount: 1,
                retainedCount: 1,
                policy: 'bounded'
            }
        }),
        false
    );
});

test('proposal sets reject shrunk or contradictory prompt consistency facts', () => {
    const value = proposalSet();
    const proposal = value.proposals[0];
    // Removed v2 fact families fail closed.
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                promptConsistency: {
                    ...proposal.promptConsistency,
                    maskConstraintsSatisfied: true
                }
            })
        ),
        false
    );
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                promptConsistency: {
                    positivePointsSatisfied: true,
                    negativePointsSatisfied: true
                }
            })
        ),
        false
    );
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    promptConsistency: {
                        positivePointsSatisfied: false,
                        negativePointsSatisfied: true,
                        positiveBoxesSatisfied: true
                    }
                }
            })
        ),
        false
    );
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    modelScore: 1.5
                }
            })
        ),
        false
    );
});

test('deterministic truncation records preserve one source-ordered proposal', () => {
    const base = proposalSet();
    const proposals = [proposalFor(0)];
    const payload = {
        ...base,
        proposals,
        truncation: {
            originalCount: 5,
            retainedCount: 1,
            policy: 'source-order-first-1'
        }
    };
    delete payload.digest;
    const bounded = {
        ...payload,
        digest: autoMaskProposalSetDigest(payload)
    };
    assert.equal(isAutoMaskProposalSet(bounded), true);
    const tooManyPayload = {
        ...payload,
        proposals: [...proposals, proposalFor(1)],
        truncation: {
            originalCount: 5,
            retainedCount: 2,
            policy: 'source-order-first-2'
        }
    };
    assert.equal(
        isAutoMaskProposalSet({
            ...tooManyPayload,
            digest: autoMaskProposalSetDigest(tooManyPayload)
        }),
        false
    );
});
