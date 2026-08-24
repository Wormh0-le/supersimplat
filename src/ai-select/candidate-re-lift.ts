import {
    cameraBindingDigest,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    createProductionCandidatePublicationBinding,
    isProductionCandidateArtifact,
    type ProductionCandidateArtifact
} from './candidate-publication';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding
} from './current-target-context';
import {
    isCurrentGaussianEvidenceArtifact,
    isEvidenceWorkingSet,
    isGaussianEvidenceAdmissionInput,
    isGaussianEvidenceArtifact,
    type EvidenceWorkingSet,
    type GaussianEvidenceAdmissionInput,
    type GaussianEvidenceArtifact
} from './gaussian-evidence-contract';
import {
    isLiftReadinessArtifact,
    type LiftReadinessArtifact
} from './lift-readiness';
import { isMaskArtifact, type MaskArtifact } from './mask-annotation';
import {
    isPackedSceneSnapshot,
    sha256Digest,
    type PackedSceneSnapshot
} from '../scene-snapshot-binary';

export const referenceEvidencePolicyDigest =
    'sha256:debcee99d261f28ab373b16016447f056872476a960a1af23599cc6ea1f20efd';
export const referenceAggregationPolicyDigest =
    'sha256:082dd2a030a21448c16571ce28f741fa50023a831990cae3dd3e7bcc16c02454';
export const referenceEvidenceRasterImplementationId =
    'supersimplat-gsplat-direct-evidence/v1';
export const referenceContributorEvidenceBackendId =
    'complete-contributor/reference-v1';
export const referenceEvidenceRuntimeBuildId =
    'sha256:257246d607e60657d8fad868d5e2cc9792f06e893e7d28279885cf888e13807f';
export const productionEvidencePolicyDigest = referenceEvidencePolicyDigest;
export const productionAggregationPolicyDigest =
    referenceAggregationPolicyDigest;
export const productionEvidenceRasterImplementationId =
    'supersimplat-gsplat-direct-evidence/v1';
export const productionDirectEvidenceBackendId = 'global-atomic/direct-v1';
export const productionEvidenceRuntimeBuildId = referenceEvidenceRuntimeBuildId;

export interface CandidateReLiftViewInput {
    readonly currentInput: GaussianEvidenceAdmissionInput;
    readonly cameraBinding: CameraBinding;
    readonly stableMask: MaskArtifact;
    readonly cachedArtifact?: GaussianEvidenceArtifact;
}

export interface CandidateReLiftRequest {
    readonly liftAttemptId: string;
    readonly productionIdentityDigest: string;
    readonly generationState: 'active' | 'stopped' | 'complete' | 'unavailable';
    readonly snapshot: PackedSceneSnapshot;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly classificationUniverseStableGaussianIds: readonly number[];
    readonly classificationScopeStableGaussianIds: readonly number[];
    readonly evidenceWorkingSet: EvidenceWorkingSet;
    readonly views: readonly CandidateReLiftViewInput[];
}

export interface CandidateReLiftEvidenceResult {
    readonly viewId: string;
    readonly reused: boolean;
    readonly artifact: GaussianEvidenceArtifact;
}

interface CandidateReLiftResponseBase {
    readonly liftAttemptId: string;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly evidence: readonly CandidateReLiftEvidenceResult[];
    readonly liftReadiness: LiftReadinessArtifact;
}

export interface CandidateReLiftCompleteResponse extends CandidateReLiftResponseBase {
    readonly status: 'complete';
    readonly candidate: ProductionCandidateArtifact;
}

export interface CandidateReLiftNotReadyResponse extends CandidateReLiftResponseBase {
    readonly status: 'not-ready';
}

export type CandidateReLiftResponse =
    CandidateReLiftCompleteResponse | CandidateReLiftNotReadyResponse;

export interface AISelectCandidateReLiftProvider {
    produceCandidateReLift(
        request: CandidateReLiftRequest
    ): Promise<CandidateReLiftResponse>;
}

type UnknownRecord = Record<string, unknown>;
const encoder = new TextEncoder();

const isRecord = (value: unknown): value is UnknownRecord =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const bindingMatches = (
    left: AIRequestBinding,
    right: AIRequestBinding
): boolean =>
    left.targetContextId === right.targetContextId &&
    left.contextRevision === right.contextRevision &&
    areTargetDependencyTokensEqual(left.dependencyToken, right.dependencyToken);

const compareUtf8 = (left: string, right: string): number => {
    const leftBytes = encoder.encode(left);
    const rightBytes = encoder.encode(right);
    const length = Math.min(leftBytes.length, rightBytes.length);
    for (let index = 0; index < length; index += 1) {
        if (leftBytes[index] !== rightBytes[index]) {
            return leftBytes[index] - rightBytes[index];
        }
    }
    return leftBytes.length - rightBytes.length;
};

const stableIdsEqual = (
    left: readonly number[],
    right: readonly number[]
): boolean =>
    left.length === right.length &&
    left.every((stableId, index) => stableId === right[index]);

const stableIdsAreSubsetOf = (
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

const targetStableIds = (
    snapshot: PackedSceneSnapshot,
    targetSplatId: string
): readonly number[] => {
    const scope = snapshot.authoritativeRenderScope;
    const target = scope?.entries.find(
        (entry) => entry.role === 'target' && entry.splatId === targetSplatId
    );
    if (
        scope?.targetSplatId !== targetSplatId ||
        target === undefined ||
        target.rowOffset < 0 ||
        target.rowCount <= 0 ||
        target.rowOffset + target.rowCount > snapshot.stableIds.length
    ) {
        return [];
    }
    return [...snapshot.stableIds]
        .slice(target.rowOffset, target.rowOffset + target.rowCount)
        .sort((left, right) => left - right);
};

export const isCandidateReLiftRequest = (
    value: unknown
): value is CandidateReLiftRequest => {
    if (
        !isRecord(value) ||
        typeof value.liftAttemptId !== 'string' ||
        value.liftAttemptId.length === 0 ||
        typeof value.productionIdentityDigest !== 'string' ||
        !/^sha256:[a-f0-9]{64}$/i.test(value.productionIdentityDigest) ||
        (value.generationState !== 'active' &&
            value.generationState !== 'stopped' &&
            value.generationState !== 'complete' &&
            value.generationState !== 'unavailable') ||
        !isPackedSceneSnapshot(value.snapshot) ||
        !isAIRequestBinding(value.requestBinding) ||
        typeof value.targetSplatId !== 'string' ||
        !Array.isArray(value.classificationUniverseStableGaussianIds) ||
        !Array.isArray(value.classificationScopeStableGaussianIds) ||
        !isEvidenceWorkingSet(value.evidenceWorkingSet) ||
        !Array.isArray(value.views) ||
        value.views.length === 0
    ) {
        return false;
    }
    const snapshot = value.snapshot;
    const requestBinding = value.requestBinding;
    const targetSplatId = value.targetSplatId;
    const evidenceWorkingSet = value.evidenceWorkingSet;
    const snapshotStableIds = [...snapshot.stableIds].sort(
        (left, right) => left - right
    );
    const targetIds = targetStableIds(snapshot, targetSplatId);
    const universe = value.classificationUniverseStableGaussianIds;
    const scope = value.classificationScopeStableGaussianIds;
    return (
        requestBinding.dependencyToken.splatId === targetSplatId &&
        snapshot.sceneId === targetSplatId &&
        evidenceWorkingSet.targetSplatId === targetSplatId &&
        targetIds.length > 0 &&
        stableIdsEqual(universe, targetIds) &&
        stableIdsAreSubsetOf(scope, universe) &&
        stableIdsAreSubsetOf(evidenceWorkingSet.stableGaussianIds, universe) &&
        value.views.every((entry) => {
            if (
                !isRecord(entry) ||
                !isGaussianEvidenceAdmissionInput(entry.currentInput) ||
                !isCameraBinding(entry.cameraBinding) ||
                !isMaskArtifact(entry.stableMask) ||
                (entry.cachedArtifact !== undefined &&
                    !isGaussianEvidenceArtifact(entry.cachedArtifact))
            ) {
                return false;
            }
            const currentInput = entry.currentInput;
            return (
                bindingMatches(currentInput.requestBinding, requestBinding) &&
                currentInput.targetSplatId === targetSplatId &&
                currentInput.evidenceWorkingSet.evidenceWorkingSetToken ===
                    evidenceWorkingSet.evidenceWorkingSetToken &&
                currentInput.evidencePolicyDigest ===
                    productionEvidencePolicyDigest &&
                currentInput.rasterImplementationId ===
                    productionEvidenceRasterImplementationId &&
                currentInput.evidenceBackendKind === 'production-direct' &&
                currentInput.evidenceBackendId ===
                    productionDirectEvidenceBackendId &&
                currentInput.runtimeBuildId ===
                    productionEvidenceRuntimeBuildId &&
                currentInput.renderWorkingSet.targetSplatId === targetSplatId &&
                currentInput.renderWorkingSet.completeness === 'complete' &&
                areTargetDependencyTokensEqual(
                    currentInput.renderWorkingSet.dependencyToken,
                    requestBinding.dependencyToken
                ) &&
                stableIdsAreSubsetOf(
                    currentInput.renderWorkingSet.stableGaussianIds,
                    snapshotStableIds
                ) &&
                currentInput.view.cameraBindingDigest ===
                    cameraBindingDigest(entry.cameraBinding) &&
                currentInput.view.rgbDigest !== undefined &&
                currentInput.view.stableMaskDigest ===
                    entry.stableMask.digest &&
                (currentInput.view.participation === 'excluded' ||
                    isCurrentGaussianEvidenceArtifact(
                        entry.cachedArtifact,
                        currentInput
                    ))
            );
        }) &&
        new Set(value.views.map((entry) => entry.currentInput.view.viewId))
            .size === value.views.length
    );
};

export const isCandidateReLiftResponseForRequest = (
    value: unknown,
    request: CandidateReLiftRequest
): value is CandidateReLiftResponse => {
    if (
        !isRecord(value) ||
        (value.status !== 'complete' && value.status !== 'not-ready') ||
        value.liftAttemptId !== request.liftAttemptId ||
        value.targetSplatId !== request.targetSplatId ||
        !isAIRequestBinding(value.requestBinding) ||
        !bindingMatches(value.requestBinding, request.requestBinding) ||
        !Array.isArray(value.evidence) ||
        !isLiftReadinessArtifact(value.liftReadiness) ||
        (value.status === 'complete'
            ? !isProductionCandidateArtifact(value.candidate)
            : value.candidate !== undefined)
    ) {
        return false;
    }
    const included = request.views
        .filter((entry) => entry.currentInput.view.participation === 'included')
        .sort((left, right) =>
            compareUtf8(
                left.currentInput.view.viewId,
                right.currentInput.view.viewId
            )
        );
    const evidence = [...value.evidence].sort((left, right) => {
        if (!isRecord(left) || !isRecord(right)) {
            return 0;
        }
        return compareUtf8(String(left.viewId), String(right.viewId));
    });
    if (
        evidence.length !== included.length ||
        !evidence.every((entry, index) => {
            if (
                !isRecord(entry) ||
                entry.viewId !== included[index].currentInput.view.viewId ||
                typeof entry.reused !== 'boolean'
            ) {
                return false;
            }
            return isCurrentGaussianEvidenceArtifact(
                entry.artifact,
                included[index].currentInput
            );
        })
    ) {
        return false;
    }
    const readiness = value.liftReadiness;
    if (
        !bindingMatches(readiness.requestBinding, request.requestBinding) ||
        readiness.targetSplatId !== request.targetSplatId ||
        readiness.evidenceWorkingSetToken !==
            request.evidenceWorkingSet.evidenceWorkingSetToken ||
        readiness.generationState !== request.generationState ||
        readiness.source !== 'formal-evidence' ||
        (value.status === 'not-ready') !== (readiness.readiness === 'not-ready')
    ) {
        return false;
    }
    const evidenceByView = new Map(
        evidence.map((entry) => [
            (entry as CandidateReLiftEvidenceResult).viewId,
            (entry as CandidateReLiftEvidenceResult).artifact
        ])
    );
    const artifactSetDigest = sha256Digest(
        new TextEncoder().encode(
            JSON.stringify({
                artifacts: [...evidenceByView]
                    .map(([viewId, artifact]) => ({
                        artifactDigest: artifact.artifactDigest,
                        viewId
                    }))
                    .sort((left, right) =>
                        compareUtf8(left.viewId, right.viewId)
                    )
            })
        )
    );
    if (readiness.evidenceArtifactSetDigest !== artifactSetDigest) {
        return false;
    }
    if (value.status === 'not-ready') {
        return true;
    }
    const candidate = value.candidate as ProductionCandidateArtifact;
    const publicationBinding = candidate.publicationBinding;
    const expectedBinding = createProductionCandidatePublicationBinding({
        requestBinding: request.requestBinding,
        targetSplatId: request.targetSplatId,
        stableInputs: request.views.map((entry) => ({
            viewId: entry.currentInput.view.viewId,
            participation: entry.currentInput.view.participation,
            stableMaskDigest: entry.currentInput.view.stableMaskDigest ?? null,
            evidenceArtifactDigest:
                entry.currentInput.view.participation === 'included'
                    ? (evidenceByView.get(entry.currentInput.view.viewId)
                          ?.artifactDigest ?? null)
                    : null
        })),
        aggregationPolicyDigest: productionAggregationPolicyDigest,
        sourceEvidencePolicyDigest: productionEvidencePolicyDigest,
        evidenceWorkingSetToken:
            request.evidenceWorkingSet.evidenceWorkingSetToken,
        evidenceArtifactSetDigest: publicationBinding.evidenceArtifactSetDigest,
        productionIdentityDigest: request.productionIdentityDigest,
        evidenceBackendIdentity: {
            rasterImplementationId: productionEvidenceRasterImplementationId,
            evidenceBackendKind: 'production-direct',
            evidenceBackendId: productionDirectEvidenceBackendId,
            runtimeBuildId: productionEvidenceRuntimeBuildId
        }
    });
    return (
        bindingMatches(
            publicationBinding.requestBinding,
            expectedBinding.requestBinding
        ) &&
        publicationBinding.targetSplatId === expectedBinding.targetSplatId &&
        publicationBinding.stableInputSetDigest ===
            expectedBinding.stableInputSetDigest &&
        publicationBinding.aggregationPolicyDigest ===
            expectedBinding.aggregationPolicyDigest &&
        publicationBinding.sourceEvidencePolicyDigest ===
            expectedBinding.sourceEvidencePolicyDigest &&
        publicationBinding.evidenceWorkingSetToken ===
            expectedBinding.evidenceWorkingSetToken &&
        publicationBinding.evidenceArtifactSetDigest === artifactSetDigest &&
        publicationBinding.productionIdentityDigest ===
            request.productionIdentityDigest &&
        candidate.sourceAggregationResultDigest ===
            readiness.aggregationResultDigest &&
        stableIdsAreSubsetOf(
            candidate.candidate.selectedStableGaussianIds,
            request.classificationScopeStableGaussianIds
        ) &&
        stableIdsAreSubsetOf(
            candidate.uncertain.stableGaussianIds,
            request.classificationScopeStableGaussianIds
        ) &&
        JSON.stringify(publicationBinding.evidenceBackendIdentity) ===
            JSON.stringify(expectedBinding.evidenceBackendIdentity)
    );
};
