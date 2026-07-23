import type { AISelectAnchorState } from './anchor-controller';
import { cameraToWorldFromPlayCanvasWorldTransform } from './camera-binding';
import type { CameraInspectionState } from './camera-inspection';

export interface AnchorFrustumManipulationTarget {
    moveAnchorFrustum(cameraToWorld: readonly number[]): void;
    endAnchorManipulation(): Promise<void>;
}

/** A suspended target remains inspectable but its frustum is not editable. */
export const canManipulateAnchorFrustum = (
    anchorState: AISelectAnchorState | undefined,
    inspectionState: CameraInspectionState | undefined
): boolean => {
    return Boolean(
        inspectionState?.mode === 'active' &&
        anchorState?.context?.lifecycle === 'active' &&
        anchorState?.anchor !== null &&
        anchorState?.anchor !== undefined
    );
};

/**
 * Pure drag lifecycle between a PlayCanvas display transform and the immutable
 * OpenCV Anchor pose. The PlayCanvas gizmo remains only a thin event adapter.
 */
export class AnchorFrustumManipulation {
    private readonly target: AnchorFrustumManipulationTarget;
    private active = false;

    constructor(target: AnchorFrustumManipulationTarget) {
        this.target = target;
    }

    begin(): void {
        this.active = true;
    }

    move(playCanvasWorldTransform: ArrayLike<number>): void {
        if (!this.active) {
            return;
        }
        this.target.moveAnchorFrustum(
            cameraToWorldFromPlayCanvasWorldTransform(playCanvasWorldTransform)
        );
    }

    async end(): Promise<void> {
        if (!this.active) {
            return;
        }
        this.active = false;
        await this.target.endAnchorManipulation();
    }

    cancel(): void {
        this.active = false;
    }
}
