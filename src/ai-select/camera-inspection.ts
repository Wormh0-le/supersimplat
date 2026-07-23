import {
    assertCameraToWorldMatrix,
    copyCameraBinding,
    type CameraBinding
} from './camera-binding';

export interface CameraInspectionVector {
    readonly x: number;
    readonly y: number;
    readonly z: number;
}

/** The editor-owned Scene View saved before Camera Inspection changes it. */
export interface SavedSceneView {
    readonly position: CameraInspectionVector;
    readonly target: CameraInspectionVector;
    readonly fov: number;
    readonly near: number;
    readonly far: number;
    readonly ortho: boolean;
}

/**
 * The editor retains the opaque camera runtime snapshot behind this closure.
 * Camera Inspection intentionally stores only a display-safe description so it
 * cannot reconstruct a tweening editor camera from mismatched public fields.
 */
export interface CapturedSceneView {
    readonly sceneView: SavedSceneView;
    readonly restore: () => void;
}

export interface CameraInspectionEditor {
    captureSceneView(): CapturedSceneView;
    setSceneView(view: SavedSceneView): void;
}

/**
 * This small port keeps the Camera Inspection lifecycle separate from Anchor
 * rendering. The Anchor controller remains the authority on revisions and
 * whether a render can publish.
 */
export interface CameraInspectionAnchor {
    getAnchorCameraBinding(): CameraBinding | null;
    updateAnchorCameraPose(cameraToWorld: readonly number[]): void;
    renderFinalPreview(): Promise<void>;
    resetAnchor(): Promise<void>;
}

export type CameraInspectionMode = 'inactive' | 'active';
export type CameraInspectionManipulation = 'move' | 'rotate';

export interface CameraInspectionState {
    readonly mode: CameraInspectionMode;
    readonly manipulation: CameraInspectionManipulation;
    readonly savedSceneView: SavedSceneView | null;
}

export interface CameraInspectionOptions {
    readonly anchor: CameraInspectionAnchor;
    readonly editor: CameraInspectionEditor;
}

export type CameraInspectionListener = (state: CameraInspectionState) => void;

const isFiniteNumber = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isFinite(value);
};

const isFiniteVector = (value: unknown): value is CameraInspectionVector => {
    return (
        typeof value === 'object' &&
        value !== null &&
        isFiniteNumber((value as CameraInspectionVector).x) &&
        isFiniteNumber((value as CameraInspectionVector).y) &&
        isFiniteNumber((value as CameraInspectionVector).z)
    );
};

const copyVector = (value: CameraInspectionVector): CameraInspectionVector => {
    return Object.freeze({ x: value.x, y: value.y, z: value.z });
};

function assertSavedSceneView(value: unknown): asserts value is SavedSceneView {
    if (
        typeof value !== 'object' ||
        value === null ||
        !isFiniteVector((value as SavedSceneView).position) ||
        !isFiniteVector((value as SavedSceneView).target) ||
        !isFiniteNumber((value as SavedSceneView).fov) ||
        !isFiniteNumber((value as SavedSceneView).near) ||
        !isFiniteNumber((value as SavedSceneView).far) ||
        (value as SavedSceneView).far <= (value as SavedSceneView).near ||
        typeof (value as SavedSceneView).ortho !== 'boolean'
    ) {
        throw new Error(
            'Camera Inspection requires a complete finite Scene View.'
        );
    }
}

export const copySavedSceneView = (view: SavedSceneView): SavedSceneView => {
    assertSavedSceneView(view);
    return Object.freeze({
        position: copyVector(view.position),
        target: copyVector(view.target),
        fov: view.fov,
        near: view.near,
        far: view.far,
        ortho: view.ortho
    });
};

const normalize = (vector: CameraInspectionVector): CameraInspectionVector => {
    const length = Math.hypot(vector.x, vector.y, vector.z);
    if (!Number.isFinite(length) || length <= 1e-8) {
        throw new Error(
            'Camera Inspection cannot derive an observer from a degenerate Anchor pose.'
        );
    }
    return Object.freeze({
        x: vector.x / length,
        y: vector.y / length,
        z: vector.z / length
    });
};

const plus = (
    left: CameraInspectionVector,
    right: CameraInspectionVector,
    scale = 1
): CameraInspectionVector => {
    return Object.freeze({
        x: left.x + right.x * scale,
        y: left.y + right.y * scale,
        z: left.z + right.z * scale
    });
};

/**
 * Choose an external observer for the editor camera. It deliberately derives
 * a view of the immutable Anchor Frustum rather than adopting that Anchor as
 * the editor camera.
 */
export const cameraInspectionObserverView = (
    binding: CameraBinding
): SavedSceneView => {
    const camera = copyCameraBinding(binding);
    const matrix = camera.cameraToWorld;
    const origin = Object.freeze({ x: matrix[3], y: matrix[7], z: matrix[11] });
    const right = normalize({ x: matrix[0], y: matrix[4], z: matrix[8] });
    const up = normalize({ x: -matrix[1], y: -matrix[5], z: -matrix[9] });
    const forward = normalize({ x: matrix[2], y: matrix[6], z: matrix[10] });
    const displayDepth = Math.min(
        camera.projection.far,
        Math.max(camera.projection.near * 8, 0.05)
    );
    const observerDistance = Math.max(displayDepth * 2.5, 0.25);
    const target = plus(origin, forward, displayDepth * 0.6);
    const position = plus(
        plus(
            plus(origin, forward, -observerDistance),
            up,
            observerDistance * 0.25
        ),
        right,
        observerDistance * 0.25
    );
    const fov =
        (2 *
            Math.atan(camera.projection.height / (2 * camera.projection.fy)) *
            180) /
        Math.PI;
    return copySavedSceneView({
        position,
        target,
        fov,
        near: camera.projection.near,
        far: camera.projection.far,
        ortho: false
    });
};

const copyState = (state: CameraInspectionState): CameraInspectionState => {
    return Object.freeze({
        mode: state.mode,
        manipulation: state.manipulation,
        savedSceneView:
            state.savedSceneView === null
                ? null
                : copySavedSceneView(state.savedSceneView)
    });
};

/**
 * Owns the explicit observer-camera mode. It never reads editor camera changes
 * back into the Anchor; only an explicit Frustum manipulation updates the
 * Anchor through its narrow port. Dragging updates only that binding; the
 * final authoritative RGB is requested when the manipulation ends.
 */
export class CameraInspectionController {
    private readonly anchor: CameraInspectionAnchor;
    private readonly editor: CameraInspectionEditor;
    private readonly listeners = new Set<CameraInspectionListener>();
    private mode: CameraInspectionMode = 'inactive';
    private manipulation: CameraInspectionManipulation = 'move';
    private savedSceneView: SavedSceneView | null = null;
    private restoreSceneView: (() => void) | null = null;
    /** Serialize fixed-pose renders because the Companion admits one at a time. */
    private anchorRenderTail: Promise<void> | null = null;

    constructor(options: CameraInspectionOptions) {
        this.anchor = options.anchor;
        this.editor = options.editor;
    }

    get state(): CameraInspectionState {
        return copyState({
            mode: this.mode,
            manipulation: this.manipulation,
            savedSceneView: this.savedSceneView
        });
    }

    subscribe(listener: CameraInspectionListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    enter(): void {
        if (this.mode === 'active') {
            return;
        }
        const anchorBinding = this.anchor.getAnchorCameraBinding();
        if (anchorBinding === null) {
            throw new Error(
                'Camera Inspection requires an active Anchor CameraBinding.'
            );
        }
        const capturedSceneView = this.editor.captureSceneView();
        if (typeof capturedSceneView.restore !== 'function') {
            throw new Error(
                'Camera Inspection requires an atomic Scene View restore action.'
            );
        }
        const savedSceneView = copySavedSceneView(capturedSceneView.sceneView);
        const observerView = cameraInspectionObserverView(anchorBinding);
        this.editor.setSceneView(observerView);
        this.mode = 'active';
        this.manipulation = 'move';
        this.savedSceneView = savedSceneView;
        this.restoreSceneView = capturedSceneView.restore;
        this.publish();
    }

    setManipulation(manipulation: CameraInspectionManipulation): void {
        this.requireActive();
        this.manipulation = manipulation;
        this.publish();
    }

    moveAnchorFrustum(cameraToWorld: readonly number[]): void {
        this.requireActive();
        assertCameraToWorldMatrix(cameraToWorld);
        this.anchor.updateAnchorCameraPose(Object.freeze([...cameraToWorld]));
    }

    async endAnchorManipulation(): Promise<void> {
        this.requireActive();
        await this.queueFinalAnchorRender(() =>
            this.anchor.renderFinalPreview()
        );
    }

    async resetAnchor(): Promise<void> {
        this.requireActive();
        await this.queueFinalAnchorRender(() => this.anchor.resetAnchor());
    }

    returnToSceneView(): void {
        if (this.mode !== 'active') {
            return;
        }
        const savedSceneView = this.savedSceneView;
        if (savedSceneView === null) {
            throw new Error('Camera Inspection lost its saved Scene View.');
        }
        if (this.restoreSceneView === null) {
            throw new Error(
                'Camera Inspection lost its atomic Scene View restore action.'
            );
        }
        this.restoreSceneView();
        this.mode = 'inactive';
        this.savedSceneView = null;
        this.restoreSceneView = null;
        this.publish();
    }

    private queueFinalAnchorRender(
        render: () => Promise<void>
    ): Promise<void> {
        const previous = this.anchorRenderTail;
        const run = (): Promise<void> => {
            if (this.mode !== 'active') {
                return Promise.resolve();
            }
            return render();
        };
        const next =
            previous === null
                ? run()
                : previous.catch((): void => undefined).then(run);
        this.anchorRenderTail = next;
        const clearTail = (): void => {
            if (this.anchorRenderTail === next) {
                this.anchorRenderTail = null;
            }
        };
        next.then(clearTail, clearTail);
        return next;
    }

    private requireActive(): void {
        if (this.mode !== 'active') {
            throw new Error(
                'Camera Inspection must be active for this operation.'
            );
        }
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
