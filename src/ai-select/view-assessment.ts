import type { AIViewParticipation } from './ai-view';

export const aiSelectViewAssessmentPolicyVersion = 'local-view-assessment/v2';

export type ViewAssessmentStatus = 'good' | 'review' | 'failed';

/**
 * The Final Spec v1.3 §14.1 Mask Review reason vocabulary. Tracker
 * propagation and Gaussian visibility/support are not Mask-quality inputs:
 * `propagation-uncertain` is deleted (no tracker propagation exists) and
 * `weak-gaussian-support` belongs to Ticket 13 Lift Readiness.
 */
export type ReviewReason =
    | 'prompt-inconsistent'
    | 'target-materially-clipped'
    | 'severely-fragmented'
    | 'box-spill-or-neighbour-leak'
    | 'empty-or-degenerate-mask';

export type ReviewActionKey =
    | 'ai-select.review.action.inspect-mask'
    | 'ai-select.review.action.add-view'
    | 'ai-select.review.action.brush'
    | 'ai-select.review.action.inspect-view';

const actionKeysByReason: Readonly<
    Record<ReviewReason, readonly ReviewActionKey[]>
> = Object.freeze({
    'prompt-inconsistent': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]),
    'target-materially-clipped': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-view',
        'ai-select.review.action.add-view'
    ]),
    'severely-fragmented': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]),
    'box-spill-or-neighbour-leak': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.brush'
    ]),
    'empty-or-degenerate-mask': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-mask'
    ])
});

export const reviewReasonActionKeys = (
    reason: ReviewReason
): readonly ReviewActionKey[] => {
    return actionKeysByReason[reason];
};

export interface ViewAssessmentInputIdentity {
    readonly rgbDigest: string;
    readonly stableMaskDigest: string;
    readonly assessmentPolicyVersion: string;
}

/**
 * The frozen `local-view-assessment/v2` geometry thresholds, mirrored from
 * the Companion Mask Review policy so the trust boundary can reject an
 * artifact whose stated reasons are not backed by its own measured
 * diagnostics. They are version-owned: changing one requires a new policy
 * version on both sides.
 */
export const aiSelectMaskReviewThresholds = Object.freeze({
    minForegroundPixels: 4,
    fullFrameRatio: 0.98,
    clippedMinBoundaryPixels: 8,
    clippedMinBoundaryRatio: 0.2,
    fragmentMinDisconnectedPixels: 16,
    fragmentMinDisconnectedRatio: 0.1,
    boxSpillMinPixels: 16,
    boxSpillMinRatio: 0.2
});

/**
 * The measured geometry backing each structured reason. Prompt/Box
 * diagnostics are null when that Prompt family does not exist; a missing
 * family never fabricates a reason.
 */
export interface ViewAssessmentDiagnostics {
    readonly framePixels: number;
    readonly foregroundPixels: number;
    readonly boundaryPixels: number;
    readonly boundaryContactRatio: number;
    readonly connectedComponents: number;
    readonly largestComponentRatio: number;
    readonly promptPointCount: number | null;
    readonly promptViolationCount: number | null;
    readonly boxSpillPixels: number | null;
    readonly boxSpillRatio: number | null;
}

export interface ViewAssessmentResult {
    readonly status: ViewAssessmentStatus;
    readonly primaryReason?: ReviewReason;
    readonly reasons: readonly ReviewReason[];
    readonly actionableReasons: readonly ReviewReason[];
    readonly policyVersion: typeof aiSelectViewAssessmentPolicyVersion;
    readonly inputIdentity: ViewAssessmentInputIdentity;
    /**
     * Retained only for trust-boundary verification and Advanced Diagnostics.
     * Ordinary UI maps structured reason codes to static localized actions.
     */
    readonly diagnostics?: ViewAssessmentDiagnostics;
}

/**
 * The source authority behind one Stable Mask. User Confirmed authority is
 * recorded by the Mask registry and cannot be silently revoked by a later
 * automatic review.
 */
export type MaskStableAuthority = 'automatic' | 'user-confirmed';

/**
 * Final Spec v1.3 §14.2 Participation defaults, centralized here and
 * independent from View role and source: automatic Good defaults Included;
 * automatic Review, Failed, or unavailable review defaults Excluded; User
 * Confirmed defaults Included unless the user explicitly excludes (an
 * explicit controller action, never a default flip).
 */
export const defaultViewParticipation = (input: {
    readonly reviewStatus: ViewAssessmentStatus | null;
    readonly authority: MaskStableAuthority;
}): AIViewParticipation => {
    if (input.authority === 'user-confirmed') {
        return 'included';
    }
    return input.reviewStatus === 'good' ? 'included' : 'excluded';
};

type UnknownRecord = Record<string, unknown>;

const reviewReasons = new Set<ReviewReason>([
    'prompt-inconsistent',
    'target-materially-clipped',
    'severely-fragmented',
    'box-spill-or-neighbour-leak',
    'empty-or-degenerate-mask'
]);

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return (
        typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    );
};

const isUnitInterval = (value: unknown): value is number => {
    return (
        typeof value === 'number' &&
        Number.isFinite(value) &&
        value >= 0 &&
        value <= 1
    );
};

const isNullableNonNegativeSafeInteger = (
    value: unknown
): value is number | null => {
    return value === null || isNonNegativeSafeInteger(value);
};

const isNullableUnitInterval = (value: unknown): value is number | null => {
    return value === null || isUnitInterval(value);
};

const isReviewReason = (value: unknown): value is ReviewReason => {
    return (
        typeof value === 'string' && reviewReasons.has(value as ReviewReason)
    );
};

const isReviewReasonArray = (
    value: unknown
): value is readonly ReviewReason[] => {
    return (
        Array.isArray(value) &&
        value.every(isReviewReason) &&
        new Set(value).size === value.length
    );
};

const isInputIdentity = (
    value: unknown
): value is ViewAssessmentInputIdentity => {
    return (
        isRecord(value) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.stableMaskDigest) &&
        value.assessmentPolicyVersion === aiSelectViewAssessmentPolicyVersion
    );
};

const isDiagnostics = (value: unknown): value is ViewAssessmentDiagnostics => {
    return (
        isRecord(value) &&
        isNonNegativeSafeInteger(value.framePixels) &&
        isNonNegativeSafeInteger(value.foregroundPixels) &&
        isNonNegativeSafeInteger(value.boundaryPixels) &&
        isUnitInterval(value.boundaryContactRatio) &&
        isNonNegativeSafeInteger(value.connectedComponents) &&
        isUnitInterval(value.largestComponentRatio) &&
        isNullableNonNegativeSafeInteger(value.promptPointCount) &&
        isNullableNonNegativeSafeInteger(value.promptViolationCount) &&
        isNullableNonNegativeSafeInteger(value.boxSpillPixels) &&
        isNullableUnitInterval(value.boxSpillRatio)
    );
};

/**
 * Reject a fabricated claim fail-closed: every structured reason must be
 * backed by the measured diagnostic that the version-owned thresholds could
 * produce it from.
 */
const reasonsAreEvidenceBacked = (
    reasons: readonly ReviewReason[],
    diagnostics: ViewAssessmentDiagnostics
): boolean => {
    const thresholds = aiSelectMaskReviewThresholds;
    return reasons.every((reason) => {
        switch (reason) {
            case 'prompt-inconsistent':
                return (
                    diagnostics.promptViolationCount !== null &&
                    diagnostics.promptViolationCount > 0
                );
            case 'target-materially-clipped':
                return (
                    diagnostics.boundaryPixels >=
                        thresholds.clippedMinBoundaryPixels &&
                    diagnostics.boundaryContactRatio >=
                        thresholds.clippedMinBoundaryRatio
                );
            case 'severely-fragmented': {
                // The stored ratio round-trips to the exact disconnected
                // pixel mass the Companion measured.
                const disconnected =
                    diagnostics.foregroundPixels -
                    Math.round(
                        diagnostics.largestComponentRatio *
                            diagnostics.foregroundPixels
                    );
                return (
                    diagnostics.connectedComponents > 1 &&
                    disconnected >= thresholds.fragmentMinDisconnectedPixels &&
                    disconnected >=
                        thresholds.fragmentMinDisconnectedRatio *
                            diagnostics.foregroundPixels
                );
            }
            case 'box-spill-or-neighbour-leak':
                return (
                    diagnostics.boxSpillPixels !== null &&
                    diagnostics.boxSpillPixels >=
                        thresholds.boxSpillMinPixels &&
                    diagnostics.boxSpillRatio !== null &&
                    diagnostics.boxSpillRatio >= thresholds.boxSpillMinRatio
                );
            case 'empty-or-degenerate-mask':
                return (
                    diagnostics.foregroundPixels <
                        thresholds.minForegroundPixels ||
                    diagnostics.foregroundPixels >=
                        thresholds.fullFrameRatio * diagnostics.framePixels
                );
            default:
                // Unreachable over the ReviewReason union; keeps the
                // callback total for the linter.
                return false;
        }
    });
};

/**
 * Structural parse of the optional diagnostics block: `undefined` when the
 * artifact carries none, `null` when it carries a malformed one.
 */
const parseAssessmentDiagnostics = (
    value: unknown
): ViewAssessmentDiagnostics | undefined | null => {
    if (value === undefined) {
        return undefined;
    }
    return isDiagnostics(value) ? value : null;
};

export const isViewAssessmentResult = (
    value: unknown
): value is ViewAssessmentResult => {
    if (!isRecord(value)) {
        return false;
    }
    const reasons = value.reasons;
    const actionableReasons = value.actionableReasons;
    if (
        (value.status !== 'good' &&
            value.status !== 'review' &&
            value.status !== 'failed') ||
        !isReviewReasonArray(reasons) ||
        !isReviewReasonArray(actionableReasons) ||
        actionableReasons.length > 2 ||
        value.policyVersion !== aiSelectViewAssessmentPolicyVersion ||
        !isInputIdentity(value.inputIdentity)
    ) {
        return false;
    }
    const diagnostics = parseAssessmentDiagnostics(value.diagnostics);
    if (diagnostics === null) {
        return false;
    }
    if (!actionableReasons.every((reason) => reasons.includes(reason))) {
        return false;
    }
    if (value.status === 'review') {
        // Review reasons are Mask-quality claims only; the failure reason
        // never appears outside a Failed assessment.
        return (
            reasons.length > 0 &&
            !reasons.includes('empty-or-degenerate-mask') &&
            isReviewReason(value.primaryReason) &&
            value.primaryReason === reasons[0] &&
            diagnostics !== undefined &&
            reasonsAreEvidenceBacked(reasons, diagnostics)
        );
    }
    if (value.status === 'failed') {
        if (diagnostics === undefined) {
            // Assessment-internal failure: no invented reason, no geometry.
            return (
                reasons.length === 0 &&
                actionableReasons.length === 0 &&
                value.primaryReason === undefined
            );
        }
        return (
            reasons.length === 1 &&
            reasons[0] === 'empty-or-degenerate-mask' &&
            actionableReasons.length === 0 &&
            value.primaryReason === 'empty-or-degenerate-mask' &&
            reasonsAreEvidenceBacked(reasons, diagnostics)
        );
    }
    return (
        reasons.length === 0 &&
        actionableReasons.length === 0 &&
        value.primaryReason === undefined &&
        diagnostics !== undefined
    );
};
