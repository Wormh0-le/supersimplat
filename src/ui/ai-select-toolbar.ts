import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import type { AISelectAnchorConfirmationController } from '../ai-select/anchor-confirmation';
import type { AISelectAnchorController } from '../ai-select/anchor-controller';
import {
    getAnchorDockPresentation,
    type AnchorDockStatus
} from '../ai-select/anchor-dock-presentation';
import {
    isAnchorInspectionTarget,
    isUserViewDraftInspectionTarget,
    type CameraInspectionController
} from '../ai-select/camera-inspection';
import type {
    CandidateApplicationController,
    CandidateApplicationOperation
} from '../ai-select/candidate-application';
import type { CandidateOverlayController } from '../ai-select/candidate-overlay';
import type {
    CandidateOperationDisabledReason,
    CandidatePresentation,
    CandidatePresentationCoordinator
} from '../ai-select/candidate-presentation';
export interface AISelectToolbarOptions {
    readonly candidatePresentation: CandidatePresentationCoordinator;
    readonly candidateOverlay: CandidateOverlayController;
    readonly candidateApplication: CandidateApplicationController;
    readonly onCandidateApplicationFailure: (error: unknown) => void;
    readonly onRestart: () => Promise<void>;
    readonly onExit: () => void;
    readonly onEnterInspection: () => void;
    readonly onReturnToSceneView: () => void;
    readonly onResetAnchor: () => Promise<void>;
    readonly onRetryPreview: () => Promise<void>;
    readonly onAddCurrentView: () => void;
    readonly onAdjustNewView: () => void;
    readonly onConfirmDraftView: () => void;
}

const statusTextKeys: Record<AnchorDockStatus, string> = {
    idle: 'ai-select.panel.idle',
    ready: 'ai-select.anchor.ready',
    previewing: 'ai-select.anchor.previewing',
    rendering: 'ai-select.anchor.rendering',
    failed: 'ai-select.anchor.failed'
};

const disabledReasonKeys: Record<CandidateOperationDisabledReason, string> = {
    'wait-for-update': 'ai-select.candidate.disabled.wait-for-update',
    'complete-or-exit-correction':
        'ai-select.candidate.disabled.complete-or-exit-correction',
    'update-candidate': 'ai-select.candidate.disabled.update-candidate',
    'restart-target': 'ai-select.candidate.disabled.restart-target'
};

/** Fixed, single-row main-viewport subtoolbar for the active AI context. */
export class AISelectToolbar extends Container {
    constructor(
        controller: AISelectAnchorController,
        inspection: CameraInspectionController,
        confirmation: AISelectAnchorConfirmationController,
        options: AISelectToolbarOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-toolbar',
            hidden: true
        });
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );

        const tool = new Label({ id: 'ai-select-toolbar-tool' });
        const anchor = new Label({ id: 'ai-select-toolbar-anchor' });
        const adjust = new Button({
            id: 'ai-select-toolbar-adjust-anchor',
            enabled: false
        });
        const move = new Button({
            id: 'ai-select-toolbar-move-anchor',
            hidden: true
        });
        const rotate = new Button({
            id: 'ai-select-toolbar-rotate-anchor',
            hidden: true
        });
        const returnToSceneView = new Button({
            id: 'ai-select-toolbar-return-to-scene-view',
            hidden: true
        });
        const resetAnchor = new Button({
            id: 'ai-select-toolbar-reset-anchor',
            hidden: true
        });
        const confirmDraftView = new Button({
            id: 'ai-select-toolbar-confirm-view',
            hidden: true
        });
        const status = new Label({
            id: 'ai-select-toolbar-status',
            hidden: true
        });
        const retry = new Button({
            id: 'ai-select-toolbar-retry-preview',
            hidden: true
        });
        const addCurrentView = new Button({
            id: 'ai-select-toolbar-add-current-view',
            hidden: true
        });

        const candidateGroup = new Container({
            id: 'ai-select-candidate-operation-group',
            hidden: true
        });
        candidateGroup.dom.setAttribute('role', 'group');
        const operationReason = new Label({
            id: 'ai-select-candidate-operation-reason'
        });
        operationReason.dom.setAttribute('role', 'status');
        const overlayToggle = new Button({
            id: 'ai-select-candidate-overlay-toggle'
        });
        const overlayMenuTrigger = new Button({
            id: 'ai-select-candidate-overlay-menu-trigger',
            text: '▾'
        });
        const overlayMenu = new Container({
            id: 'ai-select-candidate-overlay-menu',
            hidden: true
        });
        overlayMenu.dom.setAttribute('role', 'menu');
        const uncertainToggle = new Button({
            id: 'ai-select-candidate-uncertain-toggle'
        });
        uncertainToggle.dom.setAttribute('role', 'menuitemcheckbox');
        const selectedLegend = new Label({
            class: ['ai-select-candidate-legend', 'candidate-selected']
        });
        const uncertainLegend = new Label({
            class: ['ai-select-candidate-legend', 'candidate-uncertain']
        });
        overlayMenu.append(uncertainToggle);
        overlayMenu.append(selectedLegend);
        overlayMenu.append(uncertainLegend);

        const candidateOperations: readonly CandidateApplicationOperation[] = [
            'set',
            'add',
            'remove',
            'intersect'
        ];
        const operationIcons: Record<CandidateApplicationOperation, string> = {
            set: '◆',
            add: '＋',
            remove: '−',
            intersect: '∩'
        };
        const operationButtons = new Map<
            CandidateApplicationOperation,
            Button
        >();
        const applicationFailure = new Label({
            id: 'ai-select-candidate-application-failure',
            hidden: true
        });
        applicationFailure.dom.setAttribute('role', 'status');
        applicationFailure.dom.setAttribute('aria-live', 'assertive');
        let failureTimer: number | null = null;
        const reportApplicationFailure = (error: unknown): void => {
            options.onCandidateApplicationFailure(error);
            applicationFailure.text = i18n.t(
                'ai-select.candidate.selection-unchanged'
            );
            applicationFailure.hidden = false;
            if (failureTimer !== null) {
                window.clearTimeout(failureTimer);
            }
            failureTimer = window.setTimeout(() => {
                applicationFailure.hidden = true;
                failureTimer = null;
            }, 4000);
        };
        candidateGroup.append(overlayToggle);
        candidateGroup.append(overlayMenuTrigger);
        candidateGroup.append(overlayMenu);
        for (const operation of candidateOperations) {
            const button = new Button({
                id: `ai-select-toolbar-candidate-${operation}`
            });
            button.dom.dataset.icon = operationIcons[operation];
            button.on('click', () => {
                options.candidateApplication
                    .apply(operation)
                    .catch((error) => reportApplicationFailure(error));
            });
            operationButtons.set(operation, button);
            candidateGroup.append(button);
        }
        candidateGroup.append(operationReason);

        const more = new Button({
            id: 'ai-select-toolbar-more',
            text: '⋯'
        });
        more.dom.setAttribute('aria-expanded', 'false');
        const overflow = new Container({
            id: 'ai-select-toolbar-overflow',
            hidden: true
        });
        overflow.dom.setAttribute('role', 'menu');
        const adjustNewView = new Button({
            id: 'ai-select-toolbar-adjust-new-view',
            hidden: true
        });
        const restart = new Button({ id: 'ai-select-toolbar-restart' });
        const exit = new Button({ id: 'ai-select-toolbar-exit' });
        adjustNewView.dom.setAttribute('role', 'menuitem');
        restart.dom.setAttribute('role', 'menuitem');
        exit.dom.setAttribute('role', 'menuitem');

        const closeOverlayMenu = (restoreFocus: boolean): void => {
            if (overlayMenu.hidden) {
                return;
            }
            overlayMenu.hidden = true;
            overlayMenuTrigger.dom.setAttribute('aria-expanded', 'false');
            if (restoreFocus) {
                overlayMenuTrigger.dom.focus();
            }
        };
        const closeOverflow = (restoreFocus: boolean): void => {
            if (overflow.hidden) {
                return;
            }
            overflow.hidden = true;
            more.dom.setAttribute('aria-expanded', 'false');
            if (restoreFocus) {
                more.dom.focus();
            }
        };

        adjust.on('click', () => options.onEnterInspection());
        move.on('click', () => inspection.setManipulation('move'));
        rotate.on('click', () => inspection.setManipulation('rotate'));
        returnToSceneView.on('click', () => options.onReturnToSceneView());
        resetAnchor.on('click', () => {
            options
                .onResetAnchor()
                .catch((error: unknown): void => console.error(error));
        });
        confirmDraftView.on('click', () => options.onConfirmDraftView());
        retry.on('click', () => {
            options
                .onRetryPreview()
                .catch((error: unknown): void => console.error(error));
        });
        addCurrentView.on('click', () => options.onAddCurrentView());
        overlayToggle.on('click', () =>
            options.candidateOverlay.toggleSelected()
        );
        overlayMenuTrigger.on('click', () => {
            overlayMenu.hidden = !overlayMenu.hidden;
            overlayMenuTrigger.dom.setAttribute(
                'aria-expanded',
                (!overlayMenu.hidden).toString()
            );
            closeOverflow(false);
        });
        uncertainToggle.on('click', () => {
            options.candidateOverlay.setUncertainVisible(
                !options.candidateOverlay.state.uncertainVisible
            );
        });
        adjustNewView.on('click', () => {
            closeOverflow(false);
            options.onAdjustNewView();
        });
        restart.on('click', () => {
            closeOverflow(false);
            options
                .onRestart()
                .catch((error: unknown): void => console.error(error));
        });
        exit.on('click', () => options.onExit());
        more.on('click', () => {
            overflow.hidden = !overflow.hidden;
            more.dom.setAttribute(
                'aria-expanded',
                (!overflow.hidden).toString()
            );
            closeOverlayMenu(false);
        });
        document.addEventListener('pointerdown', (event) => {
            if (!candidateGroup.dom.contains(event.target as Node)) {
                closeOverlayMenu(false);
            }
            if (!this.dom.contains(event.target as Node)) {
                closeOverflow(false);
            }
        });
        window.addEventListener(
            'keydown',
            (event) => {
                if (event.key === 'Escape') {
                    const overlayWasOpen = !overlayMenu.hidden;
                    const overflowWasOpen = !overflow.hidden;
                    closeOverlayMenu(overlayWasOpen);
                    closeOverflow(!overlayWasOpen && overflowWasOpen);
                    if (overlayWasOpen || overflowWasOpen) {
                        event.preventDefault();
                        event.stopPropagation();
                    }
                }
            },
            true
        );

        this.append(tool);
        this.append(anchor);
        this.append(adjust);
        this.append(move);
        this.append(rotate);
        this.append(returnToSceneView);
        this.append(resetAnchor);
        this.append(confirmDraftView);
        this.append(status);
        this.append(retry);
        this.append(addCurrentView);
        this.append(candidateGroup);
        this.append(applicationFailure);
        this.append(more);
        overflow.append(adjustNewView);
        overflow.append(restart);
        overflow.append(exit);
        this.append(overflow);

        let anchorState = controller.state;
        let inspectionState = inspection.state;
        let confirmationState = confirmation.state;
        let candidatePresentation: CandidatePresentation =
            options.candidatePresentation.state;
        let overlayState = options.candidateOverlay.state;

        const render = () => {
            const hasContext = anchorState.context !== null;
            const hasAnchor = anchorState.anchor !== null;
            const contextIsActive = anchorState.context?.lifecycle === 'active';
            const inspecting = inspectionState.mode === 'active';
            // Camera and draft inspection own the Toolbar while active. A
            // Candidate remains inspectable in the viewport, but never
            // displaces the higher-priority manipulation controls.
            const candidateContext =
                candidatePresentation.toolbar.visible && !inspecting;
            const canAddUserView =
                contextIsActive &&
                hasAnchor &&
                confirmationState.confirmedAnchor !== null &&
                !inspecting;
            const inspectingAnchor = isAnchorInspectionTarget(inspectionState);
            const inspectingDraft =
                isUserViewDraftInspectionTarget(inspectionState);
            const presentation = getAnchorDockPresentation(anchorState);
            this.hidden = !hasContext;

            tool.text = i18n.t(
                inspectingDraft
                    ? 'ai-select.user-view.adjusting'
                    : inspecting
                      ? 'ai-select.camera-inspection'
                      : 'ai-select.tool'
            );
            anchor.text = i18n.t('ai-select.anchor.current-view');
            adjust.text = i18n.t('ai-select.adjust-anchor');
            move.text = i18n.t('ai-select.move');
            rotate.text = i18n.t('ai-select.rotate');
            returnToSceneView.text = i18n.t('ai-select.return-to-scene-view');
            resetAnchor.text = i18n.t('ai-select.reset-anchor');
            confirmDraftView.text = i18n.t('ai-select.user-view.confirm');
            status.text = i18n.t(statusTextKeys[presentation.status]);
            retry.text = i18n.t('ai-select.retry');
            addCurrentView.text = i18n.t('ai-select.views.use-current');
            adjustNewView.text = i18n.t('ai-select.views.adjust-new');
            restart.text = i18n.t('ai-select.restart-current-target');
            exit.text = i18n.t('ai-select.exit');
            more.dom.setAttribute('aria-label', i18n.t('ai-select.more'));
            more.dom.setAttribute('aria-haspopup', 'menu');

            tool.hidden = candidateContext;
            anchor.hidden = inspecting || candidateContext;
            adjust.hidden = inspecting || candidateContext;
            move.hidden =
                candidateContext || (!inspectingAnchor && !inspectingDraft);
            rotate.hidden =
                candidateContext || (!inspectingAnchor && !inspectingDraft);
            returnToSceneView.hidden = candidateContext || !inspecting;
            resetAnchor.hidden = candidateContext || !inspectingAnchor;
            confirmDraftView.hidden = candidateContext || !inspectingDraft;
            status.hidden = candidateContext || !inspecting;
            retry.hidden =
                candidateContext ||
                !inspectingAnchor ||
                presentation.status !== 'failed';
            addCurrentView.hidden = candidateContext || !canAddUserView;
            candidateGroup.hidden = !candidateContext;

            adjust.enabled = hasAnchor && hasContext && !inspecting;
            move.enabled =
                (inspectingAnchor && hasAnchor && contextIsActive) ||
                inspectingDraft;
            rotate.enabled = move.enabled;
            returnToSceneView.enabled = inspecting;
            resetAnchor.enabled =
                inspectingAnchor && hasAnchor && contextIsActive;
            retry.enabled = contextIsActive;
            addCurrentView.enabled = canAddUserView;
            adjustNewView.hidden = !canAddUserView;
            adjustNewView.enabled = canAddUserView;
            restart.enabled = hasContext;

            overlayToggle.text = i18n.t('ai-select.candidate.overlay');
            overlayToggle.dom.setAttribute(
                'aria-pressed',
                overlayState.selectedVisible.toString()
            );
            overlayToggle.dom.classList.toggle(
                'active',
                overlayState.selectedVisible
            );
            overlayMenuTrigger.dom.setAttribute(
                'aria-label',
                i18n.t('ai-select.candidate.overlay-options')
            );
            overlayMenuTrigger.dom.setAttribute('aria-haspopup', 'menu');
            overlayMenuTrigger.dom.setAttribute(
                'aria-expanded',
                (!overlayMenu.hidden).toString()
            );
            uncertainToggle.text = i18n.t(
                'ai-select.candidate.uncertain-layer'
            );
            uncertainToggle.dom.setAttribute(
                'aria-checked',
                overlayState.uncertainVisible.toString()
            );
            uncertainToggle.dom.classList.toggle(
                'active',
                overlayState.uncertainVisible
            );
            selectedLegend.text = `${i18n.t('ai-select.candidate.selected')} ${i18n.formatInteger(candidatePresentation.counts.selected)}`;
            uncertainLegend.text = `${i18n.t('ai-select.candidate.uncertain')} ${i18n.formatInteger(candidatePresentation.counts.uncertain)}`;

            const disabledReason = candidatePresentation.toolbar.disabledReason;
            const disabledText =
                disabledReason === null
                    ? ''
                    : i18n.t(disabledReasonKeys[disabledReason]);
            operationReason.text = disabledText;
            candidateGroup.dom.tabIndex = disabledReason === null ? -1 : 0;
            if (disabledReason === null) {
                candidateGroup.dom.removeAttribute('aria-describedby');
            } else {
                candidateGroup.dom.setAttribute(
                    'aria-describedby',
                    'ai-select-candidate-operation-reason'
                );
            }
            for (const operation of candidateOperations) {
                const button = operationButtons.get(operation);
                if (button === undefined) {
                    continue;
                }
                const label = i18n.t(`select-toolbar.${operation}`);
                const description = disabledText;
                button.text = label;
                button.dom.setAttribute('aria-label', label);
                button.enabled =
                    candidatePresentation.toolbar.operationsEnabled;
                button.dom.title = description || label;
                if (description.length > 0) {
                    button.dom.setAttribute('aria-description', description);
                } else {
                    button.dom.removeAttribute('aria-description');
                }
            }

            if (!candidateContext) {
                closeOverlayMenu(false);
            }
            if (!hasContext) {
                closeOverflow(false);
            }
        };
        controller.subscribe((state) => {
            anchorState = state;
            render();
        });
        inspection.subscribe((state) => {
            inspectionState = state;
            render();
        });
        confirmation.subscribe((state) => {
            confirmationState = state;
            render();
        });
        options.candidatePresentation.subscribe((state) => {
            candidatePresentation = state;
            render();
        });
        options.candidateOverlay.subscribe((state) => {
            overlayState = state;
            render();
        });
        i18n.onChange(render, this);
    }
}
