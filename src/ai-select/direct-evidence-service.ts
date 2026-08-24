import {
    cameraBindingDigest,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding
} from './current-target-context';
import {
    isCurrentGaussianEvidenceArtifact,
    isGaussianEvidenceAdmissionInput,
    type GaussianEvidenceAdmissionInput,
    type GaussianEvidenceArtifact
} from './gaussian-evidence-contract';
import {
    decodeMaskArtifact,
    isMaskArtifact,
    type MaskArtifact
} from './mask-annotation';
import {
    isPackedSceneSnapshot,
    type PackedSceneSnapshot
} from '../scene-snapshot-binary';

export const directEvidenceRasterImplementationId =
    'supersimplat-gsplat-direct-evidence/v1';
export const directEvidenceBackendId = 'global-atomic/direct-v1';
export const directEvidenceRuntimeBuildId =
    'sha256:91057a5e4da33e0a4c3afe1cace80d23e0595c411cb5a6100b8c72ce42cdbaa1';

export interface DirectEvidenceRequest {
    /** Execution identity: replay is idempotent, new intent mints a new ID. */
    readonly evidenceAttemptId: string;
    readonly snapshot: PackedSceneSnapshot;
    readonly currentInput: GaussianEvidenceAdmissionInput;
    readonly cameraBinding: CameraBinding;
    readonly stableMask: MaskArtifact;
    readonly cachedArtifact?: GaussianEvidenceArtifact;
}

export interface DirectEvidenceTelemetry {
    readonly evidenceBufferBytes: number;
    readonly pixelWeightBufferBytes: number;
    readonly boundaryBufferBytes: number;
    readonly peakVramBytes: number;
}

export interface DirectEvidenceResponse {
    readonly status: 'complete';
    readonly evidenceAttemptId: string;
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly viewId: string;
    readonly reused: boolean;
    readonly artifact: GaussianEvidenceArtifact;
    readonly telemetry?: DirectEvidenceTelemetry;
}

export interface AISelectDirectEvidenceProvider {
    produceDirectEvidence(
        request: DirectEvidenceRequest
    ): Promise<DirectEvidenceResponse>;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const equalBinding = (left: AIRequestBinding, right: AIRequestBinding) =>
    left.targetContextId === right.targetContextId &&
    left.contextRevision === right.contextRevision &&
    areTargetDependencyTokensEqual(left.dependencyToken, right.dependencyToken);

const targetStableIds = (snapshot: PackedSceneSnapshot): readonly number[] => {
    const scope = snapshot.authoritativeRenderScope;
    if (!isRecord(scope) || !Array.isArray(scope.entries)) {
        return [];
    }
    const entry = scope.entries.find(
        (candidate) => isRecord(candidate) && candidate.role === 'target'
    );
    if (
        !isRecord(entry) ||
        !Number.isSafeInteger(entry.rowOffset) ||
        (entry.rowOffset as number) < 0 ||
        !Number.isSafeInteger(entry.rowCount) ||
        (entry.rowCount as number) <= 0 ||
        (entry.rowOffset as number) + (entry.rowCount as number) >
            snapshot.stableIds.length
    ) {
        return [];
    }
    return [...snapshot.stableIds]
        .slice(
            entry.rowOffset as number,
            (entry.rowOffset as number) + (entry.rowCount as number)
        )
        .sort((left, right) => left - right);
};

const maskDigestMatchesBytes = (artifact: MaskArtifact): boolean => {
    try {
        decodeMaskArtifact(artifact);
        return true;
    } catch {
        return false;
    }
};

const isSubset = (subset: readonly number[], superset: readonly number[]) => {
    const accepted = new Set(superset);
    return subset.every((value) => accepted.has(value));
};

export const isDirectEvidenceRequest = (
    value: unknown
): value is DirectEvidenceRequest => {
    if (
        !isRecord(value) ||
        typeof value.evidenceAttemptId !== 'string' ||
        value.evidenceAttemptId.trim().length === 0 ||
        !isPackedSceneSnapshot(value.snapshot) ||
        !isGaussianEvidenceAdmissionInput(value.currentInput) ||
        !isCameraBinding(value.cameraBinding) ||
        !isMaskArtifact(value.stableMask) ||
        !maskDigestMatchesBytes(value.stableMask) ||
        !(value.snapshot.stableIds instanceof Uint32Array) ||
        !isRecord(value.snapshot.renderConfiguration) ||
        typeof value.snapshot.renderConfiguration.version !== 'string' ||
        (value.cachedArtifact !== undefined &&
            !isCurrentGaussianEvidenceArtifact(
                value.cachedArtifact,
                value.currentInput
            ))
    ) {
        return false;
    }
    const request = value as unknown as DirectEvidenceRequest;
    const input = request.currentInput;
    const renderIds = [...request.snapshot.stableIds].sort(
        (left, right) => left - right
    );
    const targetIds = targetStableIds(request.snapshot);
    return (
        request.snapshot.sceneId === input.targetSplatId &&
        request.snapshot.authoritativeRenderScope?.targetSplatId ===
            input.targetSplatId &&
        input.renderWorkingSet.completeness === 'complete' &&
        isSubset(input.renderWorkingSet.stableGaussianIds, renderIds) &&
        targetIds.length > 0 &&
        isSubset(input.evidenceWorkingSet.stableGaussianIds, targetIds) &&
        input.rasterImplementationId === directEvidenceRasterImplementationId &&
        input.evidenceBackendKind === 'production-direct' &&
        input.evidenceBackendId === directEvidenceBackendId &&
        input.runtimeBuildId === directEvidenceRuntimeBuildId &&
        input.view.participation === 'included' &&
        input.view.cameraBindingDigest ===
            cameraBindingDigest(request.cameraBinding) &&
        input.view.rgbDigest !== undefined &&
        input.view.stableMaskDigest === request.stableMask.digest &&
        request.stableMask.width === request.cameraBinding.projection.width &&
        request.stableMask.height === request.cameraBinding.projection.height
    );
};

const isTelemetry = (value: unknown): value is DirectEvidenceTelemetry =>
    isRecord(value) &&
    [
        value.evidenceBufferBytes,
        value.pixelWeightBufferBytes,
        value.boundaryBufferBytes,
        value.peakVramBytes
    ].every((item) => Number.isSafeInteger(item) && (item as number) >= 0);

export const isDirectEvidenceResponseForRequest = (
    value: unknown,
    request: DirectEvidenceRequest
): value is DirectEvidenceResponse =>
    isRecord(value) &&
    value.status === 'complete' &&
    value.evidenceAttemptId === request.evidenceAttemptId &&
    isAIRequestBinding(value.requestBinding) &&
    equalBinding(value.requestBinding, request.currentInput.requestBinding) &&
    value.targetSplatId === request.currentInput.targetSplatId &&
    value.viewId === request.currentInput.view.viewId &&
    typeof value.reused === 'boolean' &&
    isCurrentGaussianEvidenceArtifact(value.artifact, request.currentInput) &&
    (value.telemetry === undefined || isTelemetry(value.telemetry));
