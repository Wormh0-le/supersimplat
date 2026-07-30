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
    type AutoMaskProposalSet,
    type ProposalDecision
} from './mask-proposal';
import { isPromptState, type PromptState } from './prompt-state';

/**
 * The generic single-frame proposal contract. Every request binds the full
 * async identity, exact RGB/CameraBinding, immutable PromptState, selected
 * model/capability identity, bounded proposal policy, and execution attempt.
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
    readonly cameraBindingDigest: string;
    readonly rgb: AnchorRgbArtifact;
    readonly promptState: PromptState;
    readonly modelManifestDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly proposalPolicyVersion: string;
    readonly rankingPolicyVersion: typeof anchorMaskRankingPolicyVersion;
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
    rgb: AnchorRgbArtifact
): boolean => {
    return (
        promptState.rgbDigest === rgb.digest &&
        promptState.points.every(
            (point) => point.xPx < rgb.width && point.yPx < rgb.height
        ) &&
        promptState.boxes.every(
            (box) => box.x1Px < rgb.width && box.y1Px < rgb.height
        ) &&
        promptState.maskConstraints.every(
            (constraint) =>
                constraint.artifact.width === rgb.width &&
                constraint.artifact.height === rgb.height
        )
    );
};

const visualPromptDiagnosticsMatchRequest = (
    proposal: AutoMaskProposalSet['proposals'][number],
    promptState: PromptState
): boolean => {
    if (
        promptState.boxes.length === 0 &&
        promptState.maskConstraints.length === 0
    ) {
        return true;
    }
    const diagnostics = proposal.promptDiagnostics;
    if (diagnostics === undefined) {
        return false;
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
        })),
        ...promptState.maskConstraints.map((prompt) => ({
            promptId: prompt.promptId,
            family: 'mask-constraint' as const,
            polarity: prompt.polarity
        }))
    ];
    const familySatisfied = (
        family: 'point' | 'box' | 'mask-constraint',
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
        (!promptState.boxes.some((prompt) => prompt.polarity === 'include') ||
            consistency.positiveBoxesSatisfied ===
                familySatisfied('box', 'include')) &&
        (!promptState.boxes.some((prompt) => prompt.polarity === 'exclude') ||
            consistency.negativeBoxesSatisfied ===
                familySatisfied('box', 'exclude')) &&
        (promptState.maskConstraints.length === 0 ||
            consistency.maskConstraintsSatisfied ===
                familySatisfied('mask-constraint'))
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
        isDigest(value.cameraBindingDigest) &&
        isAnchorRgbReference(value.rgb) &&
        isPromptState(value.promptState) &&
        value.promptState.viewId === value.viewId &&
        promptStateMatchesRgb(value.promptState, value.rgb) &&
        isNonEmptyString(value.modelManifestDigest) &&
        isDigest(value.adapterCapabilityDigest) &&
        isNonEmptyString(value.proposalPolicyVersion) &&
        value.rankingPolicyVersion === anchorMaskRankingPolicyVersion &&
        isNonEmptyString(value.proposalAttemptId)
    );
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
        response.cameraBindingDigest === request.cameraBindingDigest &&
        response.rgbDigest === request.rgb.digest &&
        response.promptStateDigest === request.promptState.digest &&
        response.modelManifestDigest === request.modelManifestDigest &&
        response.adapterCapabilityDigest === request.adapterCapabilityDigest &&
        response.proposalPolicyVersion === request.proposalPolicyVersion &&
        response.rankingPolicyVersion === request.rankingPolicyVersion &&
        response.proposalAttemptId === request.proposalAttemptId &&
        response.proposalSet.viewId === request.viewId &&
        response.proposalSet.rgbDigest === request.rgb.digest &&
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
        response.proposalSet.proposals.every(
            (proposal) =>
                proposal.mask.width === request.rgb.width &&
                proposal.mask.height === request.rgb.height &&
                visualPromptDiagnosticsMatchRequest(
                    proposal,
                    request.promptState
                )
        )
    );
};
