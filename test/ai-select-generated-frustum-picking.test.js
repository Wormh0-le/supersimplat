const assert = require('node:assert/strict');
const test = require('node:test');

const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    generatedFrustumDisplayDepth,
    generatedFrustumDisplayDepthForProjection,
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

const largeOrbitBinding = {
    revision: 0,
    cameraToWorld: [
        0.7902635425392411,
        0.1960471730936363,
        -0.5805592469811524,
        7.431272613145292,
        0.6127671118241651,
        -0.2528349360209104,
        0.7487262261961799,
        -4.453261235388459,
        0,
        -0.9474386529212834,
        -0.3199374922554467,
        4.137180519247002,
        0,
        0,
        0,
        1
    ],
    projection: {
        model: 'pinhole',
        fx: 816.4706960850153,
        fy: 816.4706960850153,
        cx: 626.5,
        cy: 575,
        width: 1253,
        height: 1150,
        near: 0.001667584778475318,
        far: 27.32170901053961
    },
    conventionVersion: 'opencv-camera-to-world/v1'
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

test('a real large-orbit CameraBinding keeps a minimum projected display size', () => {
    const originalBinding = structuredClone(largeOrbitBinding);
    const viewportSize = 1000;
    const minimumDisplaySize = 32 / viewportSize;
    const projector = (x, y, z) => {
        const perspectiveDepth = 10 - z;
        return {
            x: (x * 0.1) / perspectiveDepth,
            y: (y * 0.1) / perspectiveDepth,
            inFront: perspectiveDepth > 0
        };
    };
    const depth = generatedFrustumDisplayDepthForProjection(
        largeOrbitBinding,
        projector,
        minimumDisplaySize
    );
    const projected = generatedFrustumLines(largeOrbitBinding, depth)
        .flat()
        .map(([x, y, z]) => projector(x, y, z));
    const width =
        Math.max(...projected.map((point) => point.x)) -
        Math.min(...projected.map((point) => point.x));
    const height =
        Math.max(...projected.map((point) => point.y)) -
        Math.min(...projected.map((point) => point.y));

    assert.ok(
        Math.max(width, height) * viewportSize >= 32 - 1e-6,
        'expected the frustum to span at least 32 pixels'
    );
    assert.deepEqual(largeOrbitBinding, originalBinding);
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
