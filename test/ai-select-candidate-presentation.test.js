const assert = require('node:assert/strict');
const test = require('node:test');

const {
    mapCandidatePresentation
} = require('../.test-dist/src/ai-select/candidate-presentation.js');

const emptyCandidate = {
    status: 'empty',
    candidate: null,
    uncertain: null,
    overlay: null,
    applicationStatus: 'unavailable'
};

const candidate = (status = 'current') => ({
    status,
    candidate: { selectedStableGaussianIds: [2, 5, 8] },
    uncertain: { stableGaussianIds: [3, 7] },
    overlay: {
        selectedStableGaussianIds: [2, 5, 8],
        uncertainStableGaussianIds: [3, 7]
    },
    applicationStatus:
        status === 'current'
            ? 'blocked-reference-pre-production'
            : 'blocked-stale'
});

const correction = (overrides = {}) => ({
    mode: 'candidate',
    status: 'idle',
    candidate: emptyCandidate,
    ...overrides
});

const application = (overrides = {}) => ({
    status: 'unavailable',
    blockReason: 'candidate-unavailable',
    applicationRecord: null,
    overlayEmphasis: 'emphasized',
    ...overrides
});

test('shared Candidate mapper hides every Candidate-owned surface before publication', () => {
    const result = mapCandidatePresentation({
        candidate: emptyCandidate,
        correction: correction(),
        application: application()
    });

    assert.equal(result.inspectable, false);
    assert.equal(result.toolbar.visible, false);
    assert.equal(result.statusBar.visible, false);
    assert.equal(result.dock.showCandidateSummary, false);
    assert.equal(result.overlay.membership, null);
});

test('first Candidate update is Status-Bar-only until an inspectable result exists', () => {
    const result = mapCandidatePresentation({
        candidate: emptyCandidate,
        correction: correction({ status: 'updating' }),
        application: application()
    });

    assert.equal(result.inspectable, false);
    assert.equal(result.toolbar.visible, false);
    assert.equal(result.statusBar.visible, true);
    assert.equal(result.statusBar.lifecycle, 'updating');
});

test('current Candidate maps counts, overlay, Dock correction and all native operations once', () => {
    const current = candidate();
    const result = mapCandidatePresentation({
        candidate: current,
        correction: correction({ candidate: current }),
        application: application({
            status: 'ready',
            blockReason: null
        })
    });

    assert.deepEqual(result.counts, { selected: 3, uncertain: 2 });
    assert.deepEqual(result.overlay.membership, current.overlay);
    assert.equal(result.overlay.treatment, 'current');
    assert.equal(result.toolbar.visible, true);
    assert.equal(result.toolbar.operationsEnabled, true);
    assert.equal(result.toolbar.disabledReason, null);
    assert.equal(result.dock.showFixCandidate, true);
    assert.equal(result.dock.showUpdateCandidate, false);
    assert.equal(result.dock.showBackToCandidate, false);
    assert.equal(result.statusBar.lifecycle, 'current');
});

test('stale and failed-update Candidates remain inspectable and share the update recovery', () => {
    const stale = candidate('stale');
    for (const status of ['idle', 'failed']) {
        const result = mapCandidatePresentation({
            candidate: stale,
            correction: correction({
                candidate: stale,
                status,
                ...(status === 'failed' ? { errorMessage: 'lift failed' } : {})
            }),
            application: application({
                status: 'blocked',
                blockReason: 'candidate-stale'
            })
        });

        assert.equal(result.overlay.treatment, 'stale');
        assert.equal(result.toolbar.operationsEnabled, false);
        assert.equal(result.toolbar.disabledReason, 'update-candidate');
        assert.equal(result.dock.showUpdateCandidate, true);
        assert.equal(
            result.statusBar.lifecycle,
            status === 'failed' ? 'update-failed' : 'stale'
        );
    }
});

test('Correction owns its exit/update actions and blocks the Toolbar with one editing reason', () => {
    const current = candidate();
    for (const status of ['idle', 'updating']) {
        const result = mapCandidatePresentation({
            candidate: current,
            correction: correction({
                mode: 'correcting',
                status,
                candidate: current
            }),
            application: application({
                status: 'ready',
                blockReason: null
            })
        });

        assert.equal(result.toolbar.operationsEnabled, false);
        assert.equal(
            result.toolbar.disabledReason,
            status === 'updating'
                ? 'wait-for-update'
                : 'complete-or-exit-correction'
        );
        assert.equal(result.dock.showBackToCandidate, true);
        assert.equal(result.dock.showUpdateCandidate, true);
        assert.equal(
            result.statusBar.lifecycle,
            status === 'updating' ? 'updating' : 'correcting'
        );
    }
});

test('durable native application outcome is projected without moving operations into the Dock', () => {
    const current = candidate();
    const result = mapCandidatePresentation({
        candidate: current,
        correction: correction({ candidate: current }),
        application: application({
            status: 'applied',
            blockReason: null,
            overlayEmphasis: 'deemphasized',
            applicationRecord: { operation: 'intersect' }
        })
    });

    assert.equal(result.statusBar.lifecycle, 'applied-intersect');
    assert.equal(result.toolbar.operationsEnabled, true);
    assert.equal(result.dock.applicationOutcome, 'intersect');
    assert.equal(Object.hasOwn(result.dock, 'operationsEnabled'), false);
});

test('technical application blocks collapse to one restart recovery action', () => {
    const current = candidate();
    for (const blockReason of [
        'context-suspended',
        'target-mismatch',
        'runtime-unverified',
        'policy-incompatible'
    ]) {
        const result = mapCandidatePresentation({
            candidate: current,
            correction: correction({ candidate: current }),
            application: application({
                status: 'blocked',
                blockReason
            })
        });

        assert.equal(result.toolbar.operationsEnabled, false);
        assert.equal(result.toolbar.disabledReason, 'restart-target');
        assert.equal(result.toolbar.technicalBlockReason, blockReason);
    }
});

test('overlay failure preserves the Candidate but disables misleading native operations', () => {
    const current = candidate();
    const result = mapCandidatePresentation({
        candidate: current,
        correction: correction({ candidate: current }),
        application: application({
            status: 'ready',
            blockReason: null
        }),
        overlayAvailable: false
    });

    assert.equal(result.inspectable, true);
    assert.equal(result.overlay.membership, current.overlay);
    assert.equal(result.toolbar.operationsEnabled, false);
    assert.equal(result.toolbar.disabledReason, 'restart-target');
});
