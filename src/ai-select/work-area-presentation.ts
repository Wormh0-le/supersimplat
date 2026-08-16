import type { LiftReadinessState } from './lift-readiness';

export type ReLiftUnavailableReason =
    | 'missing-target'
    | 'service-unavailable'
    | 'no-usable-included-stable-input'
    | 'unconfirmed-included-mask'
    | 'readiness-missing'
    | 'readiness-stale'
    | 'readiness-not-ready'
    | 'readiness-limited'
    | 'candidate-updating';

export type PaletteConfirmationAction =
    'none' | 'confirm-mask' | 'confirm-review' | 'confirm-anchor';
export type PaletteContextAction =
    'none' | 'enter-correction' | 'back-to-candidate';

export interface WorkAreaActionInput {
    readonly targetActive: boolean;
    readonly serviceAvailable: boolean;
    readonly hasUsableIncludedStableInput: boolean;
    readonly hasUnconfirmedIncludedMask: boolean;
    readonly candidateStatus: 'empty' | 'current' | 'stale';
    readonly correctionMode: 'candidate' | 'correcting';
    readonly correctionStatus: 'idle' | 'updating' | 'failed';
    readonly liftReadiness: LiftReadinessState;
    readonly canConfirmMask: boolean;
    readonly canConfirmReview: boolean;
    readonly anchorNeedsConfirmation: boolean;
}

export interface WorkAreaActionPresentation {
    readonly reLift: Readonly<{
        visible: boolean;
        enabled: boolean;
        emphasis: 'normal' | 'warning';
        state: 'idle' | 'updating';
        reason: ReLiftUnavailableReason | null;
    }>;
    readonly palette: Readonly<{
        confirmation: PaletteConfirmationAction;
        context: PaletteContextAction;
    }>;
}

const confirmationAction = (
    input: WorkAreaActionInput
): PaletteConfirmationAction => {
    if (input.canConfirmMask) {
        return 'confirm-mask';
    }
    if (input.canConfirmReview) {
        return 'confirm-review';
    }
    return input.anchorNeedsConfirmation ? 'confirm-anchor' : 'none';
};

const contextAction = (input: WorkAreaActionInput): PaletteContextAction => {
    if (input.candidateStatus !== 'current') {
        return 'none';
    }
    return input.correctionMode === 'correcting'
        ? 'back-to-candidate'
        : 'enter-correction';
};

const unavailableReason = (
    input: WorkAreaActionInput
): ReLiftUnavailableReason | null => {
    if (!input.targetActive) {
        return 'missing-target';
    }
    if (!input.serviceAvailable) {
        return 'service-unavailable';
    }
    if (!input.hasUsableIncludedStableInput) {
        return 'no-usable-included-stable-input';
    }
    if (input.hasUnconfirmedIncludedMask) {
        return 'unconfirmed-included-mask';
    }
    if (input.correctionStatus === 'updating') {
        return 'candidate-updating';
    }
    if (input.liftReadiness.status === 'empty') {
        return 'readiness-missing';
    }
    if (input.liftReadiness.status === 'stale') {
        return 'readiness-stale';
    }
    if (input.liftReadiness.readiness === 'not-ready') {
        return 'readiness-not-ready';
    }
    return input.liftReadiness.readiness === 'limited'
        ? 'readiness-limited'
        : null;
};

/**
 * Maps authoritative Candidate, Mask and Lift Readiness state onto the two
 * Work Area action slots. It deliberately does not evaluate readiness or
 * publish any artifact; the Dock only consumes the current exact-bound view.
 */
export const mapWorkAreaActions = (
    input: WorkAreaActionInput
): WorkAreaActionPresentation => {
    const hiddenCurrentCandidate =
        input.candidateStatus === 'current' &&
        input.correctionStatus !== 'updating' &&
        input.correctionStatus !== 'failed';
    const reason = unavailableReason(input);
    const updating = input.correctionStatus === 'updating';
    const enabled =
        !hiddenCurrentCandidate &&
        !updating &&
        (reason === null || reason === 'readiness-limited');
    return Object.freeze({
        reLift: Object.freeze({
            visible: !hiddenCurrentCandidate,
            enabled,
            emphasis:
                enabled && reason === 'readiness-limited'
                    ? 'warning'
                    : 'normal',
            state: updating ? 'updating' : 'idle',
            reason
        }),
        palette: Object.freeze({
            confirmation: confirmationAction(input),
            context: contextAction(input)
        })
    });
};
