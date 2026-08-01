import { Button, Container, Label } from '@playcanvas/pcui';

import {
    AISelectFloatingPalette,
    type PaletteToolAvailability
} from './ai-select-floating-palette';
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
    PointerStrokeBuffer,
    pointerActionForTool
} from '../ai-select/authoring-interaction';
import {
    PALETTE_TOOLS,
    paletteToolForShortcutKey,
    type PaletteTool
} from '../ai-select/floating-palette';
import type {
    AISelectGeneratedViewController,
    AISelectGeneratedViewState,
    GeneratedAIView
} from '../ai-select/generated-view-controller';
import {
    fitImageRect,
    mapClientPointToImagePixel,
    type ImagePixel
} from '../ai-select/image-viewport';
import { decodeMaskArtifact } from '../ai-select/mask-annotation';
import {
    type AISelectMaskController,
    type AISelectMaskState
} from '../ai-select/mask-controller';
import { promptToolCapabilityReason } from '../ai-select/prompt-state';
import { reviewReasonActionKeys } from '../ai-select/view-assessment';
import type {
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessStatus
} from '../selection-service-readiness';

export interface AISelectAnchorDockOptions {
    readonly onRetry: () => Promise<void>;
    readonly onReconnect: () => Promise<void>;
    readonly onOpenSettings: () => void;
    readonly onValidate: () => Promise<void>;
    readonly onConfirmAnchor: () => Promise<void>;
    readonly onAdjustAnchor: () => void;
    readonly generatedViews: AISelectGeneratedViewController;
    readonly readiness: SelectionServiceReadinessInterface;
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
// DG-22 Decision 5 opacity assist proximity; unrelated to the snap threshold.
const PALETTE_GESTURE_DIM_MARGIN_PX = 24;
type DockAuthoringTool = PaletteTool;

const cursorForTool = (tool: DockAuthoringTool): string => {
    const cursors: Partial<Record<DockAuthoringTool, string>> = {
        'positive-point':
            '<circle cx="16" cy="16" r="10" fill="white" stroke="#20c878" stroke-width="2"/><path d="M16 10v12M10 16h12" stroke="#087840" stroke-width="2"/>',
        'negative-point':
            '<circle cx="16" cy="16" r="10" fill="white" stroke="#f05b66" stroke-width="2"/><path d="M10 16h12" stroke="#a01420" stroke-width="2"/>',
        paint: '<circle cx="16" cy="16" r="11" fill="none" stroke="#ff8c20" stroke-width="2"/><path d="M16 11v10M11 16h10" stroke="#ff8c20" stroke-width="2"/>',
        erase: '<circle cx="16" cy="16" r="11" fill="none" stroke="#50c8ff" stroke-width="2"/><path d="m12 12 8 8m0-8-8 8" stroke="#50c8ff" stroke-width="2"/>'
    };
    const svg = cursors[tool];
    if (svg === undefined) {
        return 'crosshair';
    }
    const document = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">${svg}</svg>`;
    return `url("data:image/svg+xml,${encodeURIComponent(document)}") 16 16, crosshair`;
};

/** The first AI View Dock: authoritative RGB plus the Anchor Mask surface. */
export class AISelectAnchorDock extends Container {
    private readonly mask: AISelectMaskController;
    private readonly confirmation: AISelectAnchorConfirmationController;
    private readonly generatedViews: AISelectGeneratedViewController;
    private readonly status: Label;
    private readonly availabilityDot: HTMLSpanElement;
    private readonly availabilityLabel: Label;
    private availabilityStatus: SelectionServiceReadinessStatus;
    private readonly maskStatus: Label;
    private readonly promptStatus: Label;
    private readonly imageViewport: HTMLDivElement;
    private readonly imageSurface: HTMLDivElement;
    private readonly image: HTMLImageElement;
    private readonly overlay: HTMLCanvasElement;
    private readonly technicalDetails: HTMLDetailsElement;
    private readonly technicalDetailsBody: HTMLPreElement;
    private readonly failureActions: Container;
    private readonly maskActions: Container;
    private readonly palette: AISelectFloatingPalette;
    private readonly acceptProposalButton: Button;
    private readonly proposalSelect: HTMLSelectElement;
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
    private readonly pixelStroke = new PointerStrokeBuffer();
    private activeTool: DockAuthoringTool = 'positive-point';
    private spaceHeld = false;

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
            this.handleDockKeydown(event)
        );
        // Space release restores the palette even when the keyup lands
        // outside the Dock; a window blur never leaves it hidden.
        window.addEventListener('keyup', (event) => {
            if (event.key === ' ') {
                this.setSpaceHeld(false);
            }
        });
        window.addEventListener('blur', () => this.setSpaceHeld(false));

        const title = new Label({ id: 'ai-select-anchor-dock-title' });
        i18n.bindText(title, 'ai-select.panel.title');
        this.status = new Label({ id: 'ai-select-anchor-dock-status' });

        // The panel mirrors the 02C three-state Availability projection so
        // the user can see why Prompt tools are gated without opening
        // Settings; no technical or model detail is shown.
        const availability = new Container({
            id: 'ai-select-anchor-dock-availability'
        });
        this.availabilityDot = document.createElement('span');
        availability.dom.appendChild(this.availabilityDot);
        this.availabilityLabel = new Label({
            id: 'ai-select-anchor-dock-availability-label'
        });
        availability.append(this.availabilityLabel);
        availability.dom.setAttribute('role', 'status');
        availability.dom.setAttribute('aria-live', 'polite');
        this.availabilityStatus = options.readiness.state.status;
        options.readiness.subscribe((readinessState) => {
            this.availabilityStatus = readinessState.status;
            this.renderAvailability();
        });

        this.imageViewport = document.createElement('div');
        this.imageViewport.id = 'ai-select-anchor-dock-image-viewport';
        this.imageSurface = document.createElement('div');
        this.imageSurface.id = 'ai-select-anchor-dock-image-wrap';
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
        this.imageSurface.appendChild(this.image);
        this.imageSurface.appendChild(this.overlay);
        this.imageSurface.appendChild(this.boxPreview);
        this.imageViewport.appendChild(this.imageSurface);
        this.imageSurface.addEventListener('pointerdown', (event) =>
            this.beginStroke(event)
        );
        this.imageSurface.addEventListener('pointermove', (event) =>
            this.continueStroke(event)
        );
        this.imageSurface.addEventListener('pointerup', (event) =>
            this.endStroke(event)
        );
        this.imageSurface.addEventListener('pointercancel', () =>
            this.cancelPointerGesture()
        );
        const resizeImageSurface = () => this.updateImageSurfaceRect();
        new ResizeObserver(resizeImageSurface).observe(this.imageViewport);
        this.image.addEventListener('load', resizeImageSurface);

        this.maskStatus = new Label({
            id: 'ai-select-anchor-dock-mask-status'
        });
        this.maskStatus.hidden = true;
        this.promptStatus = new Label({
            id: 'ai-select-anchor-dock-prompt-status',
            hidden: true
        });
        this.technicalDetails = document.createElement('details');
        this.technicalDetails.id = 'ai-select-anchor-technical-details';
        const technicalSummary = document.createElement('summary');
        i18n.onChange(() => {
            technicalSummary.textContent = i18n.t(
                'ai-select.failure.technical-details'
            );
        }, this);
        this.technicalDetailsBody = document.createElement('pre');
        this.technicalDetails.append(
            technicalSummary,
            this.technicalDetailsBody
        );
        this.technicalDetails.hidden = true;

        this.maskActions = new Container({
            id: 'ai-select-anchor-dock-mask-actions',
            hidden: true
        });
        // The floating Prompt/Edit palette (Ticket 07B, DG-22): draggable,
        // collapsible and clamped inside the fitted image. It exposes exactly
        // the v1 tool set; Negative Box and Prompt Brush are absent.
        this.palette = new AISelectFloatingPalette({
            onSelectTool: (tool) => {
                this.cancelPointerGesture();
                this.activeTool = tool;
                this.renderTools();
            },
            onPromptUndo: () => {
                try {
                    this.mask.undoPromptEdit();
                } catch (error) {
                    console.error(error);
                }
            },
            onPromptRedo: () => {
                try {
                    this.mask.redoPromptEdit();
                } catch (error) {
                    console.error(error);
                }
            },
            onClearPrompts: () => {
                try {
                    this.mask.clearPrompts();
                } catch (error) {
                    console.error(error);
                }
            },
            onBrushSizeChange: () => this.renderCurrentMaskOverlay()
        });
        this.imageSurface.appendChild(this.palette.dom);
        this.acceptProposalButton = new Button({
            id: 'ai-select-anchor-proposal-accept'
        });
        this.proposalSelect = document.createElement('select');
        this.proposalSelect.id = 'ai-select-anchor-proposal-select';
        this.proposalSelect.setAttribute(
            'aria-label',
            i18n.t('ai-select.proposal.choose')
        );
        this.proposalSelect.addEventListener('change', () => {
            // The previewed candidate owns the refinement lineage: a later
            // Prompt revision refines from this candidate's logits reference.
            try {
                this.mask.previewProposal(this.proposalSelect.value);
            } catch (error) {
                console.error(error);
            }
            this.renderMaskOverlay(
                getAnchorDockPresentation(this.state, this.maskState)
            );
        });
        i18n.bindText(this.acceptProposalButton, 'ai-select.proposal.accept');
        this.acceptProposalButton.on('click', () => {
            const proposal = this.maskState.proposalSet?.proposals.find(
                (candidate) =>
                    candidate.proposalId === this.proposalSelect.value
            );
            if (proposal === undefined) {
                return;
            }
            try {
                this.mask.acceptProposal(proposal.proposalId);
            } catch (error) {
                console.error(error);
            }
        });
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

        const header = new Container({ id: 'ai-select-anchor-dock-header' });
        header.append(title);
        header.append(availability);
        this.append(header);
        // Image, information, and primary actions have separate ownership.
        // Only the exact fitted image surface accepts pointer authoring.
        const mainRow = new Container({ id: 'ai-select-anchor-dock-main' });
        mainRow.dom.appendChild(this.imageViewport);
        const sidePanel = new Container({
            id: 'ai-select-anchor-dock-side-panel'
        });
        const information = new Container({
            id: 'ai-select-anchor-dock-information'
        });
        information.append(this.status);
        information.append(this.promptStatus);
        information.append(this.maskStatus);
        information.dom.appendChild(this.technicalDetails);
        information.dom.appendChild(this.proposalSelect);
        information.append(this.validationStatus);
        information.append(this.gallery);
        const primaryActions = new Container({
            id: 'ai-select-anchor-dock-primary-actions'
        });
        primaryActions.append(this.acceptProposalButton);
        primaryActions.append(this.maskActions);
        primaryActions.append(this.anchorActions);
        primaryActions.append(this.failureActions);
        sidePanel.append(information);
        sidePanel.append(primaryActions);
        mainRow.append(sidePanel);
        this.append(mainRow);

        controller.subscribe((state) => {
            if (
                state.context?.targetContextId !==
                    this.state.context?.targetContextId ||
                state.anchor?.rgb?.digest !== this.state.anchor?.rgb?.digest
            ) {
                this.cancelPointerGesture();
            }
            // Palette placement/collapse is target-local: Restart, context
            // rotation and disposal reset it (DG-22 Decision 7).
            this.palette.retargetContext(
                state.context?.targetContextId ?? null
            );
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
            if (
                generatedState.selectedViewId !==
                this.generatedState.selectedViewId
            ) {
                this.cancelPointerGesture();
            }
            this.generatedState = generatedState;
            this.render();
        });
        i18n.onChange(() => this.render(), this);
    }

    private renderAvailability(): void {
        this.availabilityDot.className = `ai-select-availability-dot availability-${this.availabilityStatus}`;
        this.availabilityLabel.text = i18n.t(
            `ai-select.availability.${this.availabilityStatus}`
        );
    }

    private render(): void {
        this.renderAvailability();
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        if (presentation.rgb) {
            this.image.src = `data:image/png;base64,${presentation.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.updateImageSurfaceRect(
                presentation.rgb.width,
                presentation.rgb.height
            );
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
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
                mask.status === 'failed'
                    ? i18n.t(
                          this.maskState.failureKind === 'maskArtifactInvalid'
                              ? 'ai-select.mask.artifact-invalid'
                              : 'ai-select.mask.failed'
                      )
                    : mask.proposalStatus === 'unavailable'
                      ? i18n.t('ai-select.proposal.unavailable')
                      : mask.proposalStatus === 'ambiguous'
                        ? i18n.t('ai-select.proposal.ambiguous')
                        : mask.proposalStatus === 'selected' &&
                            this.maskState.editingMask === null
                          ? i18n.t('ai-select.proposal.selected')
                          : i18n.t(`ai-select.mask.${mask.status}`);
        }
        const technicalMessage =
            mask.status === 'failed' ? mask.errorMessage : undefined;
        this.technicalDetails.hidden =
            technicalMessage === undefined || technicalMessage.length === 0;
        this.technicalDetailsBody.textContent = technicalMessage ?? '';
        this.confirmMaskButton.hidden = !mask.showConfirm;
        this.retryMaskButton.hidden = !mask.showRetry;
        this.confirmMaskButton.enabled =
            mask.showConfirm && !this.confirmation.locked;
        this.retryMaskButton.enabled =
            mask.showRetry && !this.confirmation.locked;
        this.renderPromptStatus(presentation);
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

    /**
     * Why a Prompt tool cannot run, or null when it is usable. Paint/Erase
     * are local Editing Mask operations and stay usable without the model
     * service; inference tools gate on Prompt Adapter capabilities.
     */
    private toolUnavailableReason(tool: PaletteTool): string | null {
        if (tool === 'paint' || tool === 'erase') {
            return null;
        }
        const capabilities = this.maskState.promptCapabilities;
        return capabilities === null
            ? i18n.t('ai-select.prompt.capabilities-unavailable')
            : promptToolCapabilityReason(tool, capabilities);
    }

    private renderTools(): void {
        const ready =
            getAnchorDockPresentation(this.state, this.maskState).status ===
                'ready' && !this.confirmation.locked;
        const capabilities = this.maskState.promptCapabilities;
        const availability = new Map<PaletteTool, PaletteToolAvailability>();
        for (const tool of PALETTE_TOOLS) {
            const reason = this.toolUnavailableReason(tool);
            availability.set(tool, {
                enabled: ready && reason === null,
                reason
            });
        }
        if (ready && availability.get(this.activeTool)?.enabled !== true) {
            this.activeTool =
                capabilities?.positivePoints === true
                    ? 'positive-point'
                    : 'paint';
        }
        this.palette.render({
            visible: ready,
            activeTool: this.activeTool,
            availability,
            canUndoPrompt: ready && this.maskState.canUndoPrompt,
            canRedoPrompt: ready && this.maskState.canRedoPrompt,
            canClearPrompts:
                ready &&
                this.maskState.promptState !== null &&
                (this.maskState.promptState.points.length > 0 ||
                    this.maskState.promptState.boxes.length > 0)
        });
        const proposalIds =
            this.maskState.proposalDecision?.alternativeProposalIds ?? [];
        const previousSelection = this.proposalSelect.value;
        this.proposalSelect.replaceChildren(
            ...proposalIds.map((proposalId, index) => {
                const proposal = this.maskState.proposalSet?.proposals.find(
                    (candidate) => candidate.proposalId === proposalId
                );
                const option = document.createElement('option');
                option.value = proposalId;
                option.text = `${i18n.t('ai-select.proposal.option')} ${i18n.formatInteger(index + 1)} · ${i18n.formatInteger(Math.round((proposal?.rankingFeatures.areaFraction ?? 0) * 100))}% · ${i18n.formatInteger(proposal?.rankingFeatures.connectedComponentCount ?? 0)} ${i18n.t('ai-select.proposal.components')}`;
                return option;
            })
        );
        const preferredProposalId = proposalIds.includes(previousSelection)
            ? previousSelection
            : (this.maskState.acceptedProposalId ??
              this.maskState.proposalDecision?.selectedProposalId ??
              proposalIds[0] ??
              '');
        this.proposalSelect.value = preferredProposalId;
        const proposal = this.maskState.proposalSet?.proposals.find(
            (candidate) => candidate.proposalId === preferredProposalId
        );
        this.proposalSelect.hidden = proposalIds.length === 0;
        this.acceptProposalButton.hidden =
            proposal === undefined ||
            proposal.proposalId === this.maskState.acceptedProposalId;
        this.acceptProposalButton.enabled =
            ready && !this.acceptProposalButton.hidden;
        this.image.style.cursor = cursorForTool(this.activeTool);
        const maskUndo = i18n.t('ai-select.mask.undo');
        const maskRedo = i18n.t('ai-select.mask.redo');
        this.setAccessibleLabel(this.undoMaskButton, maskUndo);
        this.setAccessibleLabel(this.redoMaskButton, maskRedo);
    }

    private renderPromptStatus(presentation: AnchorDockPresentation): void {
        const prompt = presentation.mask;
        if (prompt.promptCount === 0) {
            this.promptStatus.hidden = true;
            return;
        }
        const summary = [
            `${i18n.t('ai-select.prompt.summary-positive-points')} ${i18n.formatInteger(prompt.positivePointCount)}`,
            `${i18n.t('ai-select.prompt.summary-negative-points')} ${i18n.formatInteger(prompt.negativePointCount)}`,
            `${i18n.t('ai-select.prompt.summary-boxes')} ${i18n.formatInteger(prompt.boxCount)}`,
            `${i18n.t('ai-select.prompt.summary-revision')} ${i18n.formatInteger(prompt.promptRevision)}`
        ].join(' · ');
        // Mask-quality claims live on the previewed candidate's Review record
        // (the simplified 07A decision carries no ranking reason codes). The
        // candidate choice control is authoritative for which candidate the
        // user is previewing; fall back to the decision's default preview.
        const chosenProposalId = this.maskState.proposalSet?.proposals.some(
            (candidate) => candidate.proposalId === this.proposalSelect.value
        )
            ? this.proposalSelect.value
            : undefined;
        const previewedProposalId =
            chosenProposalId ??
            this.maskState.acceptedProposalId ??
            this.maskState.proposalDecision?.selectedProposalId ??
            this.maskState.proposalDecision?.alternativeProposalIds[0];
        const previewedProposal = this.maskState.proposalSet?.proposals.find(
            (candidate) => candidate.proposalId === previewedProposalId
        );
        const reasons = (previewedProposal?.review.reasons ?? []).map(
            (reason) => i18n.t(`ai-select.review.reason.${reason}`)
        );
        if (this.maskState.proposalSet?.diagnostics?.refinementFallback) {
            reasons.push(i18n.t('ai-select.proposal.refinement-fallback'));
        }
        this.promptStatus.text = [summary, ...reasons]
            .filter((entry) => entry.length > 0)
            .join(' · ');
        this.promptStatus.hidden = false;
    }

    private setAccessibleLabel(button: Button, label: string): void {
        button.dom.title = label;
        button.dom.setAttribute('aria-label', label);
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

    /**
     * Dock-focus-scoped palette keys (DG-22 Decision 4 and 8). These never
     * reach the global ShortcutManager (it only fires for document.body
     * targets), and they never steal input from text-entry controls, native
     * button activation, or modals that own focus.
     */
    private handleDockKeydown(event: KeyboardEvent): void {
        this.routeEditingKeys(event);
        if (event.defaultPrevented) {
            return;
        }
        // Escape closes the Brush Size popover first.
        if (event.key === 'Escape' && this.palette.popoverOpen) {
            event.preventDefault();
            event.stopPropagation();
            this.palette.closeBrushPopover();
            this.palette.focusActiveTool();
            return;
        }
        const target = event.target as HTMLElement | null;
        const tag = target?.tagName;
        if (
            tag === 'INPUT' ||
            tag === 'TEXTAREA' ||
            tag === 'SELECT' ||
            target?.isContentEditable === true
        ) {
            return;
        }
        if (event.ctrlKey || event.metaKey || event.altKey) {
            return;
        }
        if (event.key === ' ') {
            // Buttons keep native Space activation; everywhere else in the
            // Dock, hold Space hides the palette until keyup/blur.
            if (tag === 'BUTTON' || tag === 'A') {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            if (!event.repeat) {
                this.setSpaceHeld(true);
            }
            return;
        }
        if (event.repeat) {
            return;
        }
        const tool = paletteToolForShortcutKey(event.key);
        if (tool === null) {
            return;
        }
        const ready =
            getAnchorDockPresentation(this.state, this.maskState).status ===
                'ready' && !this.confirmation.locked;
        if (!ready || this.toolUnavailableReason(tool) !== null) {
            return;
        }
        event.preventDefault();
        this.cancelPointerGesture();
        this.activeTool = tool;
        this.renderTools();
    }

    private setSpaceHeld(held: boolean): void {
        if (this.spaceHeld === held) {
            return;
        }
        this.spaceHeld = held;
        this.palette.setTransientHidden(held);
    }

    private renderMaskOverlay(presentation: AnchorDockPresentation): void {
        const selectedProposal = this.maskState.proposalSet?.proposals.find(
            (candidate) => candidate.proposalId === this.proposalSelect.value
        );
        const proposal =
            selectedProposal?.proposalId !== this.maskState.acceptedProposalId
                ? selectedProposal
                : undefined;
        const annotation =
            proposal === undefined
                ? (this.maskState.editingMask ?? this.maskState.stableMask)
                : null;
        const artifact = annotation?.artifact ?? proposal?.mask;
        const rgb = presentation.rgb;
        if (
            presentation.status !== 'ready' ||
            rgb === undefined ||
            (artifact !== undefined &&
                (artifact.width !== rgb.width ||
                    artifact.height !== rgb.height))
        ) {
            this.overlay.hidden = true;
            return;
        }
        const { width, height } = rgb;
        const bits =
            artifact === undefined ? null : decodeMaskArtifact(artifact);
        const pixels = new Uint8ClampedArray(width * height * 4);
        const editing =
            this.maskState.editingMask !== null || proposal !== undefined;
        for (let index = 0; index < width * height; index += 1) {
            if (
                bits === null ||
                (bits[index >> 3] & (1 << (index % 8))) === 0
            ) {
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
        this.renderPendingPixelStroke(context);
        this.renderBoxPrompts(context);
        this.renderPointMarkers(context);
        this.positionOverlay();
        this.overlay.hidden =
            artifact === undefined &&
            (this.maskState.promptState?.points.length ?? 0) === 0 &&
            (this.maskState.promptState?.boxes.length ?? 0) === 0 &&
            this.pixelStroke.previewSamples.length === 0;
    }

    private renderBoxPrompts(context: CanvasRenderingContext2D): void {
        for (const box of this.maskState.promptState?.boxes ?? []) {
            const include = box.polarity === 'include';
            context.save();
            context.lineWidth = 3;
            context.strokeStyle = include ? '#20c878' : '#f05b66';
            context.setLineDash(include ? [] : [7, 5]);
            context.strokeRect(
                box.x0Px,
                box.y0Px,
                box.x1Px - box.x0Px,
                box.y1Px - box.y0Px
            );
            context.restore();
        }
    }

    private renderPointMarkers(context: CanvasRenderingContext2D): void {
        for (const point of this.maskState.promptState?.points ?? []) {
            const include = point.polarity === 'include';
            context.save();
            context.lineWidth = 3;
            context.strokeStyle = include ? '#20c878' : '#f05b66';
            context.fillStyle = 'rgba(0, 0, 0, 0.7)';
            context.beginPath();
            context.arc(point.xPx, point.yPx, 7, 0, Math.PI * 2);
            context.fill();
            context.stroke();
            context.beginPath();
            if (include) {
                context.moveTo(point.xPx - 4, point.yPx);
                context.lineTo(point.xPx + 4, point.yPx);
                context.moveTo(point.xPx, point.yPx - 4);
                context.lineTo(point.xPx, point.yPx + 4);
            } else {
                context.moveTo(point.xPx - 4, point.yPx - 4);
                context.lineTo(point.xPx + 4, point.yPx + 4);
                context.moveTo(point.xPx + 4, point.yPx - 4);
                context.lineTo(point.xPx - 4, point.yPx + 4);
            }
            context.stroke();
            context.restore();
        }
    }

    private renderPendingPixelStroke(context: CanvasRenderingContext2D): void {
        const samples = this.pixelStroke.previewSamples;
        if (samples.length === 0) {
            return;
        }
        context.save();
        context.lineCap = 'round';
        context.lineJoin = 'round';
        context.lineWidth = this.brushRadius() * 2;
        context.strokeStyle =
            this.activeTool === 'erase'
                ? 'rgba(80, 200, 255, 0.75)'
                : 'rgba(255, 140, 32, 0.75)';
        context.beginPath();
        context.moveTo(samples[0].xPx, samples[0].yPx);
        for (const sample of samples.slice(1)) {
            context.lineTo(sample.xPx, sample.yPx);
        }
        context.stroke();
        context.restore();
    }

    /** Align the overlay with the object-fit: contain painted image area. */
    private positionOverlay(): void {
        this.overlay.style.inset = '0';
        this.overlay.style.width = '100%';
        this.overlay.style.height = '100%';
    }

    private updateImageSurfaceRect(
        imageWidth = this.image.naturalWidth,
        imageHeight = this.image.naturalHeight
    ): void {
        const fitted = fitImageRect(
            this.imageViewport.clientWidth,
            this.imageViewport.clientHeight,
            imageWidth,
            imageHeight
        );
        if (fitted === null) {
            return;
        }
        this.imageSurface.style.left = `${fitted.left}px`;
        this.imageSurface.style.top = `${fitted.top}px`;
        this.imageSurface.style.width = `${fitted.width}px`;
        this.imageSurface.style.height = `${fitted.height}px`;
        // Dock/image resize reclamps the palette without changing the tool.
        this.palette.setSurfaceSize(fitted.width, fitted.height);
    }

    private toImagePixel(event: PointerEvent): ImagePixel | null {
        const rect = this.imageSurface.getBoundingClientRect();
        return mapClientPointToImagePixel(
            event.clientX,
            event.clientY,
            {
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height
            },
            this.image.naturalWidth,
            this.image.naturalHeight
        );
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
        this.image.setPointerCapture(event.pointerId);
        this.updatePaletteGestureDim(event);
        const action = pointerActionForTool(this.activeTool);
        if (action === 'pixel-edit') {
            this.pixelStroke.begin(pixel);
            this.renderCurrentMaskOverlay();
        } else if (action === 'box') {
            this.updateBoxPreview(pixel, pixel);
        }
    }

    private continueStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        this.updatePaletteGestureDim(event);
        if (pointerActionForTool(this.activeTool) === 'pixel-edit') {
            const samples = event.getCoalescedEvents?.() ?? [event];
            for (const sampleEvent of samples) {
                const sample = this.toImagePixel(sampleEvent);
                if (sample !== null) {
                    this.pixelStroke.append(sample);
                    this.lastStrokePixel = sample;
                }
            }
            this.renderCurrentMaskOverlay();
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
        if (action === 'box' && this.gestureStartPixel !== null) {
            this.updateBoxPreview(this.gestureStartPixel, pixel);
        }
    }

    private endStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        this.palette.setGestureDimmed(false);
        const moved =
            Math.abs(event.clientX - this.dragStart.x) +
            Math.abs(event.clientY - this.dragStart.y);
        const startPixel = this.gestureStartPixel;
        const action = pointerActionForTool(this.activeTool);
        if (action === 'pixel-edit') {
            const pixel = this.toImagePixel(event);
            if (pixel !== null) {
                this.pixelStroke.append(pixel);
            }
            const samples = this.pixelStroke.commit();
            this.resetPointerGesture();
            if (samples === null) {
                return;
            }
            try {
                this.mask.applyBrushGesture({
                    samples,
                    radiusPx: this.brushRadius(),
                    mode: this.activeTool === 'erase' ? 'erase' : 'add'
                });
            } catch (error) {
                console.error(error);
            }
            return;
        }
        this.dragStart = null;
        this.gestureStartPixel = null;
        this.lastStrokePixel = null;
        this.boxPreview.hidden = true;
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
                    y1Px: pixel.yPx
                })
                .catch((error) => console.error(error));
        }
    }

    private brushRadius(): number {
        return this.palette.brushSize;
    }

    /**
     * DG-22 Decision 5 non-relocating occlusion assist: while a captured
     * image gesture passes near the palette, temporarily dim it. This never
     * moves the palette and never touches image coordinates, PromptState,
     * Mask pixels, or either history.
     */
    private updatePaletteGestureDim(event: PointerEvent): void {
        const rect = this.palette.dom.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            this.palette.setGestureDimmed(false);
            return;
        }
        const margin = PALETTE_GESTURE_DIM_MARGIN_PX;
        const near =
            event.clientX >= rect.left - margin &&
            event.clientX <= rect.right + margin &&
            event.clientY >= rect.top - margin &&
            event.clientY <= rect.bottom + margin;
        this.palette.setGestureDimmed(near);
    }

    private cancelPointerGesture(): void {
        this.pixelStroke.cancel();
        this.resetPointerGesture();
        this.palette.setGestureDimmed(false);
        this.renderCurrentMaskOverlay();
    }

    private resetPointerGesture(): void {
        this.dragStart = null;
        this.gestureStartPixel = null;
        this.lastStrokePixel = null;
        this.boxPreview.hidden = true;
    }

    private renderCurrentMaskOverlay(): void {
        this.renderMaskOverlay(
            getAnchorDockPresentation(this.state, this.maskState)
        );
    }

    private updateBoxPreview(start: ImagePixel, current: ImagePixel): void {
        const rect = this.imageSurface.getBoundingClientRect();
        if (
            rect.width === 0 ||
            rect.height === 0 ||
            this.image.naturalWidth === 0 ||
            this.image.naturalHeight === 0
        ) {
            this.boxPreview.hidden = true;
            return;
        }
        const leftPx =
            (Math.min(start.xPx, current.xPx) / this.image.naturalWidth) *
            rect.width;
        const topPx =
            (Math.min(start.yPx, current.yPx) / this.image.naturalHeight) *
            rect.height;
        const widthPx =
            (Math.abs(start.xPx - current.xPx) / this.image.naturalWidth) *
            rect.width;
        const heightPx =
            (Math.abs(start.yPx - current.yPx) / this.image.naturalHeight) *
            rect.height;
        this.boxPreview.style.left = `${leftPx}px`;
        this.boxPreview.style.top = `${topPx}px`;
        this.boxPreview.style.width = `${widthPx}px`;
        this.boxPreview.style.height = `${heightPx}px`;
        this.boxPreview.hidden = false;
    }
}
