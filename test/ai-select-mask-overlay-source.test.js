const assert = require('node:assert/strict');
const test = require('node:test');

const {
    selectInspectedMaskOverlaySource
} = require('../.test-dist/src/ai-select/mask-overlay-source.js');

test('every inspected View role renders live authoring state when a session exists', () => {
    for (const source of ['auto-generated', 'replacement', 'user-added']) {
        const authoring = { source };
        assert.deepEqual(selectInspectedMaskOverlaySource(source, authoring), {
            kind: 'authoring',
            authoring
        });
    }
});

test('an inspected View without an authoring session falls back to Registry state', () => {
    assert.deepEqual(selectInspectedMaskOverlaySource('auto-generated', null), {
        kind: 'registry'
    });
});
