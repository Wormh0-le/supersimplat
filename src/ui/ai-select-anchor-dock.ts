import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import {
    type AISelectAnchorConfirmationController,
    type AISelectAnchorConfirmationState
} from '../ai-select/anchor-confirmation';
import {
    type AISelectAnchorController,
    type AISelectAnchorState
} from '../ai-select/anchor-controller';
import {
    getAnchorDockPresentation,
    type AnchorDockPresentation
} from '../ai-select/anchor-dock-presentation';
import {
    pointerActionForTool,
    type AuthoringTool
} from '../ai-select/authoring-interaction';
import type {
    AISelectGeneratedViewController,
    AISelectGeneratedViewState,
    GeneratedAIView
} from '../ai-select/generated-view-controller';
import {
    decodeMaskArtifact,
    type BrushStroke
} from '../ai-select/mask-annotation';
import {
    type AISelectMaskController,
    type AISelectMaskState
} from '../ai-select/mask-controller';
import { promptToolCapabilityReason } from '../ai-select/prompt-state';
import { reviewReasonActionKeys } from '../ai-select/view-assessment';

export interface AISelectAnchorDockOptions {
    readonly onRetry: () => Promise<void>;
    readonly onReconnect: () => Promise<void>;
    readonly onOpenSettings: () => void;
    readonly onValidate: () => Promise<void>;
    readonly onConfirmAnchor: () => Promise<void>;
    readonly onAdjustAnchor: () => void;
    readonly generatedViews: AISelectGeneratedViewController;
}

interface ImagePixel {
    readonly xPx: number;
    readonly yPx: number;
}

interface GeneratedCardElements {
    readonly root: Container;
    readonly image: HTMLImageElement;
    readonly title: Label;
    readonly status: Label;
    readonly retryButton: Button;
    readonly retryMaskButton: Button;
    readonly confirmReviewButton: Button;
    readonly participationButton: Button;
    rgbDigest?: string;
}

const CLICK_TOLERANCE_PX = 4;
type DockAuthoringTool = Exclude<AuthoringTool, 'inspect'>;

/** The first AI View Dock: authoritative RGB plus the Anchor Mask surface. */
export class AISelectAnchorDock extends Container {
    private readonly mask: AISelectMaskController;
    private readonly confirmation: AISelectAnchorConfirmationController;
    private readonly generatedViews: AISelectGeneratedViewController;
    private readonly status: Label;
    private readonly maskStatus: Label;
    private readonly image: HTMLImageElement;
    private readonly overlay: HTMLCanvasElement;
    private readonly failureActions: Container;
    private readonly maskActions: Container;
    private readonly toolActions: Container;
    private readonly toolButtons = new Map<DockAuthoringTool, Button>();
    private readonly promptUndoButton: Button;
    private readonly promptRedoButton: Button;
    private readonly clearPromptsButton: Button;
    private readonly acceptProposalButton: Button;
    private readonly brushSizeInput: HTMLInputElement;
    private readonly textPromptInput: HTMLInputElement;
    private readonly textPromptApply: Button;
    private readonly boxPreview: HTMLDivElement;
    private readonly confirmMaskButton: Button;
    private readonly retryMaskButton: Button;
    private readonly clearMaskButton: Button;
    private readonly restoreAutoButton: Button;
    private readonly undoMaskButton: Button;
    private readonly redoMaskButton: Button;
    private readonly anchorActions: Container;
    private readonly validateButton: Button;
    private readonly confirmAnchorButton: Button;
    private readonly adjustAnchorButton: Button;
    private readonly validationStatus: Label;
    private readonly gallery: Container;
    private readonly plannerLine: Container;
    private readonly plannerStatus: Label;
    private readonly plannerRetryButton: Button;
    private readonly galleryCards: Container;
    private readonly anchorCard: GeneratedCardElements;
    private readonly generatedCards = new Map<string, GeneratedCardElements>();
    private state: AISelectAnchorState = { context: null, anchor: null };
    private maskState: AISelectMaskState;
    private confirmationState: AISelectAnchorConfirmationState;
    private generatedState: AISelectGeneratedViewState;
    private dragStart: { x: number; y: number } | null = null;
    private gestureStartPixel: ImagePixel | null = null;
    private lastStrokePixel: ImagePixel | null = null;
    private promptBrushStrokes: BrushStroke[] = [];
    private activeTool: DockAuthoringTool = 'positive-point';

    constructor(
        controller: AISelectAnchorController,
        mask: AISelectMaskController,
        confirmation: AISelectAnchorConfirmationController,
        options: AISelectAnchorDockOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-anchor-dock'
        });
        this.mask = mask;
        this.confirmation = confirmation;
        this.generatedViews = options.generatedViews;
        this.maskState = mask.state;
        this.confirmationState = confirmation.state;
        this.generatedState = options.generatedViews.state;
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );
        // Explicit focus routing: while the Mask Editor holds focus,
        // Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z (or Ctrl+Y) belong to mask-local
        // Undo/Redo and never reach native EditHistory.
        this.dom.tabIndex = 0;
        this.dom.addEventListener('keydown', (event) =>
            this.routeEditingKeys(event)
        );

        const title = new Label({ id: 'ai-select-anchor-dock-title' });
        i18n.bindText(title, 'ai-select.panel.title');
        this.status = new Label({ id: 'ai-select-anchor-dock-status' });

        const imageWrap = document.createElement('div');
        imageWrap.id = 'ai-select-anchor-dock-image-wrap';
        this.image = document.createElement('img');
        this.image.id = 'ai-select-anchor-dock-image';
        this.image.alt = '';
        this.image.hidden = true;
        this.overlay = document.createElement('canvas');
        this.overlay.id = 'ai-select-anchor-dock-mask-overlay';
        this.overlay.hidden = true;
        this.boxPreview = document.createElement('div');
        this.boxPreview.id = 'ai-select-anchor-dock-box-preview';
        this.boxPreview.hidden = true;
        imageWrap.appendChild(this.image);
        imageWrap.appendChild(this.overlay);
        imageWrap.appendChild(this.boxPreview);
        imageWrap.addEventListener('pointerdown', (event) =>
            this.beginStroke(event)
        );
        imageWrap.addEventListener('pointermove', (event) =>
            this.continueStroke(event)
        );
        imageWrap.addEventListener('pointerup', (event) =>
            this.endStroke(event)
        );
        imageWrap.addEventListener('pointercancel', () => {
            this.dragStart = null;
            this.gestureStartPixel = null;
            this.lastStrokePixel = null;
            this.promptBrushStrokes = [];
            this.boxPreview.hidden = true;
        });

        this.maskStatus = new Label({
            id: 'ai-select-anchor-dock-mask-status'
        });
        this.maskStatus.hidden = true;

        this.maskActions = new Container({
            id: 'ai-select-anchor-dock-mask-actions',
            hidden: true
        });
        this.toolActions = new Container({
            id: 'ai-select-anchor-dock-tools',
            hidden: true
        });
        const toolKeys: readonly [DockAuthoringTool, string][] = [
            ['positive-point', 'ai-select.prompt.point-positive'],
            ['negative-point', 'ai-select.prompt.point-negative'],
            ['positive-box', 'ai-select.prompt.box-positive'],
            ['negative-box', 'ai-select.prompt.box-negative'],
            ['positive-mask-constraint', 'ai-select.prompt.brush-positive'],
            ['negative-mask-constraint', 'ai-select.prompt.brush-negative'],
            ['positive-text', 'ai-select.prompt.text-positive'],
            ['negative-text', 'ai-select.prompt.text-negative'],
            ['paint', 'ai-select.edit.paint'],
            ['erase', 'ai-select.edit.erase']
        ];
        for (const [tool, key] of toolKeys) {
            const button = new Button({
                id: `ai-select-anchor-tool-${tool}`
            });
            i18n.bindText(button, key);
            button.on('click', () => {
                this.activeTool = tool;
                this.renderTools();
            });
            this.toolButtons.set(tool, button);
            this.toolActions.append(button);
        }
        this.brushSizeInput = document.createElement('input');
        this.brushSizeInput.id = 'ai-select-anchor-brush-size';
        this.brushSizeInput.type = 'range';
        this.brushSizeInput.min = '1';
        this.brushSizeInput.max = '64';
        this.brushSizeInput.value = '8';
        this.brushSizeInput.setAttribute(
            'aria-label',
            i18n.t('ai-select.edit.brush-size')
        );
        this.toolActions.dom.appendChild(this.brushSizeInput);
        this.textPromptInput = document.createElement('input');
        this.textPromptInput.id = 'ai-select-anchor-text-prompt';
        this.textPromptInput.type = 'text';
        this.textPromptInput.placeholder = i18n.t(
            'ai-select.prompt.text-placeholder'
        );
        this.textPromptApply = new Button({
            id: 'ai-select-anchor-text-apply'
        });
        i18n.bindText(this.textPromptApply, 'ai-select.prompt.text-apply');
        this.textPromptApply.on('click', () => {
            const polarity =
                this.activeTool === 'negative-text' ? 'exclude' : 'include';
            this.mask
                .addTextPrompt({
                    text: this.textPromptInput.value,
                    polarity
                })
                .then(() => {
                    this.textPromptInput.value = '';
                })
                .catch((error) => console.error(error));
        });
        this.toolActions.dom.appendChild(this.textPromptInput);
        this.toolActions.append(this.textPromptApply);
        this.promptUndoButton = new Button({
            id: 'ai-select-anchor-prompt-undo'
        });
        this.promptRedoButton = new Button({
            id: 'ai-select-anchor-prompt-redo'
        });
        this.clearPromptsButton = new Button({
            id: 'ai-select-anchor-prompt-clear'
        });
        this.acceptProposalButton = new Button({
            id: 'ai-select-anchor-proposal-accept'
        });
        i18n.bindText(this.promptUndoButton, 'ai-select.prompt.undo');
        i18n.bindText(this.promptRedoButton, 'ai-select.prompt.redo');
        i18n.bindText(this.clearPromptsButton, 'ai-select.prompt.clear');
        i18n.bindText(this.acceptProposalButton, 'ai-select.proposal.accept');
        this.promptUndoButton.on('click', () => {
            try {
                this.mask.undoPromptEdit();
            } catch (error) {
                console.error(error);
            }
        });
        this.promptRedoButton.on('click', () => {
            try {
                this.mask.redoPromptEdit();
            } catch (error) {
                console.error(error);
            }
        });
        this.clearPromptsButton.on('click', () => {
            try {
                this.mask.clearPrompts();
            } catch (error) {
                console.error(error);
            }
        });
        this.acceptProposalButton.on('click', () => {
            const proposal = this.maskState.proposalSet?.proposals[0];
            if (proposal === undefined) {
                return;
            }
            try {
                this.mask.acceptProposal(proposal.proposalId);
            } catch (error) {
                console.error(error);
            }
        });
        this.toolActions.append(this.promptUndoButton);
        this.toolActions.append(this.promptRedoButton);
        this.toolActions.append(this.clearPromptsButton);
        this.toolActions.append(this.acceptProposalButton);
        this.confirmMaskButton = new Button({
            id: 'ai-select-anchor-dock-confirm-mask'
        });
        this.retryMaskButton = new Button({
            id: 'ai-select-anchor-dock-retry-mask'
        });
        this.clearMaskButton = new Button({
            id: 'ai-select-anchor-dock-clear-mask'
        });
        this.restoreAutoButton = new Button({
            id: 'ai-select-anchor-dock-restore-auto'
        });
        this.undoMaskButton = new Button({
            id: 'ai-select-anchor-dock-undo-mask'
        });
        this.redoMaskButton = new Button({
            id: 'ai-select-anchor-dock-redo-mask'
        });
        i18n.bindText(this.confirmMaskButton, 'ai-select.mask.confirm');
        i18n.bindText(this.retryMaskButton, 'ai-select.mask.retry');
        i18n.bindText(this.clearMaskButton, 'ai-select.mask.clear');
        i18n.bindText(this.restoreAutoButton, 'ai-select.mask.restore-auto');
        i18n.bindText(this.undoMaskButton, 'ai-select.mask.undo');
        i18n.bindText(this.redoMaskButton, 'ai-select.mask.redo');
        this.confirmMaskButton.on('click', () => {
            try {
                this.mask.confirmEditingMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.retryMaskButton.on('click', () => {
            this.mask.retryMaskRequest().catch((error) => console.error(error));
        });
        this.clearMaskButton.on('click', () => {
            try {
                this.mask.clearEditingMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.restoreAutoButton.on('click', () => {
            try {
                this.mask.restoreAutoMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.undoMaskButton.on('click', () => {
            try {
                this.mask.undoMaskEdit();
            } catch (error) {
                console.error(error);
            }
        });
        this.redoMaskButton.on('click', () => {
            try {
                this.mask.redoMaskEdit();
            } catch (error) {
                console.error(error);
            }
        });
        this.maskActions.append(this.confirmMaskButton);
        this.maskActions.append(this.retryMaskButton);
        this.maskActions.append(this.clearMaskButton);
        this.maskActions.append(this.restoreAutoButton);
        this.maskActions.append(this.undoMaskButton);
        this.maskActions.append(this.redoMaskButton);

        this.anchorActions = new Container({
            id: 'ai-select-anchor-dock-anchor-actions',
            hidden: true
        });
        this.validateButton = new Button({
            id: 'ai-select-anchor-dock-validate'
        });
        this.confirmAnchorButton = new Button({
            id: 'ai-select-anchor-dock-confirm-anchor'
        });
        this.adjustAnchorButton = new Button({
            id: 'ai-select-anchor-dock-adjust-anchor',
            hidden: true
        });
        i18n.bindText(this.validateButton, 'ai-select.anchor.validate');
        i18n.bindText(this.confirmAnchorButton, 'ai-select.anchor.confirm');
        i18n.bindText(this.adjustAnchorButton, 'ai-select.adjust-anchor');
        this.validateButton.on('click', () => {
            options.onValidate().catch((error) => console.error(error));
        });
        this.confirmAnchorButton.on('click', () => {
            options.onConfirmAnchor().catch((error) => console.error(error));
        });
        this.adjustAnchorButton.on('click', () => {
            options.onAdjustAnchor();
        });
        this.anchorActions.append(this.validateButton);
        this.anchorActions.append(this.confirmAnchorButton);
        this.anchorActions.append(this.adjustAnchorButton);
        this.validationStatus = new Label({
            id: 'ai-select-anchor-dock-validation-status',
            hidden: true
        });

        this.failureActions = new Container({
            id: 'ai-select-anchor-dock-failure-actions',
            hidden: true
        });
        const retry = new Button({ id: 'ai-select-anchor-dock-retry' });
        const reconnect = new Button({ id: 'ai-select-anchor-dock-reconnect' });
        const settings = new Button({ id: 'ai-select-anchor-dock-settings' });
        i18n.bindText(retry, 'ai-select.retry');
        i18n.bindText(reconnect, 'ai-select.reconnect');
        i18n.bindText(settings, 'ai-select.open-settings');
        retry.on('click', () => {
            options.onRetry().catch((error) => console.error(error));
        });
        reconnect.on('click', () => {
            options.onReconnect().catch((error) => console.error(error));
        });
        settings.on('click', () => options.onOpenSettings());
        this.failureActions.append(retry);
        this.failureActions.append(reconnect);
        this.failureActions.append(settings);

        // The AI View Gallery: progressive Generated View cards with their
        // independent Render/Mask/Evidence states, plus the Anchor card.
        this.gallery = new Container({
            id: 'ai-select-view-gallery',
            hidden: true
        });
        this.plannerLine = new Container({
            id: 'ai-select-view-gallery-planner',
            hidden: true
        });
        this.plannerStatus = new Label({
            id: 'ai-select-view-gallery-planner-status'
        });
        this.plannerRetryButton = new Button({
            id: 'ai-select-view-gallery-planner-retry'
        });
        i18n.bindText(this.plannerRetryButton, 'ai-select.views.planner.retry');
        this.plannerRetryButton.on('click', () => {
            try {
                this.generatedViews.retryPlanning();
            } catch (error) {
                console.error(error);
            }
        });
        this.plannerLine.append(this.plannerStatus);
        this.plannerLine.append(this.plannerRetryButton);
        this.galleryCards = new Container({
            id: 'ai-select-view-gallery-cards'
        });
        this.gallery.append(this.plannerLine);
        this.gallery.append(this.galleryCards);
        this.anchorCard = this.createCard(
            () => this.selectGeneratedView(null),
            null
        );
        this.galleryCards.append(this.anchorCard.root);

        this.append(title);
        // The main area is a horizontal row: the image can never underflow
        // the control rows (the old vertical stack let an overflowing image
        // slide beneath them, swallowing clicks and clipping buttons).
        const mainRow = new Container({ id: 'ai-select-anchor-dock-main' });
        mainRow.dom.appendChild(imageWrap);
        const controls = new Container({
            id: 'ai-select-anchor-dock-controls'
        });
        controls.append(this.status);
        controls.append(this.maskStatus);
        controls.append(this.toolActions);
        controls.append(this.maskActions);
        controls.append(this.anchorActions);
        controls.append(this.validationStatus);
        controls.append(this.failureActions);
        mainRow.append(controls);
        this.append(mainRow);
        this.append(this.gallery);

        controller.subscribe((state) => {
            this.state = state;
            this.render();
        });
        mask.subscribe((maskState) => {
            this.maskState = maskState;
            this.render();
        });
        confirmation.subscribe((confirmationState) => {
            this.confirmationState = confirmationState;
            this.render();
        });
        options.generatedViews.subscribe((generatedState) => {
            this.generatedState = generatedState;
            this.render();
        });
        i18n.onChange(() => this.render(), this);
    }

    private render(): void {
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        if (presentation.rgb) {
            this.image.src = `data:image/png;base64,${presentation.rgb.pngBase64}`;
            this.image.hidden = false;
        } else {
            this.image.hidden = true;
        }
        const textKey = {
            idle: 'ai-select.panel.idle',
            ready: 'ai-select.anchor.ready',
            previewing: 'ai-select.anchor.previewing',
            rendering: 'ai-select.anchor.rendering',
            failed: 'ai-select.anchor.failed'
        }[presentation.status];
        this.status.text = i18n.t(textKey);
        this.failureActions.hidden = !presentation.showFailureActions;

        const mask = presentation.mask;
        if (mask.status === 'none' && presentation.status !== 'ready') {
            this.maskStatus.hidden = true;
        } else {
            this.maskStatus.hidden = false;
            this.maskStatus.text =
                mask.status === 'failed' && mask.errorMessage !== undefined
                    ? mask.errorMessage
                    : mask.proposalStatus === 'unavailable'
                      ? i18n.t('ai-select.proposal.unavailable')
                      : mask.proposalStatus === 'ready' &&
                          this.maskState.editingMask === null
                        ? i18n.t('ai-select.proposal.ready')
                        : i18n.t(`ai-select.mask.${mask.status}`);
        }
        this.confirmMaskButton.hidden = !mask.showConfirm;
        this.retryMaskButton.hidden = !mask.showRetry;
        this.confirmMaskButton.enabled =
            mask.showConfirm && !this.confirmation.locked;
        this.retryMaskButton.enabled =
            mask.showRetry && !this.confirmation.locked;
        this.renderEditingActions(presentation);
        this.renderTools();
        this.renderAnchorActions(presentation);
        this.renderMaskOverlay(presentation);
        this.renderGallery(presentation);
    }

    private createCard(
        onClick: () => void,
        onRetry: (() => void) | null
    ): GeneratedCardElements {
        const root = new Container({ class: 'ai-select-view-card' });
        const image = document.createElement('img');
        image.className = 'ai-select-view-card-image';
        image.alt = '';
        image.hidden = true;
        image.draggable = false;
        const title = new Label({ class: 'ai-select-view-card-title' });
        const status = new Label({ class: 'ai-select-view-card-status' });
        const retryButton = new Button({
            class: 'ai-select-view-card-retry',
            hidden: true
        });
        const retryMaskButton = new Button({
            class: 'ai-select-view-card-retry-mask',
            hidden: true
        });
        const confirmReviewButton = new Button({
            class: 'ai-select-view-card-confirm-review',
            hidden: true
        });
        const participationButton = new Button({
            class: 'ai-select-view-card-participation',
            hidden: true
        });
        i18n.bindText(retryButton, 'ai-select.views.retry-render');
        i18n.bindText(retryMaskButton, 'ai-select.views.retry-mask');
        i18n.bindText(confirmReviewButton, 'ai-select.review.confirm-as-is');
        if (onRetry !== null) {
            retryButton.on('click', (event: Event) => {
                event.stopPropagation();
                onRetry();
            });
        }
        retryMaskButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.retryGeneratedViewMask(viewId);
            }
        });
        confirmReviewButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.confirmGeneratedReview(viewId);
            }
        });
        participationButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.toggleGeneratedViewParticipation(viewId);
            }
        });
        root.dom.appendChild(image);
        root.append(title);
        root.append(status);
        root.append(retryButton);
        root.append(retryMaskButton);
        root.append(confirmReviewButton);
        root.append(participationButton);
        root.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );
        root.dom.addEventListener('click', () => onClick());
        return {
            root,
            image,
            title,
            status,
            retryButton,
            retryMaskButton,
            confirmReviewButton,
            participationButton
        };
    }

    private renderGallery(presentation: AnchorDockPresentation): void {
        const generated = this.generatedState;
        const showGallery =
            this.state.context !== null &&
            (generated.plannerStatus !== 'idle' || generated.views.length > 0);
        this.gallery.hidden = !showGallery;
        if (!showGallery) {
            return;
        }

        if (generated.plannerStatus === 'planning') {
            this.plannerLine.hidden = false;
            this.plannerStatus.text = i18n.t(
                'ai-select.views.planner.planning'
            );
            this.plannerRetryButton.hidden = true;
        } else if (generated.plannerStatus === 'failed') {
            this.plannerLine.hidden = false;
            this.plannerStatus.text =
                generated.plannerErrorMessage ??
                i18n.t('ai-select.views.planner.failed');
            this.plannerRetryButton.hidden = false;
        } else {
            this.plannerLine.hidden = true;
        }

        // The Anchor card mirrors the Anchor's own render surface.
        const anchorStatusKey = {
            idle: 'ai-select.panel.idle',
            ready: 'ai-select.anchor.ready',
            previewing: 'ai-select.anchor.previewing',
            rendering: 'ai-select.anchor.rendering',
            failed: 'ai-select.anchor.failed'
        }[presentation.status];
        this.anchorCard.title.text = i18n.t('ai-select.views.anchor');
        this.anchorCard.status.text = i18n.t(anchorStatusKey);
        this.anchorCard.retryButton.hidden = true;
        this.anchorCard.retryMaskButton.hidden = true;
        this.anchorCard.confirmReviewButton.hidden = true;
        this.anchorCard.participationButton.hidden = true;
        if (presentation.rgb !== undefined) {
            if (this.anchorCard.rgbDigest !== presentation.rgb.digest) {
                this.anchorCard.rgbDigest = presentation.rgb.digest;
                this.anchorCard.image.src = `data:image/png;base64,${presentation.rgb.pngBase64}`;
            }
            this.anchorCard.image.hidden = false;
        } else {
            this.anchorCard.image.hidden = true;
        }
        this.anchorCard.root.dom.classList.toggle(
            'selected',
            this.generatedState.selectedViewId === null
        );

        const seen = new Set<string>();
        generated.views.forEach((view, index) => {
            seen.add(view.viewId);
            let card = this.generatedCards.get(view.viewId);
            if (card === undefined) {
                card = this.createCard(
                    () => this.selectGeneratedView(view.viewId),
                    () => this.retryGeneratedViewRender(view.viewId)
                );
                this.generatedCards.set(view.viewId, card);
                this.galleryCards.append(card.root);
            }
            this.updateGeneratedCard(card, view, index);
        });
        for (const [viewId, card] of this.generatedCards) {
            if (!seen.has(viewId)) {
                card.root.destroy();
                this.generatedCards.delete(viewId);
            }
        }
    }

    private updateGeneratedCard(
        card: GeneratedCardElements,
        view: GeneratedAIView,
        index: number
    ): void {
        card.title.text = `${i18n.t('ai-select.views.generated')} ${index + 1}`;
        card.root.dom.dataset.viewId = view.viewId;
        const lines: string[] = [
            i18n.t(`ai-select.views.status.${view.renderStatus}`)
        ];
        if (
            view.renderStatus === 'failed' &&
            view.renderErrorMessage !== undefined
        ) {
            lines.push(view.renderErrorMessage);
        }
        if (view.renderStatus === 'ready') {
            lines.push(
                i18n.t(`ai-select.views.status.mask-${view.maskStatus}`)
            );
            if (
                view.maskStatus === 'failed' &&
                view.maskErrorMessage !== undefined
            ) {
                lines.push(view.maskErrorMessage);
                lines.push(i18n.t('ai-select.review.mask-failure-options'));
            }
            // Ticket 06 never requests Evidence; later statuses arrive with
            // the formal Evidence path and their own localized keys.
            if (view.evidenceStatus === 'not-requested') {
                lines.push(
                    i18n.t('ai-select.views.status.evidence-not-requested')
                );
            }
            lines.push(i18n.t(`ai-select.review.quality.${view.maskQuality}`));
            lines.push(i18n.t(`ai-select.participation.${view.participation}`));
            if (view.assessment?.status === 'review') {
                for (const reason of view.assessment.actionableReasons) {
                    lines.push(i18n.t(`ai-select.review.reason.${reason}`));
                    for (const actionKey of reviewReasonActionKeys(reason)) {
                        lines.push(`• ${i18n.t(actionKey)}`);
                    }
                }
                lines.push(i18n.t('ai-select.review.correction-options'));
            }
        }
        card.status.text = lines.join('\n');
        card.retryButton.hidden = view.renderStatus !== 'failed';
        card.retryMaskButton.hidden =
            view.renderStatus !== 'ready' || view.maskStatus !== 'failed';
        card.confirmReviewButton.hidden =
            view.maskStatus !== 'ready' ||
            view.assessment?.status !== 'review' ||
            view.maskQuality === 'user-confirmed';
        const canToggleParticipation =
            view.participation === 'included' ||
            view.maskQuality === 'auto-good' ||
            view.maskQuality === 'user-confirmed';
        card.participationButton.hidden = !canToggleParticipation;
        card.participationButton.text =
            view.participation === 'included'
                ? i18n.t('ai-select.participation.exclude')
                : i18n.t('ai-select.participation.include');
        if (view.rgb !== undefined) {
            if (card.rgbDigest !== view.rgb.digest) {
                card.rgbDigest = view.rgb.digest;
                card.image.src = `data:image/png;base64,${view.rgb.pngBase64}`;
            }
            card.image.hidden = false;
        } else {
            card.image.hidden = true;
        }
        card.root.dom.classList.toggle('selected', view.selected);
    }

    private selectGeneratedView(viewId: string | null): void {
        try {
            this.generatedViews.selectView(viewId);
        } catch (error) {
            console.error(error);
        }
    }

    private retryGeneratedViewRender(viewId: string): void {
        try {
            this.generatedViews.retryViewRender(viewId);
        } catch (error) {
            console.error(error);
        }
    }

    private retryGeneratedViewMask(viewId: string): void {
        try {
            this.generatedViews.retryViewMask(viewId);
        } catch (error) {
            console.error(error);
        }
    }

    private confirmGeneratedReview(viewId: string): void {
        try {
            this.generatedViews.confirmReviewAsIs(viewId);
        } catch (error) {
            console.error(error);
        }
    }

    private toggleGeneratedViewParticipation(viewId: string): void {
        try {
            const view = this.generatedState.views.find(
                (entry) => entry.viewId === viewId
            );
            if (view === undefined) {
                return;
            }
            this.generatedViews.setViewParticipation(
                viewId,
                view.participation === 'included' ? 'excluded' : 'included'
            );
        } catch (error) {
            console.error(error);
        }
    }

    private renderEditingActions(presentation: AnchorDockPresentation): void {
        const editingReady =
            presentation.status === 'ready' && !this.confirmation.locked;
        this.clearMaskButton.hidden = !editingReady;
        this.restoreAutoButton.hidden = !editingReady;
        this.undoMaskButton.hidden = !editingReady;
        this.redoMaskButton.hidden = !editingReady;
        this.clearMaskButton.enabled =
            editingReady && this.maskState.editingMask !== null;
        this.restoreAutoButton.enabled =
            editingReady && this.maskState.canRestoreAuto;
        this.undoMaskButton.enabled = editingReady && this.maskState.canUndo;
        this.redoMaskButton.enabled = editingReady && this.maskState.canRedo;
        this.maskActions.hidden =
            !presentation.mask.showConfirm &&
            !presentation.mask.showRetry &&
            !editingReady;
    }

    private renderTools(): void {
        const ready =
            getAnchorDockPresentation(this.state, this.maskState).status ===
                'ready' && !this.confirmation.locked;
        this.toolActions.hidden = !ready;
        const capabilities = this.maskState.promptCapabilities;
        for (const [tool, button] of this.toolButtons) {
            const reason =
                tool === 'paint' || tool === 'erase'
                    ? null
                    : capabilities === null
                      ? 'Prompt Adapter capabilities are unavailable.'
                      : promptToolCapabilityReason(tool, capabilities);
            button.enabled = ready && reason === null;
            button.dom.title = reason ?? '';
            button.dom.classList.toggle(
                'ai-select-tool-selected',
                tool === this.activeTool
            );
        }
        const activeButton = this.toolButtons.get(this.activeTool);
        if (activeButton !== undefined && !activeButton.enabled) {
            this.activeTool =
                capabilities?.points === true ? 'positive-point' : 'paint';
            this.toolButtons
                .get(this.activeTool)
                ?.dom.classList.add('ai-select-tool-selected');
        }
        const brushActive =
            this.activeTool === 'paint' ||
            this.activeTool === 'erase' ||
            this.activeTool === 'positive-mask-constraint' ||
            this.activeTool === 'negative-mask-constraint';
        this.brushSizeInput.hidden = !brushActive;
        const textActive =
            this.activeTool === 'positive-text' ||
            this.activeTool === 'negative-text';
        this.textPromptInput.hidden = !textActive;
        this.textPromptApply.hidden = !textActive;
        this.promptUndoButton.enabled = ready && this.maskState.canUndoPrompt;
        this.promptRedoButton.enabled = ready && this.maskState.canRedoPrompt;
        this.clearPromptsButton.enabled =
            ready &&
            this.maskState.promptState !== null &&
            (this.maskState.promptState.points.length > 0 ||
                this.maskState.promptState.boxes.length > 0 ||
                this.maskState.promptState.maskConstraints.length > 0 ||
                this.maskState.promptState.textPrompts.length > 0);
        const proposal = this.maskState.proposalSet?.proposals[0];
        this.acceptProposalButton.hidden =
            proposal === undefined ||
            proposal.proposalId === this.maskState.acceptedProposalId;
        this.acceptProposalButton.enabled =
            ready && !this.acceptProposalButton.hidden;
    }

    private renderAnchorActions(presentation: AnchorDockPresentation): void {
        const confirmation = this.confirmationState;
        const confirmed = confirmation.confirmedAnchor !== null;
        const ready = presentation.status === 'ready';
        this.anchorActions.hidden = !ready && !confirmed;
        this.validateButton.hidden = confirmed;
        this.validateButton.enabled =
            ready &&
            confirmation.validationStatus !== 'validating' &&
            this.maskState.stableMask !== null;
        this.confirmAnchorButton.hidden = confirmed;
        this.confirmAnchorButton.enabled =
            ready &&
            confirmation.validationStatus !== 'validating' &&
            confirmation.validation !== null &&
            confirmation.validation.canConfirm;
        this.adjustAnchorButton.hidden = !confirmed;

        const lines: string[] = [];
        if (confirmed) {
            lines.push(i18n.t('ai-select.anchor.confirmed'));
        } else if (confirmation.validationStatus === 'validating') {
            lines.push(i18n.t('ai-select.validation.validating'));
        } else if (
            confirmation.validationStatus === 'failed' &&
            confirmation.errorMessage !== undefined
        ) {
            lines.push(confirmation.errorMessage);
        } else if (confirmation.validation !== null) {
            for (const block of confirmation.validation.hardBlocks) {
                lines.push(i18n.t(`ai-select.validation.hard.${block}`));
            }
            for (const warning of confirmation.validation.softWarnings) {
                lines.push(i18n.t(`ai-select.validation.soft.${warning}`));
            }
            if (confirmation.validation.canConfirm) {
                lines.push(i18n.t('ai-select.validation.passed'));
            }
        }
        this.validationStatus.hidden = lines.length === 0;
        this.validationStatus.text = lines.join('\n');
    }

    /** Focus-routed Prompt history and Mask edit history remain independent. */
    private routeEditingKeys(event: KeyboardEvent): void {
        if (!(event.ctrlKey || event.metaKey)) {
            return;
        }
        const key = event.key.toLowerCase();
        const redo =
            (key === 'z' && event.shiftKey) || (!event.shiftKey && key === 'y');
        const undo = key === 'z' && !event.shiftKey;
        if (!undo && !redo) {
            return;
        }
        const promptMode =
            this.activeTool !== 'paint' && this.activeTool !== 'erase';
        const available = promptMode
            ? redo
                ? this.maskState.canRedoPrompt
                : this.maskState.canUndoPrompt
            : redo
              ? this.maskState.canRedo
              : this.maskState.canUndo;
        if (!available) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        try {
            if (promptMode) {
                if (redo) {
                    this.mask.redoPromptEdit();
                } else {
                    this.mask.undoPromptEdit();
                }
            } else if (redo) {
                this.mask.redoMaskEdit();
            } else {
                this.mask.undoMaskEdit();
            }
        } catch (error) {
            console.error(error);
        }
    }

    private renderMaskOverlay(presentation: AnchorDockPresentation): void {
        const annotation =
            this.maskState.editingMask ?? this.maskState.stableMask;
        const proposal =
            this.maskState.acceptedProposalId === null
                ? this.maskState.proposalSet?.proposals[0]
                : undefined;
        const artifact = annotation?.artifact ?? proposal?.mask;
        const rgb = presentation.rgb;
        if (
            presentation.status !== 'ready' ||
            artifact === undefined ||
            rgb === undefined ||
            artifact.width !== rgb.width ||
            artifact.height !== rgb.height
        ) {
            this.overlay.hidden = true;
            return;
        }
        const { width, height } = artifact;
        const bits = decodeMaskArtifact(artifact);
        const pixels = new Uint8ClampedArray(width * height * 4);
        const editing =
            this.maskState.editingMask !== null || proposal !== undefined;
        for (let index = 0; index < width * height; index += 1) {
            if ((bits[index >> 3] & (1 << (index % 8))) === 0) {
                continue;
            }
            const offset = index * 4;
            if (editing) {
                pixels[offset] = 255;
                pixels[offset + 1] = 140;
                pixels[offset + 2] = 0;
            } else {
                pixels[offset + 1] = 190;
                pixels[offset + 2] = 255;
            }
            pixels[offset + 3] = 110;
        }
        this.overlay.width = width;
        this.overlay.height = height;
        const context = this.overlay.getContext('2d');
        if (context === null) {
            this.overlay.hidden = true;
            return;
        }
        context.putImageData(new ImageData(pixels, width, height), 0, 0);
        this.positionOverlay();
        this.overlay.hidden = false;
    }

    /** Align the overlay with the object-fit: contain painted image area. */
    private positionOverlay(): void {
        const rect = this.image.getBoundingClientRect();
        const painted = this.paintedRect(rect);
        if (painted === null) {
            this.overlay.hidden = true;
            return;
        }
        this.overlay.style.left = `${(painted.left / rect.width) * 100}%`;
        this.overlay.style.top = `${(painted.top / rect.height) * 100}%`;
        this.overlay.style.width = `${(painted.width / rect.width) * 100}%`;
        this.overlay.style.height = `${(painted.height / rect.height) * 100}%`;
    }

    private paintedRect(rect: DOMRect) {
        if (
            rect.width === 0 ||
            rect.height === 0 ||
            this.image.naturalWidth === 0 ||
            this.image.naturalHeight === 0
        ) {
            return null;
        }
        const scale = Math.min(
            rect.width / this.image.naturalWidth,
            rect.height / this.image.naturalHeight
        );
        const width = this.image.naturalWidth * scale;
        const height = this.image.naturalHeight * scale;
        return {
            left: (rect.width - width) / 2,
            top: (rect.height - height) / 2,
            width,
            height
        };
    }

    private toImagePixel(event: PointerEvent): ImagePixel | null {
        const rect = this.image.getBoundingClientRect();
        const painted = this.paintedRect(rect);
        if (painted === null) {
            return null;
        }
        const xPx = Math.floor(
            ((event.clientX - rect.left - painted.left) / painted.width) *
                this.image.naturalWidth
        );
        const yPx = Math.floor(
            ((event.clientY - rect.top - painted.top) / painted.height) *
                this.image.naturalHeight
        );
        if (
            xPx < 0 ||
            yPx < 0 ||
            xPx >= this.image.naturalWidth ||
            yPx >= this.image.naturalHeight
        ) {
            return null;
        }
        return { xPx, yPx };
    }

    private beginStroke(event: PointerEvent): void {
        if (
            event.button !== 0 ||
            this.confirmation.locked ||
            getAnchorDockPresentation(this.state, this.maskState).status !==
                'ready'
        ) {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (pixel === null) {
            return;
        }
        event.preventDefault();
        this.dragStart = { x: event.clientX, y: event.clientY };
        this.gestureStartPixel = pixel;
        this.lastStrokePixel = pixel;
        this.promptBrushStrokes = [];
        this.image.setPointerCapture(event.pointerId);
        const action = pointerActionForTool(this.activeTool);
        if (action === 'pixel-edit') {
            this.applyPixelEdit(pixel);
        } else if (action === 'prompt-constraint') {
            this.promptBrushStrokes.push(this.promptBrushStroke(pixel));
        } else if (action === 'box') {
            this.updateBoxPreview(pixel, pixel);
        }
    }

    private continueStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (
            pixel === null ||
            (this.lastStrokePixel !== null &&
                pixel.xPx === this.lastStrokePixel.xPx &&
                pixel.yPx === this.lastStrokePixel.yPx)
        ) {
            return;
        }
        this.lastStrokePixel = pixel;
        const action = pointerActionForTool(this.activeTool);
        if (action === 'pixel-edit') {
            this.applyPixelEdit(pixel);
        } else if (action === 'prompt-constraint') {
            this.promptBrushStrokes.push(this.promptBrushStroke(pixel));
        } else if (action === 'box' && this.gestureStartPixel !== null) {
            this.updateBoxPreview(this.gestureStartPixel, pixel);
        }
    }

    private endStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        const moved =
            Math.abs(event.clientX - this.dragStart.x) +
            Math.abs(event.clientY - this.dragStart.y);
        const startPixel = this.gestureStartPixel;
        const strokes = this.promptBrushStrokes;
        this.dragStart = null;
        this.gestureStartPixel = null;
        this.lastStrokePixel = null;
        this.promptBrushStrokes = [];
        this.boxPreview.hidden = true;
        const action = pointerActionForTool(this.activeTool);
        if (action === 'pixel-edit') {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (pixel === null || startPixel === null) {
            return;
        }
        if (action === 'point') {
            if (moved > CLICK_TOLERANCE_PX) {
                return;
            }
            this.mask
                .addPrompt({
                    xPx: pixel.xPx,
                    yPx: pixel.yPx,
                    polarity:
                        this.activeTool === 'negative-point'
                            ? 'exclude'
                            : 'include'
                })
                .catch((error) => console.error(error));
            return;
        }
        if (action === 'box') {
            if (startPixel.xPx === pixel.xPx || startPixel.yPx === pixel.yPx) {
                return;
            }
            this.mask
                .addBoxPrompt({
                    x0Px: startPixel.xPx,
                    y0Px: startPixel.yPx,
                    x1Px: pixel.xPx,
                    y1Px: pixel.yPx,
                    polarity:
                        this.activeTool === 'negative-box'
                            ? 'exclude'
                            : 'include'
                })
                .catch((error) => console.error(error));
            return;
        }
        if (action === 'prompt-constraint') {
            if (strokes.length === 0) {
                strokes.push(this.promptBrushStroke(pixel));
            }
            this.mask
                .addPromptBrushConstraint(
                    strokes,
                    this.activeTool === 'negative-mask-constraint'
                        ? 'exclude'
                        : 'include'
                )
                .catch((error) => console.error(error));
        }
    }

    private brushRadius(): number {
        return Number(this.brushSizeInput.value);
    }

    private promptBrushStroke(pixel: ImagePixel): BrushStroke {
        return {
            xPx: pixel.xPx,
            yPx: pixel.yPx,
            radiusPx: this.brushRadius(),
            mode: 'add'
        };
    }

    private applyPixelEdit(pixel: ImagePixel): void {
        try {
            this.mask.applyBrushStroke({
                xPx: pixel.xPx,
                yPx: pixel.yPx,
                radiusPx: this.brushRadius(),
                mode: this.activeTool === 'erase' ? 'erase' : 'add'
            });
        } catch (error) {
            console.error(error);
        }
    }

    private updateBoxPreview(start: ImagePixel, current: ImagePixel): void {
        const rect = this.image.getBoundingClientRect();
        const painted = this.paintedRect(rect);
        if (painted === null) {
            this.boxPreview.hidden = true;
            return;
        }
        const leftPx =
            painted.left +
            (Math.min(start.xPx, current.xPx) / this.image.naturalWidth) *
                painted.width;
        const topPx =
            painted.top +
            (Math.min(start.yPx, current.yPx) / this.image.naturalHeight) *
                painted.height;
        const widthPx =
            (Math.abs(start.xPx - current.xPx) / this.image.naturalWidth) *
            painted.width;
        const heightPx =
            (Math.abs(start.yPx - current.yPx) / this.image.naturalHeight) *
            painted.height;
        this.boxPreview.style.left = `${leftPx}px`;
        this.boxPreview.style.top = `${topPx}px`;
        this.boxPreview.style.width = `${widthPx}px`;
        this.boxPreview.style.height = `${heightPx}px`;
        this.boxPreview.hidden = false;
    }
}
