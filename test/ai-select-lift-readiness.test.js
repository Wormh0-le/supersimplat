const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const {
    LiftReadinessStore,
    isLiftReadinessArtifact,
    liftReadinessBindingFromArtifact
} = require('../.test-dist/src/ai-select/lift-readiness.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');

const contractVector = JSON.parse(
    readFileSync(
        'test/fixtures/ai-select-lift-readiness-contract-vector.json',
        'utf8'
    )
);

test('browser validation accepts the Companion Lift Readiness golden vector', () => {
    assert.ok(isLiftReadinessArtifact(contractVector.artifact));
    assert.deepEqual(
        liftReadinessBindingFromArtifact(contractVector.artifact),
        contractVector.binding
    );
});

test('Stable Mask and Participation changes stale readiness without mutating it', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new LiftReadinessStore(dirty);
    const artifact = contractVector.artifact;
    const binding = liftReadinessBindingFromArtifact(artifact);

    store.publish(artifact, binding);
    assert.equal(store.state(binding).status, 'current');
    assert.equal(store.state(binding).readiness, 'ready');

    dirty.markEditingMaskChanged();
    assert.equal(store.state(binding).status, 'current');

    dirty.markStableMaskPublished('view-1');
    assert.equal(store.state(binding).status, 'stale');
    dirty.markCandidatePublished();
    assert.equal(store.state(binding).status, 'stale');

    dirty.markStableMaskPublished('view-1');
    dirty.markCandidatePublished(() => store.publish(artifact, binding));
    assert.equal(store.state(binding).status, 'current');

    dirty.markParticipationChanged('view-2');
    const stale = store.state(binding);
    assert.equal(stale.status, 'stale');
    assert.equal(stale.readiness, 'ready');
    assert.equal(stale.observationCoverage.coverageRatio, 1);
    assert.equal(stale.viewDiversity.maximumAngularSeparationDegrees, 30);
});

test('generation completion makes an old recommendation binding stale', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new LiftReadinessStore(dirty);
    const artifact = contractVector.artifact;
    const completeBinding = liftReadinessBindingFromArtifact(artifact);
    store.publish(artifact, completeBinding);
    const activeBinding = {
        ...completeBinding,
        generationState: 'active'
    };

    store.synchronizeCurrentBinding(activeBinding);

    assert.equal(store.presentationState.status, 'stale');
    assert.throws(
        () => store.publish(artifact, activeBinding),
        /does not match current inputs/
    );
    assert.equal(store.inspectableArtifact.resultDigest, artifact.resultDigest);
});

test('a malformed replacement preserves the previous readiness artifact', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new LiftReadinessStore(dirty);
    const artifact = contractVector.artifact;
    const binding = liftReadinessBindingFromArtifact(artifact);
    store.publish(artifact, binding);
    const malformed = structuredClone(artifact);
    malformed.observationCoverage.coverageRatio = Number.NaN;

    assert.throws(
        () => store.publish(malformed, binding),
        /Lift Readiness artifact is invalid/
    );
    assert.equal(store.inspectableArtifact.resultDigest, artifact.resultDigest);
});

test('browser validation rejects a semantic contradiction with a well-formed checksum', () => {
    const artifact = structuredClone(contractVector.artifact);
    artifact.readiness = 'limited';
    artifact.reasons = ['weak-gaussian-support'];
    artifact.recommendation = 'generate-more';
    // Reuse a syntactically valid digest to prove semantic validation happens
    // independently from the artifact checksum.
    artifact.resultDigest = `sha256:${'a'.repeat(64)}`;

    assert.equal(isLiftReadinessArtifact(artifact), false);
});

test('browser validation rejects a correctly digested extra request field', () => {
    const artifact = structuredClone(contractVector.artifact);
    artifact.requestBinding.unexpected = true;
    artifact.resultDigest = contractVector.extraRequestFieldResultDigest;

    assert.equal(isLiftReadinessArtifact(artifact), false);

    const dirty = new AISelectDirtyStateTracker();
    const store = new LiftReadinessStore(dirty);
    const current = contractVector.artifact;
    const binding = liftReadinessBindingFromArtifact(current);
    store.publish(current, binding);

    assert.throws(
        () => store.publish(artifact, binding),
        /Lift Readiness artifact is invalid/
    );
    assert.equal(store.inspectableArtifact.resultDigest, current.resultDigest);
});
