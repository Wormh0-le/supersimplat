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
    getViewMaskPresentation,
    type AnchorDockMaskPresentation,
    type AnchorDockPresentation
} from '../ai-select/anchor-dock-presentation';
import type { AnchorRgbArtifact } from '../ai-select/anchor-render-service';
import {
    PointerStrokeBuffer,
    pointerActionForTool
} from '../ai-select/authoring-interaction';
import {
    type CandidatePublicationState,
    type CandidatePublicationStore
} from '../ai-select/candidate-publication';
import {
    type AISelectCandidateCorrectionController,
    type CandidateCorrectionState
} from '../ai-select/candidate-correction';
import {
    PALETTE_TOOLS,
    paletteToolForShortcutKey,
    type PaletteTool
} from '../ai-select/floating-palette';
import {
    filterGalleryViews,
    galleryCardPresentation,
    galleryViewRole,
    orderGalleryViews,
    type GalleryCardPresentation,
    type GalleryFilter
} from '../ai-select/gallery-presentation';
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
    type AISelectMaskAuthoring,
    type AISelectMaskController,
    type AISelectMaskState
} from '../ai-select/mask-controller';
import { selectInspectedMaskOverlaySource } from '../ai-select/mask-overlay-source';
import type { MaskAnnotationRegistry } from '../ai-select/mask-registry';
import { promptToolCapabilityReason } from '../ai-select/prompt-state';
import { createThumbnailCache } from '../ai-select/thumbnail-cache';
import type { AISelectUserViewMaskController } from '../ai-select/user-view-mask-controller';
import type {
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessStatus
} from '../selection-service-readiness';

export interface AISelectAnchorDockOptions<TCandidatePayload = unknown> {
    readonly onRetry: () => Promise<void>;
    readonly onReconnect: () => Promise<void>;
    readonly onOpenSettings: () => void;
    readonly onValidate: () => Promise<void>;
    readonly onConfirmAnchor: () => Promise<void>;
    readonly onAdjustAnchor: () => void;
    readonly generatedViews: AISelectGeneratedViewController;
    readonly candidatePublications: CandidatePublicationStore;
    readonly candidateCorrection: AISelectCandidateCorrectionController<TCandidatePayload>;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly userViewMasks: AISelectUserViewMaskController;
    readonly onInspectCamera: (viewId: string) => void;
    readonly readiness: SelectionServiceReadinessInterface;
}

interface GeneratedCardElements {
    readonly root: Container;
    readonly image: HTMLImageElement;
    readonly title: Label;
    readonly status: Label;
    readonly detail: Label;
    readonly retryButton: Button;
    readonly regeneratePromptButton: Button;
    readonly refreshMaskButton: Button;
    readonly confirmReviewButton: Button;
    readonly participationButton: Button;
    readonly inspectCameraButton: Button;
    readonly excludeViewButton: Button;
    rgbDigest?: string;
}

/**
 * The View whose Mask authoring surface currently owns the Dock's image:
 * the inspected Gallery AIView, or the Anchor when nothing is inspected.
 * Every RGB Ready View supports explicit Prompt/Mask correction.
 */
interface DockAuthoringTarget {
    readonly ops: AISelectMaskAuthoring;
    readonly maskState: AISelectMaskState;
    readonly locked: boolean;
    readonly ready: boolean;
    readonly rgb?: AnchorRgbArtifact;
}

const CLICK_TOLERANCE_PX = 4;
// DG-22 Decision 5 opacity assist proximity; unrelated to the snap threshold.
const PALETTE_GESTURE_DIM_MARGIN_PX = 24;
// Gallery cards are 184px wide; double for high-density displays.
const THUMBNAIL_MAX_WIDTH_PX = 368;
// Full-resolution RGB stays authoritative in the controller; cards keep only
// bounded downscaled thumbnails so 10–20+ Views stay resource-bounded.
const THUMBNAIL_CACHE_CAPACITY = 24;
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

/**
 * The shared Mask overlay palette: orange while the displayed Mask is an
 * unpublished Editing Mask, cyan for a Stable Mask. A null bitset yields a
 * fully transparent layer (RGB inspectable with no Mask).
 */
const maskOverlayPixels = (
    bits: Uint8Array | null,
    pixelCount: number,
    editing: boolean
): Uint8ClampedArray<ArrayBuffer> => {
    const pixels = new Uint8ClampedArray(new ArrayBuffer(pixelCount * 4));
    if (bits === null) {
        return pixels;
    }
    for (let index = 0; index < pixelCount; index += 1) {
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
    return pixels;
};

/**
 * Downscale one authoritative RGB PNG for card display. The full-resolution
 * artifact stays in controller state; the cache keeps only this bounded copy.
 */
const downscaleCardThumbnail = (
    pngBase64: string,
    maxWidth: number
): Promise<string> => {
    const source = `data:image/png;base64,${pngBase64}`;
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => {
            if (image.naturalWidth <= maxWidth) {
                resolve(source);
                return;
            }
            const scale = maxWidth / image.naturalWidth;
            const canvas = document.createElement('canvas');
            canvas.width = maxWidth;
            canvas.height = Math.max(
                1,
                Math.round(image.naturalHeight * scale)
            );
            const context = canvas.getContext('2d');
            if (context === null) {
                resolve(source);
                return;
            }
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            resolve(canvas.toDataURL('image/png'));
        };
        image.onerror = () => reject(new Error('thumbnail decode failed'));
        image.src = source;
    });
};

/** The first AI View Dock: authoritative RGB plus the Anchor Mask surface. */
export class AISelectAnchorDock<TCandidatePayload = unknown> extends Container {
    private readonly mask: AISelectMaskController;
    private readonly confirmation: AISelectAnchorConfirmationController;
    private readonly generatedViews: AISelectGeneratedViewController;
    private readonly maskRegistry: MaskAnnotationRegistry;
    private readonly userViewMasks: AISelectUserViewMaskController;
    private readonly onInspectCamera: (viewId: string) => void;
    private readonly status: Label;
    private readonly availabilityDot: HTMLSpanElement;
    private readonly availabilityLabel: Label;
    private availabilityStatus: SelectionServiceReadinessStatus;
    private readonly maskStatus: Label;
    private readonly promptStatus: Label;
    private readonly candidateStatus: Label;
    private readonly candidateActions: Container;
    private readonly fixCandidateButton: Button;
    private readonly updateCandidateButton: Button;
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
    private readonly restoreAutoButton: Button;
    private readonly anchorActions: Container;
    private readonly validateButton: Button;
    private readonly confirmAnchorButton: Button;
    private readonly adjustAnchorButton: Button;
    private readonly validationStatus: Label;
    private readonly gallery: Container;
    private readonly plannerLine: Container;
    private readonly plannerStatus: Label;
    private readonly plannerRetryButton: Button;
    private readonly plannerStopButton: Button;
    private readonly plannerMoreButton: Button;
    private readonly plannerRegenerateButton: Button;
    private readonly filterLine: Container;
    private readonly filterButtons: ReadonlyMap<GalleryFilter, Button>;
    private galleryFilter: GalleryFilter = 'all';
    private readonly galleryCards: Container;
    private readonly anchorCard: GeneratedCardElements;
    private readonly generatedCards = new Map<string, GeneratedCardElements>();
    private readonly thumbnails = createThumbnailCache({
        capacity: THUMBNAIL_CACHE_CAPACITY
    });
    private readonly thumbnailPending = new Set<string>();
    private state: AISelectAnchorState = { context: null, anchor: null };
    private maskState: AISelectMaskState;
    private confirmationState: AISelectAnchorConfirmationState;
    private generatedState: AISelectGeneratedViewState;
    private candidateState: CandidatePublicationState;
    private candidateCorrectionState: CandidateCorrectionState;
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
        options: AISelectAnchorDockOptions<TCandidatePayload>,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-anchor-dock'
        });
        this.mask = mask;
        this.confirmation = confirmation;
        this.generatedViews = options.generatedViews;
        this.candidateCorrectionState = options.candidateCorrection.state;
        this.maskRegistry = options.maskRegistry;
        this.userViewMasks = options.userViewMasks;
        this.onInspectCamera = options.onInspectCamera;
        this.maskState = mask.state;
        this.confirmationState = confirmation.state;
        this.generatedState = options.generatedViews.state;
        this.candidateState = options.candidatePublications.presentationState;
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
        this.candidateStatus = new Label({
            id: 'ai-select-anchor-dock-candidate-status',
            hidden: true
        });
        this.candidateActions = new Container({
            id: 'ai-select-candidate-actions',
            hidden: true
        });
        this.fixCandidateButton = new Button({
            id: 'ai-select-fix-candidate'
        });
        this.updateCandidateButton = new Button({
            id: 'ai-select-update-candidate'
        });
        i18n.bindText(
            this.fixCandidateButton,
            'ai-select.candidate.fix-result'
        );
        i18n.bindText(this.updateCandidateButton, 'ai-select.candidate.update');
        this.fixCandidateButton.on('click', () => {
            try {
                options.candidateCorrection.beginCorrection();
            } catch (error) {
                console.error(error);
            }
        });
        this.updateCandidateButton.on('click', () => {
            options.candidateCorrection
                .updateCandidate()
                .catch((error) => console.error(error));
        });
        this.candidateActions.append(this.fixCandidateButton);
        this.candidateActions.append(this.updateCandidateButton);
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
                this.renderAuthoringTools();
            },
            onHistoryUndo: (kind) => {
                try {
                    if (kind === 'mask') {
                        this.authoring()?.ops.undoMaskEdit();
                    } else {
                        this.authoring()?.ops.undoPromptEdit();
                    }
                } catch (error) {
                    console.error(error);
                }
            },
            onHistoryRedo: (kind) => {
                try {
                    if (kind === 'mask') {
                        this.authoring()?.ops.redoMaskEdit();
                    } else {
                        this.authoring()?.ops.redoPromptEdit();
                    }
                } catch (error) {
                    console.error(error);
                }
            },
            onHistoryClear: (kind) => {
                try {
                    if (kind === 'mask') {
                        this.authoring()?.ops.clearEditingMask();
                    } else {
                        this.authoring()?.ops.clearPrompts();
                    }
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
                this.authoring()?.ops.previewProposal(
                    this.proposalSelect.value
                );
            } catch (error) {
                console.error(error);
            }
            this.renderCurrentMaskOverlay();
        });
        i18n.bindText(this.acceptProposalButton, 'ai-select.proposal.accept');
        this.acceptProposalButton.on('click', () => {
            const authoring = this.authoring();
            const proposal = authoring?.maskState.proposalSet?.proposals.find(
                (candidate) =>
                    candidate.proposalId === this.proposalSelect.value
            );
            if (authoring === null || proposal === undefined) {
                return;
            }
            try {
                authoring.ops.acceptProposal(proposal.proposalId);
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
        this.restoreAutoButton = new Button({
            id: 'ai-select-anchor-dock-restore-auto'
        });
        i18n.bindText(this.confirmMaskButton, 'ai-select.mask.confirm');
        i18n.bindText(this.retryMaskButton, 'ai-select.mask.retry');
        i18n.bindText(this.restoreAutoButton, 'ai-select.mask.restore-auto');
        this.confirmMaskButton.on('click', () => {
            try {
                this.authoring()?.ops.confirmEditingMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.retryMaskButton.on('click', () => {
            this.authoring()
                ?.ops.retryMaskRequest()
                .catch((error) => console.error(error));
        });
        this.restoreAutoButton.on('click', () => {
            try {
                this.authoring()?.ops.restoreAutoMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.maskActions.append(this.confirmMaskButton);
        this.maskActions.append(this.retryMaskButton);
        this.maskActions.append(this.restoreAutoButton);

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
        this.plannerStopButton = new Button({
            id: 'ai-select-view-gallery-planner-stop'
        });
        i18n.bindText(this.plannerStopButton, 'ai-select.views.planner.stop');
        this.plannerStopButton.on('click', () => {
            try {
                this.generatedViews.stopGeneration();
            } catch (error) {
                console.error(error);
            }
        });
        this.plannerMoreButton = new Button({
            id: 'ai-select-view-gallery-planner-more'
        });
        i18n.bindText(this.plannerMoreButton, 'ai-select.views.planner.more');
        this.plannerMoreButton.on('click', () => {
            try {
                this.generatedViews.generateMoreViews();
            } catch (error) {
                console.error(error);
            }
        });
        this.plannerRegenerateButton = new Button({
            id: 'ai-select-view-gallery-planner-regenerate'
        });
        i18n.bindText(
            this.plannerRegenerateButton,
            'ai-select.views.planner.regenerate'
        );
        this.plannerRegenerateButton.on('click', () => {
            try {
                this.generatedViews.regenerateViews();
            } catch (error) {
                console.error(error);
            }
        });
        this.plannerLine.append(this.plannerStatus);
        this.plannerLine.append(this.plannerRetryButton);
        this.plannerLine.append(this.plannerStopButton);
        this.plannerLine.append(this.plannerMoreButton);
        this.plannerLine.append(this.plannerRegenerateButton);
        // Gallery filters are presentation-only: they choose which cards are
        // visible and never call into Prompt, Mask, Participation, Evidence,
        // or Candidate state.
        this.filterLine = new Container({
            id: 'ai-select-view-gallery-filters',
            hidden: true
        });
        const filterEntries: readonly GalleryFilter[] = [
            'all',
            'included',
            'excluded',
            'needs-review'
        ];
        const filterButtons = new Map<GalleryFilter, Button>();
        for (const filter of filterEntries) {
            const button = new Button({
                class: 'ai-select-view-gallery-filter'
            });
            i18n.bindText(button, `ai-select.views.filter.${filter}`);
            button.on('click', () => {
                this.galleryFilter = filter;
                this.renderGallery(
                    getAnchorDockPresentation(this.state, this.maskState)
                );
            });
            filterButtons.set(filter, button);
            this.filterLine.append(button);
        }
        this.filterButtons = filterButtons;
        this.galleryCards = new Container({
            id: 'ai-select-view-gallery-cards'
        });
        this.gallery.append(this.plannerLine);
        this.gallery.append(this.filterLine);
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
        information.append(this.candidateStatus);
        information.dom.appendChild(this.technicalDetails);
        information.dom.appendChild(this.proposalSelect);
        information.append(this.validationStatus);
        information.append(this.gallery);
        const primaryActions = new Container({
            id: 'ai-select-anchor-dock-primary-actions'
        });
        // Anchor confirmation stays first in the fixed action area so a
        // wrapped Mask action never pushes the next lifecycle step below the
        // dock's clipped edge.
        primaryActions.append(this.anchorActions);
        primaryActions.append(this.acceptProposalButton);
        primaryActions.append(this.maskActions);
        primaryActions.append(this.candidateActions);
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
        options.userViewMasks.subscribe(() => this.render());
        options.candidatePublications.subscribe((candidateState) => {
            this.candidateState = candidateState;
            this.renderCandidateStatus();
        });
        options.candidateCorrection.subscribe((correctionState) => {
            this.candidateCorrectionState = correctionState;
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

    /** The Gallery-selected Generated View under read-only inspection. */
    private inspectedGeneratedView(): GeneratedAIView | null {
        const selectedViewId = this.generatedState.selectedViewId;
        if (selectedViewId === null) {
            return null;
        }
        return (
            this.generatedState.views.find(
                (view) => view.viewId === selectedViewId
            ) ?? null
        );
    }

    private render(): void {
        this.renderAvailability();
        this.renderCandidateStatus();
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        const inspected = this.inspectedGeneratedView();
        if (inspected !== null) {
            const viewAuthoring = this.authoring();
            if (viewAuthoring !== null && viewAuthoring.ready) {
                this.renderViewMaskAuthoring(inspected);
            } else {
                this.renderInspection(inspected);
            }
            this.renderGallery(presentation);
            return;
        }
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

        this.renderMaskSurface(
            presentation.mask,
            this.maskState,
            presentation.status === 'ready',
            this.confirmation.locked
        );
        this.renderPromptStatus(presentation.mask, this.maskState);
        this.renderEditingActions();
        this.renderAuthoringTools();
        this.renderAnchorActions(presentation);
        this.renderCurrentMaskOverlay();
        this.renderGallery(presentation);
    }

    private renderCandidateStatus(): void {
        const { candidateState } = this;
        if (candidateState.status === 'empty') {
            this.candidateStatus.hidden = true;
            const hasIncludedStableView =
                this.maskState.stableMask !== null ||
                this.generatedState.views.some(
                    (view) =>
                        view.participation === 'included' &&
                        view.stableMaskDigest !== undefined
                );
            this.candidateActions.hidden = !hasIncludedStableView;
            this.fixCandidateButton.hidden = true;
            this.updateCandidateButton.hidden = !hasIncludedStableView;
            this.updateCandidateButton.enabled =
                this.candidateCorrectionState.status !== 'updating';
            return;
        }
        const status = i18n.t(
            candidateState.status === 'current'
                ? 'ai-select.candidate.current'
                : 'ai-select.candidate.stale'
        );
        const selected = i18n.formatInteger(
            candidateState.candidate.selectedStableGaussianIds.length
        );
        const uncertain = i18n.formatInteger(
            candidateState.uncertain.stableGaussianIds.length
        );
        this.candidateStatus.text = `${status} · ${i18n.t(
            'ai-select.candidate.selected'
        )} ${selected} · ${i18n.t(
            'ai-select.candidate.uncertain'
        )} ${uncertain} · ${i18n.t('ai-select.candidate.reference-only')}`;
        this.candidateStatus.hidden = false;
        const showFix =
            candidateState.status === 'current' &&
            this.candidateCorrectionState.mode === 'candidate';
        const showUpdate =
            candidateState.status === 'stale' ||
            this.candidateCorrectionState.mode === 'correcting';
        this.candidateActions.hidden = !showFix && !showUpdate;
        this.fixCandidateButton.hidden = !showFix;
        this.updateCandidateButton.hidden = !showUpdate;
        this.updateCandidateButton.enabled =
            this.candidateCorrectionState.status !== 'updating';
        if (this.candidateCorrectionState.status === 'failed') {
            this.candidateStatus.text += ` · ${i18n.t('ai-select.candidate.update-failed')}`;
        }
    }

    /**
     * The Mask surface shared by the Anchor and user-added Views: request
     * currency, draft/confirmed Mask currency, technical failure details, and
     * the Confirm/Retry affordances.
     */
    private renderMaskSurface(
        mask: AnchorDockMaskPresentation,
        maskState: AISelectMaskState,
        ready: boolean,
        locked: boolean
    ): void {
        if (mask.status === 'none' && !ready) {
            this.maskStatus.hidden = true;
        } else {
            this.maskStatus.hidden = false;
            this.maskStatus.text =
                mask.status === 'failed'
                    ? i18n.t(
                          maskState.failureKind === 'maskArtifactInvalid'
                              ? 'ai-select.mask.artifact-invalid'
                              : 'ai-select.mask.failed'
                      )
                    : mask.proposalStatus === 'unavailable'
                      ? i18n.t('ai-select.proposal.unavailable')
                      : mask.proposalStatus === 'ambiguous'
                        ? i18n.t('ai-select.proposal.ambiguous')
                        : mask.proposalStatus === 'selected' &&
                            maskState.editingMask === null
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
        this.confirmMaskButton.enabled = mask.showConfirm && !locked;
        this.retryMaskButton.enabled = mask.showRetry && !locked;
    }

    /**
     * The editable Gallery View surface: the same Prompt/candidate/Brush/
     * Confirm UI as the Anchor, bound to this View's exact Mask session.
     */
    private renderViewMaskAuthoring(view: GeneratedAIView): void {
        const authoring = this.authoring();
        if (authoring === null) {
            this.renderInspection(view);
            return;
        }
        if (view.rgb !== undefined) {
            this.image.src = `data:image/png;base64,${view.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.updateImageSurfaceRect(view.rgb.width, view.rgb.height);
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
        }
        this.status.text = i18n.t('ai-select.views.inspecting-editing');
        this.failureActions.hidden = true;
        this.anchorActions.hidden = true;
        this.validationStatus.hidden = true;
        const mask = getViewMaskPresentation(authoring.maskState);
        this.renderMaskSurface(
            mask,
            authoring.maskState,
            authoring.ready,
            authoring.locked
        );
        this.renderPromptStatus(mask, authoring.maskState);
        this.renderEditingActions();
        this.renderAuthoringTools();
        this.renderCurrentMaskOverlay();
    }

    /**
     * The Mask authoring target that currently owns the Dock's image surface:
     * an inspected Gallery View's session, or the Anchor when none is
     * inspected. Render-pending Views have no ready authoring surface.
     */
    private authoring(): DockAuthoringTarget | null {
        const inspected = this.inspectedGeneratedView();
        if (inspected !== null) {
            const session = this.userViewMasks.sessionFor(inspected.viewId);
            if (session === null) {
                return null;
            }
            return {
                ops: session,
                maskState: session.state,
                locked: false,
                ready: inspected.renderStatus === 'ready',
                ...(inspected.rgb === undefined ? {} : { rgb: inspected.rgb })
            };
        }
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        return {
            ops: this.mask,
            maskState: this.maskState,
            locked:
                this.confirmation.locked &&
                this.candidateCorrectionState.mode !== 'correcting',
            ready: presentation.status === 'ready',
            ...(presentation.rgb === undefined ? {} : { rgb: presentation.rgb })
        };
    }

    /** Read-only fallback when an inspected View has no authoring session. */
    private renderInspection(view: GeneratedAIView): void {
        if (view.rgb !== undefined) {
            this.image.src = `data:image/png;base64,${view.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.updateImageSurfaceRect(view.rgb.width, view.rgb.height);
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
        }
        const roleKey =
            galleryViewRole(view.source) === 'user-added'
                ? 'ai-select.views.role.user-added'
                : 'ai-select.views.generated';
        this.status.text = `${i18n.t(roleKey)} — ${i18n.t('ai-select.views.inspecting')}`;
        this.failureActions.hidden = true;
        this.maskStatus.hidden = true;
        this.promptStatus.hidden = true;
        this.technicalDetails.hidden = true;
        this.proposalSelect.hidden = true;
        this.acceptProposalButton.hidden = true;
        this.maskActions.hidden = true;
        this.anchorActions.hidden = true;
        this.validationStatus.hidden = true;
        this.boxPreview.hidden = true;
        this.image.style.cursor = 'default';
        const availability = new Map<PaletteTool, PaletteToolAvailability>();
        for (const tool of PALETTE_TOOLS) {
            availability.set(tool, { enabled: false, reason: null });
        }
        this.palette.render({
            visible: false,
            activeTool: this.activeTool,
            availability,
            historyKind: 'prompt',
            canUndoHistory: false,
            canRedoHistory: false,
            canClearHistory: false
        });
        this.renderInspectedMaskOverlay(view);
    }

    /**
     * Display currency, not publication authority: the unpublished Editing
     * Mask (edit color) is the draft under correction, while the Stable Mask
     * (confirmed color) remains the only Evidence input. Mirrors the Anchor
     * surface's editing-first display rule.
     */
    private renderInspectedMaskOverlay(view: GeneratedAIView): void {
        const rgb = view.rgb;
        if (rgb === undefined) {
            this.overlay.hidden = true;
            return;
        }
        const masks = this.maskRegistry.viewState(view.viewId, rgb.digest);
        const annotation = masks.editingMask ?? masks.stableMask;
        const artifact = annotation?.artifact;
        if (
            artifact === undefined ||
            artifact.width !== rgb.width ||
            artifact.height !== rgb.height
        ) {
            this.overlay.hidden = true;
            return;
        }
        const { width, height } = rgb;
        const pixels = maskOverlayPixels(
            decodeMaskArtifact(artifact),
            width * height,
            masks.editingMask !== null
        );
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
        // Raw technical messages stay available but visually subordinate, so
        // a transport/OOM string can never replace a semantic status line.
        const detail = new Label({ class: 'ai-select-view-card-detail' });
        detail.hidden = true;
        const retryButton = new Button({
            class: 'ai-select-view-card-retry',
            hidden: true
        });
        const regeneratePromptButton = new Button({
            class: 'ai-select-view-card-regenerate-prompt',
            hidden: true
        });
        const refreshMaskButton = new Button({
            class: 'ai-select-view-card-refresh-mask',
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
        const inspectCameraButton = new Button({
            class: 'ai-select-view-card-inspect-camera',
            hidden: true
        });
        const excludeViewButton = new Button({
            class: 'ai-select-view-card-exclude',
            hidden: true
        });
        i18n.bindText(retryButton, 'ai-select.views.retry-render');
        i18n.bindText(regeneratePromptButton, 'ai-select.views.retry-prompt');
        i18n.bindText(confirmReviewButton, 'ai-select.review.confirm-as-is');
        i18n.bindText(inspectCameraButton, 'ai-select.views.inspect-camera');
        i18n.bindText(excludeViewButton, 'ai-select.participation.exclude');
        if (onRetry !== null) {
            retryButton.on('click', (event: Event) => {
                event.stopPropagation();
                onRetry();
            });
        }
        regeneratePromptButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.regenerateGeneratedViewPrompt(viewId);
            }
        });
        refreshMaskButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.refreshGeneratedViewMask(viewId);
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
        inspectCameraButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                this.onInspectCamera(viewId);
            }
        });
        excludeViewButton.on('click', (event: Event) => {
            event.stopPropagation();
            const viewId = root.dom.dataset.viewId;
            if (viewId !== undefined) {
                try {
                    this.generatedViews.setViewParticipation(
                        viewId,
                        'excluded'
                    );
                } catch (error) {
                    console.error(error);
                }
            }
        });
        root.dom.appendChild(image);
        root.append(title);
        root.append(status);
        root.append(detail);
        const actions = new Container({
            class: 'ai-select-view-card-actions'
        });
        actions.append(confirmReviewButton);
        actions.append(participationButton);
        actions.append(inspectCameraButton);
        actions.append(regeneratePromptButton);
        actions.append(refreshMaskButton);
        actions.append(retryButton);
        actions.append(excludeViewButton);
        root.append(actions);
        root.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );
        root.dom.addEventListener('click', () => onClick());
        return {
            root,
            image,
            title,
            status,
            detail,
            retryButton,
            regeneratePromptButton,
            refreshMaskButton,
            confirmReviewButton,
            participationButton,
            inspectCameraButton,
            excludeViewButton
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
            this.plannerStopButton.hidden = true;
            this.plannerMoreButton.hidden = true;
            this.plannerRegenerateButton.hidden = true;
        } else if (generated.plannerStatus === 'failed') {
            this.plannerLine.hidden = false;
            this.plannerStatus.text =
                generated.plannerErrorMessage ??
                i18n.t('ai-select.views.planner.failed');
            this.plannerRetryButton.hidden = false;
            this.plannerStopButton.hidden = true;
            this.plannerMoreButton.hidden = true;
            this.plannerRegenerateButton.hidden = true;
        } else if (generated.plannerStatus === 'active') {
            this.plannerLine.hidden = false;
            this.plannerStatus.text =
                generated.plannerErrorMessage ??
                (generated.generationStopped
                    ? i18n.t('ai-select.views.planner.stopped')
                    : i18n.t('ai-select.views.planner.active'));
            this.plannerRetryButton.hidden = true;
            this.plannerStopButton.hidden = false;
            this.plannerStopButton.enabled = !generated.generationStopped;
            this.plannerMoreButton.hidden = false;
            this.plannerRegenerateButton.hidden = false;
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
        this.anchorCard.detail.hidden = true;
        this.anchorCard.retryButton.hidden = true;
        this.anchorCard.regeneratePromptButton.hidden = true;
        this.anchorCard.refreshMaskButton.hidden = true;
        this.anchorCard.confirmReviewButton.hidden = true;
        this.anchorCard.participationButton.hidden = true;
        this.anchorCard.inspectCameraButton.hidden = true;
        this.anchorCard.excludeViewButton.hidden = true;
        if (presentation.rgb !== undefined) {
            this.applyCardThumbnail(
                this.anchorCard,
                presentation.rgb.digest,
                presentation.rgb.pngBase64
            );
        } else {
            this.anchorCard.rgbDigest = undefined;
            this.anchorCard.image.hidden = true;
        }
        this.anchorCard.root.dom.classList.toggle(
            'selected',
            this.generatedState.selectedViewId === null
        );

        // Stable order (Anchor, generated local Views in creation order, then
        // user-added Views) with per-role title ordinals; the filter only
        // changes card visibility.
        const ordered = orderGalleryViews(generated.views);
        const visible = new Set(
            filterGalleryViews(ordered, this.galleryFilter).map(
                (view) => view.viewId
            )
        );
        this.filterLine.hidden = ordered.length === 0;
        for (const [filter, button] of this.filterButtons) {
            button.dom.classList.toggle(
                'active',
                filter === this.galleryFilter
            );
        }
        const ordinals = new Map<string, number>();
        let generatedOrdinal = 0;
        let userAddedOrdinal = 0;
        for (const view of ordered) {
            const ordinal =
                galleryViewRole(view.source) === 'user-added'
                    ? (userAddedOrdinal += 1)
                    : (generatedOrdinal += 1);
            ordinals.set(view.viewId, ordinal);
        }
        const seen = new Set<string>();
        for (const view of ordered) {
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
            this.updateGeneratedCard(
                card,
                galleryCardPresentation(view, ordinals.get(view.viewId) ?? 0),
                view
            );
            card.root.hidden = !visible.has(view.viewId);
        }
        for (const [viewId, card] of this.generatedCards) {
            if (!seen.has(viewId)) {
                card.root.destroy();
                this.generatedCards.delete(viewId);
            }
        }
    }

    private updateGeneratedCard(
        card: GeneratedCardElements,
        presentation: GalleryCardPresentation,
        view: GeneratedAIView
    ): void {
        const titleKey =
            presentation.role === 'user-added'
                ? 'ai-select.views.role.user-added'
                : 'ai-select.views.generated';
        card.title.text = `${i18n.t(titleKey)} ${i18n.formatInteger(presentation.titleOrdinal)}`;
        card.root.dom.dataset.viewId = presentation.viewId;
        const statusLines: string[] = [];
        const detailLines: string[] = [];
        for (const line of presentation.lines) {
            if (line.kind === 'detail') {
                detailLines.push(line.text);
            } else {
                statusLines.push(
                    line.key.startsWith('ai-select.review.action.')
                        ? `• ${i18n.t(line.key)}`
                        : i18n.t(line.key)
                );
            }
        }
        card.status.text = statusLines.join('\n');
        card.detail.text = detailLines.join('\n');
        card.detail.hidden = detailLines.length === 0;

        card.retryButton.hidden = !presentation.actions.retryRender;
        card.regeneratePromptButton.hidden =
            !presentation.actions.regeneratePrompt;
        card.refreshMaskButton.hidden = !presentation.actions.refreshMask;
        if (presentation.actions.refreshMask) {
            card.refreshMaskButton.text = i18n.t(
                view.maskStatus === 'failed' ||
                    view.maskStatus === 'unavailable'
                    ? 'ai-select.views.retry-mask'
                    : 'ai-select.views.refresh-mask'
            );
        }
        card.confirmReviewButton.hidden = !presentation.actions.confirmAsIs;
        card.participationButton.hidden =
            presentation.actions.participationToggle === null;
        if (presentation.actions.participationToggle !== null) {
            card.participationButton.text = i18n.t(
                `ai-select.participation.${presentation.actions.participationToggle}`
            );
        }
        card.inspectCameraButton.hidden = !presentation.actions.inspectCamera;
        card.excludeViewButton.hidden = !presentation.actions.excludeView;
        if (view.rgb !== undefined) {
            this.applyCardThumbnail(card, view.rgb.digest, view.rgb.pngBase64);
        } else {
            card.rgbDigest = undefined;
            card.image.hidden = true;
        }
        card.root.dom.classList.toggle('selected', presentation.selected);
    }

    /**
     * Cards display bounded thumbnails keyed by authoritative RGB digest; the
     * full-resolution artifact stays in controller state and is never realized
     * as a card image — on a cache miss the card waits for its downscaled
     * thumbnail so a large Gallery stays inside the resource bound. Unchanged
     * digests keep their thumbnail, so Generate More never visually stales
     * prior completed Views.
     */
    private applyCardThumbnail(
        card: GeneratedCardElements,
        digest: string,
        pngBase64: string
    ): void {
        if (card.rgbDigest === digest) {
            return;
        }
        card.rgbDigest = digest;
        const cached = this.thumbnails.get(digest);
        if (cached !== undefined) {
            card.image.src = cached;
            card.image.hidden = false;
            return;
        }
        card.image.hidden = true;
        if (this.thumbnailPending.has(digest)) {
            return;
        }
        this.thumbnailPending.add(digest);
        downscaleCardThumbnail(pngBase64, THUMBNAIL_MAX_WIDTH_PX)
            .then((thumbnail) => {
                this.thumbnailPending.delete(digest);
                this.thumbnails.set(digest, thumbnail);
                for (const current of this.allCards()) {
                    if (current.rgbDigest === digest) {
                        current.image.src = thumbnail;
                        current.image.hidden = false;
                    }
                }
            })
            .catch((error) => {
                this.thumbnailPending.delete(digest);
                console.error(error);
                // Correctness over the resource bound: a decode failure falls
                // back to the authoritative RGB rather than a blank card.
                const source = `data:image/png;base64,${pngBase64}`;
                for (const current of this.allCards()) {
                    if (current.rgbDigest === digest) {
                        current.image.src = source;
                        current.image.hidden = false;
                    }
                }
            });
    }

    private allCards(): GeneratedCardElements[] {
        return [this.anchorCard, ...this.generatedCards.values()];
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

    private regenerateGeneratedViewPrompt(viewId: string): void {
        try {
            this.generatedViews.regenerateViewPrompt(viewId);
        } catch (error) {
            console.error(error);
        }
    }

    private refreshGeneratedViewMask(viewId: string): void {
        try {
            this.generatedViews.refreshViewMask(viewId);
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

    private renderEditingActions(): void {
        const authoring = this.authoring();
        if (authoring === null) {
            this.maskActions.hidden = true;
            return;
        }
        const editingReady = authoring.ready && !authoring.locked;
        const maskState = authoring.maskState;
        this.restoreAutoButton.hidden = !editingReady;
        this.restoreAutoButton.enabled =
            editingReady && maskState.canRestoreAuto;
        const mask = getViewMaskPresentation(maskState);
        this.maskActions.hidden =
            !mask.showConfirm && !mask.showRetry && !editingReady;
    }

    /**
     * Why a Prompt tool cannot run, or null when it is usable. Paint/Erase
     * are local Editing Mask operations and stay usable without the model
     * service; inference tools gate on Prompt Adapter capabilities.
     */
    private toolUnavailableReason(
        tool: PaletteTool,
        maskState: AISelectMaskState
    ): string | null {
        if (tool === 'paint' || tool === 'erase') {
            return null;
        }
        const capabilities = maskState.promptCapabilities;
        return capabilities === null
            ? i18n.t('ai-select.prompt.capabilities-unavailable')
            : promptToolCapabilityReason(tool, capabilities);
    }

    private renderAuthoringTools(): void {
        const authoring = this.authoring();
        if (authoring === null) {
            const availability = new Map<
                PaletteTool,
                PaletteToolAvailability
            >();
            for (const tool of PALETTE_TOOLS) {
                availability.set(tool, { enabled: false, reason: null });
            }
            this.palette.render({
                visible: false,
                activeTool: this.activeTool,
                availability,
                historyKind: 'prompt',
                canUndoHistory: false,
                canRedoHistory: false,
                canClearHistory: false
            });
            this.proposalSelect.hidden = true;
            this.acceptProposalButton.hidden = true;
            this.image.style.cursor = 'default';
            return;
        }
        const maskState = authoring.maskState;
        const ready = authoring.ready && !authoring.locked;
        const capabilities = maskState.promptCapabilities;
        const availability = new Map<PaletteTool, PaletteToolAvailability>();
        for (const tool of PALETTE_TOOLS) {
            const reason = this.toolUnavailableReason(tool, maskState);
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
        const editingMask =
            this.activeTool === 'paint' || this.activeTool === 'erase';
        this.palette.render({
            visible: ready,
            activeTool: this.activeTool,
            availability,
            historyKind: editingMask ? 'mask' : 'prompt',
            canUndoHistory:
                ready &&
                (editingMask ? maskState.canUndo : maskState.canUndoPrompt),
            canRedoHistory:
                ready &&
                (editingMask ? maskState.canRedo : maskState.canRedoPrompt),
            canClearHistory: editingMask
                ? ready && maskState.editingMask !== null
                : ready &&
                  maskState.promptState !== null &&
                  (maskState.promptState.points.length > 0 ||
                      maskState.promptState.boxes.length > 0)
        });
        const proposalIds =
            maskState.proposalDecision?.alternativeProposalIds ?? [];
        this.proposalSelect.replaceChildren(
            ...proposalIds.map((proposalId, index) => {
                const proposal = maskState.proposalSet?.proposals.find(
                    (candidate) => candidate.proposalId === proposalId
                );
                const option = document.createElement('option');
                option.value = proposalId;
                option.text = `${i18n.t('ai-select.proposal.option')} ${i18n.formatInteger(index + 1)} · ${i18n.formatInteger(Math.round((proposal?.rankingFeatures.areaFraction ?? 0) * 100))}% · ${i18n.formatInteger(proposal?.rankingFeatures.connectedComponentCount ?? 0)} ${i18n.t('ai-select.proposal.components')}`;
                return option;
            })
        );
        const preferredProposalId = proposalIds.includes(
            maskState.previewedProposalId ?? ''
        )
            ? (maskState.previewedProposalId ?? '')
            : (maskState.acceptedProposalId ??
              maskState.proposalDecision?.selectedProposalId ??
              proposalIds[0] ??
              '');
        this.proposalSelect.value = preferredProposalId;
        const proposal = maskState.proposalSet?.proposals.find(
            (candidate) => candidate.proposalId === preferredProposalId
        );
        this.proposalSelect.hidden = proposalIds.length === 0;
        this.acceptProposalButton.hidden =
            proposal === undefined ||
            proposal.proposalId === maskState.acceptedProposalId;
        this.acceptProposalButton.enabled =
            ready && !this.acceptProposalButton.hidden;
        this.image.style.cursor = cursorForTool(this.activeTool);
    }

    private renderPromptStatus(
        prompt: AnchorDockMaskPresentation,
        maskState: AISelectMaskState
    ): void {
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
        const previewedProposalId =
            maskState.previewedProposalId ??
            maskState.acceptedProposalId ??
            maskState.proposalDecision?.selectedProposalId ??
            maskState.proposalDecision?.alternativeProposalIds[0];
        const previewedProposal = maskState.proposalSet?.proposals.find(
            (candidate) => candidate.proposalId === previewedProposalId
        );
        const reasons = (previewedProposal?.review.reasons ?? []).map(
            (reason) => i18n.t(`ai-select.review.reason.${reason}`)
        );
        if (maskState.proposalSet?.diagnostics?.refinementFallback) {
            reasons.push(i18n.t('ai-select.proposal.refinement-fallback'));
        }
        this.promptStatus.text = [summary, ...reasons]
            .filter((entry) => entry.length > 0)
            .join(' · ');
        this.promptStatus.hidden = false;
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
        const authoring = this.authoring();
        if (authoring === null) {
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
                ? authoring.maskState.canRedoPrompt
                : authoring.maskState.canUndoPrompt
            : redo
              ? authoring.maskState.canRedo
              : authoring.maskState.canUndo;
        if (!available) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        try {
            if (promptMode) {
                if (redo) {
                    authoring.ops.redoPromptEdit();
                } else {
                    authoring.ops.undoPromptEdit();
                }
            } else if (redo) {
                authoring.ops.redoMaskEdit();
            } else {
                authoring.ops.undoMaskEdit();
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
        // A planner-owned Generated View inspection surface is read-only: no
        // mask-local Undo/Redo routing, no palette shortcuts, no tool
        // switching. A user-added View's surface authors its own session.
        if (
            this.inspectedGeneratedView() !== null &&
            this.authoring() === null
        ) {
            return;
        }
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
        const authoring = this.authoring();
        if (
            authoring === null ||
            !authoring.ready ||
            authoring.locked ||
            this.toolUnavailableReason(tool, authoring.maskState) !== null
        ) {
            return;
        }
        event.preventDefault();
        this.cancelPointerGesture();
        this.activeTool = tool;
        this.renderAuthoringTools();
    }

    private setSpaceHeld(held: boolean): void {
        if (this.spaceHeld === held) {
            return;
        }
        this.spaceHeld = held;
        this.palette.setTransientHidden(held);
    }

    private renderMaskOverlay(
        maskState: AISelectMaskState,
        rgb: AnchorRgbArtifact | undefined,
        ready: boolean
    ): void {
        const selectedProposal = maskState.proposalSet?.proposals.find(
            (candidate) =>
                candidate.proposalId === maskState.previewedProposalId
        );
        const proposal =
            selectedProposal?.proposalId !== maskState.acceptedProposalId
                ? selectedProposal
                : undefined;
        const annotation =
            proposal === undefined
                ? (maskState.editingMask ?? maskState.stableMask)
                : null;
        const artifact = annotation?.artifact ?? proposal?.mask;
        if (
            !ready ||
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
        const pixels = maskOverlayPixels(
            bits,
            width * height,
            maskState.editingMask !== null || proposal !== undefined
        );
        this.overlay.width = width;
        this.overlay.height = height;
        const context = this.overlay.getContext('2d');
        if (context === null) {
            this.overlay.hidden = true;
            return;
        }
        context.putImageData(new ImageData(pixels, width, height), 0, 0);
        this.renderPendingPixelStroke(context);
        this.renderBoxPrompts(context, maskState);
        this.renderPointMarkers(context, maskState);
        this.positionOverlay();
        this.overlay.hidden =
            artifact === undefined &&
            (maskState.promptState?.points.length ?? 0) === 0 &&
            (maskState.promptState?.boxes.length ?? 0) === 0 &&
            this.pixelStroke.previewSamples.length === 0;
    }

    private renderBoxPrompts(
        context: CanvasRenderingContext2D,
        maskState: AISelectMaskState
    ): void {
        for (const box of maskState.promptState?.boxes ?? []) {
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

    private renderPointMarkers(
        context: CanvasRenderingContext2D,
        maskState: AISelectMaskState
    ): void {
        for (const point of maskState.promptState?.points ?? []) {
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
        const authoring = this.authoring();
        if (
            event.button !== 0 ||
            authoring === null ||
            authoring.locked ||
            !authoring.ready
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
        const authoring = this.authoring();
        if (authoring === null) {
            this.cancelPointerGesture();
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
                authoring.ops.applyBrushGesture({
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
            authoring.ops
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
            authoring.ops
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
        const inspected = this.inspectedGeneratedView();
        if (inspected !== null) {
            const source = selectInspectedMaskOverlaySource(
                inspected.source,
                this.authoring()
            );
            if (source.kind === 'registry') {
                this.renderInspectedMaskOverlay(inspected);
                return;
            }
            this.renderMaskOverlay(
                source.authoring.maskState,
                inspected.rgb,
                source.authoring.ready
            );
            return;
        }
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        this.renderMaskOverlay(
            this.maskState,
            presentation.rgb,
            presentation.status === 'ready'
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
