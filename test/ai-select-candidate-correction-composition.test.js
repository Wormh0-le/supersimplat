const assert = require('node:assert/strict');
const test = require('node:test');

const {
    createAISelectCandidateCorrectionController
} = require('../.test-dist/src/ai-select/candidate-correction-composition.js');
const {
    CandidatePublicationStore,
    createCandidatePublicationBinding,
    createReferenceCandidateArtifact
} = require('../.test-dist/src/ai-select/candidate-publication.js');
const {
    referenceAggregationPolicyDigest,
    referenceContributorEvidenceBackendId,
    referenceEvidencePolicyDigest,
    referenceEvidenceRasterImplementationId,
    referenceEvidenceRuntimeBuildId
} = require('../.test-dist/src/ai-select/candidate-re-lift.js');
const {
    directEvidenceBackendId,
    directEvidenceRasterImplementationId,
    directEvidenceRuntimeBuildId
} = require('../.test-dist/src/ai-select/direct-evidence-service.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');
const {
    admitGaussianEvidence,
    createGaussianEvidenceArtifact
} = require('../.test-dist/src/ai-select/gaussian-evidence-contract.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;
const dependencyToken = {
    splatId: 'scene-1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1'
};
const cameraBinding = {
    revision: 0,
    cameraToWorld: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    projection: {
        model: 'pinhole',
        fx: 10,
        fy: 10,
        cx: 4,
        cy: 4,
        width: 8,
        height: 8,
        near: 0.1,
        far: 100
    },
    conventionVersion: 'opencv-camera-to-world/v1'
};
const snapshot = {
    sceneId: 'scene-1',
    sceneVersion: digest('a'),
    contentDigest: digest('a'),
    stableIds: new Uint32Array([5, 9, 42]),
    renderConfiguration: { version: 'supersplat-effective-rgb-v1' },
    authoritativeRenderScope: {
        targetSplatId: 'scene-1',
        entries: [
            {
                splatId: 'scene-1',
                role: 'target',
                rowOffset: 0,
                rowCount: 2
            },
            {
                splatId: 'occluder-1',
                role: 'occluder',
                rowOffset: 2,
                rowCount: 1
            }
        ]
    }
};

const artifactFor = (currentInput) => {
    const admitted = admitGaussianEvidence(currentInput);
    assert.equal(admitted.status, 'admitted');
    return createGaussianEvidenceArtifact(admitted.admission, {
        positiveMass: [0.75, 0],
        negativeMass: [0, 0.5],
        visibleMass: [1, 1],
        boundaryMass: [0, 0]
    });
};

test('composition publishes production Direct Evidence while retaining reference Candidate isolation', async () => {
    const requestBinding = {
        targetContextId: 'context-1',
        contextRevision: 3,
        dependencyToken
    };
    let anchorState = {
        context: {
            targetContextId: 'context-1',
            revision: 3,
            lifecycle: 'active',
            target: { splatId: 'scene-1' },
            dependencyToken
        },
        anchor: {
            viewId: 'anchor-view',
            renderStatus: 'ready',
            cameraBinding,
            rgb: { digest: digest('2'), width: 8, height: 8 },
            renderWorkingSetToken: digest('b'),
            renderStableGaussianIds: [5, 42]
        }
    };
    const anchorListeners = new Set();
    const anchor = {
        get state() {
            return anchorState;
        },
        getAnchorSnapshot: () => snapshot,
        isTargetActive: () => true,
        acceptsTargetBinding: (binding) =>
            binding.targetContextId === anchorState.context.targetContextId &&
            binding.contextRevision === anchorState.context.revision,
        subscribe(listener) {
            anchorListeners.add(listener);
            listener(anchorState);
            return () => anchorListeners.delete(listener);
        }
    };
    const stableMask = {
        artifact: { digest: digest('3') }
    };
    const evidenceReady = [];
    const dirtyState = new AISelectDirtyStateTracker();
    const masks = {
        state: { stableMask },
        dirtyState,
        evidenceRegistry: {
            markPending() {},
            markFailed() {},
            markReady(identity) {
                evidenceReady.push(identity);
            }
        },
        maskRegistry: {
            viewState() {
                return { stableMask: null };
            }
        }
    };
    const generatedListeners = new Set();
    const generatedViews = {
        state: { views: [] },
        subscribe(listener) {
            generatedListeners.add(listener);
            listener(this.state);
            return () => generatedListeners.delete(listener);
        }
    };
    const directCalls = [];
    const referenceCalls = [];
    const provider = {
        async produceDirectEvidence(request) {
            directCalls.push(request);
            const artifact = artifactFor(request.currentInput);
            return {
                status: 'complete',
                requestBinding: request.currentInput.requestBinding,
                targetSplatId: request.currentInput.targetSplatId,
                viewId: request.currentInput.view.viewId,
                reused: request.cachedArtifact !== undefined,
                artifact
            };
        },
        async produceCandidateReLift(request) {
            referenceCalls.push(request);
            const evidence = request.views.map((view) => ({
                viewId: view.currentInput.view.viewId,
                reused: view.cachedArtifact !== undefined,
                artifact: artifactFor(view.currentInput)
            }));
            const publicationBinding = createCandidatePublicationBinding({
                requestBinding,
                targetSplatId: 'scene-1',
                stableInputs: evidence.map((entry) => ({
                    viewId: entry.viewId,
                    participation: 'included',
                    stableMaskDigest: digest('3'),
                    evidenceArtifactDigest: entry.artifact.artifactDigest
                })),
                aggregationPolicyDigest: referenceAggregationPolicyDigest,
                sourceEvidencePolicyDigest: referenceEvidencePolicyDigest,
                evidenceWorkingSetToken:
                    request.evidenceWorkingSet.evidenceWorkingSetToken,
                evidenceArtifactSetDigest: digest('e'),
                referenceBackendIdentity: {
                    rasterImplementationId:
                        referenceEvidenceRasterImplementationId,
                    evidenceBackendKind: 'reference-contributor',
                    evidenceBackendId: referenceContributorEvidenceBackendId,
                    runtimeBuildId: referenceEvidenceRuntimeBuildId
                }
            });
            return {
                status: 'complete',
                requestBinding,
                targetSplatId: 'scene-1',
                evidence,
                candidate: createReferenceCandidateArtifact({
                    publicationBinding,
                    sourceAggregationResultDigest: digest('f'),
                    selectedStableGaussianIds: [5],
                    uncertainStableGaussianIds: [9]
                })
            };
        }
    };
    const candidatePublications = new CandidatePublicationStore(dirtyState);
    const controller = createAISelectCandidateCorrectionController({
        anchor,
        masks,
        generatedViews,
        candidatePublications,
        provider
    });

    await controller.updateCandidate();
    await controller.updateCandidate();

    assert.deepEqual(controller.cachedEvidenceViewIds, ['anchor-view']);
    assert.equal(
        directCalls[0].currentInput.evidenceBackendKind,
        'production-direct'
    );
    assert.equal(
        directCalls[0].currentInput.renderWorkingSet.renderWorkingSetToken,
        digest('b')
    );
    assert.deepEqual(
        directCalls[0].currentInput.evidenceWorkingSet.stableGaussianIds,
        [5, 9]
    );
    assert.deepEqual(
        directCalls[0].currentInput.renderWorkingSet.stableGaussianIds,
        [5, 42]
    );
    assert.equal(
        directCalls[1].cachedArtifact.evidenceBackendKind,
        'production-direct'
    );
    assert.equal(
        referenceCalls[1].views[0].cachedArtifact.evidenceBackendKind,
        'reference-contributor'
    );
    assert.equal(evidenceReady.length, 2);
    assert.equal(
        candidatePublications.inspectableCandidate.publicationBinding
            .referenceBackendIdentity.evidenceBackendKind,
        'reference-contributor'
    );

    anchorState = {
        ...anchorState,
        context: { ...anchorState.context, revision: 4 }
    };
    for (const listener of anchorListeners) {
        listener(anchorState);
    }
    assert.deepEqual(controller.cachedEvidenceViewIds, []);
});
