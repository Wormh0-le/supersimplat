import type { CameraBinding } from './camera-binding';

/**
 * The picking math behind Generated Frustum selection (Final Spec v1.0 §§21–22,
 * retained by v1.1). It is deliberately free of renderer dependencies: the
 * editor supplies a world→screen projector, and Generated Frustums stay
 * read-only — selection never mutates a CameraBinding.
 */
export interface GeneratedFrustumPickTarget {
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
}

export interface FrustumScreenPoint {
    readonly x: number;
    readonly y: number;
    readonly inFront: boolean;
}

export type GeneratedFrustumProjector = (
    x: number,
    y: number,
    z: number
) => FrustumScreenPoint;

type FrustumLine = readonly [readonly number[], readonly number[]];

const transformPoint = (
    cameraToWorld: readonly number[],
    x: number,
    y: number,
    z: number
): readonly number[] => {
    return [
        cameraToWorld[0] * x +
            cameraToWorld[1] * y +
            cameraToWorld[2] * z +
            cameraToWorld[3],
        cameraToWorld[4] * x +
            cameraToWorld[5] * y +
            cameraToWorld[6] * z +
            cameraToWorld[7],
        cameraToWorld[8] * x +
            cameraToWorld[9] * y +
            cameraToWorld[10] * z +
            cameraToWorld[11]
    ];
};

/** The display depth shared by drawing and picking so they hit-test identically. */
export const generatedFrustumDisplayDepth = (
    binding: CameraBinding
): number => {
    const { near, far } = binding.projection;
    return Math.min(far, Math.max(near * 8, 0.05));
};

/**
 * The frustum lines of the exact immutable raster binding, in world space.
 * The chosen depth changes only their visible scale; pose and projective
 * rays remain those sent to the Companion.
 */
export const generatedFrustumLines = (
    binding: CameraBinding,
    depth: number
): readonly FrustumLine[] => {
    const { projection, cameraToWorld } = binding;
    const origin = transformPoint(cameraToWorld, 0, 0, 0);
    const cornerPixels: readonly (readonly [number, number])[] = [
        [0, 0],
        [projection.width, 0],
        [projection.width, projection.height],
        [0, projection.height]
    ];
    const corners = cornerPixels.map(([x, y]) =>
        transformPoint(
            cameraToWorld,
            ((x - projection.cx) * depth) / projection.fx,
            ((y - projection.cy) * depth) / projection.fy,
            depth
        )
    );
    return [
        [origin, corners[0]],
        [origin, corners[1]],
        [origin, corners[2]],
        [origin, corners[3]],
        [corners[0], corners[1]],
        [corners[1], corners[2]],
        [corners[2], corners[3]],
        [corners[3], corners[0]]
    ];
};

const segmentDistance = (
    px: number,
    py: number,
    ax: number,
    ay: number,
    bx: number,
    by: number
): number => {
    const dx = bx - ax;
    const dy = by - ay;
    const lengthSquared = dx * dx + dy * dy;
    const t =
        lengthSquared === 0
            ? 0
            : Math.max(
                  0,
                  Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared)
              );
    const cx = ax + t * dx;
    const cy = ay + t * dy;
    return Math.hypot(px - cx, py - cy);
};

/**
 * Return the viewId of the nearest Generated Frustum within `maxDistance`
 * (in the projector's normalized screen units), or null. Segments with an
 * endpoint behind the editor camera never win.
 */
export const pickGeneratedViewFrustum = (
    targets: readonly GeneratedFrustumPickTarget[],
    projector: GeneratedFrustumProjector,
    x: number,
    y: number,
    maxDistance: number
): string | null => {
    let best: string | null = null;
    let bestDistance = maxDistance;
    for (const target of targets) {
        const depth = generatedFrustumDisplayDepth(target.cameraBinding);
        for (const [start, end] of generatedFrustumLines(
            target.cameraBinding,
            depth
        )) {
            const projectedStart = projector(start[0], start[1], start[2]);
            const projectedEnd = projector(end[0], end[1], end[2]);
            if (!projectedStart.inFront || !projectedEnd.inFront) {
                continue;
            }
            const distance = segmentDistance(
                x,
                y,
                projectedStart.x,
                projectedStart.y,
                projectedEnd.x,
                projectedEnd.y
            );
            if (distance < bestDistance) {
                bestDistance = distance;
                best = target.viewId;
            }
        }
    }
    return best;
};
