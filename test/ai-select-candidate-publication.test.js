const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const test = require('node:test');

const {
    CandidatePublicationStore,
    createCandidatePublicationBinding,
    createProductionCandidateArtifact,
    createProductionCandidatePublicationBinding,
    createReferenceCandidateArtifact,
    isProductionCandidateArtifact,
    isReferenceCandidateArtifact
} = require('../.test-dist/src/ai-select/candidate-publication.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;
const contractVector = JSON.parse(
    readFileSync(
        'test/fixtures/ai-select-reference-candidate-contract-vector.json',
        'utf8'
    )
);

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const binding = (overrides = {}) =>
    createCandidatePublicationBinding({
        requestBinding: {
            targetContextId: 'ai-target-context-1',
            contextRevision: 3,
            dependencyToken: dependency()
        },
        targetSplatId: 'editor-splat:1',
        stableInputs: [
            {
                viewId: 'view-1',
                participation: 'included',
                stableMaskDigest: digest('a'),
                evidenceArtifactDigest: digest('b')
            },
            {
                viewId: 'view-2',
                participation: 'excluded',
                stableMaskDigest: digest('c'),
                evidenceArtifactDigest: null
            }
        ],
        aggregationPolicyDigest: digest('d'),
        sourceEvidencePolicyDigest: digest('e'),
        evidenceWorkingSetToken: digest('f'),
        evidenceArtifactSetDigest: digest('1'),
        referenceBackendIdentity: {
            rasterImplementationId: 'gsplat-reference-rgb/v1',
            evidenceBackendKind: 'reference-contributor',
            evidenceBackendId: 'complete-contributor/reference-v1',
            runtimeBuildId: 'locked-runtime-build-1'
        },
        ...overrides
    });

const bindingWithMasklessExcludedView = () =>
    binding({
        stableInputs: [
            {
                viewId: 'view-1',
                participation: 'included',
                stableMaskDigest: digest('a'),
                evidenceArtifactDigest: digest('b')
            },
            {
                viewId: 'view-2',
                participation: 'excluded',
                stableMaskDigest: null,
                evidenceArtifactDigest: null
            }
        ]
    });

const artifact = (publicationBinding = binding(), overrides = {}) =>
    createReferenceCandidateArtifact({
        publicationBinding,
        sourceAggregationResultDigest: digest('2'),
        selectedStableGaussianIds: [5, 9],
        uncertainStableGaussianIds: [11],
        ...overrides
    });

const productionBinding = () =>
    createProductionCandidatePublicationBinding({
        requestBinding: {
            targetContextId: 'ai-target-context-1',
            contextRevision: 3,
            dependencyToken: dependency()
        },
        targetSplatId: 'editor-splat:1',
        stableInputs: [
            {
                viewId: 'view-1',
                participation: 'included',
                stableMaskDigest: digest('a'),
                evidenceArtifactDigest: digest('b')
            }
        ],
        aggregationPolicyDigest: digest('d'),
        sourceEvidencePolicyDigest: digest('e'),
        evidenceWorkingSetToken: digest('f'),
        evidenceArtifactSetDigest: digest('1'),
        productionIdentityDigest: digest('3'),
        evidenceBackendIdentity: {
            rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'global-atomic/direct-v1',
            runtimeBuildId: 'locked-runtime-build-1'
        }
    });

test('browser validation matches the Companion reference Candidate golden vector', () => {
    const publicationBinding = createCandidatePublicationBinding(
        contractVector.bindingInput
    );

    assert.deepEqual(
        publicationBinding,
        contractVector.artifact.publicationBinding
    );
    assert.ok(isReferenceCandidateArtifact(contractVector.artifact));
});

test('a complete reference Candidate publishes Selected-only with separate Uncertain overlay', () => {
    const dirty = new AISelectDirtyStateTracker();
    dirty.markStableMaskPublished('view-1');
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = binding();
    const candidate = artifact(currentBinding);

    store.publish(candidate, currentBinding);

    const state = store.state(currentBinding);
    assert.equal(state.status, 'current');
    assert.deepEqual(state.candidate.selectedStableGaussianIds, [5, 9]);
    assert.deepEqual(state.uncertain.stableGaussianIds, [11]);
    assert.deepEqual(state.overlay, {
        selectedStableGaussianIds: [5, 9],
        uncertainStableGaussianIds: [11]
    });
    assert.equal(state.applicationStatus, 'blocked-reference-pre-production');
    assert.equal(candidate.productionReadiness, 'reference-only');
    assert.equal(dirty.state.liftDirty, false);
    assert.equal(dirty.state.candidateStale, false);
    assert.ok(isReferenceCandidateArtifact(candidate));
    assert.deepEqual(Object.keys(candidate.candidate), [
        'selectedStableGaussianIds'
    ]);
});

test('a complete production Candidate is current and eligible for native application', () => {
    const dirty = new AISelectDirtyStateTracker();
    dirty.markStableMaskPublished('view-1');
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = productionBinding();
    const candidate = createProductionCandidateArtifact({
        publicationBinding: currentBinding,
        sourceAggregationResultDigest: digest('2'),
        selectedStableGaussianIds: [5, 9],
        uncertainStableGaussianIds: [11]
    });

    store.publish(candidate, currentBinding);

    assert.ok(isProductionCandidateArtifact(candidate));
    assert.equal(store.presentationState.status, 'current');
    assert.equal(store.presentationState.applicationStatus, 'ready');
    assert.equal(
        store.inspectableCandidate.productionReadiness,
        'production-ready'
    );
});

test('the product presentation seam reports current and stale Candidate counts', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = binding();
    const states = [];
    const unsubscribe = store.subscribe((state) => {
        states.push({
            status: state.status,
            selected: state.candidate?.selectedStableGaussianIds.length ?? 0,
            uncertain: state.uncertain?.stableGaussianIds.length ?? 0
        });
    });

    store.publish(artifact(currentBinding), currentBinding);
    dirty.markParticipationChanged('view-2');
    unsubscribe();

    assert.deepEqual(states, [
        { status: 'empty', selected: 0, uncertain: 0 },
        { status: 'current', selected: 2, uncertain: 1 },
        { status: 'stale', selected: 2, uncertain: 1 }
    ]);
});

test('a maskless Excluded View is identity-bound but does not block publication', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = bindingWithMasklessExcludedView();

    store.publish(artifact(currentBinding), currentBinding);

    assert.equal(store.state(currentBinding).status, 'current');
});

test('Stable Mask or Participation identity changes keep the old Candidate inspectable but stale', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const publishedBinding = binding();
    store.publish(artifact(publishedBinding), publishedBinding);

    dirty.markStableMaskPublished('view-1');
    const changedMaskBinding = binding({
        stableInputs: [
            {
                viewId: 'view-1',
                participation: 'included',
                stableMaskDigest: digest('9'),
                evidenceArtifactDigest: digest('8')
            },
            {
                viewId: 'view-2',
                participation: 'excluded',
                stableMaskDigest: digest('c'),
                evidenceArtifactDigest: null
            }
        ]
    });
    const staleMaskState = store.state(changedMaskBinding);
    assert.equal(staleMaskState.status, 'stale');
    assert.equal(staleMaskState.applicationStatus, 'blocked-stale');
    assert.deepEqual(staleMaskState.overlay.selectedStableGaussianIds, [5, 9]);

    const changedParticipationBinding = binding({
        stableInputs: [
            {
                viewId: 'view-1',
                participation: 'included',
                stableMaskDigest: digest('a'),
                evidenceArtifactDigest: digest('b')
            },
            {
                viewId: 'view-2',
                participation: 'included',
                stableMaskDigest: digest('c'),
                evidenceArtifactDigest: digest('7')
            }
        ]
    });
    assert.equal(store.state(changedParticipationBinding).status, 'stale');

    const changedRuntimeBinding = binding({
        referenceBackendIdentity: {
            rasterImplementationId: 'gsplat-reference-rgb/v1',
            evidenceBackendKind: 'reference-contributor',
            evidenceBackendId: 'complete-contributor/reference-v1',
            runtimeBuildId: 'locked-runtime-build-2'
        }
    });
    assert.equal(store.state(changedRuntimeBinding).status, 'stale');
});

test('a failed or stale replacement never destroys the previous inspectable Candidate', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = binding();
    const previous = artifact(currentBinding);
    store.publish(previous, currentBinding);
    dirty.markParticipationChanged('view-2');

    const malformed = {
        ...artifact(currentBinding),
        candidate: { selectedStableGaussianIds: [5, 11] }
    };
    assert.throws(
        () => store.publish(malformed, currentBinding),
        /Candidate artifact is invalid/
    );
    assert.equal(
        store.inspectableCandidate.candidateDigest,
        previous.candidateDigest
    );
    assert.equal(dirty.state.candidateStale, true);

    const oldDependencyBinding = binding({
        requestBinding: {
            targetContextId: 'ai-target-context-1',
            contextRevision: 3,
            dependencyToken: dependency({ geometryToken: 'geometry-old' })
        }
    });
    assert.throws(
        () => store.publish(artifact(oldDependencyBinding), currentBinding),
        /does not match current inputs/
    );
    assert.equal(
        store.inspectableCandidate.candidateDigest,
        previous.candidateDigest
    );
});

test('a failing observer cannot split an atomic Candidate and dirty-state commit', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = binding();
    const previous = artifact(currentBinding);
    store.publish(previous, currentBinding);
    dirty.markParticipationChanged('view-2');
    const replacement = artifact(currentBinding, {
        selectedStableGaussianIds: [5],
        uncertainStableGaussianIds: [9, 11]
    });
    const presentationStates = [];
    const unsubscribePresentation = store.subscribe((state) => {
        presentationStates.push({
            status: state.status,
            selected: state.candidate?.selectedStableGaussianIds ?? []
        });
    });
    const observedDirtyStates = [];
    let failNotification = false;
    const unsubscribe = dirty.subscribe(() => {
        if (failNotification) {
            throw new Error('publication observer failed');
        }
    });
    const unsubscribeObserver = dirty.subscribe((state) => {
        observedDirtyStates.push({
            liftDirty: state.liftDirty,
            candidateStale: state.candidateStale
        });
    });
    failNotification = true;

    const originalConsoleError = console.error;
    const reportedErrors = [];
    console.error = (error) => reportedErrors.push(error);
    try {
        store.publish(replacement, currentBinding);
    } finally {
        console.error = originalConsoleError;
    }
    unsubscribe();
    unsubscribeObserver();
    unsubscribePresentation();

    assert.equal(
        store.inspectableCandidate.candidateDigest,
        replacement.candidateDigest
    );
    assert.equal(dirty.state.liftDirty, false);
    assert.equal(dirty.state.candidateStale, false);
    assert.deepEqual(presentationStates.at(-1), {
        status: 'current',
        selected: [5]
    });
    assert.deepEqual(observedDirtyStates.at(-1), {
        liftDirty: false,
        candidateStale: false
    });
    assert.equal(reportedErrors.length, 1);
    assert.match(reportedErrors[0].message, /publication observer failed/);
});

test('reset disposes target-local Candidate state', () => {
    const dirty = new AISelectDirtyStateTracker();
    const store = new CandidatePublicationStore(dirty);
    const currentBinding = binding();
    store.publish(artifact(currentBinding), currentBinding);

    store.reset();

    assert.equal(store.state(currentBinding).status, 'empty');
    assert.equal(store.inspectableCandidate, null);
});
