import type { AIViewParticipation, AIViewSource } from './ai-view';
import { sha256Digest } from '../scene-snapshot-binary';
import type {
    AISelectAnchorConfirmationController,
    AISelectAnchorConfirmationState,
    ConfirmedAnchor
} from './anchor-confirmation';
import type { AISelectAnchorController } from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    cameraBindingDigest,
    copyCameraBinding,
    type CameraBinding
} from './camera-binding';
import {
    copyDependencyToken,
    type AIRequestBinding
} from './current-target-context';
import {
    AISelectDirtyStateTracker,
    type AISelectDirtyState
} from './dirty-state';
import {
    aiSelectEvidencePolicyVersion,
    type EvidenceDependencyIdentity,
    type EvidenceStatus,
    type PerViewEvidenceRegistry
} from './evidence-state';
import {
    aiSelectImageInstancePromptSynthesisPolicyVersion,
    generatedViewPromptSynthesisResponseMatchesRequest,
    imageInstanceMaskReviewResponseMatchesRequest,
    isAIViewRenderResponse,
    isGeneratedViewPromptSynthesisResponse,
    isImageInstanceMaskReviewResponse,
    viewRenderResponseMatchesRequest,
    type AIViewRenderRequest,
    type AIViewRenderResponse,
    type AISelectGeneratedViewPromptSynthesizer,
    type AISelectImageInstanceMaskReviewProvider,
    type AISelectViewRenderer,
    type GeneratedViewPromptSynthesisRequest,
    type ImageInstanceMaskReviewRequest,
    type ImageInstanceMaskReviewResponse
} from './generated-view-service';
import {
    createImageInstancePromptArtifact,
    createImageInstanceMaskPublicationCommand,
    imageInstanceMaskPublicationCommandMatchesArtifacts,
    inferImageInstanceMask,
    type ImageInstanceMaskProvider,
    type ImageInstanceMaskRequest,
    type ImageInstancePromptArtifact
} from './image-instance-mask';
import {
    aiSelectLocalKeyViewPlannerVersion,
    isLocalKeyViewPlanResponse,
    localKeyViewPlanResponseMatchesRequest,
    type AISelectLocalKeyViewPlanner,
    type LocalKeyViewPlan,
    type LocalKeyViewPlanRequest,
    type LocalKeyViewPlanResponse,
    type PlannedKeyView
} from './local-key-view-plan';
import type { MaskAnnotation } from './mask-annotation';
import { anchorMaskRankingPolicyVersion } from './mask-proposal';
import type { MaskAnnotationRegistry } from './mask-registry';
import {
    isMaskResultResponse,
    maskResponseMatchesRequest,
    type AIViewMaskRequest,
    type MaskResultResponse,
    type PreviousPredictionLogitsRef
} from './mask-service';
import type { PromptState } from './prompt-state';
import {
    aiSelectTargetGeometryPolicyVersion,
    isTargetGeometryHintResponse,
    targetGeometryHintResponseMatchesRequest,
    type AISelectTargetGeometryProvider,
    type TargetGeometryHintArtifact,
    type TargetGeometryHintRequest,
    type TargetGeometryHintResponse
} from './target-geometry-hint';
import {
    aiSelectViewAssessmentPolicyVersion,
    defaultViewParticipation,
    type ReviewReason,
    type ViewAssessmentResult
} from './view-assessment';

export type GeneratedViewRenderStatus =
    'pending' | 'rendering' | 'ready' | 'failed';

export type GeneratedViewMaskStatus =
    'none' | 'generating' | 'ready' | 'unavailable' | 'failed';

export type GeneratedViewPromptStatus =
    'none' | 'synthesizing' | 'ready' | 'limited' | 'failed';

export type GeneratedViewPlannerStatus =
    'idle' | 'planning' | 'active' | 'failed';

export type GeneratedViewMaskQuality =
    'none' | 'auto-good' | 'auto-review' | 'user-confirmed' | 'failed';

/**
 * The §7 per-view surface of one planner-owned Generated AIView. Render,
 * Mask, and Evidence states are independent: RGB Ready never implies Mask
 * Ready, and a Mask or render failure never demotes a completed View.
 * Companion-owned View Assessment supplies automatic quality and the default
 * Participation; user confirmation and explicit exclusion remain independent
 * authority (Final Spec v1.1 §§13, 26). `planQuality`/`planReasons` echo the
 * bounded local Key-View planner's per-candidate validation (Ticket 08); they
 * are planner diagnostics only, never Mask or Evidence state.
 */
export interface GeneratedAIView {
    readonly viewId: string;
    /**
     * Target-local monotonic presentation order across every View source.
     * It is never request, artifact, Evidence, or Candidate identity.
     */
    readonly creationOrdinal: number;
    readonly source: AIViewSource;
    readonly cameraBinding: CameraBinding;
    readonly renderStatus: GeneratedViewRenderStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly rgbDigest?: string;
    readonly rendererId?: 'gsplat';
    readonly renderWorkingSetToken?: string;
    readonly renderStableGaussianIds?: readonly number[];
    readonly renderErrorMessage?: string;
    readonly participation: AIViewParticipation;
    readonly promptStatus: GeneratedViewPromptStatus;
    readonly prompt?: ImageInstancePromptArtifact;
    readonly promptDiagnostics?: readonly string[];
    readonly promptErrorMessage?: string;
    readonly maskStatus: GeneratedViewMaskStatus;
    readonly maskErrorMessage?: string;
    readonly stableMaskId?: string;
    readonly stableMaskDigest?: string;
    readonly maskQuality: GeneratedViewMaskQuality;
    readonly assessment?: ViewAssessmentResult;
    readonly evidenceStatus: EvidenceStatus;
    readonly selected: boolean;
    readonly planQuality?: 'usable' | 'limited';
    readonly planReasons?: readonly string[];
}

export interface AISelectGeneratedViewState {
    readonly plannerStatus: GeneratedViewPlannerStatus;
    readonly plannerErrorMessage?: string;
    readonly views: readonly GeneratedAIView[];
    readonly selectedViewId: string | null;
    /**
     * The bound Target Geometry Hint for this run, or null before it is
     * Ready. It is localization/framing context only — never ownership.
     */
    readonly geometryHint: TargetGeometryHintArtifact | null;
    /** Accepted bounded local Key-View batches in acceptance order. */
    readonly keyViewPlans: readonly LocalKeyViewPlan[];
    /** Explicit target-local recompute state; it never starts work itself. */
    readonly dirtyState: AISelectDirtyState;
}

export type AISelectGeneratedViewListener = (
    state: AISelectGeneratedViewState
) => void;

export interface AISelectGeneratedViewControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly confirmation: AISelectAnchorConfirmationController;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly evidenceRegistry: PerViewEvidenceRegistry;
    readonly geometryHints: AISelectTargetGeometryProvider;
    readonly planner: AISelectLocalKeyViewPlanner;
    readonly renderer: AISelectViewRenderer;
    readonly promptSynthesizer: AISelectGeneratedViewPromptSynthesizer;
    readonly maskProvider: ImageInstanceMaskProvider;
    readonly reviewProvider: AISelectImageInstanceMaskReviewProvider;
    /** Shared with the Anchor Mask controller for one Current Target Context. */
    readonly dirtyState?: AISelectDirtyStateTracker;
    readonly getImageInstanceRuntimeBinding?: () => GeneratedViewImageInstanceRuntimeBinding | null;
    /**
     * The additive Companion capability gate: an older Companion without
     * Target Geometry and local Key-View planning keeps the Anchor flow
     * usable, and planning fails closed with an actionable diagnostic instead
     * of a transport 404.
     */
    readonly supportsGeneratedViews?: () => boolean;
}

/** The locked runtime identity required for one generated static-image call. */
export interface GeneratedViewImageInstanceRuntimeBinding {
    readonly adapterId: string;
    readonly modelManifestDigest: string;
    readonly runtimeDigest: string;
    readonly companionInstanceId: string;
    readonly adapterCapabilityDigest: string;
}

interface GeneratedViewRecord {
    readonly viewId: string;
    readonly creationOrdinal: number;
    readonly source: AIViewSource;
    readonly cameraBinding: CameraBinding;
    /** The accepted plan identity embedded in this View's generated Prompt. */
    localKeyViewPlanDigest?: string;
    planQuality?: 'usable' | 'limited';
    planReasons?: readonly string[];
    renderStatus: GeneratedViewRenderStatus;
    rgb?: AnchorRgbArtifact;
    rendererId?: 'gsplat';
    renderWorkingSetToken?: string;
    renderStableGaussianIds?: readonly number[];
    renderErrorMessage?: string;
    promptStatus: GeneratedViewPromptStatus;
    promptDiagnostics?: readonly string[];
    promptErrorMessage?: string;
    prompt?: ImageInstancePromptArtifact;
    /** The model identity echoed by the Prompt synthesis response. */
    promptModelManifestDigest?: string;
    promptRuntimeDigest?: string;
    promptCompanionInstanceId?: string;
    maskStatus: GeneratedViewMaskStatus;
    maskErrorMessage?: string;
    /** Last observed Stable Mask artifact digest for dirty-state comparison. */
    stableMaskDigest?: string;
    assessment?: ViewAssessmentResult;
    participation: AIViewParticipation;
}

/** A plan may never reuse an existing View identity. */
export const findKeyViewIdCollisions = (
    existing: readonly { readonly viewId: string }[],
    planned: readonly { readonly viewId: string }[]
): readonly string[] => {
    const existingIds = new Set(existing.map((view) => view.viewId));
    return Object.freeze(
        planned
            .map((view) => view.viewId)
            .filter(
                (viewId, index, ids) =>
                    existingIds.has(viewId) || ids.indexOf(viewId) !== index
            )
    );
};

const copyRgb = (rgb: AnchorRgbArtifact): AnchorRgbArtifact => {
    return Object.freeze({
        pngBase64: rgb.pngBase64,
        digest: rgb.digest,
        width: rgb.width,
        height: rgb.height
    });
};

const copyPrompt = (
    prompt: ImageInstancePromptArtifact
): ImageInstancePromptArtifact => {
    return createImageInstancePromptArtifact({
        schemaVersion: prompt.schemaVersion,
        targetContextId: prompt.targetContextId,
        contextRevision: prompt.contextRevision,
        viewId: prompt.viewId,
        rgbDigest: prompt.rgbDigest,
        cameraBindingDigest: prompt.cameraBindingDigest,
        ...(prompt.targetGeometryHintDigest === undefined
            ? {}
            : { targetGeometryHintDigest: prompt.targetGeometryHintDigest }),
        ...(prompt.localKeyViewPlanDigest === undefined
            ? {}
            : { localKeyViewPlanDigest: prompt.localKeyViewPlanDigest }),
        adapterCapabilityDigest: prompt.adapterCapabilityDigest,
        ...(prompt.promptSynthesisPolicyDigest === undefined
            ? {}
            : {
                  promptSynthesisPolicyDigest:
                      prompt.promptSynthesisPolicyDigest
              }),
        positivePoints: prompt.positivePoints,
        negativePoints: prompt.negativePoints,
        ...(prompt.positiveBox === undefined
            ? {}
            : { positiveBox: prompt.positiveBox }),
        ...(prompt.previousLogitsRefDigest === undefined
            ? {}
            : { previousLogitsRefDigest: prompt.previousLogitsRefDigest }),
        multimaskOutput: prompt.multimaskOutput
    });
};

const generatedViewPublicationPolicyDigest = sha256Digest(
    new TextEncoder().encode('image-instance-mask-publication/v1')
);

const isImageInstanceRuntimeBinding = (
    value: GeneratedViewImageInstanceRuntimeBinding | null
): value is GeneratedViewImageInstanceRuntimeBinding => {
    return (
        value !== null &&
        value.adapterId.trim().length > 0 &&
        value.modelManifestDigest.trim().length > 0 &&
        /^sha256:[a-f0-9]{64}$/i.test(value.runtimeDigest) &&
        value.companionInstanceId.trim().length > 0 &&
        /^sha256:[a-f0-9]{64}$/i.test(value.adapterCapabilityDigest)
    );
};

const copyWorldTriple = (
    triple: readonly [number, number, number]
): readonly [number, number, number] =>
    Object.freeze([triple[0], triple[1], triple[2]]);

/**
 * Transport responses are untrusted: retain only deep-frozen copies of the
 * Companion-published artifacts as target-local state.
 */
const copyHint = (
    hint: TargetGeometryHintArtifact
): TargetGeometryHintArtifact => {
    return Object.freeze({
        schemaVersion: hint.schemaVersion,
        targetContextId: hint.targetContextId,
        anchorCameraBindingDigest: hint.anchorCameraBindingDigest,
        anchorRgbDigest: hint.anchorRgbDigest,
        anchorStableMaskDigest: hint.anchorStableMaskDigest,
        geometryPolicyDigest: hint.geometryPolicyDigest,
        centerWorld: copyWorldTriple(hint.centerWorld),
        extentWorld: copyWorldTriple(hint.extentWorld),
        visiblePoints: Object.freeze(hint.visiblePoints.map(copyWorldTriple)),
        quality: hint.quality,
        reasons: Object.freeze([...hint.reasons]),
        promptSupport: hint.promptSupport,
        artifactDigest: hint.artifactDigest
    });
};

const copyPlannedKeyView = (view: PlannedKeyView): PlannedKeyView => {
    return Object.freeze({
        viewId: view.viewId,
        cameraBinding: copyCameraBinding(view.cameraBinding),
        quality: view.quality,
        reasons: Object.freeze([...view.reasons])
    });
};

const copyPlan = (plan: LocalKeyViewPlan): LocalKeyViewPlan => {
    return Object.freeze({
        schemaVersion: plan.schemaVersion,
        targetContextId: plan.targetContextId,
        anchorStableMaskDigest: plan.anchorStableMaskDigest,
        targetGeometryHintDigest: plan.targetGeometryHintDigest,
        localViewPolicyDigest: plan.localViewPolicyDigest,
        orderedViews: Object.freeze(plan.orderedViews.map(copyPlannedKeyView)),
        planAttemptId: plan.planAttemptId,
        artifactDigest: plan.artifactDigest
    });
};

const errorMessage = (error: unknown, fallback: string): string => {
    return error instanceof Error && error.message ? error.message : fallback;
};

const copyAssessment = (
    assessment: ViewAssessmentResult
): ViewAssessmentResult => {
    const copyReasons = (
        reasons: readonly ReviewReason[]
    ): readonly ReviewReason[] => Object.freeze([...reasons]);
    return Object.freeze({
        status: assessment.status,
        ...(assessment.primaryReason === undefined
            ? {}
            : { primaryReason: assessment.primaryReason }),
        reasons: copyReasons(assessment.reasons),
        actionableReasons: copyReasons(assessment.actionableReasons),
        policyVersion: assessment.policyVersion,
        inputIdentity: Object.freeze({
            rgbDigest: assessment.inputIdentity.rgbDigest,
            stableMaskDigest: assessment.inputIdentity.stableMaskDigest,
            assessmentPolicyVersion:
                assessment.inputIdentity.assessmentPolicyVersion
        }),
        ...(assessment.diagnostics === undefined
            ? {}
            : {
                  diagnostics: Object.freeze({
                      framePixels: assessment.diagnostics.framePixels,
                      foregroundPixels: assessment.diagnostics.foregroundPixels,
                      boundaryPixels: assessment.diagnostics.boundaryPixels,
                      boundaryContactRatio:
                          assessment.diagnostics.boundaryContactRatio,
                      connectedComponents:
                          assessment.diagnostics.connectedComponents,
                      largestComponentRatio:
                          assessment.diagnostics.largestComponentRatio,
                      promptPointCount: assessment.diagnostics.promptPointCount,
                      promptViolationCount:
                          assessment.diagnostics.promptViolationCount,
                      boxSpillPixels: assessment.diagnostics.boxSpillPixels,
                      boxSpillRatio: assessment.diagnostics.boxSpillRatio
                  })
              })
    });
};

const automaticAssessmentDefaults = (
    assessment: ViewAssessmentResult
): {
    readonly stableMaskStatus: 'auto-good' | 'auto-review';
    readonly maskQuality: GeneratedViewMaskQuality;
} => {
    switch (assessment.status) {
        case 'good':
            return {
                stableMaskStatus: 'auto-good',
                maskQuality: 'auto-good'
            };
        case 'review':
            return {
                stableMaskStatus: 'auto-review',
                maskQuality: 'auto-review'
            };
        case 'failed':
            return {
                stableMaskStatus: 'auto-review',
                maskQuality: 'failed'
            };
    }
};

/**
 * The confirmed-Anchor identity one planner run binds. Any change — a new
 * RGB, a new Stable Mask, a re-confirm, a Restart — rotates this identity and
 * disposes every target-local Generated View before planning starts again.
 */
const anchorIdentityOf = (confirmed: ConfirmedAnchor): string => {
    return [
        confirmed.targetContextId,
        String(confirmed.contextRevision),
        confirmed.rgbDigest,
        confirmed.stableMask.artifact.digest,
        confirmed.sceneId,
        confirmed.sceneVersion
    ].join('\u0000');
};

/**
 * Owns the progressive multi-view pipeline that starts when an Anchor is
 * confirmed: Companion camera planning, per-view authoritative gsplat RGB
 * publication, and mask-conditioned automatic Mask production. Evidence is
 * deliberately never requested here — it derives missing (`not-requested`)
 * from the published RGB/Mask identity until the formal P/N/V path exists.
 * Every step binds the confirmed-Anchor identity and the target kernel gate,
 * so late results from an adjusted or restarted Anchor are discarded.
 */
export class AISelectGeneratedViewController {
    private readonly anchor: AISelectAnchorController;
    private readonly maskRegistry: MaskAnnotationRegistry;
    private readonly evidenceRegistry: PerViewEvidenceRegistry;
    private readonly dirtyState: AISelectDirtyStateTracker;
    private readonly geometryHints: AISelectTargetGeometryProvider;
    private readonly planner: AISelectLocalKeyViewPlanner;
    private readonly renderer: AISelectViewRenderer;
    private readonly promptSynthesizer: AISelectGeneratedViewPromptSynthesizer;
    private readonly maskProvider: ImageInstanceMaskProvider;
    private readonly reviewProvider: AISelectImageInstanceMaskReviewProvider;
    private readonly getImageInstanceRuntimeBinding: () => GeneratedViewImageInstanceRuntimeBinding | null;
    private readonly supportsGeneratedViews: () => boolean;
    private readonly listeners = new Set<AISelectGeneratedViewListener>();
    private confirmed: ConfirmedAnchor | null = null;
    private identity: string | null = null;
    private requestBinding: AIRequestBinding | null = null;
    private runOrdinal = 0;
    private plannerStatus: GeneratedViewPlannerStatus = 'idle';
    private plannerErrorMessage: string | undefined;
    private views: GeneratedViewRecord[] = [];
    private selectedViewId: string | null = null;
    private geometryHint: TargetGeometryHintArtifact | null = null;
    private keyViewPlans: LocalKeyViewPlan[] = [];
    private queue: Promise<void> = Promise.resolve();
    private nextGeometryAttemptOrdinal = 0;
    private nextPlanAttemptOrdinal = 0;
    private nextRenderAttemptOrdinal = 0;
    private nextPromptSynthesisAttemptOrdinal = 0;
    private nextMaskAttemptOrdinal = 0;
    private nextReviewAttemptOrdinal = 0;
    private nextPublicationAttemptOrdinal = 0;
    private nextUserViewOrdinal = 0;
    private nextViewCreationOrdinal = 0;
    private observedTargetContextId: string | null = null;
    private observedTargetLifecycle: 'active' | 'suspended' | null = null;

    constructor(options: AISelectGeneratedViewControllerOptions) {
        this.anchor = options.anchor;
        this.maskRegistry = options.maskRegistry;
        this.evidenceRegistry = options.evidenceRegistry;
        this.dirtyState = options.dirtyState ?? new AISelectDirtyStateTracker();
        this.geometryHints = options.geometryHints;
        this.planner = options.planner;
        this.renderer = options.renderer;
        this.promptSynthesizer = options.promptSynthesizer;
        this.maskProvider = options.maskProvider;
        this.reviewProvider = options.reviewProvider;
        this.getImageInstanceRuntimeBinding =
            options.getImageInstanceRuntimeBinding ?? (() => null);
        this.supportsGeneratedViews =
            options.supportsGeneratedViews ?? (() => true);
        this.dirtyState.subscribe(() => this.publish());
        this.anchor.subscribe((state) =>
            this.handleTargetLifecycle(
                state.context?.targetContextId ?? null,
                state.context?.lifecycle === 'active' ||
                    state.context?.lifecycle === 'suspended'
                    ? state.context.lifecycle
                    : null
            )
        );
        options.confirmation.subscribe((state) =>
            this.handleConfirmationState(state)
        );
    }

    get state(): AISelectGeneratedViewState {
        return Object.freeze({
            plannerStatus: this.plannerStatus,
            ...(this.plannerErrorMessage === undefined
                ? {}
                : { plannerErrorMessage: this.plannerErrorMessage }),
            views: Object.freeze(this.views.map((view) => this.compose(view))),
            selectedViewId: this.selectedViewId,
            geometryHint: this.geometryHint,
            keyViewPlans: Object.freeze([...this.keyViewPlans]),
            dirtyState: this.dirtyState.state
        });
    }

    subscribe(listener: AISelectGeneratedViewListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    /** Select one Generated View for Gallery ↔ Frustum sync; null is Anchor. */
    selectView(viewId: string | null): void {
        if (
            viewId !== null &&
            !this.views.some((view) => view.viewId === viewId)
        ) {
            throw new Error(
                'AI Select cannot select an unknown Generated AIView.'
            );
        }
        if (this.selectedViewId === viewId) {
            return;
        }
        this.selectedViewId = viewId;
        this.publish();
    }

    /**
     * Confirm one Auto Review Stable Mask without changing its pixels. This
     * rotates the Stable Mask revision to User Confirmed and grants the §14.2
     * User Confirmed default Participation; the original assessment remains
     * inspectable.
     */
    confirmReviewAsIs(viewId: string): void {
        this.requireTargetActive();
        const view = this.requireView(viewId);
        if (
            view.rgb === undefined ||
            view.maskStatus !== 'ready' ||
            view.assessment?.status !== 'review'
        ) {
            throw new Error(
                'AI Select Confirm as-is requires an Auto Review Stable Mask.'
            );
        }
        this.maskRegistry.confirmStableAsIs(viewId, view.rgb.digest);
        // Authority dominates the default: User Confirmed grants Included
        // regardless of the underlying automatic review status.
        const previousParticipation = view.participation;
        const stable = this.maskRegistry.viewState(
            viewId,
            view.rgb.digest
        ).stableMask;
        view.stableMaskDigest = stable?.artifact.digest;
        view.participation = defaultViewParticipation({
            reviewStatus: view.assessment.status,
            authority: 'user-confirmed'
        });
        if (previousParticipation !== view.participation) {
            this.dirtyState.markParticipationChanged(viewId);
        }
        this.publish();
    }

    /** User Participation authority is independent from automatic quality. */
    setViewParticipation(
        viewId: string,
        participation: AIViewParticipation
    ): void {
        this.requireTargetActive();
        const view = this.requireView(viewId);
        if (participation === 'included') {
            const stable =
                view.rgb === undefined
                    ? null
                    : this.maskRegistry.viewState(viewId, view.rgb.digest)
                          .stableMask;
            if (
                view.renderStatus !== 'ready' ||
                stable === null ||
                (stable.status !== 'auto-good' &&
                    stable.status !== 'user-confirmed')
            ) {
                throw new Error(
                    'AI Select can include only an Auto Good or User Confirmed RGB Ready Stable View.'
                );
            }
        }
        if (view.participation === participation) {
            return;
        }
        view.participation = participation;
        this.dirtyState.markParticipationChanged(viewId);
        this.publish();
    }

    /**
     * Add one user-owned AIView from an explicitly captured CameraBinding
     * (Use Current View or a confirmed adjusted Camera Inspection). The
     * Editor Camera is never moved by capture, and adding the View never
     * resumes or replaces completed local generation: the View renders
     * authoritative RGB on its own explicit pipeline step and then waits —
     * Mask authoring is the user's explicit 04C Prompt/Manual Draw choice,
     * never the Route-B planner pipeline (Final Spec v1.3 §§5, 17–18).
     */
    addUserView(cameraBinding: CameraBinding): string {
        this.requireTargetActive();
        if (!this.isRunCurrent(this.runOrdinal)) {
            throw new Error(
                'AI Select requires the confirmed Current Target Context before adding a user View.'
            );
        }
        const viewId = this.mintUserViewId();
        const view: GeneratedViewRecord = {
            viewId,
            creationOrdinal: (this.nextViewCreationOrdinal += 1),
            source: 'user-added',
            cameraBinding: copyCameraBinding(cameraBinding),
            renderStatus: 'pending',
            promptStatus: 'none',
            maskStatus: 'none',
            participation: 'excluded'
        };
        this.views = [...this.views, view];
        this.selectedViewId = viewId;
        this.publish();
        this.enqueue((run) => this.renderAndMaskView(run, viewId));
        return viewId;
    }

    /**
     * Build a single-frame SAM mask request for an explicitly edited View.
     * This supports both user-added Views and manual correction of a
     * planner-owned View; automatic Route-B acquisition remains separate.
     */
    createViewMaskRequest(
        viewId: string,
        promptState: PromptState,
        proposalAttemptId: string,
        modelManifestDigest: string,
        adapterCapabilityDigest: string,
        proposalPolicyVersion: string,
        options: {
            readonly includeRgbArtifact: boolean;
            readonly previousLogitsRef?: PreviousPredictionLogitsRef;
        }
    ): AIViewMaskRequest | null {
        const view = this.views.find((entry) => entry.viewId === viewId);
        const requestBinding = this.requestBinding;
        const confirmed = this.confirmed;
        if (
            view === undefined ||
            requestBinding === null ||
            confirmed === null ||
            !this.isRunCurrent(this.runOrdinal) ||
            view.renderStatus !== 'ready' ||
            view.rgb === undefined ||
            promptState.viewId !== viewId ||
            promptState.rgbDigest !== view.rgb.digest
        ) {
            return null;
        }
        const rgb = view.rgb;
        return Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: requestBinding.dependencyToken.splatId
            }),
            sceneId: confirmed.sceneId,
            sceneVersion: confirmed.sceneVersion,
            viewId,
            cameraBindingDigest: cameraBindingDigest(view.cameraBinding),
            rgbDigest: rgb.digest,
            rgbWidth: rgb.width,
            rgbHeight: rgb.height,
            ...(options.includeRgbArtifact ? { rgb: copyRgb(rgb) } : {}),
            promptState,
            ...(options.previousLogitsRef === undefined
                ? {}
                : { previousLogitsRef: options.previousLogitsRef }),
            modelManifestDigest,
            adapterCapabilityDigest,
            proposalPolicyVersion,
            rankingPolicyVersion: anchorMaskRankingPolicyVersion,
            proposalAttemptId
        });
    }

    /**
     * Compatibility alias for existing user-View callers. The request
     * binding is now intentionally source-agnostic so a Generated View can
     * enter the same explicit Prompt/Mask correction surface.
     */
    createUserViewMaskRequest(
        viewId: string,
        promptState: PromptState,
        proposalAttemptId: string,
        modelManifestDigest: string,
        adapterCapabilityDigest: string,
        proposalPolicyVersion: string,
        options: {
            readonly includeRgbArtifact: boolean;
            readonly previousLogitsRef?: PreviousPredictionLogitsRef;
        }
    ): AIViewMaskRequest | null {
        return this.createViewMaskRequest(
            viewId,
            promptState,
            proposalAttemptId,
            modelManifestDigest,
            adapterCapabilityDigest,
            proposalPolicyVersion,
            options
        );
    }

    /**
     * The stale-result gate for explicit View-mask correction. The full
     * request binding and the View's current RGB identity must still match.
     */
    acceptsViewMaskResponse(
        response: MaskResultResponse,
        request: AIViewMaskRequest
    ): boolean {
        const view = this.views.find(
            (entry) => entry.viewId === request.viewId
        );
        return (
            view !== undefined &&
            view.renderStatus === 'ready' &&
            view.rgb !== undefined &&
            view.rgb.digest === request.rgbDigest &&
            this.anchor.acceptsTargetBinding(request.requestBinding) &&
            isMaskResultResponse(response) &&
            maskResponseMatchesRequest(response, request)
        );
    }

    /** Compatibility alias for existing user-View callers. */
    acceptsUserViewMaskResponse(
        response: MaskResultResponse,
        request: AIViewMaskRequest
    ): boolean {
        return this.acceptsViewMaskResponse(response, request);
    }

    /**
     * Project an explicitly published Stable Mask onto any View record.
     * User Confirmed authority defaults Included; the registry performs the
     * atomic swap and its rotated identity dirties Evidence without lifting.
     */
    noteViewStablePublication(viewId: string): void {
        this.requireTargetActive();
        const view = this.views.find((entry) => entry.viewId === viewId);
        if (
            view === undefined ||
            view.renderStatus !== 'ready' ||
            view.rgb === undefined
        ) {
            return;
        }
        const stable = this.maskRegistry.viewState(
            viewId,
            view.rgb.digest
        ).stableMask;
        if (stable === null) {
            return;
        }
        const stableChanged = view.stableMaskDigest !== stable.artifact.digest;
        const previousParticipation = view.participation;
        view.stableMaskDigest = stable.artifact.digest;
        view.maskStatus = 'ready';
        view.participation = defaultViewParticipation({
            reviewStatus: null,
            authority:
                stable.status === 'user-confirmed'
                    ? 'user-confirmed'
                    : 'automatic'
        });
        if (stableChanged) {
            this.dirtyState.markStableMaskPublished(viewId);
        } else if (previousParticipation !== view.participation) {
            this.dirtyState.markParticipationChanged(viewId);
        }
        this.publish();
    }

    /** Compatibility alias for existing user-View callers. */
    noteUserViewStablePublication(viewId: string): void {
        this.noteViewStablePublication(viewId);
    }

    /** The Current Target Context identity of the active run, if any. */
    getRunTargetContextId(): string | null {
        return this.requestBinding?.targetContextId ?? null;
    }

    isTargetActive(): boolean {
        return this.anchor.isTargetActive();
    }

    /** Re-run the initial bounded plan after its one product failure state. */
    retryPlanning(): void {
        this.requireTargetActive();
        if (this.identity === null || this.plannerStatus !== 'failed') {
            throw new Error(
                'AI Select can retry planning only after a planner failure.'
            );
        }
        this.plannerStatus = 'planning';
        this.plannerErrorMessage = undefined;
        this.publish();
        this.enqueue((run) => this.planViews(run));
    }

    private handleConfirmationState(
        state: AISelectAnchorConfirmationState
    ): void {
        const confirmed = state.confirmedAnchor;
        if (confirmed === null) {
            this.disposeRun();
            return;
        }
        const identity = anchorIdentityOf(confirmed);
        if (identity === this.identity) {
            return;
        }
        this.disposeRun();
        this.beginRun(confirmed, identity);
    }

    private handleTargetLifecycle(
        targetContextId: string | null,
        lifecycle: 'active' | 'suspended' | null
    ): void {
        if (targetContextId !== this.observedTargetContextId) {
            this.observedTargetContextId = targetContextId;
            this.observedTargetLifecycle = lifecycle;
            return;
        }
        const previous = this.observedTargetLifecycle;
        this.observedTargetLifecycle = lifecycle;
        if (this.identity === null || previous === lifecycle) {
            return;
        }
        if (lifecycle === 'suspended') {
            // Logical cancellation only: artifacts remain inspectable while
            // every pre-suspension asynchronous completion becomes stale.
            this.runOrdinal += 1;
            this.publish();
            return;
        }
        if (previous === 'suspended' && lifecycle === 'active') {
            const requestBinding =
                this.anchor.createCurrentTargetRequestBinding();
            if (
                requestBinding !== null &&
                requestBinding.targetContextId === targetContextId
            ) {
                this.requestBinding = requestBinding;
                this.publish();
            }
        }
    }

    private beginRun(confirmed: ConfirmedAnchor, identity: string): void {
        this.confirmed = confirmed;
        this.identity = identity;
        this.requestBinding = Object.freeze({
            targetContextId: confirmed.targetContextId,
            contextRevision: confirmed.contextRevision,
            dependencyToken: copyDependencyToken(confirmed.dependencyToken)
        });
        // A confirmed Anchor is an explicit Stable input to the bounded
        // geometry/plan pipeline. Fresh runs have no dependent Views yet;
        // the accepted plan records them below.
        this.dirtyState.markAnchorStableChanged([]);
        this.plannerStatus = 'planning';
        this.publish();
        this.enqueue((run) => this.planViews(run));
    }

    private async planViews(run: number): Promise<void> {
        const confirmed = this.confirmed;
        const requestBinding = this.requestBinding;
        if (
            !this.isRunCurrent(run) ||
            confirmed === null ||
            requestBinding === null
        ) {
            return;
        }
        if (!this.supportsGeneratedViews()) {
            this.failPlanning(
                'The Selection Service Companion does not advertise Target Geometry and local Key-View planning. Install the compatible locked Companion release, then refresh readiness.'
            );
            return;
        }
        const snapshot = this.anchor.getAnchorSnapshot();
        if (snapshot === null) {
            this.failPlanning(
                'AI Select requires the confirmed Anchor Scene Snapshot before Target Geometry derivation.'
            );
            return;
        }
        const anchorCameraBindingDigest = cameraBindingDigest(
            confirmed.cameraBinding
        );
        const hintRequest: TargetGeometryHintRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: confirmed.dependencyToken.splatId
            }),
            snapshot,
            sceneId: confirmed.sceneId,
            sceneVersion: confirmed.sceneVersion,
            geometryAttemptId: this.mintGeometryAttemptId(),
            anchorCameraBinding: copyCameraBinding(confirmed.cameraBinding),
            anchorCameraBindingDigest,
            anchorRgbDigest: confirmed.rgbDigest,
            anchorStableMask: confirmed.stableMask.artifact,
            geometryPolicyVersion: aiSelectTargetGeometryPolicyVersion
        });

        let hintResponse: TargetGeometryHintResponse;
        try {
            hintResponse =
                await this.geometryHints.produceTargetGeometryHint(hintRequest);
        } catch (error) {
            if (!this.isRunCurrent(run)) {
                return;
            }
            this.failPlanning(
                errorMessage(
                    error,
                    'AI Select Target Geometry derivation failed.'
                )
            );
            return;
        }
        if (!this.isRunCurrent(run)) {
            return;
        }
        if (
            !isTargetGeometryHintResponse(hintResponse) ||
            !targetGeometryHintResponseMatchesRequest(hintResponse, hintRequest)
        ) {
            this.failPlanning(
                'The Selection Service Companion returned an invalid or stale Target Geometry Hint binding.'
            );
            return;
        }
        const hint = copyHint(hintResponse.hint);

        let planned: LocalKeyViewPlan | null;
        try {
            planned = await this.requestPlanBatch(run, confirmed, hint, 0);
        } catch (error) {
            if (!this.isRunCurrent(run)) {
                return;
            }
            this.failPlanning(
                errorMessage(error, 'AI Select local Key-View planning failed.')
            );
            return;
        }
        if (planned === null || !this.isRunCurrent(run)) {
            return;
        }
        const collisions = findKeyViewIdCollisions(
            this.views,
            planned.orderedViews
        );
        if (collisions.length > 0) {
            this.failPlanning(
                `The Selection Service Companion reused View identity ${collisions.join(', ')}; the plan was rejected.`
            );
            return;
        }
        this.geometryHint = hint;
        this.adoptInitialPlan(planned);
        this.plannerStatus = 'active';
        this.dirtyState.markTargetGeometryReady();
        this.dirtyState.markLocalKeyViewPlanReady(
            planned.orderedViews.map((view) => view.viewId)
        );
        this.publish();
        this.enqueuePendingViewRenders();
    }

    /**
     * One bounded local Key-View batch request bound to the exact confirmed
     * Anchor and Target Geometry Hint. Returns the frozen plan artifact, or
     * null after stale-run discard; batch failures throw to the caller's
     * failure surface.
     */
    private async requestPlanBatch(
        run: number,
        confirmed: ConfirmedAnchor,
        hint: TargetGeometryHintArtifact,
        batchOrdinal: number
    ): Promise<LocalKeyViewPlan | null> {
        const requestBinding = this.requestBinding;
        if (requestBinding === null) {
            return null;
        }
        const request: LocalKeyViewPlanRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: confirmed.dependencyToken.splatId
            }),
            planAttemptId: this.mintPlanAttemptId(),
            batchOrdinal,
            anchorCameraBinding: copyCameraBinding(confirmed.cameraBinding),
            anchorCameraBindingDigest: cameraBindingDigest(
                confirmed.cameraBinding
            ),
            anchorRgbDigest: confirmed.rgbDigest,
            anchorStableMaskDigest: confirmed.stableMask.artifact.digest,
            targetGeometryHint: hint,
            localViewPolicyVersion: aiSelectLocalKeyViewPlannerVersion
        });

        const response: LocalKeyViewPlanResponse =
            await this.planner.planLocalKeyViews(request);
        if (!this.isRunCurrent(run)) {
            return null;
        }
        if (
            !isLocalKeyViewPlanResponse(response) ||
            !localKeyViewPlanResponseMatchesRequest(response, request)
        ) {
            throw new Error(
                'The Selection Service Companion returned an invalid or stale local Key-View plan binding.'
            );
        }
        return copyPlan(response.plan);
    }

    /**
     * The first plan replaces every planner-owned View of this run (none can
     * have completed yet); user-owned Views are preserved.
     */
    private adoptInitialPlan(plan: LocalKeyViewPlan): void {
        const displacedPlannerViews = this.views.filter(
            (view) => view.source !== 'user-added'
        );
        for (const view of displacedPlannerViews) {
            this.maskRegistry.disposeView(view.viewId);
            this.evidenceRegistry.disposeView(view.viewId);
        }
        const userOwned = this.views.filter(
            (view) => view.source === 'user-added'
        );
        this.views = [
            ...plan.orderedViews.map((planned) =>
                this.recordForPlannedView(planned, plan.artifactDigest)
            ),
            ...userOwned
        ];
        if (
            this.selectedViewId !== null &&
            !this.views.some((view) => view.viewId === this.selectedViewId)
        ) {
            this.selectedViewId = null;
        }
        this.keyViewPlans = [plan];
        for (const view of displacedPlannerViews) {
            if (view.participation === 'included') {
                this.dirtyState.markParticipationChanged(view.viewId);
            }
            this.dirtyState.forgetView(view.viewId);
        }
    }

    private recordForPlannedView(
        planned: PlannedKeyView,
        localKeyViewPlanDigest: string
    ): GeneratedViewRecord {
        return {
            viewId: planned.viewId,
            creationOrdinal: (this.nextViewCreationOrdinal += 1),
            source: 'auto-generated',
            cameraBinding: copyCameraBinding(planned.cameraBinding),
            localKeyViewPlanDigest,
            planQuality: planned.quality,
            planReasons: planned.reasons,
            renderStatus: 'pending',
            promptStatus: 'none',
            maskStatus: 'none',
            participation: 'excluded'
        };
    }

    /**
     * Queue render+Mask for every initial planner-owned View waiting for RGB.
     * Failed Views remain inspectable and Excluded; they are never restarted
     * through an identical-input product command.
     */
    private enqueuePendingViewRenders(): void {
        for (const view of this.views) {
            if (
                view.source !== 'user-added' &&
                view.renderStatus === 'pending'
            ) {
                this.enqueue((stepRun) =>
                    this.renderAndMaskView(stepRun, view.viewId)
                );
            }
        }
    }

    /**
     * One per-view pipeline unit: publish the View the moment authoritative
     * RGB is Ready, then produce its automatic Mask without blocking
     * publication. A render or Mask failure is contained to this View; every
     * other completed or pending View survives untouched.
     */
    private async renderAndMaskView(
        run: number,
        viewId: string
    ): Promise<void> {
        const view = this.views.find((entry) => entry.viewId === viewId);
        const requestBinding = this.requestBinding;
        if (
            !this.isRunCurrent(run) ||
            view === undefined ||
            requestBinding === null
        ) {
            return;
        }
        // A queued pipeline step only ever starts a pending View; duplicate
        // queue entries and already-running or failed Views are discarded.
        if (view.renderStatus !== 'pending') {
            return;
        }
        const snapshot = this.anchor.getAnchorSnapshot();
        if (snapshot === null) {
            this.failViewRender(
                view,
                'AI Select requires the confirmed Anchor Scene Snapshot before a Generated View render.'
            );
            return;
        }
        view.renderStatus = 'rendering';
        view.renderErrorMessage = undefined;
        this.publish();
        const request: AIViewRenderRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: requestBinding.dependencyToken.splatId
            }),
            snapshot,
            cameraBinding: copyCameraBinding(view.cameraBinding),
            viewId: view.viewId,
            renderAttemptId: this.mintRenderAttemptId()
        });

        let response: AIViewRenderResponse;
        try {
            response = await this.renderer.renderView(request);
        } catch (error) {
            if (!this.isRunCurrent(run) || !this.views.includes(view)) {
                return;
            }
            this.failViewRender(
                view,
                errorMessage(
                    error,
                    'AI Select Generated View rendering failed.'
                )
            );
            return;
        }
        // A target cutover or disposal mid-flight orphans the record; its late
        // result must never resurrect the View or republish its artifacts.
        if (!this.isRunCurrent(run) || !this.views.includes(view)) {
            return;
        }
        if (
            !isAIViewRenderResponse(response) ||
            !viewRenderResponseMatchesRequest(response, request)
        ) {
            this.failViewRender(
                view,
                'The Selection Service Companion returned an invalid or stale Generated View render binding.'
            );
            return;
        }
        // Atomic View publication: RGB Ready is independent from Mask and
        // Evidence; the Gallery may show it immediately.
        const previousRgbDigest = view.rgb?.digest;
        view.renderStatus = 'ready';
        view.rgb = copyRgb(response.rgb);
        view.rendererId = response.rendererId;
        view.renderWorkingSetToken = response.renderWorkingSetToken;
        view.renderStableGaussianIds = Object.freeze([
            ...response.renderStableGaussianIds
        ]);
        if (
            previousRgbDigest !== undefined &&
            previousRgbDigest !== view.rgb.digest
        ) {
            view.stableMaskDigest = undefined;
            this.dirtyState.markViewCameraOrRgbChanged(viewId);
        }
        this.publish();
        // User-owned Views stop at authoritative RGB: Mask authoring is the
        // explicit 04C Prompt/Manual Draw choice, never the Route-B pipeline.
        if (view.source === 'user-added') {
            return;
        }
        await this.synthesizeAndProduceViewMask(run, view);
    }

    /**
     * Route B prompt generation is distinct from Mask inference. It
     * binds the accepted local Key-View plan, geometry hint, exact RGB and
     * CameraBinding to a compact static-image Prompt artifact.
     */
    private async synthesizeAndProduceViewMask(
        run: number,
        view: GeneratedViewRecord
    ): Promise<void> {
        const synthesized = await this.synthesizeViewPrompt(run, view);
        if (synthesized === null) {
            return;
        }
        await this.produceViewMask(
            run,
            view,
            synthesized.rgb,
            synthesized.prompt
        );
    }

    /**
     * Publish the initial generated-View Prompt. The acquisition pipeline
     * explicitly composes this with `produceViewMask`.
     */
    private async synthesizeViewPrompt(
        run: number,
        view: GeneratedViewRecord
    ): Promise<{
        readonly rgb: AnchorRgbArtifact;
        readonly prompt: ImageInstancePromptArtifact;
    } | null> {
        const requestBinding = this.requestBinding;
        const hint = this.geometryHint;
        const rgb = view.rgb;
        if (
            !this.isRunCurrent(run) ||
            requestBinding === null ||
            hint === null ||
            rgb === undefined ||
            !this.views.includes(view)
        ) {
            return null;
        }
        const stable = this.maskRegistry.viewState(
            view.viewId,
            rgb.digest
        ).stableMask;
        if (stable?.status === 'user-confirmed') {
            return null;
        }
        const plan = this.keyViewPlans.find(
            (candidate) =>
                candidate.artifactDigest === view.localKeyViewPlanDigest
        );
        if (plan === undefined) {
            this.failViewPrompt(
                view,
                'AI Select requires the accepted Local Key-View Plan before Prompt synthesis.'
            );
            return null;
        }
        const runtime = this.getImageInstanceRuntimeBinding();
        if (!isImageInstanceRuntimeBinding(runtime)) {
            this.failViewPrompt(
                view,
                'AI Select requires a ready locked SAM 3 Image runtime before Prompt synthesis.'
            );
            return null;
        }
        view.promptStatus = 'synthesizing';
        view.promptDiagnostics = undefined;
        view.promptErrorMessage = undefined;
        this.dirtyState.markPromptDirty(view.viewId);
        this.publish();
        const request: GeneratedViewPromptSynthesisRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: requestBinding.dependencyToken.splatId
            }),
            viewId: view.viewId,
            viewCameraBinding: copyCameraBinding(view.cameraBinding),
            viewCameraBindingDigest: cameraBindingDigest(view.cameraBinding),
            rgb: copyRgb(rgb),
            targetGeometryHint: copyHint(hint),
            localKeyViewPlan: copyPlan(plan),
            adapterCapabilityDigest: runtime.adapterCapabilityDigest,
            modelManifestDigest: runtime.modelManifestDigest,
            runtimeDigest: runtime.runtimeDigest,
            companionInstanceId: runtime.companionInstanceId,
            promptSynthesisAttemptId: this.mintPromptSynthesisAttemptId(),
            promptSynthesisPolicyVersion:
                aiSelectImageInstancePromptSynthesisPolicyVersion
        });
        let response;
        try {
            response =
                await this.promptSynthesizer.synthesizeGeneratedViewPrompt(
                    request
                );
        } catch (error) {
            if (!this.isRunCurrent(run) || !this.views.includes(view)) {
                return null;
            }
            this.failViewPrompt(
                view,
                errorMessage(
                    error,
                    'AI Select Generated View Prompt synthesis failed.'
                )
            );
            return null;
        }
        if (!this.isRunCurrent(run) || !this.views.includes(view)) {
            return null;
        }
        if (
            !isGeneratedViewPromptSynthesisResponse(response) ||
            !generatedViewPromptSynthesisResponseMatchesRequest(
                response,
                request
            )
        ) {
            this.failViewPrompt(
                view,
                'The Selection Service Companion returned an invalid or stale Generated View Prompt binding.'
            );
            return null;
        }
        if (response.status === 'limited') {
            view.prompt = undefined;
            view.promptModelManifestDigest = undefined;
            view.promptRuntimeDigest = undefined;
            view.promptCompanionInstanceId = undefined;
            view.localKeyViewPlanDigest = response.localKeyViewPlanDigest;
            view.promptStatus = 'limited';
            view.promptDiagnostics = Object.freeze([...response.diagnostics]);
            view.promptErrorMessage = undefined;
            view.maskStatus = 'unavailable';
            view.maskErrorMessage = response.diagnostics.join('; ');
            // A failed Prompt replacement cannot demote the valid Stable
            // Mask/Evidence/Candidate inputs it did not replace. A View with
            // no Stable Mask remains Excluded by default.
            this.excludeWithoutCurrentStableMask(view);
            this.publish();
            return null;
        }
        const prompt = copyPrompt(response.prompt);
        view.prompt = prompt;
        view.localKeyViewPlanDigest = prompt.localKeyViewPlanDigest;
        view.promptModelManifestDigest = response.modelManifestDigest;
        view.promptRuntimeDigest = response.runtimeDigest;
        view.promptCompanionInstanceId = response.companionInstanceId;
        view.promptStatus = 'ready';
        view.promptDiagnostics = Object.freeze([...response.diagnostics]);
        view.promptErrorMessage = undefined;
        this.dirtyState.markPromptReady(view.viewId);
        this.publish();
        return Object.freeze({ rgb, prompt });
    }

    private async produceViewMask(
        run: number,
        view: GeneratedViewRecord,
        rgb: AnchorRgbArtifact,
        prompt: ImageInstancePromptArtifact
    ): Promise<void> {
        const requestBinding = this.requestBinding;
        if (
            !this.isRunCurrent(run) ||
            requestBinding === null ||
            !this.views.includes(view)
        ) {
            return;
        }
        const currentStable = this.maskRegistry.viewState(
            view.viewId,
            rgb.digest
        ).stableMask;
        if (currentStable?.status === 'user-confirmed') {
            return;
        }
        const runtime = this.getImageInstanceRuntimeBinding();
        if (
            !isImageInstanceRuntimeBinding(runtime) ||
            prompt.adapterCapabilityDigest !==
                runtime.adapterCapabilityDigest ||
            view.promptModelManifestDigest !== runtime.modelManifestDigest ||
            view.promptRuntimeDigest !== runtime.runtimeDigest ||
            view.promptCompanionInstanceId !== runtime.companionInstanceId
        ) {
            this.failViewPrompt(
                view,
                'The locked SAM 3 Image runtime changed after Prompt synthesis. Change the Prompt or add a replacement View before automatic Mask inference.'
            );
            return;
        }
        view.maskStatus = 'generating';
        view.maskErrorMessage = undefined;
        this.publish();
        const request: ImageInstanceMaskRequest = Object.freeze({
            schemaVersion: 1,
            identity: Object.freeze({
                targetContextId: requestBinding.targetContextId,
                contextRevision: requestBinding.contextRevision,
                viewId: view.viewId,
                rgbDigest: rgb.digest,
                promptArtifactDigest: prompt.artifactDigest,
                adapterId: runtime.adapterId,
                modelManifestDigest: runtime.modelManifestDigest,
                runtimeDigest: runtime.runtimeDigest,
                companionInstanceId: runtime.companionInstanceId,
                inferenceAttemptId: this.mintMaskAttemptId()
            }),
            rgb: Object.freeze({
                rgbDigest: rgb.digest,
                width: rgb.width,
                height: rgb.height,
                artifact: copyRgb(rgb)
            }),
            prompt: copyPrompt(prompt)
        });

        let result;
        try {
            result = await inferImageInstanceMask(this.maskProvider, request);
        } catch (error) {
            if (!this.isRunCurrent(run) || !this.views.includes(view)) {
                return;
            }
            this.failViewMask(
                view,
                errorMessage(
                    error,
                    'AI Select automatic Mask production failed.'
                )
            );
            return;
        }
        if (!this.isRunCurrent(run) || !this.views.includes(view)) {
            return;
        }
        if (result.previousLogitsRefs !== undefined) {
            this.failViewMask(
                view,
                'Generated View automatic acquisition must not return previous-logits refinement state.'
            );
            return;
        }
        if (result.masks.length === 0) {
            view.maskStatus = 'unavailable';
            view.maskErrorMessage =
                'The SAM 3 Image model returned no usable instance Mask for this View.';
            // Semantic unavailability is an unsuccessful replacement, not a
            // Stable Mask publication. Preserve a current Stable revision
            // and its Participation/Evidence inputs when one exists.
            this.excludeWithoutCurrentStableMask(view);
            this.publish();
            return;
        }
        const chosenMask = result.masks[0];
        const reviewRequest: ImageInstanceMaskReviewRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: requestBinding.dependencyToken.splatId
            }),
            viewId: view.viewId,
            rgb: copyRgb(rgb),
            prompt: copyPrompt(prompt),
            inferenceResultDigest: result.resultDigest,
            chosenMask,
            reviewAttemptId: this.mintReviewAttemptId(),
            reviewPolicyVersion: aiSelectViewAssessmentPolicyVersion
        });
        let reviewResponse: ImageInstanceMaskReviewResponse;
        try {
            reviewResponse =
                await this.reviewProvider.reviewImageInstanceMask(
                    reviewRequest
                );
        } catch (error) {
            if (!this.isRunCurrent(run) || !this.views.includes(view)) {
                return;
            }
            this.failViewMask(
                view,
                errorMessage(
                    error,
                    'AI Select Generated View Mask Review failed.'
                )
            );
            return;
        }
        if (!this.isRunCurrent(run) || !this.views.includes(view)) {
            return;
        }
        if (
            !isImageInstanceMaskReviewResponse(reviewResponse) ||
            !imageInstanceMaskReviewResponseMatchesRequest(
                reviewResponse,
                reviewRequest
            )
        ) {
            this.failViewMask(
                view,
                'The Selection Service Companion returned an invalid or stale Generated View Mask Review binding.'
            );
            return;
        }
        if (reviewResponse.assessment.status === 'failed') {
            // A failed Review publishes no replacement Stable Mask. Retain
            // any previous Stable revision and the assessment bound to it so
            // a failed refresh cannot silently change Candidate inputs.
            if (this.currentStableMask(view) === null) {
                view.assessment = copyAssessment(reviewResponse.assessment);
                this.excludeWithoutCurrentStableMask(view);
            }
            view.maskStatus = 'failed';
            view.maskErrorMessage =
                'Mask Review rejected the automatic Mask; no Stable Mask was published.';
            this.publish();
            return;
        }
        try {
            const current = this.maskRegistry.viewState(
                view.viewId,
                rgb.digest
            ).stableMask;
            if (current?.status === 'user-confirmed') {
                return;
            }
            const publication = createImageInstanceMaskPublicationCommand({
                schemaVersion: 1,
                targetContextId: requestBinding.targetContextId,
                contextRevision: requestBinding.contextRevision,
                viewId: view.viewId,
                rgbDigest: rgb.digest,
                promptArtifactDigest: prompt.artifactDigest,
                inferenceResultDigest: result.resultDigest,
                chosenMaskDigest: chosenMask.digest,
                review: reviewResponse.assessment,
                currentStableAuthority: 'automatic',
                ...(current === null
                    ? {}
                    : { currentStableMaskId: current.maskId }),
                publicationPolicyDigest: generatedViewPublicationPolicyDigest,
                publicationAttemptId: this.mintPublicationAttemptId()
            });
            if (
                !imageInstanceMaskPublicationCommandMatchesArtifacts(
                    publication,
                    { prompt, result }
                )
            ) {
                throw new Error(
                    'AI Select rejected an incoherent Image Instance Mask publication command.'
                );
            }
            const defaults = automaticAssessmentDefaults(
                reviewResponse.assessment
            );
            this.maskRegistry.publishAutoStable({
                viewId: view.viewId,
                rgbDigest: rgb.digest,
                artifact: chosenMask,
                source: 'single-frame-sam',
                status: defaults.stableMaskStatus
            });
            const stableChanged =
                current?.artifact.digest !== chosenMask.digest;
            const previousParticipation = view.participation;
            view.stableMaskDigest = chosenMask.digest;
            view.assessment = copyAssessment(reviewResponse.assessment);
            view.participation = defaultViewParticipation({
                reviewStatus: reviewResponse.assessment.status,
                authority: 'automatic'
            });
            view.maskStatus = 'ready';
            if (stableChanged) {
                this.dirtyState.markStableMaskPublished(view.viewId);
            } else if (previousParticipation !== view.participation) {
                this.dirtyState.markParticipationChanged(view.viewId);
            }
        } catch (error) {
            this.failViewMask(
                view,
                errorMessage(
                    error,
                    'AI Select automatic Mask publication failed.'
                )
            );
            return;
        }
        this.publish();
    }

    private failPlanning(message: string): void {
        this.plannerStatus = 'failed';
        this.plannerErrorMessage = message;
        this.publish();
    }

    private failViewRender(view: GeneratedViewRecord, message: string): void {
        view.renderStatus = 'failed';
        view.renderErrorMessage = message;
        view.promptStatus = 'none';
        view.promptDiagnostics = undefined;
        view.promptErrorMessage = undefined;
        view.prompt = undefined;
        view.promptModelManifestDigest = undefined;
        view.promptRuntimeDigest = undefined;
        view.promptCompanionInstanceId = undefined;
        view.maskStatus = 'none';
        view.assessment = undefined;
        view.participation = 'excluded';
        this.publish();
    }

    /** A prompt-synthesis failure is distinct from Mask inference failure. */
    private failViewPrompt(view: GeneratedViewRecord, message: string): void {
        view.prompt = undefined;
        view.promptModelManifestDigest = undefined;
        view.promptRuntimeDigest = undefined;
        view.promptCompanionInstanceId = undefined;
        view.promptStatus = 'failed';
        view.promptDiagnostics = undefined;
        view.promptErrorMessage = message;
        this.dirtyState.markPromptDirty(view.viewId);
        this.publish();
    }

    /**
     * A Mask production failure preserves the prior Stable Mask, its
     * assessment, and Participation authority (Final Spec v1.3 §§13, 24);
     * only the latest-attempt status and diagnostic change.
     */
    private failViewMask(view: GeneratedViewRecord, message: string): void {
        view.maskStatus = 'failed';
        view.maskErrorMessage = message;
        this.publish();
    }

    /** The current registry revision, never a stale RGB-bound Stable Mask. */
    private currentStableMask(
        view: GeneratedViewRecord
    ): MaskAnnotation | null {
        return view.rgb === undefined
            ? null
            : this.maskRegistry.viewState(view.viewId, view.rgb.digest)
                  .stableMask;
    }

    /**
     * Failed Prompt/Mask replacements retain a prior Stable revision. Only a
     * View with no current Stable Mask defaults to Excluded; if an external
     * lifecycle transition had marked it Included, propagate that real
     * Participation change through Evidence/Lift/Candidate state.
     */
    private excludeWithoutCurrentStableMask(view: GeneratedViewRecord): void {
        if (
            this.currentStableMask(view) === null &&
            view.participation !== 'excluded'
        ) {
            view.participation = 'excluded';
            this.dirtyState.markParticipationChanged(view.viewId);
        }
    }

    private requireView(viewId: string): GeneratedViewRecord {
        const view = this.views.find((entry) => entry.viewId === viewId);
        if (view === undefined) {
            throw new Error('AI Select requires a known Generated AIView.');
        }
        return view;
    }

    private requireTargetActive(): void {
        if (!this.anchor.isTargetActive()) {
            throw new Error(
                'AI Select target-dependent editing is unavailable while the current target is suspended.'
            );
        }
    }

    private isRunCurrent(run: number): boolean {
        return (
            this.runOrdinal === run &&
            this.identity !== null &&
            this.requestBinding !== null &&
            this.anchor.acceptsTargetBinding(this.requestBinding)
        );
    }

    private disposeRun(): void {
        if (this.identity === null) {
            return;
        }
        // Rotating the run identity discards every in-flight plan/render/mask
        // result; cancellation is only a resource optimization.
        this.runOrdinal += 1;
        this.identity = null;
        this.confirmed = null;
        this.requestBinding = null;
        for (const view of this.views) {
            this.maskRegistry.disposeView(view.viewId);
            this.evidenceRegistry.disposeView(view.viewId);
        }
        this.views = [];
        this.selectedViewId = null;
        this.geometryHint = null;
        this.keyViewPlans = [];
        this.nextUserViewOrdinal = 0;
        this.nextViewCreationOrdinal = 0;
        this.plannerStatus = 'idle';
        this.plannerErrorMessage = undefined;
        this.dirtyState.reset();
        this.publish();
    }

    private compose(view: GeneratedViewRecord): GeneratedAIView {
        const stableMask =
            view.rgb === undefined
                ? null
                : this.maskRegistry.viewState(view.viewId, view.rgb.digest)
                      .stableMask;
        const stableAssessment =
            view.rgb !== undefined &&
            stableMask !== null &&
            stableMask.status !== 'user-confirmed' &&
            view.assessment?.inputIdentity.rgbDigest === view.rgb.digest &&
            view.assessment.inputIdentity.stableMaskDigest ===
                stableMask.artifact.digest
                ? view.assessment
                : undefined;
        // A failed Review creates no Stable Mask, but its evidence-backed
        // diagnostic remains inspectable. It never replaces the assessment
        // attached to an existing automatic Stable revision for quality.
        const assessment =
            stableAssessment ??
            (view.maskStatus === 'failed' &&
            view.rgb !== undefined &&
            view.assessment?.inputIdentity.rgbDigest === view.rgb.digest
                ? view.assessment
                : undefined);
        // Quality derives from the current Stable Mask authority, not from
        // the latest attempt: a failed refresh over an existing Stable Mask
        // preserves its quality and Participation authority.
        const maskQuality: GeneratedViewMaskQuality =
            stableMask === null
                ? view.renderStatus === 'failed' || view.maskStatus === 'failed'
                    ? 'failed'
                    : 'none'
                : stableMask.status === 'user-confirmed'
                  ? 'user-confirmed'
                  : stableAssessment === undefined
                    ? 'auto-review'
                    : automaticAssessmentDefaults(stableAssessment).maskQuality;
        const participation: AIViewParticipation =
            view.participation === 'included' &&
            (maskQuality === 'auto-good' || maskQuality === 'user-confirmed') &&
            view.renderStatus === 'ready' &&
            stableMask !== null
                ? 'included'
                : 'excluded';
        return Object.freeze({
            viewId: view.viewId,
            creationOrdinal: view.creationOrdinal,
            source: view.source,
            cameraBinding: copyCameraBinding(view.cameraBinding),
            renderStatus: view.renderStatus,
            ...(view.rgb === undefined ? {} : { rgb: copyRgb(view.rgb) }),
            ...(view.rgb === undefined ? {} : { rgbDigest: view.rgb.digest }),
            ...(view.rendererId === undefined
                ? {}
                : { rendererId: view.rendererId }),
            ...(view.renderWorkingSetToken === undefined
                ? {}
                : { renderWorkingSetToken: view.renderWorkingSetToken }),
            ...(view.renderStableGaussianIds === undefined
                ? {}
                : {
                      renderStableGaussianIds: Object.freeze([
                          ...view.renderStableGaussianIds
                      ])
                  }),
            ...(view.renderErrorMessage === undefined
                ? {}
                : { renderErrorMessage: view.renderErrorMessage }),
            participation,
            promptStatus: view.promptStatus,
            ...(view.prompt === undefined
                ? {}
                : { prompt: copyPrompt(view.prompt) }),
            ...(view.promptDiagnostics === undefined
                ? {}
                : {
                      promptDiagnostics: Object.freeze([
                          ...view.promptDiagnostics
                      ])
                  }),
            ...(view.promptErrorMessage === undefined
                ? {}
                : { promptErrorMessage: view.promptErrorMessage }),
            maskStatus: view.maskStatus,
            ...(view.maskErrorMessage === undefined
                ? {}
                : { maskErrorMessage: view.maskErrorMessage }),
            ...(stableMask === null
                ? {}
                : {
                      stableMaskId: stableMask.maskId,
                      stableMaskDigest: stableMask.artifact.digest
                  }),
            maskQuality,
            ...(assessment === undefined
                ? {}
                : { assessment: copyAssessment(assessment) }),
            evidenceStatus: this.evidenceStatusFor(
                view,
                stableMask?.artifact.digest ?? null
            ),
            selected: this.selectedViewId === view.viewId,
            ...(view.planQuality === undefined
                ? {}
                : { planQuality: view.planQuality }),
            ...(view.planReasons === undefined
                ? {}
                : { planReasons: Object.freeze([...view.planReasons]) })
        });
    }

    private evidenceStatusFor(
        view: GeneratedViewRecord,
        stableMaskDigest: string | null
    ): EvidenceStatus {
        const identity: EvidenceDependencyIdentity | null =
            view.rgb === undefined || stableMaskDigest === null
                ? null
                : {
                      viewId: view.viewId,
                      rgbDigest: view.rgb.digest,
                      stableMaskDigest,
                      evidencePolicyDigest: aiSelectEvidencePolicyVersion
                  };
        return this.evidenceRegistry.statusFor(view.viewId, identity).status;
    }

    private enqueue(step: (run: number) => Promise<void>): void {
        const run = this.runOrdinal;
        // Steps own their failure surfaces; the catch-all keeps one defective
        // step from wedging the serial pipeline for the remaining Views.
        this.queue = this.queue.then(() =>
            step(run).catch((error: unknown) => {
                console.error(error);
            })
        );
    }

    private mintGeometryAttemptId(): string {
        if (this.nextGeometryAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select geometry attempt identity cannot advance safely.'
            );
        }
        this.nextGeometryAttemptOrdinal += 1;
        return `target-geometry-hint-attempt-${this.nextGeometryAttemptOrdinal}`;
    }

    private mintPlanAttemptId(): string {
        if (this.nextPlanAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select plan attempt identity cannot advance safely.'
            );
        }
        this.nextPlanAttemptOrdinal += 1;
        return `local-key-view-plan-attempt-${this.nextPlanAttemptOrdinal}`;
    }

    private mintRenderAttemptId(): string {
        if (this.nextRenderAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select render attempt identity cannot advance safely.'
            );
        }
        this.nextRenderAttemptOrdinal += 1;
        return `generated-view-render-attempt-${this.nextRenderAttemptOrdinal}`;
    }

    private mintUserViewId(): string {
        if (this.nextUserViewOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error('AI Select View identity cannot advance safely.');
        }
        this.nextUserViewOrdinal += 1;
        const viewId = `user-view-${this.nextUserViewOrdinal}`;
        // Fail closed rather than collide with any planner-owned identity.
        if (this.views.some((view) => view.viewId === viewId)) {
            return this.mintUserViewId();
        }
        return viewId;
    }

    private mintPromptSynthesisAttemptId(): string {
        if (this.nextPromptSynthesisAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select Prompt synthesis attempt identity cannot advance safely.'
            );
        }
        this.nextPromptSynthesisAttemptOrdinal += 1;
        return `generated-view-prompt-synthesis-attempt-${this.nextPromptSynthesisAttemptOrdinal}`;
    }

    private mintMaskAttemptId(): string {
        if (this.nextMaskAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select mask attempt identity cannot advance safely.'
            );
        }
        this.nextMaskAttemptOrdinal += 1;
        return `generated-view-inference-attempt-${this.nextMaskAttemptOrdinal}`;
    }

    private mintReviewAttemptId(): string {
        if (this.nextReviewAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select Mask Review attempt identity cannot advance safely.'
            );
        }
        this.nextReviewAttemptOrdinal += 1;
        return `generated-view-mask-review-attempt-${this.nextReviewAttemptOrdinal}`;
    }

    private mintPublicationAttemptId(): string {
        if (this.nextPublicationAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select Mask publication attempt identity cannot advance safely.'
            );
        }
        this.nextPublicationAttemptOrdinal += 1;
        return `generated-view-mask-publication-attempt-${this.nextPublicationAttemptOrdinal}`;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
