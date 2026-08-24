const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    captureEditorCameraBinding,
    cameraBindingDigest
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    aiSelectImageInstancePromptSynthesisPolicyDigest,
    aiSelectImageInstancePromptSynthesisPolicyVersion,
    generatedViewPromptSynthesisResponseMatchesRequest,
    imageInstanceMaskReviewResponseMatchesRequest,
    isAIViewRenderRequest,
    isAIViewRenderResponse,
    isGeneratedViewImageInstanceMaskRequest,
    isGeneratedViewPromptSynthesisRequest,
    isGeneratedViewPromptSynthesisResponse,
    isImageInstanceMaskReviewRequest,
    isImageInstanceMaskReviewResponse,
    viewRenderResponseMatchesRequest
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    createImageInstancePromptArtifact
} = require('../.test-dist/src/ai-select/image-instance-mask.js');
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
    stableIds: new Uint32Array([1]),
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

const pngArtifact = (width, height, seed = 0) => {
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width, 0);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = 2;
    const scanlines = Buffer.alloc((width * 3 + 1) * height);
    scanlines[1] = seed;
    const bytes = Buffer.concat([
        Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
        pngChunk('IHDR', header),
        pngChunk('IDAT', deflateSync(scanlines)),
        pngChunk('IEND', Buffer.alloc(0))
    ]);
    return {
        pngBase64: bytes.toString('base64'),
        digest: sha256Digest(new Uint8Array(bytes)),
        width,
        height
    };
};

const maskArtifact = (width, height, seedByte = 0b110) => {
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
    rgb: pngArtifact(
        request.cameraBinding.projection.width,
        request.cameraBinding.projection.height,
        7
    ),
    rgbRendererVersion: 'gsplat-direct-evidence-rgb/v1',
    rendererId: 'gsplat',
    rasterImplementationId: 'supersimplat-gsplat-direct-evidence/v1',
    runtimeBuildId:
        'sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f',
    renderWorkingSetToken:
        request.snapshot.contentDigest ?? `sha256:${'f'.repeat(64)}`,
    renderStableGaussianIds: Array.from(
        request.snapshot.stableIds ?? [1],
        Number
    ).sort((left, right) => left - right),
    ...overrides
});

const geometryHint = (binding, rgb) => ({
    schemaVersion: 2,
    targetContextId: binding.targetContextId,
    anchorCameraBindingDigest: digest('a'),
    anchorRgbDigest: digest('b'),
    anchorStableMaskDigest: digest('c'),
    geometryPolicyDigest: digest('d'),
    centerWorld: [0, 0, 0],
    extentWorld: [1, 1, 1],
    visiblePoints: [
        [0, 0, 0],
        [1, 0, 0],
        [0, 1, 0],
        [1, 1, 0]
    ],
    quality: 'usable',
    reasons: [],
    promptSupport: 'usable',
    artifactDigest: digest('e')
});

const localPlan = (binding, viewCamera, hint) => ({
    schemaVersion: 1,
    targetContextId: binding.targetContextId,
    anchorStableMaskDigest: digest('c'),
    targetGeometryHintDigest: hint.artifactDigest,
    localViewPolicyDigest: digest('f'),
    orderedViews: [
        {
            viewId: 'generated-00',
            cameraBinding: viewCamera,
            quality: 'usable',
            reasons: []
        },
        ...[1, 2, 3].map((index) => ({
            viewId: `generated-failed-${index}`,
            cameraBinding: { ...viewCamera, revision: index },
            quality: 'failed',
            reasons: ['insufficientVisibility']
        }))
    ],
    planAttemptId: 'local-key-view-plan-attempt-1',
    artifactDigest: digest('1')
});

const promptRequest = (overrides = {}) => {
    const binding = requestBinding();
    const viewCameraBinding = cameraBinding();
    const rgb = pngArtifact(64, 48, 8);
    const hint = geometryHint(binding, rgb);
    const plan = localPlan(binding, viewCameraBinding, hint);
    return {
        requestBinding: binding,
        target: target(),
        viewId: 'generated-00',
        viewCameraBinding,
        viewCameraBindingDigest: cameraBindingDigest(viewCameraBinding),
        rgb,
        targetGeometryHint: hint,
        localKeyViewPlan: plan,
        adapterCapabilityDigest: digest('2'),
        modelManifestDigest: 'manifest-digest-1',
        runtimeDigest: digest('3'),
        companionInstanceId: 'companion-1',
        promptSynthesisAttemptId: 'generated-view-prompt-synthesis-attempt-1',
        promptSynthesisPolicyVersion:
            aiSelectImageInstancePromptSynthesisPolicyVersion,
        ...overrides
    };
};

const promptResponseFor = (request, overrides = {}) => {
    const prompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: request.requestBinding.targetContextId,
        contextRevision: request.requestBinding.contextRevision,
        viewId: request.viewId,
        rgbDigest: request.rgb.digest,
        cameraBindingDigest: request.viewCameraBindingDigest,
        targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
        localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        promptSynthesisPolicyDigest:
            aiSelectImageInstancePromptSynthesisPolicyDigest,
        positivePoints: [{ xPx: 5, yPx: 5 }],
        negativePoints: [],
        positiveBox: { x0Px: 4, y0Px: 4, x1Px: 8, y1Px: 8 },
        multimaskOutput: false
    });
    return {
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        viewId: request.viewId,
        viewCameraBindingDigest: request.viewCameraBindingDigest,
        rgbDigest: request.rgb.digest,
        targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
        localKeyViewPlanDigest: request.localKeyViewPlan.artifactDigest,
        adapterCapabilityDigest: request.adapterCapabilityDigest,
        modelManifestDigest: request.modelManifestDigest,
        runtimeDigest: request.runtimeDigest,
        companionInstanceId: request.companionInstanceId,
        promptSynthesisAttemptId: request.promptSynthesisAttemptId,
        promptSynthesisPolicyVersion:
            aiSelectImageInstancePromptSynthesisPolicyVersion,
        status: 'ready',
        diagnostics: ['projected-support:1'],
        prompt,
        ...overrides
    };
};

const assessmentFor = (rgb, mask) => ({
    status: 'review',
    primaryReason: 'severely-fragmented',
    reasons: ['severely-fragmented'],
    actionableReasons: ['severely-fragmented'],
    policyVersion: 'local-view-assessment/v2',
    inputIdentity: {
        rgbDigest: rgb.digest,
        stableMaskDigest: mask.digest,
        assessmentPolicyVersion: 'local-view-assessment/v2'
    },
    diagnostics: {
        framePixels: rgb.width * rgb.height,
        foregroundPixels: 40,
        boundaryPixels: 0,
        boundaryContactRatio: 0,
        connectedComponents: 2,
        largestComponentRatio: 0.5,
        promptPointCount: 1,
        promptViolationCount: 0,
        boxSpillPixels: null,
        boxSpillRatio: null
    }
});

const reviewRequest = (overrides = {}) => {
    const synthesis = promptRequest();
    const prompt = promptResponseFor(synthesis).prompt;
    const chosenMask = maskArtifact(64, 48);
    return {
        requestBinding: synthesis.requestBinding,
        target: synthesis.target,
        viewId: synthesis.viewId,
        rgb: synthesis.rgb,
        prompt,
        inferenceResultDigest: digest('4'),
        chosenMask,
        reviewAttemptId: 'generated-view-mask-review-attempt-1',
        reviewPolicyVersion: 'local-view-assessment/v2',
        ...overrides
    };
};

const reviewResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    viewId: request.viewId,
    rgbDigest: request.rgb.digest,
    promptArtifactDigest: request.prompt.artifactDigest,
    inferenceResultDigest: request.inferenceResultDigest,
    chosenMaskDigest: request.chosenMask.digest,
    reviewAttemptId: request.reviewAttemptId,
    reviewPolicyVersion: request.reviewPolicyVersion,
    assessment: assessmentFor(request.rgb, request.chosenMask),
    ...overrides
});

test('a complete Generated View render request validates', () => {
    assert.ok(isAIViewRenderRequest(renderRequest()));
});

test('render response validates only when its binding and PNG dimensions match', () => {
    const request = renderRequest();
    const response = renderResponseFor(request);
    assert.ok(isAIViewRenderResponse(response));
    assert.ok(viewRenderResponseMatchesRequest(response, request));
    assert.ok(
        !viewRenderResponseMatchesRequest(
            renderResponseFor(request, { viewId: 'generated-01' }),
            request
        )
    );
    assert.ok(
        !viewRenderResponseMatchesRequest(
            renderResponseFor(request, { renderStableGaussianIds: [2] }),
            request
        )
    );
});

test('Route B Prompt synthesis accepts one bound Positive Box and 1–3 Positive Points', () => {
    const request = promptRequest();
    const response = promptResponseFor(request);
    assert.ok(isGeneratedViewPromptSynthesisRequest(request));
    assert.ok(isGeneratedViewPromptSynthesisResponse(response));
    assert.ok(
        generatedViewPromptSynthesisResponseMatchesRequest(response, request)
    );
    assert.equal(response.prompt.multimaskOutput, false);
    assert.ok(response.prompt.positiveBox);
    assert.equal(response.prompt.positivePoints.length, 1);
    assert.equal(response.prompt.negativePoints.length, 0);
});

test('Route B inference rejects generic Image Instance Prompts without current geometry lineage', () => {
    const synthesis = promptRequest();
    const prompt = promptResponseFor(synthesis).prompt;
    const request = {
        schemaVersion: 1,
        identity: {
            targetContextId: synthesis.requestBinding.targetContextId,
            contextRevision: synthesis.requestBinding.contextRevision,
            viewId: synthesis.viewId,
            rgbDigest: synthesis.rgb.digest,
            promptArtifactDigest: prompt.artifactDigest,
            adapterId: 'sam3-image',
            modelManifestDigest: synthesis.modelManifestDigest,
            runtimeDigest: digest('7'),
            companionInstanceId: 'companion-1',
            inferenceAttemptId: 'generated-view-inference-attempt-1'
        },
        rgb: {
            rgbDigest: synthesis.rgb.digest,
            width: synthesis.rgb.width,
            height: synthesis.rgb.height,
            artifact: synthesis.rgb
        },
        prompt
    };
    assert.ok(isGeneratedViewImageInstanceMaskRequest(request));

    const genericPrompt = createImageInstancePromptArtifact({
        schemaVersion: 1,
        targetContextId: synthesis.requestBinding.targetContextId,
        contextRevision: synthesis.requestBinding.contextRevision,
        viewId: synthesis.viewId,
        rgbDigest: synthesis.rgb.digest,
        cameraBindingDigest: synthesis.viewCameraBindingDigest,
        adapterCapabilityDigest: synthesis.adapterCapabilityDigest,
        positivePoints: [{ xPx: 5, yPx: 5 }],
        negativePoints: [],
        positiveBox: { x0Px: 4, y0Px: 4, x1Px: 8, y1Px: 8 },
        multimaskOutput: false
    });
    assert.ok(
        !isGeneratedViewImageInstanceMaskRequest({
            ...request,
            identity: {
                ...request.identity,
                promptArtifactDigest: genericPrompt.artifactDigest
            },
            prompt: genericPrompt
        })
    );
});

test('Route B Prompt synthesis rejects stale plans, legacy payloads, logits, and removed prompt families', () => {
    const request = promptRequest();
    assert.ok(
        !isGeneratedViewPromptSynthesisRequest({
            ...request,
            viewCameraBindingDigest: digest('9')
        })
    );
    assert.ok(
        !isGeneratedViewPromptSynthesisResponse({
            ...promptResponseFor(request),
            maskPropagation: { policyVersion: 'generated-view-mask/v1' }
        })
    );
    const response = promptResponseFor(request);
    assert.ok(
        !isGeneratedViewPromptSynthesisResponse({
            ...response,
            prompt: {
                ...response.prompt,
                previousLogitsRefDigest: digest('9')
            }
        })
    );
    assert.ok(
        !isGeneratedViewPromptSynthesisResponse({
            ...response,
            prompt: {
                ...response.prompt,
                negativeBox: { x0Px: 1, y0Px: 1, x1Px: 2, y1Px: 2 }
            }
        })
    );
});

test('limited Prompt synthesis is structured recovery and cannot carry a Mask prompt', () => {
    const request = promptRequest();
    const response = {
        ...promptResponseFor(request),
        status: 'limited',
        diagnostics: ['sparse-projectable-support']
    };
    delete response.prompt;
    assert.ok(isGeneratedViewPromptSynthesisResponse(response));
    assert.ok(
        generatedViewPromptSynthesisResponseMatchesRequest(response, request)
    );
    assert.ok(
        !isGeneratedViewPromptSynthesisResponse({
            ...response,
            prompt: promptResponseFor(request).prompt
        })
    );
});

test('Mask Review accepts only one exact inference-produced Mask and binding', () => {
    const request = reviewRequest();
    const response = reviewResponseFor(request);
    assert.ok(isImageInstanceMaskReviewRequest(request));
    assert.ok(isImageInstanceMaskReviewResponse(response));
    assert.ok(imageInstanceMaskReviewResponseMatchesRequest(response, request));
    assert.ok(
        !imageInstanceMaskReviewResponseMatchesRequest(
            reviewResponseFor(request, { inferenceResultDigest: digest('9') }),
            request
        )
    );
    assert.ok(
        !isImageInstanceMaskReviewResponse({
            ...response,
            maskSource: 'propagated'
        })
    );
});
