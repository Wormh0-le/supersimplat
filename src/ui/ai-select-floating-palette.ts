import { i18n } from './localization';
import {
    clampBrushSize,
    createFloatingPaletteState,
    dragPaletteTo,
    isPaletteEditTool,
    PALETTE_BRUSH_SIZE_DEFAULT,
    PALETTE_BRUSH_SIZE_MAX,
    PALETTE_BRUSH_SIZE_MIN,
    PALETTE_TOOLS,
    PALETTE_TOOL_SHORTCUTS,
    placeBrushSizePopover,
    resetPalettePlacement,
    resolvePaletteRect,
    retargetFloatingPaletteState,
    setPaletteMode,
    snapPalette,
    type FloatingPaletteState,
    type PaletteSize,
    type PaletteTool
} from '../ai-select/floating-palette';
import boxPositiveSvg from './svg/ai-select-box-positive.svg';
import chevronSvg from './svg/ai-select-chevron.svg';
import confirmSvg from './svg/ai-select-confirm.svg';
import eraseSvg from './svg/ai-select-erase.svg';
import gripSvg from './svg/ai-select-grip.svg';
import candidatePreviewSvg from './svg/ai-select-overlay.svg';
import paintSvg from './svg/ai-select-paint.svg';
import pointNegativeSvg from './svg/ai-select-point-negative.svg';
import pointPositiveSvg from './svg/ai-select-point-positive.svg';
import restoreAutoSvg from './svg/ai-select-restore-auto.svg';
import deleteSvg from './svg/delete.svg';
import redoSvg from './svg/edit-redo.svg';
import undoSvg from './svg/edit-undo.svg';

/** Per-tool enablement projected by the owning dock. */
export interface PaletteToolAvailability {
    readonly enabled: boolean;
    readonly reason: string | null;
}

export type PaletteHistoryKind = 'prompt' | 'mask';

/** Everything the palette needs to render one dock state. */
export interface FloatingPaletteView {
    readonly visible: boolean;
    readonly activeTool: PaletteTool;
    readonly availability: ReadonlyMap<PaletteTool, PaletteToolAvailability>;
    /** History follows the active Prompt or Paint/Erase tool family. */
    readonly historyKind: PaletteHistoryKind;
    readonly canUndoHistory: boolean;
    readonly canRedoHistory: boolean;
    readonly canClearHistory: boolean;
    readonly canConfirmMask: boolean;
    readonly confirmLabelKey?: string;
    readonly contextAction?: 'none' | 'enter-correction' | 'back-to-candidate';
    readonly contextLabelKey?: string;
    readonly canRestoreAutoMask: boolean;
}

export interface AISelectFloatingPaletteOptions {
    readonly onSelectTool: (tool: PaletteTool) => void;
    readonly onHistoryUndo: (kind: PaletteHistoryKind) => void;
    readonly onHistoryRedo: (kind: PaletteHistoryKind) => void;
    readonly onHistoryClear: (kind: PaletteHistoryKind) => void;
    readonly onConfirmMask: () => void;
    readonly onContextAction: () => void;
    readonly onRestoreAutoMask: () => void;
    readonly onBrushSizeChange: (sizePx: number) => void;
}

const TOOL_ICONS: Record<PaletteTool, string> = {
    'positive-point': pointPositiveSvg,
    'negative-point': pointNegativeSvg,
    'positive-box': boxPositiveSvg,
    paint: paintSvg,
    erase: eraseSvg
};

const TOOL_LABEL_KEYS: Record<PaletteTool, string> = {
    'positive-point': 'ai-select.prompt.point-positive',
    'negative-point': 'ai-select.prompt.point-negative',
    'positive-box': 'ai-select.prompt.box-positive',
    paint: 'ai-select.edit.paint',
    erase: 'ai-select.edit.erase'
};

const createSvg = (svgString: string): Element => {
    const decoded = decodeURIComponent(
        svgString.substring('data:image/svg+xml,'.length)
    );
    return new DOMParser().parseFromString(decoded, 'image/svg+xml')
        .documentElement;
};

const createIconButton = (
    className: string,
    icon: string
): HTMLButtonElement => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.appendChild(createSvg(icon));
    return button;
};

/**
 * The floating Prompt/Edit palette (Ticket 07B, DG-22): one draggable,
 * collapsible toolbar clamped inside the fitted authoritative image. The
 * component owns only presentation state — drag/snap/collapse/hide never
 * author pixels and never touch PromptState, Mask history, or any artifact
 * identity. All geometry transitions delegate to the pure
 * ai-select/floating-palette module.
 */
export class AISelectFloatingPalette {
    readonly dom: HTMLDivElement;
    private readonly options: AISelectFloatingPaletteOptions;
    private readonly handle: HTMLDivElement;
    private readonly body: HTMLDivElement;
    private readonly capsule: HTMLButtonElement;
    private readonly capsuleIcon: HTMLSpanElement;
    private readonly collapseButton: HTMLButtonElement;
    private readonly toolButtons = new Map<PaletteTool, HTMLButtonElement>();
    private readonly undoButton: HTMLButtonElement;
    private readonly redoButton: HTMLButtonElement;
    private readonly confirmMaskButton: HTMLButtonElement;
    private readonly contextButton: HTMLButtonElement;
    private readonly restoreAutoMaskButton: HTMLButtonElement;
    private readonly clearButton: HTMLButtonElement;
    private readonly popover: HTMLDivElement;
    private readonly sizeInput: HTMLInputElement;
    private readonly sizeValue: HTMLSpanElement;
    private state: FloatingPaletteState = createFloatingPaletteState('');
    private surface: PaletteSize = { width: 0, height: 0 };
    private view: FloatingPaletteView | null = null;
    private brushSizePx = PALETTE_BRUSH_SIZE_DEFAULT;
    private brushPopoverOpen = false;
    private transientHidden = false;
    private drag: { pointerId: number; grabDX: number; grabDY: number } | null =
        null;

    constructor(options: AISelectFloatingPaletteOptions) {
        this.options = options;
        this.dom = document.createElement('div');
        this.dom.id = 'ai-select-floating-palette';
        this.dom.setAttribute('role', 'toolbar');
        this.dom.style.display = 'none';
        // The palette swallows its own pointer gestures so a press on any
        // control can never begin image authoring underneath.
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );

        this.handle = document.createElement('div');
        this.handle.className = 'palette-handle';
        this.handle.title = i18n.t('ai-select.palette.drag-handle');
        this.handle.appendChild(createSvg(gripSvg));
        this.handle.addEventListener('pointerdown', (event) =>
            this.beginDrag(event)
        );
        this.handle.addEventListener('pointermove', (event) =>
            this.continueDrag(event)
        );
        this.handle.addEventListener('pointerup', (event) =>
            this.endDrag(event)
        );
        this.handle.addEventListener('pointercancel', (event) =>
            this.endDrag(event)
        );
        this.handle.addEventListener('dblclick', () => {
            // Double-clicking the handle restores the default placement.
            this.state = resetPalettePlacement(this.state);
            this.applyPlacement();
        });

        this.body = document.createElement('div');
        this.body.className = 'palette-body';
        const promptGroup = document.createElement('div');
        promptGroup.className = 'palette-group palette-prompt-group';
        const editGroup = document.createElement('div');
        editGroup.className = 'palette-group palette-edit-group';
        const historyGroup = document.createElement('div');
        historyGroup.className = 'palette-group palette-history-group';
        for (const tool of PALETTE_TOOLS) {
            const button = createIconButton('palette-tool', TOOL_ICONS[tool]);
            button.dataset.tool = tool;
            button.addEventListener('click', () => this.handleToolClick(tool));
            this.toolButtons.set(tool, button);
            const group = isPaletteEditTool(tool) ? editGroup : promptGroup;
            group.appendChild(button);
        }
        this.undoButton = createIconButton('palette-action', undoSvg);
        this.redoButton = createIconButton('palette-action', redoSvg);
        this.confirmMaskButton = createIconButton(
            'palette-action palette-confirm-mask',
            confirmSvg
        );
        this.contextButton = createIconButton(
            'palette-action palette-context-action',
            candidatePreviewSvg
        );
        this.restoreAutoMaskButton = createIconButton(
            'palette-action palette-restore-auto-mask',
            restoreAutoSvg
        );
        this.clearButton = createIconButton('palette-action', deleteSvg);
        this.undoButton.addEventListener('click', () => {
            if (this.view !== null) {
                this.options.onHistoryUndo(this.view.historyKind);
            }
        });
        this.redoButton.addEventListener('click', () => {
            if (this.view !== null) {
                this.options.onHistoryRedo(this.view.historyKind);
            }
        });
        this.confirmMaskButton.addEventListener('click', () =>
            this.options.onConfirmMask()
        );
        this.contextButton.addEventListener('click', () =>
            this.options.onContextAction()
        );
        this.restoreAutoMaskButton.addEventListener('click', () =>
            this.options.onRestoreAutoMask()
        );
        this.clearButton.addEventListener('click', () => {
            if (this.view !== null) {
                this.options.onHistoryClear(this.view.historyKind);
            }
        });
        historyGroup.appendChild(this.undoButton);
        historyGroup.appendChild(this.redoButton);
        historyGroup.appendChild(this.confirmMaskButton);
        historyGroup.appendChild(this.contextButton);
        historyGroup.appendChild(this.restoreAutoMaskButton);
        historyGroup.appendChild(this.clearButton);
        this.collapseButton = createIconButton(
            'palette-action palette-collapse',
            chevronSvg
        );
        this.collapseButton.addEventListener('click', () =>
            this.setMode(
                this.state.mode === 'expanded' ? 'collapsed' : 'expanded'
            )
        );
        const separator = () => {
            const element = document.createElement('div');
            element.className = 'palette-separator';
            return element;
        };
        this.body.appendChild(promptGroup);
        this.body.appendChild(separator());
        this.body.appendChild(editGroup);
        this.body.appendChild(separator());
        this.body.appendChild(historyGroup);
        this.body.appendChild(this.collapseButton);

        // Collapsed capsule: current tool identity + polarity glyph + expand.
        this.capsule = document.createElement('button');
        this.capsule.type = 'button';
        this.capsule.className = 'palette-capsule';
        this.capsuleIcon = document.createElement('span');
        this.capsuleIcon.className = 'palette-capsule-icon';
        this.capsule.appendChild(this.capsuleIcon);
        this.capsule.addEventListener('click', () => this.setMode('expanded'));

        // Brush Size popover: shared by Paint and Erase, anchored to the
        // active edit tool. A size change never authors pixels by itself.
        this.popover = document.createElement('div');
        this.popover.className = 'palette-popover';
        this.popover.style.display = 'none';
        this.sizeInput = document.createElement('input');
        this.sizeInput.type = 'range';
        this.sizeInput.min = String(PALETTE_BRUSH_SIZE_MIN);
        this.sizeInput.max = String(PALETTE_BRUSH_SIZE_MAX);
        this.sizeInput.value = String(this.brushSizePx);
        this.sizeValue = document.createElement('span');
        this.sizeValue.className = 'palette-popover-value';
        this.sizeValue.setAttribute('aria-live', 'polite');
        this.sizeInput.addEventListener('input', () => {
            this.brushSizePx = clampBrushSize(Number(this.sizeInput.value));
            this.sizeValue.textContent = i18n.formatInteger(this.brushSizePx);
            this.options.onBrushSizeChange(this.brushSizePx);
        });
        this.popover.appendChild(this.sizeInput);
        this.popover.appendChild(this.sizeValue);

        // Outside press closes the popover (it reopens on the next explicit
        // edit-tool activation).
        window.addEventListener(
            'pointerdown',
            (event) => {
                if (
                    this.brushPopoverOpen &&
                    event.target instanceof Node &&
                    !this.dom.contains(event.target)
                ) {
                    this.closeBrushPopover();
                }
            },
            true
        );

        this.dom.appendChild(this.handle);
        this.dom.appendChild(this.body);
        this.dom.appendChild(this.capsule);
        this.dom.appendChild(this.popover);
    }

    get brushSize(): number {
        return this.brushSizePx;
    }

    get popoverOpen(): boolean {
        return this.brushPopoverOpen;
    }

    get paletteState(): FloatingPaletteState {
        return this.state;
    }

    /**
     * Target-local lifecycle: Restart, context rotation and disposal reset
     * placement, collapse, popover and transient hide to the default state.
     */
    retargetContext(targetContextId: string | null): void {
        const nextId = targetContextId ?? '';
        if (this.state.targetContextId === nextId) {
            return;
        }
        this.state = retargetFloatingPaletteState(this.state, nextId);
        this.brushPopoverOpen = false;
        this.setTransientHidden(false);
        this.renderState();
    }

    /** Dock/image resize reclamps without changing state or the active tool. */
    setSurfaceSize(width: number, height: number): void {
        this.surface = { width, height };
        this.applyPlacement();
    }

    /**
     * Space temporary hide: presentation and hit testing switch off while
     * held and restore the exact stored state on release. Stored palette
     * state is never mutated; the popover closes as a side effect.
     */
    setTransientHidden(hidden: boolean): void {
        if (this.transientHidden === hidden) {
            return;
        }
        this.transientHidden = hidden;
        if (hidden) {
            this.closeBrushPopover();
        }
        this.dom.classList.toggle('transient-hidden', hidden);
    }

    /** Non-relocating occlusion assist: dim while a captured gesture is near. */
    setGestureDimmed(dimmed: boolean): void {
        this.dom.classList.toggle('gesture-dimmed', dimmed);
    }

    closeBrushPopover(): void {
        if (!this.brushPopoverOpen) {
            return;
        }
        this.brushPopoverOpen = false;
        this.renderPopover();
    }

    /** Focus the active edit tool (after Escape closes the popover). */
    focusActiveTool(): void {
        const active = this.view?.activeTool;
        if (active !== undefined) {
            this.toolButtons.get(active)?.focus();
        }
    }

    render(view: FloatingPaletteView): void {
        const previousTool = this.view?.activeTool;
        this.view = view;
        if (view.activeTool !== previousTool) {
            // Any fresh Paint/Erase activation opens the shared Brush Size
            // popover; switching to a Prompt tool closes it.
            this.brushPopoverOpen = isPaletteEditTool(view.activeTool);
        }
        this.renderState();
    }

    private setMode(mode: 'expanded' | 'collapsed'): void {
        if (this.state.mode === mode) {
            return;
        }
        // Collapse/expand preserves position, active tool and histories.
        this.state = setPaletteMode(this.state, mode);
        if (mode === 'collapsed') {
            this.closeBrushPopover();
        }
        this.renderState();
    }

    private handleToolClick(tool: PaletteTool): void {
        // Re-clicking the active edit tool toggles the Brush Size popover.
        if (this.view?.activeTool === tool && isPaletteEditTool(tool)) {
            this.brushPopoverOpen = !this.brushPopoverOpen;
        }
        this.options.onSelectTool(tool);
        this.renderPopover();
    }

    private beginDrag(event: PointerEvent): void {
        if (event.button !== 0 || this.drag !== null) {
            return;
        }
        event.preventDefault();
        this.closeBrushPopover();
        // Pointer capture belongs to the palette for the whole gesture, so
        // image Prompt/Edit input is suppressed for this pointer.
        this.handle.setPointerCapture(event.pointerId);
        const rect = this.dom.getBoundingClientRect();
        this.drag = {
            pointerId: event.pointerId,
            grabDX: event.clientX - rect.left,
            grabDY: event.clientY - rect.top
        };
        this.dom.classList.add('dragging');
    }

    private continueDrag(event: PointerEvent): void {
        if (this.drag === null || event.pointerId !== this.drag.pointerId) {
            return;
        }
        const surfaceRect = this.dom.parentElement?.getBoundingClientRect();
        if (surfaceRect === undefined) {
            return;
        }
        this.state = dragPaletteTo(
            this.state,
            { width: surfaceRect.width, height: surfaceRect.height },
            { width: this.dom.offsetWidth, height: this.dom.offsetHeight },
            event.clientX - surfaceRect.left - this.drag.grabDX,
            event.clientY - surfaceRect.top - this.drag.grabDY
        );
        this.applyPlacement();
    }

    private endDrag(event: PointerEvent): void {
        if (this.drag === null || event.pointerId !== this.drag.pointerId) {
            return;
        }
        this.drag = null;
        this.dom.classList.remove('dragging');
        const surfaceRect = this.dom.parentElement?.getBoundingClientRect();
        if (surfaceRect !== undefined) {
            this.state = snapPalette(
                this.state,
                { width: surfaceRect.width, height: surfaceRect.height },
                { width: this.dom.offsetWidth, height: this.dom.offsetHeight }
            );
        }
        this.applyPlacement();
    }

    private renderState(): void {
        const view = this.view;
        const visible = view?.visible === true;
        this.dom.style.display = visible ? '' : 'none';
        if (view === null || !visible) {
            this.popover.style.display = 'none';
            return;
        }
        this.dom.setAttribute('aria-label', i18n.t('ai-select.palette.label'));
        this.handle.title = i18n.t('ai-select.palette.drag-handle');
        this.dom.classList.toggle('collapsed', this.state.mode === 'collapsed');

        for (const [tool, button] of this.toolButtons) {
            const availability = view.availability.get(tool);
            const label = i18n.t(TOOL_LABEL_KEYS[tool]);
            const shortcut = PALETTE_TOOL_SHORTCUTS.find(
                (entry) => entry.tool === tool
            )?.key;
            const hint =
                shortcut === undefined
                    ? label
                    : `${label} (${shortcut.toUpperCase()})`;
            const enabled = availability?.enabled === true;
            const reason = availability?.reason ?? null;
            button.disabled = !enabled;
            button.title = reason ?? hint;
            button.setAttribute(
                'aria-label',
                reason === null ? hint : `${hint}: ${reason}`
            );
            button.setAttribute('aria-disabled', String(!enabled));
            button.classList.toggle(
                'ai-select-tool-selected',
                tool === view.activeTool
            );
            button.classList.toggle('unavailable', !enabled);
        }
        this.undoButton.disabled = !view.canUndoHistory;
        this.redoButton.disabled = !view.canRedoHistory;
        this.confirmMaskButton.disabled = !view.canConfirmMask;
        this.confirmMaskButton.hidden = !view.canConfirmMask;
        const contextAction = view.contextAction ?? 'none';
        this.contextButton.hidden = contextAction === 'none';
        this.contextButton.disabled = contextAction === 'none';
        if (contextAction !== 'none') {
            this.contextButton.replaceChildren(
                createSvg(
                    contextAction === 'enter-correction'
                        ? paintSvg
                        : candidatePreviewSvg
                )
            );
        }
        this.restoreAutoMaskButton.disabled = !view.canRestoreAutoMask;
        this.clearButton.disabled = !view.canClearHistory;
        const historyPrefix =
            view.historyKind === 'mask' ? 'ai-select.mask' : 'ai-select.prompt';
        this.setActionLabel(this.undoButton, `${historyPrefix}.undo`);
        this.setActionLabel(this.redoButton, `${historyPrefix}.redo`);
        this.setActionLabel(
            this.confirmMaskButton,
            view.confirmLabelKey ?? 'ai-select.mask.confirm'
        );
        this.setActionLabel(
            this.contextButton,
            view.contextLabelKey ?? 'ai-select.candidate.fix-result'
        );
        this.setActionLabel(
            this.restoreAutoMaskButton,
            'ai-select.mask.restore-auto'
        );
        this.setActionLabel(this.clearButton, `${historyPrefix}.clear`);

        const collapseKey =
            this.state.mode === 'expanded'
                ? 'ai-select.palette.collapse'
                : 'ai-select.palette.expand';
        this.setActionLabel(this.collapseButton, collapseKey);

        // Capsule mirrors the active tool identity and its polarity glyph;
        // clicking it expands without changing the tool.
        this.capsule.dataset.tool = view.activeTool;
        this.capsuleIcon.replaceChildren(
            createSvg(TOOL_ICONS[view.activeTool])
        );
        const toolLabel = i18n.t(TOOL_LABEL_KEYS[view.activeTool]);
        const expandLabel = `${i18n.t('ai-select.palette.expand')} · ${toolLabel}`;
        this.capsule.title = expandLabel;
        this.capsule.setAttribute('aria-label', expandLabel);

        this.sizeInput.setAttribute(
            'aria-label',
            i18n.t('ai-select.edit.brush-size')
        );
        this.sizeValue.textContent = i18n.formatInteger(this.brushSizePx);
        if (this.sizeInput.value !== String(this.brushSizePx)) {
            this.sizeInput.value = String(this.brushSizePx);
        }

        this.applyPlacement();
        this.renderPopover();
    }

    private setActionLabel(button: HTMLButtonElement, key: string): void {
        const label = i18n.t(key);
        button.title = label;
        button.setAttribute('aria-label', label);
    }

    private renderPopover(): void {
        const view = this.view;
        const activeTool = view?.activeTool;
        const anchorButton =
            activeTool === undefined
                ? undefined
                : this.toolButtons.get(activeTool);
        const show =
            this.brushPopoverOpen &&
            view?.visible === true &&
            this.state.mode === 'expanded' &&
            !this.transientHidden &&
            activeTool !== undefined &&
            isPaletteEditTool(activeTool) &&
            anchorButton !== undefined;
        if (!show || anchorButton === undefined) {
            this.popover.style.display = 'none';
            return;
        }
        this.popover.style.display = '';
        const paletteRect = resolvePaletteRect(this.state, this.surface, {
            width: this.dom.offsetWidth,
            height: this.dom.offsetHeight
        });
        // Anchor rect in surface coordinates: palette origin plus the button
        // offset inside the palette.
        const anchor = {
            left: paletteRect.left + anchorButton.offsetLeft,
            top: paletteRect.top + anchorButton.offsetTop,
            width: anchorButton.offsetWidth,
            height: anchorButton.offsetHeight
        };
        const placed = placeBrushSizePopover(
            anchor,
            {
                width: this.popover.offsetWidth || 180,
                height: this.popover.offsetHeight || 36
            },
            this.surface
        );
        // The popover is a child of the palette: convert surface coordinates
        // back into palette-relative offsets.
        this.popover.style.left = `${placed.left - paletteRect.left}px`;
        this.popover.style.top = `${placed.top - paletteRect.top}px`;
        this.popover.dataset.placement = placed.placement;
    }

    private applyPlacement(): void {
        if (
            this.view?.visible !== true ||
            this.surface.width <= 0 ||
            this.surface.height <= 0
        ) {
            return;
        }
        const rect = resolvePaletteRect(this.state, this.surface, {
            width: this.dom.offsetWidth,
            height: this.dom.offsetHeight
        });
        this.dom.style.left = `${rect.left}px`;
        this.dom.style.top = `${rect.top}px`;
    }
}
