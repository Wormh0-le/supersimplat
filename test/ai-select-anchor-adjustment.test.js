const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AISelectAnchorAdjustmentController
} = require('../.test-dist/src/ai-select/anchor-adjustment.js');

const digest = (character) => `sha256:${character.repeat(64)}`;

const dependency = (suffix = '1') => ({
    splatId: 'editor-splat:1',
    renderStateToken: `render-v${suffix}`,
    geometryToken: `geometry-v${suffix}`,
    gaussianIdentityToken: `gaussians-v${suffix}`,
    worldTransformToken: `transform-v${suffix}`
});

const cameraBinding = (x = 2, revision = 4) => ({
    revision,
    cameraToWorld: Object.freeze([
        1,
        0,
        0,
        x,
        0,
        -1,
        0,
        3,
        0,
        0,
        -1,
        4,
        0,
        0,
        0,
        1
    ]),
    projection: Object.freeze({
        model: 'pinhole',
        fx: 50,
        fy: 50,
        cx: 32,
        cy: 24,
        width: 64,
        height: 48,
        near: 0.1,
        far: 100
    }),
    conventionVersion: 'opencv-camera-to-world/v1'
});

const confirmedAnchor = () =>
    Object.freeze({
        targetContextId: 'target-context-1',
        contextRevision: 7,
        cameraBinding: cameraBinding(),
        rgbDigest: digest('a'),
        stableMask: Object.freeze({
            maskId: 'mask-stable-1',
            viewId: 'anchor-view',
            source: 'manual',
            status: 'user-confirmed',
            artifact: Object.freeze({
                encoding: 'bitset-base64-lsb/v1',
                width: 64,
                height: 48,
                data: '',
                digest: digest('b')
            }),
            createdFromRgbDigest: digest('a')
        }),
        maskEvidencePolicyVersion: 'evidence-policy/pnv-v0',
        dependencyToken: dependency(),
        sceneId: 'editor-splat:1',
        sceneVersion: 'snapshot-v1'
    });

const deferred = () => {
    let resolve;
    let reject;
    const promise = new Promise((innerResolve, innerReject) => {
        resolve = innerResolve;
        reject = innerReject;
    });
    return { promise, resolve, reject };
};

const createConfirmation = (confirmed = confirmedAnchor()) => {
    const listeners = new Set();
    let state = Object.freeze({
        validation: null,
        validationStatus: 'idle',
        confirmedAnchor: confirmed
    });
    const publish = () => listeners.forEach((listener) => listener(state));
    return {
        get state() {
            return state;
        },
        subscribe(listener) {
            listeners.add(listener);
            listener(state);
            return () => listeners.delete(listener);
        },
        replace(next) {
            state = Object.freeze({ ...state, confirmedAnchor: next });
            publish();
        }
    };
};

const createAnchor = () => {
    const listeners = new Set();
    let state = Object.freeze({
        context: Object.freeze({
            targetContextId: 'target-context-1',
            revision: 7,
            lifecycle: 'active',
            target: Object.freeze({ splatId: 'editor-splat:1' }),
            dependencyToken: Object.freeze(dependency())
        }),
        anchor: null
    });
    const renders = [];
    const publish = () => listeners.forEach((listener) => listener(state));
    return {
        renders,
        get state() {
            return state;
        },
        subscribe(listener) {
            listeners.add(listener);
            listener(state);
            return () => listeners.delete(listener);
        },
        replaceContext(context) {
            state = Object.freeze({ ...state, context });
            publish();
        },
        renderAnchorAdjustmentDraft(binding) {
            const gate = deferred();
            renders.push({ binding, gate });
            return gate.promise;
        },
        createAnchorAdjustmentMaskRequest() {
            throw new Error('Mask inference is not needed by this fixture.');
        },
        acceptsAnchorAdjustmentMaskResponse() {
            return false;
        }
    };
};

const renderResult = (binding, suffix = 'c') =>
    Object.freeze({
        requestBinding: Object.freeze({
            targetContextId: 'target-context-1',
            contextRevision: 7,
            dependencyToken: Object.freeze(dependency())
        }),
        cameraBinding: binding,
        rgb: Object.freeze({
            pngBase64: 'fixture',
            digest: digest(suffix),
            width: 64,
            height: 48
        }),
        rendererId: 'gsplat'
    });

const createHarness = () => {
    const anchor = createAnchor();
    const confirmation = createConfirmation();
    const adjustment = new AISelectAnchorAdjustmentController({
        anchor,
        confirmation,
        maskProvider: {
            produceMask: async () => {
                throw new Error(
                    'Mask inference is not needed by this fixture.'
                );
            }
        }
    });
    return { anchor, confirmation, adjustment };
};

test('entering and canceling Anchor adjustment preserves the confirmed run', () => {
    const { anchor, confirmation, adjustment } = createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    assert.equal(adjustment.state.status, 'adjusting');
    assert.deepEqual(
        adjustment.state.draft.cameraBinding,
        original.cameraBinding
    );
    assert.equal(confirmation.state.confirmedAnchor, original);

    adjustment.cancelAdjustment();
    assert.equal(adjustment.state.status, 'current');
    assert.equal(adjustment.state.draft, null);
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(anchor.renders.length, 0);
});

test('confirming an unchanged adjustment is a no-op', async () => {
    const { anchor, confirmation, adjustment } = createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    const outcome = await adjustment.confirmAdjustmentPose();

    assert.equal(outcome, 'unchanged');
    assert.equal(adjustment.state.status, 'current');
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(anchor.renders.length, 0);
});

test('a changed pose stages independent authoritative RGB, Prompt and Editing Mask state', async () => {
    const { anchor, confirmation, adjustment } = createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(9).cameraToWorld);
    const pending = adjustment.confirmAdjustmentPose();
    assert.equal(adjustment.state.status, 'changed');
    assert.equal(adjustment.state.draft.renderStatus, 'rendering');
    assert.equal(anchor.renders.length, 1);

    anchor.renders[0].gate.resolve(renderResult(anchor.renders[0].binding));
    assert.equal(await pending, 'staged');
    assert.equal(adjustment.state.draft.renderStatus, 'ready');
    assert.equal(adjustment.state.draft.rgb.digest, digest('c'));
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(adjustment.mask.state.viewId, 'anchor-adjustment-draft');
    assert.equal(
        adjustment.mask.state.promptState.rgbDigest,
        adjustment.state.draft.rgb.digest
    );
    assert.equal(adjustment.mask.state.stableMask, null);

    adjustment.mask.clearEditingMask();
    assert.ok(adjustment.mask.state.editingMask);
    assert.equal(adjustment.mask.state.stableMask, null);
    assert.equal(confirmation.state.confirmedAnchor, original);
});

test('failed and canceled draft attempts cannot publish late or replace the current run', async () => {
    const { anchor, confirmation, adjustment } = createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(6).cameraToWorld);
    const failed = adjustment.confirmAdjustmentPose();
    anchor.renders[0].gate.reject(new Error('draft render failed'));
    await assert.rejects(failed, /draft render failed/);
    assert.equal(adjustment.state.draft.renderStatus, 'failed');
    assert.equal(confirmation.state.confirmedAnchor, original);

    adjustment.updateAdjustmentPose(cameraBinding(7).cameraToWorld);
    const superseded = adjustment.confirmAdjustmentPose();
    adjustment.cancelAdjustment();
    anchor.renders[1].gate.resolve(
        renderResult(anchor.renders[1].binding, 'd')
    );
    assert.equal(await superseded, 'discarded');
    assert.equal(adjustment.state.status, 'current');
    assert.equal(adjustment.state.draft, null);
    assert.equal(adjustment.mask.state.promptState, null);
    assert.equal(confirmation.state.confirmedAnchor, original);
});

test('target identity rotation discards only the staged adjustment draft', async () => {
    const { anchor, confirmation, adjustment } = createHarness();

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(8).cameraToWorld);
    const pending = adjustment.confirmAdjustmentPose();
    anchor.replaceContext(
        Object.freeze({
            targetContextId: 'target-context-2',
            revision: 0,
            lifecycle: 'active',
            target: Object.freeze({ splatId: 'editor-splat:1' }),
            dependencyToken: Object.freeze(dependency('2'))
        })
    );
    anchor.renders[0].gate.resolve(
        renderResult(anchor.renders[0].binding, 'e')
    );

    assert.equal(await pending, 'discarded');
    assert.equal(adjustment.state.status, 'current');
    assert.equal(adjustment.state.draft, null);
    assert.equal(
        confirmation.state.confirmedAnchor.targetContextId,
        'target-context-1'
    );
});
