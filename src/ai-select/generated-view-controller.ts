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
    areCameraBindingsEqual,
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
    /** Stop preserves completed Views; queued pipeline steps skip while set. */
    readonly generationStopped: boolean;
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
    /** The newest accepted plan to use for a future Prompt synthesis. */
    nextPromptPlanDigest?: string;
    planQuality?: 'usable' | 'limited';
    planReasons?: readonly string[];
    renderStatus: GeneratedViewRenderStatus;
    rgb?: AnchorRgbArtifact;
    rendererId?: 'gsplat';
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

/**
 * One planner-owned View in the making; user-added Views (Ticket 11) survive
 * planner lifecycle operations by identity.
 */
interface ViewIdentityShape {
    readonly viewId: string;
    readonly source: AIViewSource;
    readonly cameraBinding: CameraBinding;
}

/**
 * The Generate More collision gate: a new batch may never reuse an existing
 * View identity, planner-owned or user-owned.
 */
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

export interface RegenerateMerge {
    /** Existing planner-owned records kept untouched (identical CameraBinding). */
    readonly preserved: readonly ViewIdentityShape[];
    /** Existing planner-owned viewIds the new plan no longer publishes. */
    readonly disposedViewIds: readonly string[];
    /** Planned Views that are new or whose CameraBinding changed. */
    readonly added: readonly PlannedKeyView[];
    /** Planned viewIds colliding with user-owned Views: fail closed. */
    readonly conflictingViewIds: readonly string[];
}

/**
 * The Regenerate merge: planner-owned Views are replaced by the new batch,
 * but a View whose exact identity (viewId + CameraBinding) survives keeps its
 * completed RGB/Mask artifacts; user-owned Views are never touched.
 */
export const planRegenerateMerge = (
    existing: readonly ViewIdentityShape[],
    planned: readonly PlannedKeyView[]
): RegenerateMerge => {
    const plannerOwned = existing.filter(
        (view) => view.source !== 'user-added'
    );
    const userOwnedIds = new Set(
        existing
            .filter((view) => view.source === 'user-added')
            .map((view) => view.viewId)
    );
    const preserved: ViewIdentityShape[] = [];
    const added: PlannedKeyView[] = [];
    const conflictingViewIds: string[] = [];
    const seenPlannedIds = new Set<string>();
    for (const view of planned) {
        if (userOwnedIds.has(view.viewId) || seenPlannedIds.has(view.viewId)) {
            conflictingViewIds.push(view.viewId);
            continue;
        }
        seenPlannedIds.add(view.viewId);
        const current = plannerOwned.find(
            (entry) => entry.viewId === view.viewId
        );
        if (
            current !== undefined &&
            areCameraBindingsEqual(current.cameraBinding, view.cameraBinding)
        ) {
            preserved.push(current);
        } else {
            added.push(view);
        }
    }
    const preservedIds = new Set(preserved.map((view) => view.viewId));
    return Object.freeze({
        preserved: Object.freeze(preserved),
        disposedViewIds: Object.freeze(
            plannerOwned
                .map((view) => view.viewId)
                .filter((viewId) => !preservedIds.has(viewId))
        ),
        added: Object.freeze(added),
        conflictingViewIds: Object.freeze(conflictingViewIds)
    });
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
    private nextBatchOrdinal = 0;
    private generationStopped = false;
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
            generationStopped: this.generationStopped,
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
     * A true Retry: a brand-new render attempt for the exact same planned
     * CameraBinding, actually re-executing the authoritative render path —
     * never a replayed failure and never a jittered camera (§8).
     */
    retryViewRender(viewId: string): void {
        const view = this.views.find((entry) => entry.viewId === viewId);
        if (view === undefined) {
            throw new Error(
                'AI Select cannot retry an unknown Generated AIView.'
            );
        }
        if (view.renderStatus !== 'failed') {
            throw new Error(
                'AI Select can retry only a Render Failed Generated AIView.'
            );
        }
        if (!this.isRunCurrent(this.runOrdinal)) {
            throw new Error(
                'AI Select requires the confirmed Current Target Context for a Render Retry.'
            );
        }
        this.enqueue((run) => this.renderAndMaskView(run, viewId, true));
    }

    /**
     * Retry only one static-image inference attempt. It reuses the current
     * bound Prompt artifact and RGB, but mints a new execution identity; it
     * never rerenders or reprojects the target geometry.
     */
    retryViewMask(viewId: string): void {
        this.enqueueViewMaskRefresh(viewId, true);
    }

    /**
     * Explicitly refresh one automatic Mask from its current Prompt artifact.
     * This is deliberately independent from 3D-guided Prompt regeneration:
     * the new inference attempt never reruns planning or synthesis.
     */
    refreshViewMask(viewId: string): void {
        this.enqueueViewMaskRefresh(viewId, false);
    }

    private enqueueViewMaskRefresh(viewId: string, retryOnly: boolean): void {
        const view = this.requireView(viewId);
        if (
            view.renderStatus !== 'ready' ||
            view.rgb === undefined ||
            view.promptStatus !== 'ready' ||
            view.prompt === undefined ||
            view.maskStatus === 'generating' ||
            (retryOnly &&
                view.maskStatus !== 'failed' &&
                view.maskStatus !== 'unavailable')
        ) {
            throw new Error(
                retryOnly
                    ? 'AI Select can retry inference only for a Prompt Ready RGB Ready AIView whose previous result failed or was unavailable.'
                    : 'AI Select can refresh an automatic Mask only for a Prompt Ready RGB Ready AIView that is not already generating.'
            );
        }
        const stable = this.maskRegistry.viewState(
            view.viewId,
            view.rgb.digest
        ).stableMask;
        if (stable?.status === 'user-confirmed') {
            throw new Error(
                'AI Select never replaces a User Confirmed Stable Mask through automatic Mask refresh.'
            );
        }
        const rgb = view.rgb;
        const prompt = view.prompt;
        this.enqueue(async (run) => {
            await this.produceViewMask(run, view, rgb, prompt);
        });
    }

    /**
     * Regenerate the 3D-guided Prompt separately from an inference Retry.
     * This mints a new prompt-synthesis attempt against the same accepted
     * View plan, authoritative RGB, and CameraBinding.
     */
    regenerateViewPrompt(viewId: string): void {
        const view = this.requireView(viewId);
        if (
            view.renderStatus !== 'ready' ||
            view.rgb === undefined ||
            view.localKeyViewPlanDigest === undefined ||
            view.promptStatus === 'none' ||
            view.promptStatus === 'synthesizing'
        ) {
            throw new Error(
                'AI Select can regenerate a Prompt only for a planned RGB Ready AIView.'
            );
        }
        const stable = this.maskRegistry.viewState(
            view.viewId,
            view.rgb.digest
        ).stableMask;
        if (stable?.status === 'user-confirmed') {
            throw new Error(
                'AI Select never replaces a User Confirmed Stable Mask through automatic Prompt regeneration.'
            );
        }
        this.enqueue(async (run) => {
            await this.synthesizeViewPrompt(run, view);
        });
    }

    /**
     * Confirm one Auto Review Stable Mask without changing its pixels. This
     * rotates the Stable Mask revision to User Confirmed and grants the §14.2
     * User Confirmed default Participation; the original assessment remains
     * inspectable.
     */
    confirmReviewAsIs(viewId: string): void {
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
     * resumes stopped or completed local generation: the View renders
     * authoritative RGB on its own explicit pipeline step and then waits —
     * Mask authoring is the user's explicit 04C Prompt/Manual Draw choice,
     * never the Route-B planner pipeline (Final Spec v1.3 §§5, 17–18).
     */
    addUserView(cameraBinding: CameraBinding): string {
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
        // forceRun: an explicit user action always re-executes the render
        // path, even while planner-owned generation is stopped.
        this.enqueue((run) => this.renderAndMaskView(run, viewId, true));
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

    /** Re-run automatic planning after a planner failure; Views are kept. */
    retryPlanning(): void {
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

    /**
     * Stop preserves every completed View; queued pipeline steps skip while
     * stopped, and in-flight identity-bound results may still publish
     * (cancellation is only a resource optimization).
     */
    stopGeneration(): void {
        if (this.plannerStatus !== 'active' || this.generationStopped) {
            throw new Error(
                'AI Select can stop generation only while planning is active.'
            );
        }
        this.generationStopped = true;
        this.publish();
    }

    /**
     * Generate More appends one bounded local batch without dirtying any
     * completed View. A batch failure keeps the planner active with an
     * actionable diagnostic; the next success clears it.
     */
    generateMoreViews(): void {
        if (this.identity === null || this.plannerStatus !== 'active') {
            throw new Error(
                'AI Select can generate more Views only while planning is active.'
            );
        }
        if (this.geometryHint === null) {
            throw new Error(
                'AI Select requires the Target Geometry Hint before Generate More.'
            );
        }
        this.generationStopped = false;
        this.plannerErrorMessage = undefined;
        this.publish();
        this.enqueue((run) => this.planMoreViews(run));
    }

    /**
     * Regenerate replaces planner-owned Views with a fresh batch 0 from the
     * same bound Target Geometry Hint, preserving user-owned Views and any
     * planner View whose exact identity (viewId + CameraBinding) survives —
     * its completed RGB/Mask artifacts remain valid. The new batch is
     * validated before any current View is disposed.
     */
    regenerateViews(): void {
        if (this.identity === null || this.plannerStatus !== 'active') {
            throw new Error(
                'AI Select can regenerate Views only while planning is active.'
            );
        }
        if (this.geometryHint === null) {
            throw new Error(
                'AI Select requires the Target Geometry Hint before Regenerate.'
            );
        }
        this.generationStopped = false;
        this.plannerErrorMessage = undefined;
        this.dirtyState.markLocalKeyViewPlanDirty();
        this.publish();
        this.enqueue((run) => this.regeneratePlan(run));
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
        this.nextBatchOrdinal = 1;
        this.generationStopped = false;
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
            nextPromptPlanDigest: localKeyViewPlanDigest,
            planQuality: planned.quality,
            planReasons: planned.reasons,
            renderStatus: 'pending',
            promptStatus: 'none',
            maskStatus: 'none',
            participation: 'excluded'
        };
    }

    /** Generate More appends one bounded batch; completed Views never move. */
    private async planMoreViews(run: number): Promise<void> {
        const confirmed = this.confirmed;
        const hint = this.geometryHint;
        if (!this.isRunCurrent(run) || confirmed === null || hint === null) {
            return;
        }
        let plan: LocalKeyViewPlan;
        try {
            const planned = await this.requestPlanBatch(
                run,
                confirmed,
                hint,
                this.nextBatchOrdinal
            );
            if (planned === null || !this.isRunCurrent(run)) {
                return;
            }
            plan = planned;
        } catch (error) {
            if (!this.isRunCurrent(run)) {
                return;
            }
            this.plannerErrorMessage = errorMessage(
                error,
                'AI Select could not generate more local Key Views.'
            );
            this.publish();
            return;
        }
        const collisions = findKeyViewIdCollisions(
            this.views,
            plan.orderedViews
        );
        if (collisions.length > 0) {
            this.plannerErrorMessage = `The Selection Service Companion reused View identity ${collisions.join(', ')}; the batch was rejected.`;
            this.publish();
            return;
        }
        this.views = [
            ...this.views,
            ...plan.orderedViews.map((planned) =>
                this.recordForPlannedView(planned, plan.artifactDigest)
            )
        ];
        this.keyViewPlans = [...this.keyViewPlans, plan];
        this.nextBatchOrdinal += 1;
        this.generationStopped = false;
        this.plannerErrorMessage = undefined;
        this.plannerStatus = 'active';
        this.publish();
        this.enqueuePendingViewRenders();
    }

    /**
     * Regenerate plans a fresh batch 0 first, then applies the merge:
     * preserved identities keep their completed artifacts, dropped
     * planner-owned Views are disposed, and a planning failure keeps every
     * current View inspectable.
     */
    private async regeneratePlan(run: number): Promise<void> {
        const confirmed = this.confirmed;
        const hint = this.geometryHint;
        if (!this.isRunCurrent(run) || confirmed === null || hint === null) {
            return;
        }
        let plan: LocalKeyViewPlan;
        try {
            const planned = await this.requestPlanBatch(
                run,
                confirmed,
                hint,
                0
            );
            if (planned === null || !this.isRunCurrent(run)) {
                return;
            }
            plan = planned;
        } catch (error) {
            if (!this.isRunCurrent(run)) {
                return;
            }
            this.plannerErrorMessage = errorMessage(
                error,
                'AI Select could not regenerate the local Key Views.'
            );
            this.publish();
            return;
        }
        const merge = planRegenerateMerge(this.views, plan.orderedViews);
        if (merge.conflictingViewIds.length > 0) {
            this.plannerErrorMessage = `The Selection Service Companion reused user-owned View identity ${merge.conflictingViewIds.join(', ')}; the batch was rejected.`;
            this.publish();
            return;
        }
        const disposed = new Set(merge.disposedViewIds);
        const disposedViews = this.views.filter((view) =>
            disposed.has(view.viewId)
        );
        for (const view of disposedViews) {
            this.maskRegistry.disposeView(view.viewId);
            this.evidenceRegistry.disposeView(view.viewId);
        }
        if (this.selectedViewId !== null && disposed.has(this.selectedViewId)) {
            this.selectedViewId = null;
        }
        const preservedIds = new Set(
            merge.preserved.map((view) => view.viewId)
        );
        const plannerViews = plan.orderedViews.map((planned) => {
            if (preservedIds.has(planned.viewId)) {
                const current = this.views.find(
                    (view) => view.viewId === planned.viewId
                );
                if (current !== undefined) {
                    current.nextPromptPlanDigest = plan.artifactDigest;
                    current.planQuality = planned.quality;
                    current.planReasons = planned.reasons;
                    // A completed artifact remains bound to its original
                    // Prompt plan. The replacement plan becomes active only
                    // for a later explicit Prompt synthesis.
                    if (current.prompt === undefined) {
                        current.localKeyViewPlanDigest = plan.artifactDigest;
                    }
                    // A failed or unavailable prior inference cannot Retry
                    // against the replaced plan. Preserve its RGB/Stable
                    // state, but require distinct Prompt regeneration.
                    if (
                        current.maskStatus === 'failed' ||
                        current.maskStatus === 'unavailable'
                    ) {
                        current.prompt = undefined;
                        current.promptModelManifestDigest = undefined;
                        current.promptRuntimeDigest = undefined;
                        current.promptCompanionInstanceId = undefined;
                        current.localKeyViewPlanDigest = plan.artifactDigest;
                        current.promptStatus = 'failed';
                        current.promptDiagnostics = undefined;
                        current.promptErrorMessage =
                            'The Local Key-View Plan changed; regenerate the 3D-guided Prompt before retrying inference.';
                    }
                    return current;
                }
            }
            return this.recordForPlannedView(planned, plan.artifactDigest);
        });
        this.views = [
            ...plannerViews,
            ...this.views.filter((view) => view.source === 'user-added')
        ];
        this.keyViewPlans = [plan];
        this.nextBatchOrdinal = 1;
        this.generationStopped = false;
        this.plannerErrorMessage = undefined;
        this.plannerStatus = 'active';
        for (const view of disposedViews) {
            if (view.participation === 'included') {
                this.dirtyState.markParticipationChanged(view.viewId);
            }
            this.dirtyState.forgetView(view.viewId);
        }
        this.dirtyState.markLocalKeyViewPlanReady(
            plannerViews.map((view) => view.viewId)
        );
        this.publish();
        this.enqueuePendingViewRenders();
    }

    /**
     * Queue render+Mask for every planner-owned View still waiting for RGB:
     * new batches, and pending Views left behind by Stop. Failed Views keep
     * their explicit-Retry semantics and are never auto-restarted here.
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
     * other completed or pending View survives untouched. Queued pipeline
     * steps skip while generation is stopped; an explicit user Retry passes
     * `forceRun` and always re-executes the render path.
     */
    private async renderAndMaskView(
        run: number,
        viewId: string,
        forceRun = false
    ): Promise<void> {
        const view = this.views.find((entry) => entry.viewId === viewId);
        const requestBinding = this.requestBinding;
        if (
            !this.isRunCurrent(run) ||
            view === undefined ||
            requestBinding === null ||
            (this.generationStopped && !forceRun)
        ) {
            return;
        }
        // A queued pipeline step only ever starts a pending View; a duplicate
        // queue entry after Stop/Generate More or an already-running View is
        // discarded. Explicit user Retry passes forceRun for a failed View.
        if (!forceRun && view.renderStatus !== 'pending') {
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
        // A Regenerate disposal mid-flight orphans the record; its late
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
     * Route B prompt generation is a distinct phase from inference Retry. It
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
     * Publish a regenerated Prompt without implicitly starting SAM. The
     * initial acquisition pipeline explicitly composes this with
     * `produceViewMask`; the user-facing Prompt action intentionally does
     * not, so refresh remains an explicit second operation.
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
        const planDigest =
            view.nextPromptPlanDigest ?? view.localKeyViewPlanDigest;
        const plan = this.keyViewPlans.find(
            (candidate) => candidate.artifactDigest === planDigest
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
            view.nextPromptPlanDigest = response.localKeyViewPlanDigest;
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
        view.nextPromptPlanDigest = prompt.localKeyViewPlanDigest;
        view.promptModelManifestDigest = response.modelManifestDigest;
        view.promptRuntimeDigest = response.runtimeDigest;
        view.promptCompanionInstanceId = response.companionInstanceId;
        view.promptStatus = 'ready';
        view.promptDiagnostics = Object.freeze([...response.diagnostics]);
        view.promptErrorMessage = undefined;
        this.dirtyState.markPromptRegenerated(view.viewId);
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
                'The locked SAM 3 Image runtime changed after Prompt synthesis; regenerate the Prompt before automatic Mask inference.'
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
        this.nextBatchOrdinal = 0;
        this.nextUserViewOrdinal = 0;
        this.nextViewCreationOrdinal = 0;
        this.generationStopped = false;
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
