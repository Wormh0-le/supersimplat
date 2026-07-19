import { Button, Container, Label } from '@playcanvas/pcui';

import type {
    ObjectSelectionMode,
    ObjectSelectionPrompt,
    ObjectSelectionPromptPolarity,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionState
} from '../object-selection-session';
import { i18n } from './localization';

interface ObjectSelectionPanelOptions {
  onError?: (error: unknown) => void;
}

interface ObjectSelectionPanelControls {
  status: Label;
  selectedPreview: Label;
  uncertainPreview: Label;
  coverage: Label;
  correctionRounds: Label;
  pendingPrompts: Label;
  refinePolarity: Label;
  acknowledgement: Label;
  add: Button;
  remove: Button;
  refine: Button;
  refineInclude: Button;
  refineExclude: Button;
  undoPrompt: Button;
  clearPrompts: Button;
  update: Button;
  cancelUpdate: Button;
  confirm: Button;
  cancel: Button;
  retryCleanup: Button;
}

class ObjectSelectionPanel extends Container {
    private session: ObjectSelectionSessionInterface;
    private options: ObjectSelectionPanelOptions;
    private controls: ObjectSelectionPanelControls;
    // Set by the first Confirm click while Uncertain Gaussians remain. Any
    // session state change requires a fresh acknowledgement.
    private acknowledgementPending = false;
    private refinePolarity: ObjectSelectionPromptPolarity = 'include';
    // Point validation crosses queued canvas capture and hit-test work. Keep
    // session actions disabled until that transient staging operation settles.
    private promptStaging = false;

    constructor(
        session: ObjectSelectionSessionInterface,
        options: ObjectSelectionPanelOptions = {},
        args = {}
    ) {
        args = {
            ...args,
            id: 'object-selection-panel'
        };

        super(args);

        this.session = session;
        this.options = options;

        this.dom.addEventListener('pointerdown', (event) => {
            event.stopPropagation();
        });

        const status = new Label({
            id: 'object-selection-panel-status'
        });
        const selectedPreview = new Label({
            id: 'object-selection-panel-selected-preview'
        });
        const uncertainPreview = new Label({
            id: 'object-selection-panel-uncertain-preview'
        });
        const coverage = new Label({
            id: 'object-selection-panel-coverage'
        });
        const correctionRounds = new Label({
            id: 'object-selection-panel-correction-rounds'
        });
        const pendingPrompts = new Label({
            id: 'object-selection-panel-pending-prompts'
        });
        const refinePolarity = new Label({
            id: 'object-selection-panel-refine-polarity'
        });
        const acknowledgement = new Label({
            id: 'object-selection-panel-acknowledgement'
        });
        const add = new Button({
            id: 'object-selection-panel-add',
            text: 'Add'
        });
        const remove = new Button({
            id: 'object-selection-panel-remove',
            text: 'Remove'
        });
        const refine = new Button({
            id: 'object-selection-panel-refine',
            text: 'Refine'
        });
        const refineInclude = new Button({
            id: 'object-selection-panel-refine-include'
        });
        const refineExclude = new Button({
            id: 'object-selection-panel-refine-exclude'
        });
        const undoPrompt = new Button({
            id: 'object-selection-panel-undo-prompt'
        });
        const clearPrompts = new Button({
            id: 'object-selection-panel-clear-prompts'
        });
        const update = new Button({
            id: 'object-selection-panel-update',
            text: 'Update Preview'
        });
        const cancelUpdate = new Button({
            id: 'object-selection-panel-cancel-update',
            text: 'Cancel Update'
        });
        const confirm = new Button({
            id: 'object-selection-panel-confirm',
            text: 'Confirm'
        });
        const cancel = new Button({
            id: 'object-selection-panel-cancel',
            text: 'Cancel'
        });
        const retryCleanup = new Button({
            id: 'object-selection-panel-retry-cleanup',
            text: 'Retry Cleanup'
        });

        this.append(status);
        this.append(selectedPreview);
        this.append(uncertainPreview);
        this.append(coverage);
        this.append(correctionRounds);
        this.append(pendingPrompts);
        this.append(acknowledgement);
        this.append(add);
        this.append(remove);
        this.append(refine);
        this.append(refinePolarity);
        this.append(refineInclude);
        this.append(refineExclude);
        this.append(undoPrompt);
        this.append(clearPrompts);
        this.append(update);
        this.append(cancelUpdate);
        this.append(confirm);
        this.append(cancel);
        this.append(retryCleanup);

        this.controls = {
            status,
            selectedPreview,
            uncertainPreview,
            coverage,
            correctionRounds,
            pendingPrompts,
            refinePolarity,
            acknowledgement,
            add,
            remove,
            refine,
            refineInclude,
            refineExclude,
            undoPrompt,
            clearPrompts,
            update,
            cancelUpdate,
            confirm,
            cancel,
            retryCleanup
        };

        i18n.bindText(refinePolarity, 'object-selection.refine-prompt');
        i18n.bindText(undoPrompt, 'object-selection.undo-last');
        i18n.bindText(clearPrompts, 'object-selection.clear-prompts');

        add.on('click', () => this.setMode('Add'));
        remove.on('click', () => this.setMode('Remove'));
        refine.on('click', () => this.setMode('Refine'));
        refineInclude.on('click', () => this.setRefinePolarity('include'));
        refineExclude.on('click', () => this.setRefinePolarity('exclude'));
        undoPrompt.on('click', () => this.undoLastPendingPrompt());
        clearPrompts.on('click', () => this.clearPendingPrompts());
        update.on('click', () => this.run(() => session.updatePreview()));
        cancelUpdate.on('click', () => this.run(() => session.cancelUpdate()));
        confirm.on('click', () => this.confirmSelection());
        cancel.on('click', () => this.run(() => session.cancel()));
        retryCleanup.on('click', () => this.run(() => session.retryCleanup()));

        session.subscribe((state) => {
            this.acknowledgementPending = false;
            this.updateControls(state);
        });
        i18n.onChange(() => this.updateControls(this.session.state), this);
    }

    stagePrompt(prompt: ObjectSelectionPrompt) {
        const polarity = this.promptPolarity(this.session.state.mode);
        this.session.stagePrompt({
            ...prompt,
            polarity
        });
    }

    setPromptStaging(staging: boolean) {
        if (this.promptStaging === staging) {
            return;
        }
        this.promptStaging = staging;
        this.updateControls(this.session.state);
    }

    private confirmSelection() {
        const state = this.session.state;
        const uncertainCount = state.candidate?.uncertainIds.length ?? 0;
        if (uncertainCount > 0 && !this.acknowledgementPending) {
            this.acknowledgementPending = true;
            this.updateControls(state);
            return;
        }
        this.acknowledgementPending = false;
        this.run(() => this.session.confirm({ acknowledgeUncertain: uncertainCount > 0 })
        );
    }

    private setMode(mode: ObjectSelectionMode) {
        try {
            this.session.setMode(mode);
        } catch (error) {
            this.reportError(error);
        }
    }

    private setRefinePolarity(polarity: ObjectSelectionPromptPolarity) {
        this.refinePolarity = polarity;
        this.updateControls(this.session.state);
    }

    private undoLastPendingPrompt() {
        try {
            this.session.undoLastPendingPrompt();
        } catch (error) {
            this.reportError(error);
        }
    }

    private clearPendingPrompts() {
        try {
            this.session.clearPendingPrompts();
        } catch (error) {
            this.reportError(error);
        }
    }

    private run(action: () => Promise<void>) {
        action().catch(error => this.reportError(error));
    }

    private reportError(error: unknown) {
        if (this.options.onError) {
            this.options.onError(error);
        } else {
            console.error(error);
        }
    }

    private updateControls(state: ObjectSelectionSessionState) {
        const controls = this.controls;
        const canUpdate = state.status === 'ready' || state.status === 'preview';
        const canCorrect = state.status === 'preview' && state.candidate !== null;
        const canAct = !this.promptStaging;
        const budgetExhausted =
      state.correctionRoundsUsed >= state.correctionRoundsLimit;
        const uncertainCount = state.candidate?.uncertainIds.length ?? 0;
        const pendingPromptCount = state.pendingPrompts.length;
        const refineMode = state.mode === 'Refine';
        const acknowledging =
      this.acknowledgementPending &&
      state.status === 'preview' &&
      uncertainCount > 0;

        controls.status.text =
      state.lockedIdsFiltered > 0 ?
          `Object Selection: ${state.status} (${state.lockedIdsFiltered} locked IDs filtered)` :
          `Object Selection: ${state.status}`;
        controls.selectedPreview.text = this.previewLabel(
            'Selected',
            state.candidate?.selectedIds
        );
        controls.uncertainPreview.text = this.previewLabel(
            'Uncertain',
            state.candidate?.uncertainIds
        );
        controls.coverage.text = this.coverageLabel(state);
        controls.pendingPrompts.text =
      `${i18n.t('object-selection.pending-prompts')}: ${pendingPromptCount}`;
        controls.correctionRounds.text =
      canUpdate && budgetExhausted ?
          `Correction rounds: ${state.correctionRoundsUsed} / ${state.correctionRoundsLimit} — No more preview updates are available for this session.` :
          `Correction rounds: ${state.correctionRoundsUsed} / ${state.correctionRoundsLimit}`;
        controls.acknowledgement.text = acknowledging ?
            `${uncertainCount} uncertain Gaussians will NOT be selected. The committed selection may be incomplete.` :
            '';
        controls.confirm.text = acknowledging ? 'Confirm Selected Only' : 'Confirm';
        controls.add.enabled = canCorrect && canAct;
        controls.remove.enabled = canCorrect && canAct;
        controls.refine.enabled = canCorrect && canAct;
        controls.refinePolarity.hidden = !refineMode;
        controls.refineInclude.hidden = !refineMode;
        controls.refineExclude.hidden = !refineMode;
        controls.refineInclude.enabled = canCorrect && refineMode && canAct;
        controls.refineExclude.enabled = canCorrect && refineMode && canAct;
        controls.refineInclude.text = this.refinePolarity === 'include' ?
            `${i18n.t('object-selection.include')} ✓` :
            i18n.t('object-selection.include');
        controls.refineExclude.text = this.refinePolarity === 'exclude' ?
            `${i18n.t('object-selection.exclude')} ✓` :
            i18n.t('object-selection.exclude');
        controls.undoPrompt.enabled = canCorrect && pendingPromptCount > 0 && canAct;
        controls.clearPrompts.enabled = canCorrect && pendingPromptCount > 0 && canAct;
        controls.update.enabled = canUpdate && !budgetExhausted && canAct;
        controls.cancelUpdate.enabled = state.status === 'previewing';
        controls.confirm.enabled =
            state.status === 'preview' && pendingPromptCount === 0 && canAct;
        controls.cancel.enabled =
            (canUpdate || state.status === 'previewing') && canAct;
        controls.retryCleanup.enabled = state.status === 'closeFailed';
    }

    private previewLabel(name: string, ids: readonly number[] | undefined) {
        if (!ids) {
            return `${name}: no preview`;
        }
        const visibleIds = ids.slice(0, 8).join(', ');
        const suffix = ids.length > 8 ? ', …' : '';
        return `${name}: ${ids.length} [${visibleIds}${suffix}]`;
    }

    private coverageLabel(state: ObjectSelectionSessionState) {
        if (!state.coverage) {
            return 'Coverage: no preview';
        }
        if (state.coverage.status === 'insufficient_coverage') {
            return 'Coverage is limited. Some Gaussians could not be observed reliably and remain uncertain. Try rotating to another visible side and use Refine.';
        }
        return `Coverage: sufficient across ${state.coverage.acceptedViews} accepted views.`;
    }

    private promptPolarity(mode: ObjectSelectionMode): ObjectSelectionPromptPolarity {
        if (mode === 'Remove') {
            return 'exclude';
        }
        return mode === 'Refine' ? this.refinePolarity : 'include';
    }
}

export { ObjectSelectionPanel };

export type { ObjectSelectionPanelOptions };
