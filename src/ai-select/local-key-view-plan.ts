import { isCameraBinding, type CameraBinding } from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import {
    isTargetGeometryHintArtifact,
    type TargetGeometryHintArtifact
} from './target-geometry-hint';

/**
 * The versioned bounded local Key-View planner contract (Final Spec v1.3 §10,
 * Ticket 08). The Companion plans a small bounded local batch of Key Views
 * from the Target Geometry Hint — left/right azimuth plus modest elevation,
 * never a room-scale orbit — and validates every candidate conservatively.
 * The editor owns the initial bounded plan and its failure-only recovery, and
 * fails closed on any other policy version. Batch ordinals remain in the
 * Companion contract for future planner evolution, not as product controls.
 */
export const aiSelectLocalKeyViewPlannerVersion = 'local-key-view-planner/v3';
export const aiSelectLocalKeyViewPolicyDigest =
    'sha256:c1e4a20cb20ac08dba8c9fed2d94e0dd7ad0b50d45b4dff2d11aed874df2749e';

export const localKeyViewPlanSchemaVersion = 1;

export interface PlannedKeyView {
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
    readonly quality: 'usable' | 'limited' | 'failed';
    readonly reasons: readonly string[];
}

/**
 * One accepted bounded local Key-View batch. `viewId` identity is stable and
 * independent from array position; `planAttemptId` binds the exact planning
 * execution that produced this batch.
 */
export interface LocalKeyViewPlan {
    readonly schemaVersion: typeof localKeyViewPlanSchemaVersion;
    readonly targetContextId: string;
    readonly anchorStableMaskDigest: string;
    readonly targetGeometryHintDigest: string;
    readonly localViewPolicyDigest: string;
    readonly orderedViews: readonly PlannedKeyView[];
    readonly planAttemptId: string;
    readonly artifactDigest: string;
}

export interface LocalKeyViewPlanRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    /**
     * The identity of one actual planning execution. Same-attempt replay is
     * idempotent; a new planning intent submits a new attempt.
     */
    readonly planAttemptId: string;
    /** 0 is the current initial batch; later ordinals remain protocol-reserved. */
    readonly batchOrdinal: number;
    readonly anchorCameraBinding: CameraBinding;
    readonly anchorCameraBindingDigest: string;
    readonly anchorRgbDigest: string;
    readonly anchorStableMaskDigest: string;
    readonly targetGeometryHint: TargetGeometryHintArtifact;
    readonly localViewPolicyVersion: typeof aiSelectLocalKeyViewPlannerVersion;
}

export interface LocalKeyViewPlanResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly planAttemptId: string;
    readonly batchOrdinal: number;
    readonly localViewPolicyVersion: string;
    readonly plan: LocalKeyViewPlan;
}

export interface AISelectLocalKeyViewPlanner {
    planLocalKeyViews(
        request: LocalKeyViewPlanRequest
    ): Promise<LocalKeyViewPlanResponse>;
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isTarget = (value: unknown): value is AITarget => {
    return isRecord(value) && isNonEmptyString(value.splatId);
};

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

export const isPlannedKeyView = (value: unknown): value is PlannedKeyView => {
    return (
        isRecord(value) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isCameraBinding(value.cameraBinding) &&
        (value.quality === 'usable' ||
            value.quality === 'limited' ||
            value.quality === 'failed') &&
        Array.isArray(value.reasons) &&
        value.reasons.every(
            (reason) => typeof reason === 'string' && reason.length > 0
        )
    );
};

export const isLocalKeyViewPlan = (
    value: unknown
): value is LocalKeyViewPlan => {
    if (
        !isRecord(value) ||
        value.schemaVersion !== localKeyViewPlanSchemaVersion ||
        !isNonEmptyString(value.targetContextId) ||
        !isDigest(value.anchorStableMaskDigest) ||
        !isDigest(value.targetGeometryHintDigest) ||
        !isDigest(value.localViewPolicyDigest) ||
        !Array.isArray(value.orderedViews) ||
        value.orderedViews.length < 4 ||
        value.orderedViews.length > 8 ||
        !value.orderedViews.every(isPlannedKeyView) ||
        !isNonEmptyString(value.planAttemptId) ||
        !isDigest(value.artifactDigest)
    ) {
        return false;
    }
    const viewIds = new Set(
        (value.orderedViews as readonly PlannedKeyView[]).map(
            (view) => view.viewId
        )
    );
    return viewIds.size === value.orderedViews.length;
};

export const isLocalKeyViewPlanRequest = (
    value: unknown
): value is LocalKeyViewPlanRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isTarget(value.target) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isNonEmptyString(value.planAttemptId) &&
        isNonNegativeSafeInteger(value.batchOrdinal) &&
        isCameraBinding(value.anchorCameraBinding) &&
        isDigest(value.anchorCameraBindingDigest) &&
        isDigest(value.anchorRgbDigest) &&
        isDigest(value.anchorStableMaskDigest) &&
        isTargetGeometryHintArtifact(value.targetGeometryHint) &&
        value.localViewPolicyVersion === aiSelectLocalKeyViewPlannerVersion
    );
};

export const isLocalKeyViewPlanResponse = (
    value: unknown
): value is LocalKeyViewPlanResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.planAttemptId) &&
        isNonNegativeSafeInteger(value.batchOrdinal) &&
        value.localViewPolicyVersion === aiSelectLocalKeyViewPlannerVersion &&
        isLocalKeyViewPlan(value.plan)
    );
};

/**
 * Fail-closed plan matching: every bound identity must echo the request and
 * the plan artifact must bind the exact Target Geometry Hint, Anchor Stable
 * Mask, and planning attempt of this request.
 */
export const localKeyViewPlanResponseMatchesRequest = (
    response: LocalKeyViewPlanResponse,
    request: LocalKeyViewPlanRequest
): boolean => {
    return (
        response.requestBinding.targetContextId ===
            request.requestBinding.targetContextId &&
        response.requestBinding.contextRevision ===
            request.requestBinding.contextRevision &&
        areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) &&
        response.targetSplatId === request.target.splatId &&
        response.planAttemptId === request.planAttemptId &&
        response.batchOrdinal === request.batchOrdinal &&
        response.localViewPolicyVersion === request.localViewPolicyVersion &&
        response.plan.targetContextId ===
            request.requestBinding.targetContextId &&
        response.plan.anchorStableMaskDigest ===
            request.anchorStableMaskDigest &&
        response.plan.targetGeometryHintDigest ===
            request.targetGeometryHint.artifactDigest &&
        response.plan.planAttemptId === request.planAttemptId
    );
};
