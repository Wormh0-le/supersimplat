export type AISelectRestartConfirmation =
    'none' | 'discard-unconfirmed' | 'discard-confirmed-context';

export interface AISelectTargetLifecycleSnapshot {
    readonly hasContext: boolean;
    readonly hasUnconfirmedChanges: boolean;
    readonly hasConfirmedTargetState: boolean;
    readonly candidateApplied: boolean;
}

export const restartConfirmationFor = (
    snapshot: AISelectTargetLifecycleSnapshot
): AISelectRestartConfirmation => {
    if (!snapshot.hasContext) {
        return 'none';
    }
    if (snapshot.hasUnconfirmedChanges) {
        return 'discard-unconfirmed';
    }
    if (snapshot.candidateApplied) {
        return 'none';
    }
    return snapshot.hasConfirmedTargetState
        ? 'discard-confirmed-context'
        : 'none';
};

export interface AISelectTargetLifecycleControllerOptions {
    readonly getSnapshot: () => AISelectTargetLifecycleSnapshot;
    readonly confirmRestart: (
        reason: Exclude<AISelectRestartConfirmation, 'none'>
    ) => Promise<boolean>;
    readonly restartCurrentTarget: () => Promise<void>;
}

/** Owns confirmation and serialization for the global target lifecycle menu. */
export class AISelectTargetLifecycleController {
    private restarting = false;

    constructor(
        private readonly options: AISelectTargetLifecycleControllerOptions
    ) {}

    async chooseAnotherObject(): Promise<boolean> {
        if (this.restarting || !this.options.getSnapshot().hasContext) {
            return false;
        }
        this.restarting = true;
        try {
            const confirmation = restartConfirmationFor(
                this.options.getSnapshot()
            );
            if (
                confirmation !== 'none' &&
                !(await this.options.confirmRestart(confirmation))
            ) {
                return false;
            }
            await this.options.restartCurrentTarget();
            return true;
        } finally {
            this.restarting = false;
        }
    }
}
