const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AISelectTargetLifecycleController,
    restartConfirmationFor
} = require('../.test-dist/src/ai-select/target-lifecycle.js');
const {
    CurrentTargetContextKernel
} = require('../.test-dist/src/ai-select/current-target-context.js');

const snapshot = (overrides = {}) => ({
    hasContext: true,
    hasUnconfirmedChanges: false,
    hasConfirmedTargetState: false,
    candidateApplied: false,
    ...overrides
});

const input = (object) => ({
    target: { splatId: 'editor-splat:1' },
    dependencyToken: {
        splatId: 'editor-splat:1',
        renderStateToken: `render-${object}`,
        geometryToken: 'geometry-v1',
        gaussianIdentityToken: 'gaussians-v1',
        worldTransformToken: 'transform-v1'
    }
});

test('restart confirmation protects drafts and confirmed context, but not committed Native Selection alone', () => {
    assert.equal(
        restartConfirmationFor(snapshot({ hasContext: false })),
        'none'
    );
    assert.equal(restartConfirmationFor(snapshot()), 'none');
    assert.equal(
        restartConfirmationFor(snapshot({ hasUnconfirmedChanges: true })),
        'discard-unconfirmed'
    );
    assert.equal(
        restartConfirmationFor(snapshot({ hasConfirmedTargetState: true })),
        'discard-confirmed-context'
    );
    assert.equal(
        restartConfirmationFor(
            snapshot({
                hasConfirmedTargetState: true,
                candidateApplied: true
            })
        ),
        'none'
    );
    assert.equal(
        restartConfirmationFor(
            snapshot({
                hasUnconfirmedChanges: true,
                hasConfirmedTargetState: true,
                candidateApplied: true
            })
        ),
        'discard-unconfirmed'
    );
});

test('cancelled confirmation does not restart or lose the current context', async () => {
    let restarts = 0;
    const controller = new AISelectTargetLifecycleController({
        getSnapshot: () => snapshot({ hasConfirmedTargetState: true }),
        confirmRestart: async () => false,
        restartCurrentTarget: async () => {
            restarts += 1;
        }
    });

    assert.equal(await controller.chooseAnotherObject(), false);
    assert.equal(restarts, 0);
});

test('A to B to C rotates context identity while Native Selection and explicit Add mode stay durable', async () => {
    const kernel = new CurrentTargetContextKernel();
    let object = 'A';
    let hasContext = true;
    const contextIds = [kernel.start(input(object)).targetContextId];
    const nativeSelection = new Set([10]);
    let pendingApplication = null;
    const controller = new AISelectTargetLifecycleController({
        getSnapshot: () => snapshot({ hasContext, candidateApplied: true }),
        confirmRestart: async () => {
            throw new Error('Applied Native Selection needs no confirmation.');
        },
        restartCurrentTarget: async () => {
            object = object === 'A' ? 'B' : 'C';
            const context = kernel.restart(input(object));
            contextIds.push(context.targetContextId);
            hasContext = true;
            pendingApplication = null;
        }
    });
    const add = (ids) => {
        pendingApplication = 'add';
        ids.forEach((id) => nativeSelection.add(id));
        pendingApplication = null;
    };

    add([11]);
    assert.equal(await controller.chooseAnotherObject(), true);
    assert.equal(pendingApplication, null);
    add([12]);
    assert.equal(await controller.chooseAnotherObject(), true);
    assert.equal(pendingApplication, null);
    add([13]);

    assert.equal(new Set(contextIds).size, 3);
    assert.deepEqual(Array.from(nativeSelection), [10, 11, 12, 13]);
    assert.equal(pendingApplication, null);
});
