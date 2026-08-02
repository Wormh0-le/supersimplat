import {
    sha256Digest,
    type PackedSceneSnapshot
} from '../scene-snapshot-binary';
import {
    aiSelectRgbRendererVersion,
    isAnchorRgbArtifact,
    parsePngDimensions,
    decodePngBase64,
    type AnchorRgbArtifact
} from './anchor-render-service';
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
import {
    decodeMaskBitsetBase64,
    isMaskArtifact,
    maskBitsetEncoding,
    type MaskArtifact
} from './mask-annotation';
import {
    aiSelectViewAssessmentPolicyVersion,
    isViewAssessmentResult,
    type ViewAssessmentResult
} from './view-assessment';

/**
 * The versioned cross-view automatic Mask policy: the Companion propagates
 * the Anchor's Stable Mask support into the Generated View camera, then runs
 * one single-frame SAM pass on the Generated View RGB. The result binds the
 * exact Generated View RGB and the Anchor RGB it was conditioned on.
 *
 * Ticket 08 moved camera planning to the Target Geometry Hint + bounded
 * local Key-View contracts (`./target-geometry-hint`, `./local-key-view-plan`);
 * this module keeps the per-View render and automatic Mask contracts.
 */
export const aiSelectGeneratedViewMaskPolicyVersion = 'generated-view-mask/v1';

/**
 * The authoritative gsplat render of one planner-owned Generated View. It is
 * the Anchor render contract with a planner-owned `viewId`; `anchor-view`
 * stays reserved for the Anchor route.
 */
export interface AIViewRenderRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly snapshot: PackedSceneSnapshot;
    readonly cameraBinding: CameraBinding;
    readonly viewId: string;
    readonly renderAttemptId: string;
}

export interface AIViewRenderResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly renderAttemptId: string;
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
    readonly rgb: AnchorRgbArtifact;
    readonly rgbRendererVersion: typeof aiSelectRgbRendererVersion;
    readonly rendererId: 'gsplat';
}

export interface GeneratedViewMaskAnchorBinding {
    readonly cameraBinding: CameraBinding;
    readonly rgbDigest: string;
    readonly stableMask: MaskArtifact;
}

export interface GeneratedViewMaskRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly snapshot: PackedSceneSnapshot;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly viewCameraBinding: CameraBinding;
    readonly maskAttemptId: string;
    readonly rgb: AnchorRgbArtifact;
    /** The confirmed Anchor identity the automatic Mask is conditioned on. */
    readonly anchor: GeneratedViewMaskAnchorBinding;
    readonly modelManifestDigest: string;
}

/**
 * Companion-owned propagation diagnostics retained for Ticket 07 View
 * Assessment. They describe the geometric support transfer only; they never
 * carry Stable Gaussian IDs or ownership classification.
 */
export interface GeneratedViewMaskPropagation {
    readonly policyVersion: string;
    readonly projectedSupportCount: number;
    readonly promptCount: number;
}

export interface GeneratedViewMaskResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly maskAttemptId: string;
    /** The exact Generated View RGB digest the mask was produced from. */
    readonly rgbDigest: string;
    /** The exact Anchor RGB digest the mask was conditioned on. */
    readonly anchorRgbDigest: string;
    readonly mask: MaskArtifact;
    readonly maskSource: 'propagated';
    readonly maskPropagation: GeneratedViewMaskPropagation;
    readonly assessment: ViewAssessmentResult;
    readonly modelManifestDigest: string;
}

export interface AISelectViewRenderer {
    renderView(request: AIViewRenderRequest): Promise<AIViewRenderResponse>;
    // Snapshot residency is Companion-local and disposable; see the Anchor.
    releaseSceneSnapshot?(request: AIViewRenderRequest): Promise<void>;
}

export interface AISelectGeneratedViewMaskProvider {
    produceGeneratedViewMask(
        request: GeneratedViewMaskRequest
    ): Promise<GeneratedViewMaskResponse>;
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

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

const isTarget = (value: unknown): value is AITarget => {
    return isRecord(value) && isNonEmptyString(value.splatId);
};

export const isAIViewRenderRequest = (
    value: unknown
): value is AIViewRenderRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isTarget(value.target) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isRecord(value.snapshot) &&
        isNonEmptyString(value.snapshot.sceneId) &&
        isNonEmptyString(value.snapshot.sceneVersion) &&
        value.snapshot.sceneId === value.target.splatId &&
        isCameraBinding(value.cameraBinding) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isNonEmptyString(value.renderAttemptId)
    );
};

export const isAIViewRenderResponse = (
    value: unknown
): value is AIViewRenderResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.renderConfigVersion) &&
        isNonEmptyString(value.renderAttemptId) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isCameraBinding(value.cameraBinding) &&
        isAnchorRgbArtifact(value.rgb) &&
        value.rgbRendererVersion === aiSelectRgbRendererVersion &&
        value.rendererId === 'gsplat'
    );
};

const actualPngDimensions = (
    base64: string
): { readonly width: number; readonly height: number } | null => {
    try {
        return parsePngDimensions(decodePngBase64(base64));
    } catch {
        return null;
    }
};

/**
 * Fail-closed render matching: every identity field must echo the request and
 * the immutable PNG envelope must match its claimed dimensions and the bound
 * CameraBinding projection.
 */
export const viewRenderResponseMatchesRequest = (
    response: AIViewRenderResponse,
    request: AIViewRenderRequest
): boolean => {
    const actualDimensions = actualPngDimensions(response.rgb.pngBase64);
    return (
        actualDimensions !== null &&
        response.requestBinding.targetContextId ===
            request.requestBinding.targetContextId &&
        response.requestBinding.contextRevision ===
            request.requestBinding.contextRevision &&
        areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) &&
        response.targetSplatId === request.target.splatId &&
        response.sceneId === request.snapshot.sceneId &&
        response.sceneVersion === request.snapshot.sceneVersion &&
        response.renderConfigVersion ===
            request.snapshot.renderConfiguration.version &&
        response.renderAttemptId === request.renderAttemptId &&
        response.viewId === request.viewId &&
        areCameraBindingsEqual(response.cameraBinding, request.cameraBinding) &&
        actualDimensions.width === response.rgb.width &&
        actualDimensions.height === response.rgb.height &&
        response.rgb.width === request.cameraBinding.projection.width &&
        response.rgb.height === request.cameraBinding.projection.height
    );
};

const isGeneratedViewMaskAnchorBinding = (
    value: unknown
): value is GeneratedViewMaskAnchorBinding => {
    return (
        isRecord(value) &&
        isCameraBinding(value.cameraBinding) &&
        isDigest(value.rgbDigest) &&
        isMaskArtifact(value.stableMask) &&
        value.stableMask.width === value.cameraBinding.projection.width &&
        value.stableMask.height === value.cameraBinding.projection.height
    );
};

export const isGeneratedViewMaskRequest = (
    value: unknown
): value is GeneratedViewMaskRequest => {
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
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isCameraBinding(value.viewCameraBinding) &&
        isNonEmptyString(value.maskAttemptId) &&
        isAnchorRgbArtifact(value.rgb) &&
        value.rgb.width === value.viewCameraBinding.projection.width &&
        value.rgb.height === value.viewCameraBinding.projection.height &&
        isGeneratedViewMaskAnchorBinding(value.anchor) &&
        isNonEmptyString(value.modelManifestDigest)
    );
};

const isGeneratedViewMaskPropagation = (
    value: unknown
): value is GeneratedViewMaskPropagation => {
    return (
        isRecord(value) &&
        value.policyVersion === aiSelectGeneratedViewMaskPolicyVersion &&
        isNonNegativeSafeInteger(value.projectedSupportCount) &&
        isNonNegativeSafeInteger(value.promptCount)
    );
};

export const isGeneratedViewMaskResponse = (
    value: unknown
): value is GeneratedViewMaskResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isNonEmptyString(value.maskAttemptId) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.anchorRgbDigest) &&
        isMaskArtifact(value.mask) &&
        value.maskSource === 'propagated' &&
        isGeneratedViewMaskPropagation(value.maskPropagation) &&
        isViewAssessmentResult(value.assessment) &&
        isNonEmptyString(value.modelManifestDigest)
    );
};

const artifactDigestMatchesBytes = (artifact: MaskArtifact): boolean => {
    let bytes: Uint8Array;
    try {
        bytes = decodeMaskBitsetBase64(artifact.data);
    } catch {
        return false;
    }
    // A response whose bytes do not match its digest is stale or corrupt.
    return sha256Digest(bytes) === artifact.digest;
};

/**
 * Fail-closed mask matching: every identity field must echo the request, the
 * mask must be bound to the exact Generated View RGB and Anchor RGB identity,
 * and the artifact digest must match its decoded bytes.
 */
export const generatedViewMaskResponseMatchesRequest = (
    response: GeneratedViewMaskResponse,
    request: GeneratedViewMaskRequest
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
        response.maskAttemptId === request.maskAttemptId &&
        response.rgbDigest === request.rgb.digest &&
        response.anchorRgbDigest === request.anchor.rgbDigest &&
        response.mask.width === request.rgb.width &&
        response.mask.height === request.rgb.height &&
        response.mask.encoding === maskBitsetEncoding &&
        response.assessment.inputIdentity.rgbDigest === response.rgbDigest &&
        response.assessment.inputIdentity.stableMaskDigest ===
            response.mask.digest &&
        response.assessment.inputIdentity.assessmentPolicyVersion ===
            aiSelectViewAssessmentPolicyVersion &&
        response.modelManifestDigest === request.modelManifestDigest &&
        artifactDigestMatchesBytes(response.mask)
    );
};
