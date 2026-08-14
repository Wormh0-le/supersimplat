import { sha256Digest } from '../scene-snapshot-binary';
import {
    copyDependencyToken,
    isAIRequestBinding,
    type AIRequestBinding
} from './current-target-context';
import { type AISelectDirtyStateTracker } from './dirty-state';

export const referenceCandidateSchemaVersion = 2;
export const referenceCandidatePublicationKind =
    'reference-pre-production' as const;

export type CandidateParticipation = 'included' | 'excluded';
export type ReferenceEvidenceBackendKind =
    'reference-contributor' | 'reference-autograd';

export interface CandidateStableInput {
    readonly viewId: string;
    readonly participation: CandidateParticipation;
    readonly stableMaskDigest: string | null;
    readonly evidenceArtifactDigest: string | null;
}

export interface ReferenceBackendIdentity {
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: ReferenceEvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
}

export interface CandidatePublicationBindingInput {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly stableInputs: readonly CandidateStableInput[];
    readonly aggregationPolicyDigest: string;
    readonly sourceEvidencePolicyDigest: string;
    readonly evidenceWorkingSetToken: string;
    readonly evidenceArtifactSetDigest: string;
    readonly referenceBackendIdentity: ReferenceBackendIdentity;
}

export interface CandidatePublicationBinding {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly stableInputSetDigest: string;
    readonly aggregationPolicyDigest: string;
    readonly sourceEvidencePolicyDigest: string;
    readonly evidenceWorkingSetToken: string;
    readonly evidenceArtifactSetDigest: string;
    readonly referenceBackendIdentity: ReferenceBackendIdentity;
}

export interface CreateReferenceCandidateArtifactInput {
    readonly publicationBinding: CandidatePublicationBinding;
    readonly sourceAggregationResultDigest: string;
    readonly selectedStableGaussianIds: readonly number[];
    readonly uncertainStableGaussianIds: readonly number[];
}

export interface ReferenceCandidateArtifact {
    readonly schemaVersion: typeof referenceCandidateSchemaVersion;
    readonly publicationKind: typeof referenceCandidatePublicationKind;
    readonly productionReadiness: 'reference-only';
    readonly publicationBinding: CandidatePublicationBinding;
    readonly sourceAggregationResultDigest: string;
    readonly candidate: Readonly<{
        selectedStableGaussianIds: readonly number[];
    }>;
    readonly uncertain: Readonly<{
        stableGaussianIds: readonly number[];
    }>;
    readonly candidateDigest: string;
}

export type CandidateApplicationStatus =
    'unavailable' | 'blocked-stale' | 'blocked-reference-pre-production';

export type CandidatePublicationState =
    | Readonly<{
          status: 'empty';
          candidate: null;
          uncertain: null;
          overlay: null;
          applicationStatus: 'unavailable';
      }>
    | Readonly<{
          status: 'current' | 'stale';
          candidate: ReferenceCandidateArtifact['candidate'];
          uncertain: ReferenceCandidateArtifact['uncertain'];
          overlay: Readonly<{
              selectedStableGaussianIds: readonly number[];
              uncertainStableGaussianIds: readonly number[];
          }>;
          applicationStatus:
              'blocked-stale' | 'blocked-reference-pre-production';
      }>;

export type CandidatePublicationListener = (
    state: CandidatePublicationState
) => void;

type UnknownRecord = Record<string, unknown>;

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;
const maximumStableGaussianId = 0xffffffff;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const hasExactKeys = (
    value: UnknownRecord,
    required: readonly string[]
): boolean => {
    return (
        Object.keys(value).length === required.length &&
        required.every((key) => Object.hasOwn(value, key))
    );
};

const isNonEmptyString = (value: unknown): value is string => {
    if (typeof value !== 'string' || value.trim().length === 0) {
        return false;
    }
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

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && digestPattern.test(value);
};

const isStableGaussianId = (value: unknown): value is number => {
    return (
        Number.isSafeInteger(value) &&
        (value as number) >= 0 &&
        (value as number) <= maximumStableGaussianId
    );
};

const isSortedStableGaussianIds = (
    value: unknown
): value is readonly number[] => {
    return (
        Array.isArray(value) &&
        value.every(
            (stableId, index) =>
                isStableGaussianId(stableId) &&
                (index === 0 || stableId > value[index - 1])
        )
    );
};

const asciiJsonString = (value: string): string => {
    return JSON.stringify(value).replace(/[\u007f-\uffff]/g, (character) => {
        return `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`;
    });
};

/** Match Companion sorted, compact, ASCII JSON for this integer-only schema. */
const candidateCanonicalJson = (value: unknown): string => {
    if (value === null) {
        return 'null';
    }
    if (typeof value === 'boolean') {
        return value ? 'true' : 'false';
    }
    if (typeof value === 'number') {
        if (!Number.isSafeInteger(value)) {
            throw new Error(
                'AI Select Candidate identity numbers must be safe integers.'
            );
        }
        return String(value);
    }
    if (typeof value === 'string') {
        return asciiJsonString(value);
    }
    if (Array.isArray(value)) {
        return `[${value.map(candidateCanonicalJson).join(',')}]`;
    }
    if (isRecord(value)) {
        return `{${Object.keys(value)
            .sort()
            .map(
                (key) =>
                    `${asciiJsonString(key)}:${candidateCanonicalJson(value[key])}`
            )
            .join(',')}}`;
    }
    throw new Error('AI Select Candidate identity contains unsupported data.');
};

const candidateDigest = (value: unknown): string => {
    return sha256Digest(encoder.encode(candidateCanonicalJson(value)));
};

const copyRequestBinding = (value: AIRequestBinding): AIRequestBinding => {
    return Object.freeze({
        targetContextId: value.targetContextId,
        contextRevision: value.contextRevision,
        dependencyToken: copyDependencyToken(value.dependencyToken)
    });
};

const copyBackendIdentity = (
    value: ReferenceBackendIdentity
): ReferenceBackendIdentity => {
    return Object.freeze({ ...value });
};

const isBackendIdentity = (
    value: unknown
): value is ReferenceBackendIdentity => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId'
        ]) &&
        isNonEmptyString(value.rasterImplementationId) &&
        (value.evidenceBackendKind === 'reference-contributor' ||
            value.evidenceBackendKind === 'reference-autograd') &&
        isNonEmptyString(value.evidenceBackendId) &&
        isNonEmptyString(value.runtimeBuildId)
    );
};

const copyStableInputs = (
    value: readonly CandidateStableInput[]
): readonly CandidateStableInput[] => {
    const result = value
        .map((entry) => Object.freeze({ ...entry }))
        .sort((left, right) => {
            const leftBytes = encoder.encode(left.viewId);
            const rightBytes = encoder.encode(right.viewId);
            const length = Math.min(leftBytes.length, rightBytes.length);
            for (let index = 0; index < length; index += 1) {
                if (leftBytes[index] !== rightBytes[index]) {
                    return leftBytes[index] - rightBytes[index];
                }
            }
            return leftBytes.length - rightBytes.length;
        });
    if (
        result.length === 0 ||
        result.some(
            (entry, index) =>
                !isRecord(entry) ||
                !hasExactKeys(entry, [
                    'viewId',
                    'participation',
                    'stableMaskDigest',
                    'evidenceArtifactDigest'
                ]) ||
                !isNonEmptyString(entry.viewId) ||
                (entry.participation !== 'included' &&
                    entry.participation !== 'excluded') ||
                (entry.participation === 'included'
                    ? !isDigest(entry.stableMaskDigest) ||
                      !isDigest(entry.evidenceArtifactDigest)
                    : (entry.stableMaskDigest !== null &&
                          !isDigest(entry.stableMaskDigest)) ||
                      entry.evidenceArtifactDigest !== null) ||
                (index > 0 && result[index - 1].viewId === entry.viewId)
        )
    ) {
        throw new Error(
            'AI Select Candidate stable input set is incomplete or invalid.'
        );
    }
    return Object.freeze(result);
};

export const createCandidatePublicationBinding = (
    input: CandidatePublicationBindingInput
): CandidatePublicationBinding => {
    if (
        !isAIRequestBinding(input.requestBinding) ||
        !isNonEmptyString(input.targetSplatId) ||
        !isDigest(input.aggregationPolicyDigest) ||
        !isDigest(input.sourceEvidencePolicyDigest) ||
        !isDigest(input.evidenceWorkingSetToken) ||
        !isDigest(input.evidenceArtifactSetDigest) ||
        !isBackendIdentity(input.referenceBackendIdentity)
    ) {
        throw new Error('AI Select Candidate publication binding is invalid.');
    }
    const stableInputs = copyStableInputs(input.stableInputs);
    return Object.freeze({
        requestBinding: copyRequestBinding(input.requestBinding),
        targetSplatId: input.targetSplatId,
        stableInputSetDigest: candidateDigest({ stableInputs }),
        aggregationPolicyDigest: input.aggregationPolicyDigest,
        sourceEvidencePolicyDigest: input.sourceEvidencePolicyDigest,
        evidenceWorkingSetToken: input.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: input.evidenceArtifactSetDigest,
        referenceBackendIdentity: copyBackendIdentity(
            input.referenceBackendIdentity
        )
    });
};

const isCandidatePublicationBinding = (
    value: unknown
): value is CandidatePublicationBinding => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'stableInputSetDigest',
            'aggregationPolicyDigest',
            'sourceEvidencePolicyDigest',
            'evidenceWorkingSetToken',
            'evidenceArtifactSetDigest',
            'referenceBackendIdentity'
        ]) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isDigest(value.stableInputSetDigest) &&
        isDigest(value.aggregationPolicyDigest) &&
        isDigest(value.sourceEvidencePolicyDigest) &&
        isDigest(value.evidenceWorkingSetToken) &&
        isDigest(value.evidenceArtifactSetDigest) &&
        isBackendIdentity(value.referenceBackendIdentity)
    );
};

const copyPublicationBinding = (
    value: CandidatePublicationBinding
): CandidatePublicationBinding => {
    return Object.freeze({
        requestBinding: copyRequestBinding(value.requestBinding),
        targetSplatId: value.targetSplatId,
        stableInputSetDigest: value.stableInputSetDigest,
        aggregationPolicyDigest: value.aggregationPolicyDigest,
        sourceEvidencePolicyDigest: value.sourceEvidencePolicyDigest,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: value.evidenceArtifactSetDigest,
        referenceBackendIdentity: copyBackendIdentity(
            value.referenceBackendIdentity
        )
    });
};

const bindingsEqual = (
    left: CandidatePublicationBinding,
    right: CandidatePublicationBinding
): boolean => {
    return candidateCanonicalJson(left) === candidateCanonicalJson(right);
};

const copyStableIds = (value: readonly number[]): readonly number[] => {
    if (!isSortedStableGaussianIds(value)) {
        throw new Error(
            'AI Select Candidate requires sorted unique uint32 Stable Gaussian IDs.'
        );
    }
    return Object.freeze([...value]);
};

export const createReferenceCandidateArtifact = (
    input: CreateReferenceCandidateArtifactInput
): ReferenceCandidateArtifact => {
    if (
        !isCandidatePublicationBinding(input.publicationBinding) ||
        !isDigest(input.sourceAggregationResultDigest)
    ) {
        throw new Error('AI Select Candidate artifact input is invalid.');
    }
    const selectedStableGaussianIds = copyStableIds(
        input.selectedStableGaussianIds
    );
    const uncertainStableGaussianIds = copyStableIds(
        input.uncertainStableGaussianIds
    );
    if (
        selectedStableGaussianIds.some((stableId) =>
            uncertainStableGaussianIds.includes(stableId)
        )
    ) {
        throw new Error(
            'AI Select Candidate Selected and Uncertain IDs must be disjoint.'
        );
    }
    const payload = {
        schemaVersion: referenceCandidateSchemaVersion as 2,
        publicationKind: referenceCandidatePublicationKind,
        productionReadiness: 'reference-only' as const,
        publicationBinding: copyPublicationBinding(input.publicationBinding),
        sourceAggregationResultDigest: input.sourceAggregationResultDigest,
        candidate: Object.freeze({ selectedStableGaussianIds }),
        uncertain: Object.freeze({
            stableGaussianIds: uncertainStableGaussianIds
        })
    };
    return Object.freeze({
        ...payload,
        candidateDigest: candidateDigest(payload)
    });
};

export const isReferenceCandidateArtifact = (
    value: unknown
): value is ReferenceCandidateArtifact => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'schemaVersion',
            'publicationKind',
            'productionReadiness',
            'publicationBinding',
            'sourceAggregationResultDigest',
            'candidate',
            'uncertain',
            'candidateDigest'
        ]) ||
        value.schemaVersion !== referenceCandidateSchemaVersion ||
        value.publicationKind !== referenceCandidatePublicationKind ||
        value.productionReadiness !== 'reference-only' ||
        !isCandidatePublicationBinding(value.publicationBinding) ||
        !isDigest(value.sourceAggregationResultDigest) ||
        !isDigest(value.candidateDigest) ||
        !isRecord(value.candidate) ||
        !hasExactKeys(value.candidate, ['selectedStableGaussianIds']) ||
        !isSortedStableGaussianIds(value.candidate.selectedStableGaussianIds) ||
        !isRecord(value.uncertain) ||
        !hasExactKeys(value.uncertain, ['stableGaussianIds']) ||
        !isSortedStableGaussianIds(value.uncertain.stableGaussianIds)
    ) {
        return false;
    }
    const selectedStableGaussianIds = value.candidate
        .selectedStableGaussianIds as readonly number[];
    const uncertainStableGaussianIds = value.uncertain
        .stableGaussianIds as readonly number[];
    if (
        selectedStableGaussianIds.some((stableId) =>
            uncertainStableGaussianIds.includes(stableId)
        )
    ) {
        return false;
    }
    const payload = Object.fromEntries(
        Object.entries(value).filter(([key]) => key !== 'candidateDigest')
    );
    try {
        return value.candidateDigest === candidateDigest(payload);
    } catch {
        return false;
    }
};

const copyArtifact = (
    value: ReferenceCandidateArtifact
): ReferenceCandidateArtifact => {
    return createReferenceCandidateArtifact({
        publicationBinding: value.publicationBinding,
        sourceAggregationResultDigest: value.sourceAggregationResultDigest,
        selectedStableGaussianIds: value.candidate.selectedStableGaussianIds,
        uncertainStableGaussianIds: value.uncertain.stableGaussianIds
    });
};

/** Browser-owned atomic Candidate/Uncertain publication and overlay state. */
export class CandidatePublicationStore {
    private published: ReferenceCandidateArtifact | null = null;
    private currentBinding: CandidatePublicationBinding | null = null;
    private readonly listeners = new Set<CandidatePublicationListener>();

    constructor(private readonly dirtyState: AISelectDirtyStateTracker) {
        this.dirtyState.subscribe(() => this.notify());
    }

    get inspectableCandidate(): ReferenceCandidateArtifact | null {
        return this.published === null ? null : copyArtifact(this.published);
    }

    get presentationState(): CandidatePublicationState {
        return this.currentBinding === null
            ? this.emptyState()
            : this.state(this.currentBinding);
    }

    subscribe(listener: CandidatePublicationListener): () => void {
        listener(this.presentationState);
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    synchronizeCurrentBinding(value: CandidatePublicationBinding): void {
        if (!isCandidatePublicationBinding(value)) {
            throw new Error(
                'AI Select Candidate publication binding is invalid.'
            );
        }
        const replacement = copyPublicationBinding(value);
        const previous = this.currentBinding;
        this.currentBinding = replacement;
        try {
            this.notify();
        } catch (error) {
            this.currentBinding = previous;
            throw error;
        }
    }

    publish(value: unknown, currentBinding: CandidatePublicationBinding): void {
        if (!isReferenceCandidateArtifact(value)) {
            throw new Error('AI Select Candidate artifact is invalid.');
        }
        if (
            !isCandidatePublicationBinding(currentBinding) ||
            !bindingsEqual(value.publicationBinding, currentBinding)
        ) {
            throw new Error(
                'AI Select Candidate does not match current inputs.'
            );
        }

        // Complete validation and copying happen before the transaction. The
        // dirty-state notification is part of the same rollback boundary so
        // a failing observer cannot leave a half-published replacement.
        const replacement = copyArtifact(value);
        this.dirtyState.markCandidatePublished(() => {
            this.published = replacement;
            this.currentBinding = copyPublicationBinding(currentBinding);
        });
    }

    state(
        currentBinding: CandidatePublicationBinding
    ): CandidatePublicationState {
        if (this.published === null) {
            return Object.freeze({
                status: 'empty',
                candidate: null,
                uncertain: null,
                overlay: null,
                applicationStatus: 'unavailable'
            });
        }
        const isCurrent =
            isCandidatePublicationBinding(currentBinding) &&
            bindingsEqual(this.published.publicationBinding, currentBinding) &&
            !this.dirtyState.state.candidateStale;
        const selectedStableGaussianIds = Object.freeze([
            ...this.published.candidate.selectedStableGaussianIds
        ]);
        const uncertainStableGaussianIds = Object.freeze([
            ...this.published.uncertain.stableGaussianIds
        ]);
        return Object.freeze({
            status: isCurrent ? 'current' : 'stale',
            candidate: Object.freeze({ selectedStableGaussianIds }),
            uncertain: Object.freeze({
                stableGaussianIds: uncertainStableGaussianIds
            }),
            overlay: Object.freeze({
                selectedStableGaussianIds,
                uncertainStableGaussianIds
            }),
            applicationStatus: isCurrent
                ? 'blocked-reference-pre-production'
                : 'blocked-stale'
        });
    }

    reset(): void {
        const previous = this.published;
        const previousBinding = this.currentBinding;
        this.published = null;
        this.currentBinding = null;
        try {
            this.notify();
        } catch (error) {
            this.published = previous;
            this.currentBinding = previousBinding;
            throw error;
        }
    }

    private emptyState(): CandidatePublicationState {
        return Object.freeze({
            status: 'empty',
            candidate: null,
            uncertain: null,
            overlay: null,
            applicationStatus: 'unavailable'
        });
    }

    private notify(): void {
        const state = this.presentationState;
        this.listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                console.error(error);
            }
        });
    }
}
