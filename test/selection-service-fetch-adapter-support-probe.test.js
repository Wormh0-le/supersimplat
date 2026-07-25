const assert = require('node:assert/strict');
const test = require('node:test');

const {
    FetchSelectionServiceAdapter
} = require('../.test-dist/src/selection-service-fetch-adapter.js');
const {
    buildPackedSceneSnapshot,
    sha256Digest
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    buildSpatialSceneSnapshot
} = require('../.test-dist/src/spatial-scene-snapshot.js');
const {
    aiSelectSupportProbePolicyVersion
} = require('../.test-dist/src/ai-select/support-probe.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');

const cameraBinding = {
    revision: 0,
    cameraToWorld: [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1],
    projection: {
        model: 'pinhole',
        fx: 100,
        fy: 100,
        cx: 32,
        cy: 24,
        width: 64,
        height: 48,
        near: 0.1,
        far: 100
    },
    conventionVersion: 'opencv-camera-to-world/v1'
};

const snapshot = buildPackedSceneSnapshot({
    sceneId: 'scene-1',
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

const maskArtifact = (() => {
    const bytes = new Uint8Array(Math.ceil((64 * 48) / 8));
    bytes[40] = 0b1100;
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width: 64,
        height: 48,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    });
})();

const probeRequest = {
    requestBinding: {
        targetContextId: 'ai-target-context-1',
        contextRevision: 0,
        dependencyToken: {
            splatId: 'scene-1',
            renderStateToken: 'render-v1',
            geometryToken: 'geometry-v1',
            gaussianIdentityToken: 'gaussians-v1',
            worldTransformToken: 'transform-v1'
        }
    },
    target: { splatId: 'scene-1' },
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    viewId: 'anchor-view',
    supportProbeAttemptId: 'support-probe-attempt-1',
    cameraBinding,
    rgbDigest: `sha256:${'a'.repeat(64)}`,
    stableMask: maskArtifact,
    supportProbePolicyVersion: aiSelectSupportProbePolicyVersion
};

const probeResponse = (request, overrides = {}) => ({
    status: 'complete',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    supportProbeAttemptId: request.supportProbeAttemptId,
    viewId: 'anchor-view',
    cameraBinding: request.cameraBinding,
    rgbDigest: request.rgbDigest,
    stableMaskDigest: request.stableMask.digest,
    supportProbePolicyVersion: request.supportProbePolicyVersion,
    support: { computable: true, observedGaussianCount: 12 },
    ...overrides
});

const probeCacheMiss = (request) => ({
    status: 'sceneCacheMiss',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    supportProbeAttemptId: request.supportProbeAttemptId,
    viewId: 'anchor-view',
    cameraBinding: request.cameraBinding
});

const stagedBinaryRegistrationReplies = (packed, uploadId = 'upload-1') => [
    { status: 'staged', uploadId, missingChunkIndices: [0] },
    { status: 'stored', uploadId, index: 0 },
    {
        status: 'committed',
        sceneId: packed.sceneId,
        sceneVersion: packed.sceneVersion,
        contentDigest: packed.contentDigest
    }
];

const responseBody = (body) =>
    typeof body === 'string' ? JSON.parse(body) : (body ?? null);

const createAdapter = (replies, options = {}) => {
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        ...(options.spatial === true
            ? { supportsCameraAwareSpatialWorkingSet: () => true }
            : {}),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            const reply = replies.shift();
            return new Response(JSON.stringify(reply), { status: 200 });
        }
    });
    return { adapter, calls };
};

test('registers the Scene Snapshot then probes Anchor support through the Companion', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        probeResponse(probeRequest)
    ]);

    const response = await adapter.probeAnchorSupport(probeRequest);

    assert.deepEqual(response, probeResponse(probeRequest));
    assert.equal(calls.length, 4);
    assert.match(calls[3].url, /\/ai-select\/anchor-support-probes$/);
    assert.equal(calls[3].init.method, 'POST');
    const body = calls[3].body;
    assert.deepEqual(body.requestBinding, probeRequest.requestBinding);
    assert.equal(body.supportProbeAttemptId, 'support-probe-attempt-1');
    assert.deepEqual(body.cameraBinding, cameraBinding);
    assert.equal(body.rgbDigest, probeRequest.rgbDigest);
    assert.deepEqual(body.stableMask, probeRequest.stableMask);
    assert.equal(
        body.supportProbePolicyVersion,
        aiSelectSupportProbePolicyVersion
    );
    // The Scene Snapshot payload and spatial transport stay off the wire.
    assert.equal(body.snapshot, undefined);
    assert.equal(body.sceneTransport, undefined);
    // The probe never requests Contributor or Evidence products.
    assert.equal(body.referenceContributor, undefined);
    assert.equal(body.evidence, undefined);
});

test('a Scene Snapshot cache miss re-registers once and retries the probe', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        probeCacheMiss(probeRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        probeResponse(probeRequest)
    ]);

    const response = await adapter.probeAnchorSupport(probeRequest);

    assert.deepEqual(response, probeResponse(probeRequest));
    const probeCalls = calls.filter((call) =>
        /anchor-support-probes/.test(call.url)
    );
    assert.equal(probeCalls.length, 2);
});

test('a repeated cache miss after re-registration fails closed', async () => {
    const { adapter } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        probeCacheMiss(probeRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        probeCacheMiss(probeRequest)
    ]);

    await assert.rejects(
        adapter.probeAnchorSupport(probeRequest),
        /repeated an Anchor Scene Snapshot cache miss/
    );
});

test('a stale or mismatched probe response fails closed', async () => {
    const { adapter } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        probeResponse(probeRequest, { supportProbeAttemptId: 'forged' })
    ]);
    await assert.rejects(
        adapter.probeAnchorSupport(probeRequest),
        /incomplete or stale Anchor support probe/
    );

    const ownership = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        probeResponse(probeRequest, {
            support: {
                computable: true,
                observedGaussianCount: 2,
                selectedGaussianIds: [3]
            }
        })
    ]);
    await assert.rejects(
        ownership.adapter.probeAnchorSupport(probeRequest),
        /incomplete or stale Anchor support probe/
    );
});

test('an incomplete probe request is rejected before any transport call', async () => {
    const { adapter, calls } = createAdapter([]);
    await assert.rejects(
        adapter.probeAnchorSupport({ ...probeRequest, rgbDigest: 'nope' }),
        /complete bound Anchor support probe request/
    );
    assert.equal(calls.length, 0);
});

test('the spatial path uploads missing working-set chunks and retries', async () => {
    const spatialSnapshot = buildSpatialSceneSnapshot(snapshot, {
        targetSplatId: probeRequest.target.splatId
    });
    const [chunk] = spatialSnapshot.manifest.chunks;
    const { adapter, calls } = createAdapter(
        [
            {
                status: 'registered',
                registrationId: 'spatial-registration-1',
                sceneId: snapshot.sceneId,
                sceneVersion: snapshot.sceneVersion,
                contentDigest: snapshot.contentDigest
            },
            {
                ...probeCacheMiss(probeRequest),
                status: 'sceneChunkMiss',
                workingSetToken: `sha256:${'c'.repeat(64)}`,
                missingChunkIds: [chunk.chunkId]
            },
            {
                status: 'staged',
                uploadId: 'spatial-upload-1',
                missingChunkIds: [chunk.chunkId]
            },
            {
                status: 'alreadyStored',
                uploadId: 'spatial-upload-1',
                chunkId: chunk.chunkId
            },
            {
                status: 'committed',
                sceneId: snapshot.sceneId,
                sceneVersion: snapshot.sceneVersion,
                committedChunkIds: [chunk.chunkId]
            },
            probeResponse(probeRequest)
        ],
        { spatial: true }
    );

    const response = await adapter.probeAnchorSupport(probeRequest);

    assert.deepEqual(response, probeResponse(probeRequest));
    const probeCalls = calls.filter((call) =>
        /anchor-support-probes/.test(call.url)
    );
    assert.equal(probeCalls.length, 2);
    assert.equal(probeCalls[0].body.sceneTransport, 'spatial-v1');
    assert.match(calls[0].url, /\/spatial-scene-manifests\/v1$/);
    assert.ok(
        calls.some((call) =>
            /\/spatial-scene-chunk-uploads\/v1\/spatial-upload-1\/chunks\//.test(
                call.url
            )
        )
    );
});
