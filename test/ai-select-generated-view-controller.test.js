const assert = require('node:assert/strict');
const test = require('node:test');
const { deflateSync } = require('node:zlib');

const {
    AISelectAnchorController
} = require('../.test-dist/src/ai-select/anchor-controller.js');
const {
    AISelectGeneratedViewController
} = require('../.test-dist/src/ai-select/generated-view-controller.js');
const {
    aiSelectGeneratedViewMaskPolicyVersion,
    aiSelectGeneratedViewPlannerVersion
} = require('../.test-dist/src/ai-select/generated-view-service.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    PerViewEvidenceRegistry
} = require('../.test-dist/src/ai-select/evidence-state.js');
const {
    maskBitsetEncoding
} = require('../.test-dist/src/ai-select/mask-annotation.js');
const {
    MaskAnnotationRegistry
} = require('../.test-dist/src/ai-select/mask-registry.js');
const { sha256Digest } = require('../.test-dist/src/scene-snapshot-binary.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const target = () => ({ splatId: 'editor-splat:1' });

const snapshot = {
    sceneId: 'editor-splat:1',
    sceneVersion: 'snapshot-v1',
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

const bitsetArtifact = (width, height, foreground) => {
    const bytes = new Uint8Array(Math.ceil((width * height) / 8));
    for (const [x, y] of foreground) {
        const index = y * width + x;
        bytes[index >> 3] |= 1 << (index % 8);
    }
    let binary = '';
    for (const byte of bytes) {
        binary += String.fromCharCode(byte);
    }
    return Object.freeze({
        encoding: maskBitsetEncoding,
        width,
        height,
        data: btoa(binary),
        digest: sha256Digest(bytes)
    });
};

const anchorStableMaskAnnotation = (digest) =>
    Object.freeze({
        maskId: 'mask-anchor-stable',
        viewId: 'anchor-view',
        source: 'single-frame-sam',
        status: 'user-confirmed',
        artifact: bitsetArtifact(64, 48, [
            [4, 4],
            [5, 4]
        ]),
        createdFromRgbDigest: digest
    });

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const flush = () => new Promise((resolve) => setImmediate(resolve));

const anchorRenderResponseFor = (request) => ({
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
        digest: rgbDigest('a'),
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

/** A controllable confirmation seam with the exact subscribe/state contract. */
const createConfirmationStub = () => {
    const listeners = new Set();
    let state = Object.freeze({
        validation: null,
        validationStatus: 'idle',
        confirmedAnchor: null
    });
    const publish = () => listeners.forEach((listener) => listener(state));
    return {
        get state() {
            return state;
        },
        subscribe(listener) {
            listeners.add(listener);
            listener(state);
            return () => listeners.delete(listener);
        },
        confirm(confirmedAnchor) {
            state = Object.freeze({ ...state, confirmedAnchor });
            publish();
        },
        adjust() {
            state = Object.freeze({ ...state, confirmedAnchor: null });
            publish();
        }
    };
};

const confirmedAnchorFor = (anchorController, overrides = {}) => {
    const { context, anchor } = anchorController.state;
    assert.ok(context && anchor?.renderStatus === 'ready' && anchor.rgb);
    return Object.freeze({
        targetContextId: context.targetContextId,
        contextRevision: context.revision,
        cameraBinding: anchor.cameraBinding,
        rgbDigest: anchor.rgb.digest,
        stableMask: anchorStableMaskAnnotation(anchor.rgb.digest),
        maskEvidencePolicyVersion: 'evidence-policy/pnv-v0',
        dependencyToken: context.dependencyToken,
        sceneId: snapshot.sceneId,
        sceneVersion: snapshot.sceneVersion,
        ...overrides
    });
};

const createHarness = (options = {}) => {
    const anchorController = new AISelectAnchorController({
        renderer: {
            renderAnchor: async (request) => anchorRenderResponseFor(request)
        }
    });
    const confirmation = createConfirmationStub();
    const maskRegistry = new MaskAnnotationRegistry();
    const evidenceRegistry = new PerViewEvidenceRegistry();
    const planner = {
        calls: [],
        next: deferred(),
        planGeneratedViews(request) {
            this.calls.push(request);
            return this.next.promise;
        }
    };
    const viewRenderer = {
        calls: [],
        deferreds: [],
        renderView(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const maskProvider = {
        calls: [],
        deferreds: [],
        produceGeneratedViewMask(request) {
            this.calls.push(request);
            const next = deferred();
            this.deferreds.push(next);
            return next.promise;
        }
    };
    const controller = new AISelectGeneratedViewController({
        anchor: anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        planner,
        renderer: viewRenderer,
        maskProvider,
        getModelManifestDigest: () => 'manifest-digest-1',
        supportsGeneratedViews: options.supportsGeneratedViews ?? (() => true)
    });
    return {
        anchorController,
        confirmation,
        maskRegistry,
        evidenceRegistry,
        planner,
        viewRenderer,
        maskProvider,
        controller
    };
};

const startAnchor = async (harness) => {
    await harness.anchorController.start({
        target: target(),
        dependencyToken: dependency(),
        getCurrentDependencyToken: () => dependency(),
        snapshot,
        cameraBinding: cameraBinding()
    });
    assert.equal(harness.anchorController.state.anchor?.renderStatus, 'ready');
};

const plannedView = (viewId, revision) => ({
    viewId,
    cameraBinding: Object.freeze({
        ...cameraBinding(),
        revision
    })
});

const planResponseFor = (request, views) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    sceneId: request.sceneId,
    sceneVersion: request.sceneVersion,
    renderConfigVersion: request.snapshot.renderConfiguration.version,
    planAttemptId: request.planAttemptId,
    plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion,
    views: views ?? [
        plannedView('generated-00', 100),
        plannedView('generated-01', 101)
    ]
});

const viewRenderResponseFor = (request, digest = rgbDigest('b')) => ({
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
        digest,
        width: request.cameraBinding.projection.width,
        height: request.cameraBinding.projection.height
    },
    rgbRendererVersion: 'gsplat-rgb/v1',
    rendererId: 'gsplat'
});

const maskResponseFor = (request, assessmentOverrides = {}) => {
    const mask = bitsetArtifact(64, 48, [
        [4, 4],
        [5, 4],
        [6, 4]
    ]);
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
            projectedSupportCount: 9,
            promptCount: 3
        },
        assessment: {
            status: 'review',
            primaryReason: 'severely-fragmented',
            reasons: ['severely-fragmented'],
            actionableReasons: ['severely-fragmented'],
            policyVersion: 'local-view-assessment/v2',
            inputIdentity: {
                rgbDigest: request.rgb.digest,
                stableMaskDigest: mask.digest,
                assessmentPolicyVersion: 'local-view-assessment/v2'
            },
            diagnostics: {
                framePixels: 3072,
                foregroundPixels: 40,
                boundaryPixels: 0,
                boundaryContactRatio: 0,
                connectedComponents: 2,
                largestComponentRatio: 0.5,
                promptPointCount: 3,
                promptViolationCount: 0,
                boxSpillPixels: null,
                boxSpillRatio: null
            },
            ...assessmentOverrides
        },
        modelManifestDigest: request.modelManifestDigest
    };
};

/** Drive the whole happy path to two fully published Generated Views. */
const completeTwoViews = async (harness) => {
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 1);
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    assert.equal(harness.maskProvider.calls.length, 1);
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 2);
    harness.viewRenderer.deferreds[1].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[1], rgbDigest('d'))
    );
    await flush();
    assert.equal(harness.maskProvider.calls.length, 2);
    harness.maskProvider.deferreds[1].resolve(
        maskResponseFor(harness.maskProvider.calls[1])
    );
    await flush();
};

test('Confirm Anchor starts automatic planning without a fixed user View count', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.planner.calls.length, 0);

    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'planning');
    assert.equal(harness.planner.calls.length, 1);
    const request = harness.planner.calls[0];
    const context = harness.anchorController.state.context;
    assert.equal(
        request.requestBinding.targetContextId,
        context.targetContextId
    );
    assert.equal(request.requestBinding.contextRevision, context.revision);
    assert.deepEqual(request.requestBinding.dependencyToken, dependency());
    assert.equal(request.target.splatId, 'editor-splat:1');
    assert.equal(request.sceneId, snapshot.sceneId);
    assert.equal(request.sceneVersion, snapshot.sceneVersion);
    assert.equal(request.anchorRgbDigest, rgbDigest('a'));
    assert.equal(request.anchorStableMask.encoding, maskBitsetEncoding);
    assert.equal(
        request.plannerPolicyVersion,
        aiSelectGeneratedViewPlannerVersion
    );
    assert.ok(request.planAttemptId.length > 0);
});

test('a Generated AIView publishes RGB Ready while its Mask is still Generating', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();

    let views = harness.controller.state.views;
    assert.equal(harness.controller.state.plannerStatus, 'active');
    assert.equal(views.length, 2);
    assert.equal(views[0].renderStatus, 'rendering');
    assert.equal(views[1].renderStatus, 'pending');

    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();

    views = harness.controller.state.views;
    // Progressive publication: RGB Ready + Mask Generating + Evidence Not
    // Requested is a legal state; the View never waits for its Mask.
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].rgbDigest, rgbDigest('b'));
    assert.equal(views[0].maskStatus, 'generating');
    assert.equal(views[0].evidenceStatus, 'not-requested');
    assert.equal(views[0].source, 'auto-generated');
    assert.equal(views[0].participation, 'excluded');
    assert.equal(views[1].renderStatus, 'pending');
    // The render request bound the exact planned CameraBinding and view id.
    assert.equal(harness.viewRenderer.calls[0].viewId, 'generated-00');
    assert.deepEqual(
        harness.viewRenderer.calls[0].cameraBinding,
        plannedView('generated-00', 100).cameraBinding
    );

    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();
    views = harness.controller.state.views;
    assert.equal(views[0].maskStatus, 'ready');
    assert.ok(views[0].stableMaskId);
});

test('a successful automatic Mask atomically publishes an auto Stable Mask bound to the View RGB', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    await completeTwoViews(harness);

    const views = harness.controller.state.views;
    assert.equal(views.length, 2);
    assert.ok(views.every((view) => view.renderStatus === 'ready'));
    assert.ok(views.every((view) => view.maskStatus === 'ready'));

    const stable = harness.maskRegistry.viewState(
        'generated-00',
        rgbDigest('b')
    ).stableMask;
    assert.ok(stable);
    assert.equal(stable.maskId, views[0].stableMaskId);
    assert.equal(stable.source, 'propagated');
    assert.equal(stable.status, 'auto-review');
    assert.equal(stable.createdFromRgbDigest, rgbDigest('b'));

    // The mask request bound the Generated View RGB, its exact CameraBinding,
    // and the confirmed Anchor Camera/RGB/Stable-Mask identity.
    const maskRequest = harness.maskProvider.calls[0];
    assert.equal(maskRequest.viewId, 'generated-00');
    assert.equal(maskRequest.rgb.digest, rgbDigest('b'));
    assert.equal(maskRequest.anchor.rgbDigest, rgbDigest('a'));
    assert.equal(maskRequest.anchor.stableMask.encoding, maskBitsetEncoding);
    assert.deepEqual(
        maskRequest.anchor.cameraBinding,
        harness.anchorController.state.anchor.cameraBinding
    );

    // Publishing the Stable Mask marks Evidence missing/dirty only; no Lift.
    assert.equal(views[0].evidenceStatus, 'not-requested');
    assert.equal(views[0].assessment.status, 'review');
    assert.deepEqual(views[0].assessment.reasons, ['severely-fragmented']);
    assert.equal(views[0].maskQuality, 'auto-review');
    assert.equal(views[0].participation, 'excluded');
});

test('Auto Good defaults Included while View source remains non-authoritative', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0], {
            status: 'good',
            primaryReason: undefined,
            reasons: [],
            actionableReasons: []
        })
    );
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.source, 'auto-generated');
    assert.equal(view.maskQuality, 'auto-good');
    assert.equal(view.participation, 'included');
});

test('Assessment Failed preserves the Stable Mask but remains Excluded without reasons', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    const response = maskResponseFor(harness.maskProvider.calls[0], {
        status: 'failed',
        primaryReason: undefined,
        reasons: [],
        actionableReasons: [],
        diagnostics: undefined
    });
    harness.maskProvider.deferreds[0].resolve(response);
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'ready');
    assert.ok(view.stableMaskId);
    assert.equal(view.assessment.status, 'failed');
    assert.deepEqual(view.assessment.reasons, []);
    assert.equal(view.maskQuality, 'failed');
    assert.equal(view.participation, 'excluded');
});

test('Confirm Review as-is publishes User Confirmed authority and Included participation', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    harness.controller.confirmReviewAsIs('generated-00');

    const view = harness.controller.state.views[0];
    assert.equal(view.assessment, undefined);
    assert.equal(view.maskQuality, 'user-confirmed');
    assert.equal(view.participation, 'included');
    const stable = harness.maskRegistry.viewState(
        'generated-00',
        rgbDigest('b')
    ).stableMask;
    assert.equal(stable.status, 'user-confirmed');

    harness.controller.setViewParticipation('generated-00', 'excluded');
    assert.equal(harness.controller.state.views[0].participation, 'excluded');
    assert.equal(
        harness.controller.state.views[0].maskQuality,
        'user-confirmed'
    );
});

test('a replacement Stable Mask hides assessment reasons bound to the previous revision', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0], {
            status: 'good',
            primaryReason: undefined,
            reasons: [],
            actionableReasons: []
        })
    );
    await flush();
    assert.equal(harness.controller.state.views[0].participation, 'included');

    harness.maskRegistry.publishAutoStable({
        viewId: 'generated-00',
        rgbDigest: rgbDigest('b'),
        artifact: bitsetArtifact(64, 48, [[20, 20]]),
        source: 'propagated',
        status: 'auto-review'
    });

    const view = harness.controller.state.views[0];
    assert.equal(view.assessment, undefined);
    assert.equal(view.maskQuality, 'auto-review');
    assert.equal(view.participation, 'excluded');
});

test('Mask failure keeps the AIView, RGB, and frustum binding: RGB Ready + Mask Failed', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].reject(new Error('SAM exploded'));
    await flush();

    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'failed');
    assert.match(view.maskErrorMessage, /SAM exploded/);
    assert.equal(view.rgbDigest, rgbDigest('b'));
    assert.equal(view.stableMaskId, undefined);
    assert.equal(view.participation, 'excluded');
    assert.equal(view.maskQuality, 'failed');

    harness.viewRenderer.deferreds[1].reject(new Error('skip second view'));
    await flush();
    harness.controller.retryViewMask('generated-00');
    await flush();
    assert.equal(harness.maskProvider.calls.length, 2);
    assert.notEqual(
        harness.maskProvider.calls[1].maskAttemptId,
        harness.maskProvider.calls[0].maskAttemptId
    );
    assert.equal(harness.controller.state.views[0].maskStatus, 'generating');
});

test('Render failure preserves a distinct failed View record; completed Views survive', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();

    // First view completes fully.
    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();
    // Second view render fails.
    harness.viewRenderer.deferreds[1].reject(new Error('GPU OOM'));
    await flush();

    const views = harness.controller.state.views;
    assert.equal(views[0].renderStatus, 'ready');
    assert.equal(views[0].maskStatus, 'ready');
    assert.equal(views[1].renderStatus, 'failed');
    assert.match(views[1].renderErrorMessage, /GPU OOM/);
    assert.equal(views[1].maskStatus, 'none');
    assert.equal(views[1].rgbDigest, undefined);
});

test('a true Render Retry creates a new attempt for the same CameraBinding and actually re-renders', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    harness.viewRenderer.deferreds[0].reject(new Error('transient'));
    await flush();

    // The failed first View does not block the second View's pipeline.
    harness.viewRenderer.deferreds[1].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[1], rgbDigest('d'))
    );
    await flush();
    harness.maskProvider.deferreds[0].resolve(
        maskResponseFor(harness.maskProvider.calls[0])
    );
    await flush();

    const failed = harness.controller.state.views[0];
    assert.equal(failed.renderStatus, 'failed');
    const firstAttemptId = harness.viewRenderer.calls[0].renderAttemptId;

    harness.controller.retryViewRender('generated-00');
    await flush();
    assert.equal(harness.viewRenderer.calls.length, 3);
    const retryRequest = harness.viewRenderer.calls[2];
    assert.equal(retryRequest.viewId, 'generated-00');
    assert.notEqual(retryRequest.renderAttemptId, firstAttemptId);
    assert.deepEqual(
        retryRequest.cameraBinding,
        harness.viewRenderer.calls[0].cameraBinding
    );

    harness.viewRenderer.deferreds[2].resolve(
        viewRenderResponseFor(retryRequest)
    );
    await flush();
    const view = harness.controller.state.views[0];
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.maskStatus, 'generating');
});

test('planner failure keeps every completed state and exposes a true planning Retry', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.reject(new Error('planner exploded'));
    await flush();

    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /planner exploded/
    );
    assert.equal(harness.controller.state.views.length, 0);

    harness.planner.next = deferred();
    harness.controller.retryPlanning();
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    assert.notEqual(
        harness.planner.calls[1].planAttemptId,
        harness.planner.calls[0].planAttemptId
    );
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[1]));
    await flush();
    assert.equal(harness.controller.state.views.length, 2);
});

test('Adjust Anchor disposes every Generated View and discards late results', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    harness.planner.next.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();

    // The first View is mid-render when the Anchor confirmation is discarded.
    harness.confirmation.adjust();
    await flush();
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(harness.controller.state.views.length, 0);

    harness.viewRenderer.deferreds[0].resolve(
        viewRenderResponseFor(harness.viewRenderer.calls[0])
    );
    await flush();
    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(
        harness.maskRegistry.viewState('generated-00', rgbDigest('b'))
            .stableMask,
        null
    );
});

test('a late plan response with an obsolete Anchor identity is discarded', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    const stalePlan = harness.planner.next;

    // Adjust and re-confirm: the new confirmed identity plans again as soon
    // as the serial pipeline releases the obsolete attempt.
    harness.confirmation.adjust();
    await flush();
    harness.planner.next = deferred();
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    assert.equal(harness.planner.calls.length, 1);

    // The stale plan resolves late: its result is discarded by run identity,
    // then the replacement planning attempt actually runs.
    stalePlan.resolve(planResponseFor(harness.planner.calls[0]));
    await flush();
    assert.equal(harness.planner.calls.length, 2);
    assert.equal(harness.controller.state.views.length, 0);

    harness.planner.next.resolve(planResponseFor(harness.planner.calls[1]));
    await flush();
    assert.equal(harness.controller.state.views.length, 2);
});

test('Restart disposes target-local Generated View and Mask state', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    await completeTwoViews(harness);
    assert.equal(harness.controller.state.views.length, 2);

    harness.confirmation.adjust();
    await harness.anchorController.restart({
        target: target(),
        dependencyToken: dependency(),
        getCurrentDependencyToken: () => dependency(),
        snapshot,
        cameraBinding: cameraBinding()
    });
    await flush();

    assert.equal(harness.controller.state.views.length, 0);
    assert.equal(harness.controller.state.plannerStatus, 'idle');
    assert.equal(
        harness.maskRegistry.viewState('generated-00', rgbDigest('b'))
            .stableMask,
        null
    );
});

test('an unsupported Companion fails planning closed with an actionable diagnostic', async () => {
    const harness = createHarness({
        supportsGeneratedViews: () => false
    });
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();

    assert.equal(harness.planner.calls.length, 0);
    assert.equal(harness.controller.state.plannerStatus, 'failed');
    assert.match(
        harness.controller.state.plannerErrorMessage,
        /does not advertise Generated View planning/
    );
});

test('View selection is explicit and read-only; unknown views are rejected', async () => {
    const harness = createHarness();
    await startAnchor(harness);
    harness.confirmation.confirm(confirmedAnchorFor(harness.anchorController));
    await flush();
    await completeTwoViews(harness);

    assert.equal(harness.controller.state.selectedViewId, null);
    harness.controller.selectView('generated-01');
    assert.equal(harness.controller.state.selectedViewId, 'generated-01');
    assert.ok(
        harness.controller.state.views.find(
            (view) => view.viewId === 'generated-01'
        ).selected
    );
    harness.controller.selectView(null);
    assert.equal(harness.controller.state.selectedViewId, null);
    assert.throws(() => harness.controller.selectView('generated-99'));
});
