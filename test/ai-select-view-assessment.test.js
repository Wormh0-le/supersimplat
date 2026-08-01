const assert = require('node:assert/strict');
const test = require('node:test');

const {
    aiSelectViewAssessmentPolicyVersion,
    defaultViewParticipation,
    isViewAssessmentResult,
    reviewReasonActionKeys
} = require('../.test-dist/src/ai-select/view-assessment.js');

const rgbDigest = `sha256:${'a'.repeat(64)}`;
const stableMaskDigest = `sha256:${'b'.repeat(64)}`;

const diagnostics = (overrides = {}) => ({
    framePixels: 3072,
    foregroundPixels: 24,
    boundaryPixels: 0,
    boundaryContactRatio: 0,
    connectedComponents: 1,
    largestComponentRatio: 1,
    promptPointCount: 2,
    promptViolationCount: 0,
    boxSpillPixels: null,
    boxSpillRatio: null,
    ...overrides
});

const assessment = (overrides = {}) => ({
    status: 'good',
    reasons: [],
    actionableReasons: [],
    policyVersion: aiSelectViewAssessmentPolicyVersion,
    inputIdentity: {
        rgbDigest,
        stableMaskDigest,
        assessmentPolicyVersion: aiSelectViewAssessmentPolicyVersion
    },
    diagnostics: diagnostics(),
    ...overrides
});

test('structured Review Reasons map to deterministic localized static actions', () => {
    assert.deepEqual(reviewReasonActionKeys('prompt-inconsistent'), [
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]);
    assert.deepEqual(reviewReasonActionKeys('target-materially-clipped'), [
        'ai-select.review.action.inspect-view',
        'ai-select.review.action.add-view'
    ]);
    assert.deepEqual(reviewReasonActionKeys('severely-fragmented'), [
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]);
    assert.deepEqual(reviewReasonActionKeys('box-spill-or-neighbour-leak'), [
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]);
    assert.deepEqual(reviewReasonActionKeys('empty-or-degenerate-mask'), [
        'ai-select.review.action.inspect-mask'
    ]);
});

test('the v2 schema accepts the current Good / Review / Failed shapes', () => {
    assert.ok(isViewAssessmentResult(assessment()));
    assert.ok(
        isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'target-materially-clipped',
                reasons: ['target-materially-clipped'],
                actionableReasons: ['target-materially-clipped'],
                diagnostics: diagnostics({
                    boundaryPixels: 15,
                    boundaryContactRatio: 15 / 64
                })
            })
        )
    );
    // A degenerate Mask fails with one structured reason and its geometry.
    assert.ok(
        isViewAssessmentResult(
            assessment({
                status: 'failed',
                primaryReason: 'empty-or-degenerate-mask',
                reasons: ['empty-or-degenerate-mask'],
                actionableReasons: [],
                diagnostics: diagnostics({
                    foregroundPixels: 0,
                    promptPointCount: null,
                    promptViolationCount: null
                })
            })
        )
    );
    // An assessment-internal failure invents no reason and no geometry.
    assert.ok(
        isViewAssessmentResult(
            assessment({
                status: 'failed',
                reasons: [],
                actionableReasons: [],
                diagnostics: undefined
            })
        )
    );
});

test('the retired v1 reasons and identity fields fail closed', () => {
    for (const reason of [
        'target-at-boundary',
        'fragmented-mask',
        'weak-gaussian-support',
        'propagation-uncertain'
    ]) {
        assert.ok(
            !isViewAssessmentResult(
                assessment({
                    status: 'review',
                    primaryReason: reason,
                    reasons: [reason],
                    actionableReasons: [reason]
                })
            ),
            reason
        );
    }
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                policyVersion: 'local-view-assessment/v1',
                inputIdentity: {
                    rgbDigest,
                    stableMaskDigest,
                    assessmentPolicyVersion: 'local-view-assessment/v1',
                    supportPolicyVersion: 'local-view-support-probe/v1',
                    supportDiagnosticId: null,
                    propagationPolicyVersion: 'generated-view-mask/v1'
                }
            })
        )
    );
});

test('every Review reason must be backed by its measured diagnostic', () => {
    // prompt-inconsistent without a Prompt violation is fabricated.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'prompt-inconsistent',
                reasons: ['prompt-inconsistent'],
                actionableReasons: ['prompt-inconsistent']
            })
        )
    );
    // A missing Prompt family can never carry the Prompt reason.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'prompt-inconsistent',
                reasons: ['prompt-inconsistent'],
                actionableReasons: ['prompt-inconsistent'],
                diagnostics: diagnostics({
                    promptPointCount: null,
                    promptViolationCount: null
                })
            })
        )
    );
    // Box spill without a Box family is fabricated.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'box-spill-or-neighbour-leak',
                reasons: ['box-spill-or-neighbour-leak'],
                actionableReasons: ['box-spill-or-neighbour-leak']
            })
        )
    );
    // The failure reason never appears inside a Review assessment.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'empty-or-degenerate-mask',
                reasons: ['empty-or-degenerate-mask'],
                actionableReasons: []
            })
        )
    );
});

test('the trust boundary enforces the version-owned geometry thresholds', () => {
    // A clipping claim needs the margin: four contact pixels is one-pixel
    // contact noise, not material clipping.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'target-materially-clipped',
                reasons: ['target-materially-clipped'],
                actionableReasons: ['target-materially-clipped'],
                diagnostics: diagnostics({
                    boundaryPixels: 4,
                    boundaryContactRatio: 0.25
                })
            })
        )
    );
    // A fragmentation claim needs material disconnected mass, not speckles.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'severely-fragmented',
                reasons: ['severely-fragmented'],
                actionableReasons: ['severely-fragmented'],
                diagnostics: diagnostics({
                    foregroundPixels: 60,
                    connectedComponents: 6,
                    largestComponentRatio: 50 / 60
                })
            })
        )
    );
    // A Box spill claim needs gross spill beyond the margin.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'review',
                primaryReason: 'box-spill-or-neighbour-leak',
                reasons: ['box-spill-or-neighbour-leak'],
                actionableReasons: ['box-spill-or-neighbour-leak'],
                diagnostics: diagnostics({
                    boxSpillPixels: 10,
                    boxSpillRatio: 0.3
                })
            })
        )
    );
    // A full-frame Mask is a valid Failed artifact with the same reason.
    assert.ok(
        isViewAssessmentResult(
            assessment({
                status: 'failed',
                primaryReason: 'empty-or-degenerate-mask',
                reasons: ['empty-or-degenerate-mask'],
                actionableReasons: [],
                diagnostics: diagnostics({
                    foregroundPixels: 3072,
                    framePixels: 3072
                })
            })
        )
    );
    // A non-degenerate, non-full-frame Mask cannot carry the failure reason.
    assert.ok(
        !isViewAssessmentResult(
            assessment({
                status: 'failed',
                primaryReason: 'empty-or-degenerate-mask',
                reasons: ['empty-or-degenerate-mask'],
                actionableReasons: []
            })
        )
    );
});

test('Participation defaults are centralized and authority-aware', () => {
    // Automatic authority: only Good defaults Included.
    assert.equal(
        defaultViewParticipation({
            reviewStatus: 'good',
            authority: 'automatic'
        }),
        'included'
    );
    assert.equal(
        defaultViewParticipation({
            reviewStatus: 'review',
            authority: 'automatic'
        }),
        'excluded'
    );
    assert.equal(
        defaultViewParticipation({
            reviewStatus: 'failed',
            authority: 'automatic'
        }),
        'excluded'
    );
    assert.equal(
        defaultViewParticipation({
            reviewStatus: null,
            authority: 'automatic'
        }),
        'excluded'
    );
    // User Confirmed authority defaults Included regardless of review state.
    for (const reviewStatus of ['good', 'review', 'failed', null]) {
        assert.equal(
            defaultViewParticipation({
                reviewStatus,
                authority: 'user-confirmed'
            }),
            'included'
        );
    }
});
