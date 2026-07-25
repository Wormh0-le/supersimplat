import { sha256Digest } from '../scene-snapshot-binary';
import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import {
    decodeMaskBitsetBase64,
    isMaskArtifact,
    isMaskPrompt,
    maskBitsetEncoding,
    type MaskArtifact,
    type MaskPrompt
} from './mask-annotation';

/**
 * The single-frame SAM mask contract. Every request binds the full async
 * identity plus the exact authoritative RGB artifact the prompts were placed
 * on, so a stale or partial response can never attach to changed
 * RGB/CameraBinding. The artifact digest pins the decoded bitset bytes.
 */
export interface AIViewMaskRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    /**
     * The identity of one actual mask-production attempt. Same-attempt
     * replay is idempotent; an explicit user Retry submits a new attempt.
     */
    readonly maskAttemptId: string;
    readonly rgb: AnchorRgbArtifact;
    readonly prompts: readonly MaskPrompt[];
    readonly modelManifestDigest: string;
}

export interface MaskResultResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly maskAttemptId: string;
    /** The exact RGB digest the mask was produced from. */
    readonly rgbDigest: string;
    readonly mask: MaskArtifact;
    readonly maskSource: 'single-frame-sam';
    readonly modelManifestDigest: string;
}

export interface AISelectMaskProvider {
    produceMask(request: AIViewMaskRequest): Promise<MaskResultResponse>;
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

const isPositiveSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) > 0;
};

const isBase64 = (value: unknown): value is string => {
    return (
        typeof value === 'string' &&
        value.length > 0 &&
        value.length % 4 === 0 &&
        /^[a-z0-9+/]*={0,2}$/i.test(value)
    );
};

const isAnchorRgbReference = (value: unknown): value is AnchorRgbArtifact => {
    return (
        isRecord(value) &&
        isBase64(value.pngBase64) &&
        isDigest(value.digest) &&
        isPositiveSafeInteger(value.width) &&
        isPositiveSafeInteger(value.height)
    );
};

export const isAIViewMaskRequest = (
    value: unknown
): value is AIViewMaskRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isRecord(value.target) &&
        isNonEmptyString(value.target.splatId) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        isNonEmptyString(value.maskAttemptId) &&
        isAnchorRgbReference(value.rgb) &&
        Array.isArray(value.prompts) &&
        value.prompts.length > 0 &&
        value.prompts.every(isMaskPrompt) &&
        isNonEmptyString(value.modelManifestDigest)
    );
};

export const isMaskResultResponse = (
    value: unknown
): value is MaskResultResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        isNonEmptyString(value.maskAttemptId) &&
        isDigest(value.rgbDigest) &&
        isMaskArtifact(value.mask) &&
        value.maskSource === 'single-frame-sam' &&
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
 * Fail-closed response matching: every identity field must echo the request,
 * the mask must be bound to the exact RGB artifact and dimensions the prompts
 * were placed on, and the artifact digest must match its decoded bytes.
 */
export const maskResponseMatchesRequest = (
    response: MaskResultResponse,
    request: AIViewMaskRequest
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
        response.mask.width === request.rgb.width &&
        response.mask.height === request.rgb.height &&
        response.mask.encoding === maskBitsetEncoding &&
        response.modelManifestDigest === request.modelManifestDigest &&
        artifactDigestMatchesBytes(response.mask)
    );
};
