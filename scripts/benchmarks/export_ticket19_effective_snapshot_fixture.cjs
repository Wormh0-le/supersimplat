const { Buffer } = require('node:buffer');

const renderConfiguration = {
    version: 'supersplat-effective-rgb-v1',
    backgroundRgba: [0, 0, 0, 1],
    alphaMode: 'opaque-background',
    shBands: 0,
    rasterizer: 'playcanvas-gsplat-classic'
};

const encodeSnapshot = (snapshot, createBinarySceneSnapshotManifest) => ({
    manifest: createBinarySceneSnapshotManifest(snapshot, 64),
    payloadBase64: Buffer.from(
        snapshot.readPayloadRange(0, snapshot.payloadByteLength)
    ).toString('base64')
});

const main = async () => {
    require('playcanvas');
    const playcanvas = await import('playcanvas');
    require.cache[require.resolve('playcanvas')].exports = playcanvas;
    const { Color, Mat4 } = playcanvas;
    const {
        SplatSceneSnapshotBinding
    } = require('../../.test-dist/src/splat-scene-snapshot.js');
    const {
        buildAuthoritativeRenderScopeSnapshot
    } = require('../../.test-dist/src/ai-select/authoritative-render-scope.js');
    const {
        buildPackedSceneSnapshot,
        createBinarySceneSnapshotManifest
    } = require('../../.test-dist/src/scene-snapshot-binary.js');

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
        ['f_dc_0', new Float32Array(3)],
        ['f_dc_1', new Float32Array(3)],
        ['f_dc_2', new Float32Array(3)]
    ]);
    const paletteTransform = new Mat4().setTranslate(0, 2, 0);
    const splat = {
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
        worldTransform: new Mat4().setTranslate(1, 0, 0),
        tintClr: new Color(1, 1, 1, 1),
        temperature: 0,
        saturation: 1,
        brightness: 0,
        blackPoint: 0,
        whitePoint: 1,
        transparency: 1,
        aiSelectContentRevision: 1,
        aiSelectGeometryRevision: 1,
        aiSelectGaussianIdentityRevision: 1,
        aiSelectWorldTransformRevision: 1,
        aiSelectRenderStateRevision: 1
    };
    const binding = new SplatSceneSnapshotBinding({
        splat,
        sceneId: 'editor-splat:42',
        getRenderConfiguration: () => renderConfiguration
    });
    const productionTarget = binding.getPackedSnapshot();
    const expectedTarget = buildPackedSceneSnapshot({
        sceneId: 'editor-splat:42',
        coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
        stableIdSchema: 'uint32',
        appearancePolicy: 'effective-editor-dc-sh-bands-0',
        renderConfiguration,
        stableIds: new Uint32Array([0, 2]),
        means: new Float32Array([2, 2, 5, 4, 0, 5]),
        rotationsXyzw: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1]),
        logScales: new Float32Array(6),
        logitOpacities: new Float32Array([2, 2]),
        dc: new Float32Array(6),
        sh: new Float32Array(0),
        shFloatCountPerGaussian: 0
    });
    const occluder = buildPackedSceneSnapshot({
        sceneId: 'editor-splat:84',
        coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
        stableIdSchema: 'uint32',
        appearancePolicy: 'effective-editor-dc-sh-bands-0',
        renderConfiguration,
        stableIds: new Uint32Array([0]),
        means: new Float32Array([0, 0, 4]),
        rotationsXyzw: new Float32Array([0, 0, 0, 1]),
        logScales: new Float32Array([0, 0, 0]),
        logitOpacities: new Float32Array([2]),
        dc: new Float32Array([-1, -1, 1]),
        sh: new Float32Array(0),
        shFloatCountPerGaussian: 0
    });
    const production = buildAuthoritativeRenderScopeSnapshot(
        { splatId: 'editor-splat:42', snapshot: productionTarget },
        [
            { splatId: 'editor-splat:42', snapshot: productionTarget },
            { splatId: 'editor-splat:84', snapshot: occluder }
        ]
    );
    const expected = buildAuthoritativeRenderScopeSnapshot(
        { splatId: 'editor-splat:42', snapshot: expectedTarget },
        [
            { splatId: 'editor-splat:42', snapshot: expectedTarget },
            { splatId: 'editor-splat:84', snapshot: occluder }
        ]
    );
    process.stdout.write(
        JSON.stringify({
            expectedStableIds: [0, 2, 3],
            expectedMeans: [2, 2, 5, 4, 0, 5, 0, 0, 4],
            production: encodeSnapshot(
                production,
                createBinarySceneSnapshotManifest
            ),
            expected: encodeSnapshot(
                expected,
                createBinarySceneSnapshotManifest
            )
        })
    );
};

main().catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
});
