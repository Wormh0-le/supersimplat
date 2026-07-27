const assert = require('node:assert/strict');
const test = require('node:test');

const {
    localViewSupportDiagnosticId,
    reviewReasonActionKeys
} = require('../.test-dist/src/ai-select/view-assessment.js');

test('support diagnostic identity binds its inputs and result', () => {
    assert.equal(
        localViewSupportDiagnosticId({
            sceneId: 'splat-1',
            sceneVersion: 'scene-v1',
            viewId: 'generated-00',
            rgbDigest: `sha256:${'a'.repeat(64)}`,
            stableMaskDigest: `sha256:${'b'.repeat(64)}`,
            observedGaussianCount: 3
        }),
        'sha256:0d59600b3bee614e7721059c893536652a13e7c25e3f834e166dcec4c54d0eee'
    );
});

test('structured Review Reasons map to deterministic localized static actions', () => {
    assert.deepEqual(reviewReasonActionKeys('target-at-boundary'), [
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.add-view'
    ]);
    assert.deepEqual(reviewReasonActionKeys('fragmented-mask'), [
        'ai-select.review.action.brush'
    ]);
    assert.deepEqual(reviewReasonActionKeys('weak-gaussian-support'), [
        'ai-select.review.action.inspect-view',
        'ai-select.review.action.add-view'
    ]);
    assert.deepEqual(reviewReasonActionKeys('propagation-uncertain'), [
        'ai-select.review.action.inspect-mask'
    ]);
});
