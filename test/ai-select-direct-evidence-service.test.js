const assert = require('node:assert/strict');
const test = require('node:test');

const {
    isDirectEvidenceRequest,
    isDirectEvidenceResponseForRequest
} = require('../.test-dist/src/ai-select/direct-evidence-service.js');
const {
    cameraBindingDigest,
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    admitGaussianEvidence,
    createEvidenceWorkingSet,
    createGaussianEvidenceArtifact
} = require('../.test-dist/src/ai-select/gaussian-evidence-contract.js');
const {
    buildPackedSceneSnapshot,
    sha256Digest
} = require('../.test-dist/src/scene-snapshot-binary.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;
const dependency = {
    splatId: 'target-splat',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1'
};
const snapshot = buildPackedSceneSnapshot({
    sceneId: 'target-splat',
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
    stableIds: new Uint32Array([5, 9, 42]),
    means: new Float32Array(9),
    rotationsXyzw: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]),
    logScales: new Float32Array(9),
    logitOpacities: new Float32Array(3),
    dc: new Float32Array(9),
    sh: new Float32Array(),
    shFloatCountPerGaussian: 0,
    authoritativeRenderScope: {
        policyId: 'visible-editor-splats-conservative/v1',
        targetSplatId: 'target-splat',
        identityDigest: digest('a'),
        entries: [
            {
                splatId: 'target-splat',
                role: 'target',
                sourceContentDigest: digest('b'),
                rowOffset: 0,
                rowCount: 2,
                renderIdStart: 5
            },
            {
                splatId: 'occluder-splat',
                role: 'occluder',
                sourceContentDigest: digest('c'),
                rowOffset: 2,
                rowCount: 1,
                renderIdStart: 42
            }
        ]
    }
});
const cameraBinding = captureEditorCameraBinding({
    targetSize: { width: 1, height: 1 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    }
});
const maskBytes = new Uint8Array([1]);
const stableMask = {
    encoding: 'bitset-lsb-v1',
    width: 1,
    height: 1,
    data: 'AQ==',
    digest: sha256Digest(maskBytes)
};
const workingSet = createEvidenceWorkingSet({
    targetSplatId: 'target-splat',
    coreTargetStableIds: [5, 9],
    contextStableGaussianIds: []
});
const currentInput = {
    requestBinding: {
        targetContextId: 'context-1',
        contextRevision: 1,
        dependencyToken: dependency
    },
    targetSplatId: 'target-splat',
    view: {
        viewId: 'view-1',
        renderStatus: 'ready',
        participation: 'included',
        cameraBindingDigest: cameraBindingDigest(cameraBinding),
        rgbDigest: digest('d'),
        stableMaskDigest: stableMask.digest
    },
    evidencePolicyDigest:
        'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd',
    renderWorkingSet: {
        targetSplatId: 'target-splat',
        dependencyToken: dependency,
        cameraBindingDigest: cameraBindingDigest(cameraBinding),
        renderWorkingSetToken: snapshot.contentDigest,
        stableGaussianIds: [5, 9, 42],
        completeness: 'complete'
    },
    evidenceWorkingSet: workingSet,
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    evidenceBackendKind: 'production-direct',
    evidenceBackendId: 'global-atomic/direct-v1',
    runtimeBuildId:
        'sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f'
};
const request = {
    evidenceAttemptId: 'direct-evidence-attempt-1',
    snapshot,
    currentInput,
    cameraBinding,
    stableMask
};

test('Direct Evidence request separates the target write set from render occluders', () => {
    assert.equal(isDirectEvidenceRequest(request), true);
    assert.equal(
        isDirectEvidenceRequest({ ...request, evidenceAttemptId: '' }),
        false
    );
    assert.equal(
        isDirectEvidenceRequest({
            ...request,
            currentInput: {
                ...currentInput,
                evidenceWorkingSet: createEvidenceWorkingSet({
                    targetSplatId: 'target-splat',
                    coreTargetStableIds: [42],
                    contextStableGaussianIds: []
                })
            }
        }),
        false
    );
});

test('Direct Evidence response must contain one current production artifact', () => {
    const admission = admitGaussianEvidence(currentInput);
    assert.equal(admission.status, 'admitted');
    const artifact = createGaussianEvidenceArtifact(admission.admission, {
        positiveMass: [0.5, 0],
        negativeMass: [0, 0.25],
        visibleMass: [0.5, 0.25],
        boundaryMass: [0, 0]
    });
    const response = {
        status: 'complete',
        evidenceAttemptId: request.evidenceAttemptId,
        requestBinding: currentInput.requestBinding,
        targetSplatId: 'target-splat',
        viewId: 'view-1',
        reused: false,
        artifact,
        telemetry: {
            evidenceBufferBytes: 32,
            pixelWeightBufferBytes: 16,
            boundaryBufferBytes: 24,
            peakVramBytes: 1024
        }
    };
    assert.equal(isDirectEvidenceResponseForRequest(response, request), true);
    assert.equal(
        isDirectEvidenceResponseForRequest(
            { ...response, evidenceAttemptId: 'stale-attempt' },
            request
        ),
        false
    );
    assert.equal(
        isDirectEvidenceResponseForRequest(
            { ...response, artifact: { ...artifact, rgbDigest: digest('e') } },
            request
        ),
        false
    );
});
