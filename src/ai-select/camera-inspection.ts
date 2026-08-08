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

/**
 * What Camera Inspection observes. The Anchor remains manipulable through the
 * Anchor port; a Generated View camera is planner-owned and read-only — the
 * observer looks at its frustum exactly as it does the Anchor's, and the
 * observer pose never becomes an implicit new Anchor or View camera. A
 * `user-view-draft` is the provisional Adjust New View target (Ticket 11):
 * manipulable like the Anchor, but its binding lives only inside the
 * inspection until an explicit Confirm View publishes it as a user-added
 * AIView; returning without confirming discards it.
 */
export type CameraInspectionTarget =
    | { readonly kind: 'anchor' }
    | {
          readonly kind: 'view';
          readonly viewId: string;
          readonly cameraBinding: CameraBinding;
      }
    | {
          readonly kind: 'user-view-draft';
          readonly cameraBinding: CameraBinding;
      };

export interface CameraInspectionState {
    readonly mode: CameraInspectionMode;
    readonly manipulation: CameraInspectionManipulation;
    readonly savedSceneView: SavedSceneView | null;
    readonly target: CameraInspectionTarget | null;
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
 *
 * The observer pulls straight back along the Anchor view axis without any
 * sideways or vertical offset. The editor camera drives orientation through a
 * roll-free azimuth/elevation model whose screen-up is world +Y, so tilting
 * the observer view direction away from the Anchor forward would force a
 * different roll for Anchors not aligned with +Y (for example Z-up scenes
 * viewed near the orbit pole), visibly rotating the whole viewport. Keeping
 * the exact Anchor view direction lets `setPose` recover the Anchor's own
 * azimuth/elevation, so the scene orientation stays continuous and only the
 * pull-back reveals the Anchor Frustum.
 */
export const cameraInspectionObserverView = (
    binding: CameraBinding
): SavedSceneView => {
    const camera = copyCameraBinding(binding);
    const matrix = camera.cameraToWorld;
    const origin = Object.freeze({ x: matrix[3], y: matrix[7], z: matrix[11] });
    const forward = normalize({ x: matrix[2], y: matrix[6], z: matrix[10] });
    const displayDepth = Math.min(
        camera.projection.far,
        Math.max(camera.projection.near * 8, 0.05)
    );
    const observerDistance = Math.max(displayDepth * 2.5, 0.25);
    const target = plus(origin, forward, displayDepth * 0.6);
    const position = plus(origin, forward, -observerDistance);
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

const copyTarget = (target: CameraInspectionTarget): CameraInspectionTarget => {
    if (target.kind === 'anchor') {
        return Object.freeze({ kind: 'anchor' });
    }
    if (target.kind === 'user-view-draft') {
        return Object.freeze({
            kind: 'user-view-draft',
            cameraBinding: copyCameraBinding(target.cameraBinding)
        });
    }
    return Object.freeze({
        kind: 'view',
        viewId: target.viewId,
        cameraBinding: copyCameraBinding(target.cameraBinding)
    });
};

/**
 * True only while Camera Inspection observes the Anchor itself. Generated
 * View inspection is read-only, so Anchor frustum display and manipulation
 * gate on this single predicate.
 */
export const isAnchorInspectionTarget = (
    state: CameraInspectionState | undefined
): boolean => {
    return state?.mode === 'active' && state.target?.kind === 'anchor';
};

/**
 * True only while Camera Inspection holds the provisional Adjust New View
 * draft: the draft frustum is manipulable and Confirm View is available,
 * but nothing is a View yet — Confirm mints it, Return discards it.
 */
export const isUserViewDraftInspectionTarget = (
    state: CameraInspectionState | undefined
): boolean => {
    return state?.mode === 'active' && state.target?.kind === 'user-view-draft';
};

const copyState = (state: CameraInspectionState): CameraInspectionState => {
    return Object.freeze({
        mode: state.mode,
        manipulation: state.manipulation,
        savedSceneView:
            state.savedSceneView === null
                ? null
                : copySavedSceneView(state.savedSceneView),
        target: state.target === null ? null : copyTarget(state.target)
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
    private target: CameraInspectionTarget | null = null;
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
            savedSceneView: this.savedSceneView,
            target: this.target
        });
    }

    subscribe(listener: CameraInspectionListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    private bindingForTarget(target: CameraInspectionTarget): CameraBinding {
        if (target.kind === 'view' || target.kind === 'user-view-draft') {
            return copyCameraBinding(target.cameraBinding);
        }
        const anchorBinding = this.anchor.getAnchorCameraBinding();
        if (anchorBinding === null) {
            throw new Error(
                'Camera Inspection requires an active Anchor CameraBinding.'
            );
        }
        return anchorBinding;
    }

    enter(target: CameraInspectionTarget = { kind: 'anchor' }): void {
        const binding = this.bindingForTarget(target);
        const observerView = cameraInspectionObserverView(binding);
        const nextTarget = copyTarget(target);
        if (this.mode === 'active') {
            // Switching targets only re-derives the external observer; the
            // original saved Scene View and its atomic restore are kept, so
            // returning still recovers the exact pre-inspection editor camera.
            this.editor.setSceneView(observerView);
            this.target = nextTarget;
            this.publish();
            return;
        }
        const capturedSceneView = this.editor.captureSceneView();
        if (typeof capturedSceneView.restore !== 'function') {
            throw new Error(
                'Camera Inspection requires an atomic Scene View restore action.'
            );
        }
        const savedSceneView = copySavedSceneView(capturedSceneView.sceneView);
        this.editor.setSceneView(observerView);
        this.mode = 'active';
        this.manipulation = 'move';
        this.savedSceneView = savedSceneView;
        this.restoreSceneView = capturedSceneView.restore;
        this.target = nextTarget;
        this.publish();
    }

    setManipulation(manipulation: CameraInspectionManipulation): void {
        this.requireActive();
        this.manipulation = manipulation;
        this.publish();
    }

    moveAnchorFrustum(cameraToWorld: readonly number[]): void {
        this.requireActive();
        this.requireAnchorTarget();
        assertCameraToWorldMatrix(cameraToWorld);
        this.anchor.updateAnchorCameraPose(Object.freeze([...cameraToWorld]));
    }

    /**
     * Drag the provisional Adjust New View draft. Only the draft binding's
     * pose changes — projection, clipping, convention, and revision stay
     * exactly as captured from the Editor Camera — and nothing renders until
     * Confirm View publishes the draft as a user-added AIView.
     */
    moveDraftFrustum(cameraToWorld: readonly number[]): void {
        this.requireActive();
        const target = this.requireDraftTarget();
        assertCameraToWorldMatrix(cameraToWorld);
        this.target = Object.freeze({
            kind: 'user-view-draft',
            cameraBinding: copyCameraBinding({
                ...target.cameraBinding,
                cameraToWorld: Object.freeze([...cameraToWorld])
            })
        });
        this.publish();
    }

    /**
     * Confirm View: atomically end the inspection (restoring the exact
     * pre-inspection Scene View) and hand the adjusted CameraBinding to the
     * caller, which publishes it as a user-added AIView. The Editor Camera
     * never adopted the draft pose.
     */
    confirmDraftView(): CameraBinding {
        this.requireActive();
        const target = this.requireDraftTarget();
        const binding = copyCameraBinding(target.cameraBinding);
        this.returnToSceneView();
        return binding;
    }

    async endAnchorManipulation(): Promise<void> {
        this.requireActive();
        this.requireAnchorTarget();
        await this.queueFinalAnchorRender(() =>
            this.anchor.renderFinalPreview()
        );
    }

    async resetAnchor(): Promise<void> {
        this.requireActive();
        this.requireAnchorTarget();
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
        this.target = null;
        this.publish();
    }

    private queueFinalAnchorRender(render: () => Promise<void>): Promise<void> {
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

    /** Generated View cameras are planner-owned and never manipulable. */
    private requireAnchorTarget(): void {
        if (this.target?.kind !== 'anchor') {
            throw new Error(
                'Camera Inspection manipulation is only available for the Anchor.'
            );
        }
    }

    private requireDraftTarget(): {
        readonly kind: 'user-view-draft';
        readonly cameraBinding: CameraBinding;
    } {
        if (this.target?.kind !== 'user-view-draft') {
            throw new Error(
                'Camera Inspection has no provisional user View draft.'
            );
        }
        return this.target;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
