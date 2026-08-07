import type { PackedSceneSnapshot } from '../scene-snapshot-binary';
import { isCameraBinding, type CameraBinding } from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import { isMaskArtifact, type MaskArtifact } from './mask-annotation';

/**
 * The versioned Target Geometry contract (Final Spec v1.3 §9, Ticket 08). The
 * Companion compresses the exact confirmed Anchor Stable Mask into one compact
 * visible-surface geometry hint; the editor binds the confirmed-Anchor
 * Camera/RGB/Stable-Mask identity and fails closed on any other policy
 * version. The hint is localization, framing, and later Prompt-synthesis
 * context only: it never carries Stable Gaussian IDs, sample weights, or
 * ownership classification, and it never bounds the Evidence Working Set.
 */
export const aiSelectTargetGeometryPolicyVersion = 'target-geometry/v2';

export const targetGeometryHintSchemaVersion = 2;

/**
 * The Companion-computed geometry hint for one exact confirmed Anchor. All
 * digests are opaque Companion/canonical identities: the editor validates
 * their shape and echoes but never recomputes them.
 */
export interface TargetGeometryHintArtifact {
    readonly schemaVersion: typeof targetGeometryHintSchemaVersion;
    readonly targetContextId: string;
    readonly anchorCameraBindingDigest: string;
    readonly anchorRgbDigest: string;
    readonly anchorStableMaskDigest: string;
    readonly geometryPolicyDigest: string;
    readonly centerWorld: readonly [number, number, number];
    readonly extentWorld: readonly [number, number, number];
    readonly visiblePoints: readonly (readonly [number, number, number])[];
    readonly quality: 'usable' | 'limited' | 'unavailable';
    readonly reasons: readonly string[];
    readonly promptSupport: 'usable' | 'limited';
    readonly artifactDigest: string;
}

export interface TargetGeometryHintRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    /**
     * The editor-side Scene Snapshot payload. It never crosses the wire as
     * geometry input; the transport retains it so a scene cache/chunk miss can
     * re-register or upload before one bounded retry.
     */
    readonly snapshot: PackedSceneSnapshot;
    readonly sceneId: string;
    readonly sceneVersion: string;
    /**
     * The identity of one actual derivation execution. Same-attempt replay is
     * idempotent; an explicit Retry submits a new attempt.
     */
    readonly geometryAttemptId: string;
    readonly anchorCameraBinding: CameraBinding;
    /**
     * The editor-owned CameraBinding digest. The Companion binds it opaquely
     * into the artifact; it never recomputes editor identity.
     */
    readonly anchorCameraBindingDigest: string;
    readonly anchorRgbDigest: string;
    readonly anchorStableMask: MaskArtifact;
    readonly geometryPolicyVersion: typeof aiSelectTargetGeometryPolicyVersion;
}

export interface TargetGeometryHintResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly geometryAttemptId: string;
    readonly geometryPolicyVersion: string;
    readonly hint: TargetGeometryHintArtifact;
}

export interface AISelectTargetGeometryProvider {
    produceTargetGeometryHint(
        request: TargetGeometryHintRequest
    ): Promise<TargetGeometryHintResponse>;
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

const isFiniteNumber = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isFinite(value);
};

const isWorldTriple = (
    value: unknown
): value is readonly [number, number, number] => {
    return (
        Array.isArray(value) &&
        value.length === 3 &&
        value.every(isFiniteNumber)
    );
};

const isPromptSupportSemanticallyValid = (
    promptSupport: unknown,
    visiblePoints: unknown,
    reasons: unknown
): boolean => {
    if (promptSupport === 'limited') {
        return true;
    }
    if (
        promptSupport !== 'usable' ||
        !Array.isArray(visiblePoints) ||
        !Array.isArray(reasons)
    ) {
        return false;
    }
    const distinctPoints = new Set(
        visiblePoints.map((point) => JSON.stringify(point))
    );
    return (
        distinctPoints.size >= 4 &&
        reasons.every((reason) => reason === 'separatedSupportFiltered')
    );
};

const isGeometryQualitySemanticallyValid = (
    quality: unknown,
    reasons: unknown
): boolean => {
    if (!Array.isArray(reasons)) {
        return false;
    }
    if (quality === 'unavailable') {
        return true;
    }
    return quality === (reasons.length > 0 ? 'limited' : 'usable');
};

export const isTargetGeometryHintArtifact = (
    value: unknown
): value is TargetGeometryHintArtifact => {
    return (
        isRecord(value) &&
        value.schemaVersion === targetGeometryHintSchemaVersion &&
        isNonEmptyString(value.targetContextId) &&
        isDigest(value.anchorCameraBindingDigest) &&
        isDigest(value.anchorRgbDigest) &&
        isDigest(value.anchorStableMaskDigest) &&
        isDigest(value.geometryPolicyDigest) &&
        isWorldTriple(value.centerWorld) &&
        isWorldTriple(value.extentWorld) &&
        Array.isArray(value.visiblePoints) &&
        value.visiblePoints.length >= 1 &&
        value.visiblePoints.length <= 64 &&
        value.visiblePoints.every(isWorldTriple) &&
        (value.quality === 'usable' ||
            value.quality === 'limited' ||
            value.quality === 'unavailable') &&
        Array.isArray(value.reasons) &&
        value.reasons.every(
            (reason) => typeof reason === 'string' && reason.length > 0
        ) &&
        isGeometryQualitySemanticallyValid(value.quality, value.reasons) &&
        isPromptSupportSemanticallyValid(
            value.promptSupport,
            value.visiblePoints,
            value.reasons
        ) &&
        isDigest(value.artifactDigest)
    );
};

export const isTargetGeometryHintRequest = (
    value: unknown
): value is TargetGeometryHintRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isTarget(value.target) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isRecord(value.snapshot) &&
        value.snapshot.sceneId === value.target.splatId &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        value.sceneId === value.target.splatId &&
        isNonEmptyString(value.geometryAttemptId) &&
        isCameraBinding(value.anchorCameraBinding) &&
        isDigest(value.anchorCameraBindingDigest) &&
        isDigest(value.anchorRgbDigest) &&
        isMaskArtifact(value.anchorStableMask) &&
        value.anchorStableMask.width ===
            value.anchorCameraBinding.projection.width &&
        value.anchorStableMask.height ===
            value.anchorCameraBinding.projection.height &&
        value.geometryPolicyVersion === aiSelectTargetGeometryPolicyVersion
    );
};

export const isTargetGeometryHintResponse = (
    value: unknown
): value is TargetGeometryHintResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.renderConfigVersion) &&
        isNonEmptyString(value.geometryAttemptId) &&
        value.geometryPolicyVersion === aiSelectTargetGeometryPolicyVersion &&
        isTargetGeometryHintArtifact(value.hint)
    );
};

/**
 * Fail-closed hint matching: every bound identity must echo the request and
 * the artifact must bind the exact confirmed-Anchor Camera/RGB/Stable-Mask
 * identity of this Current Target Context. An `unavailable` hint is a
 * derivation failure surface, never a publishable artifact.
 */
export const targetGeometryHintResponseMatchesRequest = (
    response: TargetGeometryHintResponse,
    request: TargetGeometryHintRequest
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
        response.sceneId === request.sceneId &&
        response.sceneVersion === request.sceneVersion &&
        response.renderConfigVersion ===
            request.snapshot.renderConfiguration.version &&
        response.geometryAttemptId === request.geometryAttemptId &&
        response.geometryPolicyVersion === request.geometryPolicyVersion &&
        response.hint.targetContextId ===
            request.requestBinding.targetContextId &&
        response.hint.anchorCameraBindingDigest ===
            request.anchorCameraBindingDigest &&
        response.hint.anchorRgbDigest === request.anchorRgbDigest &&
        response.hint.anchorStableMaskDigest ===
            request.anchorStableMask.digest &&
        response.hint.quality !== 'unavailable'
    );
};
