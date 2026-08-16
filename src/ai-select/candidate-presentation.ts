import type {
    CandidateApplicationBlockReason,
    CandidateApplicationOperation,
    CandidateApplicationState,
    CandidateUndoAndFixBlockReason
} from './candidate-application';
import type { CandidateCorrectionState } from './candidate-correction';
import type { CandidatePublicationState } from './candidate-publication';

export type CandidateOperationDisabledReason =
    | 'wait-for-update'
    | 'complete-or-exit-correction'
    | 'update-candidate'
    | 'restart-target';

export type CandidatePresentationLifecycle =
    | 'current'
    | 'stale'
    | 'updating'
    | 'update-failed'
    | 'correcting'
    | `applied-${CandidateApplicationOperation}`;

export interface CandidatePresentation {
    readonly inspectable: boolean;
    readonly counts: Readonly<{
        selected: number;
        uncertain: number;
    }>;
    readonly dock: Readonly<{
        showCandidateSummary: boolean;
        showFixCandidate: boolean;
        showUpdateCandidate: boolean;
        showBackToCandidate: boolean;
        applicationOutcome: CandidateApplicationOperation | null;
    }>;
    readonly toolbar: Readonly<{
        visible: boolean;
        operationsEnabled: boolean;
        disabledReason: CandidateOperationDisabledReason | null;
        technicalBlockReason: CandidateApplicationBlockReason | null;
        undoAndFixEnabled: boolean;
        undoAndFixDisabledReason: CandidateUndoAndFixBlockReason | null;
    }>;
    readonly statusBar: Readonly<{
        visible: boolean;
        lifecycle: CandidatePresentationLifecycle | null;
    }>;
    readonly overlay: Readonly<{
        membership: CandidatePublicationState['overlay'];
        treatment: 'current' | 'stale' | null;
    }>;
}

export interface CandidatePresentationInput {
    readonly candidate: CandidatePublicationState;
    readonly correction: CandidateCorrectionState;
    readonly application: CandidateApplicationState;
    readonly overlayAvailable?: boolean;
}

interface CandidatePresentationSource<TState> {
    readonly state: TState;
    subscribe(listener: (state: TState) => void): () => void;
}

interface CandidatePublicationPresentationSource {
    readonly presentationState: CandidatePublicationState;
    subscribe(listener: (state: CandidatePublicationState) => void): () => void;
}

export interface CandidatePresentationCoordinatorOptions {
    readonly candidates: CandidatePublicationPresentationSource;
    readonly correction: CandidatePresentationSource<CandidateCorrectionState>;
    readonly application: CandidatePresentationSource<CandidateApplicationState>;
}

type CandidatePresentationListener = (state: CandidatePresentation) => void;

const applicationOutcome = (
    application: CandidateApplicationState
): CandidateApplicationOperation | null =>
    application.applicationRecord?.operation ?? null;

const lifecycleFor = (
    candidate: Exclude<CandidatePublicationState, { status: 'empty' }>,
    correction: CandidateCorrectionState,
    outcome: CandidateApplicationOperation | null
): CandidatePresentationLifecycle => {
    if (correction.status === 'updating') {
        return 'updating';
    }
    if (correction.status === 'failed') {
        return 'update-failed';
    }
    if (correction.mode === 'correcting') {
        return 'correcting';
    }
    if (outcome !== null && candidate.status === 'current') {
        return `applied-${outcome}`;
    }
    return candidate.status;
};

const disabledReasonFor = (
    candidate: Exclude<CandidatePublicationState, { status: 'empty' }>,
    correction: CandidateCorrectionState,
    application: CandidateApplicationState,
    overlayAvailable: boolean
): CandidateOperationDisabledReason | null => {
    if (correction.status === 'updating') {
        return 'wait-for-update';
    }
    if (correction.mode === 'correcting') {
        return 'complete-or-exit-correction';
    }
    if (candidate.status === 'stale' || correction.status === 'failed') {
        return 'update-candidate';
    }
    if (!overlayAvailable) {
        return 'restart-target';
    }
    if (application.status === 'blocked') {
        return application.blockReason === 'candidate-stale'
            ? 'update-candidate'
            : 'restart-target';
    }
    return null;
};

/**
 * The only lifecycle projection consumed by Candidate-owned UI surfaces.
 * Domain stores remain authoritative; this mapper owns no mutable state.
 */
export const mapCandidatePresentation = (
    input: CandidatePresentationInput
): CandidatePresentation => {
    const { candidate, correction, application } = input;
    const overlayAvailable = input.overlayAvailable ?? true;
    if (candidate.status === 'empty') {
        const lifecycle =
            correction.status === 'updating'
                ? 'updating'
                : correction.status === 'failed'
                  ? 'update-failed'
                  : null;
        return Object.freeze({
            inspectable: false,
            counts: Object.freeze({ selected: 0, uncertain: 0 }),
            dock: Object.freeze({
                showCandidateSummary: false,
                showFixCandidate: false,
                showUpdateCandidate: false,
                showBackToCandidate: false,
                applicationOutcome: null
            }),
            toolbar: Object.freeze({
                visible: false,
                operationsEnabled: false,
                disabledReason: null,
                technicalBlockReason: null,
                undoAndFixEnabled: false,
                undoAndFixDisabledReason: 'candidate-not-applied'
            }),
            statusBar: Object.freeze({
                visible: lifecycle !== null,
                lifecycle
            }),
            overlay: Object.freeze({
                membership: null,
                treatment: null
            })
        });
    }

    const outcome = applicationOutcome(application);
    const disabledReason = disabledReasonFor(
        candidate,
        correction,
        application,
        overlayAvailable
    );
    return Object.freeze({
        inspectable: true,
        counts: Object.freeze({
            selected: candidate.candidate.selectedStableGaussianIds.length,
            uncertain: candidate.uncertain.stableGaussianIds.length
        }),
        dock: Object.freeze({
            showCandidateSummary: true,
            showFixCandidate:
                candidate.status === 'current' &&
                correction.mode === 'candidate' &&
                correction.status === 'idle',
            showUpdateCandidate:
                candidate.status === 'stale' ||
                correction.mode === 'correcting' ||
                correction.status === 'failed',
            showBackToCandidate: correction.mode === 'correcting',
            applicationOutcome: outcome
        }),
        toolbar: Object.freeze({
            visible: true,
            operationsEnabled:
                disabledReason === null &&
                (application.status === 'ready' ||
                    application.status === 'applied' ||
                    application.status === 'applying'),
            disabledReason,
            technicalBlockReason:
                application.status === 'blocked'
                    ? application.blockReason
                    : null,
            undoAndFixEnabled: application.undoAndFixAvailable,
            undoAndFixDisabledReason: application.undoAndFixBlockReason
        }),
        statusBar: Object.freeze({
            visible: true,
            lifecycle: lifecycleFor(candidate, correction, outcome)
        }),
        overlay: Object.freeze({
            membership: candidate.overlay,
            treatment: candidate.status
        })
    });
};

/**
 * Composes the three authoritative lifecycle sources without introducing a
 * second state machine. Dock, Toolbar, Status Bar and Overlay subscribe here.
 */
export class CandidatePresentationCoordinator {
    private readonly candidates: CandidatePublicationPresentationSource;
    private readonly correction: CandidatePresentationSource<CandidateCorrectionState>;
    private readonly application: CandidatePresentationSource<CandidateApplicationState>;
    private readonly listeners = new Set<CandidatePresentationListener>();
    private overlayAvailable = true;

    constructor(options: CandidatePresentationCoordinatorOptions) {
        this.candidates = options.candidates;
        this.correction = options.correction;
        this.application = options.application;
        this.candidates.subscribe(() => this.publish());
        this.correction.subscribe(() => this.publish());
        this.application.subscribe(() => this.publish());
    }

    get state(): CandidatePresentation {
        return mapCandidatePresentation({
            candidate: this.candidates.presentationState,
            correction: this.correction.state,
            application: this.application.state,
            overlayAvailable: this.overlayAvailable
        });
    }

    setOverlayAvailable(available: boolean): void {
        if (available === this.overlayAvailable) {
            return;
        }
        this.overlayAvailable = available;
        this.publish();
    }

    subscribe(listener: CandidatePresentationListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    private publish(): void {
        if (this.listeners.size === 0) {
            return;
        }
        const state = this.state;
        this.listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                console.error(error);
            }
        });
    }
}
