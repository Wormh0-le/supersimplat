const assert = require('node:assert/strict');
const test = require('node:test');

const {
    aiSelectSupportProbePolicyVersion,
    isAnchorSupportProbeRequest,
    isAnchorSupportProbeResponse,
    supportProbeResponseMatchesRequest
} = require('../.test-dist/src/ai-select/support-probe.js');
const {
    buildPackedSceneSnapshot,
    sha256Digest
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');

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
    stableIds: new Uint32Array([3]),
    means: new Float32Array([3, 0, 0]),
    rotationsXyzw: new Float32Array([0, 0, 0, 1]),
    logScales: new Float32Array([0, 0, 0]),
    logitOpacities: new Float32Array([0]),
    dc: new Float32Array([0, 0, 0]),
    sh: new Float32Array(),
    shFloatCountPerGaussian: 0
});

const cameraBinding = () =>
    captureEditorCameraBinding({
        targetSize: { width: 64, height: 48 },
        fov: 60,
        near: 0.1,
        far: 100,
        camera: { horizontalFov: false },
        worldTransform: {
            data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
        }
    });

const maskArtifact = (width = 64, height = 48) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    bytes[0] = 0b101;
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    });
};

const request = (overrides = {}) => ({
    requestBinding: {
        targetContextId: 'ai-target-context-1',
        contextRevision: 0,
        dependencyToken: dependency()
    },
    target: { splatId: 'editor-splat:1' },
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    viewId: 'anchor-view',
    supportProbeAttemptId: 'support-probe-attempt-1',
    cameraBinding: cameraBinding(),
    rgbDigest: `sha256:${'a'.repeat(64)}`,
    stableMask: maskArtifact(),
    supportProbePolicyVersion: aiSelectSupportProbePolicyVersion,
    ...overrides
});

const responseFor = (req, overrides = {}) => ({
    requestBinding: req.requestBinding,
    targetSplatId: req.target.splatId,
    sceneId: req.sceneId,
    sceneVersion: req.sceneVersion,
    viewId: req.viewId,
    supportProbeAttemptId: req.supportProbeAttemptId,
    cameraBinding: req.cameraBinding,
    rgbDigest: req.rgbDigest,
    stableMaskDigest: req.stableMask.digest,
    supportProbePolicyVersion: req.supportProbePolicyVersion,
    support: { computable: true, observedGaussianCount: 42 },
    ...overrides
});

test('a well-formed support probe request validates', () => {
    assert.equal(isAnchorSupportProbeRequest(request()), true);
});

test('request validation rejects broken identity and mask references', () => {
    assert.equal(
        isAnchorSupportProbeRequest(
            request({ requestBinding: { targetContextId: 'x' } })
        ),
        false
    );
    assert.equal(
        isAnchorSupportProbeRequest(request({ supportProbeAttemptId: '' })),
        false
    );
    assert.equal(
        isAnchorSupportProbeRequest(request({ rgbDigest: 'x' })),
        false
    );
    assert.equal(
        isAnchorSupportProbeRequest(request({ stableMask: { width: 64 } })),
        false
    );
    assert.equal(
        isAnchorSupportProbeRequest(
            request({ supportProbePolicyVersion: 'other/v9' })
        ),
        false
    );
    // The Stable Mask must cover the CameraBinding image extent.
    assert.equal(
        isAnchorSupportProbeRequest(
            request({ stableMask: maskArtifact(8, 8) })
        ),
        false
    );
});

test('a well-formed support probe response validates', () => {
    assert.equal(isAnchorSupportProbeResponse(responseFor(request())), true);
});

test('response validation rejects ownership-classifying payloads', () => {
    const req = request();
    assert.equal(
        isAnchorSupportProbeResponse(
            responseFor(req, {
                support: {
                    computable: true,
                    observedGaussianCount: 3,
                    selectedGaussianIds: [1]
                }
            })
        ),
        false
    );
    assert.equal(
        isAnchorSupportProbeResponse(
            responseFor(req, { support: { computable: true } })
        ),
        false
    );
});

test('response matching fails closed on any identity drift', () => {
    const req = request();
    assert.equal(
        supportProbeResponseMatchesRequest(responseFor(req), req),
        true
    );
    assert.equal(
        supportProbeResponseMatchesRequest(
            responseFor(req, { supportProbeAttemptId: 'other' }),
            req
        ),
        false
    );
    assert.equal(
        supportProbeResponseMatchesRequest(
            responseFor(req, { rgbDigest: `sha256:${'b'.repeat(64)}` }),
            req
        ),
        false
    );
    assert.equal(
        supportProbeResponseMatchesRequest(
            responseFor(req, { stableMaskDigest: `sha256:${'c'.repeat(64)}` }),
            req
        ),
        false
    );
    const movedCamera = { ...req.cameraBinding, revision: 99 };
    assert.equal(
        supportProbeResponseMatchesRequest(
            responseFor(req, { cameraBinding: movedCamera }),
            req
        ),
        false
    );
    assert.equal(
        supportProbeResponseMatchesRequest(
            responseFor(req, { supportProbePolicyVersion: 'other/v9' }),
            req
        ),
        false
    );
});
