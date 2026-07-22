const assert = require('node:assert/strict');
const test = require('node:test');

const {
    buildPackedSceneSnapshot
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    BinarySceneSnapshotRegistrar
} = require('../.test-dist/src/scene-snapshot-registration.js');

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
        stableIds: new Uint32Array([7, 8]),
        means: new Float32Array([0, 0, 0, 1, 1, 1]),
        rotationsXyzw: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1]),
        logScales: new Float32Array(6),
        logitOpacities: new Float32Array(2),
        dc: new Float32Array(6),
        sh: new Float32Array(),
        shFloatCountPerGaussian: 0
    });

test('replays only missing raw chunks and commits one bound snapshot atomically', async () => {
    const calls = [];
    const currentSnapshot = snapshot();
    const registrar = new BinarySceneSnapshotRegistrar({
        begin: async manifest => {
            calls.push(['begin', manifest]);
            return {
                status: 'staged',
                uploadId: 'upload-1',
                missingChunkIndices: [1, 0]
            };
        },
        uploadChunk: async (uploadId, index, bytes, digest) => {
            calls.push(['chunk', uploadId, index, bytes, digest]);
        },
        commit: async uploadId => {
            calls.push(['commit', uploadId]);
            return {
                status: 'committed',
                sceneId: 'editor-splat:42',
                sceneVersion: currentSnapshot.sceneVersion,
                contentDigest: currentSnapshot.contentDigest
            };
        },
        abort: async uploadId => calls.push(['abort', uploadId])
    });

    const result = await registrar.register(currentSnapshot, {
        chunkByteLength: 16
    });

    assert.deepEqual(result, {
        status: 'committed',
        sceneId: 'editor-splat:42',
        sceneVersion: currentSnapshot.sceneVersion,
        contentDigest: currentSnapshot.contentDigest
    });
    assert.equal(calls[0][0], 'begin');
    assert.deepEqual(
        calls.filter(call => call[0] === 'chunk').map(call => call[2]),
        [1, 0]
    );
    assert.ok(
        calls
            .filter(call => call[0] === 'chunk')
            .every(call => call[3] instanceof Uint8Array)
    );
    assert.deepEqual(calls.at(-1), ['commit', 'upload-1']);
});

test('replays a lost commit acknowledgement without abandoning the immutable upload', async () => {
    const currentSnapshot = snapshot();
    let commitCalls = 0;
    let abortCalls = 0;
    const registrar = new BinarySceneSnapshotRegistrar({
        begin: async () => ({
            status: 'staged',
            uploadId: 'upload-commit-retry',
            missingChunkIndices: [0]
        }),
        uploadChunk: async () => {},
        commit: async () => {
            commitCalls += 1;
            if (commitCalls === 1) {
                throw new Error('the commit response was lost');
            }
            return {
                status: 'alreadyCommitted',
                sceneId: currentSnapshot.sceneId,
                sceneVersion: currentSnapshot.sceneVersion,
                contentDigest: currentSnapshot.contentDigest
            };
        },
        abort: async () => {
            abortCalls += 1;
        }
    });

    const result = await registrar.register(currentSnapshot, {
        chunkByteLength: currentSnapshot.payloadByteLength
    });

    assert.equal(result.status, 'alreadyCommitted');
    assert.equal(commitCalls, 2);
    assert.equal(abortCalls, 0);
});
