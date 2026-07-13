import { EditHistory } from './edit-history';
import { SelectOp } from './edit-ops';
import { IndexRanges } from './index-ranges';
import { ObjectSelectionSessionEditor, StableGaussianId } from './object-selection-session';
import { Splat } from './splat';
import { State } from './splat-state';

interface StableGaussianIdMap {
    toStableGaussianIds(indices: readonly number[]): readonly StableGaussianId[];
    toSplatIndices(stableIds: readonly StableGaussianId[]): Uint32Array;
}

// Bridges ObjectSelectionSession to existing editor selection behavior. Stable
// ID resolution remains editor-owned, while SelectOp remains the sole commit.
class SelectOpObjectSelectionSessionEditor implements ObjectSelectionSessionEditor {
    private splat: Splat;
    private editHistory: EditHistory;
    private stableIds: StableGaussianIdMap;

    constructor(options: {
        splat: Splat;
        editHistory: EditHistory;
        stableIds: StableGaussianIdMap;
    }) {
        this.splat = options.splat;
        this.editHistory = options.editHistory;
        this.stableIds = options.stableIds;
    }

    captureSelection() {
        const { data } = this.splat.state;
        const selectedIndices: number[] = [];

        for (let i = 0; i < data.length; ++i) {
            if ((data[i] & State.selected) !== 0) {
                selectedIndices.push(i);
            }
        }

        return this.stableIds.toStableGaussianIds(selectedIndices);
    }

    async commitSelection(selectedIds: readonly StableGaussianId[]) {
        const splatIndices = this.stableIds.toSplatIndices(selectedIds).slice();
        splatIndices.sort();
        await this.editHistory.add(new SelectOp(this.splat, 'set', splatIndices));
    }

    async restoreSelection(entrySelection: readonly StableGaussianId[]) {
        const entryIndices = new Set(this.stableIds.toSplatIndices(entrySelection));
        const { data } = this.splat.state;
        const mutable = (index: number) => (data[index] & (State.locked | State.deleted)) === 0;
        const toSelect = IndexRanges.fromPredicate(data.length, (index) => {
            return mutable(index) && entryIndices.has(index) && (data[index] & State.selected) === 0;
        });
        const toClear = IndexRanges.fromPredicate(data.length, (index) => {
            return mutable(index) && !entryIndices.has(index) && (data[index] & State.selected) !== 0;
        });

        if (toSelect.empty && toClear.empty) {
            return;
        }

        this.splat.state.setBits(toSelect, State.selected);
        this.splat.state.clearBits(toClear, State.selected);
        await this.splat.updateState(State.selected);
    }
}

export { SelectOpObjectSelectionSessionEditor };

export type { StableGaussianIdMap };
