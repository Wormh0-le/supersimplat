const assert = require('node:assert/strict');
const test = require('node:test');

const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');

const state = (tracker) => ({
    targetGeometryDirty: tracker.state.targetGeometryDirty,
    localKeyViewPlanDirty: tracker.state.localKeyViewPlanDirty,
    promptDirtyViewIds: tracker.state.promptDirtyViewIds,
    maskInferenceDirtyViewIds: tracker.state.maskInferenceDirtyViewIds,
    evidenceDirtyViewIds: tracker.state.evidenceDirtyViewIds,
    liftDirty: tracker.state.liftDirty,
    candidateStale: tracker.state.candidateStale
});

test('dirty state keeps upstream replacement scoped to bound View dependencies', () => {
    const tracker = new AISelectDirtyStateTracker();

    tracker.markAnchorStableChanged(['view-b']);
    assert.deepEqual(state(tracker), {
        targetGeometryDirty: true,
        localKeyViewPlanDirty: true,
        promptDirtyViewIds: ['view-b'],
        maskInferenceDirtyViewIds: ['view-b'],
        evidenceDirtyViewIds: [],
        liftDirty: false,
        candidateStale: false
    });

    tracker.markTargetGeometryReady();
    tracker.markLocalKeyViewPlanReady(['view-a']);
    assert.deepEqual(state(tracker), {
        targetGeometryDirty: false,
        localKeyViewPlanDirty: false,
        promptDirtyViewIds: ['view-a', 'view-b'],
        maskInferenceDirtyViewIds: ['view-a', 'view-b'],
        evidenceDirtyViewIds: [],
        liftDirty: false,
        candidateStale: false
    });

    tracker.markPromptRegenerated('view-a');
    assert.deepEqual(state(tracker).promptDirtyViewIds, ['view-b']);
    assert.deepEqual(state(tracker).maskInferenceDirtyViewIds, [
        'view-a',
        'view-b'
    ]);

    tracker.markStableMaskPublished('view-a');
    assert.deepEqual(state(tracker), {
        targetGeometryDirty: false,
        localKeyViewPlanDirty: false,
        promptDirtyViewIds: ['view-b'],
        maskInferenceDirtyViewIds: ['view-b'],
        evidenceDirtyViewIds: ['view-a'],
        liftDirty: true,
        candidateStale: true
    });

    tracker.markViewCameraOrRgbChanged('view-b');
    assert.deepEqual(state(tracker).promptDirtyViewIds, ['view-b']);
    assert.deepEqual(state(tracker).maskInferenceDirtyViewIds, ['view-b']);
    assert.deepEqual(state(tracker).evidenceDirtyViewIds, ['view-a', 'view-b']);
});

test('unconfirmed Editing Mask changes do not dirty Evidence or Candidate state', () => {
    const tracker = new AISelectDirtyStateTracker();
    tracker.markEditingMaskChanged();

    assert.deepEqual(state(tracker), {
        targetGeometryDirty: false,
        localKeyViewPlanDirty: false,
        promptDirtyViewIds: [],
        maskInferenceDirtyViewIds: [],
        evidenceDirtyViewIds: [],
        liftDirty: false,
        candidateStale: false
    });
});

test('a Prompt replacement failure leaves only Prompt and Mask work dirty', () => {
    const tracker = new AISelectDirtyStateTracker();
    tracker.markPromptDirty('view-a');

    assert.deepEqual(state(tracker), {
        targetGeometryDirty: false,
        localKeyViewPlanDirty: false,
        promptDirtyViewIds: ['view-a'],
        maskInferenceDirtyViewIds: ['view-a'],
        evidenceDirtyViewIds: [],
        liftDirty: false,
        candidateStale: false
    });
});
