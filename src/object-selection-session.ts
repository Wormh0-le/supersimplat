type StableGaussianId = number;

interface CandidateObjectSelection {
    selectedIds: readonly StableGaussianId[];
    uncertainIds: readonly StableGaussianId[];
    rejectedIds: readonly StableGaussianId[];
}

interface SelectionServiceAdapter {
    openSession(): Promise<string>;
    updatePreview(sessionId: string): Promise<CandidateObjectSelection>;
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
    | 'preview'
    | 'confirming'
    | 'cancelling'
    | 'closed';

interface ObjectSelectionSessionState {
    status: ObjectSelectionSessionStatus;
    candidate: CandidateObjectSelection | null;
}

type ObjectSelectionSessionListener = (state: ObjectSelectionSessionState) => void;

// The toolbar, panel, and workflow tests cross this interface. The service and
// editor adapters remain implementation dependencies of the session module.
interface ObjectSelectionSessionInterface {
    readonly state: ObjectSelectionSessionState;

    subscribe(listener: ObjectSelectionSessionListener): () => void;
    startNew(): Promise<void>;
    updatePreview(): Promise<void>;
    confirm(): Promise<void>;
    cancel(): Promise<void>;
}

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
    private candidateSelection: CandidateObjectSelection | null = null;
    private sessionStatus: ObjectSelectionSessionStatus = 'idle';
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
            candidate: this.candidateSelection ? copyCandidate(this.candidateSelection) : null
        };
    }

    subscribe(listener: ObjectSelectionSessionListener) {
        this.listeners.add(listener);
        listener(this.state);

        return () => {
            this.listeners.delete(listener);
        };
    }

    async startNew() {
        this.requireStatus('idle');

        this.entrySelection = [...this.editor.captureSelection()];
        this.setStatus('opening');

        try {
            this.sessionId = await this.selectionService.openSession();
            this.setStatus('ready');
        } catch (error) {
            this.entrySelection = null;
            this.setStatus('idle');
            throw error;
        }
    }

    async updatePreview() {
        this.requireStatus('ready', 'preview');

        const previousStatus = this.sessionStatus;
        this.setStatus('previewing');

        try {
            const candidate = await this.selectionService.updatePreview(this.requireSessionId());
            this.candidateSelection = copyCandidate(candidate);
            this.setStatus('preview');
        } catch (error) {
            this.setStatus(previousStatus);
            throw error;
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

    private requireStatus(...allowed: ObjectSelectionSessionStatus[]) {
        if (!allowed.includes(this.sessionStatus)) {
            throw new Error(`Object Selection Session cannot run this command while ${this.sessionStatus}.`);
        }
    }

    private requireSessionId() {
        if (this.sessionId === null) {
            throw new Error('Object Selection Session has no active Selection Service session.');
        }
        return this.sessionId;
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

    private async closeSession() {
        const sessionId = this.sessionId;

        this.sessionId = null;
        this.entrySelection = null;
        this.candidateSelection = null;
        this.setStatus('closed');

        if (sessionId !== null) {
            await this.selectionService.closeSession(sessionId);
        }
    }

    private setStatus(status: ObjectSelectionSessionStatus) {
        this.sessionStatus = status;
        const state = this.state;
        this.listeners.forEach(listener => listener(state));
    }
}

export { ObjectSelectionSession };

export type {
    CandidateObjectSelection,
    ObjectSelectionSessionEditor,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionListener,
    ObjectSelectionSessionState,
    ObjectSelectionSessionStatus,
    SelectionServiceAdapter,
    StableGaussianId
};
