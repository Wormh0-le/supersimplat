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

test('Camera Inspection submits only the latest interactive pose and a final fixed pose', async () => {
    const anchorBinding = captureEditorCameraBinding(editorCamera());
    const pending = [];
    const cancelled = [];
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
        scheduler: {
            schedule(callback) {
                pending.push(callback);
                return callback;
            },
            cancel(handle) {
                cancelled.push(handle);
            }
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
    assert.equal(cancelled.length, 1);

    pending.at(-1)();
    await Promise.resolve();
    assert.equal(interactivePreviews, 1);

    await inspection.endAnchorManipulation();
    assert.equal(finalPreviews, 1);
});

test('Camera Inspection discards a cancelled interactive callback that fires after finalization', async () => {
    const scheduled = [];
    let interactivePreviews = 0;
    let finalPreviews = 0;
    const inspection = new CameraInspectionController({
        anchor: {
            getAnchorCameraBinding: () =>
                captureEditorCameraBinding(editorCamera()),
            updateAnchorCameraPose: () => undefined,
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
        scheduler: {
            schedule(callback) {
                scheduled.push(callback);
                return callback;
            },
            // Simulate a browser timer that has already escaped cancellation.
            cancel() {}
        }
    });

    inspection.enter();
    inspection.moveAnchorFrustum(cameraToWorld(7, 8, 9));
    await inspection.endAnchorManipulation();
    scheduled[0]();
    await Promise.resolve();

    assert.equal(finalPreviews, 1);
    assert.equal(interactivePreviews, 0);
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
