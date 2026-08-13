const assert = require('node:assert/strict');
const test = require('node:test');

const {
    isCandidateReLiftRequest
} = require('../.test-dist/src/ai-select/candidate-re-lift.js');
const {
    cameraBindingDigest,
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    createEvidenceWorkingSet
} = require('../.test-dist/src/ai-select/gaussian-evidence-contract.js');
const {
    buildPackedSceneSnapshot,
    sha256Digest
} = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = () => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1'
});

const snapshot = buildPackedSceneSnapshot({
    sceneId: 'editor-splat:1',
    coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
    stableIdSchema: 'uint32',
    appearancePolicy: 'effective-editor-dc-sh-bands-0',
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1',
        backgroundRgba: [0, 0, 0, 1],
        alphaMode: 'opaque-background',
        shBands: 0,
        rasterizer: 'playcanvas-gsplat-classic'
    },
    stableIds: new Uint32Array([5, 9]),
    means: new Float32Array([0, 0, 0, 1, 0, 0]),
    rotationsXyzw: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1]),
    logScales: new Float32Array(6),
    logitOpacities: new Float32Array(2),
    dc: new Float32Array(6),
    sh: new Float32Array(),
    shFloatCountPerGaussian: 0
});

const cameraBinding = captureEditorCameraBinding({
    targetSize: { width: 2, height: 2 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    }
});
const evidenceWorkingSet = createEvidenceWorkingSet({
    targetSplatId: snapshot.sceneId,
    coreTargetStableIds: [5, 9],
    contextStableGaussianIds: []
});
const mask = {
    encoding: 'bitset-lsb-v1',
    width: 2,
    height: 2,
    data: 'AQ==',
    digest: sha256Digest(new Uint8Array([1]))
};
const requestBinding = {
    targetContextId: 'ai-target-context-1',
    contextRevision: 1,
    dependencyToken: dependency()
};
const currentInput = {
    requestBinding,
    targetSplatId: snapshot.sceneId,
    view: {
        viewId: 'view-1',
        renderStatus: 'ready',
        participation: 'included',
        cameraBindingDigest: cameraBindingDigest(cameraBinding),
        rgbDigest: `sha256:${'b'.repeat(64)}`,
        stableMaskDigest: mask.digest
    },
    evidencePolicyDigest:
        'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd',
    renderWorkingSet: {
        targetSplatId: snapshot.sceneId,
        dependencyToken: dependency(),
        cameraBindingDigest: cameraBindingDigest(cameraBinding),
        renderWorkingSetToken: snapshot.contentDigest,
        stableGaussianIds: [5, 9],
        completeness: 'complete'
    },
    evidenceWorkingSet,
    rasterImplementationId: 'gsplat-reference-rgb/v1',
    evidenceBackendKind: 'reference-contributor',
    evidenceBackendId: 'complete-contributor/reference-v1',
    runtimeBuildId:
        'sha256:a04a3840702bca8d86365dc44c8a693344e54fb09db8a2c2131a4ed711717e40'
};
const validRequest = () => ({
    liftAttemptId: 're-lift-1',
    snapshot,
    requestBinding,
    targetSplatId: snapshot.sceneId,
    classificationUniverseStableGaussianIds: [5, 9],
    classificationScopeStableGaussianIds: [5, 9],
    evidenceWorkingSet,
    views: [{ currentInput, cameraBinding, stableMask: mask }]
});

test('Candidate Re-Lift request is bound to the exact full Scene Snapshot', () => {
    assert.equal(isCandidateReLiftRequest(validRequest()), true);
    const mismatched = validRequest();
    mismatched.views = [
        {
            ...mismatched.views[0],
            currentInput: {
                ...currentInput,
                renderWorkingSet: {
                    ...currentInput.renderWorkingSet,
                    stableGaussianIds: [5]
                }
            }
        }
    ];
    assert.equal(isCandidateReLiftRequest(mismatched), false);
});

test('Candidate Re-Lift request rejects duplicate View identities', () => {
    const mismatched = validRequest();
    mismatched.views = [...mismatched.views, mismatched.views[0]];

    assert.equal(isCandidateReLiftRequest(mismatched), false);
});
