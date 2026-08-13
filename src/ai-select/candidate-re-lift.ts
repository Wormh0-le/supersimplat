import {
    cameraBindingDigest,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    createCandidatePublicationBinding,
    isReferenceCandidateArtifact,
    type ReferenceCandidateArtifact
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
import { isMaskArtifact, type MaskArtifact } from './mask-annotation';
import {
    isLiftReadinessArtifact,
    type LiftReadinessArtifact,
    type LiftReadinessGenerationState
} from './lift-readiness';
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
    'gsplat-reference-rgb/v1';
export const referenceContributorEvidenceBackendId =
    'complete-contributor/reference-v1';
export const referenceEvidenceRuntimeBuildId =
    'sha256:a04a3840702bca8d86365dc44c8a693344e54fb09db8a2c2131a4ed711717e40';

export interface CandidateReLiftViewInput {
    readonly currentInput: GaussianEvidenceAdmissionInput;
    readonly cameraBinding: CameraBinding;
    readonly stableMask: MaskArtifact;
    readonly cachedArtifact?: GaussianEvidenceArtifact;
}

export interface CandidateReLiftRequest {
    readonly liftAttemptId: string;
    readonly snapshot: PackedSceneSnapshot;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly classificationUniverseStableGaussianIds: readonly number[];
    readonly classificationScopeStableGaussianIds: readonly number[];
    readonly evidenceWorkingSet: EvidenceWorkingSet;
    readonly generationState: LiftReadinessGenerationState;
    readonly views: readonly CandidateReLiftViewInput[];
}

export interface CandidateReLiftEvidenceResult {
    readonly viewId: string;
    readonly reused: boolean;
    readonly artifact: GaussianEvidenceArtifact;
}

export interface CandidateReLiftResponse {
    readonly status: 'complete';
    readonly liftAttemptId: string;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly evidence: readonly CandidateReLiftEvidenceResult[];
    readonly readiness: LiftReadinessArtifact;
    readonly candidate: ReferenceCandidateArtifact;
}

export interface AISelectCandidateReLiftProvider {
    produceCandidateReLift(
        request: CandidateReLiftRequest
    ): Promise<CandidateReLiftResponse>;
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const bindingMatches = (
    left: AIRequestBinding,
    right: AIRequestBinding
): boolean =>
    left.targetContextId === right.targetContextId &&
    left.contextRevision === right.contextRevision &&
    areTargetDependencyTokensEqual(
        left.dependencyToken,
        right.dependencyToken
    );

export const isCandidateReLiftRequest = (
    value: unknown
): value is CandidateReLiftRequest => {
    if (
        !isRecord(value) ||
        typeof value.liftAttemptId !== 'string' ||
        value.liftAttemptId.length === 0 ||
        !isPackedSceneSnapshot(value.snapshot) ||
        !isAIRequestBinding(value.requestBinding) ||
        typeof value.targetSplatId !== 'string' ||
        !Array.isArray(value.classificationUniverseStableGaussianIds) ||
        !Array.isArray(value.classificationScopeStableGaussianIds) ||
        !isEvidenceWorkingSet(value.evidenceWorkingSet) ||
        !['active', 'stopped', 'complete', 'unavailable'].includes(
            value.generationState as string
        ) ||
        !Array.isArray(value.views) ||
        value.views.length === 0
    ) {
        return false;
    }
    const snapshot = value.snapshot;
    const requestBinding = value.requestBinding;
    const targetSplatId = value.targetSplatId;
    const evidenceWorkingSet = value.evidenceWorkingSet;
    return (
        requestBinding.dependencyToken.splatId === targetSplatId &&
        evidenceWorkingSet.targetSplatId === targetSplatId &&
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
                    referenceEvidencePolicyDigest &&
                currentInput.rasterImplementationId ===
                    referenceEvidenceRasterImplementationId &&
                currentInput.evidenceBackendKind ===
                    'reference-contributor' &&
                currentInput.evidenceBackendId ===
                    referenceContributorEvidenceBackendId &&
                currentInput.runtimeBuildId ===
                    referenceEvidenceRuntimeBuildId &&
                currentInput.renderWorkingSet.renderWorkingSetToken ===
                    snapshot.contentDigest &&
                currentInput.view.cameraBindingDigest ===
                    cameraBindingDigest(entry.cameraBinding) &&
                currentInput.view.rgbDigest !== undefined &&
                currentInput.view.stableMaskDigest ===
                    entry.stableMask.digest
            );
        })
    );
};

export const isCandidateReLiftResponseForRequest = (
    value: unknown,
    request: CandidateReLiftRequest
): value is CandidateReLiftResponse => {
    if (
        !isRecord(value) ||
        value.status !== 'complete' ||
        value.liftAttemptId !== request.liftAttemptId ||
        value.targetSplatId !== request.targetSplatId ||
        !isAIRequestBinding(value.requestBinding) ||
        !bindingMatches(
            value.requestBinding,
            request.requestBinding
        ) ||
        !Array.isArray(value.evidence) ||
        !isLiftReadinessArtifact(value.readiness) ||
        !isReferenceCandidateArtifact(value.candidate)
    ) {
        return false;
    }
    const included = request.views
        .filter(
            (entry) => entry.currentInput.view.participation === 'included'
        )
        .sort((left, right) =>
            left.currentInput.view.viewId.localeCompare(
                right.currentInput.view.viewId
            )
        );
    const evidence = [...value.evidence].sort((left, right) => {
        if (!isRecord(left) || !isRecord(right)) {
            return 0;
        }
        return String(left.viewId).localeCompare(String(right.viewId));
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
    const candidate = value.candidate;
    const readiness = value.readiness;
    const publicationBinding = candidate.publicationBinding;
    const evidenceByView = new Map(
        evidence.map((entry) => [
            (entry as CandidateReLiftEvidenceResult).viewId,
            (entry as CandidateReLiftEvidenceResult).artifact
        ])
    );
    const expectedBinding = createCandidatePublicationBinding({
        requestBinding: request.requestBinding,
        targetSplatId: request.targetSplatId,
        stableInputs: request.views.map((entry) => ({
            viewId: entry.currentInput.view.viewId,
            participation: entry.currentInput.view.participation,
            stableMaskDigest:
                entry.currentInput.view.stableMaskDigest ?? null,
            evidenceArtifactDigest:
                entry.currentInput.view.participation === 'included'
                    ? (evidenceByView.get(entry.currentInput.view.viewId)
                          ?.artifactDigest ?? null)
                    : null
        })),
        aggregationPolicyDigest: referenceAggregationPolicyDigest,
        sourceEvidencePolicyDigest: referenceEvidencePolicyDigest,
        evidenceWorkingSetToken:
            request.evidenceWorkingSet.evidenceWorkingSetToken,
        evidenceArtifactSetDigest:
            publicationBinding.evidenceArtifactSetDigest,
        referenceBackendIdentity: {
            rasterImplementationId:
                referenceEvidenceRasterImplementationId,
            evidenceBackendKind: 'reference-contributor',
            evidenceBackendId: referenceContributorEvidenceBackendId,
            runtimeBuildId: referenceEvidenceRuntimeBuildId
        }
    });
    const artifactSetDigest = sha256Digest(
        new TextEncoder().encode(
            JSON.stringify({
                artifacts: [...evidenceByView]
                    .map(([viewId, artifact]) => ({
                        artifactDigest: artifact.artifactDigest,
                        viewId
                    }))
                    .sort((left, right) =>
                        left.viewId.localeCompare(right.viewId)
                    )
            })
        )
    );
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
        publicationBinding.evidenceArtifactSetDigest ===
            readiness.evidenceArtifactSetDigest &&
        publicationBinding.evidenceArtifactSetDigest ===
            artifactSetDigest &&
        readiness.requestBinding.targetContextId ===
            request.requestBinding.targetContextId &&
        readiness.requestBinding.contextRevision ===
            request.requestBinding.contextRevision &&
        readiness.targetSplatId === request.targetSplatId &&
        readiness.evidenceWorkingSetToken ===
            request.evidenceWorkingSet.evidenceWorkingSetToken &&
        readiness.evidenceArtifactSetDigest ===
            publicationBinding.evidenceArtifactSetDigest &&
        readiness.aggregationResultDigest ===
            candidate.sourceAggregationResultDigest &&
        readiness.generationState === request.generationState &&
        JSON.stringify(publicationBinding.referenceBackendIdentity) ===
            JSON.stringify(expectedBinding.referenceBackendIdentity)
    );
};
