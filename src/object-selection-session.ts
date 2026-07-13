type StableGaussianId = number;

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
}

interface ObjectSelectionPromptLogEntry {
    operation: ObjectSelectionMode;
    prompt: ObjectSelectionPrompt;
}

interface CandidateObjectSelection {
    selectedIds: readonly StableGaussianId[];
    uncertainIds: readonly StableGaussianId[];
    rejectedIds: readonly StableGaussianId[];
}

interface ObjectSelectionPreviewRequest {
    sessionId: string;
    requestId: string;
    target: ObjectSelectionTarget;
    operation: ObjectSelectionMode;
    promptLog: readonly ObjectSelectionPromptLogEntry[];
}

interface SelectionServiceAdapter {
    openSession(start: ObjectSelectionSessionStart): Promise<string>;
    updatePreview(request: ObjectSelectionPreviewRequest): Promise<CandidateObjectSelection>;
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

const copyPrompt = (prompt: ObjectSelectionPrompt): ObjectSelectionPrompt => {
    return {
        promptId: prompt.promptId,
        viewId: prompt.viewId,
        xPx: prompt.xPx,
        yPx: prompt.yPx,
        polarity: prompt.polarity
    };
};

const copyStart = (start: ObjectSelectionSessionStart): ObjectSelectionSessionStart => {
    return {
        target: copyTarget(start.target),
        prompt: copyPrompt(start.prompt)
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
        rejectedIds: [...candidate.rejectedIds]
    };
};

class ObjectSelectionSession implements ObjectSelectionSessionInterface {
    private selectionService: SelectionServiceAdapter;
    private editor: ObjectSelectionSessionEditor;
    private sessionId: string | null = null;
    private entrySelection: StableGaussianId[] | null = null;
    private target: ObjectSelectionTarget | null = null;
    private promptLog: ObjectSelectionPromptLogEntry[] = [];
    private candidateSelection: CandidateObjectSelection | null = null;
    private sessionStatus: ObjectSelectionSessionStatus = 'idle';
    private mode: ObjectSelectionMode = 'New';
    private requestCount = 0;
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
            promptCount: this.promptLog.length
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
        this.entrySelection = [...this.editor.captureSelection()];
        this.target = copiedStart.target;
        this.promptLog = [{
            operation: 'New',
            prompt: copiedStart.prompt
        }];
        this.mode = 'New';
        this.requestCount = 0;
        this.setStatus('opening');

        try {
            this.sessionId = await this.selectionService.openSession(copyStart(copiedStart));
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
            operation: this.mode,
            promptLog: this.promptLog.map(copyPromptLogEntry)
        };

        try {
            const candidate = await this.selectionService.updatePreview(request);
            if (this.activePreview !== activePreview || activePreview.cancelled) {
                return;
            }

            this.candidateSelection = copyCandidate(candidate);
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
        this.setStatus('confirming');

        try {
            await this.editor.commitSelection([...candidate.selectedIds]);
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
        this.promptLog = [];
        this.candidateSelection = null;
        this.mode = 'New';
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
}

export { ObjectSelectionSession };

export type {
    CandidateObjectSelection,
    ObjectSelectionMode,
    ObjectSelectionPreviewRequest,
    ObjectSelectionPrompt,
    ObjectSelectionPromptLogEntry,
    ObjectSelectionPromptPolarity,
    ObjectSelectionSessionEditor,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionListener,
    ObjectSelectionSessionStart,
    ObjectSelectionSessionState,
    ObjectSelectionSessionStatus,
    ObjectSelectionTarget,
    SelectionServiceAdapter,
    StableGaussianId
};
