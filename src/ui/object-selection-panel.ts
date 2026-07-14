import { Button, Container, Label } from '@playcanvas/pcui';

import {
    ObjectSelectionMode,
    ObjectSelectionPrompt,
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionState
} from '../object-selection-session';

interface ObjectSelectionPanelOptions {
    onError?: (error: unknown) => void;
}

class ObjectSelectionPanel extends Container {
    private session: ObjectSelectionSessionInterface;
    private options: ObjectSelectionPanelOptions;

    constructor(session: ObjectSelectionSessionInterface, options: ObjectSelectionPanelOptions = {}, args = {}) {
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
        this.append(add);
        this.append(remove);
        this.append(refine);
        this.append(update);
        this.append(cancelUpdate);
        this.append(confirm);
        this.append(cancel);
        this.append(retryCleanup);

        add.on('click', () => this.setMode('Add'));
        remove.on('click', () => this.setMode('Remove'));
        refine.on('click', () => this.setMode('Refine'));
        update.on('click', () => this.run(() => session.updatePreview()));
        cancelUpdate.on('click', () => this.run(() => session.cancelUpdate()));
        confirm.on('click', () => this.run(() => session.confirm()));
        cancel.on('click', () => this.run(() => session.cancel()));
        retryCleanup.on('click', () => this.run(() => session.retryCleanup()));

        session.subscribe((state) => {
            this.updateControls(state, {
                status,
                selectedPreview,
                uncertainPreview,
                add,
                remove,
                refine,
                update,
                cancelUpdate,
                confirm,
                cancel,
                retryCleanup
            });
        });
    }

    stagePrompt(prompt: ObjectSelectionPrompt) {
        this.session.stagePrompt(prompt);
    }

    private setMode(mode: ObjectSelectionMode) {
        try {
            this.session.setMode(mode);
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

    private updateControls(state: ObjectSelectionSessionState, controls: {
        status: Label;
        selectedPreview: Label;
        uncertainPreview: Label;
        add: Button;
        remove: Button;
        refine: Button;
        update: Button;
        cancelUpdate: Button;
        confirm: Button;
        cancel: Button;
        retryCleanup: Button;
    }) {
        const canEdit = state.status === 'ready' || state.status === 'preview';

        controls.status.text = state.lockedIdsFiltered > 0 ?
            `Object Selection: ${state.status} (${state.lockedIdsFiltered} locked IDs filtered)` :
            `Object Selection: ${state.status}`;
        controls.selectedPreview.text = this.previewLabel('Selected', state.candidate?.selectedIds);
        controls.uncertainPreview.text = this.previewLabel('Uncertain', state.candidate?.uncertainIds);
        controls.add.enabled = canEdit;
        controls.remove.enabled = canEdit;
        controls.refine.enabled = canEdit;
        controls.update.enabled = canEdit;
        controls.cancelUpdate.enabled = state.status === 'previewing';
        controls.confirm.enabled = state.status === 'preview';
        controls.cancel.enabled = canEdit || state.status === 'previewing';
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
}

export { ObjectSelectionPanel };

export type { ObjectSelectionPanelOptions };
