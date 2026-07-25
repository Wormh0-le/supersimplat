const assert = require('node:assert/strict');
const test = require('node:test');

const {
    composeAnchorAIView
} = require('../.test-dist/src/ai-select/ai-view.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const cameraBinding = () =>
    captureEditorCameraBinding({
        targetSize: { width: 640, height: 480 },
        fov: 60,
        near: 0.1,
        far: 100,
        camera: { horizontalFov: false },
        worldTransform: {
            data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
        }
    });

const requestBinding = {
    targetContextId: 'ai-target-context-1',
    contextRevision: 0,
    dependencyToken: {
        splatId: 'editor-splat:1',
        renderStateToken: 'render-v1',
        geometryToken: 'geometry-v1',
        gaussianIdentityToken: 'gaussians-v1',
        worldTransformToken: 'transform-v1'
    }
};

const anchor = (overrides = {}) => ({
    viewId: 'anchor-view',
    source: 'anchor',
    cameraBinding: cameraBinding(),
    requestBinding,
    renderStatus: 'ready',
    rgb: {
        pngBase64: 'aGVsbG8=',
        digest: digest('a'),
        width: 640,
        height: 480
    },
    rendererId: 'gsplat',
    ...overrides
});

const noMasks = { viewId: 'anchor-view', editingMask: null, stableMask: null };

const evidence = (status) => ({ viewId: 'anchor-view', status });

test('an RGB Ready Anchor with no Mask exposes Evidence not-requested', () => {
    const view = composeAnchorAIView(
        anchor(),
        noMasks,
        evidence('not-requested')
    );
    assert.equal(view.renderStatus, 'ready');
    assert.equal(view.rgbDigest, digest('a'));
    assert.equal(view.editingMaskId, undefined);
    assert.equal(view.stableMaskId, undefined);
    assert.equal(view.evidenceStatus, 'not-requested');
    assert.equal(view.participation, 'included');
    assert.equal(view.source, 'anchor');
});

test('an Anchor exposes independent editingMaskId and stableMaskId', () => {
    const masks = {
        viewId: 'anchor-view',
        editingMask: { maskId: 'mask-2' },
        stableMask: { maskId: 'mask-1' }
    };
    const view = composeAnchorAIView(
        anchor(),
        masks,
        evidence('not-requested')
    );
    assert.equal(view.editingMaskId, 'mask-2');
    assert.equal(view.stableMaskId, 'mask-1');
});

test('an Anchor stays RGB Ready when Evidence is stale or failed', () => {
    const stale = composeAnchorAIView(anchor(), noMasks, evidence('stale'));
    assert.equal(stale.renderStatus, 'ready');
    assert.equal(stale.evidenceStatus, 'stale');
    const failed = composeAnchorAIView(anchor(), noMasks, evidence('failed'));
    assert.equal(failed.renderStatus, 'ready');
    assert.equal(failed.evidenceStatus, 'failed');
});

test('a rendering Anchor carries no RGB digest and no Mask currency', () => {
    const view = composeAnchorAIView(
        anchor({
            renderStatus: 'rendering',
            rgb: undefined,
            rendererId: undefined
        }),
        noMasks,
        evidence('not-requested')
    );
    assert.equal(view.renderStatus, 'rendering');
    assert.equal(view.rgbDigest, undefined);
});
