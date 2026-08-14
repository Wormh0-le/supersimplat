import type {
    CandidateApplicationOperation,
    CandidateNativeHistoryCommand,
    CandidateNativeSelection
} from './ai-select/candidate-application';
import type { EditHistory } from './edit-history';
import { SelectOp } from './edit-ops';
import type { Splat } from './splat';
import type { SplatSceneSnapshotBinding } from './splat-scene-snapshot';

interface CandidateApplicationEditorTarget {
    readonly targetSplat: Splat;
    readonly stableIds: SplatSceneSnapshotBinding;
}

/**
 * A SelectOp whose failed GPU/state flush restores the exact pre-command
 * selection bits before propagating the failure to EditHistory.
 */
class RecoverableCandidateSelectOp extends SelectOp {
    async do(): Promise<void> {
        try {
            await super.do();
        } catch (error) {
            try {
                await super.undo();
            } catch (restoreError) {
                throw new AggregateError(
                    [error, restoreError],
                    'AI Select Candidate application and selection restoration both failed.'
                );
            }
            throw error;
        }
    }
}

/** Native editor adapter: Stable IDs resolve here and one SelectOp is queued. */
export class SelectOpCandidateNativeSelection implements CandidateNativeSelection {
    constructor(
        private readonly options: {
            readonly editHistory: EditHistory;
            readonly getTarget: () => CandidateApplicationEditorTarget | null;
        }
    ) {}

    apply(
        operation: CandidateApplicationOperation,
        selectedStableGaussianIds: readonly number[],
        validateCurrent: () => void
    ): Promise<CandidateNativeHistoryCommand> {
        return this.options.editHistory.addFromFactory(() => {
            validateCurrent();
            const target = this.options.getTarget();
            if (target === null) {
                throw new Error(
                    'AI Select Candidate no longer has a native Target Splat.'
                );
            }
            const splatIndices = target.stableIds
                .toSplatIndices(selectedStableGaussianIds)
                .slice();
            splatIndices.sort();
            return new RecoverableCandidateSelectOp(
                target.targetSplat,
                operation,
                splatIndices
            );
        });
    }
}
