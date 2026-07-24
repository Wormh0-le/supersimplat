const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const target = (splatId = 'editor-splat:1') => ({ splatId });

const snapshot = {
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
    renderConfiguration: {
        version: 'supersplat-effective-rgb-v1'
    }
};

const editorCamera = () => ({
    targetSize: { width: 640, height: 480 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
    }
});

const cameraBinding = () => captureEditorCameraBinding(editorCamera());

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

const pngBytes = (width, height, imageData = null) => {
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

const pngBase64 = (width, height) => {
    return pngBytes(width, height).toString('base64');
};

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const input = (overrides = {}) => ({
    target: target(),
    dependencyToken: dependency(),
    getCurrentDependencyToken: () => dependency(),
    snapshot,
    cameraBinding: cameraBinding(),
    ...overrides
});

const responseFor = (request) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.snapshot.sceneId,
    sceneVersion: request.snapshot.sceneVersion,
    renderConfigVersion: 'supersplat-effective-rgb-v1',
    renderAttemptId: request.renderAttemptId,
    viewId: 'anchor-view',
    cameraBinding: request.cameraBinding,
    rgb: {
        pngBase64: pngBase64(
            request.cameraBinding.projection.width,
            request.cameraBinding.projection.height
        ),
        digest: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

test('copies the Current Scene View into an immutable OpenCV CameraBinding without moving it', () => {
    const camera = editorCamera();
    const binding = captureEditorCameraBinding(camera);

    assert.equal(binding.revision, 0);
    assert.equal(binding.conventionVersion, 'opencv-camera-to-world/v1');
    assert.deepEqual(
        binding.cameraToWorld,
        [1, 0, 0, 2, 0, -1, 0, 3, 0, 0, -1, 4, 0, 0, 0, 1]
    );
    assert.equal(binding.projection.width, 640);
    assert.equal(binding.projection.height, 480);
    assert.equal(binding.projection.cx, 320);
    assert.equal(binding.projection.cy, 240);
    assert.equal(binding.projection.near, 0.1);
    assert.equal(binding.projection.far, 100);
    assert.ok(Math.abs(binding.projection.fx - 415.69219381653056) < 1e-9);
    assert.ok(Math.abs(binding.projection.fy - 415.69219381653056) < 1e-9);

    camera.worldTransform.data[12] = 99;
    camera.targetSize.width = 1;
    assert.equal(binding.cameraToWorld[3], 2);
    assert.equal(binding.projection.width, 640);
});

test('rejects an orthographic Current Scene View instead of silently changing it to pinhole', () => {
    assert.throws(
        () => captureEditorCameraBinding({ ...editorCamera(), ortho: true }),
        /perspective/i
    );
});

test('starts an Anchor AIView in Rendering state and publishes only the bound authoritative RGB', async () => {
    const rendering = deferred();
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            renderAnchor(request) {
                requests.push(request);
                return rendering.promise;
            }
        }
    });

    const start = controller.start(input());

    assert.equal(controller.state.context.lifecycle, 'active');
    assert.equal(controller.state.anchor.viewId, 'anchor-view');
    assert.equal(controller.state.anchor.renderStatus, 'rendering');
    assert.equal(requests.length, 1);
    assert.equal(
        requests[0].requestBinding.targetContextId,
        controller.state.context.targetContextId
    );
    assert.deepEqual(
        requests[0].cameraBinding,
        controller.state.anchor.cameraBinding
    );

    rendering.resolve(responseFor(requests[0]));
    await start;

    assert.equal(controller.state.anchor.renderStatus, 'ready');
    assert.equal(
        controller.state.anchor.rgb.digest,
        responseFor(requests[0]).rgb.digest
    );
    assert.equal(controller.state.anchor.rendererId, 'gsplat');
});

test('discards a late Anchor response after Restart Current Target creates a new context', async () => {
    const first = deferred();
    const second = deferred();
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            renderAnchor(request) {
                requests.push(request);
                return requests.length === 1 ? first.promise : second.promise;
            }
        }
    });

    const firstStart = controller.start(input());
    const firstContextId = controller.state.context.targetContextId;
    const secondStart = controller.restart(
        input({
            cameraBinding: {
                ...cameraBinding(),
                revision: 1
            }
        })
    );
    const secondContextId = controller.state.context.targetContextId;

    assert.notEqual(secondContextId, firstContextId);
    assert.equal(controller.state.anchor.renderStatus, 'rendering');

    first.resolve(responseFor(requests[0]));
    await firstStart;
    assert.equal(controller.state.context.targetContextId, secondContextId);
    assert.equal(controller.state.anchor.renderStatus, 'rendering');

    second.resolve(responseFor(requests[1]));
    await secondStart;
    assert.equal(controller.state.context.targetContextId, secondContextId);
    assert.equal(controller.state.anchor.renderStatus, 'ready');
});

test('releases Companion-local snapshot residency only after an exited Anchor render settles', async () => {
    const rendering = deferred();
    const released = [];
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            renderAnchor(request) {
                requests.push(request);
                return rendering.promise;
            },
            async releaseSceneSnapshot(request) {
                released.push(request);
            }
        }
    });

    const start = controller.start(input());
    controller.exit();

    assert.equal(controller.state.context, null);
    assert.deepEqual(released, []);

    rendering.resolve(responseFor(requests[0]));
    await start;

    assert.equal(released.length, 1);
    assert.equal(
        released[0].snapshot.contentDigest,
        requests[0].snapshot.contentDigest
    );
});

test('releases an idle superseded snapshot when Restart Current Target binds a new scene version', async () => {
    const released = [];
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                return responseFor(request);
            },
            async releaseSceneSnapshot(request) {
                released.push(request);
            }
        }
    });

    await controller.start(input());
    await controller.restart(
        input({
            snapshot: {
                ...snapshot,
                sceneVersion: 'snapshot-v2',
                contentDigest:
                    'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
            }
        })
    );

    assert.equal(released.length, 1);
    assert.equal(released[0].snapshot.sceneVersion, 'snapshot-v1');
});

test('discards an Anchor result after the editor semantic dependency changes', async () => {
    const rendering = deferred();
    let effectiveDependency = dependency();
    const controller = new AISelectAnchorController({
        renderer: {
            renderAnchor() {
                return rendering.promise;
            }
        }
    });

    const start = controller.start(
        input({
            getCurrentDependencyToken: () => effectiveDependency
        })
    );
    effectiveDependency = dependency({ geometryToken: 'geometry-v2' });
    rendering.resolve(
        responseFor({
            requestBinding: controller.state.anchor.requestBinding,
            target: target(),
            snapshot,
            cameraBinding: controller.state.anchor.cameraBinding
        })
    );
    await start;

    assert.equal(controller.state.context.lifecycle, 'suspended');
    assert.equal(controller.state.anchor.renderStatus, 'rendering');
    assert.deepEqual(controller.getAnchorCameraBinding(), cameraBinding());
});

test('keeps an Anchor render failure local to the AI view and can exit without a native-selection side effect', async () => {
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor() {
                throw new Error('gsplat is unavailable');
            }
        }
    });

    await controller.start(input());

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(controller.state.anchor.errorMessage, /gsplat is unavailable/);

    controller.exit();
    assert.equal(controller.state.context, null);
    assert.equal(controller.state.anchor, null);
});

test('keeps interactive and stale final responses from replacing the newest fixed Anchor revision', async () => {
    const requests = [];
    const renders = [];
    const controller = new AISelectAnchorController({
        renderer: {
            renderAnchor(request) {
                requests.push(request);
                const rendering = deferred();
                renders.push(rendering);
                return rendering.promise;
            }
        }
    });

    const start = controller.start(input());
    renders[0].resolve(responseFor(requests[0]));
    await start;

    controller.updateAnchorCameraPose([
        1, 0, 0, 7, 0, -1, 0, 8, 0, 0, -1, 9, 0, 0, 0, 1
    ]);
    const staleFinal = controller.renderFinalPreview();

    controller.updateAnchorCameraPose([
        1, 0, 0, 10, 0, -1, 0, 11, 0, 0, -1, 12, 0, 0, 0, 1
    ]);
    const interactive = controller.renderInteractivePreview();
    const newestFinal = controller.renderFinalPreview();

    assert.ok(
        requests[2].cameraBinding.projection.width <
            requests[3].cameraBinding.projection.width
    );

    renders[3].resolve({
        ...responseFor(requests[3]),
        rgb: {
            ...responseFor(requests[3]).rgb,
            digest: 'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
        }
    });
    await newestFinal;

    renders[2].resolve({
        ...responseFor(requests[2]),
        rgb: {
            ...responseFor(requests[2]).rgb,
            digest: 'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'
        }
    });
    renders[1].resolve({
        ...responseFor(requests[1]),
        rgb: {
            ...responseFor(requests[1]).rgb,
            digest: 'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
        }
    });
    await Promise.all([interactive, staleFinal]);

    assert.equal(controller.state.anchor.cameraBinding.cameraToWorld[3], 10);
    assert.equal(controller.state.anchor.renderStatus, 'ready');
    assert.equal(
        controller.state.anchor.rgb.digest,
        'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
    );
});

test('Reset Anchor restores the initial CameraBinding pose and rerenders it at final resolution', async () => {
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                requests.push(request);
                return responseFor(request);
            }
        }
    });

    await controller.start(input());
    controller.updateAnchorCameraPose([
        1, 0, 0, 90, 0, -1, 0, 91, 0, 0, -1, 92, 0, 0, 0, 1
    ]);

    await controller.resetAnchor();

    assert.equal(requests.length, 2);
    assert.deepEqual(
        requests[1].cameraBinding.cameraToWorld,
        [1, 0, 0, 2, 0, -1, 0, 3, 0, 0, -1, 4, 0, 0, 0, 1]
    );
    assert.equal(
        requests[1].cameraBinding.projection.width,
        cameraBinding().projection.width
    );
    assert.equal(controller.state.anchor.renderStatus, 'ready');
});

test('preserves a valid preview when the current final render fails and retries it', async () => {
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                requests.push(request);
                if (requests.length === 2) {
                    throw new Error('temporary gsplat failure');
                }
                return responseFor(request);
            }
        }
    });

    await controller.start(input());
    const firstDigest = controller.state.anchor.rgb.digest;
    controller.updateAnchorCameraPose([
        1, 0, 0, 20, 0, -1, 0, 21, 0, 0, -1, 22, 0, 0, 0, 1
    ]);
    await controller.renderFinalPreview();

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.equal(controller.state.anchor.preview.renderStatus, 'failed');
    assert.equal(
        controller.state.anchor.lastValidPreview.rgb.digest,
        firstDigest
    );

    await controller.retryAnchorPreview();

    assert.equal(requests.length, 3);
    assert.deepEqual(requests[2].cameraBinding, requests[1].cameraBinding);
    // The explicit user Retry mints a fresh render-attempt identity for the
    // same CameraBinding instead of replaying the cached failed attempt.
    assert.notEqual(requests[2].renderAttemptId, requests[1].renderAttemptId);
    assert.equal(controller.state.anchor.renderStatus, 'ready');
    assert.equal(controller.state.anchor.cameraBinding.cameraToWorld[3], 20);
});

test('mints a distinct render-attempt identity for every actual render execution', async () => {
    const requests = [];
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                requests.push(request);
                return responseFor(request);
            }
        }
    });

    await controller.start(input());
    await controller.renderFinalPreview();
    await controller.retryAnchorPreview();

    assert.equal(requests.length, 3);
    const attemptIds = requests.map((request) => request.renderAttemptId);
    assert.equal(new Set(attemptIds).size, requests.length);
    attemptIds.forEach((attemptId) => {
        assert.equal(typeof attemptId, 'string');
        assert.ok(attemptId.length > 0);
    });
    // Every attempt reused the same semantic CameraBinding without jitter.
    requests.forEach((request) => {
        assert.deepEqual(request.cameraBinding, requests[0].cameraBinding);
    });
});

test('rejects an Anchor response bound to a different render attempt', async () => {
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                return {
                    ...responseFor(request),
                    renderAttemptId: `${request.renderAttemptId}-stale`
                };
            }
        }
    });

    await controller.start(input());

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(
        controller.state.anchor.errorMessage,
        /invalid Anchor render binding/i
    );
});

test('rejects an Anchor response from an unsupported RGB renderer version', async () => {
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(request) {
                return {
                    ...responseFor(request),
                    rgbRendererVersion: 'flashsplat-same-decision/v1'
                };
            }
        }
    });

    await controller.start(input());

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(
        controller.state.anchor.errorMessage,
        /invalid Anchor render binding/i
    );
});

test('rejects an Anchor response whose actual PNG raster dimensions differ from its CameraBinding', async () => {
    let request;
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(anchorRequest) {
                request = anchorRequest;
                return {
                    ...responseFor(anchorRequest),
                    rgb: {
                        ...responseFor(anchorRequest).rgb,
                        pngBase64: pngBase64(1, 1)
                    }
                };
            }
        }
    });

    await controller.start(input());

    assert.ok(request);
    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(
        controller.state.anchor.errorMessage,
        /invalid Anchor render binding/i
    );
});

test('rejects a truncated Anchor PNG even when its binding fields are otherwise valid', async () => {
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(anchorRequest) {
                const truncated = pngBytes(
                    anchorRequest.cameraBinding.projection.width,
                    anchorRequest.cameraBinding.projection.height
                ).subarray(0, -12);
                return {
                    ...responseFor(anchorRequest),
                    rgb: {
                        ...responseFor(anchorRequest).rgb,
                        pngBase64: truncated.toString('base64')
                    }
                };
            }
        }
    });

    await controller.start(input());

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(
        controller.state.anchor.errorMessage,
        /invalid Anchor render binding/i
    );
});

test('rejects an Anchor PNG whose CRC-valid IDAT stream cannot be decoded', async () => {
    const controller = new AISelectAnchorController({
        renderer: {
            async renderAnchor(anchorRequest) {
                return {
                    ...responseFor(anchorRequest),
                    rgb: {
                        ...responseFor(anchorRequest).rgb,
                        pngBase64: pngBytes(
                            anchorRequest.cameraBinding.projection.width,
                            anchorRequest.cameraBinding.projection.height,
                            Buffer.from([0x78, 0x9c, 0x00])
                        ).toString('base64')
                    }
                };
            }
        }
    });

    await controller.start(input());

    assert.equal(controller.state.anchor.renderStatus, 'failed');
    assert.match(
        controller.state.anchor.errorMessage,
        /invalid Anchor render binding/i
    );
});
