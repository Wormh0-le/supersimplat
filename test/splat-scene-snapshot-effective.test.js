const assert = require('node:assert/strict');
const test = require('node:test');
require('playcanvas');

const renderConfiguration = () => ({
    version: 'supersplat-effective-rgb-v1',
    backgroundRgba: [0, 0, 0, 1],
    alphaMode: 'opaque-background',
    shBands: 0,
    rasterizer: 'playcanvas-gsplat-classic'
});

const fakeSplat = ({ Color, Mat4 }) => {
    const properties = new Map([
        ['x', new Float32Array([1, 2, 3])],
        ['y', new Float32Array([0, 0, 0])],
        ['z', new Float32Array([5, 5, 5])],
        ['rot_0', new Float32Array([1, 1, 1])],
        ['rot_1', new Float32Array(3)],
        ['rot_2', new Float32Array(3)],
        ['rot_3', new Float32Array(3)],
        ['scale_0', new Float32Array(3)],
        ['scale_1', new Float32Array(3)],
        ['scale_2', new Float32Array(3)],
        ['opacity', new Float32Array([2, 2, 2])],
        ['f_dc_0', new Float32Array([0.1, 0.2, 0.3])],
        ['f_dc_1', new Float32Array([0.1, 0.2, 0.3])],
        ['f_dc_2', new Float32Array([0.1, 0.2, 0.3])]
    ]);
    const paletteTransform = new Mat4().setTranslate(0, 2, 0);
    return {
        uid: 42,
        visible: true,
        splatData: {
            numSplats: 3,
            getProp: (name) => properties.get(name)
        },
        state: { data: new Uint8Array([0, 4, 0]) },
        transformTexture: { getSource: () => new Uint16Array([1, 0, 0]) },
        transformPalette: {
            getTransform: (index, result) =>
                result.copy(index === 1 ? paletteTransform : new Mat4())
        },
        worldTransform: new Mat4().setTranslate(10, 0, 0),
        tintClr: new Color(0.8, 1, 1, 1),
        temperature: 0.1,
        saturation: 0.9,
        brightness: 0.05,
        blackPoint: 0,
        whitePoint: 1,
        transparency: 0.75,
        aiSelectContentRevision: 1,
        aiSelectGeometryRevision: 1,
        aiSelectGaussianIdentityRevision: 1,
        aiSelectWorldTransformRevision: 1,
        aiSelectRenderStateRevision: 1
    };
};

test('browser snapshot binding applies delete, world, palette, and color-grade semantics without remapping target Stable IDs', async () => {
    const playcanvas = await import('playcanvas');
    require.cache[require.resolve('playcanvas')].exports = playcanvas;
    const {
        SplatSceneSnapshotBinding
    } = require('../.test-dist/src/splat-scene-snapshot.js');
    const { Mat4 } = playcanvas;
    const splat = fakeSplat(playcanvas);
    const binding = new SplatSceneSnapshotBinding({
        splat,
        sceneId: 'editor-splat:42',
        getRenderConfiguration: renderConfiguration
    });

    const snapshot = binding.getPackedSnapshot();
    assert.equal(snapshot.gaussianCount, 2);
    assert.deepEqual(Array.from(snapshot.stableIds), [0, 2]);
    assert.deepEqual(Array.from(snapshot.means), [11, 2, 5, 13, 0, 5]);
    assert.notDeepEqual(
        Array.from(snapshot.dc.subarray(0, 3)),
        [0.1, 0.1, 0.1]
    );
    assert.ok(snapshot.logitOpacities[0] < 2);
    assert.deepEqual(Array.from(binding.toSplatIndices([2, 0])), [2, 0]);

    const before = snapshot.contentDigest;
    splat.worldTransform = new Mat4().setTranslate(20, 0, 0);
    splat.aiSelectWorldTransformRevision += 1;
    const moved = binding.getPackedSnapshot();
    assert.notEqual(moved.contentDigest, before);
    assert.deepEqual(Array.from(moved.stableIds), [0, 2]);
    assert.deepEqual(Array.from(moved.means), [21, 2, 5, 23, 0, 5]);
});
