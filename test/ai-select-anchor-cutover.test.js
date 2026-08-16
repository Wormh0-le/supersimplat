const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AISelectAnchorCutoverCoordinator
} = require('../.test-dist/src/ai-select/anchor-cutover.js');
const {
    AISelectCandidateCorrectionController
} = require('../.test-dist/src/ai-select/candidate-correction.js');
const {
    CandidatePublicationStore
} = require('../.test-dist/src/ai-select/candidate-publication.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const deferred = () => {
    let resolve;
    const promise = new Promise((innerResolve) => {
        resolve = innerResolve;
    });
    return { promise, resolve };
};

test('changed-Anchor cutover publishes confirmation before releasing real Candidate Evidence', async () => {
    const events = [];
    let liveRgb = 'old-rgb';
    let liveMask = 'old-mask';
    let confirmedRgb = 'old-rgb';
    let oldGeneratedViews = true;
    let oldAnchorEvidence = true;
    let oldCandidate = true;
    const candidateUpdate = deferred();
    const candidateEvidenceIdentity = {
        viewId: 'anchor-view',
        cameraBindingDigest: digest('1'),
        rgbDigest: digest('2'),
        stableMaskDigest: digest('3'),
        evidencePolicyDigest: digest('4'),
        renderWorkingSetToken: digest('5'),
        evidenceWorkingSetToken: digest('6'),
        rasterImplementationId: 'gsplat-reference-rgb/v1',
        evidenceBackendKind: 'reference-contributor',
        evidenceBackendId: 'complete-contributor/reference-v1',
        runtimeBuildId: 'locked-runtime-build-1'
    };
    const candidateDirtyState = new AISelectDirtyStateTracker();
    const candidatePublications = new CandidatePublicationStore(
        candidateDirtyState
    );
    const candidateCorrection = new AISelectCandidateCorrectionController({
        dirtyState: candidateDirtyState,
        candidatePublications,
        resolveCurrentViews: () => [
            {
                viewId: 'anchor-view',
                participation: 'included',
                stableMaskDigest: candidateEvidenceIdentity.stableMaskDigest,
                evidenceIdentity: candidateEvidenceIdentity,
                payload: null
            }
        ],
        produceCandidate: () => candidateUpdate.promise
    });
    candidateCorrection.rememberPublishedEvidence({
        'anchor-view': {
            identity: candidateEvidenceIdentity,
            artifactDigest: digest('7')
        }
    });
    const updatingCandidate = candidateCorrection.updateCandidate();
    const coordinator = new AISelectAnchorCutoverCoordinator({
        anchor: {
            commitAnchorAdjustmentDraft(render) {
                assert.equal(oldGeneratedViews, true);
                assert.equal(oldCandidate, true);
                liveRgb = render.rgb.digest;
                events.push('live-anchor');
            }
        },
        mask: {
            replaceStableFromAdjustment(mask) {
                assert.equal(liveRgb, 'draft-rgb');
                assert.equal(oldAnchorEvidence, true);
                liveMask = mask.artifact.digest;
                events.push('live-mask');
            },
            releasePreviousAnchorProductsAfterAdjustment() {
                assert.equal(confirmedRgb, 'draft-rgb');
                assert.equal(oldGeneratedViews, false);
                oldAnchorEvidence = false;
                events.push('anchor-products');
            }
        },
        confirmation: {
            replaceConfirmedAnchorFromAdjustment() {
                assert.equal(liveRgb, 'draft-rgb');
                assert.equal(liveMask, 'draft-mask');
                confirmedRgb = liveRgb;
                oldGeneratedViews = false;
                events.push('confirmed-anchor');
                return { rgbDigest: confirmedRgb };
            }
        },
        releaseDependentProducts() {
            assert.equal(confirmedRgb, 'draft-rgb');
            assert.equal(oldGeneratedViews, false);
            assert.equal(oldAnchorEvidence, false);
            assert.deepEqual(candidateCorrection.cachedEvidenceViewIds, [
                'anchor-view'
            ]);
            assert.equal(candidateCorrection.state.status, 'updating');
            candidateCorrection.reset();
            candidatePublications.reset();
            oldCandidate = false;
            events.push('dependent-products');
        }
    });

    const confirmed = coordinator.commit({
        render: { rgb: { digest: 'draft-rgb' } },
        stableMask: { artifact: { digest: 'draft-mask' } }
    });

    assert.equal(confirmed.rgbDigest, 'draft-rgb');
    assert.equal(oldCandidate, false);
    assert.deepEqual(candidateCorrection.cachedEvidenceViewIds, []);
    assert.equal(candidateCorrection.state.status, 'idle');
    candidateUpdate.resolve(undefined);
    await updatingCandidate;
    assert.deepEqual(candidateCorrection.cachedEvidenceViewIds, []);
    assert.deepEqual(events, [
        'live-anchor',
        'live-mask',
        'confirmed-anchor',
        'anchor-products',
        'dependent-products'
    ]);
});
