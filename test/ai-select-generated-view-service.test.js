const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    aiSelectGeneratedViewMaskPolicyVersion,
    aiSelectGeneratedViewPlannerVersion,
    generatedViewMaskResponseMatchesRequest,
    generatedViewPlanResponseMatchesRequest,
    isAIViewRenderRequest,
    isAIViewRenderResponse,
    isGeneratedViewMaskRequest,
    isGeneratedViewMaskResponse,
    isGeneratedViewPlanRequest,
    isGeneratedViewPlanResponse,
    viewRenderResponseMatchesRequest
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
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

const rgbDigest = (letter) => `sha256:${letter.repeat(64)}`;

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

const pngBase64 = (width, height) => {
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
    ]).toString('base64');
};

const planRequest = (overrides = {}) => ({
    requestBinding: requestBinding(),
    target: target(),
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    planAttemptId: 'plan-attempt-1',
    anchorCameraBinding: cameraBinding(),
    anchorRgbDigest: rgbDigest('a'),
    anchorStableMask: maskArtifact(64, 48, 0b101),
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion,
    ...overrides
});

const plannedView = (viewId = 'generated-00') => ({
    viewId,
    cameraBinding: cameraBinding()
});

const planResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    planAttemptId: request.planAttemptId,
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion,
    views: [plannedView('generated-00'), plannedView('generated-01')],
    ...overrides
});

const renderRequest = (overrides = {}) => ({
    requestBinding: requestBinding(),
    target: target(),
    snapshot,
    cameraBinding: cameraBinding(),
    viewId: 'generated-00',
    renderAttemptId: 'generated-render-attempt-1',
    ...overrides
});

const renderResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    renderAttemptId: request.renderAttemptId,
    viewId: request.viewId,
    cameraBinding: request.cameraBinding,
    rgb: {
        pngBase64: pngBase64(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height
        ),
        digest: rgbDigest('b'),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat',
    ...overrides
});

const maskRequest = (overrides = {}) => ({
    requestBinding: requestBinding(),
    target: target(),
    snapshot,
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    viewId: 'generated-00',
    viewCameraBinding: cameraBinding(),
    maskAttemptId: 'generated-mask-attempt-1',
    rgb: {
        pngBase64: pngBase64(64, 48),
        digest: rgbDigest('b'),
        width: 64,
        height: 48
    },
    anchor: {
        cameraBinding: cameraBinding(),
        rgbDigest: rgbDigest('a'),
        stableMask: maskArtifact(64, 48, 0b101)
    },
    modelManifestDigest: 'manifest-digest-1',
    ...overrides
});

const maskResponseFor = (request, overrides = {}) => {
    const mask = maskArtifact(64, 48, 0b110);
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        maskAttemptId: request.maskAttemptId,
        rgbDigest: request.rgb.digest,
        anchorRgbDigest: request.anchor.rgbDigest,
        mask,
        maskSource: 'propagated',
        maskPropagation: {
            policyVersion: aiSelectGeneratedViewMaskPolicyVersion,
            projectedSupportCount: 17,
            promptCount: 3
        },
        assessment: {
            status: 'review',
            primaryReason: 'fragmented-mask',
            reasons: ['fragmented-mask', 'weak-gaussian-support'],
            actionableReasons: ['fragmented-mask', 'weak-gaussian-support'],
            policyVersion: 'local-view-assessment/v1',
            inputIdentity: {
                rgbDigest: request.rgb.digest,
                stableMaskDigest: mask.digest,
                assessmentPolicyVersion: 'local-view-assessment/v1',
                supportPolicyVersion: 'local-view-support-probe/v1',
                propagationPolicyVersion: aiSelectGeneratedViewMaskPolicyVersion
            },
            diagnostics: {
                foregroundPixels: 2,
                boundaryContactRatio: 0,
                connectedComponents: 2,
                largestComponentRatio: 0.5,
                observedGaussianCount: 17,
                projectedSupportCount: 17,
                promptCount: 3
            }
        },
        modelManifestDigest: request.modelManifestDigest,
        ...overrides
    };
};

test('a complete Generated View plan request validates', () => {
    assert.ok(isGeneratedViewPlanRequest(planRequest()));
});

test('plan request validation fails closed on malformed inputs', () => {
    const request = planRequest();
    assert.ok(!isGeneratedViewPlanRequest(null));
    assert.ok(
        !isGeneratedViewPlanRequest({ ...request, requestBinding: null })
    );
    assert.ok(
        !isGeneratedViewPlanRequest({
            ...request,
            anchorRgbDigest: 'not-a-digest'
        })
    );
    assert.ok(
        !isGeneratedViewPlanRequest({
            ...request,
            anchorStableMask: { ...request.anchorStableMask, digest: 'x' }
        })
    );
    assert.ok(
        !isGeneratedViewPlanRequest({
            ...request,
            plannerPolicyVersion: 'generated-view-planner/v0'
        })
    );
    assert.ok(!isGeneratedViewPlanRequest({ ...request, planAttemptId: '' }));
});

test('a matching plan response validates against its request', () => {
    const request = planRequest();
    const response = planResponseFor(request);
    assert.ok(isGeneratedViewPlanResponse(response));
    assert.ok(generatedViewPlanResponseMatchesRequest(response, request));
});

test('plan response rejects stale bindings, empty plans, and duplicate views', () => {
    const request = planRequest();
    const response = planResponseFor(request);
    assert.ok(
        !generatedViewPlanResponseMatchesRequest(
            planResponseFor(request, { planAttemptId: 'plan-attempt-2' }),
            request
        )
    );
    // Structural failures close at the response validator.
    assert.ok(
        !isGeneratedViewPlanResponse(planResponseFor(request, { views: [] }))
    );
    assert.ok(
        !isGeneratedViewPlanResponse(
            planResponseFor(request, {
                views: [
                    plannedView('generated-00'),
                    plannedView('generated-00')
                ]
            })
        )
    );
    assert.ok(
        !generatedViewPlanResponseMatchesRequest(
            planResponseFor(request, {
                renderConfigVersion: 'other-config'
            }),
            request
        )
    );
    assert.ok(
        !isGeneratedViewPlanResponse({ ...response, views: 'generated-00' })
    );
    assert.ok(
        !generatedViewPlanResponseMatchesRequest(
            planResponseFor(request, {
                plannerPolicyVersion: 'generated-view-planner/v0'
            }),
            request
        )
    );
});

test('a complete Generated View render request validates', () => {
    assert.ok(isAIViewRenderRequest(renderRequest()));
});

test('render request validation rejects the Anchor view id and bad bindings', () => {
    const request = renderRequest();
    assert.ok(!isAIViewRenderRequest({ ...request, viewId: 'anchor-view' }));
    assert.ok(!isAIViewRenderRequest({ ...request, viewId: '' }));
    assert.ok(!isAIViewRenderRequest({ ...request, renderAttemptId: '' }));
});

test('a matching render response validates, including true PNG dimensions', () => {
    const request = renderRequest();
    const response = renderResponseFor(request);
    assert.ok(isAIViewRenderResponse(response));
    assert.ok(viewRenderResponseMatchesRequest(response, request));
});

test('render response rejects stale echoes and dimension lies', () => {
    const request = renderRequest();
    assert.ok(
        !viewRenderResponseMatchesRequest(
            renderResponseFor(request, { viewId: 'generated-01' }),
            request
        )
    );
    assert.ok(
        !viewRenderResponseMatchesRequest(
            renderResponseFor(request, {
                rgb: {
                    ...renderResponseFor(request).rgb,
                    width: 32,
                    height: 24
                }
            }),
            request
        )
    );
    assert.ok(
        !viewRenderResponseMatchesRequest(
            renderResponseFor(request, {
                rgb: {
                    ...renderResponseFor(request).rgb,
                    pngBase64: pngBase64(32, 24)
                }
            }),
            request
        )
    );
    assert.ok(
        !isAIViewRenderResponse(
            renderResponseFor(request, { rgbRendererVersion: 'gsplat-rgb/v0' })
        )
    );
});

test('a complete Generated View mask request validates', () => {
    assert.ok(isGeneratedViewMaskRequest(maskRequest()));
});

test('mask request validation fails closed on malformed inputs', () => {
    const request = maskRequest();
    assert.ok(!isGeneratedViewMaskRequest(null));
    assert.ok(
        !isGeneratedViewMaskRequest({ ...request, viewId: 'anchor-view' })
    );
    assert.ok(
        !isGeneratedViewMaskRequest({
            ...request,
            anchor: { ...request.anchor, rgbDigest: 'bad' }
        })
    );
    assert.ok(
        !isGeneratedViewMaskRequest({
            ...request,
            anchor: {
                ...request.anchor,
                stableMask: { ...request.anchor.stableMask, width: 8 }
            }
        })
    );
    assert.ok(
        !isGeneratedViewMaskRequest({ ...request, modelManifestDigest: '' })
    );
});

test('a matching mask response validates against its request', () => {
    const request = maskRequest();
    const response = maskResponseFor(request);
    assert.ok(isGeneratedViewMaskResponse(response));
    assert.ok(generatedViewMaskResponseMatchesRequest(response, request));
});

test('mask response rejects stale bindings, wrong sources, and bad artifacts', () => {
    const request = maskRequest();
    assert.ok(
        !generatedViewMaskResponseMatchesRequest(
            maskResponseFor(request, { maskAttemptId: 'other-attempt' }),
            request
        )
    );
    assert.ok(
        !generatedViewMaskResponseMatchesRequest(
            maskResponseFor(request, { rgbDigest: rgbDigest('f') }),
            request
        )
    );
    assert.ok(
        !generatedViewMaskResponseMatchesRequest(
            maskResponseFor(request, { anchorRgbDigest: rgbDigest('f') }),
            request
        )
    );
    // A wrong mask source is a structural failure, closed at the validator.
    assert.ok(
        !isGeneratedViewMaskResponse(
            maskResponseFor(request, { maskSource: 'single-frame-sam' })
        )
    );
    assert.ok(
        !generatedViewMaskResponseMatchesRequest(
            maskResponseFor(request, {
                mask: {
                    ...maskResponseFor(request).mask,
                    digest: rgbDigest('9')
                }
            }),
            request
        )
    );
    // Structural failures close at the response validator.
    assert.ok(
        !isGeneratedViewMaskResponse(
            maskResponseFor(request, {
                maskPropagation: {
                    policyVersion: 'generated-view-mask/v0',
                    projectedSupportCount: 17,
                    promptCount: 3
                }
            })
        )
    );
    assert.ok(
        !isGeneratedViewMaskResponse(
            maskResponseFor(request, {
                maskPropagation: {
                    policyVersion: aiSelectGeneratedViewMaskPolicyVersion,
                    projectedSupportCount: -1,
                    promptCount: 3
                }
            })
        )
    );
    assert.ok(
        !isGeneratedViewMaskResponse(
            maskResponseFor(request, { assessment: undefined })
        )
    );
    assert.ok(
        !generatedViewMaskResponseMatchesRequest(
            maskResponseFor(request, {
                assessment: {
                    ...maskResponseFor(request).assessment,
                    inputIdentity: {
                        ...maskResponseFor(request).assessment.inputIdentity,
                        stableMaskDigest: rgbDigest('f')
                    }
                }
            }),
            request
        )
    );
    assert.ok(
        !isGeneratedViewMaskResponse(
            maskResponseFor(request, {
                assessment: {
                    ...maskResponseFor(request).assessment,
                    reasons: ['identity-drift']
                }
            })
        )
    );
});
