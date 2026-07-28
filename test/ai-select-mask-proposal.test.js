const assert = require('node:assert/strict');
const test = require('node:test');

const {
    autoMaskProposalSetDigest,
    isAutoMaskProposalSet
} = require('../.test-dist/src/ai-select/mask-proposal.js');

const digest = (character) => `sha256:${character.repeat(64)}`;
const mask = {
    encoding: 'bitset-lsb-v1',
    width: 1,
    height: 1,
    data: 'AQ==',
    digest: 'sha256:4bf5122f344554c53bde2ebb8cd2b7e3d1600ad631c385a5d7cce23c7785459a'
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
                }
            }
        ]
    };
    return { ...value, digest: autoMaskProposalSetDigest(value) };
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

test('deterministic truncation records preserve at most four source-ordered proposals', () => {
    const base = proposalSet();
    const proposals = Array.from({ length: 4 }, (_, sourceIndex) => ({
        ...base.proposals[0],
        proposalId: `proposal-${sourceIndex}`,
        sourceIndex
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
