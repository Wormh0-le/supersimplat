const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AISelectCandidateCorrectionController
} = require('../.test-dist/src/ai-select/candidate-correction.js');
const {
    CandidatePublicationStore,
    createCandidatePublicationBinding,
    createReferenceCandidateArtifact
} = require('../.test-dist/src/ai-select/candidate-publication.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const dependency = () => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1'
});

const view = (viewId, overrides = {}) => ({
    viewId,
    participation: 'included',
    stableMaskDigest: digest(viewId === 'view-1' ? '1' : '2'),
    evidenceIdentity: {
        viewId,
        cameraBindingDigest: digest('a'),
        rgbDigest: digest(viewId === 'view-1' ? '3' : '4'),
        stableMaskDigest: digest(viewId === 'view-1' ? '1' : '2'),
        evidencePolicyDigest: digest('5'),
        renderWorkingSetToken: digest('b'),
        evidenceWorkingSetToken: digest('9'),
        rasterImplementationId: 'gsplat-reference-rgb/v1',
        evidenceBackendKind: 'reference-contributor',
        evidenceBackendId: 'complete-contributor/reference-v1',
        runtimeBuildId: 'locked-runtime-build-1'
    },
    payload: null,
    ...overrides
});

const result = (views, selected = [5], uncertain = [9]) => {
    const publicationBinding = createCandidatePublicationBinding({
        requestBinding: {
            targetContextId: 'ai-target-context-1',
            contextRevision: 3,
            dependencyToken: dependency()
        },
        targetSplatId: 'editor-splat:1',
        stableInputs: views.map((entry) => ({
            viewId: entry.viewId,
            participation: entry.participation,
            stableMaskDigest: entry.stableMaskDigest,
            evidenceArtifactDigest:
                entry.participation === 'included'
                    ? digest(entry.viewId === 'view-1' ? '6' : '7')
                    : null
        })),
        aggregationPolicyDigest: digest('8'),
        sourceEvidencePolicyDigest: digest('5'),
        evidenceWorkingSetToken: digest('9'),
        evidenceArtifactSetDigest: digest('a'),
        referenceBackendIdentity: {
            rasterImplementationId: 'gsplat-reference-rgb/v1',
            evidenceBackendKind: 'reference-contributor',
            evidenceBackendId: 'complete-contributor/reference-v1',
            runtimeBuildId: 'locked-runtime-build-1'
        }
    });
    return {
        publicationBinding,
        candidate: createReferenceCandidateArtifact({
            publicationBinding,
            sourceAggregationResultDigest: digest('b'),
            selectedStableGaussianIds: selected,
            uncertainStableGaussianIds: uncertain
        }),
        evidence: Object.fromEntries(
            views
                .filter((entry) => entry.participation === 'included')
                .map((entry) => [
                    entry.viewId,
                    {
                        identity: entry.evidenceIdentity,
                        artifactDigest: digest(
                            entry.viewId === 'view-1' ? '6' : '7'
                        )
                    }
                ])
        )
    };
};

const harness = (produceReplacement) => {
    const dirty = new AISelectDirtyStateTracker();
    const publications = new CandidatePublicationStore(dirty);
    const currentViews = [view('view-1'), view('view-2')];
    const first = result(currentViews);
    publications.publish(first.candidate, first.publicationBinding);
    const calls = [];
    const controller = new AISelectCandidateCorrectionController({
        dirtyState: dirty,
        candidatePublications: publications,
        resolveCurrentViews: () => currentViews,
        produceCandidate: async (input) => {
            calls.push(input);
            return produceReplacement(input, currentViews);
        }
    });
    controller.rememberPublishedEvidence(first.evidence);
    return { controller, dirty, publications, currentViews, calls, first };
};

test('Fix AI Result returns to correction controls while retaining the current Candidate', () => {
    const h = harness(async () => result(h.currentViews));

    h.controller.beginCorrection();

    assert.equal(h.controller.state.mode, 'correcting');
    assert.equal(h.controller.state.candidate.status, 'current');
    assert.deepEqual(
        h.publications.inspectableCandidate.candidate.selectedStableGaussianIds,
        [5]
    );
    assert.equal(h.dirty.state.candidateStale, false);
});

test('browsing and unpublished Editing Mask changes do not stale Candidate or Evidence', () => {
    const h = harness(async () => result(h.currentViews));

    h.controller.beginCorrection();
    h.controller.noteEditingMaskChanged('view-1');

    assert.equal(h.controller.state.candidate.status, 'current');
    assert.equal(h.dirty.state.candidateStale, false);
    assert.deepEqual(h.dirty.state.evidenceDirtyViewIds, []);
});

test('Update 3D Candidate reuses exact Evidence and recomputes only stale Included Views', async () => {
    const h = harness(async (_input, views) => result(views, [5, 11], [9]));
    h.currentViews[0] = view('view-1', {
        stableMaskDigest: digest('c'),
        evidenceIdentity: {
            ...h.currentViews[0].evidenceIdentity,
            stableMaskDigest: digest('c')
        }
    });
    h.dirty.markStableMaskPublished('view-1');

    await h.controller.updateCandidate();

    assert.equal(h.calls.length, 1);
    assert.deepEqual(h.calls[0].recomputeViewIds, ['view-1']);
    assert.deepEqual(h.calls[0].reuseViewIds, ['view-2']);
    assert.equal(h.controller.state.status, 'idle');
    assert.equal(h.controller.state.candidate.status, 'current');
    assert.deepEqual(
        h.publications.inspectableCandidate.candidate.selectedStableGaussianIds,
        [5, 11]
    );
    assert.equal(h.dirty.state.candidateStale, false);
});

test('Excluded View Evidence may stay cached but never contributes to Re-Lift', async () => {
    const h = harness(async (_input, views) => result(views));
    h.currentViews[1] = view('view-2', { participation: 'excluded' });
    h.dirty.markParticipationChanged('view-2');

    await h.controller.updateCandidate();

    assert.deepEqual(h.calls[0].includedViewIds, ['view-1']);
    assert.deepEqual(h.calls[0].reuseViewIds, ['view-1']);
    assert.deepEqual(h.calls[0].recomputeViewIds, []);
    assert.ok(h.controller.cachedEvidenceViewIds.includes('view-2'));
});

test('failed Re-Lift preserves the previous stale Candidate and exact dirty state', async () => {
    const h = harness(async () => {
        throw new Error('Evidence recomputation failed.');
    });
    h.dirty.markStableMaskPublished('view-1');

    await assert.rejects(
        h.controller.updateCandidate(),
        /Evidence recomputation failed/
    );

    assert.equal(h.controller.state.status, 'failed');
    assert.equal(h.controller.state.candidate.status, 'stale');
    assert.equal(h.dirty.state.candidateStale, true);
    assert.deepEqual(h.dirty.state.evidenceDirtyViewIds, ['view-1']);
    assert.deepEqual(
        h.publications.inspectableCandidate.candidate.selectedStableGaussianIds,
        [5]
    );
});

test('a Stable input race discards the completed replacement before publication', async () => {
    let finish;
    const h = harness(
        (_input, views) =>
            new Promise((resolve) => {
                finish = () => resolve(result(views, [11], [9]));
            })
    );
    const updating = h.controller.updateCandidate();
    h.currentViews[0] = view('view-1', {
        stableMaskDigest: digest('d'),
        evidenceIdentity: {
            ...h.currentViews[0].evidenceIdentity,
            stableMaskDigest: digest('d')
        }
    });
    h.dirty.markStableMaskPublished('view-1');
    finish();

    await assert.rejects(updating, /inputs changed/i);

    assert.equal(h.controller.state.candidate.status, 'stale');
    assert.deepEqual(
        h.publications.inspectableCandidate.candidate.selectedStableGaussianIds,
        [5]
    );
    assert.deepEqual(h.dirty.state.evidenceDirtyViewIds, ['view-1']);
});

test('an Excluded Stable-input race discards every related publication', async () => {
    let finish;
    let relatedPublicationCount = 0;
    const h = harness(
        (_input, views) =>
            new Promise((resolve) => {
                finish = () =>
                    resolve({
                        ...result(views, [11], [9]),
                        publishRelatedProducts: () => {
                            relatedPublicationCount += 1;
                        }
                    });
            })
    );
    h.currentViews[1] = view('view-2', { participation: 'excluded' });
    h.dirty.markParticipationChanged('view-2');
    const updating = h.controller.updateCandidate();
    h.currentViews[1] = view('view-2', {
        participation: 'excluded',
        stableMaskDigest: digest('e'),
        evidenceIdentity: {
            ...h.currentViews[1].evidenceIdentity,
            stableMaskDigest: digest('e')
        }
    });
    h.dirty.markStableMaskPublished('view-2');
    finish();

    await assert.rejects(updating, /inputs changed/i);

    assert.equal(relatedPublicationCount, 0);
    assert.deepEqual(
        h.publications.inspectableCandidate.candidate.selectedStableGaussianIds,
        [5]
    );
});

test('Working Set and backend identity changes force exact Evidence recompute', async () => {
    const h = harness(async (_input, views) => result(views, [5, 11], [9]));
    h.currentViews[0] = view('view-1', {
        evidenceIdentity: {
            ...h.currentViews[0].evidenceIdentity,
            evidenceWorkingSetToken: digest('f'),
            runtimeBuildId: 'locked-runtime-build-2'
        }
    });
    h.dirty.markEvidencePolicyOrWorkingSetChanged(['view-1']);

    await h.controller.updateCandidate();

    assert.deepEqual(h.calls[0].recomputeViewIds, ['view-1']);
    assert.deepEqual(h.calls[0].reuseViewIds, ['view-2']);
});
