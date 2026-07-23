const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AnchorFrustumManipulation,
    canManipulateAnchorFrustum
} = require('../.test-dist/src/ai-select/anchor-frustum-manipulation.js');

test('Anchor Frustum drag converts a PlayCanvas transform once per active move and requests a final preview at drag end', async () => {
    const poses = [];
    let finals = 0;
    const manipulation = new AnchorFrustumManipulation({
        moveAnchorFrustum: (pose) => poses.push([...pose]),
        endAnchorManipulation: async () => {
            finals += 1;
        }
    });
    const playCanvasTransform = [
        1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1
    ];

    manipulation.move(playCanvasTransform);
    manipulation.begin();
    manipulation.move(playCanvasTransform);
    await manipulation.end();
    manipulation.move(playCanvasTransform);
    await manipulation.end();

    assert.deepEqual(poses, [
        [1, 0, 0, 7, 0, -1, 0, 8, 0, 0, -1, 9, 0, 0, 0, 1]
    ]);
    assert.equal(finals, 1);
});

test('Anchor Frustum cancellation prevents a detached gizmo from submitting a final preview', async () => {
    let finals = 0;
    const manipulation = new AnchorFrustumManipulation({
        moveAnchorFrustum: () => undefined,
        endAnchorManipulation: async () => {
            finals += 1;
        }
    });

    manipulation.begin();
    manipulation.cancel();
    await manipulation.end();

    assert.equal(finals, 0);
});

test('a suspended target keeps its Anchor inspectable but disables frustum manipulation', () => {
    const inspectionState = {
        mode: 'active',
        manipulation: 'move',
        savedSceneView: null
    };
    const anchor = { cameraBinding: {} };

    assert.equal(
        canManipulateAnchorFrustum(
            { context: { lifecycle: 'suspended' }, anchor },
            inspectionState
        ),
        false
    );
    assert.equal(
        canManipulateAnchorFrustum(
            { context: { lifecycle: 'active' }, anchor },
            inspectionState
        ),
        true
    );
});
