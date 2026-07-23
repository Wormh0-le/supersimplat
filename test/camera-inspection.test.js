const assert = require('node:assert/strict');
const test = require('node:test');

const {
    CameraInspectionController
} = require('../.test-dist/src/ai-select/camera-inspection.js');
const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');

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

const sceneView = () => ({
    position: { x: 10, y: 20, z: 30 },
    target: { x: 4, y: 5, z: 6 },
    fov: 53,
    near: 0.2,
    far: 300,
    ortho: false
});

const cameraToWorld = (x, y, z) => [
    1,
    0,
    0,
    x,
    0,
    -1,
    0,
    y,
    0,
    0,
    -1,
    z,
    0,
    0,
    0,
    1
];

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

test('Camera Inspection preserves the saved Scene View while observing a separate Anchor', () => {
    const anchorBinding = captureEditorCameraBinding(editorCamera());
    const savedSceneView = sceneView();
    const appliedSceneViews = [];
    const anchorPoses = [];
    let restored = 0;
    const inspection = new CameraInspectionController({
        anchor: {
            getAnchorCameraBinding: () => anchorBinding,
            updateAnchorCameraPose: (pose) => anchorPoses.push([...pose]),
            renderInteractivePreview: async () => undefined,
            renderFinalPreview: async () => undefined,
            resetAnchor: async () => undefined
        },
        editor: {
            captureSceneView: () => ({
                sceneView: savedSceneView,
                restore: () => {
                    restored += 1;
                }
            }),
            setSceneView: (view) => appliedSceneViews.push(view)
        }
    });

    inspection.enter();

    assert.equal(inspection.state.mode, 'active');
    assert.deepEqual(inspection.state.savedSceneView, savedSceneView);
    assert.notDeepEqual(appliedSceneViews[0].position, savedSceneView.position);
    assert.deepEqual(
        anchorBinding.cameraToWorld,
        [1, 0, 0, 2, 0, -1, 0, 3, 0, 0, -1, 4, 0, 0, 0, 1]
    );
    assert.deepEqual(anchorPoses, []);

    inspection.returnToSceneView();

    assert.equal(inspection.state.mode, 'inactive');
    assert.equal(restored, 1);
    assert.equal(appliedSceneViews.length, 1);
    assert.deepEqual(anchorPoses, []);
});

test('Camera Inspection updates only Anchor pose while dragging and renders once at manipulation end', async () => {
    const anchorBinding = captureEditorCameraBinding(editorCamera());
    const anchorPoses = [];
    let interactivePreviews = 0;
    let finalPreviews = 0;
    const inspection = new CameraInspectionController({
        anchor: {
            getAnchorCameraBinding: () => anchorBinding,
            updateAnchorCameraPose: (pose) => anchorPoses.push([...pose]),
            renderInteractivePreview: async () => {
                interactivePreviews += 1;
            },
            renderFinalPreview: async () => {
                finalPreviews += 1;
            },
            resetAnchor: async () => undefined
        },
        editor: {
            captureSceneView: () => ({
                sceneView: sceneView(),
                restore: () => undefined
            }),
            setSceneView: () => undefined
        },
        // The prior interactive-preview policy scheduled this callback for
        // every drag revision. Invoke it immediately to make that regression
        // observable without waiting for a real timer.
        scheduler: {
            schedule(callback) {
                callback();
                return callback;
            },
            cancel() {}
        }
    });

    inspection.enter();
    inspection.setManipulation('rotate');
    inspection.moveAnchorFrustum(cameraToWorld(7, 8, 9));
    inspection.moveAnchorFrustum(cameraToWorld(11, 12, 13));

    assert.equal(inspection.state.manipulation, 'rotate');
    assert.deepEqual(anchorPoses, [
        cameraToWorld(7, 8, 9),
        cameraToWorld(11, 12, 13)
    ]);
    assert.equal(interactivePreviews, 0);
    assert.equal(finalPreviews, 0);

    await inspection.endAnchorManipulation();

    assert.equal(finalPreviews, 1);
    assert.equal(interactivePreviews, 0);
});

test('Camera Inspection serializes final previews from consecutive manipulations', async () => {
    const renders = [deferred(), deferred()];
    let finalPreviews = 0;
    const inspection = new CameraInspectionController({
        anchor: {
            getAnchorCameraBinding: () =>
                captureEditorCameraBinding(editorCamera()),
            updateAnchorCameraPose: () => undefined,
            renderFinalPreview: () => {
                const render = renders[finalPreviews];
                finalPreviews += 1;
                return render.promise;
            },
            resetAnchor: async () => undefined
        },
        editor: {
            captureSceneView: () => ({
                sceneView: sceneView(),
                restore: () => undefined
            }),
            setSceneView: () => undefined
        }
    });

    inspection.enter();
    inspection.moveAnchorFrustum(cameraToWorld(7, 8, 9));
    const firstEnd = inspection.endAnchorManipulation();
    assert.equal(finalPreviews, 1);

    inspection.moveAnchorFrustum(cameraToWorld(11, 12, 13));
    const secondEnd = inspection.endAnchorManipulation();
    assert.equal(finalPreviews, 1);

    renders[0].resolve();
    await firstEnd;
    await Promise.resolve();
    assert.equal(finalPreviews, 2);

    renders[1].resolve();
    await secondEnd;
});

test('Reset Anchor does not replace the camera-owned saved Scene View with the observer view', async () => {
    const anchorBinding = captureEditorCameraBinding(editorCamera());
    const savedSceneView = sceneView();
    const cameraRuntimeSnapshot = Object.freeze({
        focalPointTween: Object.freeze({
            value: Object.freeze({ x: 4, y: 5, z: 6 }),
            target: Object.freeze({ x: 40, y: 50, z: 60 }),
            timer: 0.12
        }),
        clippingPolicy: 'fit-to-scene'
    });
    let restoredRuntimeSnapshot = null;
    let resets = 0;
    const inspection = new CameraInspectionController({
        anchor: {
            getAnchorCameraBinding: () => anchorBinding,
            updateAnchorCameraPose: () => undefined,
            renderInteractivePreview: async () => undefined,
            renderFinalPreview: async () => undefined,
            resetAnchor: async () => {
                resets += 1;
            }
        },
        editor: {
            captureSceneView: () => ({
                sceneView: savedSceneView,
                restore: () => {
                    restoredRuntimeSnapshot = cameraRuntimeSnapshot;
                }
            }),
            setSceneView: () => undefined
        }
    });

    inspection.enter();
    await inspection.resetAnchor();
    inspection.returnToSceneView();

    assert.equal(resets, 1);
    assert.equal(restoredRuntimeSnapshot, cameraRuntimeSnapshot);
});
