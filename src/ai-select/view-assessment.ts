export const aiSelectViewAssessmentPolicyVersion = 'local-view-assessment/v1';
export const aiSelectLocalViewSupportPolicyVersion =
    'local-view-support-probe/v1';

export type ViewAssessmentStatus = 'good' | 'review' | 'failed';

export type ReviewReason =
    | 'target-at-boundary'
    | 'fragmented-mask'
    | 'weak-gaussian-support'
    | 'propagation-uncertain';

export type ReviewActionKey =
    | 'ai-select.review.action.inspect-mask'
    | 'ai-select.review.action.add-view'
    | 'ai-select.review.action.brush'
    | 'ai-select.review.action.inspect-view';

const actionKeysByReason: Readonly<
    Record<ReviewReason, readonly ReviewActionKey[]>
> = Object.freeze({
    'target-at-boundary': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-mask',
        'ai-select.review.action.add-view'
    ]),
    'fragmented-mask': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.brush'
    ]),
    'weak-gaussian-support': Object.freeze<ReviewActionKey[]>([
        'ai-select.review.action.inspect-view',
        'ai-select.review.action.add-view'
    ]),
    'propagation-uncertain': Object.freeze<ReviewActionKey[]>([
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
    readonly supportPolicyVersion: string | null;
    readonly propagationPolicyVersion: string | null;
}

export interface ViewAssessmentDiagnostics {
    readonly foregroundPixels: number;
    readonly boundaryContactRatio: number;
    readonly connectedComponents: number;
    readonly largestComponentRatio: number;
    readonly observedGaussianCount: number | null;
    readonly projectedSupportCount: number | null;
    readonly promptCount: number | null;
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

type UnknownRecord = Record<string, unknown>;

const reviewReasons = new Set<ReviewReason>([
    'target-at-boundary',
    'fragmented-mask',
    'weak-gaussian-support',
    'propagation-uncertain'
]);

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isNullableNonEmptyString = (value: unknown): value is string | null => {
    return (
        value === null || (typeof value === 'string' && value.trim().length > 0)
    );
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
        value.assessmentPolicyVersion === aiSelectViewAssessmentPolicyVersion &&
        isNullableNonEmptyString(value.supportPolicyVersion) &&
        isNullableNonEmptyString(value.propagationPolicyVersion)
    );
};

const isDiagnostics = (value: unknown): value is ViewAssessmentDiagnostics => {
    return (
        isRecord(value) &&
        isNonNegativeSafeInteger(value.foregroundPixels) &&
        isUnitInterval(value.boundaryContactRatio) &&
        isNonNegativeSafeInteger(value.connectedComponents) &&
        isUnitInterval(value.largestComponentRatio) &&
        isNullableNonNegativeSafeInteger(value.observedGaussianCount) &&
        isNullableNonNegativeSafeInteger(value.projectedSupportCount) &&
        isNullableNonNegativeSafeInteger(value.promptCount)
    );
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
        !isInputIdentity(value.inputIdentity) ||
        (value.diagnostics !== undefined && !isDiagnostics(value.diagnostics))
    ) {
        return false;
    }
    if (!actionableReasons.every((reason) => reasons.includes(reason))) {
        return false;
    }
    if (value.status === 'review') {
        return (
            reasons.length > 0 &&
            isReviewReason(value.primaryReason) &&
            value.primaryReason === reasons[0] &&
            value.diagnostics !== undefined
        );
    }
    return (
        reasons.length === 0 &&
        actionableReasons.length === 0 &&
        value.primaryReason === undefined &&
        (value.status === 'failed' || value.diagnostics !== undefined)
    );
};
