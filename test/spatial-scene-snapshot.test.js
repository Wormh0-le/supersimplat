const assert = require('node:assert/strict');
const test = require('node:test');

const {
    buildPackedSceneSnapshot
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    SPATIAL_SCENE_VALIDITY_CUT,
    buildSpatialSceneSnapshot,
    conservativeGaussianSupportBounds
} = require('../.test-dist/src/spatial-scene-snapshot.js');

const snapshot = () =>
    buildPackedSceneSnapshot({
        sceneId: 'editor-splat:42',
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
        stableIds: new Uint32Array([101, 102, 103, 104]),
        means: new Float32Array([2, 0, 5, -3, 0, 5, 0, 1, 12, 80, 0, 4]),
        rotationsXyzw: new Float32Array([
            0,
            0,
            Math.sin(Math.PI / 8),
            Math.cos(Math.PI / 8),
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            1,
            0,
            0,
            0,
            1
        ]),
        logScales: new Float32Array([
            Math.log(3),
            Math.log(0.2),
            Math.log(0.2),
            0,
            0,
            0,
            Math.log(0.1),
            Math.log(0.1),
            Math.log(0.1),
            0,
            0,
            0
        ]),
        logitOpacities: new Float32Array([5, 0, -20, 0]),
        dc: new Float32Array(12),
        sh: new Float32Array(),
        shFloatCountPerGaussian: 0
    });

test('bounds an anisotropic support beyond its Gaussian center and only proves empty below the validity guard', () => {
    const support = conservativeGaussianSupportBounds({
        mean: [2, 0, 5],
        rotationXyzw: [0, 0, Math.sin(Math.PI / 8), Math.cos(Math.PI / 8)],
        logScale: [Math.log(3), Math.log(0.2), Math.log(0.2)],
        logitOpacity: 5
    });

    assert.equal(support.kind, 'finite');
    assert.ok(
        support.min[0] < 0,
        'support reaches across the center-only boundary'
    );
    assert.ok(support.max[0] > 2);
    assert.equal(
        conservativeGaussianSupportBounds({
            mean: [0, 0, 1],
            rotationXyzw: [0, 0, 0, 1],
            logScale: [0, 0, 0],
            logitOpacity: -20
        }).kind,
        'empty'
    );
    assert.ok(SPATIAL_SCENE_VALIDITY_CUT > 0);
});

test('keeps global SceneSnapshot identity separate from spatial chunks and emits only typed chunk payloads', () => {
    const packed = snapshot();
    const spatial = buildSpatialSceneSnapshot(packed, {
        targetSplatId: 'editor-splat:42',
        chunkByteLength: 96
    });

    assert.equal(spatial.manifest.sceneId, packed.sceneId);
    assert.equal(spatial.manifest.sceneVersion, packed.sceneVersion);
    assert.equal(spatial.manifest.contentDigest, packed.contentDigest);
    assert.equal(spatial.manifest.totalGaussianCount, packed.gaussianCount);
    assert.equal(Object.hasOwn(spatial, 'gaussians'), false);
    assert.ok(spatial.manifest.chunks.length > 1);
    assert.ok(spatial.manifest.chunks.every(chunk => chunk.byteLength <= 96));
    assert.ok(
        spatial.manifest.chunks.every(
            chunk => chunk.globalOrdinalMin <= chunk.globalOrdinalMax
        )
    );

    const first = spatial.manifest.chunks[0];
    const payload = spatial.readChunkPayload(first.chunkId);
    assert.equal(payload.byteLength, first.byteLength);
    assert.ok(payload instanceof Uint8Array);
    assert.equal(spatial.readChunkPayload(first.chunkId), payload);
});

test('does not let a transport partition change sceneVersion or spatial chunk content identity', () => {
    const packed = snapshot();
    const first = buildSpatialSceneSnapshot(packed, {
        targetSplatId: 'editor-splat:42',
        chunkByteLength: 96
    });
    const second = buildSpatialSceneSnapshot(packed, {
        targetSplatId: 'editor-splat:42',
        chunkByteLength: 160
    });

    assert.equal(first.manifest.sceneVersion, second.manifest.sceneVersion);
    assert.equal(first.manifest.contentDigest, second.manifest.contentDigest);
    assert.notEqual(
        first.manifest.chunks.length,
        second.manifest.chunks.length
    );
});
