import { sha256Digest } from '../scene-snapshot-binary';
import {
    copyDependencyToken,
    isAIRequestBinding,
    type AIRequestBinding
} from './current-target-context';
import type { AISelectDirtyStateTracker } from './dirty-state';

export const liftReadinessSchemaVersion = 1;
export const liftReadinessKind = 'lift-readiness/production-v1' as const;

export type LiftReadinessLevel = 'not-ready' | 'limited' | 'ready';
export type LiftReadinessSource =
    'formal-evidence' | 'low-cost-diagnostic' | 'none';
export type LiftReadinessReason =
    | 'formal-evidence-pending'
    | 'low-visible-support'
    | 'weak-gaussian-support'
    | 'low-view-diversity';
export type LiftReadinessRecommendation =
    'none' | 'wait-for-current-views' | 'generate-more' | 'add-view';
export type LiftReadinessGenerationState =
    'active' | 'stopped' | 'complete' | 'unavailable';

export interface LiftReadinessPolicy {
    readonly schemaVersion: 1;
    readonly policyId: typeof liftReadinessKind;
    readonly minimumPerGaussianVisibleMass: number;
    readonly minimumLimitedCoverageRatio: number;
    readonly minimumReadyCoverageRatio: number;
    readonly minimumUsefulViewCoverageRatio: number;
    readonly minimumReadyViewDiversityDegrees: number;
    readonly coverageAggregationMode: 'max-per-view-visible-mass/v1';
    readonly viewDirectionMode: 'opencv-camera-forward/v1';
    readonly readinessPolicyDigest: string;
}

export type ObservationCoverage =
    | Readonly<{
          status: 'available';
          coverageRatio: number;
          observedCoreGaussianCount: number;
          totalCoreGaussianCount: number;
      }>
    | Readonly<{
          status: 'pending-formal-evidence';
          totalCoreGaussianCount: number;
      }>;

export interface ViewDiversity {
    readonly status:
        'available' | 'insufficient-support' | 'pending-formal-evidence';
    readonly usefulViewCount: number;
    readonly maximumAngularSeparationDegrees: number;
}

export interface LiftReadinessArtifact {
    readonly schemaVersion: typeof liftReadinessSchemaVersion;
    readonly kind: typeof liftReadinessKind;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly evidenceWorkingSetToken: string;
    readonly evidenceArtifactSetDigest: string | null;
    readonly aggregationResultDigest: string | null;
    readonly readinessPolicy: LiftReadinessPolicy;
    readonly readinessPolicyDigest: string;
    readonly source: LiftReadinessSource;
    readonly lowCostSupportDiagnosticDigest: string | null;
    readonly observationCoverage: ObservationCoverage;
    readonly viewDiversity: ViewDiversity;
    readonly readiness: LiftReadinessLevel;
    readonly reasons: readonly LiftReadinessReason[];
    readonly generationState: LiftReadinessGenerationState;
    readonly recommendation: LiftReadinessRecommendation;
    readonly resultDigest: string;
}

export interface LiftReadinessBinding {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly evidenceWorkingSetToken: string;
    readonly evidenceArtifactSetDigest: string | null;
    readonly aggregationResultDigest: string | null;
    readonly readinessPolicyDigest: string;
    readonly source: LiftReadinessSource;
    readonly lowCostSupportDiagnosticDigest: string | null;
    readonly generationState: LiftReadinessGenerationState;
}

export type LiftReadinessState =
    | Readonly<{
          status: 'empty';
          readiness: null;
          observationCoverage: null;
          viewDiversity: null;
          reasons: readonly [];
          recommendation: null;
          source: null;
      }>
    | Readonly<{
          status: 'current' | 'stale';
          readiness: LiftReadinessLevel;
          observationCoverage: ObservationCoverage;
          viewDiversity: ViewDiversity;
          reasons: readonly LiftReadinessReason[];
          recommendation: LiftReadinessRecommendation;
          source: LiftReadinessSource;
      }>;

export type LiftReadinessListener = (state: LiftReadinessState) => void;

type UnknownRecord = Record<string, unknown>;

const encoder = new TextEncoder();
const digestPattern = /^sha256:[a-f0-9]{64}$/;
const readinessLevels = new Set<LiftReadinessLevel>([
    'not-ready',
    'limited',
    'ready'
]);
const readinessSources = new Set<LiftReadinessSource>([
    'formal-evidence',
    'low-cost-diagnostic',
    'none'
]);
const readinessReasons = new Set<LiftReadinessReason>([
    'formal-evidence-pending',
    'low-visible-support',
    'weak-gaussian-support',
    'low-view-diversity'
]);
const recommendations = new Set<LiftReadinessRecommendation>([
    'none',
    'wait-for-current-views',
    'generate-more',
    'add-view'
]);
const generationStates = new Set<LiftReadinessGenerationState>([
    'active',
    'stopped',
    'complete',
    'unavailable'
]);

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

const isExactRequestBinding = (value: unknown): value is AIRequestBinding => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'targetContextId',
            'contextRevision',
            'dependencyToken'
        ]) ||
        !isAIRequestBinding(value) ||
        !isRecord(value.dependencyToken)
    ) {
        return false;
    }
    return hasExactKeys(value.dependencyToken, [
        'splatId',
        'renderStateToken',
        'geometryToken',
        'gaussianIdentityToken',
        'worldTransformToken'
    ]);
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && digestPattern.test(value);
};

const isNonNegativeSafeInteger = (value: unknown): value is number => {
    return Number.isSafeInteger(value) && (value as number) >= 0;
};

const isFiniteRange = (value: unknown, minimum: number, maximum: number) => {
    return (
        typeof value === 'number' &&
        Number.isFinite(value) &&
        value >= minimum &&
        value <= maximum
    );
};

const asciiJsonString = (value: string): string => {
    return JSON.stringify(value).replace(/[\u007f-\uffff]/g, (character) => {
        return `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`;
    });
};

/** Match the Companion's IEEE-754 canonical artifact encoding. */
const readinessCanonicalJson = (value: unknown): string => {
    if (typeof value === 'number') {
        if (!Number.isFinite(value)) {
            throw new Error(
                'AI Select Lift Readiness artifact numbers must be finite.'
            );
        }
        const bytes = new Uint8Array(8);
        new DataView(bytes.buffer).setFloat64(
            0,
            value === 0 ? 0 : value,
            false
        );
        return `n${[...bytes]
            .map((byte) => byte.toString(16).padStart(2, '0'))
            .join('')}`;
    }
    if (typeof value === 'string') {
        return asciiJsonString(value);
    }
    if (Array.isArray(value)) {
        return `[${value.map(readinessCanonicalJson).join(',')}]`;
    }
    if (isRecord(value)) {
        return `{${Object.keys(value)
            .sort()
            .map(
                (key) =>
                    `${asciiJsonString(key)}:${readinessCanonicalJson(value[key])}`
            )
            .join(',')}}`;
    }
    const primitive = JSON.stringify(value);
    if (typeof primitive !== 'string') {
        throw new Error(
            'AI Select Lift Readiness artifact contains invalid JSON data.'
        );
    }
    return primitive;
};

const readinessDigest = (value: unknown): string => {
    return sha256Digest(encoder.encode(readinessCanonicalJson(value)));
};

export const defaultLiftReadinessPolicy = (): LiftReadinessPolicy => {
    const payload = Object.freeze({
        schemaVersion: 1 as const,
        policyId: liftReadinessKind,
        minimumPerGaussianVisibleMass: 0.1,
        minimumLimitedCoverageRatio: 0.25,
        minimumReadyCoverageRatio: 0.75,
        minimumUsefulViewCoverageRatio: 0.1,
        minimumReadyViewDiversityDegrees: 20,
        coverageAggregationMode: 'max-per-view-visible-mass/v1' as const,
        viewDirectionMode: 'opencv-camera-forward/v1' as const
    });
    return Object.freeze({
        ...payload,
        readinessPolicyDigest: readinessDigest(payload)
    });
};

const isPolicy = (value: unknown): value is LiftReadinessPolicy => {
    if (!isRecord(value)) {
        return false;
    }
    const expected = defaultLiftReadinessPolicy();
    try {
        return (
            readinessCanonicalJson(value) === readinessCanonicalJson(expected)
        );
    } catch {
        return false;
    }
};

const isCoverage = (
    value: unknown,
    source: LiftReadinessSource
): value is ObservationCoverage => {
    if (!isRecord(value)) {
        return false;
    }
    if (source === 'formal-evidence') {
        return (
            hasExactKeys(value, [
                'status',
                'coverageRatio',
                'observedCoreGaussianCount',
                'totalCoreGaussianCount'
            ]) &&
            value.status === 'available' &&
            isFiniteRange(value.coverageRatio, 0, 1) &&
            isNonNegativeSafeInteger(value.observedCoreGaussianCount) &&
            isNonNegativeSafeInteger(value.totalCoreGaussianCount) &&
            value.observedCoreGaussianCount <= value.totalCoreGaussianCount
        );
    }
    return (
        hasExactKeys(value, ['status', 'totalCoreGaussianCount']) &&
        value.status === 'pending-formal-evidence' &&
        isNonNegativeSafeInteger(value.totalCoreGaussianCount)
    );
};

const isViewDiversity = (
    value: unknown,
    source: LiftReadinessSource
): value is ViewDiversity => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'status',
            'usefulViewCount',
            'maximumAngularSeparationDegrees'
        ]) ||
        !isNonNegativeSafeInteger(value.usefulViewCount) ||
        !isFiniteRange(value.maximumAngularSeparationDegrees, 0, 180)
    ) {
        return false;
    }
    return source === 'formal-evidence'
        ? value.status === 'available' ||
              value.status === 'insufficient-support'
        : value.status === 'pending-formal-evidence';
};

const isReasonList = (
    value: unknown
): value is readonly LiftReadinessReason[] => {
    return (
        Array.isArray(value) &&
        value.every((reason) => readinessReasons.has(reason)) &&
        new Set(value).size === value.length
    );
};

const reasonsEqual = (
    actual: readonly LiftReadinessReason[],
    expected: readonly LiftReadinessReason[]
): boolean => {
    return (
        actual.length === expected.length &&
        actual.every((reason, index) => reason === expected[index])
    );
};

const recommendationFor = (
    readiness: LiftReadinessLevel,
    generationState: LiftReadinessGenerationState
): LiftReadinessRecommendation => {
    if (readiness === 'ready') {
        return 'none';
    }
    if (generationState === 'active') {
        return 'wait-for-current-views';
    }
    return generationState === 'stopped' || generationState === 'complete'
        ? 'generate-more'
        : 'add-view';
};

const hasConsistentSemantics = (value: UnknownRecord): boolean => {
    const source = value.source as LiftReadinessSource;
    const readiness = value.readiness as LiftReadinessLevel;
    const generationState =
        value.generationState as LiftReadinessGenerationState;
    const reasons = value.reasons as readonly LiftReadinessReason[];
    const coverage = value.observationCoverage as ObservationCoverage;
    const diversity = value.viewDiversity as ViewDiversity;
    if (
        value.recommendation !== recommendationFor(readiness, generationState)
    ) {
        return false;
    }
    if (source !== 'formal-evidence') {
        if (
            diversity.usefulViewCount !== 0 ||
            diversity.maximumAngularSeparationDegrees !== 0
        ) {
            return false;
        }
        return source === 'low-cost-diagnostic' && readiness === 'limited'
            ? reasonsEqual(reasons, ['formal-evidence-pending'])
            : readiness === 'not-ready' &&
                  reasonsEqual(reasons, [
                      'formal-evidence-pending',
                      'low-visible-support',
                      'weak-gaussian-support'
                  ]);
    }
    if (coverage.status !== 'available') {
        return false;
    }
    const expectedReasons: LiftReadinessReason[] = [];
    let expectedReadiness: LiftReadinessLevel = 'ready';
    if (
        coverage.coverageRatio <
        defaultLiftReadinessPolicy().minimumLimitedCoverageRatio
    ) {
        expectedReadiness = 'not-ready';
        expectedReasons.push('low-visible-support', 'weak-gaussian-support');
    } else {
        if (
            coverage.coverageRatio <
            defaultLiftReadinessPolicy().minimumReadyCoverageRatio
        ) {
            expectedReadiness = 'limited';
            expectedReasons.push('weak-gaussian-support');
        }
        if (
            diversity.status !== 'available' ||
            diversity.maximumAngularSeparationDegrees <
                defaultLiftReadinessPolicy().minimumReadyViewDiversityDegrees
        ) {
            expectedReadiness = 'limited';
            expectedReasons.push('low-view-diversity');
        }
    }
    const expectedDiversityStatus =
        diversity.usefulViewCount > 0 ? 'available' : 'insufficient-support';
    return (
        readiness === expectedReadiness &&
        reasonsEqual(reasons, expectedReasons) &&
        diversity.status === expectedDiversityStatus &&
        (diversity.usefulViewCount >= 2 ||
            diversity.maximumAngularSeparationDegrees === 0)
    );
};

export const isLiftReadinessArtifact = (
    value: unknown
): value is LiftReadinessArtifact => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'schemaVersion',
            'kind',
            'requestBinding',
            'targetSplatId',
            'evidenceWorkingSetToken',
            'evidenceArtifactSetDigest',
            'aggregationResultDigest',
            'readinessPolicy',
            'readinessPolicyDigest',
            'source',
            'lowCostSupportDiagnosticDigest',
            'observationCoverage',
            'viewDiversity',
            'readiness',
            'reasons',
            'generationState',
            'recommendation',
            'resultDigest'
        ]) ||
        value.schemaVersion !== liftReadinessSchemaVersion ||
        value.kind !== liftReadinessKind ||
        !isExactRequestBinding(value.requestBinding) ||
        !isNonEmptyString(value.targetSplatId) ||
        value.requestBinding.dependencyToken.splatId !== value.targetSplatId ||
        !isDigest(value.evidenceWorkingSetToken) ||
        !isPolicy(value.readinessPolicy) ||
        value.readinessPolicyDigest !==
            value.readinessPolicy.readinessPolicyDigest ||
        !readinessSources.has(value.source as LiftReadinessSource) ||
        !readinessLevels.has(value.readiness as LiftReadinessLevel) ||
        !isReasonList(value.reasons) ||
        !generationStates.has(
            value.generationState as LiftReadinessGenerationState
        ) ||
        !recommendations.has(
            value.recommendation as LiftReadinessRecommendation
        ) ||
        !isDigest(value.resultDigest)
    ) {
        return false;
    }
    const source = value.source as LiftReadinessSource;
    if (
        !isCoverage(value.observationCoverage, source) ||
        !isViewDiversity(value.viewDiversity, source)
    ) {
        return false;
    }
    if (source === 'formal-evidence') {
        if (
            !isDigest(value.evidenceArtifactSetDigest) ||
            !isDigest(value.aggregationResultDigest)
        ) {
            return false;
        }
    } else if (
        value.evidenceArtifactSetDigest !== null ||
        value.aggregationResultDigest !== null
    ) {
        return false;
    }
    if (source === 'low-cost-diagnostic') {
        if (!isDigest(value.lowCostSupportDiagnosticDigest)) {
            return false;
        }
    } else if (source === 'none') {
        if (value.lowCostSupportDiagnosticDigest !== null) {
            return false;
        }
    } else if (
        value.lowCostSupportDiagnosticDigest !== null &&
        !isDigest(value.lowCostSupportDiagnosticDigest)
    ) {
        return false;
    }
    if (!hasConsistentSemantics(value)) {
        return false;
    }
    const payload = Object.fromEntries(
        Object.entries(value).filter(([key]) => key !== 'resultDigest')
    );
    try {
        return value.resultDigest === readinessDigest(payload);
    } catch {
        return false;
    }
};

const copyRequestBinding = (value: AIRequestBinding): AIRequestBinding => {
    return Object.freeze({
        targetContextId: value.targetContextId,
        contextRevision: value.contextRevision,
        dependencyToken: copyDependencyToken(value.dependencyToken)
    });
};

const copyBinding = (value: LiftReadinessBinding): LiftReadinessBinding => {
    return Object.freeze({
        requestBinding: copyRequestBinding(value.requestBinding),
        targetSplatId: value.targetSplatId,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: value.evidenceArtifactSetDigest,
        aggregationResultDigest: value.aggregationResultDigest,
        readinessPolicyDigest: value.readinessPolicyDigest,
        source: value.source,
        lowCostSupportDiagnosticDigest: value.lowCostSupportDiagnosticDigest,
        generationState: value.generationState
    });
};

const isBinding = (value: unknown): value is LiftReadinessBinding => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'evidenceWorkingSetToken',
            'evidenceArtifactSetDigest',
            'aggregationResultDigest',
            'readinessPolicyDigest',
            'source',
            'lowCostSupportDiagnosticDigest',
            'generationState'
        ]) &&
        isExactRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        value.requestBinding.dependencyToken.splatId === value.targetSplatId &&
        isDigest(value.evidenceWorkingSetToken) &&
        (value.evidenceArtifactSetDigest === null ||
            isDigest(value.evidenceArtifactSetDigest)) &&
        (value.aggregationResultDigest === null ||
            isDigest(value.aggregationResultDigest)) &&
        isDigest(value.readinessPolicyDigest) &&
        readinessSources.has(value.source as LiftReadinessSource) &&
        (value.lowCostSupportDiagnosticDigest === null ||
            isDigest(value.lowCostSupportDiagnosticDigest)) &&
        generationStates.has(
            value.generationState as LiftReadinessGenerationState
        )
    );
};

const bindingsEqual = (
    left: LiftReadinessBinding,
    right: LiftReadinessBinding
): boolean => {
    return readinessCanonicalJson(left) === readinessCanonicalJson(right);
};

export const liftReadinessBindingFromArtifact = (
    value: unknown
): LiftReadinessBinding => {
    if (!isLiftReadinessArtifact(value)) {
        throw new Error('AI Select Lift Readiness artifact is invalid.');
    }
    return copyBinding({
        requestBinding: value.requestBinding,
        targetSplatId: value.targetSplatId,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: value.evidenceArtifactSetDigest,
        aggregationResultDigest: value.aggregationResultDigest,
        readinessPolicyDigest: value.readinessPolicyDigest,
        source: value.source,
        lowCostSupportDiagnosticDigest: value.lowCostSupportDiagnosticDigest,
        generationState: value.generationState
    });
};

const copyCoverage = (value: ObservationCoverage): ObservationCoverage => {
    return value.status === 'available'
        ? Object.freeze({
              status: value.status,
              coverageRatio: value.coverageRatio,
              observedCoreGaussianCount: value.observedCoreGaussianCount,
              totalCoreGaussianCount: value.totalCoreGaussianCount
          })
        : Object.freeze({
              status: value.status,
              totalCoreGaussianCount: value.totalCoreGaussianCount
          });
};

const copyDiversity = (value: ViewDiversity): ViewDiversity => {
    return Object.freeze({
        status: value.status,
        usefulViewCount: value.usefulViewCount,
        maximumAngularSeparationDegrees: value.maximumAngularSeparationDegrees
    });
};

const copyArtifact = (value: LiftReadinessArtifact): LiftReadinessArtifact => {
    return Object.freeze({
        schemaVersion: value.schemaVersion,
        kind: value.kind,
        requestBinding: copyRequestBinding(value.requestBinding),
        targetSplatId: value.targetSplatId,
        evidenceWorkingSetToken: value.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: value.evidenceArtifactSetDigest,
        aggregationResultDigest: value.aggregationResultDigest,
        readinessPolicy: defaultLiftReadinessPolicy(),
        readinessPolicyDigest: value.readinessPolicyDigest,
        source: value.source,
        lowCostSupportDiagnosticDigest: value.lowCostSupportDiagnosticDigest,
        observationCoverage: copyCoverage(value.observationCoverage),
        viewDiversity: copyDiversity(value.viewDiversity),
        readiness: value.readiness,
        reasons: Object.freeze([...value.reasons]),
        generationState: value.generationState,
        recommendation: value.recommendation,
        resultDigest: value.resultDigest
    });
};

/** Browser-owned target-local publication state; it never starts Lift work. */
export class LiftReadinessStore {
    private published: LiftReadinessArtifact | null = null;
    private currentBinding: LiftReadinessBinding | null = null;
    private staleSincePublication = false;
    private readonly listeners = new Set<LiftReadinessListener>();

    constructor(private readonly dirtyState: AISelectDirtyStateTracker) {
        this.dirtyState.subscribe((state) => {
            if (state.liftDirty) {
                this.staleSincePublication = true;
            }
            this.notify();
        });
    }

    get inspectableArtifact(): LiftReadinessArtifact | null {
        return this.published === null ? null : copyArtifact(this.published);
    }

    get presentationState(): LiftReadinessState {
        return this.currentBinding === null
            ? this.emptyState()
            : this.state(this.currentBinding);
    }

    subscribe(listener: LiftReadinessListener): () => void {
        listener(this.presentationState);
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    synchronizeCurrentBinding(value: LiftReadinessBinding): void {
        if (!isBinding(value)) {
            throw new Error('AI Select Lift Readiness binding is invalid.');
        }
        this.currentBinding = copyBinding(value);
        this.notify();
    }

    publish(value: unknown, currentBinding: LiftReadinessBinding): void {
        if (!isLiftReadinessArtifact(value)) {
            throw new Error('AI Select Lift Readiness artifact is invalid.');
        }
        const artifactBinding = liftReadinessBindingFromArtifact(value);
        if (
            !isBinding(currentBinding) ||
            !bindingsEqual(artifactBinding, currentBinding)
        ) {
            throw new Error(
                'AI Select Lift Readiness does not match current inputs.'
            );
        }
        const replacement = copyArtifact(value);
        if (!isLiftReadinessArtifact(replacement)) {
            throw new Error(
                'AI Select Lift Readiness defensive copy is invalid.'
            );
        }
        this.published = replacement;
        this.currentBinding = copyBinding(currentBinding);
        this.staleSincePublication = false;
        this.notify();
    }

    state(currentBinding: LiftReadinessBinding): LiftReadinessState {
        if (this.published === null) {
            return this.emptyState();
        }
        const isCurrent =
            isBinding(currentBinding) &&
            bindingsEqual(
                liftReadinessBindingFromArtifact(this.published),
                currentBinding
            ) &&
            !this.staleSincePublication &&
            !this.dirtyState.state.liftDirty;
        return Object.freeze({
            status: isCurrent ? 'current' : 'stale',
            readiness: this.published.readiness,
            observationCoverage: copyCoverage(
                this.published.observationCoverage
            ),
            viewDiversity: copyDiversity(this.published.viewDiversity),
            reasons: Object.freeze([...this.published.reasons]),
            recommendation: this.published.recommendation,
            source: this.published.source
        });
    }

    reset(): void {
        this.published = null;
        this.currentBinding = null;
        this.staleSincePublication = false;
        this.notify();
    }

    private emptyState(): LiftReadinessState {
        return Object.freeze({
            status: 'empty',
            readiness: null,
            observationCoverage: null,
            viewDiversity: null,
            reasons: Object.freeze([]) as readonly [],
            recommendation: null,
            source: null
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
