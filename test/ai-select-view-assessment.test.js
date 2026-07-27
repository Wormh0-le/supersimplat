const assert = require('node:assert/strict');
const test = require('node:test');

const {
    reviewReasonActionKeys
} = require('../.test-dist/src/ai-select/view-assessment.js');

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
