const assert = require('node:assert/strict');
const test = require('node:test');

const {
    captureEditorCameraBinding
} = require('../.test-dist/src/ai-select/camera-binding.js');
const {
    aiSelectLocalKeyViewPlannerVersion,
    isLocalKeyViewPlan,
    isLocalKeyViewPlanRequest,
    isLocalKeyViewPlanResponse,
    isPlannedKeyView,
    localKeyViewPlanResponseMatchesRequest
} = require('../.test-dist/src/ai-select/local-key-view-plan.js');

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const requestBinding = () => ({
    targetContextId: 'ai-target-context-1',
    contextRevision: 3,
    dependencyToken: dependency()
});

const target = () => ({ splatId: 'editor-splat:1' });

const editorCamera = () => ({
    targetSize: { width: 64, height: 48 },
    fov: 60,
    near: 0.1,
    far: 100,
    camera: { horizontalFov: false },
    worldTransform: {
        data: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2, 3, 4, 1]
    }
});

const cameraBinding = () => captureEditorCameraBinding(editorCamera());

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const hintArtifact = (overrides = {}) => ({
    schemaVersion: 1,
    targetContextId: 'ai-target-context-1',
    anchorCameraBindingDigest: digest('b'),
    anchorRgbDigest: digest('a'),
    anchorStableMaskDigest: digest('d'),
    geometryPolicyDigest: digest('e'),
    centerWorld: [1, 2, 3],
    extentWorld: [0.5, 0.25, 0.125],
    visiblePoints: [[1, 2, 3]],
    quality: 'usable',
    reasons: [],
    artifactDigest: digest('f'),
    ...overrides
});

const plannedKeyView = (viewId, revision, overrides = {}) => ({
    viewId,
    cameraBinding: Object.freeze({ ...cameraBinding(), revision }),
    quality: 'usable',
    reasons: [],
    ...overrides
});

const planFor = (request, overrides = {}) => ({
    schemaVersion: 1,
    targetContextId: request.requestBinding.targetContextId,
    anchorStableMaskDigest: request.anchorStableMaskDigest,
    targetGeometryHintDigest: request.targetGeometryHint.artifactDigest,
    localViewPolicyDigest: digest('9'),
    orderedViews: [
        plannedKeyView('key-view-0-0', 100),
        plannedKeyView('key-view-0-1', 101),
        plannedKeyView('key-view-0-2', 102)
    ],
    planAttemptId: request.planAttemptId,
    artifactDigest: digest('8'),
    ...overrides
});

const planRequest = (overrides = {}) => ({
    requestBinding: requestBinding(),
    target: target(),
    planAttemptId: 'local-key-view-plan-attempt-1',
    batchOrdinal: 0,
    anchorCameraBinding: cameraBinding(),
    anchorCameraBindingDigest: digest('b'),
    anchorRgbDigest: digest('a'),
    anchorStableMaskDigest: digest('d'),
    targetGeometryHint: hintArtifact(),
    localViewPolicyVersion: aiSelectLocalKeyViewPlannerVersion,
    ...overrides
});

const planResponseFor = (request, overrides = {}) => ({
    requestBinding: request.requestBinding,
    targetSplatId: request.target.splatId,
    planAttemptId: request.planAttemptId,
    batchOrdinal: request.batchOrdinal,
    localViewPolicyVersion: request.localViewPolicyVersion,
    plan: planFor(request),
    ...overrides
});

test('a complete local Key-View plan request validates', () => {
    assert.ok(isLocalKeyViewPlanRequest(planRequest()));
    // The plan request carries no scene payload: the route is pure CPU on
    // the bound Target Geometry Hint.
    const request = planRequest();
    assert.equal(request.snapshot, undefined);
    assert.equal(request.sceneTransport, undefined);
});

test('plan request validation fails closed on malformed inputs', () => {
    const request = planRequest();
    assert.ok(!isLocalKeyViewPlanRequest(null));
    assert.ok(!isLocalKeyViewPlanRequest({ ...request, requestBinding: null }));
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            requestBinding: { ...request.requestBinding, contextRevision: -1 }
        })
    );
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            target: { splatId: 'editor-splat:2' }
        })
    );
    assert.ok(!isLocalKeyViewPlanRequest({ ...request, planAttemptId: '' }));
    // batchOrdinal is a non-negative safe integer.
    assert.ok(!isLocalKeyViewPlanRequest({ ...request, batchOrdinal: -1 }));
    assert.ok(!isLocalKeyViewPlanRequest({ ...request, batchOrdinal: 1.5 }));
    assert.ok(!isLocalKeyViewPlanRequest({ ...request, batchOrdinal: '0' }));
    assert.ok(isLocalKeyViewPlanRequest({ ...request, batchOrdinal: 7 }));
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            anchorCameraBinding: { revision: 0 }
        })
    );
    for (const field of [
        'anchorCameraBindingDigest',
        'anchorRgbDigest',
        'anchorStableMaskDigest'
    ]) {
        assert.ok(
            !isLocalKeyViewPlanRequest({ ...request, [field]: 'nope' }),
            field
        );
    }
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            targetGeometryHint: hintArtifact({ schemaVersion: 2 })
        })
    );
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            targetGeometryHint: hintArtifact({ visiblePoints: [] })
        })
    );
    assert.ok(
        !isLocalKeyViewPlanRequest({
            ...request,
            localViewPolicyVersion: 'local-key-view-planner/v0'
        })
    );
});

test('a complete Planned Key View validates; the Anchor view id stays reserved', () => {
    assert.ok(isPlannedKeyView(plannedKeyView('key-view-0-0', 100)));
    assert.ok(
        isPlannedKeyView(
            plannedKeyView('key-view-0-1', 101, {
                quality: 'limited',
                reasons: ['reducedVisibility']
            })
        )
    );
    const view = plannedKeyView('key-view-0-0', 100);
    assert.ok(!isPlannedKeyView(null));
    assert.ok(!isPlannedKeyView({ ...view, viewId: '' }));
    assert.ok(!isPlannedKeyView({ ...view, viewId: 'anchor-view' }));
    assert.ok(!isPlannedKeyView({ ...view, cameraBinding: null }));
    assert.ok(!isPlannedKeyView({ ...view, quality: 'unavailable' }));
    assert.ok(!isPlannedKeyView({ ...view, quality: 'good' }));
    assert.ok(!isPlannedKeyView({ ...view, reasons: [''] }));
    assert.ok(!isPlannedKeyView({ ...view, reasons: 'reducedVisibility' }));
});

test('a complete local Key-View plan validates', () => {
    const request = planRequest();
    assert.ok(isLocalKeyViewPlan(planFor(request)));
    // One to three bounded local Key Views per batch.
    assert.ok(
        isLocalKeyViewPlan(
            planFor(request, {
                orderedViews: [plannedKeyView('key-view-0-0', 100)]
            })
        )
    );
});

test('plan validation fails closed on malformed fields', () => {
    const request = planRequest();
    const plan = planFor(request);
    assert.ok(!isLocalKeyViewPlan(null));
    assert.ok(!isLocalKeyViewPlan({ ...plan, schemaVersion: 2 }));
    assert.ok(!isLocalKeyViewPlan({ ...plan, schemaVersion: '1' }));
    assert.ok(!isLocalKeyViewPlan({ ...plan, targetContextId: '' }));
    for (const field of [
        'anchorStableMaskDigest',
        'targetGeometryHintDigest',
        'localViewPolicyDigest',
        'artifactDigest'
    ]) {
        assert.ok(!isLocalKeyViewPlan({ ...plan, [field]: 'nope' }), field);
    }
    assert.ok(!isLocalKeyViewPlan({ ...plan, orderedViews: [] }));
    assert.ok(
        !isLocalKeyViewPlan({
            ...plan,
            orderedViews: [
                plannedKeyView('key-view-0-0', 100),
                plannedKeyView('key-view-0-1', 101),
                plannedKeyView('key-view-0-2', 102),
                plannedKeyView('key-view-0-3', 103)
            ]
        })
    );
    // View identity is unique within the plan and never the Anchor's.
    assert.ok(
        !isLocalKeyViewPlan({
            ...plan,
            orderedViews: [
                plannedKeyView('key-view-0-0', 100),
                plannedKeyView('key-view-0-0', 101)
            ]
        })
    );
    assert.ok(
        !isLocalKeyViewPlan({
            ...plan,
            orderedViews: [plannedKeyView('anchor-view', 100)]
        })
    );
    assert.ok(
        !isLocalKeyViewPlan({
            ...plan,
            orderedViews: [
                plannedKeyView('key-view-0-0', 100, { quality: 'unavailable' })
            ]
        })
    );
    assert.ok(!isLocalKeyViewPlan({ ...plan, planAttemptId: '' }));
});

test('a complete local Key-View plan response validates', () => {
    const request = planRequest();
    assert.ok(isLocalKeyViewPlanResponse(planResponseFor(request)));
});

test('plan response validation fails closed on malformed inputs', () => {
    const request = planRequest();
    const response = planResponseFor(request);
    assert.ok(!isLocalKeyViewPlanResponse(null));
    assert.ok(
        !isLocalKeyViewPlanResponse({ ...response, requestBinding: null })
    );
    assert.ok(!isLocalKeyViewPlanResponse({ ...response, targetSplatId: '' }));
    assert.ok(!isLocalKeyViewPlanResponse({ ...response, planAttemptId: '' }));
    assert.ok(!isLocalKeyViewPlanResponse({ ...response, batchOrdinal: -1 }));
    assert.ok(!isLocalKeyViewPlanResponse({ ...response, batchOrdinal: 0.5 }));
    assert.ok(
        !isLocalKeyViewPlanResponse({
            ...response,
            localViewPolicyVersion: 'local-key-view-planner/v0'
        })
    );
    assert.ok(
        !isLocalKeyViewPlanResponse({
            ...response,
            plan: planFor(request, { schemaVersion: 2 })
        })
    );
});

test('a matching plan response matches its request', () => {
    const request = planRequest();
    const response = planResponseFor(request);
    assert.ok(localKeyViewPlanResponseMatchesRequest(response, request));
});

test('plan matching fails closed on every identity echo mismatch', () => {
    const request = planRequest();
    const reject = (overrides) =>
        assert.ok(
            !localKeyViewPlanResponseMatchesRequest(
                planResponseFor(request, overrides),
                request
            ),
            JSON.stringify(Object.keys(overrides))
        );
    reject({
        requestBinding: {
            ...request.requestBinding,
            targetContextId: 'ai-target-context-2'
        }
    });
    reject({
        requestBinding: { ...request.requestBinding, contextRevision: 4 }
    });
    reject({
        requestBinding: {
            ...request.requestBinding,
            dependencyToken: dependency({ geometryToken: 'geometry-v2' })
        }
    });
    reject({ targetSplatId: 'editor-splat:2' });
    reject({ planAttemptId: 'local-key-view-plan-attempt-2' });
    // The batch ordinal echo binds exactly this Generate More batch.
    reject({ batchOrdinal: 1 });
});

test('plan matching fails closed on artifact binding drift', () => {
    const request = planRequest();
    const rejectWithPlan = (planOverrides) =>
        assert.ok(
            !localKeyViewPlanResponseMatchesRequest(
                planResponseFor(request, {
                    plan: planFor(request, planOverrides)
                }),
                request
            ),
            JSON.stringify(Object.keys(planOverrides))
        );
    rejectWithPlan({ targetContextId: 'ai-target-context-2' });
    rejectWithPlan({ anchorStableMaskDigest: digest('0') });
    // The plan must bind the exact Target Geometry Hint of this request.
    rejectWithPlan({ targetGeometryHintDigest: digest('0') });
    rejectWithPlan({ planAttemptId: 'local-key-view-plan-attempt-2' });
    // The request-side hint identity drives the match: a plan bound to a
    // different hint artifact digest is rejected.
    const otherRequest = planRequest({
        targetGeometryHint: hintArtifact({ artifactDigest: digest('7') })
    });
    assert.ok(
        !localKeyViewPlanResponseMatchesRequest(
            planResponseFor(otherRequest, {
                plan: planFor(request)
            }),
            otherRequest
        )
    );
});
