const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    FetchSelectionServiceAdapter
} = require('../.test-dist/src/selection-service-fetch-adapter.js');
const {
    aiSelectGeneratedViewMaskPolicyVersion,
    aiSelectGeneratedViewPlannerVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    buildPackedSceneSnapshot,
    sha256Digest
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    buildSpatialSceneSnapshot
} = require('../.test-dist/src/spatial-scene-snapshot.js');

const anchorCameraBinding = {
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

const generatedCameraBinding = {
    ...anchorCameraBinding,
    revision: 100,
    cameraToWorld: [
        0.7071067811865476, 0, -0.7071067811865476, 5, 0, 1, 0, 0,
        0.7071067811865476, 0, 0.7071067811865476, 5, 0, 0, 0, 1
    ]
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

const requestBinding = {
    targetContextId: 'ai-target-context-1',
    contextRevision: 0,
    dependencyToken: {
        splatId: 'scene-1',
        renderStateToken: 'render-v1',
        geometryToken: 'geometry-v1',
        gaussianIdentityToken: 'gaussians-v1',
        worldTransformToken: 'transform-v1'
    }
};

const anchorRgbDigest = `sha256:${'a'.repeat(64)}`;

const planRequest = {
    requestBinding,
    target: { splatId: 'scene-1' },
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    planAttemptId: 'generated-view-plan-attempt-1',
    anchorCameraBinding,
    anchorRgbDigest,
    anchorStableMask: maskArtifact,
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion
};

const planResponse = (request, overrides = {}) => ({
    status: 'complete',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    planAttemptId: request.planAttemptId,
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion,
    views: [
        { viewId: 'generated-00', cameraBinding: generatedCameraBinding },
        {
            viewId: 'generated-01',
            cameraBinding: { ...generatedCameraBinding, revision: 101 }
        }
    ],
    ...overrides
});

const planCacheMiss = (request) => ({
    status: 'sceneCacheMiss',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    planAttemptId: request.planAttemptId,
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion
});

const renderRequest = {
    requestBinding,
    target: { splatId: 'scene-1' },
    snapshot,
    cameraBinding: generatedCameraBinding,
    viewId: 'generated-00',
    renderAttemptId: 'generated-view-render-attempt-1'
};

const pngCrc32 = (bytes) => {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
};

const pngChunk = (type, data) => {
    const typeBytes = Buffer.from(type, 'ascii');
    const payload = Buffer.concat([typeBytes, data]);
    const length = Buffer.alloc(4);
    const checksum = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    checksum.writeUInt32BE(pngCrc32(payload));
    return Buffer.concat([length, payload, checksum]);
};

const pngBytesFor = (width, height) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    return Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]);
};

const pngFor = (width, height) => {
    const bytes = pngBytesFor(width, height);
    return {
        pngBase64: bytes.toString('base64'),
        digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`
    };
};

const renderResponse = (request, overrides = {}) => ({
    status: 'complete',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    renderAttemptId: request.renderAttemptId,
    viewId: request.viewId,
    cameraBinding: request.cameraBinding,
    rgb: {
        ...pngFor(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height
        ),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat',
    ...overrides
});

const maskRequest = {
    requestBinding,
    target: { splatId: 'scene-1' },
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    viewId: 'generated-00',
    viewCameraBinding: generatedCameraBinding,
    maskAttemptId: 'generated-view-mask-attempt-1',
    rgb: {
        ...pngFor(64, 48),
        width: 64,
        height: 48
    },
    anchor: {
        cameraBinding: anchorCameraBinding,
        rgbDigest: anchorRgbDigest,
        stableMask: maskArtifact
    },
    modelManifestDigest: 'sha256:model-v1'
};

const maskResponse = (request, overrides = {}) => ({
    status: 'complete',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    viewId: request.viewId,
    maskAttemptId: request.maskAttemptId,
    rgbDigest: request.rgb.digest,
    anchorRgbDigest: request.anchor.rgbDigest,
    mask: maskArtifact,
    maskSource: 'propagated',
    maskPropagation: {
        policyVersion: aiSelectGeneratedViewMaskPolicyVersion,
        projectedSupportCount: 7,
        promptCount: 3
    },
    assessment: {
        status: 'good',
        reasons: [],
        actionableReasons: [],
        policyVersion: 'local-view-assessment/v2',
        inputIdentity: {
            rgbDigest: request.rgb.digest,
            stableMaskDigest: maskArtifact.digest,
            assessmentPolicyVersion: 'local-view-assessment/v2'
        },
        diagnostics: {
            framePixels: 3072,
            foregroundPixels: 24,
            boundaryPixels: 0,
            boundaryContactRatio: 0,
            connectedComponents: 1,
            largestComponentRatio: 1,
            promptPointCount: 3,
            promptViolationCount: 0,
            boxSpillPixels: null,
            boxSpillRatio: null
        }
    },
    modelManifestDigest: request.modelManifestDigest,
    ...overrides
});

const maskCacheMiss = (request) => ({
    status: 'sceneCacheMiss',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    viewId: request.viewId,
    maskAttemptId: request.maskAttemptId
});

const renderCacheMiss = (request) => ({
    status: 'sceneCacheMiss',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    renderAttemptId: request.renderAttemptId,
    viewId: request.viewId,
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

test('plans Generated Views through the Companion with the confirmed Anchor binding', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        planResponse(planRequest)
    ]);

    const response = await adapter.planGeneratedViews(planRequest);

    assert.deepEqual(response, planResponse(planRequest));
    const planCall = calls.at(-1);
    assert.match(planCall.url, /\/ai-select\/generated-view-plans$/);
    assert.equal(planCall.init.method, 'POST');
    const body = planCall.body;
    assert.deepEqual(body.requestBinding, planRequest.requestBinding);
    assert.equal(body.planAttemptId, planRequest.planAttemptId);
    assert.deepEqual(body.anchorCameraBinding, anchorCameraBinding);
    assert.equal(body.anchorRgbDigest, anchorRgbDigest);
    assert.deepEqual(body.anchorStableMask, maskArtifact);
    assert.equal(
        body.plannerPolicyVersion,
        aiSelectGeneratedViewPlannerVersion
    );
    assert.equal(
        body.renderConfigVersion,
        snapshot.renderConfiguration.version
    );
    // The Scene Snapshot payload stays off the wire.
    assert.equal(body.snapshot, undefined);
    assert.equal(body.sceneTransport, undefined);
});

test('a plan cache miss re-registers once and retries; a repeated miss fails closed', async () => {
    const recovered = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        planCacheMiss(planRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        planResponse(planRequest)
    ]);
    const response = await recovered.adapter.planGeneratedViews(planRequest);
    assert.deepEqual(response, planResponse(planRequest));
    assert.equal(
        recovered.calls.filter((call) => /generated-view-plans/.test(call.url))
            .length,
        2
    );

    const repeated = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        planCacheMiss(planRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        planCacheMiss(planRequest)
    ]);
    await assert.rejects(
        repeated.adapter.planGeneratedViews(planRequest),
        /repeated a Generated View plan Scene Snapshot cache miss/
    );
});

test('a stale or invalid plan response fails closed', async () => {
    const stale = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        planResponse(planRequest, { planAttemptId: 'forged' })
    ]);
    await assert.rejects(
        stale.adapter.planGeneratedViews(planRequest),
        /incomplete or stale Generated View plan/
    );

    const empty = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        planResponse(planRequest, { views: [] })
    ]);
    await assert.rejects(
        empty.adapter.planGeneratedViews(planRequest),
        /incomplete or stale Generated View plan/
    );
});

test('an incomplete plan request is rejected before any transport call', async () => {
    const { adapter, calls } = createAdapter([]);
    await assert.rejects(
        adapter.planGeneratedViews({
            ...planRequest,
            anchorRgbDigest: 'nope'
        }),
        /complete bound Generated View plan request/
    );
    assert.equal(calls.length, 0);
});

test('renders a Generated View through the Companion and verifies the RGB digest', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        renderResponse(renderRequest)
    ]);

    const response = await adapter.renderView(renderRequest);

    assert.deepEqual(response, renderResponse(renderRequest));
    const renderCall = calls.at(-1);
    assert.match(renderCall.url, /\/ai-select\/view-renders$/);
    assert.equal(renderCall.init.method, 'POST');
    assert.equal(renderCall.body.viewId, 'generated-00');
    assert.deepEqual(renderCall.body.cameraBinding, generatedCameraBinding);
    assert.equal(
        renderCall.body.renderAttemptId,
        'generated-view-render-attempt-1'
    );
    // Generated View renders never request the debug reference Contributor.
    assert.equal(renderCall.body.referenceContributor, undefined);
});

test('a Generated View render cache miss re-registers once and retries', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        renderCacheMiss(renderRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        renderResponse(renderRequest)
    ]);

    const response = await adapter.renderView(renderRequest);
    assert.deepEqual(response, renderResponse(renderRequest));
    assert.equal(
        calls.filter((call) => /view-renders/.test(call.url)).length,
        2
    );
});

test('a stale Generated View render binding fails closed', async () => {
    const { adapter } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        renderResponse(renderRequest, { viewId: 'generated-99' })
    ]);
    await assert.rejects(
        adapter.renderView(renderRequest),
        /incomplete or stale Generated View render/
    );
});

test('an Anchor view id is rejected on the Generated View render route', async () => {
    const { adapter, calls } = createAdapter([]);
    await assert.rejects(
        adapter.renderView({ ...renderRequest, viewId: 'anchor-view' }),
        /complete bound Generated View render request/
    );
    assert.equal(calls.length, 0);
});

test('produces an automatic Generated View Mask bound to the View and Anchor identity', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        maskResponse(maskRequest)
    ]);

    const response = await adapter.produceGeneratedViewMask(maskRequest);

    assert.deepEqual(response, maskResponse(maskRequest));
    const maskCall = calls.at(-1);
    assert.match(maskCall.url, /\/ai-select\/generated-view-masks$/);
    const body = maskCall.body;
    assert.equal(body.viewId, 'generated-00');
    assert.deepEqual(body.viewCameraBinding, generatedCameraBinding);
    assert.deepEqual(body.anchor, maskRequest.anchor);
    assert.equal(body.maskAttemptId, maskRequest.maskAttemptId);
    assert.equal(body.modelManifestDigest, 'sha256:model-v1');
    assert.equal(body.snapshot, undefined);
});

test('a Generated View Mask cache miss re-registers once and retries', async () => {
    const { adapter, calls } = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        maskCacheMiss(maskRequest),
        ...stagedBinaryRegistrationReplies(snapshot, 'upload-2'),
        maskResponse(maskRequest)
    ]);

    const response = await adapter.produceGeneratedViewMask(maskRequest);
    assert.deepEqual(response, maskResponse(maskRequest));
    assert.equal(
        calls.filter((call) => /generated-view-masks/.test(call.url)).length,
        2
    );
});

test('a stale or wrong-source Generated View Mask response fails closed', async () => {
    const stale = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        maskResponse(maskRequest, {
            anchorRgbDigest: `sha256:${'f'.repeat(64)}`
        })
    ]);
    await assert.rejects(
        stale.adapter.produceGeneratedViewMask(maskRequest),
        /incomplete or stale Generated View Mask/
    );

    const wrongSource = createAdapter([
        ...stagedBinaryRegistrationReplies(snapshot),
        maskResponse(maskRequest, { maskSource: 'single-frame-sam' })
    ]);
    await assert.rejects(
        wrongSource.adapter.produceGeneratedViewMask(maskRequest),
        /incomplete or stale Generated View Mask/
    );
});

test('the spatial path plans and renders Generated Views with chunk-miss recovery', async () => {
    const spatialSnapshot = buildSpatialSceneSnapshot(snapshot, {
        targetSplatId: planRequest.target.splatId
    });
    const [chunk] = spatialSnapshot.manifest.chunks;
    const spatialRegistration = {
        status: 'registered',
        registrationId: 'spatial-registration-1',
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
        contentDigest: snapshot.contentDigest
    };
    const { adapter, calls } = createAdapter(
        [
            spatialRegistration,
            {
                ...planCacheMiss(planRequest),
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
            planResponse(planRequest),
            renderResponse(renderRequest)
        ],
        { spatial: true }
    );

    const plan = await adapter.planGeneratedViews(planRequest);
    assert.deepEqual(plan, planResponse(planRequest));
    const planCalls = calls.filter((call) =>
        /generated-view-plans/.test(call.url)
    );
    assert.equal(planCalls.length, 2);
    assert.equal(planCalls[0].body.sceneTransport, 'spatial-v1');

    const render = await adapter.renderView(renderRequest);
    assert.deepEqual(render, renderResponse(renderRequest));
    const renderCalls = calls.filter((call) => /view-renders/.test(call.url));
    assert.equal(renderCalls.length, 1);
    assert.equal(renderCalls[0].body.sceneTransport, 'spatial-v1');
});
