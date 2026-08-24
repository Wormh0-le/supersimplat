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
    admitGaussianEvidence,
    createGaussianEvidenceArtifact,
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
    shFloatCountPerGaussian: 0,
    authoritativeRenderScope: {
        policyId: 'visible-editor-splats-conservative/v1',
        targetSplatId: 'editor-splat:1',
        identityDigest: `sha256:${'a'.repeat(64)}`,
        entries: [
            {
                splatId: 'editor-splat:1',
                role: 'target',
                sourceContentDigest: `sha256:${'b'.repeat(64)}`,
                rowOffset: 0,
                rowCount: 2,
                renderIdStart: 5
            }
        ]
    }
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
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    evidenceBackendKind: 'production-direct',
    evidenceBackendId: 'global-atomic/direct-v1',
    runtimeBuildId:
        'sha256:b87858ec0baaeea5cc272e02273f8f3a13410f4322c33c088fed4b4144ecf1e0'
};
const admission = admitGaussianEvidence(currentInput);
assert.equal(admission.status, 'admitted');
const cachedArtifact = createGaussianEvidenceArtifact(admission.admission, {
    positiveMass: [0.5, 0],
    negativeMass: [0, 0.5],
    visibleMass: [0.5, 0.5],
    boundaryMass: [0, 0]
});
const validRequest = () => ({
    liftAttemptId: 're-lift-1',
    productionIdentityDigest: `sha256:${'c'.repeat(64)}`,
    generationState: 'complete',
    snapshot,
    requestBinding,
    targetSplatId: snapshot.sceneId,
    classificationUniverseStableGaussianIds: [5, 9],
    classificationScopeStableGaussianIds: [5, 9],
    evidenceWorkingSet,
    views: [
        {
            currentInput,
            cameraBinding,
            stableMask: mask,
            cachedArtifact
        }
    ]
});

test('Candidate Re-Lift request binds target identity without requiring every render occluder', () => {
    assert.equal(isCandidateReLiftRequest(validRequest()), true);
    const mismatched = validRequest();
    mismatched.views = [
        {
            ...mismatched.views[0],
            currentInput: {
                ...currentInput,
                renderWorkingSet: {
                    ...currentInput.renderWorkingSet,
                    stableGaussianIds: [42]
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
