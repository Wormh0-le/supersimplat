import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import type { AISelectAnchorAdjustmentController } from '../ai-select/anchor-adjustment';
import type { AISelectAnchorConfirmationController } from '../ai-select/anchor-confirmation';
import type { AISelectAnchorController } from '../ai-select/anchor-controller';
import type { CameraInspectionController } from '../ai-select/camera-inspection';
import type {
    CandidateApplicationController,
    CandidateApplicationOperation,
    CandidateUndoAndFixBlockReason
} from '../ai-select/candidate-application';
import type { CandidateOverlayController } from '../ai-select/candidate-overlay';
import type {
    CandidateOperationDisabledReason,
    CandidatePresentation,
    CandidatePresentationCoordinator
} from '../ai-select/candidate-presentation';
import {
    mapAISelectViewportToolbar,
    type AISelectViewportToolbarControl
} from '../ai-select/viewport-toolbar-presentation';
import addViewSvg from './svg/ai-select-add-view.svg';
import addSvg from './svg/ai-select-add.svg';
import anchorAdjustSvg from './svg/ai-select-anchor-adjust.svg';
import cancelSvg from './svg/ai-select-cancel.svg';
import chevronSvg from './svg/ai-select-chevron.svg';
import confirmSvg from './svg/ai-select-confirm.svg';
import intersectSvg from './svg/ai-select-intersect.svg';
import moveSvg from './svg/ai-select-move.svg';
import newPoseSvg from './svg/ai-select-new-pose.svg';
import overlaySvg from './svg/ai-select-overlay.svg';
import removeSvg from './svg/ai-select-remove.svg';
import resetSvg from './svg/ai-select-reset.svg';
import rotateSvg from './svg/ai-select-rotate.svg';
import setSvg from './svg/ai-select-set.svg';
import undoSvg from './svg/edit-undo.svg';

export interface AISelectToolbarOptions {
    readonly candidatePresentation: CandidatePresentationCoordinator;
    readonly candidateOverlay: CandidateOverlayController;
    readonly candidateApplication: CandidateApplicationController;
    readonly onCandidateApplicationFailure: (error: unknown) => void;
    readonly onBeginAnchorAdjustment: () => void;
    readonly onCancelInspection: () => void;
    readonly onResetAnchorAdjustment: () => void;
    readonly onAddCurrentView: () => void;
    readonly onAdjustNewView: () => void;
    readonly onConfirmDraftView: () => void;
}

const disabledReasonKeys: Record<CandidateOperationDisabledReason, string> = {
    'wait-for-update': 'ai-select.candidate.disabled.wait-for-update',
    'complete-or-exit-correction':
        'ai-select.candidate.disabled.complete-or-exit-correction',
    'update-candidate': 'ai-select.candidate.disabled.update-candidate',
    'restart-target': 'ai-select.candidate.disabled.restart-target'
};

const undoAndFixDisabledReasonKeys: Record<
    CandidateUndoAndFixBlockReason,
    string
> = {
    'candidate-not-applied':
        'ai-select.candidate.undo-and-fix.disabled.not-applied',
    'native-history-changed':
        'ai-select.candidate.undo-and-fix.disabled.history-changed'
};

const operationIcons: Readonly<Record<CandidateApplicationOperation, string>> =
    Object.freeze({
        set: setSvg,
        add: addSvg,
        remove: removeSvg,
        intersect: intersectSvg
    });

const createSvg = (svgString: string): Element => {
    const decoded = decodeURIComponent(
        svgString.substring('data:image/svg+xml,'.length)
    );
    return new DOMParser().parseFromString(decoded, 'image/svg+xml')
        .documentElement;
};

const iconButton = (id: string, icon: string): Button => {
    const button = new Button({ id });
    button.dom.appendChild(createSvg(icon));
    return button;
};

const describeButton = (
    button: Button,
    label: string,
    description = ''
): void => {
    button.dom.setAttribute('aria-label', label);
    button.dom.title =
        description.length > 0 ? `${label}: ${description}` : label;
    if (description.length > 0) {
        button.dom.setAttribute('aria-description', description);
    } else {
        button.dom.removeAttribute('aria-description');
    }
};

/** Compact, icon-only spatial actions for the active AI Select context. */
export class AISelectToolbar extends Container {
    constructor(
        controller: AISelectAnchorController,
        inspection: CameraInspectionController,
        confirmation: AISelectAnchorConfirmationController,
        adjustment: AISelectAnchorAdjustmentController,
        options: AISelectToolbarOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-toolbar',
            hidden: true
        });
        this.dom.setAttribute('role', 'toolbar');
        this.dom.setAttribute('aria-label', i18n.t('ai-select.tool'));
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );

        const anchorAdjust = iconButton(
            'ai-select-toolbar-adjust-anchor',
            anchorAdjustSvg
        );
        const addViewGroup = new Container({
            id: 'ai-select-toolbar-add-view-group',
            hidden: true
        });
        addViewGroup.dom.setAttribute('role', 'group');
        const addCurrentView = iconButton(
            'ai-select-toolbar-add-current-view',
            addViewSvg
        );
        const addViewMenuTrigger = iconButton(
            'ai-select-toolbar-add-view-menu-trigger',
            chevronSvg
        );
        addViewMenuTrigger.dom.setAttribute('aria-haspopup', 'menu');
        addViewMenuTrigger.dom.setAttribute('aria-expanded', 'false');
        const addViewMenu = new Container({
            id: 'ai-select-toolbar-add-view-menu',
            hidden: true
        });
        addViewMenu.dom.setAttribute('role', 'menu');
        const adjustNewView = iconButton(
            'ai-select-toolbar-adjust-new-view',
            newPoseSvg
        );
        adjustNewView.dom.setAttribute('role', 'menuitem');
        addViewMenu.append(adjustNewView);
        addViewGroup.append(addCurrentView);
        addViewGroup.append(addViewMenuTrigger);
        addViewGroup.append(addViewMenu);

        const move = iconButton('ai-select-toolbar-move-anchor', moveSvg);
        const rotate = iconButton('ai-select-toolbar-rotate-anchor', rotateSvg);
        const reset = iconButton('ai-select-toolbar-reset-anchor', resetSvg);
        const confirmDraftView = iconButton(
            'ai-select-toolbar-confirm-view',
            confirmSvg
        );
        const cancel = iconButton(
            'ai-select-toolbar-cancel-inspection',
            cancelSvg
        );

        const candidateGroup = new Container({
            id: 'ai-select-candidate-operation-group',
            hidden: true
        });
        candidateGroup.dom.setAttribute('role', 'group');
        const operationReason = new Label({
            id: 'ai-select-candidate-operation-reason'
        });
        operationReason.dom.setAttribute('role', 'status');
        const overlaySplit = new Container({
            id: 'ai-select-candidate-overlay-split'
        });
        const overlayToggle = iconButton(
            'ai-select-candidate-overlay-toggle',
            overlaySvg
        );
        const overlayMenuTrigger = iconButton(
            'ai-select-candidate-overlay-menu-trigger',
            chevronSvg
        );
        overlayMenuTrigger.dom.setAttribute('aria-haspopup', 'menu');
        overlayMenuTrigger.dom.setAttribute('aria-expanded', 'false');
        const overlayMenu = new Container({
            id: 'ai-select-candidate-overlay-menu',
            hidden: true
        });
        overlayMenu.dom.setAttribute('role', 'menu');
        const uncertainToggle = iconButton(
            'ai-select-candidate-uncertain-toggle',
            overlaySvg
        );
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
        overlaySplit.append(overlayToggle);
        overlaySplit.append(overlayMenuTrigger);
        overlaySplit.append(overlayMenu);
        candidateGroup.append(overlaySplit);

        const candidateOperations: readonly CandidateApplicationOperation[] = [
            'set',
            'add',
            'remove',
            'intersect'
        ];
        const operationButtons = new Map<
            CandidateApplicationOperation,
            Button
        >();
        let candidatePresentation: CandidatePresentation =
            options.candidatePresentation.state;
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
        const applyCandidate = (
            operation: CandidateApplicationOperation
        ): (() => void) => {
            return () => {
                if (!candidatePresentation.toolbar.operationsEnabled) {
                    return;
                }
                options.candidateApplication
                    .apply(operation)
                    .catch((error) => reportApplicationFailure(error));
            };
        };
        for (const operation of candidateOperations) {
            const button = iconButton(
                `ai-select-toolbar-candidate-${operation}`,
                operationIcons[operation]
            );
            button.on('click', applyCandidate(operation));
            operationButtons.set(operation, button);
            candidateGroup.append(button);
        }
        const undoAndFix = iconButton(
            'ai-select-toolbar-candidate-undo-and-fix',
            undoSvg
        );
        undoAndFix.on('click', () => {
            if (!candidatePresentation.toolbar.undoAndFixEnabled) {
                return;
            }
            options.candidateApplication
                .undoAndFix()
                .catch((error) => reportApplicationFailure(error));
        });
        candidateGroup.append(undoAndFix);
        candidateGroup.append(operationReason);

        const closeAddViewMenu = (restoreFocus: boolean): void => {
            if (addViewMenu.hidden) {
                return;
            }
            addViewMenu.hidden = true;
            addViewMenuTrigger.dom.setAttribute('aria-expanded', 'false');
            if (restoreFocus) {
                addViewMenuTrigger.dom.focus();
            }
        };
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
        const openAddViewMenu = (): void => {
            addViewMenu.hidden = false;
            addViewMenuTrigger.dom.setAttribute('aria-expanded', 'true');
            closeOverlayMenu(false);
            adjustNewView.dom.focus();
        };
        const openOverlayMenu = (): void => {
            overlayMenu.hidden = false;
            overlayMenuTrigger.dom.setAttribute('aria-expanded', 'true');
            closeAddViewMenu(false);
            uncertainToggle.dom.focus();
        };

        anchorAdjust.on('click', () => options.onBeginAnchorAdjustment());
        addCurrentView.on('click', () => options.onAddCurrentView());
        addViewMenuTrigger.on('click', () => {
            if (addViewMenu.hidden) {
                openAddViewMenu();
            } else {
                closeAddViewMenu(true);
            }
        });
        addViewMenuTrigger.dom.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown') {
                openAddViewMenu();
                event.preventDefault();
            }
        });
        adjustNewView.on('click', () => {
            closeAddViewMenu(false);
            options.onAdjustNewView();
        });
        move.on('click', () => inspection.setManipulation('move'));
        rotate.on('click', () => inspection.setManipulation('rotate'));
        reset.on('click', () => options.onResetAnchorAdjustment());
        confirmDraftView.on('click', () => options.onConfirmDraftView());
        cancel.on('click', () => options.onCancelInspection());
        overlayToggle.on('click', () =>
            options.candidateOverlay.toggleSelected()
        );
        overlayMenuTrigger.on('click', () => {
            if (overlayMenu.hidden) {
                openOverlayMenu();
            } else {
                closeOverlayMenu(true);
            }
        });
        overlayMenuTrigger.dom.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown') {
                openOverlayMenu();
                event.preventDefault();
            }
        });
        uncertainToggle.on('click', () => {
            options.candidateOverlay.setUncertainVisible(
                !options.candidateOverlay.state.uncertainVisible
            );
        });
        document.addEventListener('pointerdown', (event) => {
            if (!addViewGroup.dom.contains(event.target as Node)) {
                closeAddViewMenu(false);
            }
            if (!candidateGroup.dom.contains(event.target as Node)) {
                closeOverlayMenu(false);
            }
        });
        window.addEventListener(
            'keydown',
            (event) => {
                if (event.key !== 'Escape') {
                    return;
                }
                const addWasOpen = !addViewMenu.hidden;
                const overlayWasOpen = !overlayMenu.hidden;
                closeAddViewMenu(addWasOpen);
                closeOverlayMenu(!addWasOpen && overlayWasOpen);
                if (addWasOpen || overlayWasOpen) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            },
            true
        );

        this.append(anchorAdjust);
        this.append(addViewGroup);
        this.append(move);
        this.append(rotate);
        this.append(reset);
        this.append(confirmDraftView);
        this.append(cancel);
        this.append(candidateGroup);
        this.append(applicationFailure);

        const allButtons: Readonly<
            Partial<Record<AISelectViewportToolbarControl, Button>>
        > = Object.freeze({
            'anchor-adjust': anchorAdjust,
            'add-current-view': addCurrentView,
            'add-new-pose': adjustNewView,
            move,
            rotate,
            reset,
            'confirm-view': confirmDraftView,
            cancel,
            overlay: overlayToggle,
            set: operationButtons.get('set'),
            add: operationButtons.get('add'),
            remove: operationButtons.get('remove'),
            intersect: operationButtons.get('intersect'),
            'undo-and-fix': undoAndFix
        });
        let anchorState = controller.state;
        let inspectionState = inspection.state;
        let confirmationState = confirmation.state;
        let adjustmentState = adjustment.state;
        let overlayState = options.candidateOverlay.state;

        const render = (): void => {
            const presentation = mapAISelectViewportToolbar({
                hasContext: anchorState.context !== null,
                contextActive: anchorState.context?.lifecycle === 'active',
                hasConfirmedAnchor: confirmationState.confirmedAnchor !== null,
                inspectionTarget:
                    inspectionState.mode === 'active'
                        ? inspectionState.target
                        : null,
                manipulation: inspectionState.manipulation,
                adjustmentStatus: adjustmentState.status,
                candidate: candidatePresentation.toolbar
            });
            const controls = new Map(
                presentation.controls.map((entry) => [entry.control, entry])
            );
            this.hidden = presentation.mode === 'hidden';
            anchorAdjust.hidden = !controls.has('anchor-adjust');
            addViewGroup.hidden = !controls.has('add-current-view');
            move.hidden = !controls.has('move');
            rotate.hidden = !controls.has('rotate');
            reset.hidden = !controls.has('reset');
            confirmDraftView.hidden = !controls.has('confirm-view');
            cancel.hidden = !controls.has('cancel');
            candidateGroup.hidden = presentation.mode !== 'candidate';

            for (const [name, button] of Object.entries(allButtons)) {
                if (button === undefined) {
                    continue;
                }
                const entry = controls.get(
                    name as AISelectViewportToolbarControl
                );
                button.enabled = entry?.enabled ?? false;
                if (
                    name === 'anchor-adjust' ||
                    name === 'move' ||
                    name === 'rotate'
                ) {
                    button.dom.setAttribute(
                        'aria-pressed',
                        (entry?.pressed ?? false).toString()
                    );
                } else {
                    button.dom.removeAttribute('aria-pressed');
                }
                button.dom.classList.toggle('active', entry?.pressed ?? false);
            }

            describeButton(
                anchorAdjust,
                i18n.t('ai-select.adjust-anchor'),
                adjustmentState.draft?.renderStatus === 'failed'
                    ? i18n.t('ai-select.anchor.failed')
                    : ''
            );
            describeButton(
                addCurrentView,
                i18n.t('ai-select.views.use-current')
            );
            describeButton(
                addViewMenuTrigger,
                i18n.t('ai-select.views.adjust-new')
            );
            describeButton(adjustNewView, i18n.t('ai-select.views.adjust-new'));
            describeButton(move, i18n.t('ai-select.move'));
            describeButton(rotate, i18n.t('ai-select.rotate'));
            describeButton(reset, i18n.t('ai-select.reset-anchor'));
            describeButton(
                confirmDraftView,
                i18n.t('ai-select.user-view.confirm')
            );
            describeButton(cancel, i18n.t('ai-select.return-to-scene-view'));

            describeButton(
                overlayToggle,
                i18n.t('ai-select.candidate.overlay')
            );
            overlayToggle.dom.setAttribute(
                'aria-pressed',
                overlayState.selectedVisible.toString()
            );
            overlayToggle.dom.classList.toggle(
                'active',
                overlayState.selectedVisible
            );
            describeButton(
                overlayMenuTrigger,
                i18n.t('ai-select.candidate.overlay-options')
            );
            describeButton(
                uncertainToggle,
                i18n.t('ai-select.candidate.uncertain-layer')
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
            candidateGroup.dom.tabIndex = disabledText.length > 0 ? 0 : -1;
            if (disabledText.length > 0) {
                candidateGroup.dom.setAttribute(
                    'aria-describedby',
                    'ai-select-candidate-operation-reason'
                );
            } else {
                candidateGroup.dom.removeAttribute('aria-describedby');
            }
            for (const operation of candidateOperations) {
                const button = operationButtons.get(operation);
                if (button !== undefined) {
                    describeButton(
                        button,
                        i18n.t(`select-toolbar.${operation}`),
                        disabledText
                    );
                }
            }
            const undoAndFixReason =
                candidatePresentation.toolbar.undoAndFixDisabledReason;
            describeButton(
                undoAndFix,
                i18n.t('ai-select.candidate.undo-and-fix'),
                undoAndFixReason === null
                    ? ''
                    : i18n.t(undoAndFixDisabledReasonKeys[undoAndFixReason])
            );

            addViewMenuTrigger.enabled =
                controls.get('add-new-pose')?.enabled ?? false;
            overlayMenuTrigger.enabled = presentation.mode === 'candidate';
            uncertainToggle.enabled = presentation.mode === 'candidate';
            if (presentation.mode !== 'current') {
                closeAddViewMenu(false);
            }
            if (presentation.mode !== 'candidate') {
                closeOverlayMenu(false);
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
        adjustment.subscribe((state) => {
            adjustmentState = state;
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
