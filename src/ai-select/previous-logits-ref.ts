import { sha256Digest } from '../scene-snapshot-binary';
import { promptCanonicalJson } from './prompt-state';

/**
 * The opaque reference to Companion-local previous-prediction logits (04C
 * contract §7). Raw logits bytes/tensors never cross the protocol boundary;
 * the editor validates structure and recomputes `refDigest`, and treats every
 * other field as opaque identity data.
 */
export interface PreviousPredictionLogitsRef {
    readonly schemaVersion: 1;
    readonly companionInstanceId: string;
    readonly stateId: string;
    readonly targetContextId: string;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly sourceInferenceAttemptId: string;
    readonly sourceCandidateId: string;
    readonly adapterRuntimeDigest: string;
    readonly shape: readonly number[];
    readonly dtype: string;
    readonly dataDigest: string;
    readonly refDigest: string;
}

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const previousPredictionLogitsRefKeys = [
    'schemaVersion',
    'companionInstanceId',
    'stateId',
    'targetContextId',
    'viewId',
    'rgbDigest',
    'sourceInferenceAttemptId',
    'sourceCandidateId',
    'adapterRuntimeDigest',
    'shape',
    'dtype',
    'dataDigest',
    'refDigest'
] as const;

export const previousPredictionLogitsRefDigest = (
    payload: Omit<PreviousPredictionLogitsRef, 'refDigest'>
): string => {
    return sha256Digest(encoder.encode(promptCanonicalJson(payload)));
};

export const isPreviousPredictionLogitsRef = (
    value: unknown
): value is PreviousPredictionLogitsRef => {
    if (
        !isRecord(value) ||
        Object.keys(value).length !== previousPredictionLogitsRefKeys.length ||
        !previousPredictionLogitsRefKeys.every((key) =>
            Object.hasOwn(value, key)
        ) ||
        value.schemaVersion !== 1 ||
        !isNonEmptyString(value.companionInstanceId) ||
        !isNonEmptyString(value.stateId) ||
        !isNonEmptyString(value.targetContextId) ||
        !isNonEmptyString(value.viewId) ||
        typeof value.rgbDigest !== 'string' ||
        !digestPattern.test(value.rgbDigest) ||
        !isNonEmptyString(value.sourceInferenceAttemptId) ||
        !isNonEmptyString(value.sourceCandidateId) ||
        !isNonEmptyString(value.adapterRuntimeDigest) ||
        !Array.isArray(value.shape) ||
        value.shape.length === 0 ||
        !value.shape.every(
            (dimension) =>
                Number.isSafeInteger(dimension) && (dimension as number) > 0
        ) ||
        !isNonEmptyString(value.dtype) ||
        typeof value.dataDigest !== 'string' ||
        !digestPattern.test(value.dataDigest) ||
        typeof value.refDigest !== 'string' ||
        !digestPattern.test(value.refDigest)
    ) {
        return false;
    }
    const { refDigest, ...payload } = value;
    return (
        previousPredictionLogitsRefDigest(
            payload as Omit<PreviousPredictionLogitsRef, 'refDigest'>
        ) === refDigest
    );
};
