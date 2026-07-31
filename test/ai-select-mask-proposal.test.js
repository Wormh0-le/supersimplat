const assert = require('node:assert/strict');
const test = require('node:test');

const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalPolicyVersion,
    autoMaskProposalSetDigest,
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

const rankingFeatures = {
    promptConsistency: promptConsistency(),
    eligible: true,
    areaFraction: 1,
    boundingBox: { x0Px: 0, y0Px: 0, x1Px: 0, y1Px: 0 },
    connectedComponentCount: 1,
    positivePointComponentIds: [0],
    positivePointBoundaryDistances: [1],
    pairwiseRelations: [],
    boundaryContactFraction: 1,
    compactness: Math.PI / 4,
    boxFillRatios: [],
    boxSpillRatios: [],
    promptMaskOverlap: 1,
    optionalSupportSanity: {
        participated: false,
        changedDecision: false
    },
    modelScore: 2.5
};

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
        shape: [1, 256, 256],
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
        schemaVersion: 3,
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

test('policy identities rotate to the SAM 3 Image instance contract', () => {
    assert.equal(
        autoMaskProposalPolicyVersion,
        'auto-mask-proposals/bounded-source-order-v2'
    );
    assert.equal(anchorMaskRankingPolicyVersion, 'anchor-mask-ranking/v2');
});

test('a bounded proposal set preserves score semantics and exact identity', () => {
    const value = proposalSet();
    assert.equal(isAutoMaskProposalSet(value), true);
    assert.equal(value.proposals[0].modelScoreSemantics, 'adapter-local logit');
    assert.equal(
        isAutoMaskProposalSet({ ...value, proposalAttemptId: 'stale-attempt' }),
        false
    );
    // A v2 proposal set identity fails closed on the v3 schema.
    assert.equal(isAutoMaskProposalSet({ ...value, schemaVersion: 2 }), false);
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

test('the multimask policy bounds candidates by prompt shape and refinement', () => {
    const singlePoint = revisePromptState(
        createEmptyPromptState('anchor-view', digest('a')),
        {
            points: [{ promptId: 'p-1', polarity: 'include', xPx: 1, yPx: 1 }]
        }
    );
    // Exactly one include Point, no Box, no refinement: at most 3 candidates.
    assert.equal(maximumAutoMaskProposalCount(singlePoint, false), 3);
    // Any refinement forces single-mask mode.
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

test('a ProposalDecision binds the exact proposal set and structured ambiguity reasons', () => {
    const proposals = proposalSet();
    const decision = {
        schemaVersion: 1,
        viewId: proposals.viewId,
        rgbDigest: proposals.rgbDigest,
        promptStateDigest: proposals.promptStateDigest,
        proposalSetDigest: proposals.digest,
        rankingPolicyVersion: anchorMaskRankingPolicyVersion,
        status: 'ambiguous',
        selectedProposalId: 'proposal-0',
        alternativeProposalIds: ['proposal-0'],
        reasons: [
            {
                code: 'nested-part-vs-whole',
                proposalIds: ['proposal-0']
            }
        ]
    };
    assert.equal(isProposalDecision(decision, proposals), true);
    assert.equal(
        isProposalDecision(
            { ...decision, proposalSetDigest: digest('f') },
            proposals
        ),
        false
    );
    assert.equal(
        isProposalDecision(
            {
                ...decision,
                reasons: [{ code: 'made-up-confidence', proposalIds: [] }]
            },
            proposals
        ),
        false
    );
});

test('a ProposalDecision cannot select or advertise a prompt-ineligible proposal', () => {
    const base = proposalSet();
    const proposals = withProposal(base, {
        ...base.proposals[0],
        rankingFeatures: {
            ...base.proposals[0].rankingFeatures,
            eligible: false
        }
    });
    const decision = {
        schemaVersion: 1,
        viewId: proposals.viewId,
        rgbDigest: proposals.rgbDigest,
        promptStateDigest: proposals.promptStateDigest,
        proposalSetDigest: proposals.digest,
        rankingPolicyVersion: anchorMaskRankingPolicyVersion,
        status: 'selected',
        selectedProposalId: 'proposal-0',
        alternativeProposalIds: ['proposal-0'],
        reasons: []
    };
    assert.equal(isProposalDecision(decision, proposals), false);
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
                    boundingBox: { x0Px: 0, y0Px: 0, x1Px: 1, y1Px: 0 }
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

test('deterministic truncation records preserve at most three source-ordered proposals', () => {
    const base = proposalSet();
    const proposals = Array.from({ length: 3 }, (_, sourceIndex) => ({
        ...base.proposals[0],
        proposalId: `proposal-${sourceIndex}`,
        sourceIndex,
        rankingFeatures: {
            ...rankingFeatures,
            pairwiseRelations: Array.from(
                { length: 3 },
                (_, relatedIndex) => relatedIndex
            )
                .filter((relatedIndex) => relatedIndex !== sourceIndex)
                .map((relatedIndex) => ({
                    proposalId: `proposal-${relatedIndex}`,
                    intersectionOverUnion: 1,
                    areaRatio: 1,
                    containment: 'none',
                    materiallyDistinct: false
                }))
        }
    }));
    const payload = {
        ...base,
        proposals,
        truncation: {
            originalCount: 5,
            retainedCount: 3,
            policy: 'source-order-first-3'
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
        proposals: [
            ...proposals,
            {
                ...base.proposals[0],
                proposalId: 'proposal-3',
                sourceIndex: 3
            }
        ],
        truncation: {
            originalCount: 5,
            retainedCount: 4,
            policy: 'source-order-first-4'
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
