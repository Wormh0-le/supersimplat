import {
    sha256Digest,
    type PackedSceneSnapshot
} from '../scene-snapshot-binary';
import {
    aiSelectRgbRendererVersion,
    aiSelectRasterImplementationId,
    aiSelectRuntimeBuildId,
    isAnchorRgbArtifact,
    parsePngDimensions,
    decodePngBase64,
    type AnchorRgbArtifact
} from './anchor-render-service';
import {
    areCameraBindingsEqual,
    cameraBindingDigest,
    isCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding,
    type AIRequestBinding,
    type AITarget
} from './current-target-context';
import {
    isImageInstanceMaskRequest,
    isImageInstancePromptArtifact,
    type ImageInstanceMaskRequest,
    type ImageInstancePromptArtifact
} from './image-instance-mask';
import {
    isLocalKeyViewPlan,
    type LocalKeyViewPlan
} from './local-key-view-plan';
import { isMaskArtifact, type MaskArtifact } from './mask-annotation';
import {
    isTargetGeometryHintArtifact,
    type TargetGeometryHintArtifact
} from './target-geometry-hint';
import {
    aiSelectViewAssessmentPolicyVersion,
    isViewAssessmentResult,
    type ViewAssessmentResult
} from './view-assessment';

/**
 * The authoritative gsplat render of one planner-owned Generated View. It is
 * the Anchor render contract with a planner-owned `viewId`; `anchor-view`
 * stays reserved for the Anchor route.
 */
export interface AIViewRenderRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly snapshot: PackedSceneSnapshot;
    readonly cameraBinding: CameraBinding;
    readonly viewId: string;
    readonly renderAttemptId: string;
}

export interface AIViewRenderResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly renderAttemptId: string;
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
    readonly rgb: AnchorRgbArtifact;
    readonly rgbRendererVersion: typeof aiSelectRgbRendererVersion;
    readonly rendererId: 'gsplat';
    readonly rasterImplementationId: typeof aiSelectRasterImplementationId;
    readonly runtimeBuildId: typeof aiSelectRuntimeBuildId;
}

export interface AISelectViewRenderer {
    renderView(request: AIViewRenderRequest): Promise<AIViewRenderResponse>;
    // Snapshot residency is Companion-local and disposable; see the Anchor.
    releaseSceneSnapshot?(request: AIViewRenderRequest): Promise<void>;
}

/**
 * Route B creates one compact SAM 3 Image prompt from the exact local View
 * plan, target geometry hint, CameraBinding, and authoritative RGB. It is
 * deliberately independent from inference, review, and Stable publication.
 */
export const aiSelectImageInstancePromptSynthesisPolicyVersion =
    'image-instance-prompt-synthesis/v1';

/**
 * Canonical digest shared with the Companion's sorted policy descriptor.
 * Keep fields in lexical order: JSON.stringify then matches Python's compact
 * `sort_keys=True` digest encoding exactly.
 */
export const aiSelectImageInstancePromptSynthesisPolicyDigest = sha256Digest(
    new TextEncoder().encode(
        JSON.stringify({
            coordinateConvention: 'authoritative-pixel-xyxy/v1',
            maxNegativePoints: 2,
            maxPositivePoints: 3,
            negativePointPolicy: 'none/v1',
            pointSelection: 'farthest-point-projection-samples/v1',
            positiveInstanceBoxes: 1,
            version: aiSelectImageInstancePromptSynthesisPolicyVersion
        })
    )
);

export interface GeneratedViewPromptSynthesisRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly viewId: string;
    readonly viewCameraBinding: CameraBinding;
    readonly viewCameraBindingDigest: string;
    readonly rgb: AnchorRgbArtifact;
    readonly targetGeometryHint: TargetGeometryHintArtifact;
    readonly localKeyViewPlan: LocalKeyViewPlan;
    readonly adapterCapabilityDigest: string;
    readonly modelManifestDigest: string;
    readonly runtimeDigest: string;
    readonly companionInstanceId: string;
    readonly promptSynthesisAttemptId: string;
    readonly promptSynthesisPolicyVersion: typeof aiSelectImageInstancePromptSynthesisPolicyVersion;
}

export interface GeneratedViewPromptSynthesisReadyResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly viewId: string;
    readonly viewCameraBindingDigest: string;
    readonly rgbDigest: string;
    readonly targetGeometryHintDigest: string;
    readonly localKeyViewPlanDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly modelManifestDigest: string;
    readonly runtimeDigest: string;
    readonly companionInstanceId: string;
    readonly promptSynthesisAttemptId: string;
    readonly promptSynthesisPolicyVersion: typeof aiSelectImageInstancePromptSynthesisPolicyVersion;
    readonly status: 'ready';
    /** Bounded projection/clipping diagnostics; never Gaussian ownership. */
    readonly diagnostics: readonly string[];
    readonly prompt: ImageInstancePromptArtifact;
}

export interface GeneratedViewPromptSynthesisLimitedResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly viewId: string;
    readonly viewCameraBindingDigest: string;
    readonly rgbDigest: string;
    readonly targetGeometryHintDigest: string;
    readonly localKeyViewPlanDigest: string;
    readonly adapterCapabilityDigest: string;
    readonly modelManifestDigest: string;
    readonly runtimeDigest: string;
    readonly companionInstanceId: string;
    readonly promptSynthesisAttemptId: string;
    readonly promptSynthesisPolicyVersion: typeof aiSelectImageInstancePromptSynthesisPolicyVersion;
    readonly status: 'limited';
    readonly diagnostics: readonly string[];
}

export type GeneratedViewPromptSynthesisResponse =
    | GeneratedViewPromptSynthesisReadyResponse
    | GeneratedViewPromptSynthesisLimitedResponse;

export interface AISelectGeneratedViewPromptSynthesizer {
    synthesizeGeneratedViewPrompt(
        request: GeneratedViewPromptSynthesisRequest
    ): Promise<GeneratedViewPromptSynthesisResponse>;
}

/**
 * Mask Review consumes exactly one inference-produced mask. It does not know
 * about propagation, Stable publication, Participation, Evidence, or Lift.
 */
export interface ImageInstanceMaskReviewRequest {
    readonly requestBinding: AIRequestBinding;
    readonly target: AITarget;
    readonly viewId: string;
    readonly rgb: AnchorRgbArtifact;
    readonly prompt: ImageInstancePromptArtifact;
    readonly inferenceResultDigest: string;
    readonly chosenMask: MaskArtifact;
    readonly reviewAttemptId: string;
    readonly reviewPolicyVersion: typeof aiSelectViewAssessmentPolicyVersion;
}

export interface ImageInstanceMaskReviewResponse {
    readonly requestBinding: AIRequestBinding;
    readonly targetSplatId: string;
    readonly viewId: string;
    readonly rgbDigest: string;
    readonly promptArtifactDigest: string;
    readonly inferenceResultDigest: string;
    readonly chosenMaskDigest: string;
    readonly reviewAttemptId: string;
    readonly reviewPolicyVersion: typeof aiSelectViewAssessmentPolicyVersion;
    readonly assessment: ViewAssessmentResult;
}

export interface AISelectImageInstanceMaskReviewProvider {
    reviewImageInstanceMask(
        request: ImageInstanceMaskReviewRequest
    ): Promise<ImageInstanceMaskReviewResponse>;
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

/**
 * Route B artifacts are closed schemas. In particular, a cached
 * `generated-view-mask/v1` propagation payload must not be accepted merely
 * because it happens to contain fields that resemble the new response.
 */
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

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.trim().length > 0;
};

const isDigest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);
};

const isTarget = (value: unknown): value is AITarget => {
    return isRecord(value) && isNonEmptyString(value.splatId);
};

const isStringArray = (value: unknown): value is readonly string[] => {
    return (
        Array.isArray(value) && value.every((entry) => isNonEmptyString(entry))
    );
};

const actualPngDimensions = (
    base64: string
): { readonly width: number; readonly height: number } | null => {
    try {
        return parsePngDimensions(decodePngBase64(base64));
    } catch {
        return null;
    }
};

const localPlanContainsBoundView = (
    plan: LocalKeyViewPlan,
    viewId: string,
    cameraBinding: CameraBinding
): boolean => {
    return plan.orderedViews.some(
        (view) =>
            view.viewId === viewId &&
            areCameraBindingsEqual(view.cameraBinding, cameraBinding)
    );
};

/**
 * Generated View Route B has one Positive Instance Box, one to three positive
 * pixel points, at most two negative pixel points, and never transports a
 * previous-logits refinement reference. Like interactive Anchor requests,
 * Route B is pinned to single-result inference.
 */
const isRouteBGeneratedPrompt = (
    value: unknown
): value is ImageInstancePromptArtifact => {
    return (
        isImageInstancePromptArtifact(value) &&
        value.viewId !== 'anchor-view' &&
        value.multimaskOutput === false &&
        value.previousLogitsRefDigest === undefined &&
        isDigest(value.targetGeometryHintDigest) &&
        isDigest(value.localKeyViewPlanDigest) &&
        value.promptSynthesisPolicyDigest ===
            aiSelectImageInstancePromptSynthesisPolicyDigest &&
        value.positiveBox !== undefined &&
        value.positivePoints.length >= 1 &&
        value.positivePoints.length <= 3 &&
        value.negativePoints.length <= 2
    );
};

/**
 * Route B narrows the reusable 04C request to a Companion-produced,
 * geometry-guided Prompt. The generic image-instance contract remains useful
 * for Anchor acquisition, but cannot attach to this Generated View endpoint.
 */
export const isGeneratedViewImageInstanceMaskRequest = (
    value: unknown
): value is ImageInstanceMaskRequest => {
    return (
        isImageInstanceMaskRequest(value) &&
        value.identity.viewId !== 'anchor-view' &&
        isRouteBGeneratedPrompt(value.prompt) &&
        value.prompt.targetContextId === value.identity.targetContextId &&
        value.prompt.contextRevision === value.identity.contextRevision &&
        value.prompt.viewId === value.identity.viewId &&
        value.prompt.rgbDigest === value.identity.rgbDigest &&
        value.prompt.artifactDigest === value.identity.promptArtifactDigest
    );
};

export const isGeneratedViewPromptSynthesisRequest = (
    value: unknown
): value is GeneratedViewPromptSynthesisRequest => {
    if (
        !isRecord(value) ||
        !hasExactKeys(value, [
            'requestBinding',
            'target',
            'viewId',
            'viewCameraBinding',
            'viewCameraBindingDigest',
            'rgb',
            'targetGeometryHint',
            'localKeyViewPlan',
            'adapterCapabilityDigest',
            'modelManifestDigest',
            'runtimeDigest',
            'companionInstanceId',
            'promptSynthesisAttemptId',
            'promptSynthesisPolicyVersion'
        ]) ||
        !isAIRequestBinding(value.requestBinding) ||
        !isTarget(value.target) ||
        value.requestBinding.dependencyToken.splatId !== value.target.splatId ||
        !isNonEmptyString(value.viewId) ||
        value.viewId === 'anchor-view' ||
        !isCameraBinding(value.viewCameraBinding) ||
        !isDigest(value.viewCameraBindingDigest) ||
        cameraBindingDigest(value.viewCameraBinding) !==
            value.viewCameraBindingDigest ||
        !isAnchorRgbArtifact(value.rgb) ||
        value.rgb.width !== value.viewCameraBinding.projection.width ||
        value.rgb.height !== value.viewCameraBinding.projection.height ||
        !isTargetGeometryHintArtifact(value.targetGeometryHint) ||
        !isLocalKeyViewPlan(value.localKeyViewPlan) ||
        value.targetGeometryHint.targetContextId !==
            value.requestBinding.targetContextId ||
        value.localKeyViewPlan.targetContextId !==
            value.requestBinding.targetContextId ||
        value.localKeyViewPlan.targetGeometryHintDigest !==
            value.targetGeometryHint.artifactDigest ||
        !localPlanContainsBoundView(
            value.localKeyViewPlan,
            value.viewId,
            value.viewCameraBinding
        ) ||
        !isDigest(value.adapterCapabilityDigest) ||
        !isNonEmptyString(value.modelManifestDigest) ||
        !isDigest(value.runtimeDigest) ||
        !isNonEmptyString(value.companionInstanceId) ||
        !isNonEmptyString(value.promptSynthesisAttemptId) ||
        value.promptSynthesisPolicyVersion !==
            aiSelectImageInstancePromptSynthesisPolicyVersion
    ) {
        return false;
    }
    return actualPngDimensions(value.rgb.pngBase64) !== null;
};

const hasPromptSynthesisResponseBindings = (
    response: Omit<
        GeneratedViewPromptSynthesisResponse,
        'status' | 'diagnostics'
    > & {
        readonly status: 'ready' | 'limited';
        readonly diagnostics: readonly string[];
    }
): boolean => {
    return (
        isAIRequestBinding(response.requestBinding) &&
        isNonEmptyString(response.targetSplatId) &&
        isNonEmptyString(response.viewId) &&
        response.viewId !== 'anchor-view' &&
        isDigest(response.viewCameraBindingDigest) &&
        isDigest(response.rgbDigest) &&
        isDigest(response.targetGeometryHintDigest) &&
        isDigest(response.localKeyViewPlanDigest) &&
        isDigest(response.adapterCapabilityDigest) &&
        isNonEmptyString(response.modelManifestDigest) &&
        isDigest(response.runtimeDigest) &&
        isNonEmptyString(response.companionInstanceId) &&
        isNonEmptyString(response.promptSynthesisAttemptId) &&
        response.promptSynthesisPolicyVersion ===
            aiSelectImageInstancePromptSynthesisPolicyVersion &&
        isStringArray(response.diagnostics)
    );
};

export const isGeneratedViewPromptSynthesisResponse = (
    value: unknown
): value is GeneratedViewPromptSynthesisResponse => {
    if (!isRecord(value) || !isStringArray(value.diagnostics)) {
        return false;
    }
    if (value.status === 'ready') {
        return (
            hasExactKeys(value, [
                'requestBinding',
                'targetSplatId',
                'viewId',
                'viewCameraBindingDigest',
                'rgbDigest',
                'targetGeometryHintDigest',
                'localKeyViewPlanDigest',
                'adapterCapabilityDigest',
                'modelManifestDigest',
                'runtimeDigest',
                'companionInstanceId',
                'promptSynthesisAttemptId',
                'promptSynthesisPolicyVersion',
                'status',
                'diagnostics',
                'prompt'
            ]) &&
            hasPromptSynthesisResponseBindings(
                value as unknown as GeneratedViewPromptSynthesisReadyResponse
            ) &&
            isRouteBGeneratedPrompt(value.prompt)
        );
    }
    return (
        value.status === 'limited' &&
        value.diagnostics.length > 0 &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'viewId',
            'viewCameraBindingDigest',
            'rgbDigest',
            'targetGeometryHintDigest',
            'localKeyViewPlanDigest',
            'adapterCapabilityDigest',
            'modelManifestDigest',
            'runtimeDigest',
            'companionInstanceId',
            'promptSynthesisAttemptId',
            'promptSynthesisPolicyVersion',
            'status',
            'diagnostics'
        ]) &&
        hasPromptSynthesisResponseBindings(
            value as unknown as GeneratedViewPromptSynthesisLimitedResponse
        ) &&
        !Object.hasOwn(value, 'prompt')
    );
};

export const generatedViewPromptSynthesisResponseMatchesRequest = (
    response: GeneratedViewPromptSynthesisResponse,
    request: GeneratedViewPromptSynthesisRequest
): boolean => {
    if (
        !isGeneratedViewPromptSynthesisResponse(response) ||
        !isGeneratedViewPromptSynthesisRequest(request) ||
        response.requestBinding.targetContextId !==
            request.requestBinding.targetContextId ||
        response.requestBinding.contextRevision !==
            request.requestBinding.contextRevision ||
        !areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) ||
        response.targetSplatId !== request.target.splatId ||
        response.viewId !== request.viewId ||
        response.viewCameraBindingDigest !== request.viewCameraBindingDigest ||
        response.rgbDigest !== request.rgb.digest ||
        response.targetGeometryHintDigest !==
            request.targetGeometryHint.artifactDigest ||
        response.localKeyViewPlanDigest !==
            request.localKeyViewPlan.artifactDigest ||
        response.adapterCapabilityDigest !== request.adapterCapabilityDigest ||
        response.modelManifestDigest !== request.modelManifestDigest ||
        response.runtimeDigest !== request.runtimeDigest ||
        response.companionInstanceId !== request.companionInstanceId ||
        response.promptSynthesisAttemptId !==
            request.promptSynthesisAttemptId ||
        response.promptSynthesisPolicyVersion !==
            request.promptSynthesisPolicyVersion
    ) {
        return false;
    }
    if (response.status === 'limited') {
        return true;
    }
    const prompt = response.prompt;
    return (
        prompt.targetContextId === request.requestBinding.targetContextId &&
        prompt.contextRevision === request.requestBinding.contextRevision &&
        prompt.viewId === request.viewId &&
        prompt.rgbDigest === request.rgb.digest &&
        prompt.cameraBindingDigest === request.viewCameraBindingDigest &&
        prompt.targetGeometryHintDigest ===
            request.targetGeometryHint.artifactDigest &&
        prompt.localKeyViewPlanDigest ===
            request.localKeyViewPlan.artifactDigest &&
        prompt.adapterCapabilityDigest === request.adapterCapabilityDigest &&
        prompt.promptSynthesisPolicyDigest !== undefined
    );
};

export const isImageInstanceMaskReviewRequest = (
    value: unknown
): value is ImageInstanceMaskReviewRequest => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'target',
            'viewId',
            'rgb',
            'prompt',
            'inferenceResultDigest',
            'chosenMask',
            'reviewAttemptId',
            'reviewPolicyVersion'
        ]) &&
        isAIRequestBinding(value.requestBinding) &&
        isTarget(value.target) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isAnchorRgbArtifact(value.rgb) &&
        isRouteBGeneratedPrompt(value.prompt) &&
        value.prompt.targetContextId === value.requestBinding.targetContextId &&
        value.prompt.contextRevision === value.requestBinding.contextRevision &&
        value.prompt.viewId === value.viewId &&
        value.prompt.rgbDigest === value.rgb.digest &&
        isDigest(value.inferenceResultDigest) &&
        isMaskArtifact(value.chosenMask) &&
        value.chosenMask.width === value.rgb.width &&
        value.chosenMask.height === value.rgb.height &&
        isNonEmptyString(value.reviewAttemptId) &&
        value.reviewPolicyVersion === aiSelectViewAssessmentPolicyVersion
    );
};

export const isImageInstanceMaskReviewResponse = (
    value: unknown
): value is ImageInstanceMaskReviewResponse => {
    return (
        isRecord(value) &&
        hasExactKeys(value, [
            'requestBinding',
            'targetSplatId',
            'viewId',
            'rgbDigest',
            'promptArtifactDigest',
            'inferenceResultDigest',
            'chosenMaskDigest',
            'reviewAttemptId',
            'reviewPolicyVersion',
            'assessment'
        ]) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isDigest(value.rgbDigest) &&
        isDigest(value.promptArtifactDigest) &&
        isDigest(value.inferenceResultDigest) &&
        isDigest(value.chosenMaskDigest) &&
        isNonEmptyString(value.reviewAttemptId) &&
        value.reviewPolicyVersion === aiSelectViewAssessmentPolicyVersion &&
        isViewAssessmentResult(value.assessment)
    );
};

export const imageInstanceMaskReviewResponseMatchesRequest = (
    response: ImageInstanceMaskReviewResponse,
    request: ImageInstanceMaskReviewRequest
): boolean => {
    return (
        isImageInstanceMaskReviewResponse(response) &&
        isImageInstanceMaskReviewRequest(request) &&
        response.requestBinding.targetContextId ===
            request.requestBinding.targetContextId &&
        response.requestBinding.contextRevision ===
            request.requestBinding.contextRevision &&
        areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) &&
        response.targetSplatId === request.target.splatId &&
        response.viewId === request.viewId &&
        response.rgbDigest === request.rgb.digest &&
        response.promptArtifactDigest === request.prompt.artifactDigest &&
        response.inferenceResultDigest === request.inferenceResultDigest &&
        response.chosenMaskDigest === request.chosenMask.digest &&
        response.reviewAttemptId === request.reviewAttemptId &&
        response.reviewPolicyVersion === request.reviewPolicyVersion &&
        response.assessment.inputIdentity.rgbDigest === request.rgb.digest &&
        response.assessment.inputIdentity.stableMaskDigest ===
            request.chosenMask.digest &&
        response.assessment.inputIdentity.assessmentPolicyVersion ===
            request.reviewPolicyVersion
    );
};

export const isAIViewRenderRequest = (
    value: unknown
): value is AIViewRenderRequest => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isTarget(value.target) &&
        value.requestBinding.dependencyToken.splatId === value.target.splatId &&
        isRecord(value.snapshot) &&
        isNonEmptyString(value.snapshot.sceneId) &&
        isNonEmptyString(value.snapshot.sceneVersion) &&
        value.snapshot.sceneId === value.target.splatId &&
        isCameraBinding(value.cameraBinding) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isNonEmptyString(value.renderAttemptId)
    );
};

export const isAIViewRenderResponse = (
    value: unknown
): value is AIViewRenderResponse => {
    return (
        isRecord(value) &&
        isAIRequestBinding(value.requestBinding) &&
        isNonEmptyString(value.targetSplatId) &&
        isNonEmptyString(value.sceneId) &&
        isNonEmptyString(value.sceneVersion) &&
        isNonEmptyString(value.renderConfigVersion) &&
        isNonEmptyString(value.renderAttemptId) &&
        isNonEmptyString(value.viewId) &&
        value.viewId !== 'anchor-view' &&
        isCameraBinding(value.cameraBinding) &&
        isAnchorRgbArtifact(value.rgb) &&
        value.rgbRendererVersion === aiSelectRgbRendererVersion &&
        value.rendererId === 'gsplat' &&
        value.rasterImplementationId === aiSelectRasterImplementationId &&
        value.runtimeBuildId === aiSelectRuntimeBuildId
    );
};

/**
 * Fail-closed render matching: every identity field must echo the request and
 * the immutable PNG envelope must match its claimed dimensions and the bound
 * CameraBinding projection.
 */
export const viewRenderResponseMatchesRequest = (
    response: AIViewRenderResponse,
    request: AIViewRenderRequest
): boolean => {
    const actualDimensions = actualPngDimensions(response.rgb.pngBase64);
    return (
        actualDimensions !== null &&
        response.requestBinding.targetContextId ===
            request.requestBinding.targetContextId &&
        response.requestBinding.contextRevision ===
            request.requestBinding.contextRevision &&
        areTargetDependencyTokensEqual(
            response.requestBinding.dependencyToken,
            request.requestBinding.dependencyToken
        ) &&
        response.targetSplatId === request.target.splatId &&
        response.sceneId === request.snapshot.sceneId &&
        response.sceneVersion === request.snapshot.sceneVersion &&
        response.renderConfigVersion ===
            request.snapshot.renderConfiguration.version &&
        response.renderAttemptId === request.renderAttemptId &&
        response.viewId === request.viewId &&
        areCameraBindingsEqual(response.cameraBinding, request.cameraBinding) &&
        actualDimensions.width === response.rgb.width &&
        actualDimensions.height === response.rgb.height &&
        response.rgb.width === request.cameraBinding.projection.width &&
        response.rgb.height === request.cameraBinding.projection.height
    );
};
