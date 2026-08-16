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
        },
        createAnchorAdjustmentSupportProbeRequest(
            draft,
            stableMask,
            supportProbeAttemptId
        ) {
            return Object.freeze({
                requestBinding: draft.requestBinding,
                target: Object.freeze({ splatId: 'editor-splat:1' }),
                snapshot: Object.freeze({ fixture: true }),
                sceneId: 'editor-splat:1',
                sceneVersion: 'snapshot-v1',
                viewId: 'anchor-adjustment-draft',
                supportProbeAttemptId,
                cameraBinding: draft.cameraBinding,
                rgbDigest: draft.rgb.digest,
                stableMask,
                supportProbePolicyVersion: 'anchor-support-probe/v1'
            });
        },
        acceptsAnchorAdjustmentSupportProbeResponse(response, request) {
            return (
                response.supportProbeAttemptId ===
                    request.supportProbeAttemptId &&
                response.rgbDigest === request.rgbDigest &&
                response.stableMaskDigest === request.stableMask.digest
            );
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
    const probes = [];
    const commits = [];
    const adjustment = new AISelectAnchorAdjustmentController({
        anchor,
        confirmation,
        maskProvider: {
            produceMask: async () => {
                throw new Error(
                    'Mask inference is not needed by this fixture.'
                );
            }
        },
        supportProbe: {
            probeAnchorSupport: (request) => {
                const gate = deferred();
                probes.push({ request, gate });
                return gate.promise;
            }
        },
        commitDraft: (input) => {
            commits.push(input);
            const baseline = confirmation.state.confirmedAnchor;
            const replacement = Object.freeze({
                ...baseline,
                contextRevision: baseline.contextRevision + 1,
                cameraBinding: input.render.cameraBinding,
                rgbDigest: input.render.rgb.digest,
                stableMask: input.stableMask
            });
            confirmation.replace(replacement);
            return replacement;
        }
    });
    return { anchor, confirmation, adjustment, probes, commits };
};

const supportResponse = (
    request,
    support = {
        computable: true,
        observedGaussianCount: 512
    }
) =>
    Object.freeze({
        requestBinding: request.requestBinding,
        targetSplatId: request.target.splatId,
        sceneId: request.sceneId,
        sceneVersion: request.sceneVersion,
        viewId: request.viewId,
        supportProbeAttemptId: request.supportProbeAttemptId,
        cameraBinding: request.cameraBinding,
        rgbDigest: request.rgbDigest,
        stableMaskDigest: request.stableMask.digest,
        supportProbePolicyVersion: request.supportProbePolicyVersion,
        support
    });

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

test('changed-Anchor confirmation keeps the old run until fresh draft Mask validation succeeds', async () => {
    const { anchor, confirmation, adjustment, probes, commits } =
        createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(11).cameraToWorld);
    const rendered = adjustment.confirmAdjustmentPose();
    anchor.renders[0].gate.resolve(renderResult(anchor.renders[0].binding));
    assert.equal(await rendered, 'staged');
    adjustment.mask.clearEditingMask();
    adjustment.mask.applyBrushStroke({
        mode: 'add',
        radiusPx: 12,
        xPx: 20,
        yPx: 20
    });

    const confirming = adjustment.confirmAdjustment();
    assert.equal(probes.length, 1);
    assert.equal(commits.length, 0);
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(adjustment.mask.state.stableMask.status, 'user-confirmed');

    probes[0].gate.resolve(supportResponse(probes[0].request));
    const replacement = await confirming;

    assert.equal(commits.length, 1);
    assert.equal(replacement.rgbDigest, digest('c'));
    assert.equal(replacement.contextRevision, 8);
    assert.equal(confirmation.state.confirmedAnchor, replacement);
    assert.equal(adjustment.state.draft, null);
});

test('failed changed-Anchor validation retains the old run and the complete retryable draft', async () => {
    const { anchor, confirmation, adjustment, probes, commits } =
        createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(12).cameraToWorld);
    const rendered = adjustment.confirmAdjustmentPose();
    anchor.renders[0].gate.resolve(renderResult(anchor.renders[0].binding));
    await rendered;
    adjustment.mask.clearEditingMask();
    adjustment.mask.applyBrushStroke({
        mode: 'add',
        radiusPx: 12,
        xPx: 20,
        yPx: 20
    });
    const confirming = adjustment.confirmAdjustment();
    probes[0].gate.resolve(
        supportResponse(probes[0].request, {
            computable: false,
            observedGaussianCount: 0
        })
    );

    await assert.rejects(confirming, /no-computable-gaussian-support/);
    assert.equal(commits.length, 0);
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(adjustment.state.draft.renderStatus, 'ready');
    assert.equal(adjustment.mask.state.stableMask.status, 'user-confirmed');
    assert.equal(adjustment.state.confirmationStatus, 'failed');
});

test('canceling a changed-Anchor confirmation makes its late validation response inert', async () => {
    const { anchor, confirmation, adjustment, probes, commits } =
        createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(13).cameraToWorld);
    const rendered = adjustment.confirmAdjustmentPose();
    anchor.renders[0].gate.resolve(renderResult(anchor.renders[0].binding));
    await rendered;
    adjustment.mask.clearEditingMask();
    adjustment.mask.applyBrushStroke({
        mode: 'add',
        radiusPx: 12,
        xPx: 20,
        yPx: 20
    });
    const confirming = adjustment.confirmAdjustment();
    adjustment.cancelAdjustment();
    probes[0].gate.resolve(supportResponse(probes[0].request));

    assert.equal(await confirming, null);
    assert.equal(commits.length, 0);
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.equal(adjustment.state.draft, null);
});

test('editing the draft during changed-Anchor validation retires the late probe', async () => {
    const { anchor, confirmation, adjustment, probes, commits } =
        createHarness();
    const original = confirmation.state.confirmedAnchor;

    adjustment.beginAdjustment();
    adjustment.updateAdjustmentPose(cameraBinding(14).cameraToWorld);
    const rendered = adjustment.confirmAdjustmentPose();
    anchor.renders[0].gate.resolve(renderResult(anchor.renders[0].binding));
    await rendered;
    adjustment.mask.clearEditingMask();
    adjustment.mask.applyBrushStroke({
        mode: 'add',
        radiusPx: 12,
        xPx: 20,
        yPx: 20
    });
    const confirming = adjustment.confirmAdjustment();
    assert.equal(probes.length, 1);

    adjustment.mask.beginCorrectionFromStable();
    adjustment.mask.applyBrushStroke({
        mode: 'add',
        radiusPx: 5,
        xPx: 28,
        yPx: 24
    });
    assert.equal(adjustment.state.confirmationStatus, 'failed');
    probes[0].gate.resolve(supportResponse(probes[0].request));

    assert.equal(await confirming, null);
    assert.equal(commits.length, 0);
    assert.equal(confirmation.state.confirmedAnchor, original);
    assert.ok(adjustment.state.draft);
    assert.ok(adjustment.mask.state.editingMask);
    assert.equal(adjustment.mask.state.hasUnconfirmedChanges, true);
});
