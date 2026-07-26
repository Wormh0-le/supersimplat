const assert = require('node:assert/strict');
const test = require('node:test');

const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    generatedFrustumDisplayDepth,
    generatedFrustumLines,
    pickGeneratedViewFrustum
} = require('../.test-dist/src/ai-select/generated-frustum-picking.js');

const bindingAt = (x, y, z) => {
    const binding = captureEditorCameraBinding({
        targetSize: { width: 64, height: 48 },
        fov: 60,
        near: 0.1,
        far: 100,
        camera: { horizontalFov: false },
        worldTransform: {
            data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
        }
    });
    return binding;
};

test('frustum lines derive from the exact CameraBinding pose and projection', () => {
    const binding = bindingAt(2, 3, 4);
    const depth = generatedFrustumDisplayDepth(binding);
    const lines = generatedFrustumLines(binding, depth);
    assert.equal(lines.length, 8);
    // Every ray starts at the camera position.
    for (const [start] of lines.slice(0, 4)) {
        assert.deepEqual(start, [2, 3, 4]);
    }
    const moved = generatedFrustumLines(bindingAt(9, 9, 9), depth);
    assert.notDeepEqual(moved[0][0], lines[0][0]);
});

test('picking selects the nearest frustum and ignores far-away clicks', () => {
    const targets = [
        { viewId: 'generated-00', cameraBinding: bindingAt(0, 0, 0) },
        { viewId: 'generated-01', cameraBinding: bindingAt(10, 0, 0) }
    ];
    // A trivial identity projector: world x/y map directly to screen.
    const projector = (x, y, z) => ({ x, y, inFront: true });

    const origin = targets[0].cameraBinding.cameraToWorld;
    const hit = pickGeneratedViewFrustum(
        targets,
        projector,
        origin[3] + 0.001,
        origin[7],
        0.01
    );
    assert.equal(hit, 'generated-00');

    assert.equal(
        pickGeneratedViewFrustum(targets, projector, 5, 5, 0.01),
        null
    );
});

test('segments behind the editor camera never win the pick', () => {
    const targets = [
        { viewId: 'generated-00', cameraBinding: bindingAt(0, 0, 0) }
    ];
    const projector = (x, y, z) => ({ x, y, inFront: false });
    assert.equal(pickGeneratedViewFrustum(targets, projector, 0, 0, 100), null);
});

test('a closer second frustum beats a farther first frustum', () => {
    const targets = [
        { viewId: 'generated-00', cameraBinding: bindingAt(0, 0, 0) },
        { viewId: 'generated-01', cameraBinding: bindingAt(2, 0, 0) }
    ];
    const projector = (x, y, z) => ({ x, y, inFront: true });
    assert.equal(
        pickGeneratedViewFrustum(targets, projector, 2.001, 0, 0.01),
        'generated-01'
    );
});
