const assert = require('node:assert/strict');
const test = require('node:test');

const {
    buildAuthoritativeRenderScopeSnapshot
} = require('../.test-dist/src/ai-select/authoritative-render-scope.js');
const {
    buildPackedSceneSnapshot
} = require('../.test-dist/src/scene-snapshot-binary.js');
const {
    buildSpatialSceneSnapshot
} = require('../.test-dist/src/spatial-scene-snapshot.js');

const snapshot = (sceneId, stableId, x, shFloatCountPerGaussian = 0) =>
    buildPackedSceneSnapshot({
        sceneId,
        coordinateConvention: 'right-handed world coordinates; quaternion xyzw',
        stableIdSchema: 'uint32',
        appearancePolicy: `effective-editor-dc-sh-bands-${
            shFloatCountPerGaussian === 0 ? 0 : 1
        }`,
        renderConfiguration: {
            version: 'supersplat-effective-rgb-v1',
            backgroundRgba: [0, 0, 0, 1],
            alphaMode: 'opaque-background',
            shBands: shFloatCountPerGaussian === 0 ? 0 : 1,
            rasterizer: 'playcanvas-gsplat-classic'
        },
        stableIds: new Uint32Array([stableId]),
        means: new Float32Array([x, 0, 5]),
        rotationsXyzw: new Float32Array([0, 0, 0, 1]),
        logScales: new Float32Array([0, 0, 0]),
        logitOpacities: new Float32Array([5]),
        dc: new Float32Array([0.1, 0.2, 0.3]),
        sh: new Float32Array(shFloatCountPerGaussian),
        shFloatCountPerGaussian
    });

test('keeps target Stable IDs while adding deterministic collision-free visible occluders', () => {
    const target = snapshot('editor-splat:target', 17, 0);
    const occluderB = snapshot('editor-splat:b', 17, 1, 9);
    const occluderA = snapshot('editor-splat:a', 17, -1);

    const scoped = buildAuthoritativeRenderScopeSnapshot(
        { splatId: target.sceneId, snapshot: target },
        [
            { splatId: occluderB.sceneId, snapshot: occluderB },
            { splatId: target.sceneId, snapshot: target },
            { splatId: occluderA.sceneId, snapshot: occluderA }
        ]
    );

    assert.deepEqual(Array.from(scoped.stableIds), [17, 18, 19]);
    assert.equal(scoped.shFloatCountPerGaussian, 9);
    assert.deepEqual(
        scoped.authoritativeRenderScope.entries.map((entry) => [
            entry.splatId,
            entry.role,
            entry.rowOffset,
            entry.rowCount
        ]),
        [
            ['editor-splat:target', 'target', 0, 1],
            ['editor-splat:a', 'occluder', 1, 1],
            ['editor-splat:b', 'occluder', 2, 1]
        ]
    );
    const repeat = buildAuthoritativeRenderScopeSnapshot(
        { splatId: target.sceneId, snapshot: target },
        [
            { splatId: occluderA.sceneId, snapshot: occluderA },
            { splatId: occluderB.sceneId, snapshot: occluderB }
        ]
    );
    assert.equal(scoped.contentDigest, repeat.contentDigest);
    assert.equal(
        scoped.authoritativeRenderScope.identityDigest,
        repeat.authoritativeRenderScope.identityDigest
    );
    const spatial = buildSpatialSceneSnapshot(scoped, {
        targetSplatId: target.sceneId,
        chunkByteLength: 100
    });
    assert.deepEqual(
        spatial.manifest.authoritativeRenderScope,
        scoped.authoritativeRenderScope
    );
});

test('binds render-scope identity to occluder content and fails closed on ID exhaustion', () => {
    const target = snapshot('editor-splat:target', 7, 0);
    const before = snapshot('editor-splat:occluder', 0, 1);
    const after = snapshot('editor-splat:occluder', 0, 2);
    const first = buildAuthoritativeRenderScopeSnapshot(
        { splatId: target.sceneId, snapshot: target },
        [{ splatId: before.sceneId, snapshot: before }]
    );
    const second = buildAuthoritativeRenderScopeSnapshot(
        { splatId: target.sceneId, snapshot: target },
        [{ splatId: after.sceneId, snapshot: after }]
    );
    assert.notEqual(first.contentDigest, second.contentDigest);

    const exhausted = snapshot('editor-splat:exhausted', 0xffffffff, 0);
    assert.throws(
        () =>
            buildAuthoritativeRenderScopeSnapshot(
                { splatId: exhausted.sceneId, snapshot: exhausted },
                [{ splatId: before.sceneId, snapshot: before }]
            ),
        /collision-free occluder IDs/
    );
});
