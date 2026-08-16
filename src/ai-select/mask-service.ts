import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import {
    decodeMaskArtifact,
    isMaskArtifact,
    type MaskArtifact
} from './mask-annotation';
import {
    anchorMaskRankingPolicyVersion,
    isAutoMaskProposalSet,
    isProposalDecision,
    maximumAutoMaskProposalCount,
    type AutoMaskProposalSet,
    type ProposalDecision
} from './mask-proposal';
import {
    isPreviousPredictionLogitsRef,
    previousPredictionLogitsRefDigest,
    type PreviousPredictionLogitsRef
} from './previous-logits-ref';
import { isPromptState, type PromptState } from './prompt-state';
import {
    isViewAssessmentShape,
    type ViewAssessmentShape
} from './view-assessment';

export {
    isPreviousPredictionLogitsRef,
    previousPredictionLogitsRefDigest,
    type PreviousPredictionLogitsRef
};

/**
 * The generic single-frame Mask request. Every request
 * binds the full async identity, exact RGB/CameraBinding, immutable
 * PromptState v2, selected model/capability identity, retained compatibility
 * policy identity, and execution attempt. The RGB identity/dimensions cross the
 * boundary; the RGB artifact itself crosses on first use of a digest and may
 * be omitted afterwards, with the Companion resolving its immutable RGB cache
 * by digest. An optional opaque logits reference marks a refinement attempt.
 */
export interface AIViewMaskRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly cameraBindingDigest: string;
    readonly rgbDigest: string;
    readonly rgbWidth: number;
    readonly rgbHeight: number;
    /** Present on the first request for this RGB digest in a target context. */
    readonly rgb?: AnchorRgbArtifact;
    readonly promptState: PromptState;
    /** Present only on an explicit prompt-revision refinement attempt. */
    readonly previousLogitsRef?: PreviousPredictionLogitsRef;
    readonly modelManifestDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly proposalPolicyVersion: string;
    readonly rankingPolicyVersion: typeof anchorMaskRankingPolicyVersion;
    /**
     * The identity of one actual mask-production attempt. Same-attempt
     * replay is idempotent; changed Prompt intent submits a new attempt.
     */
    readonly proposalAttemptId: string;
}

interface MaskResponseBinding {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly viewId: string;
    readonly cameraBindingDigest: string;
    readonly rgbDigest: string;
    readonly promptStateDigest: string;
    readonly modelManifestDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly proposalPolicyVersion: string;
    readonly rankingPolicyVersion: typeof anchorMaskRankingPolicyVersion;
    readonly proposalAttemptId: string;
}

/**
 * The temporarily retained Companion wire envelope. This type belongs only to
 * the compatibility adapter below; product authoring consumes
 * `MaskResultResponse`, which is singular by construction.
 */
interface MaskProposalEnvelopeResponse extends MaskResponseBinding {
    readonly proposalSet: AutoMaskProposalSet;
    readonly proposalDecision: ProposalDecision;
}

export type SingleMaskResult =
    | {
          readonly status: 'usable';
          readonly mask: MaskArtifact;
          readonly review: ViewAssessmentShape;
          readonly logitsRef?: PreviousPredictionLogitsRef;
          readonly refinementFallback: boolean;
      }
    | {
          readonly status: 'unavailable';
          readonly refinementFallback: boolean;
      };

/** One product Mask result plus the exact compatibility identities. */
export interface MaskResultResponse extends MaskResponseBinding {
    readonly result: SingleMaskResult;
}

export interface AISelectMaskProvider {
    produceMask(request: AIViewMaskRequest): Promise<MaskResultResponse>;
}

export class MaskArtifactInvalidError extends Error {
    constructor(
        message = 'The Selection Service Companion returned an invalid Mask artifact publication.'
    ) {
        super(message);
        this.name = 'MaskArtifactInvalidError';
    }
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

const promptStateMatchesRgb = (
    promptState: PromptState,
    rgbDigest: string,
    rgbWidth: number,
    rgbHeight: number
): boolean => {
    return (
        promptState.rgbDigest === rgbDigest &&
        promptState.points.every(
            (point) => point.xPx < rgbWidth && point.yPx < rgbHeight
        ) &&
        promptState.boxes.every(
            (box) => box.x1Px < rgbWidth && box.y1Px < rgbHeight
        )
    );
};

const visualPromptDiagnosticsMatchRequest = (
    proposal: AutoMaskProposalSet['proposals'][number],
    promptState: PromptState
): boolean => {
    const diagnostics = proposal.promptDiagnostics;
    if (diagnostics === undefined) {
        return promptState.boxes.length === 0;
    }
    const expected = [
        ...promptState.points.map((prompt) => ({
            promptId: prompt.promptId,
            family: 'point' as const,
            polarity: prompt.polarity
        })),
        ...promptState.boxes.map((prompt) => ({
            promptId: prompt.promptId,
            family: 'box' as const,
            polarity: prompt.polarity
        }))
    ];
    const familySatisfied = (
        family: 'point' | 'box',
        polarity?: 'include' | 'exclude'
    ): boolean =>
        diagnostics
            .filter(
                (diagnostic) =>
                    diagnostic.family === family &&
                    (polarity === undefined || diagnostic.polarity === polarity)
            )
            .every((diagnostic) => diagnostic.satisfied);
    const consistency = proposal.promptConsistency;
    return (
        diagnostics.length === expected.length &&
        expected.every((expectedPrompt) =>
            diagnostics.some(
                (diagnostic) =>
                    diagnostic.promptId === expectedPrompt.promptId &&
                    diagnostic.family === expectedPrompt.family &&
                    diagnostic.polarity === expectedPrompt.polarity
            )
        ) &&
        consistency.positivePointsSatisfied ===
            familySatisfied('point', 'include') &&
        consistency.negativePointsSatisfied ===
            familySatisfied('point', 'exclude') &&
        (promptState.boxes.length === 0 ||
            consistency.positiveBoxesSatisfied ===
                familySatisfied('box', 'include'))
    );
};

export const isAIViewMaskRequest = (
    value: unknown
): value is AIViewMaskRequest => {
    if (
        !isRecord(value) ||
        !isAIRequestBinding(value.requestBinding) ||
        !isRecord(value.target) ||
        !isNonEmptyString(value.target.splatId) ||
        value.requestBinding.dependencyToken.splatId !== value.target.splatId ||
        !isNonEmptyString(value.sceneId) ||
        !isNonEmptyString(value.sceneVersion) ||
        !isNonEmptyString(value.viewId) ||
        !isDigest(value.cameraBindingDigest) ||
        !isDigest(value.rgbDigest) ||
        !isPositiveSafeInteger(value.rgbWidth) ||
        !isPositiveSafeInteger(value.rgbHeight) ||
        !isPromptState(value.promptState) ||
        value.promptState.viewId !== value.viewId ||
        !promptStateMatchesRgb(
            value.promptState,
            value.rgbDigest,
            value.rgbWidth,
            value.rgbHeight
        ) ||
        !isNonEmptyString(value.modelManifestDigest) ||
        !isDigest(value.adapterCapabilityDigest) ||
        !isNonEmptyString(value.proposalPolicyVersion) ||
        value.rankingPolicyVersion !== anchorMaskRankingPolicyVersion ||
        !isNonEmptyString(value.proposalAttemptId)
    ) {
        return false;
    }
    if (
        value.rgb !== undefined &&
        (!isAnchorRgbReference(value.rgb) ||
            value.rgb.digest !== value.rgbDigest ||
            value.rgb.width !== value.rgbWidth ||
            value.rgb.height !== value.rgbHeight)
    ) {
        return false;
    }
    if (
        value.previousLogitsRef !== undefined &&
        (!isPreviousPredictionLogitsRef(value.previousLogitsRef) ||
            value.previousLogitsRef.viewId !== value.viewId ||
            value.previousLogitsRef.rgbDigest !== value.rgbDigest ||
            value.previousLogitsRef.targetContextId !==
                value.requestBinding.targetContextId)
    ) {
        return false;
    }
    return true;
};

const hasMaskResponseBinding = (value: UnknownRecord): boolean => {
    return (
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.viewId) &&
        isDigest(value.cameraBindingDigest) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.promptStateDigest) &&
        isNonEmptyString(value.modelManifestDigest) &&
        isDigest(value.adapterCapabilityDigest) &&
        isNonEmptyString(value.proposalPolicyVersion) &&
        value.rankingPolicyVersion === anchorMaskRankingPolicyVersion &&
        isNonEmptyString(value.proposalAttemptId)
    );
};

const isMaskProposalEnvelopeResponse = (
    value: unknown
): value is MaskProposalEnvelopeResponse => {
    if (
        !isRecord(value) ||
        !hasMaskResponseBinding(value) ||
        !isAutoMaskProposalSet(value.proposalSet)
    ) {
        return false;
    }
    return isProposalDecision(value.proposalDecision, value.proposalSet);
};

const isDigestVerifiedMaskArtifact = (
    value: unknown
): value is MaskArtifact => {
    if (!isMaskArtifact(value)) {
        return false;
    }
    try {
        decodeMaskArtifact(value);
        return true;
    } catch {
        return false;
    }
};

const resultLogitsRefMatchesRequest = (
    ref: PreviousPredictionLogitsRef,
    request: AIViewMaskRequest,
    sourceCandidateId?: string
): boolean => {
    return (
        ref.targetContextId === request.requestBinding.targetContextId &&
        ref.viewId === request.viewId &&
        ref.rgbDigest === request.rgbDigest &&
        ref.sourceInferenceAttemptId === request.proposalAttemptId &&
        (sourceCandidateId === undefined ||
            ref.sourceCandidateId === sourceCandidateId)
    );
};

const maskResponseBindingMatchesRequest = (
    response: MaskResponseBinding,
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
        response.cameraBindingDigest === request.cameraBindingDigest &&
        response.rgbDigest === request.rgbDigest &&
        response.promptStateDigest === request.promptState.digest &&
        response.modelManifestDigest === request.modelManifestDigest &&
        response.adapterCapabilityDigest === request.adapterCapabilityDigest &&
        response.proposalPolicyVersion === request.proposalPolicyVersion &&
        response.rankingPolicyVersion === request.rankingPolicyVersion &&
        response.proposalAttemptId === request.proposalAttemptId
    );
};

export const isMaskResultResponse = (
    value: unknown
): value is MaskResultResponse => {
    if (
        !isRecord(value) ||
        !hasMaskResponseBinding(value) ||
        !isRecord(value.result)
    ) {
        return false;
    }
    if (value.result.status === 'unavailable') {
        return (
            Object.keys(value.result).every((key) =>
                ['status', 'refinementFallback'].includes(key)
            ) && typeof value.result.refinementFallback === 'boolean'
        );
    }
    return (
        value.result.status === 'usable' &&
        Object.keys(value.result).every((key) =>
            [
                'status',
                'mask',
                'review',
                'logitsRef',
                'refinementFallback'
            ].includes(key)
        ) &&
        isDigestVerifiedMaskArtifact(value.result.mask) &&
        isViewAssessmentShape(value.result.review) &&
        (value.result.logitsRef === undefined ||
            isPreviousPredictionLogitsRef(value.result.logitsRef)) &&
        typeof value.result.refinementFallback === 'boolean'
    );
};

/**
 * Fail-closed response matching: every identity field must echo the request,
 * and the response must be bound to the exact RGB digest the prompts were
 * placed on (matching on rgbDigest, not on artifact presence) plus the exact
 * request dimensions. The artifact digest must match its decoded bytes.
 */
const maskProposalEnvelopeMatchesRequest = (
    response: MaskProposalEnvelopeResponse,
    request: AIViewMaskRequest
): boolean => {
    return (
        maskResponseBindingMatchesRequest(response, request) &&
        response.proposalSet.viewId === request.viewId &&
        response.proposalSet.rgbDigest === request.rgbDigest &&
        response.proposalSet.promptStateDigest === request.promptState.digest &&
        response.proposalSet.modelManifestDigest ===
            request.modelManifestDigest &&
        response.proposalSet.adapterCapabilityDigest ===
            request.adapterCapabilityDigest &&
        response.proposalSet.proposalPolicyVersion ===
            request.proposalPolicyVersion &&
        response.proposalSet.proposalAttemptId === request.proposalAttemptId &&
        response.proposalDecision.rankingPolicyVersion ===
            request.rankingPolicyVersion &&
        // The editor enforces the single-result Mask contract fail-closed
        // rather than trusting the wire.
        response.proposalSet.proposals.length <=
            maximumAutoMaskProposalCount(
                request.promptState,
                request.previousLogitsRef !== undefined
            ) &&
        response.proposalSet.proposals.every(
            (proposal) =>
                isDigestVerifiedMaskArtifact(proposal.mask) &&
                proposal.mask.width === request.rgbWidth &&
                proposal.mask.height === request.rgbHeight &&
                (proposal.logitsRef === undefined ||
                    resultLogitsRefMatchesRequest(
                        proposal.logitsRef,
                        request,
                        proposal.proposalId
                    )) &&
                visualPromptDiagnosticsMatchRequest(
                    proposal,
                    request.promptState
                )
        )
    );
};

/**
 * Collapse the retained ProposalSet/ProposalDecision wire envelope at the
 * transport seam. Zero eligible results are semantic unavailability; exactly
 * one eligible result carries its Review and refinement lineage. Any malformed
 * or plural envelope fails closed before product authoring can observe it.
 */
export const adaptMaskProposalEnvelope = (
    value: unknown,
    request: AIViewMaskRequest
): MaskResultResponse => {
    if (
        !isMaskProposalEnvelopeResponse(value) ||
        !maskProposalEnvelopeMatchesRequest(value, request)
    ) {
        throw new MaskArtifactInvalidError();
    }
    const refinementFallback =
        value.proposalSet.diagnostics?.refinementFallback === true;
    const proposal = value.proposalSet.proposals[0];
    const result: SingleMaskResult =
        proposal === undefined || !proposal.rankingFeatures.eligible
            ? Object.freeze({
                  status: 'unavailable',
                  refinementFallback
              })
            : Object.freeze({
                  status: 'usable',
                  mask: proposal.mask,
                  review: proposal.review,
                  ...(proposal.logitsRef === undefined
                      ? {}
                      : { logitsRef: proposal.logitsRef }),
                  refinementFallback
              });
    const {
        proposalSet: _proposalSet,
        proposalDecision: _proposalDecision,
        ...binding
    } = value;
    return Object.freeze({ ...binding, result });
};

export const maskResponseMatchesRequest = (
    response: MaskResultResponse,
    request: AIViewMaskRequest
): boolean => {
    return (
        maskResponseBindingMatchesRequest(response, request) &&
        (response.result.status !== 'usable' ||
            (response.result.mask.width === request.rgbWidth &&
                response.result.mask.height === request.rgbHeight &&
                (response.result.logitsRef === undefined ||
                    resultLogitsRefMatchesRequest(
                        response.result.logitsRef,
                        request
                    ))))
    );
};
