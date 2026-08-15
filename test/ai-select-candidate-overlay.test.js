const assert = require('node:assert/strict');
const test = require('node:test');

const {
    CandidateOverlayController,
    candidateOverlayMembershipBytes
} = require('../.test-dist/src/ai-select/candidate-overlay.js');

class PresentationSource {
    listeners = new Set();

    constructor(state, revision = null) {
        this.state = state;
        this.revision = revision;
    }

    subscribe(listener) {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    publish(state, revision = this.revision) {
        this.state = state;
        this.revision = revision;
        this.listeners.forEach((listener) => listener(state));
    }
}

const hidden = {
    inspectable: false,
    overlay: { membership: null, treatment: null },
    statusBar: { lifecycle: null }
};

const candidate = (
    lifecycle = 'current',
    treatment = lifecycle === 'stale' ? 'stale' : 'current'
) => ({
    inspectable: true,
    overlay: {
        membership: {
            selectedStableGaussianIds: [1, 4],
            uncertainStableGaussianIds: [2, 4]
        },
        treatment
    },
    statusBar: { lifecycle }
});

test('Candidate publication shows a revision-scoped Selected overlay and keeps Uncertain off', () => {
    const source = new PresentationSource(hidden);
    const overlay = new CandidateOverlayController({
        presentation: source,
        getCandidateRevision: () => source.revision
    });

    source.publish(candidate(), 'candidate-a');
    assert.equal(overlay.state.revision, 'candidate-a');
    assert.equal(overlay.state.selectedVisible, true);
    assert.equal(overlay.state.uncertainVisible, false);

    overlay.toggleSelected();
    assert.equal(overlay.state.selectedVisible, false);
    source.publish(candidate('stale'), 'candidate-a');
    assert.equal(overlay.state.selectedVisible, false);
    assert.equal(overlay.state.treatment, 'stale');

    source.publish(candidate(), 'candidate-b');
    assert.equal(overlay.state.revision, 'candidate-b');
    assert.equal(overlay.state.selectedVisible, true);
});

test('successful native application hides Selected while failure-like state changes preserve it', () => {
    const source = new PresentationSource(candidate(), 'candidate-a');
    const overlay = new CandidateOverlayController({
        presentation: source,
        getCandidateRevision: () => source.revision
    });

    source.publish(candidate('update-failed'), 'candidate-a');
    assert.equal(overlay.state.selectedVisible, true);

    source.publish(candidate('applied-add'), 'candidate-a');
    assert.equal(overlay.state.selectedVisible, false);
    overlay.toggleSelected();
    assert.equal(overlay.state.selectedVisible, true);
});

test('Uncertain preference survives Candidate revisions within a Target and reset releases all state', () => {
    const source = new PresentationSource(candidate(), 'candidate-a');
    const overlay = new CandidateOverlayController({
        presentation: source,
        getCandidateRevision: () => source.revision
    });

    overlay.setUncertainVisible(true);
    source.publish(candidate(), 'candidate-b');
    assert.equal(overlay.state.uncertainVisible, true);

    overlay.reset();
    assert.equal(overlay.state.revision, null);
    assert.equal(overlay.state.membership, null);
    assert.equal(overlay.state.selectedVisible, false);
    assert.equal(overlay.state.uncertainVisible, false);
});

test('dedicated overlay membership bytes never alias native state and Selected wins overlap', () => {
    const nativeState = new Uint8Array([1, 0, 2, 4, 1]);
    const before = nativeState.slice();
    const bytes = candidateOverlayMembershipBytes(
        5,
        Uint32Array.from([1, 4]),
        Uint32Array.from([2, 4])
    );

    assert.deepEqual([...bytes], [0, 1, 2, 0, 1]);
    assert.deepEqual(nativeState, before);
    assert.notEqual(bytes.buffer, nativeState.buffer);
});
