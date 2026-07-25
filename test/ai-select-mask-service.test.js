const assert = require('node:assert/strict');
const test = require('node:test');

const {
    isAIViewMaskRequest,
    isMaskResultResponse,
    maskResponseMatchesRequest
} = require('../.test-dist/src/ai-select/mask-service.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const bitsetArtifact = (width, height, firstByte) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    bytes[0] = firstByte;
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

const request = (overrides = {}) => ({
    requestBinding: {
        targetContextId: 'ai-target-context-1',
        contextRevision: 3,
        dependencyToken: {
            splatId: 'editor-splat:1',
            renderStateToken: 'render-v1',
            geometryToken: 'geometry-v1',
            gaussianIdentityToken: 'gaussians-v1',
            worldTransformToken: 'transform-v1'
        }
    },
    target: { splatId: 'editor-splat:1' },
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    viewId: 'anchor-view',
    maskAttemptId: 'mask-attempt-7',
    rgb: {
        pngBase64: 'aGVsbG8=',
        digest: digest('a'),
        width: 8,
        height: 8
    },
    prompts: [{ promptId: 'p-1', xPx: 2, yPx: 2, polarity: 'include' }],
    modelManifestDigest: 'modelscope-facebook-sam31-616acbee',
    ...overrides
});

const responseFor = (req, overrides = {}) => ({
    requestBinding: req.requestBinding,
    targetSplatId: req.target.splatId,
    sceneId: req.sceneId,
    sceneVersion: req.sceneVersion,
    viewId: req.viewId,
    maskAttemptId: req.maskAttemptId,
    rgbDigest: req.rgb.digest,
    mask: bitsetArtifact(req.rgb.width, req.rgb.height, 0b101),
    maskSource: 'single-frame-sam',
    modelManifestDigest: req.modelManifestDigest,
    ...overrides
});

test('a complete bound mask response matches its request', () => {
    const req = request();
    const response = responseFor(req);
    assert.ok(isMaskResultResponse(response));
    assert.ok(maskResponseMatchesRequest(response, req));
});

test('the request contract requires bound identity, RGB, and prompts', () => {
    assert.ok(isAIViewMaskRequest(request()));
    assert.ok(!isAIViewMaskRequest(request({ prompts: [] })));
    assert.ok(!isAIViewMaskRequest(request({ maskAttemptId: '' })));
    assert.ok(!isAIViewMaskRequest(request({ modelManifestDigest: '' })));
    assert.ok(
        !isAIViewMaskRequest(
            request({
                prompts: [
                    { promptId: 'p', xPx: -1, yPx: 0, polarity: 'include' }
                ]
            })
        )
    );
    const mismatchedTarget = request();
    mismatchedTarget.target = { splatId: 'other-splat' };
    assert.ok(!isAIViewMaskRequest(mismatchedTarget));
});

test('stale or partial responses are rejected', () => {
    const req = request();
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { rgbDigest: digest('b') }),
            req
        )
    );
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { maskAttemptId: 'mask-attempt-8' }),
            req
        )
    );
    assert.ok(
        !maskResponseMatchesRequest(responseFor(req, { viewId: 'view-2' }), req)
    );
    const wrongRevision = responseFor(req);
    wrongRevision.requestBinding = {
        ...req.requestBinding,
        contextRevision: 4
    };
    assert.ok(!maskResponseMatchesRequest(wrongRevision, req));
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, {
                mask: bitsetArtifact(req.rgb.width + 8, req.rgb.height, 0b101)
            }),
            req
        )
    );
    const tamperedBytes = bitsetArtifact(req.rgb.width, req.rgb.height, 0b101);
    tamperedBytes.data = bitsetArtifact(
        req.rgb.width,
        req.rgb.height,
        0b111
    ).data;
    assert.ok(
        !maskResponseMatchesRequest(
            responseFor(req, { mask: tamperedBytes }),
            req
        )
    );
    assert.ok(
        !isMaskResultResponse(responseFor(req, { maskSource: 'propagated' }))
    );
    assert.ok(!isMaskResultResponse({ status: 'maskError' }));
});
