import {
    isPackedSceneSnapshot,
    type PackedSceneSnapshot
} from '../scene-snapshot-binary';
import {
    areCameraBindingsEqual,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import { isMaskArtifact, type MaskArtifact } from './mask-annotation';

/**
 * The versioned Anchor support-probe contract (Final Spec v1.1 §12.2). The
 * probe is a cheap computability gate: it answers only whether useful
 * Gaussian support is computable/observable for the exact
 * Camera/RGB/Stable-Mask identity under the declared policy. It is not
 * complete Contributor publication, it is not formal P/N/V Evidence, and it
 * must never classify Selected/Rejected ownership or feed a Candidate.
 */
export const aiSelectSupportProbePolicyVersion = 'anchor-support-probe/v1';

export interface AnchorSupportProbeRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    /**
     * The editor-side Scene Snapshot payload. It never crosses the wire as
     * probe input; the transport retains it so a scene cache/chunk miss can
     * re-register or upload before one bounded retry.
     */
    readonly snapshot: PackedSceneSnapshot;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    /**
     * The identity of one actual probe execution. Same-attempt replay is
     * idempotent; an explicit re-validation submits a new attempt.
     */
    readonly supportProbeAttemptId: string;
    readonly cameraBinding: CameraBinding;
    readonly rgbDigest: string;
    readonly stableMask: MaskArtifact;
    readonly supportProbePolicyVersion: string;
}

/**
 * The only answer the probe may give. `observedGaussianCount` is a
 * diagnostic magnitude for the weak-support soft warning; it is not an
 * ownership set and carries no Stable Gaussian IDs.
 */
export interface AnchorSupportProbeSupport {
    readonly computable: boolean;
    readonly observedGaussianCount: number;
}

export interface AnchorSupportProbeResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly supportProbeAttemptId: string;
    readonly cameraBinding: CameraBinding;
    readonly rgbDigest: string;
    readonly stableMaskDigest: string;
    readonly supportProbePolicyVersion: string;
    readonly support: AnchorSupportProbeSupport;
}

export interface AISelectSupportProbeProvider {
    probeAnchorSupport(
        request: AnchorSupportProbeRequest
    ): Promise<AnchorSupportProbeResponse>;
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

/**
 * The support payload carries exactly the computability verdict and its
 * diagnostic count. Any additional field — in particular Stable Gaussian ID
 * lists or ownership/Evidence-shaped data — fails closed at the boundary.
 */
const isSupport = (value: unknown): value is AnchorSupportProbeSupport => {
    if (!isRecord(value)) {
        return false;
    }
    const keys = Object.keys(value).sort();
    return (
        keys.length === 2 &&
        keys[0] === 'computable' &&
        keys[1] === 'observedGaussianCount' &&
        typeof value.computable === 'boolean' &&
        Number.isSafeInteger(value.observedGaussianCount) &&
        (value.observedGaussianCount as number) >= 0
    );
};

export const isAnchorSupportProbeRequest = (
    value: unknown
): value is AnchorSupportProbeRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isRecord(value.target) &&
        isNonEmptyString(value.target.splatId) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isPackedSceneSnapshot(value.snapshot) &&
        value.snapshot.sceneId === value.sceneId &&
        value.snapshot.sceneVersion === value.sceneVersion &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        isNonEmptyString(value.supportProbeAttemptId) &&
        isCameraBinding(value.cameraBinding) &&
        isDigest(value.rgbDigest) &&
        isMaskArtifact(value.stableMask) &&
        value.stableMask.width === value.cameraBinding.projection.width &&
        value.stableMask.height === value.cameraBinding.projection.height &&
        value.supportProbePolicyVersion === aiSelectSupportProbePolicyVersion
    );
};

export const isAnchorSupportProbeResponse = (
    value: unknown
): value is AnchorSupportProbeResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        isNonEmptyString(value.supportProbeAttemptId) &&
        isCameraBinding(value.cameraBinding) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.stableMaskDigest) &&
        value.supportProbePolicyVersion === aiSelectSupportProbePolicyVersion &&
        isSupport(value.support)
    );
};

/** Fail-closed response matching on the full explicit input identity. */
export const supportProbeResponseMatchesRequest = (
    response: AnchorSupportProbeResponse,
    request: AnchorSupportProbeRequest
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
        response.viewId === request.viewId &&
        response.supportProbeAttemptId === request.supportProbeAttemptId &&
        areCameraBindingsEqual(response.cameraBinding, request.cameraBinding) &&
        response.rgbDigest === request.rgbDigest &&
        response.stableMaskDigest === request.stableMask.digest &&
        response.supportProbePolicyVersion === request.supportProbePolicyVersion
    );
};
