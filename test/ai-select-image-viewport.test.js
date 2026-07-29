const assert = require('node:assert/strict');
const test = require('node:test');

const {
    fitImageRect,
    mapClientPointToImagePixel
} = require('../.test-dist/src/ai-select/image-viewport.js');

test('a wide viewport contains the authoritative image without stretching', () => {
    const rect = fitImageRect(1076, 231, 1440, 824);
    assert.equal(rect.top, 0);
    assert.equal(rect.height, 231);
    assert.ok(Math.abs(rect.left - 336.1553398058253) < 1e-9);
    assert.ok(Math.abs(rect.width / rect.height - 1440 / 824) < 1e-12);
});

test('a tall viewport letterboxes vertically and preserves aspect ratio', () => {
    assert.deepEqual(fitImageRect(600, 600, 1440, 824), {
        left: 0,
        top: 128.33333333333331,
        width: 600,
        height: 343.33333333333337
    });
});

test('pointer mapping consumes the exact fitted surface rect', () => {
    const rect = {
        left: 100,
        top: 50,
        width: 720,
        height: 412
    };
    assert.deepEqual(mapClientPointToImagePixel(460, 256, rect, 1440, 824), {
        xPx: 720,
        yPx: 412
    });
    assert.equal(mapClientPointToImagePixel(99.9, 256, rect, 1440, 824), null);
    assert.equal(mapClientPointToImagePixel(820, 256, rect, 1440, 824), null);
});

test('invalid or collapsed geometry is non-interactive', () => {
    assert.equal(fitImageRect(0, 100, 1440, 824), null);
    assert.equal(
        mapClientPointToImagePixel(
            0,
            0,
            { left: 0, top: 0, width: 0, height: 10 },
            1440,
            824
        ),
        null
    );
});
