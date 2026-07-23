import { Entity, Mat4, Quat, RotateGizmo, TranslateGizmo } from 'playcanvas';

import type { Scene } from '../scene';
import {
    type AISelectAnchorController,
    type AISelectAnchorState
} from './anchor-controller';
import {
    AnchorFrustumManipulation,
    canManipulateAnchorFrustum
} from './anchor-frustum-manipulation';
import {
    playCanvasWorldTransformFromCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    type CameraInspectionController,
    type CameraInspectionManipulation,
    type CameraInspectionState
} from './camera-inspection';

/**
 * The display entity is deliberately separate from the Editor Camera. Gizmo
 * transforms flow only into CameraInspectionController, which revises the
 * Anchor CameraBinding and requests its authoritative gsplat preview.
 */
export class AnchorFrustumManipulator {
    private readonly scene: Scene;
    private readonly inspection: CameraInspectionController;
    private readonly entity = new Entity('aiSelectAnchorFrustumManipulator');
    private readonly translateGizmo: TranslateGizmo;
    private readonly rotateGizmo: RotateGizmo;
    private readonly manipulation: AnchorFrustumManipulation;
    private readonly unsubscriptions: (() => void)[] = [];
    private inspectionState: CameraInspectionState;
    private anchorState: AISelectAnchorState;
    private attachedMode: CameraInspectionManipulation | null = null;
    private dragging = false;

    constructor(options: {
        readonly scene: Scene;
        readonly controller: AISelectAnchorController;
        readonly inspection: CameraInspectionController;
    }) {
        this.scene = options.scene;
        this.inspection = options.inspection;
        this.manipulation = new AnchorFrustumManipulation(this.inspection);
        this.translateGizmo = new TranslateGizmo(
            this.scene.camera.camera,
            this.scene.gizmoLayer
        );
        this.rotateGizmo = new RotateGizmo(
            this.scene.camera.camera,
            this.scene.gizmoLayer
        );
        this.rotateGizmo.rotationMode = 'absolute';
        this.scene.app.root.addChild(this.entity);
        this.configureGizmo(this.translateGizmo);
        this.configureGizmo(this.rotateGizmo);
        this.updateGizmoSize();
        this.scene.events.on('camera.resize', this.updateGizmoSize, this);
        this.scene.events.on('camera.ortho', this.updateGizmoSize, this);
        this.unsubscriptions.push(
            options.controller.subscribe((state) => {
                this.anchorState = state;
                this.refresh();
            }),
            options.inspection.subscribe((state) => {
                this.inspectionState = state;
                this.refresh();
            })
        );
    }

    destroy(): void {
        this.unsubscriptions.splice(0).forEach((unsubscribe) => unsubscribe());
        this.scene.events.off('camera.resize', this.updateGizmoSize, this);
        this.scene.events.off('camera.ortho', this.updateGizmoSize, this);
        this.manipulation.cancel();
        this.detachGizmos();
        this.translateGizmo.destroy();
        this.rotateGizmo.destroy();
        this.entity.destroy();
    }

    private configureGizmo(gizmo: TranslateGizmo | RotateGizmo): void {
        gizmo.on('render:update', () => {
            this.scene.forceRender = true;
        });
        gizmo.on('transform:start', () => {
            this.dragging = true;
            this.manipulation.begin();
        });
        gizmo.on('transform:move', () => {
            this.moveAnchorFrustum();
            this.scene.forceRender = true;
        });
        gizmo.on('transform:end', () => {
            this.dragging = false;
            this.manipulation.end().catch((error: unknown): void => {
                console.error(error);
            });
            this.refresh();
        });
    }

    private refresh(): void {
        const binding = this.anchorState?.anchor?.cameraBinding;
        if (
            !canManipulateAnchorFrustum(
                this.anchorState,
                this.inspectionState
            ) ||
            binding === undefined
        ) {
            this.detachGizmos();
            return;
        }
        if (!this.dragging) {
            this.setEntityFromBinding(binding);
        }
        const mode = this.inspectionState.manipulation;
        if (this.attachedMode === mode) {
            return;
        }
        this.detachGizmos();
        const gizmo = mode === 'move' ? this.translateGizmo : this.rotateGizmo;
        gizmo.enabled = true;
        gizmo.attach([this.entity]);
        this.attachedMode = mode;
        this.scene.forceRender = true;
    }

    private detachGizmos(): void {
        if (this.dragging) {
            this.dragging = false;
            this.manipulation.cancel();
        }
        this.translateGizmo.detach();
        this.rotateGizmo.detach();
        this.translateGizmo.enabled = false;
        this.rotateGizmo.enabled = false;
        this.attachedMode = null;
    }

    private updateGizmoSize(): void {
        const { camera, canvas } = this.scene;
        const size = camera.ortho
            ? 1125 / canvas.clientHeight
            : 1200 / Math.max(canvas.clientWidth, canvas.clientHeight);
        this.translateGizmo.size = size;
        this.rotateGizmo.size = size;
    }

    private setEntityFromBinding(binding: CameraBinding): void {
        const matrix = new Mat4();
        matrix.data.set(playCanvasWorldTransformFromCameraBinding(binding));
        this.entity.setPosition(matrix.getTranslation());
        this.entity.setRotation(new Quat().setFromMat4(matrix));
    }

    private moveAnchorFrustum(): void {
        if (this.inspectionState?.mode !== 'active') {
            return;
        }
        this.manipulation.move(this.entity.getWorldTransform().data);
    }
}
