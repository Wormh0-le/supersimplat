import { Color, Vec3 } from 'playcanvas';

import type { CameraBinding } from './ai-select/camera-binding';
import { Element, ElementType } from './element';

type FrustumLine = readonly [Vec3, Vec3];

const frustumColor = new Color(0.2, 0.85, 1.0, 0.9);

const transformPoint = (
    cameraToWorld: readonly number[],
    x: number,
    y: number,
    z: number
): Vec3 => {
    return new Vec3(
        cameraToWorld[0] * x + cameraToWorld[1] * y + cameraToWorld[2] * z + cameraToWorld[3],
        cameraToWorld[4] * x + cameraToWorld[5] * y + cameraToWorld[6] * z + cameraToWorld[7],
        cameraToWorld[8] * x + cameraToWorld[9] * y + cameraToWorld[10] * z + cameraToWorld[11]
    );
};

/**
 * Produce a display-only frustum using the exact immutable raster binding.
 * The chosen depth changes only its visible scale; pose and projective rays
 * remain those sent to the Companion.
 */
export const anchorFrustumLines = (
    binding: CameraBinding,
    depth: number
): readonly FrustumLine[] => {
    const { projection, cameraToWorld } = binding;
    const origin = transformPoint(cameraToWorld, 0, 0, 0);
    const cornerPixels: readonly [number, number][] = [
        [0, 0],
        [projection.width, 0],
        [projection.width, projection.height],
        [0, projection.height]
    ];
    const corners = cornerPixels.map(([x, y]) => transformPoint(
        cameraToWorld,
        ((x - projection.cx) * depth) / projection.fx,
        ((y - projection.cy) * depth) / projection.fy,
        depth
    ));
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

/** Draws the immutable Anchor camera, without observing or moving the editor camera. */
export class AnchorFrustum extends Element {
    private binding: CameraBinding | null = null;

    constructor() {
        super(ElementType.debug);
    }

    setCameraBinding(binding: CameraBinding | null): void {
        this.binding = binding;
        if (this.scene) {
            this.scene.forceRender = true;
        }
    }

    onPreRender(): void {
        if (this.binding === null) {
            return;
        }
        const { near, far } = this.binding.projection;
        const displayDepth = Math.min(far, Math.max(near * 8, 0.05));
        anchorFrustumLines(this.binding, displayDepth).forEach(([start, end]) => {
            this.scene.app.drawLine(start, end, frustumColor, true, this.scene.gizmoLayer);
        });
    }
}
