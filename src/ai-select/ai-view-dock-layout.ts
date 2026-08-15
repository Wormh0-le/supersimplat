export interface AIViewDockColumns {
    readonly navigator: boolean;
    readonly inspector: boolean;
}

const THREE_COLUMN_BREAKPOINT_PX = 1180;
const NAVIGATOR_BREAKPOINT_PX = 900;
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
