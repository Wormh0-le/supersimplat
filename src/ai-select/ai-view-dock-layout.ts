export interface AIViewDockColumns {
    readonly navigator: boolean;
    readonly inspector: boolean;
}

export type AIViewToolLayout = 'vertical' | 'short-vertical' | 'horizontal';

const THREE_COLUMN_BREAKPOINT_PX = 1180;
const NAVIGATOR_BREAKPOINT_PX = 900;
const SPACIOUS_DOCK_BREAKPOINT_PX = 1600;
const SHORT_TOOL_RAIL_HEIGHT_PX = 420;
const MINIMUM_SHORT_TOOL_RAIL_HEIGHT_PX = 310;
export const AI_VIEW_DOCK_DEFAULT_HEIGHT_PX = 420;
export const AI_VIEW_DOCK_MINIMUM_HEIGHT_PX = 300;
export const AI_VIEW_DOCK_EDITOR_CLEARANCE_PX = 160;

/** Responsive defaults; an explicit trigger choice always wins and pushes. */
export const resolveAIViewDockColumns = (
    width: number,
    explicit: Partial<AIViewDockColumns> = {}
): AIViewDockColumns => {
    if (!Number.isFinite(width) || width < 0) {
        throw new Error(
            'AI View Dock width must be a finite non-negative value.'
        );
    }
    return Object.freeze({
        navigator: explicit.navigator ?? width >= NAVIGATOR_BREAKPOINT_PX,
        inspector: explicit.inspector ?? width >= THREE_COLUMN_BREAKPOINT_PX
    });
};

/** Keep every authoring control reachable without covering the image. */
export const resolveAIViewToolLayout = (input: {
    readonly width: number;
    readonly canvasHeight: number;
}): AIViewToolLayout => {
    if (
        !Number.isFinite(input.width) ||
        input.width < 0 ||
        !Number.isFinite(input.canvasHeight) ||
        input.canvasHeight < 0
    ) {
        throw new Error(
            'AI View Tool Rail dimensions must be finite non-negative values.'
        );
    }
    if (
        input.width <= THREE_COLUMN_BREAKPOINT_PX ||
        input.canvasHeight < MINIMUM_SHORT_TOOL_RAIL_HEIGHT_PX
    ) {
        return 'horizontal';
    }
    if (input.canvasHeight >= SHORT_TOOL_RAIL_HEIGHT_PX) {
        return 'vertical';
    }
    return input.width >= SPACIOUS_DOCK_BREAKPOINT_PX
        ? 'short-vertical'
        : 'horizontal';
};

/** Aspect-derived ideal width; spare horizontal space stays outside the image. */
export const resolveAIViewWorkAreaWidth = (input: {
    readonly availableWidth: number;
    readonly availableHeight: number;
    readonly imageWidth: number;
    readonly imageHeight: number;
}): number => {
    const values = [
        input.availableWidth,
        input.availableHeight,
        input.imageWidth,
        input.imageHeight
    ];
    if (values.some((value) => !Number.isFinite(value) || value <= 0)) {
        return 0;
    }
    return Math.round(
        Math.min(
            input.availableWidth,
            input.availableHeight * (input.imageWidth / input.imageHeight)
        )
    );
};

export const clampAIViewDockHeight = (
    requestedHeight: number | undefined,
    editorHeight: number
): number => {
    const maximumHeight = Math.max(
        AI_VIEW_DOCK_MINIMUM_HEIGHT_PX,
        editorHeight - AI_VIEW_DOCK_EDITOR_CLEARANCE_PX
    );
    const requested = requestedHeight ?? AI_VIEW_DOCK_DEFAULT_HEIGHT_PX;
    return Math.round(
        Math.max(
            AI_VIEW_DOCK_MINIMUM_HEIGHT_PX,
            Math.min(maximumHeight, requested)
        )
    );
};
