const assert = require('node:assert/strict');
const test = require('node:test');

const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest,
    isAutoMaskProposalSet,
    isProposalDecision
} = require('../.test-dist/src/ai-select/mask-proposal.js');

const digest = (character) => `sha256:${character.repeat(64)}`;
const mask = {
    encoding: 'bitset-lsb-v1',
    width: 1,
    height: 1,
    data: 'AQ==',
    digest: 'sha256:4bf5122f344554c53bde2ebb8cd2b7e3d1600ad631c385a5d7cce23c7785459a'
};

const rankingFeatures = {
    promptConsistency: {
        positivePointsSatisfied: true,
        negativePointsSatisfied: true
    },
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

const proposalSet = () => {
    const value = {
        schemaVersion: 1,
        viewId: 'anchor-view',
        rgbDigest: digest('a'),
        promptStateDigest: digest('b'),
        modelManifestDigest: digest('c'),
        adapterCapabilityDigest: digest('d'),
        proposalPolicyVersion: 'auto-mask-proposals/bounded-source-order-v1',
        proposalAttemptId: 'proposal-attempt-1',
        proposals: [
            {
                proposalId: 'proposal-0',
                mask,
                sourceIndex: 0,
                modelScore: 2.5,
                modelScoreSemantics: 'adapter-local logit',
                promptConsistency: {
                    positivePointsSatisfied: true,
                    negativePointsSatisfied: true
                },
                rankingFeatures
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

test('a bounded proposal set preserves score semantics and exact identity', () => {
    const value = proposalSet();
    assert.equal(isAutoMaskProposalSet(value), true);
    assert.equal(value.proposals[0].modelScoreSemantics, 'adapter-local logit');
    assert.equal(
        isAutoMaskProposalSet({ ...value, proposalAttemptId: 'stale-attempt' }),
        false
    );
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

test('proposal sets reject ranking features that contradict their mask or proposal facts', () => {
    const value = proposalSet();
    const proposal = value.proposals[0];
    assert.equal(
        isAutoMaskProposalSet(
            withProposal(value, {
                ...proposal,
                rankingFeatures: {
                    ...proposal.rankingFeatures,
                    promptConsistency: {
                        positivePointsSatisfied: false,
                        negativePointsSatisfied: true
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

test('deterministic truncation records preserve at most four source-ordered proposals', () => {
    const base = proposalSet();
    const proposals = Array.from({ length: 4 }, (_, sourceIndex) => ({
        ...base.proposals[0],
        proposalId: `proposal-${sourceIndex}`,
        sourceIndex,
        rankingFeatures: {
            ...rankingFeatures,
            pairwiseRelations: Array.from(
                { length: 4 },
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
            originalCount: 6,
            retainedCount: 4,
            policy: 'source-order-first-4'
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
                proposalId: 'proposal-4',
                sourceIndex: 4
            }
        ],
        truncation: {
            originalCount: 6,
            retainedCount: 5,
            policy: 'source-order-first-5'
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
