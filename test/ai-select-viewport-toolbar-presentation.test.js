const assert = require('node:assert/strict');
const test = require('node:test');

const {
    mapAISelectViewportToolbar
} = require('../.test-dist/src/ai-select/viewport-toolbar-presentation.js');

const candidate = (
    visible = false,
    operationsEnabled = false,
    disabledReason = null,
    undoAndFixEnabled = false,
    undoAndFixDisabledReason = 'candidate-not-applied'
) => ({
    visible,
    operationsEnabled,
    disabledReason,
    undoAndFixEnabled,
    undoAndFixDisabledReason,
    technicalBlockReason: null
});

const present = (overrides = {}) =>
    mapAISelectViewportToolbar({
        hasContext: true,
        contextActive: true,
        hasConfirmedAnchor: true,
        inspectionTarget: null,
        manipulation: 'move',
        adjustmentStatus: 'current',
        candidate: candidate(),
        ...overrides
    });

const names = (presentation) =>
    presentation.controls.map((entry) => entry.control);

test('normal mode is only combined Anchor adjustment and the Add View split', () => {
    assert.deepEqual(names(present()), [
        'anchor-adjust',
        'add-current-view',
        'add-new-pose'
    ]);
});

test('Anchor adjustment owns the toolbar and exposes pressed move/rotate state', () => {
    const presentation = present({
        inspectionTarget: {
            kind: 'anchor-adjustment-draft',
            cameraBinding: {}
        },
        manipulation: 'rotate',
        adjustmentStatus: 'changed'
    });
    assert.equal(presentation.mode, 'anchor-adjustment');
    assert.deepEqual(names(presentation), [
        'anchor-adjust',
        'move',
        'rotate',
        'reset',
        'cancel'
    ]);
    assert.equal(
        presentation.controls.find((entry) => entry.control === 'rotate')
            .pressed,
        true
    );
});

test('Candidate current and applied states keep stable native operation order', () => {
    for (const operationsEnabled of [true, false]) {
        assert.deepEqual(
            names(
                present({
                    candidate: candidate(
                        true,
                        operationsEnabled,
                        null,
                        operationsEnabled,
                        operationsEnabled ? null : 'native-history-changed'
                    )
                })
            ),
            ['overlay', 'set', 'add', 'remove', 'intersect', 'undo-and-fix']
        );
    }
});

test('Candidate stale, updating and failed states retain their disabled reason', () => {
    for (const reason of ['update-candidate', 'wait-for-update']) {
        const presentation = present({
            candidate: candidate(true, false, reason)
        });
        assert.equal(presentation.mode, 'candidate');
        assert.deepEqual(
            presentation.controls.slice(1, 5).map((entry) => ({
                enabled: entry.enabled,
                reason: entry.disabledReason
            })),
            Array.from({ length: 4 }, () => ({
                enabled: false,
                reason
            }))
        );
    }
});

test('Undo and Fix has its own history-sensitive disabled reason', () => {
    const presentation = present({
        candidate: candidate(true, true, null, false, 'native-history-changed')
    });
    const undoAndFix = presentation.controls.at(-1);

    assert.equal(undoAndFix.control, 'undo-and-fix');
    assert.equal(undoAndFix.enabled, false);
    assert.equal(undoAndFix.disabledReason, 'native-history-changed');
});

test('a hidden Candidate cannot execute over an active inspection target', () => {
    const presentation = present({
        inspectionTarget: { kind: 'user-view-draft', cameraBinding: {} },
        candidate: candidate(true, true, null)
    });
    assert.equal(presentation.mode, 'user-view-adjustment');
    assert.deepEqual(names(presentation), [
        'move',
        'rotate',
        'confirm-view',
        'cancel'
    ]);
});

test('Candidate controls keep their stable position during read-only View inspection', () => {
    const presentation = present({
        inspectionTarget: {
            kind: 'view',
            viewId: 'view-1',
            cameraBinding: {}
        },
        candidate: candidate(true, true, null)
    });
    assert.equal(presentation.mode, 'candidate');
    assert.deepEqual(names(presentation), [
        'overlay',
        'set',
        'add',
        'remove',
        'intersect',
        'undo-and-fix'
    ]);
});
