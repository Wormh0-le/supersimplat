import { Color, Vec3 } from 'playcanvas';

import type { CameraBinding } from './ai-select/camera-binding';
import {
    generatedFrustumDisplayDepth,
    generatedFrustumLines
} from './ai-select/generated-frustum-picking';
import { Element, ElementType } from './element';

export interface GeneratedFrustumView {
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
    readonly selected: boolean;
}

const frustumColor = new Color(0.35, 0.9, 0.55, 0.7);
const selectedFrustumColor = new Color(0.55, 1.0, 0.35, 1.0);

/**
 * Draws every Generated View frustum from its exact immutable CameraBinding.
 * Generated Frustums are read-only: this element never observes or moves the
 * Editor Camera and exposes no manipulation gizmo (Final Spec v1.0 §21).
 */
export class GeneratedViewFrustums extends Element {
    private views: readonly GeneratedFrustumView[] = [];
    private visible = false;

    constructor() {
        super(ElementType.debug);
    }

    setViews(views: readonly GeneratedFrustumView[]): void {
        this.views = views;
        if (this.scene) {
            this.scene.forceRender = true;
        }
    }

    setVisible(visible: boolean): void {
        if (this.visible === visible) {
            return;
        }
        this.visible = visible;
        if (this.scene) {
            this.scene.forceRender = true;
        }
    }

    onPreRender(): void {
        if (!this.visible) {
            return;
        }
        for (const view of this.views) {
            const depth = generatedFrustumDisplayDepth(view.cameraBinding);
            const color = view.selected ? selectedFrustumColor : frustumColor;
            for (const [start, end] of generatedFrustumLines(
                view.cameraBinding,
                depth
            )) {
                this.scene.app.drawLine(
                    new Vec3(start[0], start[1], start[2]),
                    new Vec3(end[0], end[1], end[2]),
                    color,
                    true,
                    this.scene.gizmoLayer
                );
            }
        }
    }
}
