import {
    assertSceneSnapshot,
    isStableGaussianId,
    type SceneSnapshot,
    type SceneSnapshotBinding,
    type StableGaussianId
} from './scene-snapshot';

type ObjectSelectionMode = 'New' | 'Add' | 'Remove' | 'Refine';
type ObjectSelectionPromptPolarity = 'include' | 'exclude';

interface ObjectSelectionTarget {
    targetSplatId: string;
}

interface ObjectSelectionPrompt {
    promptId: string;
    viewId: string;
    xPx: number;
    yPx: number;
    polarity: ObjectSelectionPromptPolarity;
}

interface ObjectSelectionSessionStart {
    target: ObjectSelectionTarget;
    prompt: ObjectSelectionPrompt;
    scene: SceneSnapshotBinding;
    requestContext: ObjectSelectionRequestContext;
}

interface ObjectSelectionServiceSessionStart {
    target: ObjectSelectionTarget;
    prompt: ObjectSelectionPrompt;
    snapshot: SceneSnapshot;
    requestContext: ObjectSelectionRequestContext;
}

// These values are fixed for one session before the first service request.
// Keeping them in the editor-owned start input makes every later preview
// independently checkable without granting the service editor authority.
interface ObjectSelectionRequestContext {
    deterministicSeed: string;
    frameSetVersion: string;
    modelManifestDigest: string;
}

interface ObjectSelectionPromptLogEntry {
    operation: ObjectSelectionMode;
    prompt: ObjectSelectionPrompt;
}

interface SelectionResultIds {
    selectedIds: readonly StableGaussianId[];
    uncertainIds: readonly StableGaussianId[];
    rejectedIds: readonly StableGaussianId[];
}

interface CandidateObjectSelection extends SelectionResultIds {
    lockedIdsFiltered: number;
}

// A single versioned identity tuple crosses the editor/Companion boundary.
// Requests and every terminal/cache response use this exact structure.
interface ObjectSelectionPreviewBindings {
    sessionId: string;
    requestId: string;
    targetSplatId: string;
    sceneId: string;
    sceneVersion: string;
    operation: ObjectSelectionMode;
    correctionRound: number;
    deterministicSeed: string;
    promptLogRevision: number;
    frameSetVersion: string;
    renderConfigVersion: string;
    modelManifestDigest: string;
}

interface ObjectSelectionPreviewRequest extends ObjectSelectionPreviewBindings {
    target: ObjectSelectionTarget;
    promptLog: readonly ObjectSelectionPromptLogEntry[];
    snapshot: SceneSnapshot;
}

interface SelectionServicePreviewResponse extends ObjectSelectionPreviewBindings, SelectionResultIds {
    status: 'complete';
}

interface SelectionServiceAdapter {
    openSession(start: ObjectSelectionServiceSessionStart): Promise<string>;
    updatePreview(request: ObjectSelectionPreviewRequest): Promise<SelectionServicePreviewResponse>;
    cancelUpdate(sessionId: string, requestId: string): Promise<void>;
    closeSession(sessionId: string): Promise<void>;
}

interface ObjectSelectionSessionEditor {
    captureSelection(): readonly StableGaussianId[];

    // This is the only path that may create an editor selection-history entry.
    // Its editor adapter must use the existing SelectOp transition.
    commitSelection(selectedIds: readonly StableGaussianId[]): Promise<void>;

    // Restoring an entry selection is presentation recovery, not a commit.
    // It must not create a selection-history entry.
    restoreSelection(entrySelection: readonly StableGaussianId[]): Promise<void>;
}

type ObjectSelectionSessionStatus =
    | 'idle'
    | 'opening'
    | 'ready'
    | 'previewing'
    | 'cancellingUpdate'
    | 'preview'
    | 'confirming'
    | 'cancelling'
    | 'closing'
    | 'closeFailed';

interface ObjectSelectionSessionState {
    status: ObjectSelectionSessionStatus;
    candidate: CandidateObjectSelection | null;
    mode: ObjectSelectionMode;
    promptCount: number;
    lockedIdsFiltered: number;
}

type ObjectSelectionSessionListener = (state: ObjectSelectionSessionState) => void;

// The toolbar, panel, and workflow tests cross this interface. The service and
// editor adapters remain implementation dependencies of the session module.
interface ObjectSelectionSessionInterface {
    readonly state: ObjectSelectionSessionState;

    subscribe(listener: ObjectSelectionSessionListener): () => void;
    startNew(start: ObjectSelectionSessionStart): Promise<void>;
    setMode(mode: ObjectSelectionMode): void;
    stagePrompt(prompt: ObjectSelectionPrompt): void;
    updatePreview(): Promise<void>;
    cancelUpdate(): Promise<void>;
    confirm(): Promise<void>;
    cancel(): Promise<void>;
    retryCleanup(): Promise<void>;
}

interface ActivePreview {
    requestId: string;
    previousStatus: 'ready' | 'preview';
    cancelled: boolean;
}

const copyTarget = (target: ObjectSelectionTarget): ObjectSelectionTarget => {
    return {
        targetSplatId: target.targetSplatId
    };
};

const copyPreviewBindings = (
    bindings: ObjectSelectionPreviewBindings
): ObjectSelectionPreviewBindings => {
    return {
        sessionId: bindings.sessionId,
        requestId: bindings.requestId,
        targetSplatId: bindings.targetSplatId,
        sceneId: bindings.sceneId,
        sceneVersion: bindings.sceneVersion,
        operation: bindings.operation,
        correctionRound: bindings.correctionRound,
        deterministicSeed: bindings.deterministicSeed,
        promptLogRevision: bindings.promptLogRevision,
        frameSetVersion: bindings.frameSetVersion,
        renderConfigVersion: bindings.renderConfigVersion,
        modelManifestDigest: bindings.modelManifestDigest
    };
};

const previewBindingsFromRequest = (
    request: ObjectSelectionPreviewRequest
): ObjectSelectionPreviewBindings => copyPreviewBindings(request);

const previewBindingsMatch = (
    bindings: ObjectSelectionPreviewBindings,
    request: ObjectSelectionPreviewRequest
) => {
    const expected = previewBindingsFromRequest(request);
    return (
        bindings.sessionId === expected.sessionId &&
        bindings.requestId === expected.requestId &&
        bindings.targetSplatId === expected.targetSplatId &&
        bindings.sceneId === expected.sceneId &&
        bindings.sceneVersion === expected.sceneVersion &&
        bindings.operation === expected.operation &&
        bindings.correctionRound === expected.correctionRound &&
        bindings.deterministicSeed === expected.deterministicSeed &&
        bindings.promptLogRevision === expected.promptLogRevision &&
        bindings.frameSetVersion === expected.frameSetVersion &&
        bindings.renderConfigVersion === expected.renderConfigVersion &&
        bindings.modelManifestDigest === expected.modelManifestDigest
    );
};

const copyPrompt = (prompt: ObjectSelectionPrompt): ObjectSelectionPrompt => {
    return {
        promptId: prompt.promptId,
        viewId: prompt.viewId,
        xPx: prompt.xPx,
        yPx: prompt.yPx,
        polarity: prompt.polarity
    };
};

const copyRequestContext = (
    requestContext: ObjectSelectionRequestContext
): ObjectSelectionRequestContext => {
    return {
        deterministicSeed: requestContext.deterministicSeed,
        frameSetVersion: requestContext.frameSetVersion,
        modelManifestDigest: requestContext.modelManifestDigest
    };
};

const copyStart = (start: ObjectSelectionSessionStart): ObjectSelectionSessionStart => {
    return {
        target: copyTarget(start.target),
        prompt: copyPrompt(start.prompt),
        scene: start.scene,
        requestContext: copyRequestContext(start.requestContext)
    };
};

const copyServiceStart = (start: ObjectSelectionServiceSessionStart): ObjectSelectionServiceSessionStart => {
    return {
        target: copyTarget(start.target),
        prompt: copyPrompt(start.prompt),
        snapshot: start.snapshot,
        requestContext: copyRequestContext(start.requestContext)
    };
};

const copyPromptLogEntry = (entry: ObjectSelectionPromptLogEntry): ObjectSelectionPromptLogEntry => {
    return {
        operation: entry.operation,
        prompt: copyPrompt(entry.prompt)
    };
};

const copyCandidate = (candidate: CandidateObjectSelection): CandidateObjectSelection => {
    return {
        selectedIds: [...candidate.selectedIds],
        uncertainIds: [...candidate.uncertainIds],
        rejectedIds: [...candidate.rejectedIds],
        lockedIdsFiltered: candidate.lockedIdsFiltered
    };
};

class ObjectSelectionSession implements ObjectSelectionSessionInterface {
    private selectionService: SelectionServiceAdapter;
    private editor: ObjectSelectionSessionEditor;
    private sessionId: string | null = null;
    private entrySelection: StableGaussianId[] | null = null;
    private target: ObjectSelectionTarget | null = null;
    private scene: SceneSnapshotBinding | null = null;
    private snapshot: SceneSnapshot | null = null;
    private requestContext: ObjectSelectionRequestContext | null = null;
    private promptLog: ObjectSelectionPromptLogEntry[] = [];
    private candidateSelection: CandidateObjectSelection | null = null;
    private sessionStatus: ObjectSelectionSessionStatus = 'idle';
    private mode: ObjectSelectionMode = 'New';
    private requestCount = 0;
    private successfulPreviewCount = 0;
    private activePreview: ActivePreview | null = null;
    private listeners = new Set<ObjectSelectionSessionListener>();

    constructor(options: {
        selectionService: SelectionServiceAdapter;
        editor: ObjectSelectionSessionEditor;
    }) {
        this.selectionService = options.selectionService;
        this.editor = options.editor;
    }

    get state(): ObjectSelectionSessionState {
        return {
            status: this.sessionStatus,
            candidate: this.candidateSelection ? copyCandidate(this.candidateSelection) : null,
            mode: this.mode,
            promptCount: this.promptLog.length,
            lockedIdsFiltered: this.candidateSelection?.lockedIdsFiltered ?? 0
        };
    }

    subscribe(listener: ObjectSelectionSessionListener) {
        this.listeners.add(listener);
        listener(this.state);

        return () => {
            this.listeners.delete(listener);
        };
    }

    async startNew(start: ObjectSelectionSessionStart) {
        this.requireStatus('idle');

        const copiedStart = copyStart(start);
        const snapshot = copiedStart.scene.getSnapshot();
        assertSceneSnapshot(snapshot);
        this.assertRequestContext(copiedStart.requestContext);
        this.entrySelection = [...this.editor.captureSelection()];
        this.target = copiedStart.target;
        this.scene = copiedStart.scene;
        this.snapshot = snapshot;
        this.requestContext = copiedStart.requestContext;
        this.promptLog = [{
            operation: 'New',
            prompt: copiedStart.prompt
        }];
        this.mode = 'New';
        this.requestCount = 0;
        this.successfulPreviewCount = 0;
        this.setStatus('opening');

        try {
            this.sessionId = await this.selectionService.openSession(copyServiceStart({
                target: copiedStart.target,
                prompt: copiedStart.prompt,
                snapshot,
                requestContext: copiedStart.requestContext
            }));
            this.setStatus('ready');
        } catch (error) {
            this.clearSessionState();
            this.setStatus('idle');
            throw error;
        }
    }

    setMode(mode: ObjectSelectionMode) {
        this.requireStatus('ready', 'preview');
        this.mode = mode;
        this.publishState();
    }

    stagePrompt(prompt: ObjectSelectionPrompt) {
        this.requireStatus('ready', 'preview');
        this.promptLog.push({
            operation: this.mode,
            prompt: copyPrompt(prompt)
        });
        this.publishState();
    }

    async updatePreview() {
        const previousStatus = this.requirePreviewStatus();
        this.requireCurrentSnapshot();

        const activePreview: ActivePreview = {
            requestId: `request-${++this.requestCount}`,
            previousStatus,
            cancelled: false
        };
        this.activePreview = activePreview;
        this.setStatus('previewing');

        const request: ObjectSelectionPreviewRequest = {
            sessionId: this.requireSessionId(),
            requestId: activePreview.requestId,
            target: copyTarget(this.requireTarget()),
            targetSplatId: this.requireTarget().targetSplatId,
            sceneId: this.requireSnapshot().sceneId,
            sceneVersion: this.requireSnapshot().sceneVersion,
            operation: this.mode,
            correctionRound: this.successfulPreviewCount,
            deterministicSeed: this.requireRequestContext().deterministicSeed,
            promptLogRevision: this.promptLog.length,
            frameSetVersion: this.requireRequestContext().frameSetVersion,
            renderConfigVersion: this.requireSnapshot().renderConfiguration.version,
            modelManifestDigest: this.requireRequestContext().modelManifestDigest,
            promptLog: this.promptLog.map(copyPromptLogEntry),
            snapshot: this.requireSnapshot()
        };

        try {
            const response = await this.selectionService.updatePreview(request);
            if (this.activePreview !== activePreview || activePreview.cancelled) {
                return;
            }

            this.requireCurrentSnapshot();
            this.validatePreviewResponse(response, request);
            this.candidateSelection = copyCandidate(this.filterLockedIds(response));
            this.successfulPreviewCount += 1;
            this.setStatus('preview');
        } catch (error) {
            if (!activePreview.cancelled) {
                this.setStatus(activePreview.previousStatus);
                throw error;
            }
        } finally {
            if (this.activePreview === activePreview) {
                this.activePreview = null;
            }
        }
    }

    async cancelUpdate() {
        this.requireStatus('previewing');

        const activePreview = this.requireActivePreview();
        activePreview.cancelled = true;
        this.setStatus('cancellingUpdate');

        try {
            await this.selectionService.cancelUpdate(this.requireSessionId(), activePreview.requestId);
        } catch (error) {
            // Once cancellation has been requested, never let a racing result
            // replace the preceding usable Candidate Object Selection. A failed
            // abort is recoverable by submitting a fresh preview request.
            activePreview.cancelled = true;
            if (this.activePreview === activePreview) {
                this.activePreview = null;
            }
            if (this.sessionStatus === 'cancellingUpdate') {
                this.setStatus(activePreview.previousStatus);
            }
            throw error;
        }

        if (this.activePreview === activePreview) {
            this.activePreview = null;
        }
        if (this.sessionStatus === 'cancellingUpdate') {
            this.setStatus(activePreview.previousStatus);
        }
    }

    async confirm() {
        this.requireStatus('preview');

        const candidate = this.requireCandidate();
        this.requireCurrentSnapshot();
        const selectedIds = this.filterLockedIds(candidate).selectedIds;
        this.setStatus('confirming');

        try {
            await this.editor.commitSelection([...selectedIds]);
        } catch (error) {
            this.setStatus('preview');
            throw error;
        }

        await this.closeSession();
    }

    async cancel() {
        if (this.sessionStatus === 'previewing') {
            await this.cancelUpdate();
        }
        this.requireStatus('ready', 'preview');

        const previousStatus = this.sessionStatus;
        this.setStatus('cancelling');

        try {
            await this.editor.restoreSelection(this.requireEntrySelection());
        } catch (error) {
            this.setStatus(previousStatus);
            throw error;
        }

        await this.closeSession();
    }

    async retryCleanup() {
        this.requireStatus('closeFailed');
        await this.closeSession();
    }

    private requireStatus(...allowed: ObjectSelectionSessionStatus[]) {
        if (!allowed.includes(this.sessionStatus)) {
            throw new Error(`Object Selection Session cannot run this command while ${this.sessionStatus}.`);
        }
    }

    private requirePreviewStatus(): 'ready' | 'preview' {
        if (this.sessionStatus !== 'ready' && this.sessionStatus !== 'preview') {
            throw new Error(`Object Selection Session cannot update preview while ${this.sessionStatus}.`);
        }
        return this.sessionStatus;
    }

    private requireSessionId() {
        if (this.sessionId === null) {
            throw new Error('Object Selection Session has no active Selection Service session.');
        }
        return this.sessionId;
    }

    private requireTarget() {
        if (this.target === null) {
            throw new Error('Object Selection Session has no Target Splat.');
        }
        return this.target;
    }

    private requireSnapshot() {
        if (this.snapshot === null) {
            throw new Error('Object Selection Session has no Scene Snapshot.');
        }
        return this.snapshot;
    }

    private requireRequestContext() {
        if (this.requestContext === null) {
            throw new Error('Object Selection Session has no immutable request context.');
        }
        return this.requestContext;
    }

    private requireCurrentSnapshot() {
        const scene = this.requireScene();
        const snapshot = this.requireSnapshot();
        if (!scene.isCurrent(snapshot)) {
            throw new Error('The Target Splat changed while this Object Selection Session was active. Start a new session for its current Scene Snapshot.');
        }
        return snapshot;
    }

    private requireScene() {
        if (this.scene === null) {
            throw new Error('Object Selection Session has no editor Scene Snapshot binding.');
        }
        return this.scene;
    }

    private requireCandidate() {
        if (this.candidateSelection === null) {
            throw new Error('Object Selection Session has no Candidate Object Selection to confirm.');
        }
        return this.candidateSelection;
    }

    private requireEntrySelection() {
        if (this.entrySelection === null) {
            throw new Error('Object Selection Session has no entry Gaussian Selection to restore.');
        }
        return [...this.entrySelection];
    }

    private requireActivePreview() {
        if (this.activePreview === null) {
            throw new Error('Object Selection Session has no active preview update to cancel.');
        }
        return this.activePreview;
    }

    private async closeSession() {
        const sessionId = this.requireSessionId();
        this.setStatus('closing');

        try {
            await this.selectionService.closeSession(sessionId);
        } catch (error) {
            this.setStatus('closeFailed');
            throw error;
        }

        this.clearSessionState();
        this.setStatus('idle');
    }

    private clearSessionState() {
        this.sessionId = null;
        this.entrySelection = null;
        this.target = null;
        this.scene = null;
        this.snapshot = null;
        this.requestContext = null;
        this.promptLog = [];
        this.candidateSelection = null;
        this.mode = 'New';
        this.successfulPreviewCount = 0;
        this.activePreview = null;
    }

    private setStatus(status: ObjectSelectionSessionStatus) {
        this.sessionStatus = status;
        this.publishState();
    }

    private publishState() {
        const state = this.state;
        this.listeners.forEach(listener => listener(state));
    }

    private assertRequestContext(context: ObjectSelectionRequestContext) {
        if (
            !context.deterministicSeed ||
            !context.frameSetVersion ||
            !context.modelManifestDigest
        ) {
            throw new Error('Object Selection Session requires deterministic seed, Frame Set, and Model Manifest bindings.');
        }
    }

    private validatePreviewResponse(
        response: SelectionServicePreviewResponse,
        request: ObjectSelectionPreviewRequest
    ) {
        if (response.status !== 'complete') {
            throw new Error('The Selection Service Companion did not return a complete preview result.');
        }
        if (!previewBindingsMatch(response, request)) {
            throw new Error('The Selection Service Companion returned stale Object Selection request bindings.');
        }

        const knownIds = new Set(request.snapshot.gaussians.map(gaussian => gaussian.stableId));
        const returnedIds = new Set<StableGaussianId>();
        const sets: Array<[string, readonly StableGaussianId[]]> = [
            ['selected', response.selectedIds],
            ['uncertain', response.uncertainIds],
            ['rejected', response.rejectedIds]
        ];

        sets.forEach(([name, ids]) => {
            let previous = -1;
            ids.forEach((id) => {
                if (!isStableGaussianId(id) || !knownIds.has(id)) {
                    throw new Error(`The Selection Service Companion returned an unknown ${name} Stable Gaussian ID.`);
                }
                if (id <= previous) {
                    throw new Error(`The Selection Service Companion must return sorted unique ${name} Stable Gaussian IDs.`);
                }
                if (returnedIds.has(id)) {
                    throw new Error('The Selection Service Companion returned overlapping Candidate Object Selection ID sets.');
                }
                previous = id;
                returnedIds.add(id);
            });
        });
        if (returnedIds.size !== knownIds.size) {
            throw new Error('The Selection Service Companion returned an incomplete Candidate Object Selection.');
        }
    }

    private filterLockedIds(
        candidate: SelectionResultIds & Partial<Pick<CandidateObjectSelection, 'lockedIdsFiltered'>>
    ): CandidateObjectSelection {
        const scene = this.requireScene();
        let lockedIdsFiltered = candidate.lockedIdsFiltered ?? 0;
        const filter = (ids: readonly StableGaussianId[]) => ids.filter((id) => {
            const locked = scene.isLocked(id);
            if (locked) {
                lockedIdsFiltered += 1;
            }
            return !locked;
        });
        return {
            selectedIds: filter(candidate.selectedIds),
            uncertainIds: filter(candidate.uncertainIds),
            rejectedIds: filter(candidate.rejectedIds),
            lockedIdsFiltered
        };
    }
}

export {
    ObjectSelectionSession,
    copyPreviewBindings,
    previewBindingsFromRequest,
    previewBindingsMatch
};

export type {
    CandidateObjectSelection,
    ObjectSelectionMode,
    ObjectSelectionPreviewBindings,
    ObjectSelectionPreviewRequest,
    ObjectSelectionPrompt,
    ObjectSelectionPromptLogEntry,
    ObjectSelectionPromptPolarity,
    ObjectSelectionRequestContext,
    ObjectSelectionServiceSessionStart,
    ObjectSelectionSessionEditor,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionListener,
    ObjectSelectionSessionStart,
    ObjectSelectionSessionState,
    ObjectSelectionSessionStatus,
    ObjectSelectionTarget,
    SelectionServiceAdapter,
    SelectionServicePreviewResponse,
    SelectionResultIds,
    StableGaussianId
};
