/**
 * Floating Prompt/Edit Palette geometry and lifecycle (Ticket 07B, DG-22).
 *
 * This module owns pure presentation state for the draggable, collapsible
 * palette over the fitted authoritative image. Palette position/mode never
 * enters PromptState, Mask history, model requests, Evidence or Candidate
 * identity; every function here is free of artifact references.
 */

export type PaletteMode = 'expanded' | 'collapsed';
export type PaletteEdge = 'free' | 'top' | 'right' | 'bottom' | 'left';

export interface FloatingPaletteState {
    readonly targetContextId: string;
    readonly mode: PaletteMode;
    readonly edge: PaletteEdge;
    readonly xRatio: number;
    readonly yRatio: number;
}

export interface PaletteSize {
    readonly width: number;
    readonly height: number;
}

export interface PaletteRect {
    readonly left: number;
    readonly top: number;
    readonly width: number;
    readonly height: number;
}

export interface BrushPopoverPlacement {
    readonly left: number;
    readonly top: number;
    readonly placement: 'above' | 'below';
}

/**
 * Versioned snap threshold: releasing a drag within this distance of an image
 * edge anchors the palette to that edge. Ties resolve through
 * PALETTE_SNAP_PRIORITY so snapping is deterministic.
 */
export const PALETTE_SNAP_THRESHOLD_PX = 24;
export const PALETTE_SNAP_PRIORITY: readonly PaletteEdge[] = [
    'top',
    'right',
    'bottom',
    'left'
];

export const PALETTE_BRUSH_SIZE_MIN = 1;
export const PALETTE_BRUSH_SIZE_MAX = 64;
export const PALETTE_BRUSH_SIZE_DEFAULT = 8;

/**
 * The exact v1 tool inventory (Final Spec v1.3 §8). Negative Box, Prompt
 * Brush, Mask Constraints and Text Prompt are absent — not disabled
 * placeholders. Paint/Erase are the only Brush Size consumers.
 */
export const PALETTE_PROMPT_TOOLS = [
    'positive-point',
    'negative-point',
    'positive-box'
] as const;
export const PALETTE_EDIT_TOOLS = ['paint', 'erase'] as const;
export const PALETTE_TOOLS = [
    ...PALETTE_PROMPT_TOOLS,
    ...PALETTE_EDIT_TOOLS
] as const;
export type PalettePromptTool = (typeof PALETTE_PROMPT_TOOLS)[number];
export type PaletteEditTool = (typeof PALETTE_EDIT_TOOLS)[number];
export type PaletteTool = (typeof PALETTE_TOOLS)[number];

/** Paint/Erase are the edit group — the only Brush Size consumers. */
export const isPaletteEditTool = (tool: PaletteTool): tool is PaletteEditTool =>
    PALETTE_EDIT_TOOLS.includes(tool as PaletteEditTool);

/**
 * Dock-focus-scoped tool shortcuts. Conflict audit: the global editor binds
 * 1/2/3 (move/rotate/scale tools), B (brush selection) and Space (timeline
 * play) through ShortcutManager, which only fires when the event target is
 * document.body. Palette shortcuts are handled on the Anchor Dock element and
 * skip text-entry/button targets, so neither mapping shadows the other.
 */
export const PALETTE_TOOL_SHORTCUTS: readonly {
    readonly key: string;
    readonly tool: PaletteTool;
}[] = [
    { key: '1', tool: 'positive-point' },
    { key: '2', tool: 'negative-point' },
    { key: '3', tool: 'positive-box' },
    { key: 'b', tool: 'paint' },
    { key: 'e', tool: 'erase' }
];

export const paletteToolForShortcutKey = (key: string): PaletteTool | null => {
    if (typeof key !== 'string' || key.length !== 1) {
        return null;
    }
    const lowered = key.toLowerCase();
    const match = PALETTE_TOOL_SHORTCUTS.find((entry) => entry.key === lowered);
    return match?.tool ?? null;
};

/** Default: expanded, bottom edge, horizontally centered. */
export const createFloatingPaletteState = (
    targetContextId: string
): FloatingPaletteState => ({
    targetContextId,
    mode: 'expanded',
    edge: 'bottom',
    xRatio: 0.5,
    yRatio: 1
});

const clamp01 = (value: number): number =>
    Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;

const isValidSize = (size: PaletteSize): boolean =>
    Number.isFinite(size.width) &&
    Number.isFinite(size.height) &&
    size.width > 0 &&
    size.height > 0;

/**
 * Resolve the stored ratios into a pixel rect that keeps the full palette
 * inside the fitted image surface. This single resolver is used after drag,
 * resize, collapse/expand and locale changes, so reclamping never changes
 * the stored state, the active tool, or either history.
 */
export const resolvePaletteRect = (
    state: FloatingPaletteState,
    surface: PaletteSize,
    palette: PaletteSize
): PaletteRect => {
    const surfaceWidth = Number.isFinite(surface.width)
        ? Math.max(0, surface.width)
        : 0;
    const surfaceHeight = Number.isFinite(surface.height)
        ? Math.max(0, surface.height)
        : 0;
    const width = Number.isFinite(palette.width)
        ? Math.max(0, palette.width)
        : 0;
    const height = Number.isFinite(palette.height)
        ? Math.max(0, palette.height)
        : 0;
    const maxLeft = Math.max(0, surfaceWidth - width);
    const maxTop = Math.max(0, surfaceHeight - height);
    return {
        left: clamp01(state.xRatio) * maxLeft,
        top: clamp01(state.yRatio) * maxTop,
        width,
        height
    };
};

/**
 * Continuous drag: clamp the requested top-left corner into the fitted rect
 * and record free placement. Edge snapping happens on release via snapPalette.
 * Invalid geometry leaves the state untouched (fail-closed).
 */
export const dragPaletteTo = (
    state: FloatingPaletteState,
    surface: PaletteSize,
    palette: PaletteSize,
    leftPx: number,
    topPx: number
): FloatingPaletteState => {
    if (
        !isValidSize(surface) ||
        !isValidSize(palette) ||
        !Number.isFinite(leftPx) ||
        !Number.isFinite(topPx)
    ) {
        return state;
    }
    const maxLeft = Math.max(0, surface.width - palette.width);
    const maxTop = Math.max(0, surface.height - palette.height);
    const left = Math.min(maxLeft, Math.max(0, leftPx));
    const top = Math.min(maxTop, Math.max(0, topPx));
    return {
        ...state,
        edge: 'free',
        xRatio: maxLeft > 0 ? left / maxLeft : 0,
        yRatio: maxTop > 0 ? top / maxTop : 0
    };
};

/**
 * Release snap: when the palette is within PALETTE_SNAP_THRESHOLD_PX of an
 * image edge, anchor it exactly to the nearest edge (ties resolve through the
 * versioned priority order). The non-snapped axis keeps its dragged ratio.
 */
export const snapPalette = (
    state: FloatingPaletteState,
    surface: PaletteSize,
    palette: PaletteSize
): FloatingPaletteState => {
    if (!isValidSize(surface) || !isValidSize(palette)) {
        return state;
    }
    const rect = resolvePaletteRect(state, surface, palette);
    const maxLeft = Math.max(0, surface.width - palette.width);
    const maxTop = Math.max(0, surface.height - palette.height);
    const distances: Record<PaletteEdge, number> = {
        free: Number.POSITIVE_INFINITY,
        left: rect.left,
        right: maxLeft - rect.left,
        top: rect.top,
        bottom: maxTop - rect.top
    };
    let best: PaletteEdge | null = null;
    let bestDistance = PALETTE_SNAP_THRESHOLD_PX;
    for (const edge of PALETTE_SNAP_PRIORITY) {
        const distance = distances[edge];
        if (distance <= bestDistance && distance >= 0) {
            if (best === null || distance < bestDistance) {
                best = edge;
                bestDistance = distance;
            }
        }
    }
    if (best === null) {
        return state;
    }
    return {
        ...state,
        edge: best,
        xRatio: best === 'left' ? 0 : best === 'right' ? 1 : state.xRatio,
        yRatio: best === 'top' ? 0 : best === 'bottom' ? 1 : state.yRatio
    };
};

/**
 * Collapse/expand only flips the mode. Position ratios and edge survive, and
 * the next resolvePaletteRect reclamps the new palette size inside the image.
 * The active Prompt/Edit tool and both histories are untouched.
 */
export const setPaletteMode = (
    state: FloatingPaletteState,
    mode: PaletteMode
): FloatingPaletteState => ({
    ...state,
    mode
});

/** Restore the default bottom-center placement; the mode is preserved. */
export const resetPalettePlacement = (
    state: FloatingPaletteState
): FloatingPaletteState => ({
    ...state,
    edge: 'bottom',
    xRatio: 0.5,
    yRatio: 1
});

/**
 * Palette state is scoped to the current Target Context: it survives Prompt
 * revisions, Retry, tool changes and Dock resize, and resets on Restart,
 * targetContextId rotation, scene/target replacement and AI Select disposal
 * (an empty id represents the disposed state).
 */
export const retargetFloatingPaletteState = (
    state: FloatingPaletteState,
    targetContextId: string
): FloatingPaletteState =>
    state.targetContextId === targetContextId
        ? state
        : createFloatingPaletteState(targetContextId);

/** Paint and Erase share one contextual Brush Size; clamp it fail-closed. */
export const clampBrushSize = (value: number): number => {
    if (!Number.isFinite(value)) {
        return PALETTE_BRUSH_SIZE_DEFAULT;
    }
    return Math.min(
        PALETTE_BRUSH_SIZE_MAX,
        Math.max(PALETTE_BRUSH_SIZE_MIN, Math.round(value))
    );
};

/**
 * Place the Brush Size popover relative to the active edit tool button:
 * anchored above by default, flipping below when above does not fit, always
 * fully clamped inside the fitted surface. Only when neither side fits (a
 * degenerate tiny surface) does it take the side with more room. Placement
 * changes presentation only; changing the size never authors pixels.
 */
export const placeBrushSizePopover = (
    anchor: PaletteRect,
    popover: PaletteSize,
    surface: PaletteSize,
    gapPx = 6
): BrushPopoverPlacement => {
    const surfaceWidth = Number.isFinite(surface.width)
        ? Math.max(0, surface.width)
        : 0;
    const surfaceHeight = Number.isFinite(surface.height)
        ? Math.max(0, surface.height)
        : 0;
    const maxLeft = Math.max(0, surfaceWidth - popover.width);
    const maxTop = Math.max(0, surfaceHeight - popover.height);
    const spaceAbove = Math.max(0, anchor.top);
    const spaceBelow = Math.max(
        0,
        surfaceHeight - (anchor.top + anchor.height)
    );
    const fitsAbove = anchor.top - gapPx - popover.height >= 0;
    const fitsBelow =
        anchor.top + anchor.height + gapPx + popover.height <= surfaceHeight;
    // A side is safe only when the popover fits there without covering the
    // anchor; the more-room side is the deterministic last resort.
    const placement = fitsAbove
        ? 'above'
        : fitsBelow
          ? 'below'
          : spaceAbove >= spaceBelow
            ? 'above'
            : 'below';
    const unclampedTop =
        placement === 'above'
            ? anchor.top - gapPx - popover.height
            : anchor.top + anchor.height + gapPx;
    return {
        left: Math.min(
            maxLeft,
            Math.max(0, anchor.left + anchor.width / 2 - popover.width / 2)
        ),
        top: Math.min(maxTop, Math.max(0, unclampedTop)),
        placement
    };
};
