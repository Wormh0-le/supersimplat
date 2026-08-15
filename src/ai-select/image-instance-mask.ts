import { sha256Digest } from '../scene-snapshot-binary';
import {
    decodePngBase64,
    parsePngDimensions,
    type AnchorRgbArtifact
} from './anchor-render-service';
import {
    decodeMaskBitsetBase64,
    isMaskArtifact,
    type MaskArtifact
} from './mask-annotation';
import {
    isPreviousPredictionLogitsRef,
    type PreviousPredictionLogitsRef
} from './previous-logits-ref';
import { promptCanonicalJson } from './prompt-state';
import {
    isViewAssessmentResult,
    type MaskStableAuthority,
    type ViewAssessmentResult
} from './view-assessment';

/** The compact per-View Image Instance Prompt artifact schema. */
export const imageInstancePromptArtifactSchemaVersion = 1;

/** One authoritative-image pixel coordinate. */
export interface PixelPoint {
    readonly xPx: number;
    readonly yPx: number;
}

/** One positive instance Box in authoritative-image pixel XYXY coordinates. */
export interface PixelBoxXYXY {
    readonly x0Px: number;
    readonly y0Px: number;
    readonly x1Px: number;
    readonly y1Px: number;
}

/**
 * The immutable per-View program passed to the SAM 3 Image instance seam.
 * Polarity is represented by separate point arrays; a negative Box is not a
 * representable current artifact.
 */
export interface ImageInstancePromptArtifact {
    readonly schemaVersion: typeof imageInstancePromptArtifactSchemaVersion;
    readonly targetContextId: string;
    readonly contextRevision: number;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly cameraBindingDigest: string;
    readonly targetGeometryHintDigest?: string;
    readonly localKeyViewPlanDigest?: string;
    readonly adapterCapabilityDigest: string;
    readonly promptSynthesisPolicyDigest?: string;
    readonly positivePoints: readonly PixelPoint[];
    readonly negativePoints: readonly PixelPoint[];
    readonly positiveBox?: PixelBoxXYXY;
    readonly previousLogitsRefDigest?: string;
    readonly multimaskOutput: boolean;
    readonly artifactDigest: string;
}

export type ImageInstancePromptArtifactInput = Omit<
    ImageInstancePromptArtifact,
    'artifactDigest'
>;

type UnknownRecord = Record<string, unknown>;

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;

/**
 * Result digests carry adapter-local floating-point scores. Encode every
 * number by its IEEE-754 bits so Companion and browser do not disagree on
 * JSON exponent or integral-float spelling.
 */
const imageInstanceResultCanonicalJson = (value: unknown): string => {
    if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
            throw new Error(
                'Image Instance Mask result numbers must be finite.'
            );
        }
        const bytes = new Uint8Array(8);
        new DataView(bytes.buffer).setFloat64(0, value, false);
        return `n${[...bytes]
            .map((byte) => byte.toString(16).padStart(2, '0'))
            .join('')}`;
    }
    if (Array.isArray(value)) {
        return `[${value.map(imageInstanceResultCanonicalJson).join(',')}]`;
    }
    if (value !== null && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        return `{${Object.keys(record)
            .sort()
            .map(
                (key) =>
                    `${JSON.stringify(key)}:${imageInstanceResultCanonicalJson(
                        record[key]
                    )}`
            )
            .join(',')}}`;
    }
    const primitive = JSON.stringify(value);
    if (typeof primitive !== 'string') {
        throw new Error(
            'Image Instance Mask result is not canonical JSON data.'
        );
    }
    return primitive;
};

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const hasOnlyUnicodeScalarValues = (value: string): boolean => {
    for (let index = 0; index < value.length; index += 1) {
        const codeUnit = value.charCodeAt(index);
        if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
            const nextCodeUnit = value.charCodeAt(index + 1);
            if (
                index + 1 >= value.length ||
                nextCodeUnit < 0xdc00 ||
                nextCodeUnit > 0xdfff
            ) {
                return false;
            }
            index += 1;
        } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
            return false;
        }
    }
    return true;
};

const isNonEmptyString = (value: unknown): value is string => {
    return (
        typeof value === 'string' &&
        value.trim().length > 0 &&
        hasOnlyUnicodeScalarValues(value)
    );
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && digestPattern.test(value);
};

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

const hasExactKeys = (
    value: UnknownRecord,
    required: readonly string[],
    optional: readonly string[] = []
): boolean => {
    const allowed = new Set([...required, ...optional]);
    return (
        required.every((key) => Object.hasOwn(value, key)) &&
        Object.keys(value).every((key) => allowed.has(key))
    );
};

const isPixelPoint = (value: unknown): value is PixelPoint => {
    return (
        isRecord(value) &&
        hasExactKeys(value, ['xPx', 'yPx']) &&
        isNonNegativeSafeInteger(value.xPx) &&
        isNonNegativeSafeInteger(value.yPx)
    );
};

const isPixelBoxXYXY = (value: unknown): value is PixelBoxXYXY => {
    return (
        isRecord(value) &&
        hasExactKeys(value, ['x0Px', 'y0Px', 'x1Px', 'y1Px']) &&
        isNonNegativeSafeInteger(value.x0Px) &&
        isNonNegativeSafeInteger(value.y0Px) &&
        isNonNegativeSafeInteger(value.x1Px) &&
        isNonNegativeSafeInteger(value.y1Px) &&
        value.x0Px < value.x1Px &&
        value.y0Px < value.y1Px
    );
};

const promptArtifactPayload = (
    value: ImageInstancePromptArtifactInput
): ImageInstancePromptArtifactInput => {
    return {
        schemaVersion: value.schemaVersion,
        targetContextId: value.targetContextId,
        contextRevision: value.contextRevision,
        viewId: value.viewId,
        rgbDigest: value.rgbDigest,
        cameraBindingDigest: value.cameraBindingDigest,
        ...(value.targetGeometryHintDigest === undefined
            ? {}
            : { targetGeometryHintDigest: value.targetGeometryHintDigest }),
        ...(value.localKeyViewPlanDigest === undefined
            ? {}
            : { localKeyViewPlanDigest: value.localKeyViewPlanDigest }),
        adapterCapabilityDigest: value.adapterCapabilityDigest,
        ...(value.promptSynthesisPolicyDigest === undefined
            ? {}
            : {
                  promptSynthesisPolicyDigest: value.promptSynthesisPolicyDigest
              }),
        positivePoints: value.positivePoints.map((point) => ({ ...point })),
        negativePoints: value.negativePoints.map((point) => ({ ...point })),
        ...(value.positiveBox === undefined
            ? {}
            : { positiveBox: { ...value.positiveBox } }),
        ...(value.previousLogitsRefDigest === undefined
            ? {}
            : { previousLogitsRefDigest: value.previousLogitsRefDigest }),
        multimaskOutput: value.multimaskOutput
    };
};

const freezePromptArtifactPayload = (
    value: ImageInstancePromptArtifactInput
): ImageInstancePromptArtifactInput => {
    const payload = promptArtifactPayload(value);
    return Object.freeze({
        ...payload,
        positivePoints: Object.freeze(
            payload.positivePoints.map((point) => Object.freeze({ ...point }))
        ),
        negativePoints: Object.freeze(
            payload.negativePoints.map((point) => Object.freeze({ ...point }))
        ),
        ...(payload.positiveBox === undefined
            ? {}
            : { positiveBox: Object.freeze({ ...payload.positiveBox }) })
    });
};

const isPromptArtifactPayload = (
    value: unknown
): value is ImageInstancePromptArtifactInput => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'targetContextId',
                'contextRevision',
                'viewId',
                'rgbDigest',
                'cameraBindingDigest',
                'adapterCapabilityDigest',
                'positivePoints',
                'negativePoints',
                'multimaskOutput'
            ],
            [
                'targetGeometryHintDigest',
                'localKeyViewPlanDigest',
                'promptSynthesisPolicyDigest',
                'positiveBox',
                'previousLogitsRefDigest'
            ]
        ) ||
        value.schemaVersion !== imageInstancePromptArtifactSchemaVersion ||
        !isNonEmptyString(value.targetContextId) ||
        !isNonNegativeSafeInteger(value.contextRevision) ||
        !isNonEmptyString(value.viewId) ||
        !isDigest(value.rgbDigest) ||
        !isDigest(value.cameraBindingDigest) ||
        !isDigest(value.adapterCapabilityDigest) ||
        !Array.isArray(value.positivePoints) ||
        !value.positivePoints.every(isPixelPoint) ||
        !Array.isArray(value.negativePoints) ||
        !value.negativePoints.every(isPixelPoint) ||
        typeof value.multimaskOutput !== 'boolean'
    ) {
        return false;
    }
    return (
        (value.targetGeometryHintDigest === undefined ||
            isDigest(value.targetGeometryHintDigest)) &&
        (value.localKeyViewPlanDigest === undefined ||
            isDigest(value.localKeyViewPlanDigest)) &&
        (value.promptSynthesisPolicyDigest === undefined ||
            isDigest(value.promptSynthesisPolicyDigest)) &&
        (value.positiveBox === undefined ||
            isPixelBoxXYXY(value.positiveBox)) &&
        (value.previousLogitsRefDigest === undefined ||
            isDigest(value.previousLogitsRefDigest))
    );
};

export const imageInstancePromptArtifactDigest = (
    payload: ImageInstancePromptArtifactInput
): string => {
    return sha256Digest(encoder.encode(promptCanonicalJson(payload)));
};

export const createImageInstancePromptArtifact = (
    input: ImageInstancePromptArtifactInput
): ImageInstancePromptArtifact => {
    if (!isPromptArtifactPayload(input)) {
        throw new Error('Image Instance Prompt artifact input is invalid.');
    }
    const payload = freezePromptArtifactPayload(input);
    return Object.freeze({
        ...payload,
        artifactDigest: imageInstancePromptArtifactDigest(payload)
    });
};

export const isImageInstancePromptArtifact = (
    value: unknown
): value is ImageInstancePromptArtifact => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'targetContextId',
                'contextRevision',
                'viewId',
                'rgbDigest',
                'cameraBindingDigest',
                'adapterCapabilityDigest',
                'positivePoints',
                'negativePoints',
                'multimaskOutput',
                'artifactDigest'
            ],
            [
                'targetGeometryHintDigest',
                'localKeyViewPlanDigest',
                'promptSynthesisPolicyDigest',
                'positiveBox',
                'previousLogitsRefDigest'
            ]
        ) ||
        !isDigest(value.artifactDigest)
    ) {
        return false;
    }
    const { artifactDigest, ...payload } = value;
    return (
        isPromptArtifactPayload(payload) &&
        imageInstancePromptArtifactDigest(payload) === artifactDigest
    );
};

/** The opaque Companion RGB reference schema. */
export const companionRgbArtifactRefSchemaVersion = 1;

/**
 * A Companion-local reference to immutable authoritative RGB bytes. The
 * bytes themselves remain in the current Companion Instance, but every
 * identity required to resolve and verify them crosses the browser boundary.
 */
export interface CompanionRgbArtifactRef {
    readonly schemaVersion: typeof companionRgbArtifactRefSchemaVersion;
    readonly companionInstanceId: string;
    readonly stateId: string;
    readonly rgbDigest: string;
    readonly width: number;
    readonly height: number;
    readonly refDigest: string;
}

export type CompanionRgbArtifactRefInput = Omit<
    CompanionRgbArtifactRef,
    'refDigest'
>;

/** The authoritative RGB payload form used for browser-to-Companion calls. */
export type AuthoritativeRgbArtifact = AnchorRgbArtifact;

/**
 * Exactly one authoritative payload form is present. A digest by itself is
 * intentionally not a valid inference input.
 */
export type ImageInstanceRgbInput =
    | {
          readonly rgbDigest: string;
          readonly width: number;
          readonly height: number;
          readonly artifact: AuthoritativeRgbArtifact;
          readonly companionRgbRef?: never;
      }
    | {
          readonly rgbDigest: string;
          readonly width: number;
          readonly height: number;
          readonly artifact?: never;
          readonly companionRgbRef: CompanionRgbArtifactRef;
      };

/** The semantic identity of one image-instance inference execution. */
export interface ImageInstanceMaskRequestIdentity {
    readonly targetContextId: string;
    readonly contextRevision: number;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptArtifactDigest: string;
    readonly adapterId: string;
    readonly modelManifestDigest: string;
    readonly runtimeDigest: string;
    readonly companionInstanceId: string;
    readonly inferenceAttemptId: string;
}

export const imageInstanceMaskRequestSchemaVersion = 1;

export interface ImageInstanceMaskRequest {
    readonly schemaVersion: typeof imageInstanceMaskRequestSchemaVersion;
    readonly identity: ImageInstanceMaskRequestIdentity;
    readonly rgb: ImageInstanceRgbInput;
    readonly prompt: ImageInstancePromptArtifact;
}

export const imageInstanceMaskResultSchemaVersion = 1;

/**
 * This result is intentionally inference-only. Review, Stable publication,
 * Participation, Evidence, and Candidate state belong to later layers.
 */
export interface ImageInstanceMaskResult {
    readonly schemaVersion: typeof imageInstanceMaskResultSchemaVersion;
    readonly requestIdentity: ImageInstanceMaskRequestIdentity;
    readonly masks: readonly MaskArtifact[];
    readonly modelScores: readonly number[];
    readonly previousLogitsRefs?: readonly PreviousPredictionLogitsRef[];
    readonly diagnostics: ImageInstanceMaskDiagnostics;
    readonly resultDigest: string;
}

/** Semantic unavailability is a completed result, unlike a rejected Promise. */
export interface ImageInstanceMaskDiagnostics {
    readonly outcome: 'available' | 'unavailable';
    readonly refinementFallback?: boolean;
}

export type ImageInstanceMaskResultInput = Omit<
    ImageInstanceMaskResult,
    'resultDigest'
>;

/** The separate Mask Review record required by Stable publication. */
export type ImageInstanceMaskReviewResult = ViewAssessmentResult;

export const imageInstanceMaskPublicationCommandSchemaVersion = 1;

/**
 * The minimal browser-owned command that can later promote one inference
 * result. It deliberately does not perform publication itself.
 */
export interface ImageInstanceMaskPublicationCommand {
    readonly schemaVersion: typeof imageInstanceMaskPublicationCommandSchemaVersion;
    readonly targetContextId: string;
    readonly contextRevision: number;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptArtifactDigest: string;
    readonly inferenceResultDigest: string;
    readonly chosenMaskDigest: string;
    readonly review: ImageInstanceMaskReviewResult;
    readonly currentStableAuthority: MaskStableAuthority;
    readonly currentStableMaskId?: string;
    readonly publicationPolicyDigest: string;
    readonly publicationAttemptId: string;
    readonly commandDigest: string;
}

export type ImageInstanceMaskPublicationCommandInput = Omit<
    ImageInstanceMaskPublicationCommand,
    'commandDigest'
>;

/**
 * The single SAM 3 Image adapter seam used by Anchor and future per-View
 * work. Refinement transports only `previousLogitsRefDigest`; the current
 * Companion resolves it to its own local logits state before SAM invocation.
 */
export interface ImageInstanceMaskProvider {
    infer(request: ImageInstanceMaskRequest): Promise<ImageInstanceMaskResult>;
}

export class ImageInstanceMaskContractError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'ImageInstanceMaskContractError';
    }
}

export const companionRgbArtifactRefDigest = (
    payload: CompanionRgbArtifactRefInput
): string => {
    return sha256Digest(encoder.encode(promptCanonicalJson(payload)));
};

export const createCompanionRgbArtifactRef = (
    input: CompanionRgbArtifactRefInput
): CompanionRgbArtifactRef => {
    if (
        input.schemaVersion !== companionRgbArtifactRefSchemaVersion ||
        !isNonEmptyString(input.companionInstanceId) ||
        !isNonEmptyString(input.stateId) ||
        !isDigest(input.rgbDigest) ||
        !isNonNegativeSafeInteger(input.width) ||
        input.width === 0 ||
        !isNonNegativeSafeInteger(input.height) ||
        input.height === 0
    ) {
        throw new ImageInstanceMaskContractError(
            'Companion RGB reference input is invalid.'
        );
    }
    const payload = Object.freeze({ ...input });
    return Object.freeze({
        ...payload,
        refDigest: companionRgbArtifactRefDigest(payload)
    });
};

export const isCompanionRgbArtifactRef = (
    value: unknown
): value is CompanionRgbArtifactRef => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'schemaVersion',
            'companionInstanceId',
            'stateId',
            'rgbDigest',
            'width',
            'height',
            'refDigest'
        ]) ||
        value.schemaVersion !== companionRgbArtifactRefSchemaVersion ||
        !isNonEmptyString(value.companionInstanceId) ||
        !isNonEmptyString(value.stateId) ||
        !isDigest(value.rgbDigest) ||
        !isNonNegativeSafeInteger(value.width) ||
        value.width === 0 ||
        !isNonNegativeSafeInteger(value.height) ||
        value.height === 0 ||
        !isDigest(value.refDigest)
    ) {
        return false;
    }
    const { refDigest, ...payload } = value;
    return (
        companionRgbArtifactRefDigest(
            payload as CompanionRgbArtifactRefInput
        ) === refDigest
    );
};

const isAuthoritativeRgbArtifact = (
    value: unknown
): value is AuthoritativeRgbArtifact => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, ['pngBase64', 'digest', 'width', 'height']) ||
        !isNonEmptyString(value.pngBase64) ||
        !isDigest(value.digest) ||
        !isNonNegativeSafeInteger(value.width) ||
        value.width === 0 ||
        !isNonNegativeSafeInteger(value.height) ||
        value.height === 0
    ) {
        return false;
    }
    try {
        const bytes = decodePngBase64(value.pngBase64);
        const dimensions = parsePngDimensions(bytes);
        return (
            sha256Digest(bytes) === value.digest &&
            dimensions.width === value.width &&
            dimensions.height === value.height
        );
    } catch {
        return false;
    }
};

export const isImageInstanceRgbInput = (
    value: unknown
): value is ImageInstanceRgbInput => {
    if (
        !isRecord(value) ||
        !isDigest(value.rgbDigest) ||
        !isNonNegativeSafeInteger(value.width) ||
        value.width === 0 ||
        !isNonNegativeSafeInteger(value.height) ||
        value.height === 0
    ) {
        return false;
    }
    if (
        hasExactKeys(value, ['rgbDigest', 'width', 'height', 'artifact']) &&
        isAuthoritativeRgbArtifact(value.artifact)
    ) {
        return (
            value.artifact.digest === value.rgbDigest &&
            value.artifact.width === value.width &&
            value.artifact.height === value.height
        );
    }
    if (
        hasExactKeys(value, [
            'rgbDigest',
            'width',
            'height',
            'companionRgbRef'
        ]) &&
        isCompanionRgbArtifactRef(value.companionRgbRef)
    ) {
        return (
            value.companionRgbRef.rgbDigest === value.rgbDigest &&
            value.companionRgbRef.width === value.width &&
            value.companionRgbRef.height === value.height
        );
    }
    return false;
};

export const imageInstanceMaskRequestIdentityDigest = (
    identity: ImageInstanceMaskRequestIdentity
): string => {
    return sha256Digest(encoder.encode(promptCanonicalJson(identity)));
};

export const isImageInstanceMaskRequestIdentity = (
    value: unknown
): value is ImageInstanceMaskRequestIdentity => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'targetContextId',
            'contextRevision',
            'viewId',
            'rgbDigest',
            'promptArtifactDigest',
            'adapterId',
            'modelManifestDigest',
            'runtimeDigest',
            'companionInstanceId',
            'inferenceAttemptId'
        ]) &&
        isNonEmptyString(value.targetContextId) &&
        isNonNegativeSafeInteger(value.contextRevision) &&
        isNonEmptyString(value.viewId) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.promptArtifactDigest) &&
        isNonEmptyString(value.adapterId) &&
        isNonEmptyString(value.modelManifestDigest) &&
        isDigest(value.runtimeDigest) &&
        isNonEmptyString(value.companionInstanceId) &&
        isNonEmptyString(value.inferenceAttemptId)
    );
};

const pointIsInsideRgb = (
    point: PixelPoint,
    rgb: Pick<ImageInstanceRgbInput, 'width' | 'height'>
): boolean => {
    return point.xPx < rgb.width && point.yPx < rgb.height;
};

const boxIsInsideRgb = (
    box: PixelBoxXYXY,
    rgb: Pick<ImageInstanceRgbInput, 'width' | 'height'>
): boolean => {
    return box.x1Px <= rgb.width && box.y1Px <= rgb.height;
};

const promptMatchesMultimaskPolicy = (
    prompt: ImageInstancePromptArtifact
): boolean => {
    return prompt.multimaskOutput === false;
};

const promptHasPositiveSeed = (
    prompt: ImageInstancePromptArtifact
): boolean => {
    return prompt.positivePoints.length > 0 || prompt.positiveBox !== undefined;
};

export const isImageInstanceMaskRequest = (
    value: unknown
): value is ImageInstanceMaskRequest => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, ['schemaVersion', 'identity', 'rgb', 'prompt']) ||
        value.schemaVersion !== imageInstanceMaskRequestSchemaVersion ||
        !isImageInstanceMaskRequestIdentity(value.identity) ||
        !isImageInstanceRgbInput(value.rgb) ||
        !isImageInstancePromptArtifact(value.prompt)
    ) {
        return false;
    }
    const { identity, rgb, prompt } = value;
    return (
        identity.targetContextId === prompt.targetContextId &&
        identity.contextRevision === prompt.contextRevision &&
        identity.viewId === prompt.viewId &&
        identity.rgbDigest === rgb.rgbDigest &&
        identity.rgbDigest === prompt.rgbDigest &&
        identity.promptArtifactDigest === prompt.artifactDigest &&
        (rgb.companionRgbRef === undefined ||
            rgb.companionRgbRef.companionInstanceId ===
                identity.companionInstanceId) &&
        promptHasPositiveSeed(prompt) &&
        prompt.positivePoints.every((point) => pointIsInsideRgb(point, rgb)) &&
        prompt.negativePoints.every((point) => pointIsInsideRgb(point, rgb)) &&
        (prompt.positiveBox === undefined ||
            boxIsInsideRgb(prompt.positiveBox, rgb)) &&
        promptMatchesMultimaskPolicy(prompt)
    );
};

const maskArtifactDigestMatchesBytes = (artifact: MaskArtifact): boolean => {
    try {
        return (
            sha256Digest(decodeMaskBitsetBase64(artifact.data)) ===
            artifact.digest
        );
    } catch {
        return false;
    }
};

const isImageInstanceMaskDiagnostics = (
    value: unknown
): value is ImageInstanceMaskDiagnostics => {
    return (
        isRecord(value) &&
        hasExactKeys(value, ['outcome'], ['refinementFallback']) &&
        (value.outcome === 'available' || value.outcome === 'unavailable') &&
        (value.refinementFallback === undefined ||
            typeof value.refinementFallback === 'boolean')
    );
};

const isImageInstanceMaskResultInput = (
    value: unknown
): value is ImageInstanceMaskResultInput => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'requestIdentity',
                'masks',
                'modelScores',
                'diagnostics'
            ],
            ['previousLogitsRefs']
        ) ||
        value.schemaVersion !== imageInstanceMaskResultSchemaVersion ||
        !isImageInstanceMaskRequestIdentity(value.requestIdentity) ||
        !Array.isArray(value.masks) ||
        value.masks.length > 1 ||
        !value.masks.every(
            (mask) =>
                isMaskArtifact(mask) && maskArtifactDigestMatchesBytes(mask)
        ) ||
        !Array.isArray(value.modelScores) ||
        value.modelScores.length !== value.masks.length ||
        !value.modelScores.every(
            (score) => typeof score === 'number' && Number.isFinite(score)
        ) ||
        !isImageInstanceMaskDiagnostics(value.diagnostics)
    ) {
        return false;
    }
    if (
        value.previousLogitsRefs !== undefined &&
        (!Array.isArray(value.previousLogitsRefs) ||
            value.previousLogitsRefs.length !== value.masks.length ||
            !value.previousLogitsRefs.every(isPreviousPredictionLogitsRef))
    ) {
        return false;
    }
    return value.masks.length === 0
        ? value.diagnostics.outcome === 'unavailable'
        : value.diagnostics.outcome === 'available';
};

const copyMaskArtifact = (artifact: MaskArtifact): MaskArtifact => {
    return Object.freeze({ ...artifact });
};

const copyPreviousLogitsRef = (
    reference: PreviousPredictionLogitsRef
): PreviousPredictionLogitsRef => {
    return Object.freeze({
        ...reference,
        shape: Object.freeze([...reference.shape])
    });
};

const copyImageInstanceMaskResultInput = (
    input: ImageInstanceMaskResultInput
): ImageInstanceMaskResultInput => {
    return Object.freeze({
        schemaVersion: input.schemaVersion,
        requestIdentity: Object.freeze({ ...input.requestIdentity }),
        masks: Object.freeze(input.masks.map(copyMaskArtifact)),
        modelScores: Object.freeze([...input.modelScores]),
        ...(input.previousLogitsRefs === undefined
            ? {}
            : {
                  previousLogitsRefs: Object.freeze(
                      input.previousLogitsRefs.map(copyPreviousLogitsRef)
                  )
              }),
        diagnostics: Object.freeze({ ...input.diagnostics })
    });
};

export const imageInstanceMaskResultDigest = (
    payload: ImageInstanceMaskResultInput
): string => {
    return sha256Digest(
        encoder.encode(imageInstanceResultCanonicalJson(payload))
    );
};

export const createImageInstanceMaskResult = (
    input: ImageInstanceMaskResultInput
): ImageInstanceMaskResult => {
    if (!isImageInstanceMaskResultInput(input)) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask result input is invalid.'
        );
    }
    const payload = copyImageInstanceMaskResultInput(input);
    return Object.freeze({
        ...payload,
        resultDigest: imageInstanceMaskResultDigest(payload)
    });
};

export const isImageInstanceMaskResult = (
    value: unknown
): value is ImageInstanceMaskResult => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'requestIdentity',
                'masks',
                'modelScores',
                'diagnostics',
                'resultDigest'
            ],
            ['previousLogitsRefs']
        ) ||
        !isDigest(value.resultDigest)
    ) {
        return false;
    }
    const { resultDigest, ...payload } = value;
    return (
        isImageInstanceMaskResultInput(payload) &&
        imageInstanceMaskResultDigest(payload) === resultDigest
    );
};

const isImageInstanceMaskPublicationCommandInput = (
    value: unknown
): value is ImageInstanceMaskPublicationCommandInput => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'targetContextId',
                'contextRevision',
                'viewId',
                'rgbDigest',
                'promptArtifactDigest',
                'inferenceResultDigest',
                'chosenMaskDigest',
                'review',
                'currentStableAuthority',
                'publicationPolicyDigest',
                'publicationAttemptId'
            ],
            ['currentStableMaskId']
        ) ||
        value.schemaVersion !==
            imageInstanceMaskPublicationCommandSchemaVersion ||
        !isNonEmptyString(value.targetContextId) ||
        !isNonNegativeSafeInteger(value.contextRevision) ||
        !isNonEmptyString(value.viewId) ||
        !isDigest(value.rgbDigest) ||
        !isDigest(value.promptArtifactDigest) ||
        !isDigest(value.inferenceResultDigest) ||
        !isDigest(value.chosenMaskDigest) ||
        !isViewAssessmentResult(value.review) ||
        (value.currentStableAuthority !== 'automatic' &&
            value.currentStableAuthority !== 'user-confirmed') ||
        (value.currentStableMaskId !== undefined &&
            !isNonEmptyString(value.currentStableMaskId)) ||
        !isDigest(value.publicationPolicyDigest) ||
        !isNonEmptyString(value.publicationAttemptId)
    ) {
        return false;
    }
    return (
        value.review.inputIdentity.rgbDigest === value.rgbDigest &&
        value.review.inputIdentity.stableMaskDigest === value.chosenMaskDigest
    );
};

const copyImageInstanceMaskReviewResult = (
    review: ImageInstanceMaskReviewResult
): ImageInstanceMaskReviewResult => {
    return Object.freeze({
        ...review,
        reasons: Object.freeze([...review.reasons]),
        actionableReasons: Object.freeze([...review.actionableReasons]),
        inputIdentity: Object.freeze({ ...review.inputIdentity }),
        ...(review.diagnostics === undefined
            ? {}
            : { diagnostics: Object.freeze({ ...review.diagnostics }) })
    });
};

const copyImageInstanceMaskPublicationCommandInput = (
    input: ImageInstanceMaskPublicationCommandInput
): ImageInstanceMaskPublicationCommandInput => {
    return Object.freeze({
        ...input,
        review: copyImageInstanceMaskReviewResult(input.review)
    });
};

export const imageInstanceMaskPublicationCommandDigest = (
    payload: ImageInstanceMaskPublicationCommandInput
): string => {
    return sha256Digest(encoder.encode(promptCanonicalJson(payload)));
};

export const createImageInstanceMaskPublicationCommand = (
    input: ImageInstanceMaskPublicationCommandInput
): ImageInstanceMaskPublicationCommand => {
    if (!isImageInstanceMaskPublicationCommandInput(input)) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask publication command input is invalid.'
        );
    }
    const payload = copyImageInstanceMaskPublicationCommandInput(input);
    return Object.freeze({
        ...payload,
        commandDigest: imageInstanceMaskPublicationCommandDigest(payload)
    });
};

export const isImageInstanceMaskPublicationCommand = (
    value: unknown
): value is ImageInstanceMaskPublicationCommand => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'targetContextId',
                'contextRevision',
                'viewId',
                'rgbDigest',
                'promptArtifactDigest',
                'inferenceResultDigest',
                'chosenMaskDigest',
                'review',
                'currentStableAuthority',
                'publicationPolicyDigest',
                'publicationAttemptId',
                'commandDigest'
            ],
            ['currentStableMaskId']
        ) ||
        !isDigest(value.commandDigest)
    ) {
        return false;
    }
    const { commandDigest, ...payload } = value;
    return (
        isImageInstanceMaskPublicationCommandInput(payload) &&
        imageInstanceMaskPublicationCommandDigest(payload) === commandDigest
    );
};

const identitiesMatch = (
    left: ImageInstanceMaskRequestIdentity,
    right: ImageInstanceMaskRequestIdentity
): boolean => {
    return (
        left.targetContextId === right.targetContextId &&
        left.contextRevision === right.contextRevision &&
        left.viewId === right.viewId &&
        left.rgbDigest === right.rgbDigest &&
        left.promptArtifactDigest === right.promptArtifactDigest &&
        left.adapterId === right.adapterId &&
        left.modelManifestDigest === right.modelManifestDigest &&
        left.runtimeDigest === right.runtimeDigest &&
        left.companionInstanceId === right.companionInstanceId &&
        left.inferenceAttemptId === right.inferenceAttemptId
    );
};

const resultRefMatchesIdentity = (
    reference: PreviousPredictionLogitsRef,
    identity: ImageInstanceMaskRequestIdentity
): boolean => {
    return (
        reference.companionInstanceId === identity.companionInstanceId &&
        reference.targetContextId === identity.targetContextId &&
        reference.viewId === identity.viewId &&
        reference.rgbDigest === identity.rgbDigest &&
        reference.adapterRuntimeDigest === identity.runtimeDigest
    );
};

/**
 * Verify the browser-held opaque ref before a refinement request is admitted.
 * The request carries only the ref digest; this helper is used where the
 * browser still holds the corresponding opaque metadata.
 */
export const previousLogitsRefMatchesImageInstanceMaskRequest = (
    reference: PreviousPredictionLogitsRef,
    request: ImageInstanceMaskRequest
): boolean => {
    return (
        isPreviousPredictionLogitsRef(reference) &&
        isImageInstanceMaskRequest(request) &&
        request.prompt.previousLogitsRefDigest === reference.refDigest &&
        !request.prompt.multimaskOutput &&
        resultRefMatchesIdentity(reference, request.identity)
    );
};

/**
 * Resolve an opaque refinement reference inside the current Companion scope.
 * The request intentionally carries only the canonical ref digest, never
 * logits or a browser-supplied tensor. A missing or incompatible local ref
 * is a fresh-inference fallback; resolver failures remain technical errors.
 */
export const resolveImageInstanceMaskRefinementRef = (
    request: ImageInstanceMaskRequest,
    currentCompanionInstanceId: string,
    resolve: (refDigest: string) => PreviousPredictionLogitsRef | undefined
): PreviousPredictionLogitsRef | undefined => {
    if (
        !isImageInstanceMaskRequest(request) ||
        !isNonEmptyString(currentCompanionInstanceId)
    ) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask request is invalid before refinement resolution.'
        );
    }
    if (request.identity.companionInstanceId !== currentCompanionInstanceId) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask request is not bound to the current Companion Instance.'
        );
    }
    const refDigest = request.prompt.previousLogitsRefDigest;
    if (refDigest === undefined) {
        return undefined;
    }
    const reference = resolve(refDigest);
    return reference !== undefined &&
        previousLogitsRefMatchesImageInstanceMaskRequest(reference, request)
        ? copyPreviousLogitsRef(reference)
        : undefined;
};

/**
 * Match a completed result against every inference identity before exposing
 * it to browser state. Semantic unavailable is allowed; malformed or stale
 * output is not.
 */
export const imageInstanceMaskResultMatchesRequest = (
    result: ImageInstanceMaskResult,
    request: ImageInstanceMaskRequest
): boolean => {
    if (
        !isImageInstanceMaskResult(result) ||
        !isImageInstanceMaskRequest(request) ||
        !identitiesMatch(result.requestIdentity, request.identity) ||
        result.masks.some(
            (mask) =>
                mask.width !== request.rgb.width ||
                mask.height !== request.rgb.height
        ) ||
        result.masks.length > 1
    ) {
        return false;
    }
    return (
        result.previousLogitsRefs === undefined ||
        result.previousLogitsRefs.every((reference) =>
            resultRefMatchesIdentity(reference, request.identity)
        )
    );
};

/**
 * Validate a publication command against the independently produced Prompt
 * and inference artifacts. Publication policy and registry mutation remain a
 * later browser-owned step.
 */
export const imageInstanceMaskPublicationCommandMatchesArtifacts = (
    command: ImageInstanceMaskPublicationCommand,
    artifacts: {
        readonly prompt: ImageInstancePromptArtifact;
        readonly result: ImageInstanceMaskResult;
    }
): boolean => {
    const { prompt, result } = artifacts;
    return (
        isImageInstanceMaskPublicationCommand(command) &&
        isImageInstancePromptArtifact(prompt) &&
        isImageInstanceMaskResult(result) &&
        command.targetContextId === result.requestIdentity.targetContextId &&
        command.contextRevision === result.requestIdentity.contextRevision &&
        command.viewId === result.requestIdentity.viewId &&
        command.rgbDigest === result.requestIdentity.rgbDigest &&
        command.promptArtifactDigest === prompt.artifactDigest &&
        command.promptArtifactDigest ===
            result.requestIdentity.promptArtifactDigest &&
        command.inferenceResultDigest === result.resultDigest &&
        result.masks.some((mask) => mask.digest === command.chosenMaskDigest)
    );
};

const copyImageInstanceMaskRequest = (
    request: ImageInstanceMaskRequest
): ImageInstanceMaskRequest => {
    const prompt = createImageInstancePromptArtifact({
        schemaVersion: request.prompt.schemaVersion,
        targetContextId: request.prompt.targetContextId,
        contextRevision: request.prompt.contextRevision,
        viewId: request.prompt.viewId,
        rgbDigest: request.prompt.rgbDigest,
        cameraBindingDigest: request.prompt.cameraBindingDigest,
        ...(request.prompt.targetGeometryHintDigest === undefined
            ? {}
            : {
                  targetGeometryHintDigest:
                      request.prompt.targetGeometryHintDigest
              }),
        ...(request.prompt.localKeyViewPlanDigest === undefined
            ? {}
            : {
                  localKeyViewPlanDigest: request.prompt.localKeyViewPlanDigest
              }),
        adapterCapabilityDigest: request.prompt.adapterCapabilityDigest,
        ...(request.prompt.promptSynthesisPolicyDigest === undefined
            ? {}
            : {
                  promptSynthesisPolicyDigest:
                      request.prompt.promptSynthesisPolicyDigest
              }),
        positivePoints: request.prompt.positivePoints,
        negativePoints: request.prompt.negativePoints,
        ...(request.prompt.positiveBox === undefined
            ? {}
            : { positiveBox: request.prompt.positiveBox }),
        ...(request.prompt.previousLogitsRefDigest === undefined
            ? {}
            : {
                  previousLogitsRefDigest:
                      request.prompt.previousLogitsRefDigest
              }),
        multimaskOutput: request.prompt.multimaskOutput
    });
    const rgb =
        request.rgb.artifact === undefined
            ? Object.freeze({
                  rgbDigest: request.rgb.rgbDigest,
                  width: request.rgb.width,
                  height: request.rgb.height,
                  companionRgbRef: createCompanionRgbArtifactRef(
                      request.rgb.companionRgbRef
                  )
              })
            : Object.freeze({
                  rgbDigest: request.rgb.rgbDigest,
                  width: request.rgb.width,
                  height: request.rgb.height,
                  artifact: Object.freeze({ ...request.rgb.artifact })
              });
    return Object.freeze({
        schemaVersion: request.schemaVersion,
        identity: Object.freeze({ ...request.identity }),
        rgb,
        prompt
    });
};

/**
 * Validate before the provider can start inference and again before a
 * completed result can cross into browser state.
 */
export const inferImageInstanceMask = async (
    provider: ImageInstanceMaskProvider,
    request: ImageInstanceMaskRequest
): Promise<ImageInstanceMaskResult> => {
    if (!isImageInstanceMaskRequest(request)) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask request is invalid before inference.'
        );
    }
    const result = await provider.infer(copyImageInstanceMaskRequest(request));
    if (!imageInstanceMaskResultMatchesRequest(result, request)) {
        throw new ImageInstanceMaskContractError(
            'Image Instance Mask provider returned an invalid or stale result.'
        );
    }
    const { resultDigest: _resultDigest, ...payload } = result;
    return createImageInstanceMaskResult(payload);
};
