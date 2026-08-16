export interface AIViewDockColumns {
    readonly navigator: boolean;
    readonly inspector: boolean;
}

export interface AIViewDockPreferences {
    readonly navigatorWidth: number;
    readonly inspectorWidth: number;
    readonly navigatorExpanded: boolean;
    readonly inspectorExpanded: boolean;
}

export type AIViewDockSidebar = 'navigator' | 'inspector';

export type AIViewImageZoomState =
    | { readonly mode: 'auto' }
    | {
          readonly mode: 'manual';
          readonly width: number;
      };

export interface AIViewImageRect {
    readonly left: number;
    readonly top: number;
    readonly width: number;
    readonly height: number;
}

const THREE_COLUMN_BREAKPOINT_PX = 1180;
const NAVIGATOR_BREAKPOINT_PX = 900;
const DOCK_COLUMN_GAP_PX = 8;
export const AI_VIEW_NAVIGATOR_DEFAULT_WIDTH_PX = 220;
export const AI_VIEW_NAVIGATOR_MINIMUM_WIDTH_PX = 180;
export const AI_VIEW_NAVIGATOR_MAXIMUM_WIDTH_PX = 280;
export const AI_VIEW_INSPECTOR_DEFAULT_WIDTH_PX = 280;
export const AI_VIEW_INSPECTOR_MINIMUM_WIDTH_PX = 240;
export const AI_VIEW_INSPECTOR_MAXIMUM_WIDTH_PX = 360;
export const AI_VIEW_IMAGE_SAFETY_MARGIN_PX = 12;
export const AI_VIEW_DOCK_DEFAULT_HEIGHT_PX = 420;
export const AI_VIEW_DOCK_MINIMUM_HEIGHT_PX = 300;
export const AI_VIEW_DOCK_EDITOR_CLEARANCE_PX = 160;

export const AI_VIEW_DOCK_DEFAULT_PREFERENCES: AIViewDockPreferences =
    Object.freeze({
        navigatorWidth: AI_VIEW_NAVIGATOR_DEFAULT_WIDTH_PX,
        inspectorWidth: AI_VIEW_INSPECTOR_DEFAULT_WIDTH_PX,
        navigatorExpanded: true,
        inspectorExpanded: true
    });

const finiteNumber = (value: unknown): value is number =>
    typeof value === 'number' && Number.isFinite(value);

const clamp = (value: number, minimum: number, maximum: number): number =>
    Math.round(Math.max(minimum, Math.min(maximum, value)));

export const parseAIViewDockPreferences = (
    serialized: string | null
): AIViewDockPreferences => {
    if (serialized === null || serialized.length === 0) {
        return AI_VIEW_DOCK_DEFAULT_PREFERENCES;
    }
    try {
        const value = JSON.parse(serialized) as Record<string, unknown>;
        if (
            value === null ||
            typeof value !== 'object' ||
            !finiteNumber(value.navigatorWidth) ||
            !finiteNumber(value.inspectorWidth) ||
            typeof value.navigatorExpanded !== 'boolean' ||
            typeof value.inspectorExpanded !== 'boolean'
        ) {
            return AI_VIEW_DOCK_DEFAULT_PREFERENCES;
        }
        return Object.freeze({
            navigatorWidth: clamp(
                value.navigatorWidth,
                AI_VIEW_NAVIGATOR_MINIMUM_WIDTH_PX,
                AI_VIEW_NAVIGATOR_MAXIMUM_WIDTH_PX
            ),
            inspectorWidth: clamp(
                value.inspectorWidth,
                AI_VIEW_INSPECTOR_MINIMUM_WIDTH_PX,
                AI_VIEW_INSPECTOR_MAXIMUM_WIDTH_PX
            ),
            navigatorExpanded: value.navigatorExpanded,
            inspectorExpanded: value.inspectorExpanded
        });
    } catch {
        return AI_VIEW_DOCK_DEFAULT_PREFERENCES;
    }
};

export const serializeAIViewDockPreferences = (
    value: AIViewDockPreferences
): string => JSON.stringify(value);

export const setAIViewDockSidebarExpanded = (
    preferences: AIViewDockPreferences,
    sidebar: AIViewDockSidebar,
    expanded: boolean
): AIViewDockPreferences =>
    Object.freeze({
        ...preferences,
        ...(sidebar === 'navigator'
            ? { navigatorExpanded: expanded }
            : { inspectorExpanded: expanded })
    });

export const resizeAIViewDockSidebar = (
    preferences: AIViewDockPreferences,
    sidebar: AIViewDockSidebar,
    width: number
): AIViewDockPreferences =>
    Object.freeze({
        ...preferences,
        ...(sidebar === 'navigator'
            ? {
                  navigatorWidth: clamp(
                      width,
                      AI_VIEW_NAVIGATOR_MINIMUM_WIDTH_PX,
                      AI_VIEW_NAVIGATOR_MAXIMUM_WIDTH_PX
                  )
              }
            : {
                  inspectorWidth: clamp(
                      width,
                      AI_VIEW_INSPECTOR_MINIMUM_WIDTH_PX,
                      AI_VIEW_INSPECTOR_MAXIMUM_WIDTH_PX
                  )
              })
    });

/** Responsive safety always keeps Work Area resident, honoring saved collapse. */
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
        navigator:
            (explicit.navigator ?? true) && width >= NAVIGATOR_BREAKPOINT_PX,
        inspector:
            (explicit.inspector ?? true) && width >= THREE_COLUMN_BREAKPOINT_PX
    });
};

export const resolveAIViewDockLayout = (
    width: number,
    preferences: AIViewDockPreferences = AI_VIEW_DOCK_DEFAULT_PREFERENCES
): {
    readonly navigator: boolean;
    readonly navigatorWidth: number;
    readonly inspector: boolean;
    readonly inspectorWidth: number;
    readonly workAreaWidth: number;
} => {
    const columns = resolveAIViewDockColumns(width, {
        navigator: preferences.navigatorExpanded,
        inspector: preferences.inspectorExpanded
    });
    const navigatorWidth = columns.navigator ? preferences.navigatorWidth : 0;
    const inspectorWidth = columns.inspector ? preferences.inspectorWidth : 0;
    const visibleSidebars =
        Number(columns.navigator) + Number(columns.inspector);
    return Object.freeze({
        navigator: columns.navigator,
        navigatorWidth,
        inspector: columns.inspector,
        inspectorWidth,
        workAreaWidth: Math.max(
            0,
            Math.round(
                width -
                    navigatorWidth -
                    inspectorWidth -
                    visibleSidebars * DOCK_COLUMN_GAP_PX
            )
        )
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

/** Automatic fit is contained with margin; manual dimensions survive resize. */
export const resolveAIViewImageRect = (
    input: {
        readonly viewportWidth: number;
        readonly viewportHeight: number;
        readonly imageWidth: number;
        readonly imageHeight: number;
    },
    zoom: AIViewImageZoomState
): AIViewImageRect | null => {
    const values = [
        input.viewportWidth,
        input.viewportHeight,
        input.imageWidth,
        input.imageHeight
    ];
    if (values.some((value) => !Number.isFinite(value) || value <= 0)) {
        return null;
    }
    let width: number;
    let height: number;
    if (
        zoom.mode === 'manual' &&
        Number.isFinite(zoom.width) &&
        zoom.width > 0
    ) {
        width = zoom.width;
        // Preserve the user's on-screen zoom width across layout changes,
        // while always deriving height from the currently inspected RGB.
        // A View switch can therefore never reuse another image's aspect.
        height = width * (input.imageHeight / input.imageWidth);
    } else {
        const availableWidth = Math.max(
            1,
            input.viewportWidth - AI_VIEW_IMAGE_SAFETY_MARGIN_PX * 2
        );
        const availableHeight = Math.max(
            1,
            input.viewportHeight - AI_VIEW_IMAGE_SAFETY_MARGIN_PX * 2
        );
        const scale = Math.min(
            availableWidth / input.imageWidth,
            availableHeight / input.imageHeight
        );
        width = Math.round(input.imageWidth * scale);
        height = Math.round(input.imageHeight * scale);
    }
    return Object.freeze({
        left: Math.round((input.viewportWidth - width) / 2),
        top: Math.round((input.viewportHeight - height) / 2),
        width,
        height
    });
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
