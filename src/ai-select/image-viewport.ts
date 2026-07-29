export interface ImageViewportRect {
    readonly left: number;
    readonly top: number;
    readonly width: number;
    readonly height: number;
}

export interface ImagePixel {
    readonly xPx: number;
    readonly yPx: number;
}

const isPositiveFinite = (value: number): boolean =>
    Number.isFinite(value) && value > 0;

/** Fit one authoritative image into a viewport without crop or distortion. */
export const fitImageRect = (
    viewportWidth: number,
    viewportHeight: number,
    imageWidth: number,
    imageHeight: number
): ImageViewportRect | null => {
    if (
        !isPositiveFinite(viewportWidth) ||
        !isPositiveFinite(viewportHeight) ||
        !isPositiveFinite(imageWidth) ||
        !isPositiveFinite(imageHeight)
    ) {
        return null;
    }
    const scale = Math.min(
        viewportWidth / imageWidth,
        viewportHeight / imageHeight
    );
    const width = imageWidth * scale;
    const height = imageHeight * scale;
    return Object.freeze({
        left: (viewportWidth - width) / 2,
        top: (viewportHeight - height) / 2,
        width,
        height
    });
};

/**
 * Map through the same fitted rectangle used by RGB and every overlay.
 * The neutral letterbox outside this rectangle is deliberately non-interactive.
 */
export const mapClientPointToImagePixel = (
    clientX: number,
    clientY: number,
    rect: ImageViewportRect,
    imageWidth: number,
    imageHeight: number
): ImagePixel | null => {
    if (
        ![clientX, clientY, rect.left, rect.top].every(Number.isFinite) ||
        !isPositiveFinite(rect.width) ||
        !isPositiveFinite(rect.height) ||
        !Number.isSafeInteger(imageWidth) ||
        !Number.isSafeInteger(imageHeight) ||
        imageWidth <= 0 ||
        imageHeight <= 0 ||
        clientX < rect.left ||
        clientY < rect.top ||
        clientX >= rect.left + rect.width ||
        clientY >= rect.top + rect.height
    ) {
        return null;
    }
    return Object.freeze({
        xPx: Math.floor(((clientX - rect.left) / rect.width) * imageWidth),
        yPx: Math.floor(((clientY - rect.top) / rect.height) * imageHeight)
    });
};
