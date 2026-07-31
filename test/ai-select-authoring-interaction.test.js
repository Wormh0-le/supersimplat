const assert = require('node:assert/strict');
const test = require('node:test');

const {
    PointerStrokeBuffer,
    pointerActionForTool
} = require('../.test-dist/src/ai-select/authoring-interaction.js');

test('pointer behavior depends only on the selected Prompt/Edit tool', () => {
    assert.equal(pointerActionForTool('positive-point'), 'point');
    assert.equal(pointerActionForTool('negative-point'), 'point');
    assert.equal(pointerActionForTool('positive-box'), 'box');
    assert.equal(pointerActionForTool('paint'), 'pixel-edit');
    assert.equal(pointerActionForTool('erase'), 'pixel-edit');
    assert.equal(pointerActionForTool('inspect'), 'none');
});

test('Box prompts can never route to direct pixel editing', () => {
    assert.notEqual(pointerActionForTool('positive-box'), 'pixel-edit');
});

test('pointercancel discards a buffered stroke without a commit payload', () => {
    const stroke = new PointerStrokeBuffer();
    stroke.begin({ xPx: 2, yPx: 3 });
    stroke.append({ xPx: 12, yPx: 8 });
    stroke.cancel();

    assert.equal(stroke.commit(), null);
});

test('a pointer gesture commits its deduplicated samples exactly once', () => {
    const stroke = new PointerStrokeBuffer();
    stroke.begin({ xPx: 2, yPx: 3 });
    stroke.append({ xPx: 2, yPx: 3 });
    stroke.append({ xPx: 12, yPx: 8 });

    assert.deepEqual(stroke.commit(), [
        { xPx: 2, yPx: 3 },
        { xPx: 12, yPx: 8 }
    ]);
    assert.equal(stroke.commit(), null);
});
