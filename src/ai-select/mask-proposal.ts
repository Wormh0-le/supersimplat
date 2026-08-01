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
import {
    isViewAssessmentShape,
    type ViewAssessmentShape
} from './view-assessment';

// Schema v2 binds numbers by binary64 value instead of language-specific JSON
// spelling, keeping browser and Companion artifact identity deterministic.
// Schema v3 (ticket 04C) rotated the proposal policy/ranking identity for the
// SAM 3 Image instance adapter and bound the optional opaque logits ref.
// Schema v4 (ticket 07A) removes the superseded v1 ranking machinery
// (pairwise relations, material-distinctness clustering, margin calibration,
// Gaussian support sanity) and binds the per-candidate Mask Review record.
export const autoMaskProposalSetSchemaVersion = 4;
export const autoMaskProposalPolicyVersion =
    'auto-mask-proposals/bounded-source-order-v2';
export const anchorMaskRankingPolicyVersion = 'anchor-mask-ranking/v3';
export const proposalDecisionSchemaVersion = 2;

/** The wire-level retention bound; the policy function may tighten it. */
export const maximumRetainedAutoMaskProposalCount = 3;

/**
 * Multimask policy (04C contract §6, retained by 07A): exactly one include
 * Point, no Box, and no previous-logits refinement retains at most 3
 * candidates; every other program retains at most 1.
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
 * Candidate-local prompt facts preserved for prompt-consistency enforcement.
 * These measurements deliberately do not contain a cross-candidate score.
 */
export interface PromptFamilyDiagnostic {
    readonly promptId: string;
    readonly family: PromptDiagnosticFamily;
    readonly polarity: 'include' | 'exclude';
    readonly satisfied: boolean;
    readonly constraintCoverageFraction?: number;
    readonly candidateCoverageFraction?: number;
}

/**
 * The 07A per-candidate feature record. The v1 ranking pipeline is gone:
 * no pairwise containment/IoU, no material-distinctness clustering, no
 * compactness, no decision-margin features, and no Gaussian support sanity
 * (Gaussian readiness belongs to Ticket 13 Lift Readiness, never to Anchor
 * candidate selection). What remains is exactly what the simplified decision
 * and the candidate choice UI consume.
 */
export interface ProposalRankingFeatures {
    readonly promptConsistency: PromptConsistencyFacts;
    /**
     * A candidate is eligible when every declared prompt fact holds and its
     * Mask Review did not fail (empty/degenerate/full-frame). Ineligible
     * candidates stay in the set for diagnostics but are never offered for
     * preview or Accept.
     */
    readonly eligible: boolean;
    readonly areaFraction: number;
    readonly connectedComponentCount: number;
    readonly modelScore?: number;
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
     * The versioned local Mask Review for this candidate (Ticket 07 policy
     * `local-view-assessment/v2`). Candidates are not Stable Masks, so the
     * record carries no Stable-Mask input identity; Accept for editing
     * remains explicit even when the status is Review.
     */
    readonly review: ViewAssessmentShape;
    /**
     * The opaque Companion-local previous-prediction logits reference for
     * refinement lineage (04C contract §7). Never raw logits.
     */
    readonly logitsRef?: PreviousPredictionLogitsRef;
}

export type ProposalDecisionStatus = 'selected' | 'ambiguous' | 'unavailable';

/**
 * The simplified 07A pre-Stable decision. One-point multimask ambiguity is
 * resolved by explicit user choice, not by margin calibration or clustering:
 * the decision only enumerates the eligible candidates and names the default
 * preview, which is the highest raw model score (never auto-confirmed, never
 * a correctness probability). Structured ranking reason codes are removed;
 * Mask-quality claims live on the per-candidate `review` record instead.
 */
export interface ProposalDecision {
    readonly schemaVersion: typeof proposalDecisionSchemaVersion;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptStateDigest: string;
    readonly proposalSetDigest: string;
    readonly rankingPolicyVersion: typeof anchorMaskRankingPolicyVersion;
    readonly status: ProposalDecisionStatus;
    /**
     * The default preview candidate: the eligible candidate with the highest
     * raw model score (ties broken by lowest sourceIndex). Absent only when
     * no eligible candidate exists.
     */
    readonly selectedProposalId?: string;
    /**
     * Every eligible candidate, ordered by raw model score descending with
     * ties broken by ascending sourceIndex.
     */
    readonly alternativeProposalIds: readonly string[];
}

export interface ProposalTruncationRecord {
    readonly originalCount: number;
    readonly retainedCount: number;
    readonly policy: string;
}

/**
 * Publication-level diagnostics that are not Mask-quality claims. A
 * `refinementFallback` records that a missing/expired/foreign logits ref was
 * discarded and the inference ran fresh without `mask_input` (04C §7).
 */
export interface AutoMaskProposalSetDiagnostics {
    readonly refinementFallback?: boolean;
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
    readonly diagnostics?: AutoMaskProposalSetDiagnostics;
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

const allFactsSatisfied = (value: PromptConsistencyFacts): boolean => {
    return (
        value.positivePointsSatisfied &&
        value.negativePointsSatisfied &&
        value.positiveBoxesSatisfied
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

const isProposalRankingFeatures = (
    value: unknown
): value is ProposalRankingFeatures =>
    isRecord(value) &&
    Object.keys(value).every((key) =>
        [
            'promptConsistency',
            'eligible',
            'areaFraction',
            'connectedComponentCount',
            'modelScore'
        ].includes(key)
    ) &&
    exactBooleanFacts(value.promptConsistency) &&
    typeof value.eligible === 'boolean' &&
    isUnitNumber(value.areaFraction) &&
    Number.isSafeInteger(value.connectedComponentCount) &&
    (value.connectedComponentCount as number) >= 0 &&
    (value.modelScore === undefined || isFiniteNumber(value.modelScore));

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
    if (
        value.diagnostics !== undefined &&
        (!isRecord(value.diagnostics) ||
            !Object.keys(value.diagnostics).every(
                (key) => key === 'refinementFallback'
            ) ||
            typeof value.diagnostics.refinementFallback !== 'boolean')
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
            proposal.rankingFeatures.modelScore !== proposal.modelScore ||
            (proposal.modelScore !== undefined &&
                (typeof proposal.modelScore !== 'number' ||
                    !Number.isFinite(proposal.modelScore))) ||
            (proposal.modelScoreSemantics !== undefined &&
                !isNonEmptyString(proposal.modelScoreSemantics)) ||
            !isViewAssessmentShape(proposal.review) ||
            (proposal.logitsRef !== undefined &&
                !isPreviousPredictionLogitsRef(proposal.logitsRef))
        ) {
            return false;
        }
        // Eligibility is a Companion decision, but its declared necessary
        // conditions are mechanically checkable: a candidate that contradicts
        // a declared prompt fact or failed Mask Review is never eligible.
        if (
            proposal.rankingFeatures.eligible &&
            (!allFactsSatisfied(
                proposal.promptConsistency as PromptConsistencyFacts
            ) ||
                proposal.review.status === 'failed')
        ) {
            return false;
        }
        proposalIds.add(proposal.proposalId);
        sourceIndexes.add(proposal.sourceIndex as number);
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

/**
 * The deterministic 07A default-preview ordering: raw model score descending
 * (absent scores sort last), ties broken by ascending sourceIndex. This is
 * the only use the model score has; it never auto-confirms a candidate.
 */
export const defaultPreviewProposalOrder = (
    proposals: readonly AutoMaskProposal[]
): readonly AutoMaskProposal[] => {
    return [...proposals].sort((left, right) => {
        const leftScore = left.modelScore ?? Number.NEGATIVE_INFINITY;
        const rightScore = right.modelScore ?? Number.NEGATIVE_INFINITY;
        if (leftScore !== rightScore) {
            return rightScore - leftScore;
        }
        return left.sourceIndex - right.sourceIndex;
    });
};

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
                    'alternativeProposalIds'
                ].includes(key)
        ) ||
        !['selected', 'ambiguous', 'unavailable'].includes(
            value.status as string
        ) ||
        !Array.isArray(value.alternativeProposalIds)
    ) {
        return false;
    }
    // The decision must advertise exactly the eligible candidates in the
    // deterministic default-preview order; nothing else is a valid v3
    // decision for this set.
    const expectedAlternatives = defaultPreviewProposalOrder(
        proposalSet.proposals.filter(
            (proposal) => proposal.rankingFeatures.eligible
        )
    ).map((proposal) => proposal.proposalId);
    const alternatives = value.alternativeProposalIds;
    if (
        alternatives.length !== expectedAlternatives.length ||
        alternatives.some(
            (proposalId, index) => proposalId !== expectedAlternatives[index]
        )
    ) {
        return false;
    }
    if (value.status === 'unavailable') {
        return (
            alternatives.length === 0 && value.selectedProposalId === undefined
        );
    }
    if (value.status === 'selected') {
        return (
            alternatives.length === 1 &&
            value.selectedProposalId === alternatives[0]
        );
    }
    return (
        alternatives.length >= 2 && value.selectedProposalId === alternatives[0]
    );
};
