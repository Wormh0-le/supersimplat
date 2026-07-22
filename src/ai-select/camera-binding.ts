/**
 * The immutable camera truth shared by the AI renderer and the editor-side
 * frustum. Camera coordinates use OpenCV's right/down/forward axes so the
 * Companion can derive its locked gsplat world-to-camera matrix without
 * guessing from PlayCanvas viewport state.
 */
export const aiSelectCameraConvention = 'opencv-camera-to-world/v1';

export interface CameraBindingProjection {
    readonly model: 'pinhole';
    readonly fx: number;
    readonly fy: number;
    readonly cx: number;
    readonly cy: number;
    readonly width: number;
    readonly height: number;
    readonly near: number;
    readonly far: number;
}

export interface CameraBinding {
    readonly revision: number;
    /** A row-major OpenCV camera-to-world affine matrix. */
    readonly cameraToWorld: readonly number[];
    readonly projection: CameraBindingProjection;
    readonly conventionVersion: typeof aiSelectCameraConvention;
}

/**
 * The narrow editor-camera surface needed to copy a Current Scene View. The
 * production Camera satisfies this structurally; keeping it narrow lets the
 * conversion remain independently testable from the PlayCanvas renderer.
 */
export interface EditorCameraBindingSource {
    readonly targetSize: {
        readonly width: number;
        readonly height: number;
    };
    readonly fov: number;
    readonly near: number;
    readonly far: number;
    /** The v1 Anchor protocol accepts only an exact perspective/pinhole view. */
    readonly ortho?: boolean;
    readonly camera: {
        readonly horizontalFov: boolean;
    };
    readonly worldTransform: {
        readonly data: ArrayLike<number>;
    };
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isFiniteNumber = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isFinite(value);
};

const isPositiveFiniteNumber = (value: unknown): value is number => {
    return isFiniteNumber(value) && value > 0;
};

const isPositiveSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) > 0;
};

const copyMatrix = (matrix: readonly number[]): readonly number[] => {
    return Object.freeze([...matrix]);
};

const negate = (value: number): number => {
    return value === 0 ? 0 : -value;
};

const copyProjection = (
    projection: CameraBindingProjection
): CameraBindingProjection => {
    return Object.freeze({
        model: projection.model,
        fx: projection.fx,
        fy: projection.fy,
        cx: projection.cx,
        cy: projection.cy,
        width: projection.width,
        height: projection.height,
        near: projection.near,
        far: projection.far
    });
};

const isProjection = (value: unknown): value is CameraBindingProjection => {
    if (!isRecord(value) || value.model !== 'pinhole') {
        return false;
    }

    return (
        isPositiveFiniteNumber(value.fx) &&
        isPositiveFiniteNumber(value.fy) &&
        isFiniteNumber(value.cx) &&
        isFiniteNumber(value.cy) &&
        isPositiveSafeInteger(value.width) &&
        isPositiveSafeInteger(value.height) &&
        isPositiveFiniteNumber(value.near) &&
        isPositiveFiniteNumber(value.far) &&
        value.far > value.near
    );
};

const isAffineCameraToWorld = (value: unknown): value is readonly number[] => {
    if (!Array.isArray(value) || value.length !== 16 || !value.every(isFiniteNumber)) {
        return false;
    }

    return value[12] === 0 && value[13] === 0 && value[14] === 0 && value[15] === 1;
};

export const isCameraBinding = (value: unknown): value is CameraBinding => {
    return (
        isRecord(value) &&
        Number.isSafeInteger(value.revision) &&
        (value.revision as number) >= 0 &&
        value.conventionVersion === aiSelectCameraConvention &&
        isAffineCameraToWorld(value.cameraToWorld) &&
        isProjection(value.projection)
    );
};

export function assertCameraBinding(
    value: unknown
): asserts value is CameraBinding {
    if (!isCameraBinding(value)) {
        throw new Error(
            'AI Select CameraBinding must contain a finite affine camera pose and complete pinhole projection.'
        );
    }
}

export const copyCameraBinding = (binding: CameraBinding): CameraBinding => {
    assertCameraBinding(binding);
    return Object.freeze({
        revision: binding.revision,
        cameraToWorld: copyMatrix(binding.cameraToWorld),
        projection: copyProjection(binding.projection),
        conventionVersion: binding.conventionVersion
    });
};

export const areCameraBindingsEqual = (
    left: CameraBinding,
    right: CameraBinding
): boolean => {
    return (
        left.revision === right.revision &&
        left.conventionVersion === right.conventionVersion &&
        left.cameraToWorld.length === right.cameraToWorld.length &&
        left.cameraToWorld.every((value, index) => value === right.cameraToWorld[index]) &&
        left.projection.model === right.projection.model &&
        left.projection.fx === right.projection.fx &&
        left.projection.fy === right.projection.fy &&
        left.projection.cx === right.projection.cx &&
        left.projection.cy === right.projection.cy &&
        left.projection.width === right.projection.width &&
        left.projection.height === right.projection.height &&
        left.projection.near === right.projection.near &&
        left.projection.far === right.projection.far
    );
};

/**
 * Copy the visible editor camera without changing it. PlayCanvas uses a
 * right/up/back camera basis, while the Companion's explicit convention uses
 * right/down/forward; this conversion is the single boundary between them.
 */
export const captureEditorCameraBinding = (
    camera: EditorCameraBindingSource,
    revision = 0
): CameraBinding => {
    const { width, height } = camera.targetSize;
    const matrix = camera.worldTransform.data;
    if (camera.ortho === true) {
        throw new Error(
            'AI Select v1 requires a perspective Current Scene View; orthographic views cannot be represented by its pinhole CameraBinding.'
        );
    }
    if (
        !isPositiveSafeInteger(width) ||
        !isPositiveSafeInteger(height) ||
        !isPositiveFiniteNumber(camera.fov) ||
        !isPositiveFiniteNumber(camera.near) ||
        !isPositiveFiniteNumber(camera.far) ||
        camera.far <= camera.near ||
        !Number.isSafeInteger(revision) ||
        revision < 0 ||
        matrix.length !== 16
    ) {
        throw new Error('Current Scene View cannot produce a complete AI Select CameraBinding.');
    }

    const transform = Array.from(matrix);
    if (!transform.every(Number.isFinite)) {
        throw new Error('Current Scene View camera transform contains non-finite values.');
    }

    const radians = camera.fov * Math.PI / 180;
    const focalLength = camera.camera.horizontalFov ?
        width / (2 * Math.tan(radians / 2)) :
        height / (2 * Math.tan(radians / 2));
    if (!Number.isFinite(focalLength) || focalLength <= 0) {
        throw new Error('Current Scene View camera field of view is invalid for AI Select.');
    }

    // PlayCanvas Mat4 data is column-major. Its local camera axes are
    // right/up/back, so OpenCV camera-to-world is right/down/forward.
    const cameraToWorld = [
        transform[0], negate(transform[4]), negate(transform[8]), transform[12],
        transform[1], negate(transform[5]), negate(transform[9]), transform[13],
        transform[2], negate(transform[6]), negate(transform[10]), transform[14],
        0, 0, 0, 1
    ];

    return copyCameraBinding({
        revision,
        cameraToWorld,
        projection: {
            model: 'pinhole',
            fx: focalLength,
            fy: focalLength,
            cx: width / 2,
            cy: height / 2,
            width,
            height,
            near: camera.near,
            far: camera.far
        },
        conventionVersion: aiSelectCameraConvention
    });
};
