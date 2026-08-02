const assert = require('node:assert/strict');
const test = require('node:test');

const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    aiSelectTargetGeometryPolicyVersion,
    isTargetGeometryHintArtifact,
    isTargetGeometryHintRequest,
    isTargetGeometryHintResponse,
    targetGeometryHintResponseMatchesRequest
} = require('../.test-dist/src/ai-select/target-geometry-hint.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const requestBinding = () => ({
    targetContextId: 'ai-target-context-1',
    contextRevision: 3,
    dependencyToken: dependency()
});

const target = () => ({ splatId: 'editor-splat:1' });

const snapshot = {
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    contentDigest: `sha256:${'c'.repeat(64)}`,
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1'
    }
};

const editorCamera = () => ({
    targetSize: { width: 64, height: 48 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
    }
});

const cameraBinding = () => captureEditorCameraBinding(editorCamera());

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const maskArtifact = (width, height, seedByte) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    bytes[0] = seedByte;
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return {
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    };
};

const hintArtifactFor = (request, overrides = {}) => ({
    schemaVersion: 1,
    targetContextId: request.requestBinding.targetContextId,
    anchorCameraBindingDigest: request.anchorCameraBindingDigest,
    anchorRgbDigest: request.anchorRgbDigest,
    anchorStableMaskDigest: request.anchorStableMask.digest,
    geometryPolicyDigest: digest('e'),
    centerWorld: [1, 2, 3],
    extentWorld: [0.5, 0.25, 0.125],
    visiblePoints: [
        [1, 2, 3],
        [4, 5, 6]
    ],
    quality: 'usable',
    reasons: [],
    artifactDigest: digest('f'),
    ...overrides
});

const hintRequest = (overrides = {}) => ({
    requestBinding: requestBinding(),
    target: target(),
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    geometryAttemptId: 'target-geometry-hint-attempt-1',
    anchorCameraBinding: cameraBinding(),
    anchorCameraBindingDigest: digest('b'),
    anchorRgbDigest: digest('a'),
    anchorStableMask: maskArtifact(64, 48, 0b101),
    geometryPolicyVersion: aiSelectTargetGeometryPolicyVersion,
    ...overrides
});

const hintResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    geometryAttemptId: request.geometryAttemptId,
    geometryPolicyVersion: request.geometryPolicyVersion,
    hint: hintArtifactFor(request),
    ...overrides
});

test('a complete Target Geometry Hint request validates', () => {
    assert.ok(isTargetGeometryHintRequest(hintRequest()));
});

test('hint request validation fails closed on malformed inputs', () => {
    const request = hintRequest();
    assert.ok(!isTargetGeometryHintRequest(null));
    assert.ok(!isTargetGeometryHintRequest([]));
    assert.ok(
        !isTargetGeometryHintRequest({ ...request, requestBinding: null })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            requestBinding: { ...request.requestBinding, contextRevision: -1 }
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            target: { splatId: 'editor-splat:2' }
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            snapshot: { ...snapshot, sceneId: 'editor-splat:2' }
        })
    );
    assert.ok(!isTargetGeometryHintRequest({ ...request, snapshot: null }));
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            sceneId: 'editor-splat:2'
        })
    );
    assert.ok(!isTargetGeometryHintRequest({ ...request, sceneVersion: '' }));
    assert.ok(
        !isTargetGeometryHintRequest({ ...request, geometryAttemptId: '' })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            anchorCameraBinding: { revision: 0 }
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            anchorCameraBindingDigest: 'not-a-digest'
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            anchorRgbDigest: 'sha256:xyz'
        })
    );
    // The Stable Mask must match the Anchor CameraBinding projection exactly.
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            anchorStableMask: maskArtifact(32, 24, 0b101)
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            anchorStableMask: { ...request.anchorStableMask, digest: 'x' }
        })
    );
    assert.ok(
        !isTargetGeometryHintRequest({
            ...request,
            geometryPolicyVersion: 'target-geometry/v0'
        })
    );
});

test('a complete Target Geometry Hint artifact validates', () => {
    const request = hintRequest();
    assert.ok(isTargetGeometryHintArtifact(hintArtifactFor(request)));
    // A limited hint with evidence-backed reasons is a valid artifact.
    assert.ok(
        isTargetGeometryHintArtifact(
            hintArtifactFor(request, {
                quality: 'limited',
                reasons: ['sparseSupport']
            })
        )
    );
});

test('hint artifact validation fails closed on malformed fields', () => {
    const request = hintRequest();
    const artifact = hintArtifactFor(request);
    assert.ok(!isTargetGeometryHintArtifact(null));
    assert.ok(!isTargetGeometryHintArtifact({ ...artifact, schemaVersion: 2 }));
    assert.ok(
        !isTargetGeometryHintArtifact({ ...artifact, schemaVersion: '1' })
    );
    assert.ok(
        !isTargetGeometryHintArtifact({ ...artifact, targetContextId: '' })
    );
    for (const field of [
        'anchorCameraBindingDigest',
        'anchorRgbDigest',
        'anchorStableMaskDigest',
        'geometryPolicyDigest',
        'artifactDigest'
    ]) {
        assert.ok(
            !isTargetGeometryHintArtifact({ ...artifact, [field]: 'nope' }),
            field
        );
        assert.ok(
            !isTargetGeometryHintArtifact({
                ...artifact,
                [field]: 'sha256:zzzz'
            }),
            field
        );
    }
    for (const field of ['centerWorld', 'extentWorld']) {
        assert.ok(
            !isTargetGeometryHintArtifact({ ...artifact, [field]: [0, 0] }),
            field
        );
        assert.ok(
            !isTargetGeometryHintArtifact({
                ...artifact,
                [field]: [0, 0, Number.NaN]
            }),
            field
        );
        assert.ok(
            !isTargetGeometryHintArtifact({
                ...artifact,
                [field]: [0, 0, Number.POSITIVE_INFINITY]
            }),
            field
        );
    }
    // visiblePoints is bounded to 1..64 finite triples.
    assert.ok(
        !isTargetGeometryHintArtifact({ ...artifact, visiblePoints: [] })
    );
    assert.ok(
        !isTargetGeometryHintArtifact({
            ...artifact,
            visiblePoints: Array.from({ length: 65 }, () => [0, 0, 0])
        })
    );
    assert.ok(
        isTargetGeometryHintArtifact({
            ...artifact,
            visiblePoints: Array.from({ length: 64 }, () => [0, 0, 0])
        })
    );
    assert.ok(
        !isTargetGeometryHintArtifact({
            ...artifact,
            visiblePoints: [[0, 0, Number.NaN]]
        })
    );
    assert.ok(
        !isTargetGeometryHintArtifact({ ...artifact, visiblePoints: [[1, 2]] })
    );
    assert.ok(!isTargetGeometryHintArtifact({ ...artifact, quality: 'good' }));
    assert.ok(!isTargetGeometryHintArtifact({ ...artifact, reasons: [''] }));
    assert.ok(!isTargetGeometryHintArtifact({ ...artifact, reasons: [7] }));
    assert.ok(
        !isTargetGeometryHintArtifact({
            ...artifact,
            reasons: 'sparseSupport'
        })
    );
});

test('a complete Target Geometry Hint response validates', () => {
    const request = hintRequest();
    assert.ok(isTargetGeometryHintResponse(hintResponseFor(request)));
});

test('hint response validation fails closed on malformed inputs', () => {
    const request = hintRequest();
    const response = hintResponseFor(request);
    assert.ok(!isTargetGeometryHintResponse(null));
    assert.ok(
        !isTargetGeometryHintResponse({ ...response, requestBinding: null })
    );
    assert.ok(
        !isTargetGeometryHintResponse({ ...response, targetSplatId: '' })
    );
    assert.ok(!isTargetGeometryHintResponse({ ...response, sceneId: '' }));
    assert.ok(!isTargetGeometryHintResponse({ ...response, sceneVersion: '' }));
    assert.ok(
        !isTargetGeometryHintResponse({ ...response, renderConfigVersion: '' })
    );
    assert.ok(
        !isTargetGeometryHintResponse({ ...response, geometryAttemptId: '' })
    );
    assert.ok(
        !isTargetGeometryHintResponse({
            ...response,
            geometryPolicyVersion: 'target-geometry/v0'
        })
    );
    assert.ok(
        !isTargetGeometryHintResponse({
            ...response,
            hint: hintArtifactFor(request, { schemaVersion: 2 })
        })
    );
});

test('a matching hint response matches its request', () => {
    const request = hintRequest();
    const response = hintResponseFor(request);
    assert.ok(targetGeometryHintResponseMatchesRequest(response, request));
});

test('hint matching fails closed on every identity echo mismatch', () => {
    const request = hintRequest();
    const reject = (overrides) =>
        assert.ok(
            !targetGeometryHintResponseMatchesRequest(
                hintResponseFor(request, overrides),
                request
            ),
            JSON.stringify(Object.keys(overrides))
        );
    reject({
        requestBinding: {
            ...request.requestBinding,
            targetContextId: 'ai-target-context-2'
        }
    });
    reject({
        requestBinding: { ...request.requestBinding, contextRevision: 4 }
    });
    reject({
        requestBinding: {
            ...request.requestBinding,
            dependencyToken: dependency({ renderStateToken: 'render-v2' })
        }
    });
    reject({ targetSplatId: 'editor-splat:2' });
    reject({ sceneId: 'editor-splat:2' });
    reject({ sceneVersion: 'snapshot-v2' });
    reject({ renderConfigVersion: 'supersplat-effective-rgb-v0' });
    reject({ geometryAttemptId: 'target-geometry-hint-attempt-2' });
});

test('hint matching fails closed on artifact binding drift and unavailable quality', () => {
    const request = hintRequest();
    const rejectWithHint = (hintOverrides) =>
        assert.ok(
            !targetGeometryHintResponseMatchesRequest(
                hintResponseFor(request, {
                    hint: hintArtifactFor(request, hintOverrides)
                }),
                request
            ),
            JSON.stringify(Object.keys(hintOverrides))
        );
    rejectWithHint({ targetContextId: 'ai-target-context-2' });
    rejectWithHint({ anchorCameraBindingDigest: digest('0') });
    rejectWithHint({ anchorRgbDigest: digest('0') });
    rejectWithHint({ anchorStableMaskDigest: digest('0') });
    // An unavailable hint is a derivation failure surface, never a
    // publishable artifact: structurally well-formed, rejected on match.
    assert.ok(
        isTargetGeometryHintArtifact(
            hintArtifactFor(request, { quality: 'unavailable' })
        )
    );
    rejectWithHint({ quality: 'unavailable' });
    // The artifact digest itself is opaque but must stay well-formed; the
    // artifactDigest field is not re-derived by the editor.
    assert.ok(
        targetGeometryHintResponseMatchesRequest(
            hintResponseFor(request, {
                hint: hintArtifactFor(request, { artifactDigest: digest('7') })
            }),
            request
        )
    );
});
