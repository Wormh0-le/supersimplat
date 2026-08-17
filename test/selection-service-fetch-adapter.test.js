const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    FetchSelectionServiceAdapter
} = require('../.test-dist/src/selection-service-fetch-adapter.js');
const {
    buildPackedSceneSnapshot
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    buildSpatialSceneSnapshot
} = require('../.test-dist/src/spatial-scene-snapshot.js');
const {
    createEmptyPromptState,
    revisePromptState
} = require('../.test-dist/src/ai-select/prompt-state.js');
const {
    admitGaussianEvidence,
    createEvidenceWorkingSet,
    createGaussianEvidenceArtifact
} = require('../.test-dist/src/ai-select/gaussian-evidence-contract.js');
const {
    cameraBindingDigest
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    anchorMaskRankingPolicyVersion,
    autoMaskProposalSetDigest
} = require('../.test-dist/src/ai-select/mask-proposal.js');
const {
    aiSelectViewAssessmentPolicyVersion
} = require('../.test-dist/src/ai-select/view-assessment.js');
const {
    previousPredictionLogitsRefDigest
} = require('../.test-dist/src/ai-select/previous-logits-ref.js');

const snapshot = {
    protocolVersion: '1',
    sceneId: 'scene-1',
    sceneVersion: 'snapshot-v1',
    gaussianCount: 3,
    coordinateConvention: 'right-handed/world',
    attributeSchema: 'gaussian-v1',
    stableIdSchema: 'uint32',
    appearancePolicy: 'dc-sh-v1',
    renderConfiguration: {
        version: 'effective-rgb-v1',
        backgroundRgba: [0, 0, 0, 1],
        alphaMode: 'opaque-background',
        shBands: 3,
        rasterizer: 'playcanvas-gsplat-classic'
    },
    gaussians: [3, 7, 9].map((stableId) => ({
        stableId,
        mean: [stableId, 0, 0],
        rotation: [0, 0, 0, 1],
        logScale: [0, 0, 0],
        logitOpacity: 0,
        dc: [0, 0, 0],
        sh: []
    }))
};

const start = {
    target: { targetSplatId: 'splat-1' },
    prompt: {
        promptId: 'prompt-1',
        viewId: 'anchor-view',
        frameDigest: 'sha256:anchor-frame-v1',
        frameWidth: 64,
        frameHeight: 48,
        xPx: 10,
        yPx: 20,
        polarity: 'include'
    },
    snapshot,
    requestContext: {
        deterministicSeed: 'seed-1',
        frameSetVersion: 'anchor:anchor-view',
        frameSet: {
            frameSetId: 'frames-1',
            frameSetVersion: 'anchor:anchor-view',
            orderedViews: [
                {
                    viewId: 'anchor-view',
                    frameDigest: 'sha256:anchor-frame-v1',
                    width: 64,
                    height: 48
                }
            ]
        },
        modelManifestDigest: 'sha256:model-v1'
    }
};

const previewRequest = (sessionId = 'session-1', requestId = 'request-1') => ({
    sessionId,
    requestId,
    target: start.target,
    targetSplatId: start.target.targetSplatId,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    operation: 'New',
    correctionRound: 0,
    deterministicSeed: start.requestContext.deterministicSeed,
    promptLogRevision: 1,
    frameSetVersion: start.requestContext.frameSetVersion,
    frameSet: start.requestContext.frameSet,
    renderConfigVersion: snapshot.renderConfiguration.version,
    modelManifestDigest: start.requestContext.modelManifestDigest,
    promptLog: [{ operation: 'New', prompt: start.prompt }],
    snapshot
});

const previewBindings = (requestId) => ({
    requestId,
    sessionId: 'session-1',
    targetSplatId: start.target.targetSplatId,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    operation: 'New',
    correctionRound: 0,
    deterministicSeed: start.requestContext.deterministicSeed,
    promptLogRevision: 1,
    frameSetVersion: start.requestContext.frameSetVersion,
    renderConfigVersion: snapshot.renderConfiguration.version,
    modelManifestDigest: start.requestContext.modelManifestDigest
});

const frameSetForBindings = (bindings) => ({
    ...start.requestContext.frameSet,
    frameSetVersion: bindings.frameSetVersion
});

const coverageReport = (
    bindings,
    frameSet = frameSetForBindings(bindings)
) => ({
    frameSetVersion: bindings.frameSetVersion,
    renderConfigVersion: bindings.renderConfigVersion,
    attemptedViews: frameSet.orderedViews.length,
    acceptedViews: frameSet.orderedViews.length,
    rejectedViewCount: 0,
    status: 'insufficient_coverage'
});

const maskSet = (bindings, frameSet = frameSetForBindings(bindings)) => ({
    status: 'complete',
    requestId: bindings.requestId,
    sessionId: bindings.sessionId,
    promptLogRevision: bindings.promptLogRevision,
    frameSetVersion: bindings.frameSetVersion,
    modelManifestDigest: bindings.modelManifestDigest,
    threshold: 0.5,
    tracks: [
        {
            trackId: 'primary',
            role: 'include',
            frames: frameSet.orderedViews.map((view) => ({
                viewId: view.viewId,
                status: 'accepted',
                binaryMask: {
                    encoding: 'sparse-points-v1',
                    width: view.width,
                    height: view.height,
                    foregroundPixels: [[0, 0]]
                }
            }))
        }
    ]
});

const evidenceSnapshot = (
    bindings,
    frameSet = frameSetForBindings(bindings)
) => ({
    ...bindings,
    frameSetId: frameSet.frameSetId,
    policy: {
        id: 'selection-evidence-policy/v1',
        renderConfigVersion: bindings.renderConfigVersion,
        contributorSemantics: 'alpha-times-transmittance/v1',
        evidenceScale: 'contributor-mass/v1',
        betaPrior: { alpha: 1, beta: 1 },
        minimumEffectiveObservation: 0.1,
        selectedPosteriorThreshold: 0.8,
        rejectedPosteriorThreshold: 0.2
    },
    records: [
        {
            stableId: 3,
            positiveEvidence: 3,
            negativeEvidence: 0,
            effectiveObservation: 3,
            posterior: 0.8,
            uncertaintyReason: null,
            classification: 'selected'
        },
        {
            stableId: 7,
            positiveEvidence: 0,
            negativeEvidence: 0,
            effectiveObservation: 0,
            posterior: 0.5,
            uncertaintyReason: 'unobserved',
            classification: 'uncertain'
        },
        {
            stableId: 9,
            positiveEvidence: 0,
            negativeEvidence: 3,
            effectiveObservation: 3,
            posterior: 0.2,
            uncertaintyReason: null,
            classification: 'rejected'
        }
    ]
});

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

const anchorSnapshot = buildPackedSceneSnapshot({
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
    shFloatCountPerGaussian: 0,
    authoritativeRenderScope: {
        policyId: 'visible-editor-splats-conservative/v1',
        targetSplatId: 'scene-1',
        identityDigest: `sha256:${'e'.repeat(64)}`,
        entries: [
            {
                splatId: 'scene-1',
                role: 'target',
                sourceContentDigest: `sha256:${'f'.repeat(64)}`,
                rowOffset: 0,
                rowCount: 1,
                renderIdStart: 3
            }
        ]
    }
});

const anchorRequest = {
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
    snapshot: anchorSnapshot,
    cameraBinding: anchorCameraBinding,
    renderAttemptId: 'anchor-render-attempt-1'
};

const stagedBinaryRegistrationReplies = (packed, uploadId = 'upload-1') => [
    {
        status: 'staged',
        uploadId,
        missingChunkIndices: [0]
    },
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

const anchorPngBytes = (width, height, imageData = null) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    return Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', imageData ?? deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]);
};

const anchorPng = (width, height) => {
    const bytes = anchorPngBytes(width, height);
    return {
        pngBase64: bytes.toString('base64'),
        digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`
    };
};

const anchorResponse = (request) => ({
    status: 'complete',
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    renderAttemptId: request.renderAttemptId,
    viewId: 'anchor-view',
    cameraBinding: request.cameraBinding,
    rgb: {
        ...anchorPng(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height
        ),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
    rendererId: 'gsplat',
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    runtimeBuildId:
        'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4',
    renderWorkingSetToken: request.snapshot.contentDigest,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds,
        Number
    ).sort((left, right) => left - right)
});

test('registers the editor-owned Scene Snapshot then renders a bound authoritative Anchor through the Companion', async () => {
    const calls = [];
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot),
        anchorResponse(anchorRequest)
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    const response = await adapter.renderAnchor(anchorRequest);

    assert.deepEqual(response, anchorResponse(anchorRequest));
    assert.equal(calls.length, 4);
    assert.match(calls[0].url, /\/scene-snapshot-uploads\/v1$/);
    assert.equal(calls[0].init.method, 'POST');
    assert.equal(calls[0].body.content.gaussianCount, 1);
    assert.equal(calls[0].body.content.gaussians, undefined);
    assert.match(
        calls[1].url,
        /\/scene-snapshot-uploads\/v1\/upload-1\/chunks\/0$/
    );
    assert.equal(calls[1].init.method, 'PUT');
    assert.ok(calls[1].init.body instanceof ArrayBuffer);
    assert.equal(
        calls[1].init.headers['Content-Type'],
        'application/octet-stream'
    );
    assert.match(
        calls[2].url,
        /\/scene-snapshot-uploads\/v1\/upload-1\/commit$/
    );
    assert.match(calls[3].url, /\/ai-select\/anchor-renders$/);
    assert.equal(calls[3].init.method, 'POST');
    assert.deepEqual(
        calls[3].body.requestBinding,
        anchorRequest.requestBinding
    );
    assert.deepEqual(calls[3].body.cameraBinding, anchorRequest.cameraBinding);
});

test('rejects packed RGB whose Render Working Set token is not the packed snapshot', async () => {
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot),
        {
            ...anchorResponse(anchorRequest),
            renderWorkingSetToken: `sha256:${'f'.repeat(64)}`
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(JSON.stringify(replies.shift()), { status: 200 })
    });

    await assert.rejects(
        adapter.renderAnchor(anchorRequest),
        /Render Working Set outside the requested transport/
    );
});

test('registers one global spatial manifest, uploads only the missing Anchor chunk, and retries a lost acknowledgement', async () => {
    const spatialSnapshot = buildSpatialSceneSnapshot(anchorSnapshot, {
        targetSplatId: anchorRequest.target.splatId
    });
    const [chunk] = spatialSnapshot.manifest.chunks;
    const calls = [];
    const replies = [
        {
            status: 'registered',
            registrationId: 'spatial-registration-1',
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            contentDigest: anchorSnapshot.contentDigest
        },
        {
            status: 'sceneChunkMiss',
            requestBinding: anchorRequest.requestBinding,
            targetSplatId: anchorRequest.target.splatId,
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            renderConfigVersion: anchorSnapshot.renderConfiguration.version,
            renderAttemptId: anchorRequest.renderAttemptId,
            viewId: 'anchor-view',
            cameraBinding: anchorCameraBinding,
            workingSetToken:
                'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
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
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            committedChunkIds: [chunk.chunkId]
        },
        anchorResponse(anchorRequest),
        { status: 'released' }
    ];
    let lostChunkAcknowledgement = false;
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        supportsCameraAwareSpatialWorkingSet: () => true,
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            if (url.includes('/chunks/') && !lostChunkAcknowledgement) {
                lostChunkAcknowledgement = true;
                throw new Error('lost chunk acknowledgement');
            }
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    const response = await adapter.renderAnchor(anchorRequest);
    await adapter.releaseSceneSnapshot(anchorRequest);
    await adapter.releaseSceneSnapshot(anchorRequest);

    assert.deepEqual(response, anchorResponse(anchorRequest));
    assert.equal(calls.length, 8);
    assert.match(calls[0].url, /\/spatial-scene-manifests\/v1$/);
    assert.equal(calls[0].body.format, 'supersplat-spatial-scene-manifest');
    assert.equal(calls[0].body.chunks.length, 1);
    assert.equal(calls[0].body.chunks[0].payload, undefined);
    assert.match(calls[1].url, /\/ai-select\/anchor-renders$/);
    assert.equal(calls[1].body.sceneTransport, 'spatial-v1');
    assert.deepEqual(
        calls[1].body.requestBinding,
        anchorRequest.requestBinding
    );
    assert.match(calls[2].url, /\/spatial-scene-chunk-uploads\/v1$/);
    assert.deepEqual(calls[2].body.chunkIds, [chunk.chunkId]);
    assert.match(
        calls[3].url,
        /\/spatial-scene-chunk-uploads\/v1\/spatial-upload-1\/chunks\/spatial-00000000$/
    );
    assert.ok(calls[3].init.body instanceof ArrayBuffer);
    assert.equal(
        calls[3].init.headers['X-Spatial-Scene-Chunk-Digest'],
        chunk.chunkDigest
    );
    assert.match(
        calls[4].url,
        /\/spatial-scene-chunk-uploads\/v1\/spatial-upload-1\/chunks\/spatial-00000000$/
    );
    assert.equal(
        calls[4].init.headers['X-Spatial-Scene-Chunk-Digest'],
        chunk.chunkDigest
    );
    assert.match(
        calls[5].url,
        /\/spatial-scene-chunk-uploads\/v1\/spatial-upload-1\/commit$/
    );
    assert.match(calls[6].url, /\/ai-select\/anchor-renders$/);
    assert.equal(calls[6].body.sceneTransport, 'spatial-v1');
    assert.deepEqual(
        calls[6].body.requestBinding,
        anchorRequest.requestBinding
    );
    assert.match(
        calls[7].url,
        /\/spatial-scene-manifests\/v1\/spatial-registration-1$/
    );
    assert.equal(calls[7].init.method, 'DELETE');
    assert.equal(
        calls.some((call) => call.url.includes('/scene-snapshot-uploads/v1')),
        false
    );
});

test('rejects a stale Spatial Scene chunk miss before any raw chunk upload can begin', async () => {
    const calls = [];
    const replies = [
        {
            status: 'registered',
            registrationId: 'spatial-registration-stale',
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            contentDigest: anchorSnapshot.contentDigest
        },
        {
            status: 'sceneChunkMiss',
            requestBinding: {
                ...anchorRequest.requestBinding,
                contextRevision:
                    anchorRequest.requestBinding.contextRevision + 1
            },
            targetSplatId: anchorRequest.target.splatId,
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            renderConfigVersion: anchorSnapshot.renderConfiguration.version,
            renderAttemptId: anchorRequest.renderAttemptId,
            viewId: 'anchor-view',
            cameraBinding: anchorCameraBinding,
            workingSetToken:
                'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
            missingChunkIds: ['spatial-00000000']
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        supportsCameraAwareSpatialWorkingSet: () => true,
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    await assert.rejects(
        adapter.renderAnchor(anchorRequest),
        /stale or invalid Anchor Spatial Scene chunk-miss bindings/i
    );
    assert.equal(calls.length, 2);
    assert.equal(
        calls.some((call) =>
            call.url.includes('/spatial-scene-chunk-uploads/v1')
        ),
        false
    );
});

test('rejects an Anchor target that does not bind the editor-owned Scene Snapshot', async () => {
    const calls = [];
    const mismatchedRequest = {
        ...anchorRequest,
        target: { splatId: 'different-splat' },
        requestBinding: {
            ...anchorRequest.requestBinding,
            dependencyToken: {
                ...anchorRequest.requestBinding.dependencyToken,
                splatId: 'different-splat'
            }
        }
    };
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () => {
            calls.push('fetch');
            throw new Error('request should not be sent');
        }
    });

    await assert.rejects(
        adapter.renderAnchor(mismatchedRequest),
        /complete bound Anchor render request/i
    );
    assert.deepEqual(calls, []);
});

test('re-registers the Scene Snapshot exactly once when an Anchor render reports a cache miss', async () => {
    const calls = [];
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot),
        {
            status: 'sceneCacheMiss',
            requestBinding: anchorRequest.requestBinding,
            targetSplatId: anchorRequest.target.splatId,
            sceneId: anchorSnapshot.sceneId,
            sceneVersion: anchorSnapshot.sceneVersion,
            renderConfigVersion: anchorSnapshot.renderConfiguration.version,
            renderAttemptId: anchorRequest.renderAttemptId,
            viewId: 'anchor-view',
            cameraBinding: anchorCameraBinding
        },
        ...stagedBinaryRegistrationReplies(anchorSnapshot, 'upload-2'),
        anchorResponse(anchorRequest)
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    const response = await adapter.renderAnchor(anchorRequest);

    assert.deepEqual(response, anchorResponse(anchorRequest));
    assert.equal(calls.length, 8);
    assert.equal(calls.filter((call) => call.init.method === 'PUT').length, 2);
    assert.equal(calls.filter((call) => call.init.method === 'POST').length, 6);
});

test('rejects an Anchor PNG whose declared digest does not bind its bytes', async () => {
    const response = anchorResponse(anchorRequest);
    response.rgb.digest =
        'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot),
        response
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(JSON.stringify(replies.shift()), { status: 200 })
    });

    await assert.rejects(
        adapter.renderAnchor(anchorRequest),
        /PNG digest does not match/i
    );
});

test('rejects malformed or dimension-mismatched Anchor PNG bytes even when their digest is valid', async (t) => {
    for (const [name, rgb, message] of [
        [
            'malformed',
            {
                pngBase64: Buffer.from('not a PNG').toString('base64'),
                digest: `sha256:${createHash('sha256').update('not a PNG').digest('hex')}`,
                width: 64,
                height: 48
            },
            /invalid Anchor PNG/i
        ],
        [
            'wrong actual dimensions',
            {
                ...anchorPng(1, 1),
                width: 64,
                height: 48
            },
            /PNG dimensions do not match/i
        ],
        [
            'truncated chunk stream',
            (() => {
                const bytes = anchorPngBytes(64, 48).subarray(0, -12);
                return {
                    pngBase64: bytes.toString('base64'),
                    digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`,
                    width: 64,
                    height: 48
                };
            })(),
            /invalid Anchor PNG/i
        ],
        [
            'corrupted chunk checksum',
            (() => {
                const bytes = anchorPngBytes(64, 48);
                bytes[bytes.length - 1] ^= 0x01;
                return {
                    pngBase64: bytes.toString('base64'),
                    digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`,
                    width: 64,
                    height: 48
                };
            })(),
            /invalid Anchor PNG/i
        ],
        [
            'undecodable IDAT stream',
            (() => {
                const bytes = anchorPngBytes(
                    64,
                    48,
                    Buffer.from([0x78, 0x9c, 0x00])
                );
                return {
                    pngBase64: bytes.toString('base64'),
                    digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`,
                    width: 64,
                    height: 48
                };
            })(),
            /invalid Anchor PNG/i
        ]
    ]) {
        await t.test(name, async () => {
            const response = anchorResponse(anchorRequest);
            response.rgb = rgb;
            const replies = [
                ...stagedBinaryRegistrationReplies(anchorSnapshot),
                response
            ];
            const adapter = new FetchSelectionServiceAdapter({
                getConfiguration: () => ({
                    endpoint: 'https://companion.example:8787',
                    modelManifestDigest: 'sha256:model-v1'
                }),
                fetch: async () =>
                    new Response(JSON.stringify(replies.shift()), {
                        status: 200
                    })
            });

            await assert.rejects(adapter.renderAnchor(anchorRequest), message);
        });
    }
});

test('registers one immutable Scene Snapshot, resends it after a cache miss, and retries the bound preview', async () => {
    const calls = [];
    const replies = [
        {
            status: 'registered',
            frameSetVersion: start.requestContext.frameSetVersion
        },
        { status: 'accepted', sessionId: 'session-1' },
        {
            status: 'registered',
            sceneId: snapshot.sceneId,
            sceneVersion: snapshot.sceneVersion
        },
        {
            status: 'sceneCacheMiss',
            ...previewBindings('request-1')
        },
        {
            status: 'registered',
            sceneId: snapshot.sceneId,
            sceneVersion: snapshot.sceneVersion
        },
        {
            status: 'complete',
            ...previewBindings('request-1'),
            selectedIds: [3],
            uncertainIds: [7],
            rejectedIds: [9],
            frameSet: frameSetForBindings(previewBindings('request-1')),
            maskSet: maskSet(previewBindings('request-1')),
            evidenceSnapshot: evidenceSnapshot(previewBindings('request-1')),
            coverageReport: coverageReport(previewBindings('request-1'))
        },
        {
            status: 'complete',
            ...previewBindings('request-2'),
            selectedIds: [3],
            uncertainIds: [7],
            rejectedIds: [9],
            frameSet: frameSetForBindings(previewBindings('request-2')),
            maskSet: maskSet(previewBindings('request-2')),
            evidenceSnapshot: evidenceSnapshot(previewBindings('request-2')),
            coverageReport: coverageReport(previewBindings('request-2'))
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            const body = init.body ? JSON.parse(init.body) : null;
            calls.push({ url, init, body });
            const reply = replies.shift();
            if (reply.status === 'accepted') {
                reply.openRequestId = body.openRequestId;
            }
            return new Response(JSON.stringify(reply), { status: 200 });
        }
    });

    const sessionId = await adapter.openSession(start);
    const first = await adapter.updatePreview(previewRequest(sessionId));
    const second = await adapter.updatePreview(
        previewRequest(sessionId, 'request-2')
    );

    assert.equal(sessionId, 'session-1');
    assert.deepEqual(first.selectedIds, [3]);
    assert.equal(first.maskSet.threshold, 0.5);
    assert.deepEqual(second.uncertainIds, [7]);
    assert.deepEqual(
        calls.map((call) => `${call.init.method} ${call.url}`),
        [
            'PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view',
            'POST https://companion.example:8787/object-selection-sessions',
            'PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1',
            'POST https://companion.example:8787/object-selection-sessions/session-1/previews',
            'PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1',
            'POST https://companion.example:8787/object-selection-sessions/session-1/previews',
            'POST https://companion.example:8787/object-selection-sessions/session-1/previews'
        ]
    );
    assert.deepEqual(calls[0].body, start.requestContext.frameSet);
    assert.deepEqual(calls[2].body, snapshot);
    assert.equal(calls[3].body.snapshot, undefined);
    assert.equal(calls[3].body.modelManifestDigest, 'sha256:model-v1');
    for (const call of calls) {
        assert.equal(call.init.mode, 'cors');
        assert.equal(call.init.credentials, 'omit');
        assert.equal(call.init.cache, 'no-store');
    }
});

test("accepts a complete preview bound to the Companion's generated Frame Set", async () => {
    const request = previewRequest();
    const bindings = {
        ...previewBindings(request.requestId),
        frameSetVersion: 'generated-frames-1:sha256:frame-set-v1'
    };
    const frameSet = {
        frameSetId: 'generated-frames-1',
        frameSetVersion: bindings.frameSetVersion,
        orderedViews: [
            ...start.requestContext.frameSet.orderedViews,
            {
                viewId: 'generated-ring-01',
                frameDigest: 'sha256:generated-ring-01-v1',
                width: 64,
                height: 48
            }
        ]
    };
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'complete',
                    ...bindings,
                    selectedIds: [3],
                    uncertainIds: [7],
                    rejectedIds: [9],
                    frameSet,
                    maskSet: maskSet(bindings, frameSet),
                    evidenceSnapshot: evidenceSnapshot(bindings, frameSet),
                    coverageReport: coverageReport(bindings, frameSet)
                }),
                { status: 200 }
            )
    });

    const response = await adapter.updatePreview(request);

    assert.equal(response.frameSetVersion, frameSet.frameSetVersion);
    assert.deepEqual(
        response.frameSet.orderedViews.map((view) => view.viewId),
        ['anchor-view', 'generated-ring-01']
    );
    assert.equal(response.maskSet.frameSetVersion, frameSet.frameSetVersion);
    assert.equal(response.evidenceSnapshot.frameSetId, frameSet.frameSetId);
    assert.equal(
        response.coverageReport.frameSetVersion,
        frameSet.frameSetVersion
    );
});

test('re-registers the Scene Snapshot after closing the Companion session lease', async () => {
    const calls = [];
    const replies = [
        {
            status: 200,
            body: {
                status: 'registered',
                frameSetVersion: start.requestContext.frameSetVersion
            }
        },
        { status: 200, body: { status: 'accepted', sessionId: 'session-1' } },
        {
            status: 200,
            body: {
                status: 'registered',
                sceneId: snapshot.sceneId,
                sceneVersion: snapshot.sceneVersion
            }
        },
        { status: 204 },
        {
            status: 200,
            body: {
                status: 'registered',
                frameSetVersion: start.requestContext.frameSetVersion
            }
        },
        { status: 200, body: { status: 'accepted', sessionId: 'session-2' } },
        {
            status: 200,
            body: {
                status: 'registered',
                sceneId: snapshot.sceneId,
                sceneVersion: snapshot.sceneVersion
            }
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            const body = init.body ? JSON.parse(init.body) : null;
            calls.push({ url, init, body });
            const reply = replies.shift();
            if (reply.body?.status === 'accepted') {
                reply.body.openRequestId = body.openRequestId;
            }
            return new Response(
                reply.body === undefined ? null : JSON.stringify(reply.body),
                { status: reply.status }
            );
        }
    });

    const firstSession = await adapter.openSession(start);
    await adapter.closeSession(firstSession);
    await adapter.openSession(start);

    assert.equal(
        calls.filter((call) => call.url.includes('/scene-snapshots/')).length,
        2
    );
});

test('cleans an unrecovered opening after session admission fails', async () => {
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({
                url,
                init,
                body: init.body ? JSON.parse(init.body) : null
            });
            if (calls.length === 1 || calls.length === 3) {
                return new Response(
                    JSON.stringify({
                        status: 'registered',
                        frameSetVersion: start.requestContext.frameSetVersion
                    }),
                    { status: 200 }
                );
            }
            if (calls.length === 2 || calls.length === 4) {
                throw new Error(
                    'connection reset after Frame Set registration'
                );
            }
            return new Response(null, { status: 204 });
        }
    });

    await assert.rejects(
        adapter.openSession(start),
        /could not complete the Selection Service Companion request/
    );
    const openRequestId = calls[1].body.openRequestId;
    assert.deepEqual(
        calls.map((call) => `${call.init.method} ${call.url}`),
        [
            'PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view',
            'POST https://companion.example:8787/object-selection-sessions',
            'PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view',
            'POST https://companion.example:8787/object-selection-sessions',
            `DELETE https://companion.example:8787/object-selection-sessions/open-requests/${encodeURIComponent(openRequestId)}`,
            'DELETE https://companion.example:8787/frame-sets/anchor%3Aanchor-view'
        ]
    );
    assert.equal(calls[1].body.openRequestId, openRequestId);
    assert.equal(calls[3].body.openRequestId, openRequestId);
});

test('recovers a session when its first admission response is lost', async () => {
    const calls = [];
    let admissionAttempts = 0;
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            const body = init.body ? JSON.parse(init.body) : null;
            calls.push({ url, init, body });
            if (url.includes('/frame-sets/')) {
                return new Response(
                    JSON.stringify({
                        status: 'registered',
                        frameSetVersion: start.requestContext.frameSetVersion
                    }),
                    { status: 200 }
                );
            }
            if (url.endsWith('/object-selection-sessions')) {
                admissionAttempts += 1;
                if (admissionAttempts === 1) {
                    throw new Error(
                        'response lost after successful Companion admission'
                    );
                }
                return new Response(
                    JSON.stringify({
                        status: 'accepted',
                        sessionId: 'recovered-session',
                        openRequestId: body.openRequestId
                    }),
                    { status: 201 }
                );
            }
            if (url.includes('/scene-snapshots/')) {
                return new Response(
                    JSON.stringify({
                        status: 'registered',
                        sceneId: snapshot.sceneId,
                        sceneVersion: snapshot.sceneVersion
                    }),
                    { status: 200 }
                );
            }
            throw new Error(`unexpected request: ${url}`);
        }
    });

    const sessionId = await adapter.openSession(start);

    assert.equal(sessionId, 'recovered-session');
    assert.deepEqual(
        calls.map((call) => `${call.init.method} ${call.url}`),
        [
            'PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view',
            'POST https://companion.example:8787/object-selection-sessions',
            'PUT https://companion.example:8787/frame-sets/anchor%3Aanchor-view',
            'POST https://companion.example:8787/object-selection-sessions',
            'PUT https://companion.example:8787/scene-snapshots/scene-1/snapshot-v1'
        ]
    );
    assert.equal(calls[1].body.openRequestId, calls[3].body.openRequestId);
});

test('uses a distinct admission ID for each logical New opening', async () => {
    const calls = [];
    let sessionNumber = 0;
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            const body = init.body ? JSON.parse(init.body) : null;
            calls.push({ url, init, body });
            if (url.includes('/frame-sets/')) {
                return new Response(
                    JSON.stringify({
                        status: 'registered',
                        frameSetVersion: start.requestContext.frameSetVersion
                    }),
                    { status: 200 }
                );
            }
            if (url.endsWith('/object-selection-sessions')) {
                sessionNumber += 1;
                return new Response(
                    JSON.stringify({
                        status: 'accepted',
                        sessionId: `session-${sessionNumber}`,
                        openRequestId: body.openRequestId
                    }),
                    { status: 201 }
                );
            }
            if (url.includes('/scene-snapshots/')) {
                return new Response(
                    JSON.stringify({
                        status: 'registered',
                        sceneId: snapshot.sceneId,
                        sceneVersion: snapshot.sceneVersion
                    }),
                    { status: 200 }
                );
            }
            if (init.method === 'DELETE') {
                return new Response(null, { status: 204 });
            }
            throw new Error(`unexpected request: ${url}`);
        }
    });
    const nextStart = {
        ...start,
        prompt: {
            ...start.prompt,
            promptId: 'prompt-2',
            xPx: 11
        }
    };

    const firstSession = await adapter.openSession(start);
    await adapter.closeSession(firstSession);
    await adapter.openSession(nextStart);

    const admissions = calls.filter(
        (call) =>
            call.init.method === 'POST' &&
            call.url.endsWith('/object-selection-sessions')
    );
    assert.equal(admissions.length, 2);
    assert.match(admissions[0].body.openRequestId, /^open:/);
    assert.notEqual(
        admissions[0].body.openRequestId,
        admissions[1].body.openRequestId
    );
});

test('rejects a preview response that omits its complete Mask Set', async () => {
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'complete',
                    ...previewBindings('request-1'),
                    selectedIds: [3],
                    uncertainIds: [7],
                    rejectedIds: [9],
                    frameSet: frameSetForBindings(previewBindings('request-1')),
                    evidenceSnapshot: evidenceSnapshot(
                        previewBindings('request-1')
                    ),
                    coverageReport: coverageReport(previewBindings('request-1'))
                }),
                { status: 200 }
            )
    });

    await assert.rejects(
        adapter.updatePreview(previewRequest()),
        /complete, version-bound Mask Set/
    );
});

test('rejects a preview response that omits its complete Evidence Snapshot', async () => {
    const bindings = previewBindings('request-1');
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'complete',
                    ...bindings,
                    selectedIds: [3],
                    uncertainIds: [7],
                    rejectedIds: [9],
                    frameSet: frameSetForBindings(bindings),
                    maskSet: maskSet(bindings),
                    coverageReport: coverageReport(bindings)
                }),
                { status: 200 }
            )
    });

    await assert.rejects(
        adapter.updatePreview(previewRequest()),
        /complete, version-bound Evidence Snapshot/
    );
});

test('rejects a complete Mask Set that omits its threshold', async () => {
    const bindings = previewBindings('request-1');
    const noThresholdMaskSet = maskSet(bindings);
    delete noThresholdMaskSet.threshold;
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'complete',
                    ...bindings,
                    selectedIds: [3],
                    uncertainIds: [7],
                    rejectedIds: [9],
                    frameSet: frameSetForBindings(bindings),
                    maskSet: noThresholdMaskSet,
                    evidenceSnapshot: evidenceSnapshot(bindings),
                    coverageReport: coverageReport(bindings)
                }),
                { status: 200 }
            )
    });

    await assert.rejects(
        adapter.updatePreview(previewRequest()),
        /invalid Mask Set threshold/
    );
});

test('rejects a Mask Set with a malformed accepted binary mask', async () => {
    const bindings = previewBindings('request-1');
    const malformedMaskSet = maskSet(bindings);
    malformedMaskSet.tracks[0].frames[0].binaryMask = {
        encoding: 'sparse-points-v1',
        width: 1,
        height: 1,
        foregroundPixels: [[0, 0]]
    };
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'complete',
                    ...bindings,
                    selectedIds: [3],
                    uncertainIds: [7],
                    rejectedIds: [9],
                    frameSet: frameSetForBindings(bindings),
                    maskSet: malformedMaskSet,
                    evidenceSnapshot: evidenceSnapshot(bindings),
                    coverageReport: coverageReport(bindings)
                }),
                { status: 200 }
            )
    });

    await assert.rejects(
        adapter.updatePreview(previewRequest()),
        /complete, version-bound Mask Set/
    );
});

const maskPromptState = revisePromptState(
    createEmptyPromptState('anchor-view', `sha256:${'a'.repeat(64)}`),
    {
        points: [
            {
                promptId: 'prompt-1',
                xPx: 10,
                yPx: 12,
                polarity: 'include'
            }
        ]
    }
);

const maskRequest = {
    requestBinding: anchorRequest.requestBinding,
    target: anchorRequest.target,
    sceneId: anchorSnapshot.sceneId,
    sceneVersion: anchorSnapshot.sceneVersion,
    viewId: 'anchor-view',
    cameraBindingDigest: `sha256:${'c'.repeat(64)}`,
    rgbDigest: `sha256:${'a'.repeat(64)}`,
    rgbWidth: 64,
    rgbHeight: 48,
    rgb: {
        pngBase64: anchorPng(64, 48).pngBase64,
        digest: `sha256:${'a'.repeat(64)}`,
        width: 64,
        height: 48
    },
    promptState: maskPromptState,
    modelManifestDigest: 'sha256:model-v1',
    adapterCapabilityDigest: `sha256:${'d'.repeat(64)}`,
    proposalPolicyVersion: 'auto-mask-proposals/bounded-source-order-v2',
    rankingPolicyVersion: anchorMaskRankingPolicyVersion,
    proposalAttemptId: 'proposal-attempt-1'
};

const maskBitset = (width, height, foreground = [[10, 12]]) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    for (const [x, y] of foreground) {
        const index = y * width + x;
        bytes[index >> 3] |= 1 << (index % 8);
    }
    return {
        encoding: 'bitset-lsb-v1',
        width,
        height,
        data: Buffer.from(bytes).toString('base64'),
        digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`
    };
};

const candidateReLiftRequest = () => {
    const evidenceWorkingSet = createEvidenceWorkingSet({
        targetSplatId: 'scene-1',
        coreTargetStableIds: [3],
        contextStableGaussianIds: []
    });
    const stableMask = maskBitset(64, 48, [[0, 0]]);
    const bindingDigest = cameraBindingDigest(anchorCameraBinding);
    const currentInput = {
        requestBinding: anchorRequest.requestBinding,
        targetSplatId: 'scene-1',
        view: {
            viewId: 'view-1',
            renderStatus: 'ready',
            participation: 'included',
            cameraBindingDigest: bindingDigest,
            rgbDigest: `sha256:${'b'.repeat(64)}`,
            stableMaskDigest: stableMask.digest
        },
        evidencePolicyDigest:
            'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd',
        renderWorkingSet: {
            targetSplatId: 'scene-1',
            dependencyToken: anchorRequest.requestBinding.dependencyToken,
            cameraBindingDigest: bindingDigest,
            renderWorkingSetToken: anchorSnapshot.contentDigest,
            stableGaussianIds: [3],
            completeness: 'complete'
        },
        evidenceWorkingSet,
        rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
        evidenceBackendKind: 'production-direct',
        evidenceBackendId: 'global-atomic/direct-v1',
        runtimeBuildId:
            'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4'
    };
    const evidenceAdmission = admitGaussianEvidence(currentInput);
    assert.equal(evidenceAdmission.status, 'admitted');
    const cachedArtifact = createGaussianEvidenceArtifact(
        evidenceAdmission.admission,
        {
            positiveMass: [0.5],
            negativeMass: [0.25],
            visibleMass: [0.75],
            boundaryMass: [0]
        }
    );
    return {
        liftAttemptId: 'candidate-re-lift-1',
        productionIdentityDigest: `sha256:${'8'.repeat(64)}`,
        generationState: 'complete',
        snapshot: anchorSnapshot,
        requestBinding: anchorRequest.requestBinding,
        targetSplatId: 'scene-1',
        classificationUniverseStableGaussianIds: [3],
        classificationScopeStableGaussianIds: [3],
        evidenceWorkingSet,
        views: [
            {
                currentInput,
                cameraBinding: anchorCameraBinding,
                stableMask,
                cachedArtifact
            }
        ]
    };
};

const directEvidenceRequest = () => {
    const reference = candidateReLiftRequest().views[0];
    return {
        evidenceAttemptId: 'direct-evidence-attempt-1',
        snapshot: anchorSnapshot,
        cameraBinding: reference.cameraBinding,
        stableMask: reference.stableMask,
        currentInput: {
            ...reference.currentInput,
            rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'global-atomic/direct-v1',
            runtimeBuildId:
                'sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4'
        }
    };
};

const maskReply = (request, overrides = {}) => {
    const promptConsistency = {
        positivePointsSatisfied: true,
        negativePointsSatisfied: true,
        positiveBoxesSatisfied: true
    };
    const proposalPayload = {
        schemaVersion: 4,
        viewId: request.viewId,
        rgbDigest: request.rgbDigest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposals: [
            {
                proposalId: 'proposal-0',
                sourceIndex: 0,
                mask:
                    overrides.mask ??
                    maskBitset(request.rgbWidth, request.rgbHeight),
                promptConsistency,
                rankingFeatures: {
                    promptConsistency,
                    eligible: true,
                    areaFraction: 1 / (request.rgbWidth * request.rgbHeight),
                    connectedComponentCount: 1
                },
                review: {
                    status: 'good',
                    reasons: [],
                    actionableReasons: [],
                    policyVersion: aiSelectViewAssessmentPolicyVersion,
                    diagnostics: {
                        framePixels: request.rgbWidth * request.rgbHeight,
                        foregroundPixels: 1,
                        boundaryPixels: 0,
                        boundaryContactRatio: 0,
                        connectedComponents: 1,
                        largestComponentRatio: 1,
                        promptPointCount: 1,
                        promptViolationCount: 0,
                        boxSpillPixels: null,
                        boxSpillRatio: null
                    }
                }
            }
        ]
    };
    const proposalSet = {
        ...proposalPayload,
        digest: autoMaskProposalSetDigest(proposalPayload)
    };
    const { mask: ignoredMask, ...responseOverrides } = overrides;
    return {
        status: 'complete',
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        cameraBindingDigest: request.cameraBindingDigest,
        rgbDigest: request.rgbDigest,
        promptStateDigest: request.promptState.digest,
        modelManifestDigest: request.modelManifestDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        proposalPolicyVersion: request.proposalPolicyVersion,
        rankingPolicyVersion: request.rankingPolicyVersion,
        proposalAttemptId: request.proposalAttemptId,
        proposalSet,
        proposalDecision: {
            schemaVersion: 2,
            viewId: request.viewId,
            rgbDigest: request.rgbDigest,
            promptStateDigest: request.promptState.digest,
            proposalSetDigest: proposalSet.digest,
            rankingPolicyVersion: request.rankingPolicyVersion,
            status: 'selected',
            selectedProposalId: 'proposal-0',
            alternativeProposalIds: ['proposal-0']
        },
        ...responseOverrides
    };
};

test('sends a bound single-frame Mask request and returns the validated Mask result', async () => {
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(maskReply(maskRequest)), {
                status: 200
            });
        }
    });

    const response = await adapter.produceMask(maskRequest);

    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /\/ai-select\/mask-proposals$/);
    assert.equal(calls[0].init.method, 'POST');
    assert.deepEqual(calls[0].body.requestBinding, maskRequest.requestBinding);
    assert.deepEqual(calls[0].body.promptState, maskRequest.promptState);
    assert.equal(
        calls[0].body.rankingPolicyVersion,
        maskRequest.rankingPolicyVersion
    );
    assert.equal(calls[0].body.proposalAttemptId, 'proposal-attempt-1');
    assert.equal(calls[0].body.rgbDigest, maskRequest.rgbDigest);
    assert.equal(calls[0].body.rgbWidth, 64);
    assert.equal(calls[0].body.rgbHeight, 48);
    assert.deepEqual(calls[0].body.rgb, maskRequest.rgb);
    assert.equal(response.result.status, 'usable');
    assert.equal(
        response.result.mask.digest,
        maskReply(maskRequest).proposalSet.proposals[0].mask.digest
    );
});

test('sends an RGB reference and refinement lineage without the RGB artifact', async () => {
    const refPayload = {
        schemaVersion: 1,
        companionInstanceId: 'companion-instance-1',
        stateId: 'logits-state-1',
        targetContextId: maskRequest.requestBinding.targetContextId,
        viewId: 'anchor-view',
        rgbDigest: maskRequest.rgbDigest,
        sourceInferenceAttemptId: 'proposal-attempt-0',
        sourceCandidateId: 'proposal-0',
        adapterRuntimeDigest: `sha256:${'9'.repeat(64)}`,
        shape: [1, 288, 288],
        dtype: 'float32',
        dataDigest: `sha256:${'8'.repeat(64)}`
    };
    const previousLogitsRef = {
        ...refPayload,
        refDigest: previousPredictionLogitsRefDigest(refPayload)
    };
    const { rgb: _rgb, ...referenceOnly } = maskRequest;
    const refinementRequest = {
        ...referenceOnly,
        previousLogitsRef,
        proposalAttemptId: 'proposal-attempt-2'
    };
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(maskReply(refinementRequest)), {
                status: 200
            });
        }
    });

    await adapter.produceMask(refinementRequest);

    assert.equal(calls.length, 1);
    assert.equal(calls[0].body.rgb, undefined);
    assert.equal(calls[0].body.rgbDigest, maskRequest.rgbDigest);
    assert.deepEqual(calls[0].body.previousLogitsRef, previousLogitsRef);
    assert.equal(calls[0].body.proposalAttemptId, 'proposal-attempt-2');
});

test('rejects a structurally invalid refinement reference before transport', async () => {
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () => {
            throw new Error('must not be called');
        }
    });
    await assert.rejects(
        adapter.produceMask({
            ...maskRequest,
            previousLogitsRef: {
                stateId: 'logits-state-1',
                logitsBase64: 'AAAA'
            }
        }),
        /complete bound Mask request/
    );
});

test('rejects a Mask response bound to a stale attempt or RGB identity', async () => {
    const staleAttempt = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify(
                    maskReply(maskRequest, {
                        proposalAttemptId: 'proposal-attempt-2'
                    })
                ),
                { status: 200 }
            )
    });
    await assert.rejects(
        staleAttempt.produceMask(maskRequest),
        /invalid Mask artifact publication/
    );

    const staleRgb = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify(
                    maskReply(maskRequest, {
                        rgbDigest: `sha256:${'b'.repeat(64)}`
                    })
                ),
                { status: 200 }
            )
    });
    await assert.rejects(
        staleRgb.produceMask(maskRequest),
        /invalid Mask artifact publication/
    );
});

test('rejects a Mask artifact whose bytes do not match its digest', async () => {
    const tampered = maskBitset(64, 48, [[1, 1]]);
    tampered.data = maskBitset(64, 48, [[2, 2]]).data;
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify(maskReply(maskRequest, { mask: tampered })),
                {
                    status: 200
                }
            )
    });
    await assert.rejects(
        adapter.produceMask(maskRequest),
        /invalid Mask artifact publication/
    );
});

test('rejects malformed compatibility Mask decisions at the product adapter', async () => {
    const reply = maskReply(maskRequest);
    reply.proposalDecision.status = 'made-up';
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(JSON.stringify(reply), {
                status: 200
            })
    });
    await assert.rejects(
        adapter.produceMask(maskRequest),
        /invalid Mask artifact publication/
    );
});

test('surfaces a Companion Mask error without publishing anything', async () => {
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async () =>
            new Response(
                JSON.stringify({
                    status: 'maskProposalError',
                    code: 'incompleteMaskSet',
                    message: 'The adapter returned an invalid Mask artifact.'
                }),
                { status: 409 }
            )
    });
    await assert.rejects(
        adapter.produceMask(maskRequest),
        (error) =>
            error.message.includes('HTTP 409') &&
            error.serviceCode === 'incompleteMaskSet' &&
            error.serviceMessage ===
                'The adapter returned an invalid Mask artifact.'
    );
});

test('rejects a Mask request that is not bound to the configured Model Manifest', async () => {
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:other-model'
        }),
        fetch: async () => {
            throw new Error('must not be called');
        }
    });
    await assert.rejects(adapter.produceMask(maskRequest));
});

test('bounds a Candidate Re-Lift transport that never completes', async () => {
    const replies = stagedBinaryRegistrationReplies(anchorSnapshot);
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        candidateReLiftTimeoutMs: 5,
        fetch: async (url, init) => {
            calls.push({ url, init });
            const reply = replies.shift();
            if (reply !== undefined) {
                return new Response(JSON.stringify(reply), { status: 200 });
            }
            await new Promise((resolve) => setTimeout(resolve, 50));
            throw new Error('late transport failure');
        }
    });
    const request = candidateReLiftRequest();
    request.liftAttemptId = 'candidate-re-lift-timeout-1';

    await assert.rejects(adapter.produceCandidateReLift(request), /timed out/);
    assert.match(calls.at(-1).url, /\/ai-select\/candidate-re-lifts$/);
});

test('disposes exact Companion target replay authority', async () => {
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init });
            return new Response(null, { status: 204 });
        }
    });

    await adapter.disposeTargetContext('target/context-a');

    assert.ok(calls[0].url.endsWith('/ai-select/targets/target%2Fcontext-a'));
    assert.equal(calls[0].init.method, 'DELETE');
});

test('registers the exact Scene Snapshot before producing bound Direct Evidence', async () => {
    const request = directEvidenceRequest();
    const admission = admitGaussianEvidence(request.currentInput);
    assert.equal(admission.status, 'admitted');
    const artifact = createGaussianEvidenceArtifact(admission.admission, {
        positiveMass: [0.5],
        negativeMass: [0.25],
        visibleMass: [0.75],
        boundaryMass: [0]
    });
    const calls = [];
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot),
        {
            status: 'complete',
            evidenceAttemptId: request.evidenceAttemptId,
            requestBinding: request.currentInput.requestBinding,
            targetSplatId: request.currentInput.targetSplatId,
            viewId: request.currentInput.view.viewId,
            reused: false,
            artifact,
            telemetry: {
                evidenceBufferBytes: 16,
                pixelWeightBufferBytes: 64 * 48 * 16,
                boundaryBufferBytes: 16392,
                peakVramBytes: 1024
            }
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    const response = await adapter.produceDirectEvidence(request);

    assert.equal(response.artifact.artifactDigest, artifact.artifactDigest);
    assert.ok(calls.at(-1).url.endsWith('/ai-select/direct-evidence'));
    assert.equal('snapshot' in calls.at(-1).body, false);
    assert.deepEqual(calls.at(-1).body.currentInput, request.currentInput);
});

test('uploads spatial chunks for both the Render and Direct Evidence Working Sets', async () => {
    const gaussianCount = 16_385;
    const stableIds = new Uint32Array(gaussianCount);
    const means = new Float32Array(gaussianCount * 3);
    const rotationsXyzw = new Float32Array(gaussianCount * 4);
    for (let index = 0; index < gaussianCount; index += 1) {
        stableIds[index] = index + 1;
        means[index * 3] = index * 0.001;
        means[index * 3 + 2] = 5;
        rotationsXyzw[index * 4 + 3] = 1;
    }
    const multiChunkSnapshot = buildPackedSceneSnapshot({
        sceneId: 'scene-1',
        coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
        stableIdSchema: 'uint32',
        appearancePolicy: 'effective-editor-dc-sh-bands-0',
        renderConfiguration: anchorSnapshot.renderConfiguration,
        stableIds,
        means,
        rotationsXyzw,
        logScales: new Float32Array(gaussianCount * 3),
        logitOpacities: new Float32Array(gaussianCount),
        dc: new Float32Array(gaussianCount * 3),
        sh: new Float32Array(),
        shFloatCountPerGaussian: 0,
        authoritativeRenderScope: {
            policyId: 'visible-editor-splats-conservative/v1',
            targetSplatId: 'scene-1',
            identityDigest: `sha256:${'d'.repeat(64)}`,
            entries: [
                {
                    splatId: 'scene-1',
                    role: 'target',
                    sourceContentDigest: `sha256:${'f'.repeat(64)}`,
                    rowOffset: 0,
                    rowCount: gaussianCount,
                    renderIdStart: 1
                }
            ]
        }
    });
    const spatialSnapshot = buildSpatialSceneSnapshot(multiChunkSnapshot, {
        targetSplatId: anchorRequest.target.splatId
    });
    assert.equal(spatialSnapshot.manifest.chunks.length, 2);
    const [renderChunk, evidenceOnlyChunk] = spatialSnapshot.manifest.chunks;
    const request = directEvidenceRequest();
    const evidenceWorkingSet = createEvidenceWorkingSet({
        targetSplatId: 'scene-1',
        coreTargetStableIds: [1],
        contextStableGaussianIds: [gaussianCount]
    });
    request.snapshot = multiChunkSnapshot;
    request.currentInput = {
        ...request.currentInput,
        renderWorkingSet: {
            ...request.currentInput.renderWorkingSet,
            renderWorkingSetToken: `sha256:${'c'.repeat(64)}`,
            stableGaussianIds: [1]
        },
        evidenceWorkingSet
    };
    const admission = admitGaussianEvidence(request.currentInput);
    assert.equal(admission.status, 'admitted');
    const artifact = createGaussianEvidenceArtifact(admission.admission, {
        positiveMass: [0.5, 0.25],
        negativeMass: [0.25, 0.5],
        visibleMass: [0.75, 0.75],
        boundaryMass: [0, 0]
    });
    const replies = [
        {
            status: 'registered',
            registrationId: 'spatial-registration-direct',
            sceneId: multiChunkSnapshot.sceneId,
            sceneVersion: multiChunkSnapshot.sceneVersion,
            contentDigest: multiChunkSnapshot.contentDigest
        },
        {
            status: 'staged',
            uploadId: 'spatial-upload-direct',
            missingChunkIds: [renderChunk.chunkId, evidenceOnlyChunk.chunkId]
        },
        {
            status: 'stored',
            uploadId: 'spatial-upload-direct',
            chunkId: renderChunk.chunkId
        },
        {
            status: 'stored',
            uploadId: 'spatial-upload-direct',
            chunkId: evidenceOnlyChunk.chunkId
        },
        {
            status: 'committed',
            sceneId: multiChunkSnapshot.sceneId,
            sceneVersion: multiChunkSnapshot.sceneVersion,
            committedChunkIds: [renderChunk.chunkId, evidenceOnlyChunk.chunkId]
        },
        {
            status: 'complete',
            evidenceAttemptId: request.evidenceAttemptId,
            requestBinding: request.currentInput.requestBinding,
            targetSplatId: request.currentInput.targetSplatId,
            viewId: request.currentInput.view.viewId,
            reused: false,
            artifact
        }
    ];
    const calls = [];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init, body: responseBody(init.body) });
            return new Response(JSON.stringify(replies.shift()), {
                status: 200
            });
        }
    });

    const response = await adapter.produceDirectEvidence(request);

    assert.equal(response.artifact.artifactDigest, artifact.artifactDigest);
    assert.match(calls[0].url, /\/spatial-scene-manifests\/v1$/);
    assert.match(calls[1].url, /\/spatial-scene-chunk-uploads\/v1$/);
    assert.match(calls[2].url, /\/chunks\/spatial-00000000$/);
    assert.match(calls[3].url, /\/chunks\/spatial-00000001$/);
    assert.match(calls[4].url, /\/commit$/);
    assert.ok(calls[5].url.endsWith('/ai-select/direct-evidence'));
    assert.equal(calls[5].body.sceneTransport, 'spatial-v1');
    assert.deepEqual(calls[5].body.currentInput, request.currentInput);
});

test('re-registers the Candidate Scene Snapshot once after a Companion cache-loss 409', async () => {
    const calls = [];
    const replies = [
        ...stagedBinaryRegistrationReplies(anchorSnapshot, 'upload-1'),
        {
            statusCode: 409,
            body: {
                status: 'candidateReLiftError',
                code: 'sceneCacheMiss',
                message:
                    'The Scene Snapshot is unavailable for Candidate Re-Lift.'
            }
        },
        ...stagedBinaryRegistrationReplies(anchorSnapshot, 'upload-2'),
        {
            statusCode: 409,
            body: {
                status: 'candidateReLiftError',
                code: 'candidateReLiftFailure',
                message: 'second request reached Candidate Re-Lift'
            }
        }
    ];
    const adapter = new FetchSelectionServiceAdapter({
        getConfiguration: () => ({
            endpoint: 'https://companion.example:8787',
            modelManifestDigest: 'sha256:model-v1'
        }),
        fetch: async (url, init) => {
            calls.push({ url, init });
            const reply = replies.shift();
            if (reply.statusCode !== undefined) {
                return new Response(JSON.stringify(reply.body), {
                    status: reply.statusCode
                });
            }
            return new Response(JSON.stringify(reply), { status: 200 });
        }
    });

    await assert.rejects(
        adapter.produceCandidateReLift(candidateReLiftRequest()),
        (error) =>
            error.serviceCode === 'candidateReLiftFailure' &&
            error.message.includes(
                'candidateReLiftFailure: second request reached Candidate Re-Lift'
            )
    );
    assert.equal(
        calls.filter((call) =>
            call.url.endsWith('/ai-select/candidate-re-lifts')
        ).length,
        2
    );
    assert.equal(
        calls.filter((call) => call.url.endsWith('/scene-snapshot-uploads/v1'))
            .length,
        2
    );
});
