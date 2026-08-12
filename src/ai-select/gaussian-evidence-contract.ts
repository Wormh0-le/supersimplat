import { sha256Digest } from '../scene-snapshot-binary';
import {
    areTargetDependencyTokensEqual,
    copyDependencyToken,
    isAIRequestBinding,
    isTargetDependencyToken,
    type AIRequestBinding,
    type TargetDependencyToken
} from './current-target-context';

/**
 * Ticket 14A's reference-only per-view P/N/V artifact schema. Ticket 20
 * deliberately receives a distinct production Direct Evidence contract: a
 * reference artifact must never be mistaken for same-decision Evidence.
 */
export const gaussianEvidenceArtifactSchemaVersion = 1;
export const evidenceWorkingSetSchemaVersion = 1;

export type EvidenceBackendKind =
    'reference-contributor' | 'reference-autograd';

type KnownEvidenceBackendKind = EvidenceBackendKind | 'production-direct';
type UnknownRecord = Record<string, unknown>;

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;
const maximumStableGaussianId = 0xffffffff;

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

const isStableGaussianId = (value: unknown): value is number => {
    return (
        Number.isSafeInteger(value) &&
        (value as number) >= 0 &&
        (value as number) <= maximumStableGaussianId
    );
};

const isStrictlyAscendingStableGaussianIds = (
    value: unknown,
    allowEmpty = false
): value is readonly number[] => {
    if (!Array.isArray(value) || (!allowEmpty && value.length === 0)) {
        return false;
    }
    return value.every(
        (stableId, index) =>
            isStableGaussianId(stableId) &&
            (index === 0 || stableId > value[index - 1])
    );
};

const copyStableGaussianIds = (
    value: readonly number[],
    allowEmpty = false
): readonly number[] => {
    if (!isStrictlyAscendingStableGaussianIds(value, allowEmpty)) {
        throw new Error(
            'AI Select Evidence requires sorted unique uint32 Stable Gaussian IDs.'
        );
    }
    return Object.freeze([...value]);
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

/**
 * Use IEEE-754 binary64 spelling for every numeric value. It makes artifact
 * digests stable across the browser and Companion even where JSON would spell
 * the same Number as `1`, `1.0`, or an exponent differently.
 */
const evidenceCanonicalJson = (value: unknown): string => {
    if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
            throw new Error(
                'AI Select Evidence artifact numbers must be finite.'
            );
        }
        const bytes = new Uint8Array(8);
        new DataView(bytes.buffer).setFloat64(0, value, false);
        return `n${[...bytes]
            .map((byte) => byte.toString(16).padStart(2, '0'))
            .join('')}`;
    }
    if (Array.isArray(value)) {
        return `[${value.map(evidenceCanonicalJson).join(',')}]`;
    }
    if (value !== null && typeof value === 'object') {
        const record = value as UnknownRecord;
        return `{${Object.keys(record)
            .sort()
            .map(
                (key) =>
                    `${JSON.stringify(key)}:${evidenceCanonicalJson(record[key])}`
            )
            .join(',')}}`;
    }
    const primitive = JSON.stringify(value);
    if (typeof primitive !== 'string') {
        throw new Error(
            'AI Select Evidence artifact contains invalid JSON data.'
        );
    }
    return primitive;
};

const canonicalDigest = (value: unknown): string => {
    return sha256Digest(encoder.encode(evidenceCanonicalJson(value)));
};

const unionStableGaussianIds = (
    left: readonly number[],
    right: readonly number[]
): readonly number[] => {
    const result: number[] = [];
    let leftIndex = 0;
    let rightIndex = 0;
    while (leftIndex < left.length || rightIndex < right.length) {
        const leftValue = left[leftIndex];
        const rightValue = right[rightIndex];
        if (rightIndex >= right.length || leftValue < rightValue) {
            result.push(leftValue);
            leftIndex += 1;
        } else if (leftIndex >= left.length || rightValue < leftValue) {
            result.push(rightValue);
            rightIndex += 1;
        } else {
            result.push(leftValue);
            leftIndex += 1;
            rightIndex += 1;
        }
    }
    return Object.freeze(result);
};

const stableGaussianIdsIntersect = (
    left: readonly number[],
    right: readonly number[]
): boolean => {
    let leftIndex = 0;
    let rightIndex = 0;
    while (leftIndex < left.length && rightIndex < right.length) {
        if (left[leftIndex] === right[rightIndex]) {
            return true;
        }
        if (left[leftIndex] < right[rightIndex]) {
            leftIndex += 1;
        } else {
            rightIndex += 1;
        }
    }
    return false;
};

const stableGaussianIdsAreSubsetOf = (
    subset: readonly number[],
    superset: readonly number[]
): boolean => {
    let subsetIndex = 0;
    let supersetIndex = 0;
    while (subsetIndex < subset.length && supersetIndex < superset.length) {
        if (subset[subsetIndex] === superset[supersetIndex]) {
            subsetIndex += 1;
            supersetIndex += 1;
        } else if (subset[subsetIndex] > superset[supersetIndex]) {
            supersetIndex += 1;
        } else {
            return false;
        }
    }
    return subsetIndex === subset.length;
};

const areStableGaussianIdArraysEqual = (
    left: readonly number[],
    right: readonly number[]
): boolean => {
    return (
        left.length === right.length &&
        left.every((stableId, index) => stableId === right[index])
    );
};

export interface EvidenceWorkingSetInput {
    readonly targetSplatId: string;
    /** Conservative target-local evidence capture set; never ownership. */
    readonly coreTargetStableIds: readonly number[];
    /** Local neighboring/occluding evidence capture set; never ownership. */
    readonly contextStableGaussianIds: readonly number[];
    /** Optional provenance only; it is deliberately not part of the token. */
    readonly targetGeometryHintSeedDigest?: string;
}

/**
 * The local set allowed to receive P/N/V writes. It is explicitly distinct
 * from the complete Render Working Set and its membership is not a Candidate
 * or ownership classification.
 */
export interface EvidenceWorkingSet {
    readonly schemaVersion: typeof evidenceWorkingSetSchemaVersion;
    readonly targetSplatId: string;
    readonly coreTargetStableIds: readonly number[];
    readonly contextStableGaussianIds: readonly number[];
    readonly stableGaussianIds: readonly number[];
    readonly targetGeometryHintSeedDigest?: string;
    readonly evidenceWorkingSetToken: string;
}

const evidenceWorkingSetPayload = (
    input: Pick<
        EvidenceWorkingSet,
        'targetSplatId' | 'coreTargetStableIds' | 'contextStableGaussianIds'
    >
): UnknownRecord => {
    return {
        schemaVersion: evidenceWorkingSetSchemaVersion,
        targetSplatId: input.targetSplatId,
        coreTargetStableIds: [...input.coreTargetStableIds],
        contextStableGaussianIds: [...input.contextStableGaussianIds]
    };
};

const evidenceWorkingSetToken = (
    input: Pick<
        EvidenceWorkingSet,
        'targetSplatId' | 'coreTargetStableIds' | 'contextStableGaussianIds'
    >
): string => canonicalDigest(evidenceWorkingSetPayload(input));

const isEvidenceWorkingSetInput = (
    value: unknown
): value is EvidenceWorkingSetInput => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'targetSplatId',
                'coreTargetStableIds',
                'contextStableGaussianIds'
            ],
            ['targetGeometryHintSeedDigest']
        ) ||
        !isNonEmptyString(value.targetSplatId) ||
        !isStrictlyAscendingStableGaussianIds(
            value.coreTargetStableIds,
            true
        ) ||
        !isStrictlyAscendingStableGaussianIds(
            value.contextStableGaussianIds,
            true
        ) ||
        stableGaussianIdsIntersect(
            value.coreTargetStableIds,
            value.contextStableGaussianIds
        )
    ) {
        return false;
    }
    const stableIds = unionStableGaussianIds(
        value.coreTargetStableIds,
        value.contextStableGaussianIds
    );
    return (
        stableIds.length > 0 &&
        (value.targetGeometryHintSeedDigest === undefined ||
            isDigest(value.targetGeometryHintSeedDigest))
    );
};

export const createEvidenceWorkingSet = (
    input: EvidenceWorkingSetInput
): EvidenceWorkingSet => {
    if (!isEvidenceWorkingSetInput(input)) {
        throw new Error(
            'AI Select Evidence Working Set requires disjoint sorted Core Target and Context Stable Gaussian IDs.'
        );
    }
    const coreTargetStableIds = copyStableGaussianIds(
        input.coreTargetStableIds,
        true
    );
    const contextStableGaussianIds = copyStableGaussianIds(
        input.contextStableGaussianIds,
        true
    );
    const stableGaussianIds = unionStableGaussianIds(
        coreTargetStableIds,
        contextStableGaussianIds
    );
    const payload = {
        targetSplatId: input.targetSplatId,
        coreTargetStableIds,
        contextStableGaussianIds
    };
    return Object.freeze({
        schemaVersion: evidenceWorkingSetSchemaVersion,
        targetSplatId: input.targetSplatId,
        coreTargetStableIds,
        contextStableGaussianIds,
        stableGaussianIds,
        ...(input.targetGeometryHintSeedDigest === undefined
            ? {}
            : {
                  targetGeometryHintSeedDigest:
                      input.targetGeometryHintSeedDigest
              }),
        evidenceWorkingSetToken: evidenceWorkingSetToken(payload)
    });
};

export const isEvidenceWorkingSet = (
    value: unknown
): value is EvidenceWorkingSet => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'targetSplatId',
                'coreTargetStableIds',
                'contextStableGaussianIds',
                'stableGaussianIds',
                'evidenceWorkingSetToken'
            ],
            ['targetGeometryHintSeedDigest']
        ) ||
        value.schemaVersion !== evidenceWorkingSetSchemaVersion ||
        !isDigest(value.evidenceWorkingSetToken) ||
        !isEvidenceWorkingSetInput({
            targetSplatId: value.targetSplatId,
            coreTargetStableIds: value.coreTargetStableIds,
            contextStableGaussianIds: value.contextStableGaussianIds,
            ...(value.targetGeometryHintSeedDigest === undefined
                ? {}
                : {
                      targetGeometryHintSeedDigest:
                          value.targetGeometryHintSeedDigest
                  })
        })
    ) {
        return false;
    }
    const candidate = value as unknown as EvidenceWorkingSet;
    const expectedStableGaussianIds = unionStableGaussianIds(
        candidate.coreTargetStableIds,
        candidate.contextStableGaussianIds
    );
    return (
        areStableGaussianIdArraysEqual(
            candidate.stableGaussianIds,
            expectedStableGaussianIds
        ) &&
        candidate.evidenceWorkingSetToken ===
            evidenceWorkingSetToken({
                targetSplatId: candidate.targetSplatId,
                coreTargetStableIds: candidate.coreTargetStableIds,
                contextStableGaussianIds: candidate.contextStableGaussianIds
            })
    );
};

const copyEvidenceWorkingSet = (
    value: EvidenceWorkingSet
): EvidenceWorkingSet => {
    if (!isEvidenceWorkingSet(value)) {
        throw new Error('AI Select Evidence Working Set is invalid.');
    }
    return Object.freeze({
        schemaVersion: value.schemaVersion,
        targetSplatId: value.targetSplatId,
        coreTargetStableIds: copyStableGaussianIds(
            value.coreTargetStableIds,
            true
        ),
        contextStableGaussianIds: copyStableGaussianIds(
            value.contextStableGaussianIds,
            true
        ),
        stableGaussianIds: copyStableGaussianIds(value.stableGaussianIds),
        ...(value.targetGeometryHintSeedDigest === undefined
            ? {}
            : {
                  targetGeometryHintSeedDigest:
                      value.targetGeometryHintSeedDigest
              }),
        evidenceWorkingSetToken: value.evidenceWorkingSetToken
    });
};

export interface EvidenceWorkingSetExpansionSource {
    readonly viewId: string;
    readonly renderStatus: 'pending' | 'rendering' | 'ready' | 'failed';
    readonly participation: 'included' | 'excluded';
    readonly stableMaskDigest?: string;
}

export interface EvidenceWorkingSetExpansion {
    readonly sourceView: EvidenceWorkingSetExpansionSource;
    readonly coreTargetStableIds: readonly number[];
    readonly contextStableGaussianIds: readonly number[];
}

const isEvidenceWorkingSetExpansion = (
    value: unknown
): value is EvidenceWorkingSetExpansion => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'sourceView',
            'coreTargetStableIds',
            'contextStableGaussianIds'
        ]) ||
        !isRecord(value.sourceView) ||
        !hasExactKeys(value.sourceView, [
            'viewId',
            'renderStatus',
            'participation',
            'stableMaskDigest'
        ]) ||
        !isNonEmptyString(value.sourceView.viewId) ||
        value.sourceView.renderStatus !== 'ready' ||
        value.sourceView.participation !== 'included' ||
        !isDigest(value.sourceView.stableMaskDigest) ||
        !isStrictlyAscendingStableGaussianIds(
            value.coreTargetStableIds,
            true
        ) ||
        !isStrictlyAscendingStableGaussianIds(
            value.contextStableGaussianIds,
            true
        ) ||
        stableGaussianIdsIntersect(
            value.coreTargetStableIds,
            value.contextStableGaussianIds
        )
    ) {
        return false;
    }
    return (
        value.coreTargetStableIds.length +
            value.contextStableGaussianIds.length >
        0
    );
};

/**
 * Scope growth is permitted only from a later Included Stable View. This
 * expands observation/write scope; it does not classify any Gaussian as
 * target-owned.
 */
export const expandEvidenceWorkingSet = (
    current: EvidenceWorkingSet,
    expansion: EvidenceWorkingSetExpansion
): EvidenceWorkingSet => {
    if (!isEvidenceWorkingSet(current)) {
        throw new Error('AI Select Evidence Working Set is invalid.');
    }
    if (!isEvidenceWorkingSetExpansion(expansion)) {
        throw new Error(
            'AI Select Evidence Working Set expansion requires an Included Stable View and valid Stable Gaussian IDs.'
        );
    }
    const coreTargetStableIds = unionStableGaussianIds(
        current.coreTargetStableIds,
        expansion.coreTargetStableIds
    );
    const contextStableGaussianIds = unionStableGaussianIds(
        current.contextStableGaussianIds,
        expansion.contextStableGaussianIds
    );
    if (
        stableGaussianIdsIntersect(
            coreTargetStableIds,
            contextStableGaussianIds
        )
    ) {
        throw new Error(
            'AI Select Evidence Working Set expansion cannot silently move a Stable Gaussian ID between Core Target and Context.'
        );
    }
    return createEvidenceWorkingSet({
        targetSplatId: current.targetSplatId,
        coreTargetStableIds,
        contextStableGaussianIds,
        ...(current.targetGeometryHintSeedDigest === undefined
            ? {}
            : {
                  targetGeometryHintSeedDigest:
                      current.targetGeometryHintSeedDigest
              })
    });
};

/**
 * A complete CameraBinding-specific Render Working Set. It carries all
 * potentially compositing Stable IDs, including IDs that must remain
 * occluders but never receive P/N/V writes.
 */
export interface RenderWorkingSetBinding {
    readonly targetSplatId: string;
    readonly dependencyToken: TargetDependencyToken;
    readonly cameraBindingDigest: string;
    readonly renderWorkingSetToken: string;
    readonly stableGaussianIds: readonly number[];
    readonly completeness: 'complete' | 'partial';
}

const isRenderWorkingSetBinding = (
    value: unknown
): value is RenderWorkingSetBinding => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'targetSplatId',
            'dependencyToken',
            'cameraBindingDigest',
            'renderWorkingSetToken',
            'stableGaussianIds',
            'completeness'
        ]) &&
        isNonEmptyString(value.targetSplatId) &&
        isTargetDependencyToken(value.dependencyToken) &&
        isDigest(value.cameraBindingDigest) &&
        isDigest(value.renderWorkingSetToken) &&
        isStrictlyAscendingStableGaussianIds(value.stableGaussianIds) &&
        (value.completeness === 'complete' || value.completeness === 'partial')
    );
};

/** The minimal current View surface allowed to enter formal Evidence. */
export interface EvidenceAdmissionView {
    readonly viewId: string;
    readonly renderStatus: 'pending' | 'rendering' | 'ready' | 'failed';
    readonly participation: 'included' | 'excluded';
    readonly cameraBindingDigest: string;
    readonly rgbDigest?: string;
    readonly stableMaskDigest?: string;
}

const isEvidenceAdmissionView = (
    value: unknown
): value is EvidenceAdmissionView => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            ['viewId', 'renderStatus', 'participation', 'cameraBindingDigest'],
            ['rgbDigest', 'stableMaskDigest']
        ) ||
        !isNonEmptyString(value.viewId) ||
        !isDigest(value.cameraBindingDigest) ||
        !['pending', 'rendering', 'ready', 'failed'].includes(
            value.renderStatus as string
        ) ||
        !['included', 'excluded'].includes(value.participation as string)
    ) {
        return false;
    }
    return (
        (value.rgbDigest === undefined || isDigest(value.rgbDigest)) &&
        (value.stableMaskDigest === undefined ||
            isDigest(value.stableMaskDigest))
    );
};

export interface GaussianEvidenceAdmissionInput {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly view: EvidenceAdmissionView;
    readonly evidencePolicyDigest: string;
    readonly renderWorkingSet: RenderWorkingSetBinding;
    readonly evidenceWorkingSet: EvidenceWorkingSet;
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: KnownEvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
}

const isKnownEvidenceBackendKind = (
    value: unknown
): value is KnownEvidenceBackendKind => {
    return (
        value === 'reference-contributor' ||
        value === 'reference-autograd' ||
        value === 'production-direct'
    );
};

export const isGaussianEvidenceAdmissionInput = (
    value: unknown
): value is GaussianEvidenceAdmissionInput => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'view',
            'evidencePolicyDigest',
            'renderWorkingSet',
            'evidenceWorkingSet',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId'
        ]) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        value.requestBinding.dependencyToken.splatId === value.targetSplatId &&
        isEvidenceAdmissionView(value.view) &&
        isDigest(value.evidencePolicyDigest) &&
        isRenderWorkingSetBinding(value.renderWorkingSet) &&
        isEvidenceWorkingSet(value.evidenceWorkingSet) &&
        isNonEmptyString(value.rasterImplementationId) &&
        isKnownEvidenceBackendKind(value.evidenceBackendKind) &&
        isNonEmptyString(value.evidenceBackendId) &&
        isNonEmptyString(value.runtimeBuildId)
    );
};

export type GaussianEvidenceAdmissionRejectionReason =
    | 'invalid-input'
    | 'render-not-ready'
    | 'view-excluded'
    | 'rgb-unavailable'
    | 'stable-mask-unavailable'
    | 'render-working-set-incomplete'
    | 'render-working-set-mismatch'
    | 'evidence-working-set-mismatch'
    | 'stable-id-mapping-invalid'
    | 'unsupported-evidence-backend';

/** The complete, computation-ready Ticket 14A handoff for Ticket 14B. */
export interface AdmittedGaussianEvidenceInput {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly viewId: string;
    readonly cameraBindingDigest: string;
    readonly rgbDigest: string;
    readonly stableMaskDigest: string;
    readonly evidencePolicyDigest: string;
    readonly renderWorkingSetToken: string;
    readonly evidenceWorkingSetToken: string;
    readonly stableGaussianIds: readonly number[];
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: EvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
}

export type GaussianEvidenceAdmission =
    | {
          readonly status: 'admitted';
          readonly admission: AdmittedGaussianEvidenceInput;
      }
    | {
          readonly status: 'rejected';
          readonly reason: GaussianEvidenceAdmissionRejectionReason;
      };

const rejectedAdmission = (
    reason: GaussianEvidenceAdmissionRejectionReason
): GaussianEvidenceAdmission => Object.freeze({ status: 'rejected', reason });

const copyAdmittedGaussianEvidenceInput = (
    value: AdmittedGaussianEvidenceInput
): AdmittedGaussianEvidenceInput => {
    return Object.freeze({
        requestBinding: Object.freeze({
            targetContextId: value.requestBinding.targetContextId,
            contextRevision: value.requestBinding.contextRevision,
            dependencyToken: copyDependencyToken(
                value.requestBinding.dependencyToken
            )
        }),
        targetSplatId: value.targetSplatId,
        viewId: value.viewId,
        cameraBindingDigest: value.cameraBindingDigest,
        rgbDigest: value.rgbDigest,
        stableMaskDigest: value.stableMaskDigest,
        evidencePolicyDigest: value.evidencePolicyDigest,
        renderWorkingSetToken: value.renderWorkingSetToken,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        stableGaussianIds: copyStableGaussianIds(value.stableGaussianIds),
        rasterImplementationId: value.rasterImplementationId,
        evidenceBackendKind: value.evidenceBackendKind,
        evidenceBackendId: value.evidenceBackendId,
        runtimeBuildId: value.runtimeBuildId
    });
};

const isAdmittedGaussianEvidenceInput = (
    value: unknown
): value is AdmittedGaussianEvidenceInput => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'viewId',
            'cameraBindingDigest',
            'rgbDigest',
            'stableMaskDigest',
            'evidencePolicyDigest',
            'renderWorkingSetToken',
            'evidenceWorkingSetToken',
            'stableGaussianIds',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId'
        ]) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        value.requestBinding.dependencyToken.splatId === value.targetSplatId &&
        isNonEmptyString(value.viewId) &&
        isDigest(value.cameraBindingDigest) &&
        isDigest(value.rgbDigest) &&
        isDigest(value.stableMaskDigest) &&
        isDigest(value.evidencePolicyDigest) &&
        isDigest(value.renderWorkingSetToken) &&
        isDigest(value.evidenceWorkingSetToken) &&
        isStrictlyAscendingStableGaussianIds(value.stableGaussianIds) &&
        isNonEmptyString(value.rasterImplementationId) &&
        (value.evidenceBackendKind === 'reference-contributor' ||
            value.evidenceBackendKind === 'reference-autograd') &&
        isNonEmptyString(value.evidenceBackendId) &&
        isNonEmptyString(value.runtimeBuildId)
    );
};

/**
 * Fail-closed admission. Its input intentionally contains no View source,
 * Prompt, geometry, SAM score, logits ref, or Mask Review metadata; those can
 * remain provenance elsewhere but cannot enter Gaussian ownership Evidence.
 */
export const admitGaussianEvidence = (
    input: unknown
): GaussianEvidenceAdmission => {
    if (!isGaussianEvidenceAdmissionInput(input)) {
        return rejectedAdmission('invalid-input');
    }
    if (input.view.renderStatus !== 'ready') {
        return rejectedAdmission('render-not-ready');
    }
    if (input.view.participation !== 'included') {
        return rejectedAdmission('view-excluded');
    }
    if (input.view.rgbDigest === undefined) {
        return rejectedAdmission('rgb-unavailable');
    }
    if (input.view.stableMaskDigest === undefined) {
        return rejectedAdmission('stable-mask-unavailable');
    }
    if (input.renderWorkingSet.completeness !== 'complete') {
        return rejectedAdmission('render-working-set-incomplete');
    }
    if (
        input.renderWorkingSet.targetSplatId !== input.targetSplatId ||
        !areTargetDependencyTokensEqual(
            input.renderWorkingSet.dependencyToken,
            input.requestBinding.dependencyToken
        ) ||
        input.renderWorkingSet.cameraBindingDigest !==
            input.view.cameraBindingDigest
    ) {
        return rejectedAdmission('render-working-set-mismatch');
    }
    if (input.evidenceWorkingSet.targetSplatId !== input.targetSplatId) {
        return rejectedAdmission('evidence-working-set-mismatch');
    }
    if (
        !stableGaussianIdsAreSubsetOf(
            input.evidenceWorkingSet.stableGaussianIds,
            input.renderWorkingSet.stableGaussianIds
        )
    ) {
        return rejectedAdmission('stable-id-mapping-invalid');
    }
    if (
        input.evidenceBackendKind !== 'reference-contributor' &&
        input.evidenceBackendKind !== 'reference-autograd'
    ) {
        return rejectedAdmission('unsupported-evidence-backend');
    }
    return Object.freeze({
        status: 'admitted',
        admission: copyAdmittedGaussianEvidenceInput({
            requestBinding: input.requestBinding,
            targetSplatId: input.targetSplatId,
            viewId: input.view.viewId,
            cameraBindingDigest: input.view.cameraBindingDigest,
            rgbDigest: input.view.rgbDigest,
            stableMaskDigest: input.view.stableMaskDigest,
            evidencePolicyDigest: input.evidencePolicyDigest,
            renderWorkingSetToken: input.renderWorkingSet.renderWorkingSetToken,
            evidenceWorkingSetToken:
                input.evidenceWorkingSet.evidenceWorkingSetToken,
            stableGaussianIds: input.evidenceWorkingSet.stableGaussianIds,
            rasterImplementationId: input.rasterImplementationId,
            evidenceBackendKind: input.evidenceBackendKind,
            evidenceBackendId: input.evidenceBackendId,
            runtimeBuildId: input.runtimeBuildId
        })
    });
};

export interface GaussianEvidenceMasses {
    readonly positiveMass: readonly number[];
    readonly negativeMass: readonly number[];
    readonly visibleMass: readonly number[];
    readonly boundaryMass?: readonly number[];
}

const isNonNegativeFiniteMassArray = (
    value: unknown,
    expectedLength: number
): value is readonly number[] => {
    return (
        Array.isArray(value) &&
        value.length === expectedLength &&
        value.every(
            (mass) =>
                typeof mass === 'number' && Number.isFinite(mass) && mass >= 0
        )
    );
};

const isGaussianEvidenceMasses = (
    value: unknown,
    expectedLength: number
): value is GaussianEvidenceMasses => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            ['positiveMass', 'negativeMass', 'visibleMass'],
            ['boundaryMass']
        )
    ) {
        return false;
    }
    return (
        isNonNegativeFiniteMassArray(value.positiveMass, expectedLength) &&
        isNonNegativeFiniteMassArray(value.negativeMass, expectedLength) &&
        isNonNegativeFiniteMassArray(value.visibleMass, expectedLength) &&
        (value.boundaryMass === undefined ||
            isNonNegativeFiniteMassArray(value.boundaryMass, expectedLength))
    );
};

const copyMassArray = (value: readonly number[]): readonly number[] => {
    return Object.freeze([...value]);
};

/**
 * A raw reference P/N/V product. Ticket 14A only validates this schema; 14B
 * owns population of its numerical channels and Ticket 20 owns production
 * same-decision Direct Evidence.
 */
export interface GaussianEvidenceArtifact extends AdmittedGaussianEvidenceInput {
    readonly schemaVersion: typeof gaussianEvidenceArtifactSchemaVersion;
    readonly positiveMass: readonly number[];
    readonly negativeMass: readonly number[];
    readonly visibleMass: readonly number[];
    readonly boundaryMass?: readonly number[];
    readonly artifactDigest: string;
}

type GaussianEvidenceArtifactPayload = Omit<
    GaussianEvidenceArtifact,
    'artifactDigest'
>;

const gaussianEvidenceArtifactPayload = (
    admission: AdmittedGaussianEvidenceInput,
    masses: GaussianEvidenceMasses
): GaussianEvidenceArtifactPayload => {
    return {
        schemaVersion: gaussianEvidenceArtifactSchemaVersion,
        requestBinding: {
            targetContextId: admission.requestBinding.targetContextId,
            contextRevision: admission.requestBinding.contextRevision,
            dependencyToken: {
                splatId: admission.requestBinding.dependencyToken.splatId,
                renderStateToken:
                    admission.requestBinding.dependencyToken.renderStateToken,
                geometryToken:
                    admission.requestBinding.dependencyToken.geometryToken,
                gaussianIdentityToken:
                    admission.requestBinding.dependencyToken
                        .gaussianIdentityToken,
                worldTransformToken:
                    admission.requestBinding.dependencyToken.worldTransformToken
            }
        },
        targetSplatId: admission.targetSplatId,
        viewId: admission.viewId,
        cameraBindingDigest: admission.cameraBindingDigest,
        rgbDigest: admission.rgbDigest,
        stableMaskDigest: admission.stableMaskDigest,
        evidencePolicyDigest: admission.evidencePolicyDigest,
        renderWorkingSetToken: admission.renderWorkingSetToken,
        evidenceWorkingSetToken: admission.evidenceWorkingSetToken,
        stableGaussianIds: [...admission.stableGaussianIds],
        positiveMass: [...masses.positiveMass],
        negativeMass: [...masses.negativeMass],
        visibleMass: [...masses.visibleMass],
        ...(masses.boundaryMass === undefined
            ? {}
            : { boundaryMass: [...masses.boundaryMass] }),
        rasterImplementationId: admission.rasterImplementationId,
        evidenceBackendKind: admission.evidenceBackendKind,
        evidenceBackendId: admission.evidenceBackendId,
        runtimeBuildId: admission.runtimeBuildId
    };
};

const isGaussianEvidenceArtifactPayload = (
    value: unknown
): value is GaussianEvidenceArtifactPayload => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'requestBinding',
                'targetSplatId',
                'viewId',
                'cameraBindingDigest',
                'rgbDigest',
                'stableMaskDigest',
                'evidencePolicyDigest',
                'renderWorkingSetToken',
                'evidenceWorkingSetToken',
                'stableGaussianIds',
                'positiveMass',
                'negativeMass',
                'visibleMass',
                'rasterImplementationId',
                'evidenceBackendKind',
                'evidenceBackendId',
                'runtimeBuildId'
            ],
            ['boundaryMass']
        ) ||
        value.schemaVersion !== gaussianEvidenceArtifactSchemaVersion
    ) {
        return false;
    }
    const admission = {
        requestBinding: value.requestBinding,
        targetSplatId: value.targetSplatId,
        viewId: value.viewId,
        cameraBindingDigest: value.cameraBindingDigest,
        rgbDigest: value.rgbDigest,
        stableMaskDigest: value.stableMaskDigest,
        evidencePolicyDigest: value.evidencePolicyDigest,
        renderWorkingSetToken: value.renderWorkingSetToken,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        stableGaussianIds: value.stableGaussianIds,
        rasterImplementationId: value.rasterImplementationId,
        evidenceBackendKind: value.evidenceBackendKind,
        evidenceBackendId: value.evidenceBackendId,
        runtimeBuildId: value.runtimeBuildId
    };
    const candidate = value as GaussianEvidenceArtifactPayload;
    return (
        isAdmittedGaussianEvidenceInput(admission) &&
        isNonNegativeFiniteMassArray(
            candidate.positiveMass,
            candidate.stableGaussianIds.length
        ) &&
        isNonNegativeFiniteMassArray(
            candidate.negativeMass,
            candidate.stableGaussianIds.length
        ) &&
        isNonNegativeFiniteMassArray(
            candidate.visibleMass,
            candidate.stableGaussianIds.length
        ) &&
        (candidate.boundaryMass === undefined ||
            isNonNegativeFiniteMassArray(
                candidate.boundaryMass,
                candidate.stableGaussianIds.length
            ))
    );
};

export const gaussianEvidenceArtifactDigest = (
    payload: GaussianEvidenceArtifactPayload
): string => {
    if (!isGaussianEvidenceArtifactPayload(payload)) {
        throw new Error(
            'AI Select Gaussian Evidence artifact payload is invalid.'
        );
    }
    return canonicalDigest(payload);
};

export const createGaussianEvidenceArtifact = (
    admission: AdmittedGaussianEvidenceInput,
    masses: GaussianEvidenceMasses
): GaussianEvidenceArtifact => {
    if (!isAdmittedGaussianEvidenceInput(admission)) {
        throw new Error('AI Select Gaussian Evidence admission is invalid.');
    }
    if (!isGaussianEvidenceMasses(masses, admission.stableGaussianIds.length)) {
        throw new Error(
            'AI Select Gaussian Evidence requires complete finite non-negative P/N/V arrays.'
        );
    }
    const payload = gaussianEvidenceArtifactPayload(admission, masses);
    if (!isGaussianEvidenceArtifactPayload(payload)) {
        throw new Error(
            'AI Select Gaussian Evidence requires complete finite non-negative P/N/V arrays.'
        );
    }
    return Object.freeze({
        schemaVersion: payload.schemaVersion,
        requestBinding: Object.freeze({
            targetContextId: payload.requestBinding.targetContextId,
            contextRevision: payload.requestBinding.contextRevision,
            dependencyToken: copyDependencyToken(
                payload.requestBinding.dependencyToken
            )
        }),
        targetSplatId: payload.targetSplatId,
        viewId: payload.viewId,
        cameraBindingDigest: payload.cameraBindingDigest,
        rgbDigest: payload.rgbDigest,
        stableMaskDigest: payload.stableMaskDigest,
        evidencePolicyDigest: payload.evidencePolicyDigest,
        renderWorkingSetToken: payload.renderWorkingSetToken,
        evidenceWorkingSetToken: payload.evidenceWorkingSetToken,
        stableGaussianIds: copyStableGaussianIds(payload.stableGaussianIds),
        positiveMass: copyMassArray(payload.positiveMass),
        negativeMass: copyMassArray(payload.negativeMass),
        visibleMass: copyMassArray(payload.visibleMass),
        ...(payload.boundaryMass === undefined
            ? {}
            : { boundaryMass: copyMassArray(payload.boundaryMass) }),
        rasterImplementationId: payload.rasterImplementationId,
        evidenceBackendKind: payload.evidenceBackendKind,
        evidenceBackendId: payload.evidenceBackendId,
        runtimeBuildId: payload.runtimeBuildId,
        artifactDigest: gaussianEvidenceArtifactDigest(payload)
    });
};

export const isGaussianEvidenceArtifact = (
    value: unknown
): value is GaussianEvidenceArtifact => {
    if (
        !isRecord(value) ||
        !hasExactKeys(
            value,
            [
                'schemaVersion',
                'requestBinding',
                'targetSplatId',
                'viewId',
                'cameraBindingDigest',
                'rgbDigest',
                'stableMaskDigest',
                'evidencePolicyDigest',
                'renderWorkingSetToken',
                'evidenceWorkingSetToken',
                'stableGaussianIds',
                'positiveMass',
                'negativeMass',
                'visibleMass',
                'rasterImplementationId',
                'evidenceBackendKind',
                'evidenceBackendId',
                'runtimeBuildId',
                'artifactDigest'
            ],
            ['boundaryMass']
        ) ||
        !isDigest(value.artifactDigest)
    ) {
        return false;
    }
    const { artifactDigest, ...payload } = value;
    return (
        isGaussianEvidenceArtifactPayload(payload) &&
        gaussianEvidenceArtifactDigest(payload) === artifactDigest
    );
};

const areRequestBindingsEqual = (
    left: AIRequestBinding,
    right: AIRequestBinding
): boolean => {
    return (
        left.targetContextId === right.targetContextId &&
        left.contextRevision === right.contextRevision &&
        areTargetDependencyTokensEqual(
            left.dependencyToken,
            right.dependencyToken
        )
    );
};

/**
 * An artifact may only become current after the exact Ticket 14A admission
 * is re-evaluated. This covers exclude/reinclude, Stable Mask replacement,
 * Working Set expansion, and every runtime identity without a mutable cache
 * shortcut.
 */
export const gaussianEvidenceArtifactMatchesAdmission = (
    artifact: unknown,
    admission: unknown
): boolean => {
    return (
        isGaussianEvidenceArtifact(artifact) &&
        isAdmittedGaussianEvidenceInput(admission) &&
        areRequestBindingsEqual(
            artifact.requestBinding,
            admission.requestBinding
        ) &&
        artifact.targetSplatId === admission.targetSplatId &&
        artifact.viewId === admission.viewId &&
        artifact.cameraBindingDigest === admission.cameraBindingDigest &&
        artifact.rgbDigest === admission.rgbDigest &&
        artifact.stableMaskDigest === admission.stableMaskDigest &&
        artifact.evidencePolicyDigest === admission.evidencePolicyDigest &&
        artifact.renderWorkingSetToken === admission.renderWorkingSetToken &&
        artifact.evidenceWorkingSetToken ===
            admission.evidenceWorkingSetToken &&
        areStableGaussianIdArraysEqual(
            artifact.stableGaussianIds,
            admission.stableGaussianIds
        ) &&
        artifact.rasterImplementationId === admission.rasterImplementationId &&
        artifact.evidenceBackendKind === admission.evidenceBackendKind &&
        artifact.evidenceBackendId === admission.evidenceBackendId &&
        artifact.runtimeBuildId === admission.runtimeBuildId
    );
};

export const isCurrentGaussianEvidenceArtifact = (
    artifact: unknown,
    currentInput: unknown
): boolean => {
    const currentAdmission = admitGaussianEvidence(currentInput);
    return (
        currentAdmission.status === 'admitted' &&
        gaussianEvidenceArtifactMatchesAdmission(
            artifact,
            currentAdmission.admission
        )
    );
};

export interface EvidenceWorkingSetBoundaryInput {
    readonly renderWorkingSet: RenderWorkingSetBinding;
    readonly evidenceWorkingSet: EvidenceWorkingSet;
    /** IDs observed at the capture boundary before any P/N/V write occurs. */
    readonly boundaryStableGaussianIds: readonly number[];
    readonly resolution: 'expand' | 'fail-closed';
    readonly expansion?: EvidenceWorkingSetExpansion;
}

export type EvidenceWorkingSetBoundaryResolution =
    | {
          readonly status: 'clear';
          readonly contactStableGaussianIds: readonly number[];
      }
    | {
          readonly status: 'expanded';
          readonly contactStableGaussianIds: readonly number[];
          readonly evidenceWorkingSet: EvidenceWorkingSet;
      }
    | {
          readonly status: 'failed-closed';
          readonly reason:
              | 'invalid-boundary-input'
              | 'stable-id-mapping-invalid'
              | 'evidence-working-set-boundary-contact'
              | 'expansion-does-not-cover-boundary';
          readonly contactStableGaussianIds: readonly number[];
      };

const failedBoundary = (
    reason: Extract<
        EvidenceWorkingSetBoundaryResolution,
        { readonly status: 'failed-closed' }
    >['reason'],
    contactStableGaussianIds: readonly number[] = []
): EvidenceWorkingSetBoundaryResolution => {
    return Object.freeze({
        status: 'failed-closed',
        reason,
        contactStableGaussianIds: Object.freeze([...contactStableGaussianIds])
    });
};

/**
 * Report a boundary contact before Evidence writes. The caller must either
 * expand the scope from an Included Stable View or abandon this attempt; an
 * Evidence Working Set is never silently truncated at its boundary.
 */
export const resolveEvidenceWorkingSetBoundary = (
    input: unknown
): EvidenceWorkingSetBoundaryResolution => {
    if (
        !isRecord(input) ||
        !hasExactKeys(
            input,
            [
                'renderWorkingSet',
                'evidenceWorkingSet',
                'boundaryStableGaussianIds',
                'resolution'
            ],
            ['expansion']
        ) ||
        !isRenderWorkingSetBinding(input.renderWorkingSet) ||
        !isEvidenceWorkingSet(input.evidenceWorkingSet) ||
        !isStrictlyAscendingStableGaussianIds(
            input.boundaryStableGaussianIds,
            true
        ) ||
        (input.resolution !== 'expand' && input.resolution !== 'fail-closed')
    ) {
        return failedBoundary('invalid-boundary-input');
    }
    const candidate = input as unknown as EvidenceWorkingSetBoundaryInput;
    if (
        candidate.renderWorkingSet.completeness !== 'complete' ||
        candidate.renderWorkingSet.targetSplatId !==
            candidate.evidenceWorkingSet.targetSplatId
    ) {
        return failedBoundary('invalid-boundary-input');
    }
    const contactStableGaussianIds = candidate.boundaryStableGaussianIds.filter(
        (stableId) =>
            !candidate.evidenceWorkingSet.stableGaussianIds.includes(stableId)
    );
    if (contactStableGaussianIds.length === 0) {
        return Object.freeze({
            status: 'clear',
            contactStableGaussianIds: Object.freeze([])
        });
    }
    if (
        !stableGaussianIdsAreSubsetOf(
            contactStableGaussianIds,
            candidate.renderWorkingSet.stableGaussianIds
        )
    ) {
        return failedBoundary(
            'stable-id-mapping-invalid',
            contactStableGaussianIds
        );
    }
    if (candidate.resolution === 'fail-closed') {
        return failedBoundary(
            'evidence-working-set-boundary-contact',
            contactStableGaussianIds
        );
    }
    if (!isEvidenceWorkingSetExpansion(candidate.expansion)) {
        return failedBoundary(
            'expansion-does-not-cover-boundary',
            contactStableGaussianIds
        );
    }
    let evidenceWorkingSet: EvidenceWorkingSet;
    try {
        evidenceWorkingSet = expandEvidenceWorkingSet(
            candidate.evidenceWorkingSet,
            candidate.expansion
        );
    } catch {
        return failedBoundary(
            'expansion-does-not-cover-boundary',
            contactStableGaussianIds
        );
    }
    if (
        !stableGaussianIdsAreSubsetOf(
            contactStableGaussianIds,
            evidenceWorkingSet.stableGaussianIds
        ) ||
        !stableGaussianIdsAreSubsetOf(
            evidenceWorkingSet.stableGaussianIds,
            candidate.renderWorkingSet.stableGaussianIds
        )
    ) {
        return failedBoundary(
            'expansion-does-not-cover-boundary',
            contactStableGaussianIds
        );
    }
    return Object.freeze({
        status: 'expanded',
        contactStableGaussianIds: Object.freeze([...contactStableGaussianIds]),
        evidenceWorkingSet: copyEvidenceWorkingSet(evidenceWorkingSet)
    });
};
