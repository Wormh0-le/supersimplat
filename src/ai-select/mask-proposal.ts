import { sha256Digest } from '../scene-snapshot-binary';
import {
    decodeMaskBitsetBase64,
    isMaskArtifact,
    type MaskArtifact
} from './mask-annotation';
import {
    isPreviousPredictionLogitsRef,
    type PreviousPredictionLogitsRef
} from './previous-logits-ref';
import type { PromptState } from './prompt-state';

// Schema v2 binds numbers by binary64 value instead of language-specific JSON
// spelling, keeping browser and Companion artifact identity deterministic.
// Schema v3 (ticket 04C) rotates the proposal policy/ranking identity for the
// SAM 3 Image instance adapter and binds the optional opaque logits ref.
export const autoMaskProposalSetSchemaVersion = 3;
export const autoMaskProposalPolicyVersion =
    'auto-mask-proposals/bounded-source-order-v2';
export const anchorMaskRankingPolicyVersion = 'anchor-mask-ranking/v2';
export const proposalDecisionSchemaVersion = 1;

/** The wire-level retention bound; the policy function may tighten it. */
export const maximumRetainedAutoMaskProposalCount = 3;

/**
 * Multimask policy (04C contract §6): exactly one include Point, no Box, and
 * no previous-logits refinement retains at most 3 candidates; every other
 * program retains at most 1.
 */
export const maximumAutoMaskProposalCount = (
    promptState: PromptState,
    hasRefinement: boolean
): number => {
    return !hasRefinement &&
        promptState.boxes.length === 0 &&
        promptState.points.length === 1 &&
        promptState.points[0].polarity === 'include'
        ? 3
        : 1;
};

export interface PromptConsistencyFacts {
    readonly positivePointsSatisfied: boolean;
    readonly negativePointsSatisfied: boolean;
    readonly positiveBoxesSatisfied: boolean;
}

export type PromptDiagnosticFamily = 'point' | 'box';

/**
 * Candidate-local prompt facts preserved for later 2D proposal policy. These
 * measurements deliberately do not contain a cross-candidate score.
 */
export interface PromptFamilyDiagnostic {
    readonly promptId: string;
    readonly family: PromptDiagnosticFamily;
    readonly polarity: 'include' | 'exclude';
    readonly satisfied: boolean;
    readonly constraintCoverageFraction?: number;
    readonly candidateCoverageFraction?: number;
}

export interface AutoMaskProposal {
    readonly proposalId: string;
    readonly mask: MaskArtifact;
    readonly sourceIndex: number;
    readonly modelScore?: number;
    readonly modelScoreSemantics?: string;
    readonly promptConsistency: PromptConsistencyFacts;
    readonly promptDiagnostics?: readonly PromptFamilyDiagnostic[];
    readonly rankingFeatures: ProposalRankingFeatures;
    /**
     * The opaque Companion-local previous-prediction logits reference for
     * refinement lineage (04C contract §7). Never raw logits.
     */
    readonly logitsRef?: PreviousPredictionLogitsRef;
}

export interface PixelBox {
    readonly x0Px: number;
    readonly y0Px: number;
    readonly x1Px: number;
    readonly y1Px: number;
}

export interface ProposalRelation {
    readonly proposalId: string;
    readonly intersectionOverUnion: number;
    readonly areaRatio: number;
    readonly containment: 'contains' | 'contained-by' | 'none';
    readonly materiallyDistinct: boolean;
}

export interface ProposalRankingFeatures {
    readonly promptConsistency: PromptConsistencyFacts;
    readonly eligible: boolean;
    readonly areaFraction: number;
    readonly boundingBox: PixelBox;
    readonly connectedComponentCount: number;
    readonly positivePointComponentIds: readonly number[];
    readonly positivePointBoundaryDistances: readonly number[];
    readonly pairwiseRelations: readonly ProposalRelation[];
    readonly boundaryContactFraction: number;
    readonly compactness: number;
    readonly boxFillRatios: readonly number[];
    readonly boxSpillRatios: readonly number[];
    readonly promptMaskOverlap: number;
    readonly modelScore?: number;
    readonly optionalSupportSanity: {
        readonly participated: boolean;
        readonly changedDecision: boolean;
        readonly policyId?: string;
        readonly computable?: boolean;
        readonly observedGaussianCount?: number;
        readonly supportConcentration?: number;
    };
}

export type ProposalDecisionStatus = 'selected' | 'ambiguous' | 'unavailable';
export type ProposalDecisionReasonCode =
    | 'nested-part-vs-whole'
    | 'similar-score-different-area'
    | 'multiple-disconnected-targets'
    | 'box-spill'
    | 'prompt-conflict'
    | 'neighbour-object-leak-risk'
    | 'model-score-disagreement'
    | 'insufficient-decision-margin';

export interface ProposalDecisionReason {
    readonly code: ProposalDecisionReasonCode;
    readonly proposalIds: readonly string[];
}

export interface ProposalDecision {
    readonly schemaVersion: typeof proposalDecisionSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptStateDigest: string;
    readonly proposalSetDigest: string;
    readonly rankingPolicyVersion: typeof anchorMaskRankingPolicyVersion;
    readonly status: ProposalDecisionStatus;
    /** Suggested proposal for selected/ambiguous; acceptance remains explicit. */
    readonly selectedProposalId?: string;
    readonly alternativeProposalIds: readonly string[];
    readonly reasons: readonly ProposalDecisionReason[];
}

export interface ProposalTruncationRecord {
    readonly originalCount: number;
    readonly retainedCount: number;
    readonly policy: string;
}

export interface AutoMaskProposalSet {
    readonly schemaVersion: typeof autoMaskProposalSetSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptStateDigest: string;
    readonly modelManifestDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly proposalPolicyVersion: string;
    readonly proposalAttemptId: string;
    readonly proposals: readonly AutoMaskProposal[];
    readonly truncation?: ProposalTruncationRecord;
    readonly digest: string;
}

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const canonicalNumber = (value: number): string => {
    if (!Number.isFinite(value)) {
        throw new Error('Proposal identity numbers must be finite.');
    }
    const bytes = new Uint8Array(8);
    new DataView(bytes.buffer).setFloat64(0, value, false);
    return `n${Array.from(bytes, (byte) =>
        byte.toString(16).padStart(2, '0')
    ).join('')}`;
};

const canonicalJson = (value: unknown): string => {
    if (Array.isArray(value)) {
        return `[${value.map(canonicalJson).join(',')}]`;
    }
    if (value !== null && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        return `{${Object.keys(record)
            .filter((key) => record[key] !== undefined)
            .sort()
            .map(
                (key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`
            )
            .join(',')}}`;
    }
    if (typeof value === 'number') {
        return canonicalNumber(value);
    }
    return JSON.stringify(value);
};

export const proposalIdentityDigest = (value: unknown): string => {
    return sha256Digest(encoder.encode(canonicalJson(value)));
};

export const autoMaskProposalSetDigest = (
    value: Omit<AutoMaskProposalSet, 'digest'>
): string => {
    return proposalIdentityDigest(value);
};

const artifactDigestMatchesBytes = (artifact: MaskArtifact): boolean => {
    try {
        return (
            sha256Digest(decodeMaskBitsetBase64(artifact.data)) ===
            artifact.digest
        );
    } catch {
        return false;
    }
};

const exactBooleanFacts = (value: unknown): boolean => {
    if (!isRecord(value)) {
        return false;
    }
    const required = [
        'positivePointsSatisfied',
        'negativePointsSatisfied',
        'positiveBoxesSatisfied'
    ];
    return (
        Object.keys(value).length === required.length &&
        required.every((key) => typeof value[key] === 'boolean')
    );
};

const isFiniteNumber = (value: unknown): value is number =>
    typeof value === 'number' && Number.isFinite(value);

const isUnitNumber = (value: unknown): value is number =>
    isFiniteNumber(value) && value >= 0 && value <= 1;

const isPromptFamilyDiagnostic = (
    value: unknown
): value is PromptFamilyDiagnostic => {
    if (!isRecord(value)) {
        return false;
    }
    const allowed = new Set([
        'promptId',
        'family',
        'polarity',
        'satisfied',
        'constraintCoverageFraction',
        'candidateCoverageFraction'
    ]);
    return (
        Object.keys(value).every((key) => allowed.has(key)) &&
        isNonEmptyString(value.promptId) &&
        ['point', 'box'].includes(value.family as string) &&
        ['include', 'exclude'].includes(value.polarity as string) &&
        typeof value.satisfied === 'boolean' &&
        (value.constraintCoverageFraction === undefined ||
            isUnitNumber(value.constraintCoverageFraction)) &&
        (value.candidateCoverageFraction === undefined ||
            isUnitNumber(value.candidateCoverageFraction))
    );
};

const isNumberArray = (
    value: unknown,
    predicate: (entry: number) => boolean = () => true
): value is number[] =>
    Array.isArray(value) &&
    value.every((entry) => isFiniteNumber(entry) && predicate(entry as number));

const isPixelBox = (value: unknown): value is PixelBox =>
    isRecord(value) &&
    Object.keys(value).length === 4 &&
    ['x0Px', 'y0Px', 'x1Px', 'y1Px'].every((key) =>
        Number.isSafeInteger(value[key])
    ) &&
    (value.x0Px as number) >= 0 &&
    (value.y0Px as number) >= 0 &&
    (value.x1Px as number) >= (value.x0Px as number) &&
    (value.y1Px as number) >= (value.y0Px as number);

const isProposalRelation = (value: unknown): value is ProposalRelation =>
    isRecord(value) &&
    Object.keys(value).length === 5 &&
    isNonEmptyString(value.proposalId) &&
    isUnitNumber(value.intersectionOverUnion) &&
    isFiniteNumber(value.areaRatio) &&
    value.areaRatio >= 1 &&
    ['contains', 'contained-by', 'none'].includes(
        value.containment as string
    ) &&
    typeof value.materiallyDistinct === 'boolean';

const isProposalRankingFeatures = (
    value: unknown
): value is ProposalRankingFeatures =>
    isRecord(value) &&
    Object.keys(value).every((key) =>
        [
            'promptConsistency',
            'eligible',
            'areaFraction',
            'boundingBox',
            'connectedComponentCount',
            'positivePointComponentIds',
            'positivePointBoundaryDistances',
            'pairwiseRelations',
            'boundaryContactFraction',
            'compactness',
            'boxFillRatios',
            'boxSpillRatios',
            'promptMaskOverlap',
            'modelScore',
            'optionalSupportSanity'
        ].includes(key)
    ) &&
    exactBooleanFacts(value.promptConsistency) &&
    typeof value.eligible === 'boolean' &&
    isUnitNumber(value.areaFraction) &&
    isPixelBox(value.boundingBox) &&
    Number.isSafeInteger(value.connectedComponentCount) &&
    (value.connectedComponentCount as number) >= 0 &&
    isNumberArray(
        value.positivePointComponentIds,
        (entry) => Number.isSafeInteger(entry) && entry >= -1
    ) &&
    isNumberArray(
        value.positivePointBoundaryDistances,
        (entry) => entry >= 0
    ) &&
    Array.isArray(value.pairwiseRelations) &&
    value.pairwiseRelations.every(isProposalRelation) &&
    isUnitNumber(value.boundaryContactFraction) &&
    isFiniteNumber(value.compactness) &&
    value.compactness >= 0 &&
    isNumberArray(value.boxFillRatios, (entry) => entry >= 0 && entry <= 1) &&
    isNumberArray(value.boxSpillRatios, (entry) => entry >= 0 && entry <= 1) &&
    isUnitNumber(value.promptMaskOverlap) &&
    (value.modelScore === undefined || isFiniteNumber(value.modelScore)) &&
    isRecord(value.optionalSupportSanity) &&
    Object.keys(value.optionalSupportSanity).every((key) =>
        [
            'participated',
            'changedDecision',
            'policyId',
            'computable',
            'observedGaussianCount',
            'supportConcentration'
        ].includes(key)
    ) &&
    typeof value.optionalSupportSanity.participated === 'boolean' &&
    typeof value.optionalSupportSanity.changedDecision === 'boolean' &&
    (value.optionalSupportSanity.policyId === undefined ||
        isNonEmptyString(value.optionalSupportSanity.policyId)) &&
    (value.optionalSupportSanity.computable === undefined ||
        typeof value.optionalSupportSanity.computable === 'boolean') &&
    (value.optionalSupportSanity.observedGaussianCount === undefined ||
        (Number.isSafeInteger(
            value.optionalSupportSanity.observedGaussianCount
        ) &&
            (value.optionalSupportSanity.observedGaussianCount as number) >=
                0)) &&
    (value.optionalSupportSanity.supportConcentration === undefined ||
        isUnitNumber(value.optionalSupportSanity.supportConcentration));

const promptConsistencyMatches = (left: unknown, right: unknown): boolean =>
    canonicalJson(left) === canonicalJson(right);

export const isAutoMaskProposalSet = (
    value: unknown
): value is AutoMaskProposalSet => {
    if (
        !isRecord(value) ||
        value.schemaVersion !== autoMaskProposalSetSchemaVersion ||
        !isNonEmptyString(value.viewId) ||
        typeof value.rgbDigest !== 'string' ||
        !digestPattern.test(value.rgbDigest) ||
        typeof value.promptStateDigest !== 'string' ||
        !digestPattern.test(value.promptStateDigest) ||
        !isNonEmptyString(value.modelManifestDigest) ||
        typeof value.adapterCapabilityDigest !== 'string' ||
        !digestPattern.test(value.adapterCapabilityDigest) ||
        !isNonEmptyString(value.proposalPolicyVersion) ||
        !isNonEmptyString(value.proposalAttemptId) ||
        !Array.isArray(value.proposals) ||
        value.proposals.length > maximumRetainedAutoMaskProposalCount ||
        typeof value.digest !== 'string' ||
        !digestPattern.test(value.digest)
    ) {
        return false;
    }
    const proposalIds = new Set<string>();
    const sourceIndexes = new Set<number>();
    for (const proposal of value.proposals) {
        if (
            !isRecord(proposal) ||
            !isNonEmptyString(proposal.proposalId) ||
            proposalIds.has(proposal.proposalId) ||
            !Number.isSafeInteger(proposal.sourceIndex) ||
            (proposal.sourceIndex as number) < 0 ||
            sourceIndexes.has(proposal.sourceIndex as number) ||
            !isMaskArtifact(proposal.mask) ||
            !artifactDigestMatchesBytes(proposal.mask) ||
            !exactBooleanFacts(proposal.promptConsistency) ||
            (proposal.promptDiagnostics !== undefined &&
                (!Array.isArray(proposal.promptDiagnostics) ||
                    !proposal.promptDiagnostics.every(
                        isPromptFamilyDiagnostic
                    ) ||
                    new Set(
                        proposal.promptDiagnostics.map(
                            (diagnostic) => diagnostic.promptId
                        )
                    ).size !== proposal.promptDiagnostics.length)) ||
            !isProposalRankingFeatures(proposal.rankingFeatures) ||
            !promptConsistencyMatches(
                proposal.promptConsistency,
                proposal.rankingFeatures.promptConsistency
            ) ||
            proposal.rankingFeatures.boundingBox.x1Px >= proposal.mask.width ||
            proposal.rankingFeatures.boundingBox.y1Px >= proposal.mask.height ||
            proposal.rankingFeatures.modelScore !== proposal.modelScore ||
            (proposal.modelScore !== undefined &&
                (typeof proposal.modelScore !== 'number' ||
                    !Number.isFinite(proposal.modelScore))) ||
            (proposal.modelScoreSemantics !== undefined &&
                !isNonEmptyString(proposal.modelScoreSemantics)) ||
            (proposal.logitsRef !== undefined &&
                !isPreviousPredictionLogitsRef(proposal.logitsRef))
        ) {
            return false;
        }
        proposalIds.add(proposal.proposalId);
        sourceIndexes.add(proposal.sourceIndex as number);
    }
    for (const proposal of value.proposals) {
        const relatedIds = new Set<string>();
        for (const relation of proposal.rankingFeatures.pairwiseRelations) {
            if (
                relation.proposalId === proposal.proposalId ||
                !proposalIds.has(relation.proposalId) ||
                relatedIds.has(relation.proposalId)
            ) {
                return false;
            }
            relatedIds.add(relation.proposalId);
        }
        if (relatedIds.size !== value.proposals.length - 1) {
            return false;
        }
    }
    if (
        value.truncation !== undefined &&
        (!isRecord(value.truncation) ||
            !Number.isSafeInteger(value.truncation.originalCount) ||
            !Number.isSafeInteger(value.truncation.retainedCount) ||
            (value.truncation.originalCount as number) <=
                (value.truncation.retainedCount as number) ||
            value.truncation.retainedCount !== value.proposals.length ||
            !isNonEmptyString(value.truncation.policy))
    ) {
        return false;
    }
    const { digest, ...payload } = value;
    return (
        autoMaskProposalSetDigest(
            payload as Omit<AutoMaskProposalSet, 'digest'>
        ) === digest
    );
};

const proposalDecisionReasonCodes = new Set<ProposalDecisionReasonCode>([
    'nested-part-vs-whole',
    'similar-score-different-area',
    'multiple-disconnected-targets',
    'box-spill',
    'prompt-conflict',
    'neighbour-object-leak-risk',
    'model-score-disagreement',
    'insufficient-decision-margin'
]);

export const isProposalDecision = (
    value: unknown,
    proposalSet: AutoMaskProposalSet
): value is ProposalDecision => {
    if (
        !isRecord(value) ||
        value.schemaVersion !== proposalDecisionSchemaVersion ||
        value.viewId !== proposalSet.viewId ||
        value.rgbDigest !== proposalSet.rgbDigest ||
        value.promptStateDigest !== proposalSet.promptStateDigest ||
        value.proposalSetDigest !== proposalSet.digest ||
        value.rankingPolicyVersion !== anchorMaskRankingPolicyVersion ||
        Object.keys(value).some(
            (key) =>
                ![
                    'schemaVersion',
                    'viewId',
                    'rgbDigest',
                    'promptStateDigest',
                    'proposalSetDigest',
                    'rankingPolicyVersion',
                    'status',
                    'selectedProposalId',
                    'alternativeProposalIds',
                    'reasons'
                ].includes(key)
        ) ||
        !['selected', 'ambiguous', 'unavailable'].includes(
            value.status as string
        ) ||
        !Array.isArray(value.alternativeProposalIds) ||
        !Array.isArray(value.reasons)
    ) {
        return false;
    }
    const proposalIds = new Set(
        proposalSet.proposals.map((proposal) => proposal.proposalId)
    );
    const eligibleProposalIds = new Set(
        proposalSet.proposals
            .filter((proposal) => proposal.rankingFeatures.eligible)
            .map((proposal) => proposal.proposalId)
    );
    const alternatives = value.alternativeProposalIds;
    if (
        alternatives.some(
            (proposalId) =>
                !isNonEmptyString(proposalId) ||
                !proposalIds.has(proposalId) ||
                !eligibleProposalIds.has(proposalId)
        ) ||
        new Set(alternatives).size !== alternatives.length
    ) {
        return false;
    }
    if (value.status === 'unavailable') {
        if (
            value.selectedProposalId !== undefined ||
            alternatives.length !== 0
        ) {
            return false;
        }
    } else if (
        !isNonEmptyString(value.selectedProposalId) ||
        !proposalIds.has(value.selectedProposalId) ||
        !eligibleProposalIds.has(value.selectedProposalId) ||
        !alternatives.includes(value.selectedProposalId)
    ) {
        return false;
    }
    return value.reasons.every(
        (reason) =>
            isRecord(reason) &&
            Object.keys(reason).length === 2 &&
            proposalDecisionReasonCodes.has(
                reason.code as ProposalDecisionReasonCode
            ) &&
            Array.isArray(reason.proposalIds) &&
            reason.proposalIds.every(
                (proposalId) =>
                    isNonEmptyString(proposalId) && proposalIds.has(proposalId)
            ) &&
            new Set(reason.proposalIds).size === reason.proposalIds.length
    );
};
