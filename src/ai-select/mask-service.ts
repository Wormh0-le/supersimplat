import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
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

export {
    isPreviousPredictionLogitsRef,
    previousPredictionLogitsRefDigest,
    type PreviousPredictionLogitsRef
};

/**
 * The generic single-frame proposal contract (04C contract §5). Every request
 * binds the full async identity, exact RGB/CameraBinding, immutable
 * PromptState v2, selected model/capability identity, bounded proposal
 * policy, and execution attempt. The RGB identity/dimensions always cross the
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
     * replay is idempotent; an explicit user Retry submits a new attempt.
     */
    readonly proposalAttemptId: string;
}

export interface MaskResultResponse {
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
    readonly proposalSet: AutoMaskProposalSet;
    readonly proposalDecision: ProposalDecision;
}

export interface AISelectMaskProvider {
    produceMaskProposals(
        request: AIViewMaskRequest
    ): Promise<MaskResultResponse>;
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

export const isMaskResultResponse = (
    value: unknown
): value is MaskResultResponse => {
    if (
        !isRecord(value) ||
        !isAIRequestBinding(value.requestBinding) ||
        !isNonEmptyString(value.targetSplatId) ||
        !isNonEmptyString(value.sceneId) ||
        !isNonEmptyString(value.sceneVersion) ||
        !isNonEmptyString(value.viewId) ||
        !isDigest(value.cameraBindingDigest) ||
        !isDigest(value.rgbDigest) ||
        !isDigest(value.promptStateDigest) ||
        !isNonEmptyString(value.modelManifestDigest) ||
        !isDigest(value.adapterCapabilityDigest) ||
        !isNonEmptyString(value.proposalPolicyVersion) ||
        value.rankingPolicyVersion !== anchorMaskRankingPolicyVersion ||
        !isNonEmptyString(value.proposalAttemptId) ||
        !isAutoMaskProposalSet(value.proposalSet)
    ) {
        return false;
    }
    return isProposalDecision(value.proposalDecision, value.proposalSet);
};

/**
 * Fail-closed response matching: every identity field must echo the request,
 * and the response must be bound to the exact RGB digest the prompts were
 * placed on (matching on rgbDigest, not on artifact presence) plus the exact
 * request dimensions. The artifact digest must match its decoded bytes.
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
        response.cameraBindingDigest === request.cameraBindingDigest &&
        response.rgbDigest === request.rgbDigest &&
        response.promptStateDigest === request.promptState.digest &&
        response.modelManifestDigest === request.modelManifestDigest &&
        response.adapterCapabilityDigest === request.adapterCapabilityDigest &&
        response.proposalPolicyVersion === request.proposalPolicyVersion &&
        response.rankingPolicyVersion === request.rankingPolicyVersion &&
        response.proposalAttemptId === request.proposalAttemptId &&
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
                proposal.mask.width === request.rgbWidth &&
                proposal.mask.height === request.rgbHeight &&
                visualPromptDiagnosticsMatchRequest(
                    proposal,
                    request.promptState
                )
        )
    );
};
