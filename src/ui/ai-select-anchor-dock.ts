import { Button, Container, Label } from '@playcanvas/pcui';

import {
    AISelectFloatingPalette,
    type PaletteToolAvailability
} from './ai-select-floating-palette';
import { i18n } from './localization';
import confirmSvg from './svg/ai-select-confirm.svg';
import reLiftSvg from './svg/ai-select-re-lift.svg';
import arrowSvg from './svg/arrow.svg';
import cameraResetSvg from './svg/camera-reset.svg';
import collapseSvg from './svg/collapse.svg';
import undoSvg from './svg/edit-undo.svg';
import hiddenSvg from './svg/hidden.svg';
import pinSvg from './svg/pin.svg';
import redoSvg from './svg/redo.svg';
import type { Tooltips } from './tooltips';
import {
    AI_VIEW_DOCK_DEFAULT_PREFERENCES,
    AI_VIEW_INSPECTOR_MAXIMUM_WIDTH_PX,
    AI_VIEW_INSPECTOR_MINIMUM_WIDTH_PX,
    AI_VIEW_NAVIGATOR_MAXIMUM_WIDTH_PX,
    AI_VIEW_NAVIGATOR_MINIMUM_WIDTH_PX,
    type AIViewDockPreferences,
    type AIViewImageZoomState,
    parseAIViewDockPreferences,
    resizeAIViewDockSidebar,
    resolveAIViewDockColumns,
    resolveAIViewImageRect,
    serializeAIViewDockPreferences,
    setAIViewDockSidebarExpanded,
    resolveAIViewWorkAreaWidth
} from '../ai-select/ai-view-dock-layout';
import type {
    AISelectAnchorAdjustmentController,
    AISelectAnchorAdjustmentState
} from '../ai-select/anchor-adjustment';
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
    type AISelectCandidateCorrectionController,
    type CandidateCorrectionState
} from '../ai-select/candidate-correction';
import type { CandidatePresentationCoordinator } from '../ai-select/candidate-presentation';
import {
    PALETTE_TOOLS,
    paletteToolForShortcutKey,
    type PaletteTool
} from '../ai-select/floating-palette';
import {
    filterGalleryViews,
    galleryCardPresentation,
    galleryViewRole,
    NAVIGATOR_ANCHOR_ID,
    nextRadioChoice,
    navigatorBadgePresentation,
    orderGalleryViews,
    projectNavigatorViews,
    type GalleryCardPresentation,
    type GalleryFilter,
    type GallerySort,
    type NavigatorBadge
} from '../ai-select/gallery-presentation';
import type {
    AISelectGeneratedViewController,
    AISelectGeneratedViewState,
    GeneratedAIView
} from '../ai-select/generated-view-controller';
import {
    mapClientPointToImagePixel,
    type ImagePixel
} from '../ai-select/image-viewport';
import type {
    LiftReadinessState,
    LiftReadinessStore
} from '../ai-select/lift-readiness';
import { decodeMaskArtifact } from '../ai-select/mask-annotation';
import {
    type AISelectMaskAuthoring,
    type AISelectMaskController,
    type AISelectMaskState
} from '../ai-select/mask-controller';
import { selectInspectedMaskOverlaySource } from '../ai-select/mask-overlay-source';
import {
    hasSemanticEditingMaskChange,
    type MaskAnnotationRegistry
} from '../ai-select/mask-registry';
import { promptToolCapabilityReason } from '../ai-select/prompt-state';
import { createThumbnailCache } from '../ai-select/thumbnail-cache';
import type { AISelectUserViewMaskController } from '../ai-select/user-view-mask-controller';
import { viewInspectorPresentation } from '../ai-select/view-inspector-presentation';
import {
    mapWorkAreaActions,
    type WorkAreaActionPresentation
} from '../ai-select/work-area-presentation';
import type {
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessStatus
} from '../selection-service-readiness';
export interface AISelectAnchorDockOptions<TCandidatePayload = unknown> {
    readonly onConfirmAnchor: () => Promise<void>;
    readonly onConfirmAnchorAdjustment: () => Promise<void>;
    readonly anchorAdjustment: AISelectAnchorAdjustmentController;
    readonly generatedViews: AISelectGeneratedViewController;
    readonly candidateCorrection: AISelectCandidateCorrectionController<TCandidatePayload>;
    readonly candidatePresentation: CandidatePresentationCoordinator;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly userViewMasks: AISelectUserViewMaskController;
    readonly onInspectCamera: (viewId: string | null) => void;
    readonly readiness: SelectionServiceReadinessInterface;
    readonly liftReadiness: LiftReadinessStore;
    readonly tooltips: Tooltips;
    readonly onUndoSceneChange: () => Promise<void>;
    readonly canUndoSceneChange: () => boolean;
}

interface GeneratedCardElements {
    readonly root: Container;
    readonly image: HTMLImageElement;
    readonly anchorPin: HTMLSpanElement;
    readonly badge: HTMLSpanElement;
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
// Navigator thumbnails fill a 220px-default strip; retain dense-display detail.
const THUMBNAIL_MAX_WIDTH_PX = 512;
// Full-resolution RGB stays authoritative in the controller; cards keep only
// bounded downscaled thumbnails so 10–20+ Views stay resource-bounded.
const THUMBNAIL_CACHE_CAPACITY = 24;
type DockAuthoringTool = PaletteTool;

const createSvg = (svgString: string): Element => {
    const decoded = decodeURIComponent(
        svgString.substring('data:image/svg+xml,'.length)
    );
    return new DOMParser().parseFromString(decoded, 'image/svg+xml')
        .documentElement;
};

const setSvgButtonLabel = (button: Button, label: string): void => {
    button.dom.title = label;
    button.dom.setAttribute('aria-label', label);
};

const setSvgButtonIcon = (
    button: Button,
    svg: string,
    label: string,
    iconClass = 'ai-select-icon-action-glyph'
): void => {
    const icon = createSvg(svg);
    icon.classList.add(iconClass);
    icon.setAttribute('aria-hidden', 'true');
    icon.setAttribute('focusable', 'false');
    button.dom.replaceChildren(icon);
    setSvgButtonLabel(button, label);
};

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
    private readonly anchorAdjustment: AISelectAnchorAdjustmentController;
    private readonly generatedViews: AISelectGeneratedViewController;
    private readonly maskRegistry: MaskAnnotationRegistry;
    private readonly userViewMasks: AISelectUserViewMaskController;
    private readonly onInspectCamera: (viewId: string | null) => void;
    private readonly status: Label;
    private readonly suspendedSurface: Container;
    private readonly suspendedMessage: Label;
    private readonly undoSceneChangeButton: Button;
    private readonly canUndoSceneChange: () => boolean;
    private undoSceneChangePending = false;
    private undoSceneChangeFailed = false;
    private suspendedTargetContextId: string | null = null;
    private availabilityStatus: SelectionServiceReadinessStatus;
    private readonly maskStatus: Label;
    private readonly promptStatus: Label;
    private liftReadinessState: LiftReadinessState;
    private readonly workAreaControls: Container;
    private readonly reLiftButton: Button;
    private readonly imageViewport: HTMLDivElement;
    private readonly workCanvasRow: Container;
    private readonly imageSurface: HTMLDivElement;
    private readonly image: HTMLImageElement;
    private readonly overlay: HTMLCanvasElement;
    private readonly technicalDetails: HTMLDetailsElement;
    private readonly technicalDetailsBody: HTMLPreElement;
    private readonly canvasStateActions: Container;
    private readonly palette: AISelectFloatingPalette;
    private readonly boxPreview: HTMLDivElement;
    private readonly validationStatus: Label;
    private readonly selectedViewPrimaryButton: Button;
    private selectedViewPrimaryAction: 'next-review' | null = null;
    private readonly gallery: Container;
    private readonly plannerLine: Container;
    private readonly plannerStatus: Label;
    private readonly plannerRetryButton: Button;
    private readonly filterLine: Container;
    private readonly filterTrigger: Button;
    private readonly filterPopover: Container;
    private readonly filterButtons: ReadonlyMap<GalleryFilter, Button>;
    private readonly sortButtons: ReadonlyMap<GallerySort, Button>;
    private galleryFilter: GalleryFilter = 'all';
    private gallerySort: GallerySort = 'creation';
    private readonly galleryCards: Container;
    private readonly galleryEmptyState: Label;
    private readonly anchorCard: GeneratedCardElements;
    private readonly selectedViewAssessment: Label;
    private readonly selectedViewParticipation: Button;
    private readonly selectedViewIssues: Label;
    private readonly inspectorInformation: Container;
    private readonly generatedCards = new Map<string, GeneratedCardElements>();
    private readonly thumbnails = createThumbnailCache({
        capacity: THUMBNAIL_CACHE_CAPACITY
    });
    private readonly thumbnailPending = new Set<string>();
    private state: AISelectAnchorState = { context: null, anchor: null };
    private maskState: AISelectMaskState;
    private confirmationState: AISelectAnchorConfirmationState;
    private anchorAdjustmentState: AISelectAnchorAdjustmentState;
    private generatedState: AISelectGeneratedViewState;
    private candidateCorrectionState: CandidateCorrectionState;
    private dragStart: { x: number; y: number } | null = null;
    private gestureStartPixel: ImagePixel | null = null;
    private lastStrokePixel: ImagePixel | null = null;
    private readonly pixelStroke = new PointerStrokeBuffer();
    private activeTool: DockAuthoringTool = 'positive-point';
    private spaceHeld = false;
    private imageZoom: AIViewImageZoomState = { mode: 'auto' };
    private filteredSelectionEmpty = false;
    private pendingGalleryScrollId: string | null = null;

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
        this.anchorAdjustment = options.anchorAdjustment;
        this.generatedViews = options.generatedViews;
        this.candidateCorrectionState = options.candidateCorrection.state;
        this.liftReadinessState = options.liftReadiness.presentationState;
        this.maskRegistry = options.maskRegistry;
        this.userViewMasks = options.userViewMasks;
        this.onInspectCamera = options.onInspectCamera;
        this.canUndoSceneChange = options.canUndoSceneChange;
        this.maskState = mask.state;
        this.confirmationState = confirmation.state;
        this.anchorAdjustmentState = options.anchorAdjustment.state;
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

        this.status = new Label({ id: 'ai-select-work-canvas-state' });
        this.status.dom.setAttribute('role', 'status');
        this.status.dom.setAttribute('aria-live', 'polite');
        this.availabilityStatus = options.readiness.state.status;
        options.readiness.subscribe((readinessState) => {
            this.availabilityStatus = readinessState.status;
            this.render();
        });

        this.suspendedSurface = new Container({
            id: 'ai-select-suspended-surface',
            hidden: true
        });
        this.suspendedSurface.dom.setAttribute('role', 'status');
        this.suspendedMessage = new Label({
            id: 'ai-select-suspended-message'
        });
        this.undoSceneChangeButton = new Button({
            id: 'ai-select-undo-scene-change'
        });
        const renderUndoSceneChangeLabel = (): void => {
            const label = i18n.t('ai-select.suspended.undo-scene-change');
            const icon = createSvg(undoSvg);
            icon.classList.add('ai-select-undo-scene-change-icon');
            icon.setAttribute('aria-hidden', 'true');
            const text = document.createElement('span');
            text.textContent = label;
            this.undoSceneChangeButton.dom.replaceChildren(icon, text);
            setSvgButtonLabel(this.undoSceneChangeButton, label);
        };
        this.undoSceneChangeButton.on('click', () => {
            if (this.undoSceneChangePending) {
                return;
            }
            this.undoSceneChangeFailed = false;
            this.undoSceneChangePending = true;
            this.renderSuspensionSurface();
            options
                .onUndoSceneChange()
                .catch((error) => {
                    console.error(error);
                    this.undoSceneChangeFailed = true;
                })
                .finally(() => {
                    this.undoSceneChangePending = false;
                    this.renderSuspensionSurface();
                });
        });
        this.suspendedSurface.append(this.suspendedMessage);
        this.suspendedSurface.append(this.undoSceneChangeButton);
        renderUndoSceneChangeLabel();

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
        this.imageSurface.addEventListener(
            'wheel',
            (event) => {
                if (this.image.hidden) {
                    return;
                }
                const factor = Math.exp(-event.deltaY * 0.0015);
                const width = Math.max(
                    40,
                    Math.min(
                        this.image.naturalWidth * 8,
                        this.imageSurface.clientWidth * factor
                    )
                );
                this.imageZoom = { mode: 'manual', width };
                this.updateImageSurfaceRect();
                event.preventDefault();
                event.stopPropagation();
            },
            { passive: false }
        );
        const resizeImageSurface = () => this.updateImageSurfaceRect();
        const imageResizeObserver = new ResizeObserver(resizeImageSurface);
        imageResizeObserver.observe(this.imageViewport);
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
        this.technicalDetails.open = false;

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
            onConfirmMask: () => {
                this.runPaletteConfirmAction(
                    options.onConfirmAnchor,
                    options.onConfirmAnchorAdjustment
                );
            },
            onContextAction: () => {
                const action = this.workAreaActions().palette.context;
                try {
                    if (action === 'enter-correction') {
                        const authoring = this.authoring();
                        options.candidateCorrection.beginCorrection();
                        try {
                            authoring?.ops.beginCorrectionFromStable();
                        } catch (error) {
                            options.candidateCorrection.backToCandidate();
                            throw error;
                        }
                    } else if (action === 'back-to-candidate') {
                        options.candidateCorrection.backToCandidate();
                    }
                } catch (error) {
                    console.error(error);
                }
            },
            onRestoreAutoMask: () => {
                try {
                    this.authoring()?.ops.restoreAutoMask();
                } catch (error) {
                    console.error(error);
                }
            },
            onBrushSizeChange: () => this.renderCurrentMaskOverlay()
        });
        this.imageSurface.appendChild(this.palette.dom);

        this.validationStatus = new Label({
            id: 'ai-select-anchor-dock-validation-status',
            hidden: true
        });
        this.selectedViewPrimaryButton = new Button({
            id: 'ai-select-selected-view-primary',
            hidden: true
        });
        this.selectedViewPrimaryButton.on('click', () =>
            this.runSelectedViewPrimaryAction()
        );
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
        const retryPlanningLabel = i18n.t('ai-select.views.planner.retry');
        setSvgButtonIcon(this.plannerRetryButton, redoSvg, retryPlanningLabel);
        this.plannerRetryButton.on('click', () => {
            try {
                this.generatedViews.retryPlanning();
            } catch (error) {
                console.error(error);
            }
        });
        this.plannerLine.append(this.plannerStatus);
        this.plannerLine.append(this.plannerRetryButton);
        // Filter and sort are one presentation-only control. The radio
        // choices never call Prompt, Mask, Participation, Evidence, or
        // Candidate operations.
        this.filterLine = new Container({
            id: 'ai-select-view-gallery-filters',
            hidden: true
        });
        this.filterTrigger = new Button({
            id: 'ai-select-view-gallery-filter-trigger'
        });
        this.filterTrigger.dom.setAttribute('aria-haspopup', 'dialog');
        this.filterTrigger.dom.setAttribute('aria-expanded', 'false');
        this.filterPopover = new Container({
            id: 'ai-select-view-gallery-filter-popover',
            hidden: true
        });
        this.filterPopover.dom.setAttribute('role', 'dialog');
        this.filterPopover.dom.setAttribute(
            'aria-label',
            i18n.t('ai-select.views.filter-sort')
        );
        const filterEntries: readonly GalleryFilter[] = ['all', 'needs-review'];
        const filterButtons = new Map<GalleryFilter, Button>();
        const filterGroup = new Container({
            class: 'ai-select-view-gallery-choice-group'
        });
        filterGroup.dom.setAttribute('role', 'radiogroup');
        filterGroup.dom.setAttribute(
            'aria-label',
            i18n.t('ai-select.views.filter-group')
        );
        for (const filter of filterEntries) {
            const button = new Button({
                class: 'ai-select-view-gallery-choice'
            });
            button.dom.setAttribute('role', 'radio');
            button.on('click', () => {
                this.galleryFilter = filter;
                this.render();
            });
            filterButtons.set(filter, button);
            filterGroup.append(button);
        }
        this.filterButtons = filterButtons;
        const sortEntries: readonly GallerySort[] = [
            'creation',
            'newest',
            'needs-review'
        ];
        const sortButtons = new Map<GallerySort, Button>();
        const sortGroup = new Container({
            class: 'ai-select-view-gallery-choice-group'
        });
        sortGroup.dom.setAttribute('role', 'radiogroup');
        sortGroup.dom.setAttribute(
            'aria-label',
            i18n.t('ai-select.views.sort-group')
        );
        for (const sort of sortEntries) {
            const button = new Button({
                class: 'ai-select-view-gallery-choice'
            });
            button.dom.setAttribute('role', 'radio');
            button.on('click', () => {
                this.gallerySort = sort;
                this.render();
            });
            sortButtons.set(sort, button);
            sortGroup.append(button);
        }
        this.sortButtons = sortButtons;
        const bindRadioNavigation = <T extends string>(
            entries: readonly T[],
            buttons: ReadonlyMap<T, Button>,
            current: () => T,
            select: (entry: T) => void
        ): void => {
            for (const entry of entries) {
                buttons.get(entry)?.dom.addEventListener('keydown', (event) => {
                    const next = nextRadioChoice(entries, current(), event.key);
                    if (next === null) {
                        return;
                    }
                    select(next);
                    buttons.get(next)?.dom.focus();
                    event.preventDefault();
                    event.stopPropagation();
                });
            }
        };
        bindRadioNavigation(
            filterEntries,
            filterButtons,
            () => this.galleryFilter,
            (filter) => {
                this.galleryFilter = filter;
                this.render();
            }
        );
        bindRadioNavigation(
            sortEntries,
            sortButtons,
            () => this.gallerySort,
            (sort) => {
                this.gallerySort = sort;
                this.render();
            }
        );
        this.filterPopover.append(filterGroup);
        this.filterPopover.append(sortGroup);
        this.filterTrigger.on('click', () =>
            this.setFilterPopoverOpen(this.filterPopover.hidden)
        );
        this.filterLine.append(this.filterTrigger);
        this.filterLine.append(this.filterPopover);
        window.addEventListener(
            'pointerdown',
            (event) => {
                if (
                    !this.filterPopover.hidden &&
                    event.target instanceof Node &&
                    !this.filterLine.dom.contains(event.target)
                ) {
                    this.setFilterPopoverOpen(false, true);
                }
            },
            true
        );
        window.addEventListener(
            'keydown',
            (event) => {
                if (event.key === 'Escape' && !this.filterPopover.hidden) {
                    this.setFilterPopoverOpen(false, true);
                    event.preventDefault();
                    event.stopPropagation();
                }
            },
            true
        );
        this.galleryCards = new Container({
            id: 'ai-select-view-gallery-cards'
        });
        this.galleryCards.dom.setAttribute('role', 'listbox');
        this.galleryEmptyState = new Label({
            id: 'ai-select-view-gallery-empty',
            hidden: true
        });
        this.galleryEmptyState.dom.setAttribute('role', 'status');
        this.gallery.append(this.plannerLine);
        this.gallery.append(this.filterLine);
        this.gallery.append(this.galleryEmptyState);
        this.gallery.append(this.galleryCards);
        this.anchorCard = this.createCard(() => this.selectGeneratedView(null));
        this.galleryCards.append(this.anchorCard.root);

        const mainRow = new Container({ id: 'ai-select-anchor-dock-main' });
        const navigator = new Container({
            id: 'ai-select-view-navigator'
        });
        const navigatorHeader = new Container({
            id: 'ai-select-view-navigator-header'
        });
        const navigatorTitle = new Label({
            id: 'ai-select-view-navigator-title'
        });
        i18n.bindText(navigatorTitle, 'ai-select.dock.navigator');
        const navigatorCollapse = new Button({
            id: 'ai-select-navigator-collapse',
            class: 'ai-select-sidebar-collapse'
        });
        const navigatorReveal = new Button({
            id: 'ai-select-navigator-reveal',
            class: 'ai-select-sidebar-reveal'
        });
        setSvgButtonIcon(
            navigatorCollapse,
            collapseSvg,
            i18n.t('ai-select.dock.hide-navigator'),
            'ai-select-sidebar-control-icon'
        );
        setSvgButtonIcon(
            navigatorReveal,
            arrowSvg,
            i18n.t('ai-select.dock.show-navigator'),
            'ai-select-sidebar-control-icon'
        );
        navigatorCollapse.dom.setAttribute(
            'aria-controls',
            'ai-select-view-navigator'
        );
        navigatorReveal.dom.setAttribute(
            'aria-controls',
            'ai-select-view-navigator'
        );
        navigatorHeader.append(navigatorTitle);
        navigatorHeader.append(navigatorCollapse);
        const workArea = new Container({
            id: 'ai-select-view-work-area'
        });
        const inspector = new Container({
            id: 'ai-select-view-inspector'
        });
        const inspectorHeader = new Container({
            id: 'ai-select-view-inspector-header'
        });
        const inspectorTitle = new Label({
            id: 'ai-select-view-inspector-title'
        });
        i18n.bindText(inspectorTitle, 'ai-select.dock.inspector');
        const inspectorCollapse = new Button({
            id: 'ai-select-inspector-collapse',
            class: 'ai-select-sidebar-collapse'
        });
        const inspectorReveal = new Button({
            id: 'ai-select-inspector-reveal',
            class: 'ai-select-sidebar-reveal'
        });
        setSvgButtonIcon(
            inspectorCollapse,
            collapseSvg,
            i18n.t('ai-select.dock.hide-inspector'),
            'ai-select-sidebar-control-icon'
        );
        setSvgButtonIcon(
            inspectorReveal,
            arrowSvg,
            i18n.t('ai-select.dock.show-inspector'),
            'ai-select-sidebar-control-icon'
        );
        inspectorCollapse.dom.setAttribute(
            'aria-controls',
            'ai-select-view-inspector'
        );
        inspectorReveal.dom.setAttribute(
            'aria-controls',
            'ai-select-view-inspector'
        );
        inspectorHeader.append(inspectorCollapse);
        inspectorHeader.append(inspectorTitle);
        this.inspectorInformation = new Container({
            id: 'ai-select-anchor-dock-information'
        });
        this.selectedViewAssessment = new Label({
            id: 'ai-select-selected-view-assessment'
        });
        this.selectedViewParticipation = new Button({
            id: 'ai-select-selected-view-participation'
        });
        this.selectedViewParticipation.on('click', () => {
            const selected = this.inspectedGeneratedView();
            if (selected !== null) {
                this.toggleGeneratedViewParticipation(selected.viewId);
            }
        });
        this.selectedViewIssues = new Label({
            id: 'ai-select-selected-view-issues',
            hidden: true
        });
        const createInspectorGroup = (
            id: string,
            titleKey: string
        ): Container => {
            const group = new Container({
                id,
                class: 'ai-select-inspector-group'
            });
            const heading = new Label({
                class: 'ai-select-inspector-heading'
            });
            i18n.bindText(heading, titleKey);
            group.append(heading);
            return group;
        };
        const assessmentGroup = createInspectorGroup(
            'ai-select-inspector-assessment-group',
            'ai-select.dock.assessment'
        );
        assessmentGroup.append(this.selectedViewAssessment);
        assessmentGroup.append(this.selectedViewParticipation);
        assessmentGroup.append(this.selectedViewIssues);
        const maskGroup = createInspectorGroup(
            'ai-select-inspector-mask-group',
            'ai-select.dock.prompt-mask'
        );
        maskGroup.append(this.promptStatus);
        maskGroup.append(this.maskStatus);
        maskGroup.append(this.validationStatus);
        const technicalGroup = new Container({
            id: 'ai-select-inspector-technical-group',
            class: 'ai-select-inspector-group'
        });
        technicalGroup.dom.appendChild(this.technicalDetails);
        this.inspectorInformation.append(assessmentGroup);
        this.inspectorInformation.append(maskGroup);
        this.inspectorInformation.append(technicalGroup);
        this.canvasStateActions = new Container({
            id: 'ai-select-work-canvas-actions',
            hidden: true
        });
        this.canvasStateActions.append(this.selectedViewPrimaryButton);
        navigator.append(navigatorHeader);
        navigator.append(this.gallery);
        this.workCanvasRow = new Container({
            id: 'ai-select-view-work-canvas-row'
        });
        this.workCanvasRow.dom.appendChild(this.imageViewport);
        this.workCanvasRow.append(this.status);
        this.workCanvasRow.append(this.canvasStateActions);
        imageResizeObserver.observe(this.workCanvasRow.dom);
        const resetFitButton = new Button({
            id: 'ai-select-view-reset-fit'
        });
        const resetFitLabel = i18n.t('ai-select.dock.reset-fit');
        setSvgButtonIcon(resetFitButton, cameraResetSvg, resetFitLabel);
        resetFitButton.on('click', () => {
            this.imageZoom = { mode: 'auto' };
            this.updateImageSurfaceRect();
        });
        this.reLiftButton = new Button({
            id: 'ai-select-work-area-re-lift'
        });
        setSvgButtonIcon(
            this.reLiftButton,
            reLiftSvg,
            i18n.t('ai-select.candidate.update'),
            'ai-select-re-lift-glyph'
        );
        this.reLiftButton.on('click', () => {
            options.candidateCorrection
                .updateCandidate()
                .catch((error) => console.error(error));
        });
        options.tooltips.register(
            this.reLiftButton,
            () => this.reLiftDescription(),
            'bottom'
        );
        this.workAreaControls = new Container({
            id: 'ai-select-work-area-controls'
        });
        this.workAreaControls.append(resetFitButton);
        this.workAreaControls.append(this.reLiftButton);
        workArea.append(navigatorReveal);
        workArea.append(inspectorReveal);
        workArea.append(this.workAreaControls);
        workArea.append(this.workCanvasRow);
        inspector.append(inspectorHeader);
        inspector.append(this.inspectorInformation);
        const navigatorResizeHandle = document.createElement('div');
        navigatorResizeHandle.id = 'ai-select-navigator-resize-handle';
        navigatorResizeHandle.className = 'ai-select-sidebar-resize-handle';
        navigatorResizeHandle.setAttribute('role', 'separator');
        navigatorResizeHandle.setAttribute('aria-orientation', 'vertical');
        navigatorResizeHandle.setAttribute(
            'aria-labelledby',
            'ai-select-view-navigator-title'
        );
        navigatorResizeHandle.tabIndex = 0;
        const inspectorResizeHandle = document.createElement('div');
        inspectorResizeHandle.id = 'ai-select-inspector-resize-handle';
        inspectorResizeHandle.className = 'ai-select-sidebar-resize-handle';
        inspectorResizeHandle.setAttribute('role', 'separator');
        inspectorResizeHandle.setAttribute('aria-orientation', 'vertical');
        inspectorResizeHandle.setAttribute(
            'aria-labelledby',
            'ai-select-view-inspector-title'
        );
        inspectorResizeHandle.tabIndex = 0;
        mainRow.append(navigator);
        mainRow.dom.appendChild(navigatorResizeHandle);
        mainRow.append(workArea);
        mainRow.dom.appendChild(inspectorResizeHandle);
        mainRow.append(inspector);
        this.append(this.suspendedSurface);
        this.append(mainRow);

        const dockPreferenceKey = 'supersplat.ai-select.view-dock-layout';
        let dockPreferences: AIViewDockPreferences;
        try {
            dockPreferences = parseAIViewDockPreferences(
                localStorage.getItem(dockPreferenceKey)
            );
        } catch {
            dockPreferences = AI_VIEW_DOCK_DEFAULT_PREFERENCES;
        }
        const writeDockPreferences = (): void => {
            try {
                localStorage.setItem(
                    dockPreferenceKey,
                    serializeAIViewDockPreferences(dockPreferences)
                );
            } catch {
                // Blocked device storage must not block the editor Dock.
            }
        };
        const renderColumns = (): void => {
            const width = mainRow.dom.clientWidth;
            const columns = resolveAIViewDockColumns(width, {
                navigator: dockPreferences.navigatorExpanded,
                inspector: dockPreferences.inspectorExpanded
            });
            const expandable = resolveAIViewDockColumns(width, {
                navigator: true,
                inspector: true
            });
            navigator.hidden = !columns.navigator;
            inspector.hidden = !columns.inspector;
            navigatorResizeHandle.hidden = !columns.navigator;
            inspectorResizeHandle.hidden = !columns.inspector;
            navigator.style.width = `${dockPreferences.navigatorWidth}px`;
            inspector.style.width = `${dockPreferences.inspectorWidth}px`;
            navigatorResizeHandle.setAttribute(
                'aria-valuenow',
                dockPreferences.navigatorWidth.toString()
            );
            inspectorResizeHandle.setAttribute(
                'aria-valuenow',
                dockPreferences.inspectorWidth.toString()
            );
            const renderSidebarControls = (
                collapseButton: Button,
                revealButton: Button,
                expanded: boolean,
                canExpand: boolean,
                collapseLabelKey: string,
                revealLabelKey: string
            ): void => {
                const expandedValue = expanded.toString();
                collapseButton.hidden = !expanded;
                revealButton.hidden = expanded || !canExpand;
                collapseButton.dom.setAttribute('aria-expanded', expandedValue);
                revealButton.dom.setAttribute('aria-expanded', expandedValue);
                const renderButtonLabel = (
                    button: Button,
                    labelKey: string
                ): void => {
                    setSvgButtonLabel(button, i18n.t(labelKey));
                };
                renderButtonLabel(collapseButton, collapseLabelKey);
                renderButtonLabel(revealButton, revealLabelKey);
            };
            renderSidebarControls(
                navigatorCollapse,
                navigatorReveal,
                columns.navigator,
                expandable.navigator,
                'ai-select.dock.hide-navigator',
                'ai-select.dock.show-navigator'
            );
            renderSidebarControls(
                inspectorCollapse,
                inspectorReveal,
                columns.inspector,
                expandable.inspector,
                'ai-select.dock.hide-inspector',
                'ai-select.dock.show-inspector'
            );
            if (!this.filterPopover.hidden) {
                this.updateFilterPopoverSize();
            }
        };
        navigatorCollapse.on('click', () => {
            dockPreferences = setAIViewDockSidebarExpanded(
                dockPreferences,
                'navigator',
                false
            );
            writeDockPreferences();
            renderColumns();
            navigatorReveal.dom.focus();
        });
        navigatorReveal.on('click', () => {
            dockPreferences = setAIViewDockSidebarExpanded(
                dockPreferences,
                'navigator',
                true
            );
            writeDockPreferences();
            renderColumns();
            (navigator.hidden
                ? navigatorReveal.dom
                : navigatorCollapse.dom
            ).focus();
        });
        inspectorCollapse.on('click', () => {
            dockPreferences = setAIViewDockSidebarExpanded(
                dockPreferences,
                'inspector',
                false
            );
            writeDockPreferences();
            renderColumns();
            inspectorReveal.dom.focus();
        });
        inspectorReveal.on('click', () => {
            dockPreferences = setAIViewDockSidebarExpanded(
                dockPreferences,
                'inspector',
                true
            );
            writeDockPreferences();
            renderColumns();
            (inspector.hidden
                ? inspectorReveal.dom
                : inspectorCollapse.dom
            ).focus();
        });
        const bindSidebarResize = (
            handle: HTMLDivElement,
            side: 'navigator' | 'inspector'
        ): void => {
            const minimum =
                side === 'navigator'
                    ? AI_VIEW_NAVIGATOR_MINIMUM_WIDTH_PX
                    : AI_VIEW_INSPECTOR_MINIMUM_WIDTH_PX;
            const maximum =
                side === 'navigator'
                    ? AI_VIEW_NAVIGATOR_MAXIMUM_WIDTH_PX
                    : AI_VIEW_INSPECTOR_MAXIMUM_WIDTH_PX;
            handle.setAttribute('aria-valuemin', minimum.toString());
            handle.setAttribute('aria-valuemax', maximum.toString());
            let startX = 0;
            let startWidth = 0;
            let resizing = false;
            const resize = (clientX: number): void => {
                const delta =
                    (clientX - startX) * (side === 'navigator' ? 1 : -1);
                const next = Math.round(
                    Math.max(minimum, Math.min(maximum, startWidth + delta))
                );
                dockPreferences = resizeAIViewDockSidebar(
                    dockPreferences,
                    side,
                    next
                );
                renderColumns();
            };
            handle.addEventListener('pointerdown', (event) => {
                if (!event.isPrimary) {
                    return;
                }
                resizing = true;
                startX = event.clientX;
                startWidth =
                    side === 'navigator'
                        ? dockPreferences.navigatorWidth
                        : dockPreferences.inspectorWidth;
                handle.setPointerCapture(event.pointerId);
                event.preventDefault();
                event.stopPropagation();
            });
            handle.addEventListener('pointermove', (event) => {
                if (resizing) {
                    resize(event.clientX);
                }
            });
            handle.addEventListener('lostpointercapture', () => {
                resizing = false;
                writeDockPreferences();
            });
            handle.addEventListener('keydown', (event) => {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
                    return;
                }
                startX = 0;
                startWidth =
                    side === 'navigator'
                        ? dockPreferences.navigatorWidth
                        : dockPreferences.inspectorWidth;
                resize(event.key === 'ArrowLeft' ? -8 : 8);
                writeDockPreferences();
                event.preventDefault();
                event.stopPropagation();
            });
        };
        bindSidebarResize(navigatorResizeHandle, 'navigator');
        bindSidebarResize(inspectorResizeHandle, 'inspector');
        window.addEventListener(
            'keydown',
            (event) => {
                if (
                    event.key !== 'Escape' ||
                    this.dom.getClientRects().length === 0 ||
                    this.palette.popoverOpen ||
                    document.querySelector(
                        '[role="menu"]:not(.pcui-hidden)'
                    ) !== null ||
                    (event.target instanceof HTMLElement &&
                        event.target.closest('[role="dialog"]') !== null)
                ) {
                    return;
                }
                if (!inspector.hidden) {
                    dockPreferences = setAIViewDockSidebarExpanded(
                        dockPreferences,
                        'inspector',
                        false
                    );
                    writeDockPreferences();
                    renderColumns();
                    inspectorReveal.dom.focus();
                    event.preventDefault();
                } else if (!navigator.hidden) {
                    dockPreferences = setAIViewDockSidebarExpanded(
                        dockPreferences,
                        'navigator',
                        false
                    );
                    writeDockPreferences();
                    renderColumns();
                    navigatorReveal.dom.focus();
                    event.preventDefault();
                }
            },
            true
        );
        const dockLayoutObserver = new ResizeObserver(renderColumns);
        dockLayoutObserver.observe(mainRow.dom);
        dockLayoutObserver.observe(this.workCanvasRow.dom);
        renderColumns();

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
        options.anchorAdjustment.subscribe((state) => {
            this.anchorAdjustmentState = state;
            this.cancelPointerGesture();
            this.render();
        });
        options.generatedViews.subscribe((generatedState) => {
            if (
                generatedState.selectedViewId !==
                this.generatedState.selectedViewId
            ) {
                this.cancelPointerGesture();
                this.pendingGalleryScrollId =
                    generatedState.selectedViewId ?? NAVIGATOR_ANCHOR_ID;
            }
            this.generatedState = generatedState;
            this.render();
        });
        options.userViewMasks.subscribe(() => this.render());
        options.candidatePresentation.subscribe(() => this.render());
        options.candidateCorrection.subscribe((correctionState) => {
            this.candidateCorrectionState = correctionState;
            this.render();
        });
        options.liftReadiness.subscribe((state) => {
            this.liftReadinessState = state;
            this.render();
        });
        i18n.onChange(() => {
            renderUndoSceneChangeLabel();
            setSvgButtonLabel(
                this.plannerRetryButton,
                i18n.t('ai-select.views.planner.retry')
            );
            setSvgButtonLabel(
                resetFitButton,
                i18n.t('ai-select.dock.reset-fit')
            );
            setSvgButtonLabel(
                this.reLiftButton,
                i18n.t('ai-select.candidate.update')
            );
            this.filterPopover.dom.setAttribute(
                'aria-label',
                i18n.t('ai-select.views.filter-sort')
            );
            filterGroup.dom.setAttribute(
                'aria-label',
                i18n.t('ai-select.views.filter-group')
            );
            sortGroup.dom.setAttribute(
                'aria-label',
                i18n.t('ai-select.views.sort-group')
            );
            renderColumns();
            this.render();
        }, this);
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

    private renderSelectedViewMetadata(view: GeneratedAIView): void {
        const role = galleryViewRole(view.source);
        const sameRoleViews = orderGalleryViews(
            this.generatedState.views
        ).filter((entry) => galleryViewRole(entry.source) === role);
        const ordinal = Math.max(1, sameRoleViews.indexOf(view) + 1);
        const card = galleryCardPresentation(view, ordinal);
        const rgbDigest = view.rgb?.digest;
        const currentMasks = this.maskRegistry.viewState(
            view.viewId,
            rgbDigest ?? ''
        );
        const authoring = this.authoring();
        const hasMaskChanges =
            currentMasks.editingMaskIssue !== null ||
            hasSemanticEditingMaskChange(
                currentMasks.editingMask,
                currentMasks.stableMask
            );
        const maskState: Parameters<
            typeof viewInspectorPresentation
        >[0]['maskState'] = authoring?.maskState ?? {
            editingMask: currentMasks.editingMask,
            stableMask: currentMasks.stableMask,
            editingMaskIssue: currentMasks.editingMaskIssue,
            promptState: null,
            publishedPromptState: null,
            requestStatus:
                view.maskStatus === 'generating'
                    ? 'pending'
                    : view.maskStatus === 'failed'
                      ? 'failed'
                      : 'idle',
            hasUnconfirmedPromptChanges: false,
            hasUnconfirmedMaskChanges: hasMaskChanges
        };
        this.renderInspectorPresentation({
            viewId: view.viewId,
            ...(rgbDigest === undefined ? {} : { rgbDigest }),
            quality: view.maskQuality,
            participation: view.participation,
            participationToggle: card.actions.participationToggle,
            actionableIssues: view.assessment?.actionableReasons ?? [],
            maskState,
            ...(view.prompt === undefined
                ? {}
                : { generatedPrompt: view.prompt }),
            technicalErrors: [
                view.renderErrorMessage,
                view.promptErrorMessage,
                view.maskErrorMessage,
                this.candidateCorrectionState.status === 'failed'
                    ? this.candidateCorrectionState.errorMessage
                    : undefined
            ].filter((entry): entry is string => entry !== undefined)
        });
    }

    private renderAnchorMetadata(
        presentation: AnchorDockPresentation,
        statusKey: string
    ): void {
        const hasStableMask = this.maskState.stableMask !== null;
        this.status.text = i18n.t(statusKey);
        this.renderInspectorPresentation({
            viewId: this.maskState.viewId,
            ...(presentation.rgb === undefined
                ? {}
                : { rgbDigest: presentation.rgb.digest }),
            quality: hasStableMask ? 'user-confirmed' : 'none',
            participation: hasStableMask ? 'included' : 'excluded',
            participationToggle: null,
            actionableIssues: [],
            maskState: this.maskState,
            technicalErrors: [
                this.maskState.errorMessage,
                this.confirmationState.errorMessage,
                this.candidateCorrectionState.status === 'failed'
                    ? this.candidateCorrectionState.errorMessage
                    : undefined
            ].filter((entry): entry is string => entry !== undefined)
        });
    }

    private renderInspectorPresentation(
        input: Parameters<typeof viewInspectorPresentation>[0]
    ): void {
        const inspector = viewInspectorPresentation(input);
        this.selectedViewAssessment.text = i18n.t(
            `ai-select.review.quality.${inspector.assessment.quality}`
        );
        const participation = inspector.assessment.participation;
        const participationText = i18n.t(
            `ai-select.participation.${participation.value}`
        );
        this.selectedViewParticipation.text = '';
        const participationIcon = createSvg(
            participation.icon === 'included' ? confirmSvg : hiddenSvg
        );
        participationIcon.setAttribute('aria-hidden', 'true');
        participationIcon.classList.add('ai-select-participation-icon');
        this.selectedViewParticipation.dom.replaceChildren(participationIcon);
        this.selectedViewParticipation.enabled =
            participation.toggle !== null &&
            this.state.context?.lifecycle === 'active';
        this.selectedViewParticipation.dom.setAttribute(
            'aria-pressed',
            participation.pressed.toString()
        );
        const actionText =
            participation.toggle === null
                ? participation.value === 'excluded'
                    ? i18n.t('ai-select.participation.include-unavailable')
                    : ''
                : i18n.t(`ai-select.participation.${participation.toggle}`);
        const participationLabel = [participationText, actionText]
            .filter((entry) => entry.length > 0)
            .join('. ');
        this.selectedViewParticipation.dom.setAttribute(
            'aria-label',
            participationLabel
        );
        this.selectedViewParticipation.dom.title = participationLabel;

        const issues = inspector.assessment.issueReasons.map((reason) =>
            i18n.t(
                reason === 'editing-mask-state-invalid'
                    ? 'ai-select.mask.editing-state-invalid'
                    : `ai-select.review.reason.${reason}`
            )
        );
        this.selectedViewIssues.hidden = issues.length === 0;
        this.selectedViewIssues.text = issues.join('\n');

        const prompt = inspector.promptAndMask.prompt;
        const version = (identity: {
            revision?: number;
            digest: string;
        }): string =>
            identity.revision === undefined
                ? identity.digest.slice(0, 15)
                : `r${i18n.formatInteger(identity.revision)}`;
        const promptVersions = [
            ...(prompt.published === null
                ? []
                : [
                      `${i18n.t('ai-select.inspector.published')}: ${version(prompt.published)}`
                  ]),
            ...(prompt.editing === null
                ? []
                : [
                      `${i18n.t('ai-select.inspector.editing')}: ${version(prompt.editing)}`
                  ])
        ];
        this.promptStatus.text = [
            `${i18n.t('ai-select.prompt.summary-positive-points')} ${i18n.formatInteger(prompt.positivePointCount)}`,
            `${i18n.t('ai-select.prompt.summary-negative-points')} ${i18n.formatInteger(prompt.negativePointCount)}`,
            `${i18n.t('ai-select.prompt.summary-boxes')} ${i18n.formatInteger(prompt.boxCount)}`,
            ...promptVersions
        ].join(' · ');
        this.promptStatus.hidden = false;

        const mask = inspector.promptAndMask.mask;
        const maskText =
            mask.status === 'invalid-editing'
                ? i18n.t('ai-select.mask.editing-state-invalid')
                : i18n.t(`ai-select.mask.${mask.status}`);
        const maskVersions = [
            ...(mask.published === null
                ? []
                : [
                      `${i18n.t('ai-select.inspector.published')}: ${mask.published.maskId}`
                  ]),
            ...(mask.editing === null
                ? []
                : [
                      `${i18n.t('ai-select.inspector.editing')}: ${mask.editing.maskId}`
                  ])
        ];
        this.maskStatus.text = [maskText, ...maskVersions].join(' · ');
        this.maskStatus.hidden = false;
        this.technicalDetailsBody.textContent = inspector.technicalDetails.rows
            .map(
                (row) =>
                    `${i18n.t(`ai-select.inspector.field.${row.label}`)}: ${row.value}`
            )
            .join('\n');
    }

    private render(): void {
        this.renderSuspensionSurface();
        this.renderWorkAreaActions();
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        if (this.state.context !== null) {
            const currentId =
                this.generatedState.selectedViewId === null
                    ? NAVIGATOR_ANCHOR_ID
                    : this.generatedState.selectedViewId;
            const projection = projectNavigatorViews(
                this.generatedState.views,
                this.galleryFilter,
                this.gallerySort,
                currentId
            );
            this.filteredSelectionEmpty = projection.empty;
            if (projection.selectionChanged && projection.currentId !== null) {
                this.selectGeneratedView(
                    projection.currentId === NAVIGATOR_ANCHOR_ID
                        ? null
                        : projection.currentId
                );
                return;
            }
        } else {
            this.filteredSelectionEmpty = false;
        }
        this.inspectorInformation.hidden =
            this.state.context === null || this.filteredSelectionEmpty;
        if (this.filteredSelectionEmpty) {
            this.cancelPointerGesture();
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
            this.status.text = i18n.t('ai-select.views.filter-empty');
            this.status.hidden = false;
            this.canvasStateActions.hidden = true;
            this.renderGallery(presentation);
            return;
        }
        if (this.anchorAdjustmentState.draft !== null) {
            this.renderAnchorAdjustmentDraft();
            this.renderGallery(presentation);
            this.renderCanvasStateActionsVisibility();
            return;
        }
        const inspected = this.inspectedGeneratedView();
        if (inspected !== null) {
            const viewAuthoring = this.authoring();
            if (viewAuthoring !== null && viewAuthoring.ready) {
                this.renderViewMaskAuthoring(inspected);
            } else {
                this.renderInspection(inspected);
            }
            this.renderSelectedViewMetadata(inspected);
            this.renderGallery(presentation);
            this.renderCanvasStateActionsVisibility();
            return;
        }
        if (presentation.rgb) {
            this.image.width = presentation.rgb.width;
            this.image.height = presentation.rgb.height;
            this.image.src = `data:image/png;base64,${presentation.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.status.hidden = true;
            this.updateImageSurfaceRect(
                presentation.rgb.width,
                presentation.rgb.height
            );
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.status.hidden = false;
        }
        const textKey = {
            idle: 'ai-select.panel.idle',
            ready: 'ai-select.anchor.ready',
            previewing: 'ai-select.anchor.previewing',
            rendering: 'ai-select.anchor.rendering',
            failed: 'ai-select.anchor.failed'
        }[presentation.status];
        this.renderMaskSurface(
            presentation.mask,
            this.maskState,
            presentation.status === 'ready'
        );
        this.renderPromptStatus(presentation.mask, this.maskState);
        this.renderAnchorMetadata(presentation, textKey);
        this.renderAuthoringTools();
        this.renderAnchorValidationStatus();
        this.renderCurrentMaskOverlay();
        this.renderGallery(presentation);
        this.renderCanvasStateActionsVisibility();
    }

    private renderSuspensionSurface(): void {
        const suspended = this.state.context?.lifecycle === 'suspended';
        const suspendedTargetContextId = suspended
            ? (this.state.context?.targetContextId ?? null)
            : null;
        if (suspendedTargetContextId !== this.suspendedTargetContextId) {
            this.suspendedTargetContextId = suspendedTargetContextId;
            this.undoSceneChangeFailed = false;
        }
        this.suspendedSurface.hidden = !suspended;
        this.suspendedMessage.text = i18n.t(
            this.undoSceneChangeFailed
                ? 'ai-select.suspended.undo-failed'
                : 'ai-select.suspended.message'
        );
        this.undoSceneChangeButton.enabled =
            suspended &&
            !this.undoSceneChangePending &&
            this.canUndoSceneChange();
        this.undoSceneChangeButton.dom.setAttribute(
            'aria-busy',
            String(this.undoSceneChangePending)
        );
    }

    private renderAnchorAdjustmentDraft(): void {
        const draft = this.anchorAdjustmentState.draft;
        const authoring = this.authoring();
        if (draft === null || authoring === null) {
            return;
        }
        if (draft.rgb !== undefined && draft.renderStatus === 'ready') {
            this.image.width = draft.rgb.width;
            this.image.height = draft.rgb.height;
            this.image.src = `data:image/png;base64,${draft.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.status.hidden = true;
            this.updateImageSurfaceRect(draft.rgb.width, draft.rgb.height);
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
            this.status.hidden = false;
            this.status.text =
                draft.renderStatus === 'failed'
                    ? (draft.errorMessage ?? i18n.t('ai-select.anchor.failed'))
                    : i18n.t('ai-select.anchor.rendering');
        }
        const mask = getViewMaskPresentation(authoring.maskState);
        this.renderMaskSurface(mask, authoring.maskState, authoring.ready);
        this.renderPromptStatus(mask, authoring.maskState);
        this.renderAuthoringTools();
        this.renderCurrentMaskOverlay();
        this.renderInspectorPresentation({
            viewId: authoring.maskState.viewId,
            ...(draft.rgb === undefined ? {} : { rgbDigest: draft.rgb.digest }),
            quality:
                authoring.maskState.stableMask === null
                    ? 'none'
                    : 'user-confirmed',
            participation: 'included',
            participationToggle: null,
            actionableIssues: [],
            maskState: authoring.maskState,
            technicalErrors: [
                authoring.maskState.errorMessage,
                this.anchorAdjustmentState.errorMessage
            ].filter((entry): entry is string => entry !== undefined)
        });
        this.validationStatus.text = [
            ...(this.anchorAdjustmentState.confirmationStatus === 'validating'
                ? [i18n.t('ai-select.validation.validating')]
                : []),
            ...(this.anchorAdjustmentState.errorMessage === undefined
                ? []
                : [this.anchorAdjustmentState.errorMessage])
        ].join('\n');
        this.validationStatus.hidden = this.validationStatus.text.length === 0;
    }

    private workAreaActions(
        canConfirmMask = false,
        canConfirmReview = false,
        anchorNeedsConfirmation = false
    ): WorkAreaActionPresentation {
        const generatedIncluded = this.generatedState.views.filter(
            (view) =>
                view.participation === 'included' &&
                view.stableMaskDigest !== undefined
        );
        const generatedHasDraft = generatedIncluded.some((view) => {
            const session = this.userViewMasks.sessionFor(view.viewId);
            return session?.state.hasUnconfirmedChanges === true;
        });
        return mapWorkAreaActions({
            targetActive: this.state.context?.lifecycle === 'active',
            serviceAvailable: this.availabilityStatus === 'available',
            hasUsableIncludedStableInput:
                this.maskState.stableMask !== null ||
                generatedIncluded.length > 0,
            hasUnconfirmedIncludedMask:
                (this.maskState.stableMask !== null &&
                    this.maskState.hasUnconfirmedChanges) ||
                generatedHasDraft,
            candidateStatus: this.candidateCorrectionState.candidate.status,
            correctionMode: this.candidateCorrectionState.mode,
            correctionStatus: this.candidateCorrectionState.status,
            liftReadiness: this.liftReadinessState,
            canConfirmMask,
            canConfirmReview,
            anchorNeedsConfirmation
        });
    }

    private reLiftDescription(): string {
        const presentation = this.workAreaActions().reLift;
        if (presentation.state === 'updating') {
            return i18n.t('ai-select.candidate.updating');
        }
        return presentation.reason === null
            ? i18n.t('ai-select.candidate.update')
            : i18n.t(`ai-select.re-lift.reason.${presentation.reason}`);
    }

    private renderWorkAreaActions(): void {
        const presentation = this.workAreaActions().reLift;
        const description = this.reLiftDescription();
        this.reLiftButton.hidden = !presentation.visible;
        this.reLiftButton.enabled = presentation.enabled;
        this.reLiftButton.dom.title = description;
        this.reLiftButton.dom.setAttribute('aria-label', description);
        this.reLiftButton.dom.setAttribute('aria-description', description);
        this.reLiftButton.dom.setAttribute(
            'aria-busy',
            String(presentation.state === 'updating')
        );
        this.reLiftButton.dom.dataset.reason = presentation.reason ?? '';
        this.reLiftButton.dom.classList.toggle(
            'readiness-limited',
            presentation.emphasis === 'warning'
        );
        this.reLiftButton.dom.classList.toggle(
            'updating',
            presentation.state === 'updating'
        );
    }

    /**
     * The Mask surface shared by the Anchor and user-added Views: request
     * currency, draft/confirmed Mask currency, technical failure details, and
     * the palette Confirm affordance. Failure recovery changes the Prompt,
     * edits the Mask manually, or adds a replacement View.
     */
    private renderMaskSurface(
        mask: AnchorDockMaskPresentation,
        maskState: AISelectMaskState,
        ready: boolean
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
                    : mask.automaticMaskStatus === 'unavailable'
                      ? i18n.t('ai-select.mask.unavailable')
                      : i18n.t(`ai-select.mask.${mask.status}`);
        }
    }

    /**
     * The editable Gallery View surface: the same Prompt/Mask/Brush/
     * Confirm UI as the Anchor, bound to this View's exact Mask session.
     */
    private renderViewMaskAuthoring(view: GeneratedAIView): void {
        const authoring = this.authoring();
        if (authoring === null) {
            this.renderInspection(view);
            return;
        }
        if (view.rgb !== undefined) {
            this.image.width = view.rgb.width;
            this.image.height = view.rgb.height;
            this.image.src = `data:image/png;base64,${view.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.status.hidden = true;
            this.updateImageSurfaceRect(view.rgb.width, view.rgb.height);
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
            this.status.hidden = false;
        }
        this.status.text = i18n.t('ai-select.views.inspecting-editing');
        this.validationStatus.hidden = true;
        const mask = getViewMaskPresentation(authoring.maskState);
        this.renderMaskSurface(mask, authoring.maskState, authoring.ready);
        this.renderPromptStatus(mask, authoring.maskState);
        this.renderAuthoringTools();
        this.renderCurrentMaskOverlay();
    }

    /**
     * The Mask authoring target that currently owns the Dock's image surface:
     * an inspected Gallery View's session, or the Anchor when none is
     * inspected. Render-pending Views have no ready authoring surface.
     */
    private authoring(): DockAuthoringTarget | null {
        const targetActive = this.state.context?.lifecycle === 'active';
        const adjustmentDraft = this.anchorAdjustmentState.draft;
        if (adjustmentDraft !== null) {
            return {
                ops: this.anchorAdjustment.mask,
                maskState: this.anchorAdjustment.mask.state,
                locked: false,
                ready:
                    targetActive &&
                    adjustmentDraft.renderStatus === 'ready' &&
                    adjustmentDraft.rgb !== undefined,
                ...(adjustmentDraft.rgb === undefined
                    ? {}
                    : { rgb: adjustmentDraft.rgb })
            };
        }
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
                ready: targetActive && inspected.renderStatus === 'ready',
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
            ready: targetActive && presentation.status === 'ready',
            ...(presentation.rgb === undefined ? {} : { rgb: presentation.rgb })
        };
    }

    /** Read-only fallback when an inspected View has no authoring session. */
    private renderInspection(view: GeneratedAIView): void {
        if (view.rgb !== undefined) {
            this.image.width = view.rgb.width;
            this.image.height = view.rgb.height;
            this.image.src = `data:image/png;base64,${view.rgb.pngBase64}`;
            this.image.hidden = false;
            this.imageSurface.hidden = false;
            this.status.hidden = true;
            this.updateImageSurfaceRect(view.rgb.width, view.rgb.height);
        } else {
            this.image.hidden = true;
            this.imageSurface.hidden = true;
            this.overlay.hidden = true;
            this.status.hidden = false;
        }
        const roleKey =
            galleryViewRole(view.source) === 'user-added'
                ? 'ai-select.views.role.user-added'
                : 'ai-select.views.generated';
        this.status.text = `${i18n.t(roleKey)} — ${i18n.t('ai-select.views.inspecting')}`;
        this.maskStatus.hidden = true;
        this.promptStatus.hidden = true;
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
            canClearHistory: false,
            canConfirmMask: false,
            canRestoreAutoMask: false
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
        const editing = hasSemanticEditingMaskChange(
            masks.editingMask,
            masks.stableMask
        );
        const annotation = editing
            ? masks.editingMask
            : (masks.stableMask ?? masks.editingMask);
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
            editing
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

    private createCard(onClick: () => void): GeneratedCardElements {
        const root = new Container({ class: 'ai-select-view-card' });
        root.dom.setAttribute('role', 'option');
        root.dom.tabIndex = -1;
        const image = document.createElement('img');
        image.className = 'ai-select-view-card-image';
        image.alt = '';
        image.loading = 'lazy';
        image.hidden = true;
        image.draggable = false;
        const anchorPin = document.createElement('span');
        anchorPin.className = 'ai-select-view-card-anchor-pin';
        anchorPin.setAttribute('aria-hidden', 'true');
        anchorPin.hidden = true;
        anchorPin.appendChild(createSvg(pinSvg));
        const badge = document.createElement('span');
        badge.className = 'ai-select-view-card-badge';
        badge.setAttribute('aria-hidden', 'true');
        root.dom.appendChild(image);
        root.dom.appendChild(anchorPin);
        root.dom.appendChild(badge);
        root.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );
        root.dom.addEventListener('click', () => {
            root.dom.focus();
            onClick();
        });
        root.dom.addEventListener('keydown', (event) => {
            if (event.target !== root.dom) {
                return;
            }
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick();
                return;
            }
            if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
                event.preventDefault();
                this.moveGalleryFocus(root.dom, 1);
            } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
                event.preventDefault();
                this.moveGalleryFocus(root.dom, -1);
            }
        });
        return {
            root,
            image,
            anchorPin,
            badge
        };
    }

    private renderGallery(presentation: AnchorDockPresentation): void {
        const generated = this.generatedState;
        this.gallery.hidden = false;
        if (this.state.context === null) {
            this.plannerLine.hidden = true;
            this.filterLine.hidden = true;
            this.galleryCards.hidden = true;
            this.galleryEmptyState.text = i18n.t('ai-select.views.no-target');
            this.galleryEmptyState.hidden = false;
            this.selectedViewPrimaryAction = null;
            this.selectedViewPrimaryButton.hidden = true;
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
        } else if (generated.plannerStatus === 'active') {
            const generationInProgress = generated.views.some(
                (view) =>
                    view.renderStatus === 'pending' ||
                    view.renderStatus === 'rendering' ||
                    view.promptStatus === 'synthesizing' ||
                    view.maskStatus === 'generating'
            );
            this.plannerLine.hidden = !generationInProgress;
            this.plannerStatus.text = i18n.t(
                'ai-select.views.planner.planning'
            );
            this.plannerRetryButton.hidden = true;
        } else {
            this.plannerLine.hidden = true;
        }

        const currentId =
            generated.selectedViewId === null
                ? NAVIGATOR_ANCHOR_ID
                : generated.selectedViewId;
        const projection = projectNavigatorViews(
            generated.views,
            this.galleryFilter,
            this.gallerySort,
            currentId
        );
        this.filteredSelectionEmpty = projection.empty;
        this.filterLine.hidden = false;
        const filterLabel = i18n.t(
            `ai-select.views.filter.${this.galleryFilter === 'all' ? 'all' : 'needs-review'}`
        );
        const sortLabel = i18n.t(`ai-select.views.sort.${this.gallerySort}`);
        this.filterTrigger.text = `${filterLabel} · ${sortLabel}`;
        this.filterTrigger.dom.title = `${i18n.t('ai-select.views.filter-sort')}: ${this.filterTrigger.text}`;
        this.filterTrigger.dom.setAttribute(
            'aria-label',
            this.filterTrigger.dom.title
        );
        for (const [filter, button] of this.filterButtons) {
            button.text = i18n.t(
                `ai-select.views.filter.${filter === 'all' ? 'all' : 'needs-review'}`
            );
            button.dom.setAttribute(
                'aria-checked',
                (filter === this.galleryFilter).toString()
            );
            button.dom.tabIndex = filter === this.galleryFilter ? 0 : -1;
        }
        for (const [sort, button] of this.sortButtons) {
            button.text = i18n.t(`ai-select.views.sort.${sort}`);
            button.dom.setAttribute(
                'aria-checked',
                (sort === this.gallerySort).toString()
            );
            button.dom.tabIndex = sort === this.gallerySort ? 0 : -1;
        }
        this.galleryEmptyState.text = i18n.t('ai-select.views.filter-empty');
        this.galleryEmptyState.hidden = !projection.empty;
        this.galleryCards.hidden = projection.empty;

        // The Anchor remains the oldest global item and uses an identity pin.
        this.anchorCard.anchorPin.hidden = false;
        const anchorBadge: NavigatorBadge =
            presentation.status === 'failed'
                ? 'failure'
                : presentation.status === 'ready'
                  ? 'ready'
                  : 'processing';
        this.renderCardBadge(this.anchorCard, anchorBadge);
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
        const anchorSelected =
            !projection.empty && generated.selectedViewId === null;
        this.anchorCard.root.hidden = !projection.items.some(
            (item) => item.id === NAVIGATOR_ANCHOR_ID
        );
        this.anchorCard.root.dom.classList.toggle('selected', anchorSelected);
        this.anchorCard.root.dom.tabIndex = anchorSelected ? 0 : -1;
        this.anchorCard.root.dom.setAttribute(
            'aria-selected',
            anchorSelected.toString()
        );
        this.anchorCard.root.dom.setAttribute(
            'aria-label',
            `${i18n.t('ai-select.views.anchor')}, ${i18n.t(`ai-select.views.badge.${anchorBadge}`)}`
        );
        this.anchorCard.root.dom.setAttribute(
            'aria-current',
            anchorSelected ? 'true' : 'false'
        );

        const ordered = orderGalleryViews(generated.views);
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
                card = this.createCard(() =>
                    this.selectGeneratedView(view.viewId)
                );
                this.generatedCards.set(view.viewId, card);
                this.galleryCards.append(card.root);
            }
            this.updateGeneratedCard(
                card,
                galleryCardPresentation(view, ordinals.get(view.viewId) ?? 0),
                view
            );
            const visible = projection.items.some(
                (item) => item.id === view.viewId
            );
            card.root.hidden = !visible;
            card.root.dom.setAttribute(
                'aria-current',
                view.selected ? 'true' : 'false'
            );
            card.root.dom.setAttribute(
                'aria-selected',
                view.selected.toString()
            );
            card.root.dom.tabIndex = view.selected && visible ? 0 : -1;
        }
        for (const [viewId, card] of this.generatedCards) {
            if (!seen.has(viewId)) {
                card.root.destroy();
                this.generatedCards.delete(viewId);
            }
        }
        for (const item of projection.items) {
            const card =
                item.id === NAVIGATOR_ANCHOR_ID
                    ? this.anchorCard
                    : this.generatedCards.get(item.id);
            if (card !== undefined) {
                this.galleryCards.dom.appendChild(card.root.dom);
            }
        }
        if (this.pendingGalleryScrollId !== null) {
            const selectedCard =
                this.pendingGalleryScrollId === NAVIGATOR_ANCHOR_ID
                    ? this.anchorCard
                    : this.generatedCards.get(this.pendingGalleryScrollId);
            if (selectedCard !== undefined && !selectedCard.root.hidden) {
                selectedCard.root.dom.scrollIntoView({ block: 'nearest' });
                this.pendingGalleryScrollId = null;
            }
        }
        this.renderSelectedViewActions(ordered, ordinals);
    }

    private setFilterPopoverOpen(open: boolean, restoreFocus = false): void {
        this.filterPopover.hidden = !open;
        this.filterTrigger.dom.setAttribute('aria-expanded', open.toString());
        if (open) {
            this.updateFilterPopoverSize();
            const active = this.filterButtons.get(this.galleryFilter);
            active?.dom.focus();
        } else if (restoreFocus) {
            this.filterTrigger.dom.focus();
        }
    }

    private updateFilterPopoverSize(): void {
        const galleryRect = this.gallery.dom.getBoundingClientRect();
        const triggerRect = this.filterTrigger.dom.getBoundingClientRect();
        const availableBelow = Math.max(
            80,
            Math.floor(galleryRect.bottom - triggerRect.bottom - 8)
        );
        this.filterPopover.style.maxHeight = `${Math.min(240, availableBelow)}px`;
    }

    private renderCardBadge(
        card: GeneratedCardElements,
        badge: NavigatorBadge
    ): void {
        card.badge.textContent = i18n.t(`ai-select.views.badge.${badge}`);
        card.badge.className = `ai-select-view-card-badge badge-${badge}`;
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
        const title = `${i18n.t(titleKey)} ${i18n.formatInteger(presentation.titleOrdinal)}`;
        const badge = navigatorBadgePresentation(view);
        this.renderCardBadge(card, badge);
        const accessibilityStates = [
            title,
            i18n.t(`ai-select.views.badge.${badge}`),
            ...(view.participation === 'excluded'
                ? [i18n.t('ai-select.participation.excluded')]
                : [])
        ];
        card.root.dom.setAttribute(
            'aria-label',
            accessibilityStates.join(', ')
        );
        card.root.dom.dataset.viewId = presentation.viewId;
        card.anchorPin.hidden = true;
        if (view.rgb !== undefined) {
            this.applyCardThumbnail(card, view.rgb.digest, view.rgb.pngBase64);
        } else {
            card.rgbDigest = undefined;
            card.image.hidden = true;
        }
        card.root.dom.classList.toggle('selected', presentation.selected);
        card.root.dom.classList.toggle(
            'excluded',
            view.participation === 'excluded'
        );
    }

    private moveGalleryFocus(from: HTMLElement, delta: -1 | 1): void {
        const cards = this.allCards();
        const visibleCards = Array.from(this.galleryCards.dom.children)
            .map((element) => cards.find((card) => card.root.dom === element))
            .filter(
                (card): card is GeneratedCardElements =>
                    card !== undefined && !card.root.hidden
            );
        const currentIndex = visibleCards.findIndex(
            (card) => card.root.dom === from
        );
        if (currentIndex < 0 || visibleCards.length === 0) {
            return;
        }
        const nextIndex =
            (currentIndex + delta + visibleCards.length) % visibleCards.length;
        for (const card of visibleCards) {
            card.root.dom.tabIndex = -1;
        }
        visibleCards[nextIndex].root.dom.tabIndex = 0;
        visibleCards[nextIndex].root.dom.focus();
    }

    private renderSelectedViewActions(
        ordered: readonly GeneratedAIView[],
        ordinals: ReadonlyMap<string, number>
    ): void {
        const selected =
            this.anchorAdjustmentState.draft === null
                ? this.inspectedGeneratedView()
                : null;
        if (selected === null) {
            this.selectedViewPrimaryAction = null;
            this.selectedViewPrimaryButton.hidden = true;
            return;
        }
        const card = galleryCardPresentation(
            selected,
            ordinals.get(selected.viewId) ?? 0
        );
        const authoring = this.authoring();
        const authoringPrimaryVisible =
            authoring !== null &&
            getViewMaskPresentation(authoring.maskState).showConfirm;
        let action: AISelectAnchorDock<TCandidatePayload>['selectedViewPrimaryAction'] =
            null;
        if (
            !authoringPrimaryVisible &&
            !card.actions.confirmAsIs &&
            filterGalleryViews(ordered, 'needs-review').some(
                (view) => view.viewId !== selected.viewId
            )
        ) {
            action = 'next-review';
        }
        this.selectedViewPrimaryAction = action;
        this.selectedViewPrimaryButton.hidden = action === null;
        if (action !== null) {
            this.selectedViewPrimaryButton.text = i18n.t(
                'ai-select.views.next-review'
            );
        }
    }

    private runSelectedViewPrimaryAction(): void {
        const selected =
            this.anchorAdjustmentState.draft === null
                ? this.inspectedGeneratedView()
                : null;
        if (selected === null || this.selectedViewPrimaryAction === null) {
            return;
        }
        switch (this.selectedViewPrimaryAction) {
            case 'next-review': {
                const next = filterGalleryViews(
                    orderGalleryViews(this.generatedState.views),
                    'needs-review'
                ).find((view) => view.viewId !== selected.viewId);
                if (next !== undefined) {
                    this.selectGeneratedView(next.viewId);
                }
            }
        }
    }

    /**
     * Cards display bounded thumbnails keyed by authoritative RGB digest; the
     * full-resolution artifact stays in controller state and is never realized
     * as a card image — on a cache miss the card waits for its downscaled
     * thumbnail so a large Gallery stays inside the resource bound. Unchanged
     * digests keep their thumbnail while the bounded initial plan completes.
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
            this.onInspectCamera(viewId);
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

    /**
     * Publish the current Editing Mask. On the initial Anchor this same user
     * intent also completes Anchor confirmation, whose observer starts
     * Generated View planning. Gallery View confirmations remain local.
     */
    private async confirmCurrentMask(
        onConfirmAnchor: () => Promise<void>
    ): Promise<void> {
        const authoring = this.authoring();
        if (authoring === null) {
            return;
        }
        authoring.ops.confirmEditingMask();
        if (
            this.inspectedGeneratedView() === null &&
            this.confirmationState.confirmedAnchor === null
        ) {
            await onConfirmAnchor();
        }
    }

    /** The palette checkmark confirms the draft Mask first, then Review. */
    private runPaletteConfirmAction(
        onConfirmAnchor: () => Promise<void>,
        onConfirmAnchorAdjustment: () => Promise<void>
    ): void {
        if (this.anchorAdjustmentState.draft !== null) {
            onConfirmAnchorAdjustment().catch((error) => console.error(error));
            return;
        }
        const authoring = this.authoring();
        if (
            authoring !== null &&
            getViewMaskPresentation(authoring.maskState).showConfirm
        ) {
            this.confirmCurrentMask(onConfirmAnchor).catch((error) =>
                console.error(error)
            );
            return;
        }
        const selected = this.inspectedGeneratedView();
        if (
            selected !== null &&
            galleryCardPresentation(selected, 1).actions.confirmAsIs
        ) {
            this.confirmGeneratedReview(selected.viewId);
            return;
        }
        if (
            selected === null &&
            authoring !== null &&
            authoring.maskState.stableMask !== null &&
            this.confirmationState.confirmedAnchor === null
        ) {
            onConfirmAnchor().catch((error) => console.error(error));
        }
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
                canClearHistory: false,
                canConfirmMask: false,
                canRestoreAutoMask: false
            });
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
        const canConfirmMask =
            ready && getViewMaskPresentation(maskState).showConfirm;
        const selected =
            this.anchorAdjustmentState.draft === null
                ? this.inspectedGeneratedView()
                : null;
        const canConfirmReview =
            ready &&
            selected !== null &&
            galleryCardPresentation(selected, 1).actions.confirmAsIs;
        const anchorNeedsConfirmation =
            ready &&
            selected === null &&
            maskState.stableMask !== null &&
            (this.anchorAdjustmentState.draft !== null ||
                this.confirmationState.confirmedAnchor === null) &&
            this.confirmationState.validationStatus !== 'validating' &&
            this.anchorAdjustmentState.confirmationStatus !== 'validating';
        const actions = this.workAreaActions(
            canConfirmMask,
            canConfirmReview,
            anchorNeedsConfirmation
        ).palette;
        const contextAction =
            this.anchorAdjustmentState.draft === null
                ? actions.context
                : 'none';
        this.palette.render({
            visible:
                authoring.ready &&
                (ready ||
                    actions.confirmation !== 'none' ||
                    contextAction !== 'none'),
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
                      maskState.promptState.boxes.length > 0),
            canConfirmMask: actions.confirmation !== 'none',
            confirmLabelKey: {
                none: 'ai-select.mask.confirm',
                'confirm-mask': 'ai-select.mask.confirm',
                'confirm-review': 'ai-select.review.confirm-as-is',
                'confirm-anchor': 'ai-select.anchor.confirm'
            }[actions.confirmation],
            contextAction,
            contextLabelKey:
                contextAction === 'back-to-candidate'
                    ? 'ai-select.candidate.back-to-candidate'
                    : 'ai-select.candidate.fix-result',
            canRestoreAutoMask: ready && maskState.canRestoreAuto
        });
        this.image.style.cursor = cursorForTool(this.activeTool);
    }

    private renderCanvasStateActionsVisibility(): void {
        this.canvasStateActions.hidden = this.selectedViewPrimaryButton.hidden;
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
        const reasons = (maskState.automaticMaskReview?.reasons ?? []).map(
            (reason) => i18n.t(`ai-select.review.reason.${reason}`)
        );
        if (maskState.refinementFallback) {
            reasons.push(i18n.t('ai-select.mask.refinement-fallback'));
        }
        this.promptStatus.text = [summary, ...reasons]
            .filter((entry) => entry.length > 0)
            .join(' · ');
        this.promptStatus.hidden = false;
    }

    private renderAnchorValidationStatus(): void {
        const confirmation = this.confirmationState;
        const confirmed = confirmation.confirmedAnchor !== null;
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
        const editing =
            maskState.hasUnconfirmedMaskChanges &&
            maskState.editingMask !== null;
        const annotation = editing
            ? maskState.editingMask
            : (maskState.stableMask ?? maskState.editingMask);
        const artifact = annotation?.artifact;
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
        const pixels = maskOverlayPixels(bits, width * height, editing);
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
        const availableWidth = Math.max(0, this.workCanvasRow.dom.clientWidth);
        const availableHeight = Math.max(
            0,
            this.workCanvasRow.dom.clientHeight
        );
        const idealWidth = resolveAIViewWorkAreaWidth({
            availableWidth,
            availableHeight,
            imageWidth,
            imageHeight
        });
        if (idealWidth > 0) {
            this.imageViewport.style.width = `${idealWidth}px`;
            this.imageViewport.style.flex = `0 1 ${idealWidth}px`;
        }
        const fitted = resolveAIViewImageRect(
            {
                viewportWidth: this.imageViewport.clientWidth,
                viewportHeight: this.imageViewport.clientHeight,
                imageWidth,
                imageHeight
            },
            this.imageZoom
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
