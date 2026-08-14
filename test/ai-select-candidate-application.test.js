const assert = require('node:assert/strict');
const Module = require('node:module');
const test = require('node:test');

class TestEventHandler {
    constructor() {
        this.callbacks = new Map();
    }

    on(name, callback) {
        const callbacks = this.callbacks.get(name) ?? [];
        callbacks.push(callback);
        this.callbacks.set(name, callbacks);
    }

    fire(name, ...args) {
        (this.callbacks.get(name) ?? []).forEach((callback) =>
            callback(...args)
        );
    }
}

class UnusedPlayCanvasType {}

const originalModuleLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (request === 'playcanvas') {
        return new Proxy(
            { EventHandler: TestEventHandler },
            {
                get: (target, property) =>
                    target[property] ?? UnusedPlayCanvasType
            }
        );
    }
    return originalModuleLoad.call(this, request, parent, isMain);
};

const {
    CandidateApplicationBlockedError,
    CandidateApplicationController
} = require('../.test-dist/src/ai-select/candidate-application.js');
const {
    CandidatePublicationStore,
    createCandidatePublicationBinding,
    createReferenceCandidateArtifact
} = require('../.test-dist/src/ai-select/candidate-publication.js');
const {
    AISelectDirtyStateTracker
} = require('../.test-dist/src/ai-select/dirty-state.js');
const {
    SelectOpCandidateNativeSelection
} = require('../.test-dist/src/ai-select-candidate-application.js');
const { CommandQueue } = require('../.test-dist/src/command-queue.js');
const { EditHistory } = require('../.test-dist/src/edit-history.js');
const { Events } = require('../.test-dist/src/events.js');
Module._load = originalModuleLoad;

const digest = (letter) => `sha256:${letter.repeat(64)}`;

const dependency = (overrides = {}) => ({
    splatId: 'editor-splat:1',
    renderStateToken: 'render-v1',
    geometryToken: 'geometry-v1',
    gaussianIdentityToken: 'gaussians-v1',
    worldTransformToken: 'transform-v1',
    ...overrides
});

const publicationBinding = (overrides = {}) =>
    createCandidatePublicationBinding({
        requestBinding: {
            targetContextId: 'ai-target-context-1',
            contextRevision: 3,
            dependencyToken: dependency()
        },
        targetSplatId: 'editor-splat:1',
        stableInputs: [
            {
                viewId: 'anchor-view',
                participation: 'included',
                stableMaskDigest: digest('a'),
                evidenceArtifactDigest: digest('b')
            }
        ],
        aggregationPolicyDigest: digest('c'),
        sourceEvidencePolicyDigest: digest('d'),
        evidenceWorkingSetToken: digest('e'),
        evidenceArtifactSetDigest: digest('f'),
        referenceBackendIdentity: {
            rasterImplementationId: 'gsplat-reference-rgb/v1',
            evidenceBackendKind: 'reference-contributor',
            evidenceBackendId: 'complete-contributor/reference-v1',
            runtimeBuildId: 'locked-runtime-build-1'
        },
        ...overrides
    });

const publishCandidate = (store, binding = publicationBinding()) => {
    const candidate = createReferenceCandidateArtifact({
        publicationBinding: binding,
        sourceAggregationResultDigest: digest('1'),
        selectedStableGaussianIds: [1, 3],
        uncertainStableGaussianIds: [2]
    });
    store.publish(candidate, binding);
    return candidate;
};

const createNativeSelection = (initialSelected = []) => {
    const data = new Uint8Array(5);
    initialSelected.forEach((index) => {
        data[index] = 1;
    });
    const state = {
        data,
        setBits(ranges, mask) {
            ranges.forEach((index) => {
                data[index] |= mask;
            });
        },
        clearBits(ranges, mask) {
            ranges.forEach((index) => {
                data[index] &= ~mask;
            });
        },
        toggleBits(ranges, mask) {
            ranges.forEach((index) => {
                data[index] ^= mask;
            });
        }
    };
    const splat = {
        splatData: {
            numSplats: data.length,
            getProp: (name) => (name === 'state' ? data : undefined)
        },
        state,
        updateState: async () => {}
    };
    return {
        splat,
        selected: () =>
            Array.from(data.keys()).filter((index) => (data[index] & 1) !== 0)
    };
};

const createHarness = ({
    initialSelected = [],
    applicationMode = 'production',
    getAcceptedRuntime = () => null,
    contextLifecycle = 'active',
    effectiveDependencyToken = dependency(),
    beforeNativeValidation = () => {},
    nativeFailure = null
} = {}) => {
    const dirtyState = new AISelectDirtyStateTracker();
    const candidates = new CandidatePublicationStore(dirtyState);
    const native = createNativeSelection(initialSelected);
    const nativeHistory = [];
    let nativeHistoryCursor = 0;
    const setSelected = (selectedIds) => {
        const selected = new Set(selectedIds);
        native.splat.state.data.forEach((_value, index) => {
            native.splat.state.data[index] = selected.has(index) ? 1 : 0;
        });
    };
    const nativeSelection = {
        apply: async (operation, candidateIds, validateCurrent) => {
            beforeNativeValidation();
            validateCurrent();
            if (nativeFailure !== null) {
                throw nativeFailure;
            }
            const before = native.selected();
            const current = new Set(before);
            const candidate = new Set(candidateIds);
            const after = Array.from(native.splat.state.data.keys()).filter(
                (index) => {
                    if (operation === 'set') {
                        return candidate.has(index);
                    }
                    if (operation === 'add') {
                        return current.has(index) || candidate.has(index);
                    }
                    if (operation === 'remove') {
                        return current.has(index) && !candidate.has(index);
                    }
                    return current.has(index) && candidate.has(index);
                }
            );
            const command = {
                name: 'selectOp',
                operation,
                undo: async () => setSelected(before),
                redo: async () => setSelected(after)
            };
            nativeHistory.splice(nativeHistoryCursor);
            nativeHistory.push(command);
            nativeHistoryCursor += 1;
            setSelected(after);
            return command;
        },
        undo: async () => {
            if (nativeHistoryCursor === 0) {
                return;
            }
            nativeHistoryCursor -= 1;
            await nativeHistory[nativeHistoryCursor].undo();
        },
        redo: async () => {
            if (nativeHistoryCursor === nativeHistory.length) {
                return;
            }
            await nativeHistory[nativeHistoryCursor].redo();
            nativeHistoryCursor += 1;
        }
    };
    const context = {
        targetContextId: 'ai-target-context-1',
        revision: 3,
        target: { splatId: 'editor-splat:1' },
        dependencyToken: dependency(),
        lifecycle: contextLifecycle
    };
    const controller = new CandidateApplicationController({
        candidates,
        nativeSelection,
        applicationMode,
        getAcceptedRuntime,
        getTarget: () => ({
            context,
            effectiveDependencyToken
        })
    });
    return {
        candidates,
        controller,
        dirtyState,
        nativeHistory,
        nativeSelection,
        native
    };
};

const acceptedReferenceRuntime = () => ({
    rasterImplementationId: 'gsplat-reference-rgb/v1',
    evidenceBackendKind: 'reference-contributor',
    evidenceBackendId: 'complete-contributor/reference-v1',
    runtimeBuildId: 'locked-runtime-build-1',
    sourceEvidencePolicyDigest: digest('d'),
    aggregationPolicyDigest: digest('c')
});

const acceptedProductionRuntime = () => ({
    ...acceptedReferenceRuntime(),
    rasterImplementationId: 'gsplat-direct-rgb/v1',
    evidenceBackendKind: 'production-direct',
    evidenceBackendId: 'gsplat-direct-pnv/v1',
    runtimeBuildId: 'production-runtime-build-1'
});

test('a reference Candidate is blocked by the default production application gate', async () => {
    const harness = createHarness({ initialSelected: [0, 4] });
    publishCandidate(harness.candidates);

    assert.equal(harness.controller.state.status, 'blocked');
    assert.equal(harness.controller.state.blockReason, 'reference-disallowed');
    await assert.rejects(
        harness.controller.apply('set'),
        (error) =>
            error instanceof CandidateApplicationBlockedError &&
            error.reason === 'reference-disallowed'
    );
    assert.deepEqual(harness.native.selected(), [0, 4]);
    assert.equal(harness.nativeHistory.length, 0);
    assert.equal(harness.candidates.presentationState.status, 'current');
});

test('the production gate accepts an exact production-ready Candidate identity', async () => {
    const native = createNativeSelection([0, 2, 4]);
    const {
        referenceBackendIdentity: _referenceBackendIdentity,
        ...baseBinding
    } = publicationBinding();
    const binding = Object.freeze({
        ...baseBinding,
        evidenceBackendIdentity: {
            rasterImplementationId: 'gsplat-direct-rgb/v1',
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: 'gsplat-direct-pnv/v1',
            runtimeBuildId: 'production-runtime-build-1'
        }
    });
    const artifact = Object.freeze({
        productionReadiness: 'production-ready',
        publicationBinding: binding,
        candidate: Object.freeze({ selectedStableGaussianIds: [1, 3] }),
        candidateDigest: digest('7')
    });
    const source = {
        presentationState: Object.freeze({ status: 'current' }),
        inspectableCandidate: artifact,
        subscribe(listener) {
            listener(this.presentationState);
            return () => {};
        }
    };
    const nativeHistory = [];
    const controller = new CandidateApplicationController({
        candidates: source,
        nativeSelection: {
            apply: async (operation, selectedIds, validateCurrent) => {
                validateCurrent();
                nativeHistory.push({ name: 'selectOp' });
                native.splat.state.data.fill(0);
                selectedIds.forEach((id) => {
                    native.splat.state.data[id] = 1;
                });
                return nativeHistory[0];
            }
        },
        applicationMode: 'production',
        getAcceptedRuntime: acceptedProductionRuntime,
        getTarget: () => ({
            context: {
                targetContextId: 'ai-target-context-1',
                revision: 3,
                target: { splatId: 'editor-splat:1' },
                dependencyToken: dependency(),
                lifecycle: 'active'
            },
            effectiveDependencyToken: dependency()
        })
    });

    assert.equal(controller.state.status, 'ready');
    const record = await controller.apply('set');

    assert.deepEqual(native.selected(), [1, 3]);
    assert.equal(record.evidenceBackendKind, 'production-direct');
    assert.equal(record.nativeHistoryCommand, nativeHistory[0]);
});

test('an explicit development capability applies Selected-only through native history', async () => {
    const harness = createHarness({
        initialSelected: [0, 2, 4],
        applicationMode: 'development-reference',
        getAcceptedRuntime: acceptedReferenceRuntime
    });
    const candidate = publishCandidate(harness.candidates);

    assert.equal(harness.controller.state.status, 'ready');
    const record = await harness.controller.apply('set');

    assert.deepEqual(harness.native.selected(), [1, 3]);
    assert.equal(harness.nativeHistory.length, 1);
    assert.equal(record.nativeHistoryCommand, harness.nativeHistory[0]);
    assert.deepEqual(record.candidateRevision, {
        candidateDigest: candidate.candidateDigest,
        targetContextId: 'ai-target-context-1',
        contextRevision: 3
    });
    assert.equal(record.rasterImplementationId, 'gsplat-reference-rgb/v1');
    assert.equal(record.evidenceBackendKind, 'reference-contributor');
    assert.equal(record.evidenceBackendId, 'complete-contributor/reference-v1');
    assert.equal(record.runtimeBuildId, 'locked-runtime-build-1');
    assert.deepEqual(record.policyIdentity, {
        sourceEvidencePolicyDigest: digest('d'),
        aggregationPolicyDigest: digest('c')
    });
    assert.equal(record.operation, 'set');
    assert.equal(harness.controller.state.status, 'applied');
    assert.equal(harness.controller.state.overlayEmphasis, 'deemphasized');

    harness.controller.showAIResult();
    assert.equal(harness.controller.state.status, 'applied');
    assert.equal(harness.controller.state.overlayEmphasis, 'emphasized');

    await harness.nativeSelection.undo();
    assert.deepEqual(harness.native.selected(), [0, 2, 4]);
    assert.equal(harness.candidates.presentationState.status, 'current');

    await harness.nativeSelection.redo();
    assert.deepEqual(harness.native.selected(), [1, 3]);
    assert.equal(harness.candidates.presentationState.status, 'current');
});

test('a failing observer cannot cancel or misreport a native application', async () => {
    const harness = createHarness({
        initialSelected: [0, 2, 4],
        applicationMode: 'development-reference',
        getAcceptedRuntime: acceptedReferenceRuntime
    });
    publishCandidate(harness.candidates);
    const observerError = new Error('observer failed');
    const originalConsoleError = console.error;
    const reportedErrors = [];
    console.error = (error) => reportedErrors.push(error);
    let shouldThrow = false;
    harness.controller.subscribe(() => {
        if (shouldThrow) {
            throw observerError;
        }
    });
    shouldThrow = true;

    try {
        const record = await harness.controller.apply('set');

        assert.equal(record.operation, 'set');
        assert.deepEqual(harness.native.selected(), [1, 3]);
        assert.equal(harness.nativeHistory.length, 1);
        assert.equal(harness.controller.state.status, 'applied');
        assert.deepEqual(reportedErrors, [observerError, observerError]);
    } finally {
        console.error = originalConsoleError;
    }
});

test('an applied record and de-emphasis never leak to a replacement Candidate', async () => {
    let runtime = acceptedReferenceRuntime();
    const harness = createHarness({
        applicationMode: 'development-reference',
        getAcceptedRuntime: () => runtime
    });
    publishCandidate(harness.candidates);
    await harness.controller.apply('set');
    const replacementBinding = publicationBinding({
        evidenceArtifactSetDigest: digest('8')
    });
    publishCandidate(harness.candidates, replacementBinding);
    runtime = {
        ...acceptedReferenceRuntime(),
        runtimeBuildId: 'other-runtime-build'
    };
    harness.controller.refresh();

    assert.equal(harness.controller.state.status, 'blocked');
    assert.equal(harness.controller.state.applicationRecord, null);
    assert.equal(harness.controller.state.overlayEmphasis, 'emphasized');
});

test('the real SelectOp/EditHistory adapter is undoable and preserves a redo branch on failure', async () => {
    const native = createNativeSelection([0, 2, 4]);
    let updateFailure = null;
    native.splat.updateState = async () => {
        if (updateFailure !== null) {
            const error = updateFailure;
            updateFailure = null;
            throw error;
        }
    };
    const events = new Events();
    const history = new EditHistory(events, new CommandQueue());
    const adapter = new SelectOpCandidateNativeSelection({
        editHistory: history,
        getTarget: () => ({
            targetSplat: native.splat,
            stableIds: {
                toSplatIndices: (ids) => Uint32Array.from(ids)
            }
        })
    });

    const command = await adapter.apply('set', [1, 3], () => {});
    assert.equal(command.name, 'selectOp');
    assert.deepEqual(native.selected(), [1, 3]);
    assert.equal(history.canUndo(), true);

    await history.undo();
    assert.deepEqual(native.selected(), [0, 2, 4]);
    assert.equal(history.canRedo(), true);

    const originalConsoleError = console.error;
    console.error = () => {};
    updateFailure = new Error('native flush failed');
    try {
        await assert.rejects(
            adapter.apply('add', [1, 3], () => {}),
            /native flush failed/
        );
    } finally {
        console.error = originalConsoleError;
    }
    assert.deepEqual(native.selected(), [0, 2, 4]);
    assert.equal(history.canRedo(), true);

    await history.redo();
    assert.deepEqual(native.selected(), [1, 3]);
});

test('real history observer and discarded-command cleanup failures cannot misreport a committed application', async () => {
    const native = createNativeSelection([0, 2, 4]);
    const events = new Events();
    const history = new EditHistory(events, new CommandQueue());
    await history.add({
        name: 'discarded',
        do: () => {},
        undo: () => {},
        destroy: () => {
            throw new Error('discard cleanup failed');
        }
    });
    await history.undo();
    events.on('edit.apply', () => {
        throw new Error('history observer failed');
    });
    const adapter = new SelectOpCandidateNativeSelection({
        editHistory: history,
        getTarget: () => ({
            targetSplat: native.splat,
            stableIds: {
                toSplatIndices: (ids) => Uint32Array.from(ids)
            }
        })
    });
    const originalConsoleError = console.error;
    const reportedErrors = [];
    console.error = (error) => reportedErrors.push(error);

    try {
        const command = await adapter.apply('set', [1, 3], () => {});

        assert.equal(command.name, 'selectOp');
        assert.deepEqual(native.selected(), [1, 3]);
        assert.equal(history.canUndo(), true);
        assert.equal(history.canRedo(), false);
        assert.deepEqual(
            reportedErrors.map((error) => error.message),
            ['discard cleanup failed', 'history observer failed']
        );
    } finally {
        console.error = originalConsoleError;
    }
});

test('Add, Remove, and Intersect use exact native set algebra', async (t) => {
    const cases = [
        { operation: 'add', expected: [0, 1, 2, 3, 4] },
        { operation: 'remove', expected: [0, 2, 4] },
        { operation: 'intersect', expected: [] }
    ];
    for (const { operation, expected } of cases) {
        await t.test(operation, async () => {
            const harness = createHarness({
                initialSelected: [0, 2, 4],
                applicationMode: 'development-reference',
                getAcceptedRuntime: acceptedReferenceRuntime
            });
            publishCandidate(harness.candidates);

            await harness.controller.apply(operation);

            assert.deepEqual(harness.native.selected(), expected);
            assert.equal(
                harness.controller.state.applicationRecord.operation,
                operation
            );
        });
    }
});

test('stale, suspended, and incompatible Candidates expose actionable block reasons', async (t) => {
    const cases = [
        {
            name: 'suspended context',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: acceptedReferenceRuntime,
                contextLifecycle: 'suspended'
            },
            expected: 'context-suspended'
        },
        {
            name: 'changed target dependency',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: acceptedReferenceRuntime,
                effectiveDependencyToken: dependency({
                    geometryToken: 'geometry-v2'
                })
            },
            expected: 'target-mismatch'
        },
        {
            name: 'unverified runtime',
            options: { applicationMode: 'development-reference' },
            expected: 'runtime-unverified'
        },
        {
            name: 'renderer mismatch',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: () => ({
                    ...acceptedReferenceRuntime(),
                    rasterImplementationId: 'other-renderer/v1'
                })
            },
            expected: 'renderer-incompatible'
        },
        {
            name: 'backend mismatch',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: () => ({
                    ...acceptedReferenceRuntime(),
                    evidenceBackendId: 'other-backend/v1'
                })
            },
            expected: 'backend-incompatible'
        },
        {
            name: 'runtime build mismatch',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: () => ({
                    ...acceptedReferenceRuntime(),
                    runtimeBuildId: 'other-runtime-build'
                })
            },
            expected: 'runtime-incompatible'
        },
        {
            name: 'policy mismatch',
            options: {
                applicationMode: 'development-reference',
                getAcceptedRuntime: () => ({
                    ...acceptedReferenceRuntime(),
                    sourceEvidencePolicyDigest: digest('9')
                })
            },
            expected: 'policy-incompatible'
        }
    ];
    for (const entry of cases) {
        await t.test(entry.name, () => {
            const harness = createHarness(entry.options);
            publishCandidate(harness.candidates);

            assert.equal(harness.controller.state.status, 'blocked');
            assert.equal(harness.controller.state.blockReason, entry.expected);
        });
    }

    await t.test('stale Candidate', () => {
        const harness = createHarness({
            applicationMode: 'development-reference',
            getAcceptedRuntime: acceptedReferenceRuntime
        });
        publishCandidate(harness.candidates);
        harness.dirtyState.markParticipationChanged('anchor-view');

        assert.equal(harness.controller.state.status, 'blocked');
        assert.equal(harness.controller.state.blockReason, 'candidate-stale');
    });
});

test('a queued stale race or native failure leaves selection and history unchanged', async (t) => {
    await t.test('Candidate becomes stale in the queue', async () => {
        let harness;
        harness = createHarness({
            initialSelected: [0, 4],
            applicationMode: 'development-reference',
            getAcceptedRuntime: acceptedReferenceRuntime,
            beforeNativeValidation: () =>
                harness.dirtyState.markParticipationChanged('anchor-view')
        });
        publishCandidate(harness.candidates);

        await assert.rejects(
            harness.controller.apply('set'),
            (error) =>
                error instanceof CandidateApplicationBlockedError &&
                error.reason === 'candidate-stale'
        );
        assert.deepEqual(harness.native.selected(), [0, 4]);
        assert.equal(harness.nativeHistory.length, 0);
        assert.equal(harness.candidates.presentationState.status, 'stale');
    });

    await t.test('native command fails', async () => {
        const failure = new Error('native selection failed');
        const harness = createHarness({
            initialSelected: [0, 4],
            applicationMode: 'development-reference',
            getAcceptedRuntime: acceptedReferenceRuntime,
            nativeFailure: failure
        });
        publishCandidate(harness.candidates);

        await assert.rejects(harness.controller.apply('set'), failure);
        assert.deepEqual(harness.native.selected(), [0, 4]);
        assert.equal(harness.nativeHistory.length, 0);
        assert.equal(harness.candidates.presentationState.status, 'current');
        assert.equal(harness.controller.state.status, 'ready');
    });
});
