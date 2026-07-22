const assert = require('node:assert/strict');
const test = require('node:test');

const {
    MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES,
    buildPackedSceneSnapshot,
    createBinarySceneSnapshotManifest
} = require('../.test-dist/src/scene-snapshot-binary.js');

const input = () => ({
    sceneId: 'editor-splat:42',
    coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
    stableIdSchema: 'uint32',
    appearancePolicy: 'effective-editor-dc-sh-bands-1',
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1',
        backgroundRgba: [0.25, 0.5, 0.75, 1],
        alphaMode: 'opaque-background',
        shBands: 1,
        rasterizer: 'playcanvas-gsplat-classic'
    },
    stableIds: new Uint32Array([17, 42]),
    means: new Float32Array([1, 2, 3, 4, 5, 6]),
    rotationsXyzw: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1]),
    logScales: new Float32Array([0, 0, 0, 1, 1, 1]),
    logitOpacities: new Float32Array([0, 1]),
    dc: new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
    sh: new Float32Array([
        0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.11, 0.12, 0.13,
        0.14, 0.15, 0.16, 0.17, 0.18, 0.19
    ]),
    shFloatCountPerGaussian: 9
});

test('packs an effective SceneSnapshot as SoA bytes without Gaussian records', () => {
    const snapshot = buildPackedSceneSnapshot(input());

    assert.equal(snapshot.gaussianCount, 2);
    assert.equal(snapshot.contentDigest, snapshot.sceneVersion);
    assert.ok(snapshot.stableIds instanceof Uint32Array);
    assert.ok(snapshot.means instanceof Float32Array);
    assert.equal(Object.hasOwn(snapshot, 'gaussians'), false);
    assert.deepEqual(
        Array.from(snapshot.readPayloadRange(0, 8)),
        [17, 0, 0, 0, 42, 0, 0, 0]
    );
});

test('keeps the Snapshot Content Digest independent of bounded transport chunking', () => {
    const snapshot = buildPackedSceneSnapshot(input());
    const shortChunks = createBinarySceneSnapshotManifest(snapshot, 16);
    const longChunks = createBinarySceneSnapshotManifest(snapshot, 64);

    assert.equal(shortChunks.contentDigest, longChunks.contentDigest);
    assert.equal(shortChunks.sceneVersion, longChunks.sceneVersion);
    assert.notDeepEqual(
        shortChunks.transfer.chunks,
        longChunks.transfer.chunks
    );
    assert.ok(
        shortChunks.transfer.chunks.every(chunk => chunk.byteLength <= 16)
    );
    assert.throws(
        () =>
            createBinarySceneSnapshotManifest(
                snapshot,
                MAX_BINARY_SCENE_SNAPSHOT_CHUNK_BYTES + 1
            ),
        /chunk/i
    );
});

test('matches the shared Binary SceneSnapshot v1 digest test vector', () => {
    const snapshot = buildPackedSceneSnapshot({
        sceneId: 'digest-test-scene',
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
        stableIds: new Uint32Array([7]),
        means: new Float32Array([1, 2, 3]),
        rotationsXyzw: new Float32Array([0, 0, 0, 1]),
        logScales: new Float32Array([0, 0, 0]),
        logitOpacities: new Float32Array([0]),
        dc: new Float32Array([0, 0, 0]),
        sh: new Float32Array(),
        shFloatCountPerGaussian: 0
    });

    assert.equal(
        snapshot.contentDigest,
        'sha256:d2e86ef6efa8979eed111a6d3ecea9419e09bb780b69ab769f279dd768be925e'
    );
});
