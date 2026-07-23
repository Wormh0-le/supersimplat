const assert = require('node:assert/strict');
const test = require('node:test');

const {
    getAnchorDockPresentation
} = require('../.test-dist/src/ai-select/anchor-dock-presentation.js');

const binding = {
    targetContextId: 'context-1',
    contextRevision: 1,
    dependencyToken: {
        splatId: 'splat-1',
        renderStateToken: 'render-v1',
        geometryToken: 'geometry-v1',
        gaussianIdentityToken: 'ids-v1',
        worldTransformToken: 'world-v1'
    }
};

const cameraBinding = {
    revision: 1,
    cameraToWorld: [1, 0, 0, 0, 0, -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1],
    projection: {
        model: 'pinhole',
        fx: 100,
        fy: 100,
        cx: 50,
        cy: 50,
        width: 100,
        height: 100,
        near: 0.1,
        far: 100
    },
    conventionVersion: 'opencv-camera-to-world/v1'
};

const rgb = (digest) => ({
    pngBase64: 'preview',
    digest,
    width: 100,
    height: 100
});

const state = (anchor) => ({
    context: {
        targetContextId: 'context-1',
        contextRevision: 1,
        target: { splatId: 'splat-1' },
        dependencyToken: binding.dependencyToken,
        lifecycle: 'active'
    },
    anchor
});

const baseAnchor = (overrides = {}) => ({
    viewId: 'anchor-view',
    source: 'anchor',
    cameraBinding,
    requestBinding: binding,
    renderStatus: 'ready',
    rgb: rgb('sha256:formal'),
    ...overrides
});

test('AI View Dock displays the newest ready interactive RGB instead of a retained formal Anchor RGB', () => {
    const interactiveRgb = rgb('sha256:interactive');

    const result = getAnchorDockPresentation(
        state(
            baseAnchor({
                preview: {
                    kind: 'interactive',
                    cameraBinding,
                    requestBinding: binding,
                    renderStatus: 'ready',
                    rgb: interactiveRgb
                }
            })
        )
    );

    assert.equal(result.status, 'previewing');
    assert.equal(result.rgb.digest, interactiveRgb.digest);
    assert.equal(result.showFailureActions, false);
});

test('AI View Dock exposes Retry when an interactive preview fails while retaining a valid RGB', () => {
    const formalRgb = rgb('sha256:formal');

    const result = getAnchorDockPresentation(
        state(
            baseAnchor({
                rgb: formalRgb,
                preview: {
                    kind: 'interactive',
                    cameraBinding,
                    requestBinding: binding,
                    renderStatus: 'failed',
                    errorMessage: 'temporary gsplat failure'
                }
            })
        )
    );

    assert.equal(result.status, 'failed');
    assert.equal(result.rgb.digest, formalRgb.digest);
    assert.equal(result.showFailureActions, true);
});
