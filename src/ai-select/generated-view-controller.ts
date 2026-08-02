import type { PackedSceneSnapshot } from '../scene-snapshot-binary';
import type { AIViewParticipation, AIViewSource } from './ai-view';
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
    aiSelectEvidencePolicyVersion,
    type EvidenceDependencyIdentity,
    type EvidenceStatus,
    type PerViewEvidenceRegistry
} from './evidence-state';
import {
    generatedViewMaskResponseMatchesRequest,
    isAIViewRenderResponse,
    isGeneratedViewMaskResponse,
    viewRenderResponseMatchesRequest,
    type AIViewRenderRequest,
    type AIViewRenderResponse,
    type AISelectGeneratedViewMaskProvider,
    type AISelectViewRenderer,
    type GeneratedViewMaskRequest,
    type GeneratedViewMaskResponse
} from './generated-view-service';
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
import type { MaskAnnotationRegistry } from './mask-registry';
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
    defaultViewParticipation,
    type ReviewReason,
    type ViewAssessmentResult
} from './view-assessment';

export type GeneratedViewRenderStatus =
    'pending' | 'rendering' | 'ready' | 'failed';

export type GeneratedViewMaskStatus =
    'none' | 'generating' | 'ready' | 'failed';

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
    readonly source: AIViewSource;
    readonly cameraBinding: CameraBinding;
    readonly renderStatus: GeneratedViewRenderStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly rgbDigest?: string;
    readonly rendererId?: 'gsplat';
    readonly renderErrorMessage?: string;
    readonly participation: AIViewParticipation;
    readonly maskStatus: GeneratedViewMaskStatus;
    readonly maskErrorMessage?: string;
    readonly stableMaskId?: string;
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
    readonly maskProvider: AISelectGeneratedViewMaskProvider;
    readonly getModelManifestDigest?: () => string | null;
    /**
     * The additive Companion capability gate: an older Companion without
     * Target Geometry and local Key-View planning keeps the Anchor flow
     * usable, and planning fails closed with an actionable diagnostic instead
     * of a transport 404.
     */
    readonly supportsGeneratedViews?: () => boolean;
}

interface GeneratedViewRecord {
    readonly viewId: string;
    readonly source: AIViewSource;
    readonly cameraBinding: CameraBinding;
    readonly planQuality?: 'usable' | 'limited';
    readonly planReasons?: readonly string[];
    renderStatus: GeneratedViewRenderStatus;
    rgb?: AnchorRgbArtifact;
    rendererId?: 'gsplat';
    renderErrorMessage?: string;
    maskStatus: GeneratedViewMaskStatus;
    maskErrorMessage?: string;
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
    private readonly geometryHints: AISelectTargetGeometryProvider;
    private readonly planner: AISelectLocalKeyViewPlanner;
    private readonly renderer: AISelectViewRenderer;
    private readonly maskProvider: AISelectGeneratedViewMaskProvider;
    private readonly getModelManifestDigest: () => string | null;
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
    private nextMaskAttemptOrdinal = 0;

    constructor(options: AISelectGeneratedViewControllerOptions) {
        this.anchor = options.anchor;
        this.maskRegistry = options.maskRegistry;
        this.evidenceRegistry = options.evidenceRegistry;
        this.geometryHints = options.geometryHints;
        this.planner = options.planner;
        this.renderer = options.renderer;
        this.maskProvider = options.maskProvider;
        this.getModelManifestDigest =
            options.getModelManifestDigest ?? (() => null);
        this.supportsGeneratedViews =
            options.supportsGeneratedViews ?? (() => true);
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
            generationStopped: this.generationStopped
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

    /** Retry only automatic Mask production; the valid RGB/View survives. */
    retryViewMask(viewId: string): void {
        const view = this.requireView(viewId);
        if (
            view.renderStatus !== 'ready' ||
            view.rgb === undefined ||
            view.maskStatus !== 'failed'
        ) {
            throw new Error(
                'AI Select can retry only a Mask Failed RGB Ready AIView.'
            );
        }
        const rgb = view.rgb;
        this.enqueue(async (run) => {
            const snapshot = this.anchor.getAnchorSnapshot();
            if (snapshot === null) {
                this.failViewMask(
                    view,
                    'AI Select requires the confirmed Anchor Scene Snapshot before a Mask Retry.'
                );
                return;
            }
            await this.produceViewMask(run, view, rgb, snapshot);
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
        view.participation = defaultViewParticipation({
            reviewStatus: view.assessment.status,
            authority: 'user-confirmed'
        });
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
        view.participation = participation;
        this.publish();
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
        for (const view of this.views) {
            if (view.source !== 'user-added') {
                this.maskRegistry.disposeView(view.viewId);
                this.evidenceRegistry.disposeView(view.viewId);
            }
        }
        const userOwned = this.views.filter(
            (view) => view.source === 'user-added'
        );
        this.views = [
            ...plan.orderedViews.map((planned) =>
                this.recordForPlannedView(planned)
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
    }

    private recordForPlannedView(planned: PlannedKeyView): GeneratedViewRecord {
        return {
            viewId: planned.viewId,
            source: 'auto-generated',
            cameraBinding: copyCameraBinding(planned.cameraBinding),
            planQuality: planned.quality,
            planReasons: planned.reasons,
            renderStatus: 'pending',
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
                this.recordForPlannedView(planned)
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
        for (const viewId of disposed) {
            this.maskRegistry.disposeView(viewId);
            this.evidenceRegistry.disposeView(viewId);
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
                    return current;
                }
            }
            return this.recordForPlannedView(planned);
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
        view.renderStatus = 'ready';
        view.rgb = copyRgb(response.rgb);
        view.rendererId = response.rendererId;
        this.publish();
        await this.produceViewMask(run, view, view.rgb, snapshot);
    }

    private async produceViewMask(
        run: number,
        view: GeneratedViewRecord,
        rgb: AnchorRgbArtifact,
        snapshot: PackedSceneSnapshot
    ): Promise<void> {
        const confirmed = this.confirmed;
        const requestBinding = this.requestBinding;
        if (
            !this.isRunCurrent(run) ||
            confirmed === null ||
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
        view.maskStatus = 'generating';
        view.maskErrorMessage = undefined;
        this.publish();
        const modelManifestDigest = this.getModelManifestDigest();
        if (modelManifestDigest === null || modelManifestDigest.length === 0) {
            this.failViewMask(
                view,
                'AI Select requires a configured Model Manifest before automatic Mask production.'
            );
            return;
        }
        const request: GeneratedViewMaskRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: requestBinding.dependencyToken.splatId
            }),
            snapshot,
            sceneId: confirmed.sceneId,
            sceneVersion: confirmed.sceneVersion,
            viewId: view.viewId,
            viewCameraBinding: copyCameraBinding(view.cameraBinding),
            maskAttemptId: this.mintMaskAttemptId(),
            rgb: copyRgb(rgb),
            anchor: Object.freeze({
                cameraBinding: copyCameraBinding(confirmed.cameraBinding),
                rgbDigest: confirmed.rgbDigest,
                stableMask: confirmed.stableMask.artifact
            }),
            modelManifestDigest
        });

        let response: GeneratedViewMaskResponse;
        try {
            response =
                await this.maskProvider.produceGeneratedViewMask(request);
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
        if (
            !isGeneratedViewMaskResponse(response) ||
            !generatedViewMaskResponseMatchesRequest(response, request)
        ) {
            this.failViewMask(
                view,
                'The Selection Service Companion returned an invalid or stale Generated View Mask binding.'
            );
            return;
        }
        try {
            // Atomic Stable Mask publication: Evidence derives missing/dirty
            // by identity; no formal Lift is triggered here.
            const defaults = automaticAssessmentDefaults(response.assessment);
            this.maskRegistry.publishAutoStable({
                viewId: view.viewId,
                rgbDigest: rgb.digest,
                artifact: response.mask,
                source: 'propagated',
                status: defaults.stableMaskStatus
            });
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
        view.assessment = copyAssessment(response.assessment);
        view.participation = defaultViewParticipation({
            reviewStatus: response.assessment.status,
            authority: 'automatic'
        });
        view.maskStatus = 'ready';
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
        view.maskStatus = 'none';
        view.assessment = undefined;
        view.participation = 'excluded';
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
        this.generationStopped = false;
        this.plannerStatus = 'idle';
        this.plannerErrorMessage = undefined;
        this.publish();
    }

    private compose(view: GeneratedViewRecord): GeneratedAIView {
        const stableMask =
            view.rgb === undefined
                ? null
                : this.maskRegistry.viewState(view.viewId, view.rgb.digest)
                      .stableMask;
        const assessment =
            view.rgb !== undefined &&
            stableMask !== null &&
            stableMask.status !== 'user-confirmed' &&
            view.assessment?.inputIdentity.rgbDigest === view.rgb.digest &&
            view.assessment.inputIdentity.stableMaskDigest ===
                stableMask.artifact.digest
                ? view.assessment
                : undefined;
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
                  : assessment === undefined
                    ? 'auto-review'
                    : automaticAssessmentDefaults(assessment).maskQuality;
        const participation: AIViewParticipation =
            view.participation === 'included' &&
            (maskQuality === 'auto-good' || maskQuality === 'user-confirmed') &&
            view.renderStatus === 'ready' &&
            stableMask !== null
                ? 'included'
                : 'excluded';
        return Object.freeze({
            viewId: view.viewId,
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
            maskStatus: view.maskStatus,
            ...(view.maskErrorMessage === undefined
                ? {}
                : { maskErrorMessage: view.maskErrorMessage }),
            ...(stableMask === null ? {} : { stableMaskId: stableMask.maskId }),
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

    private mintMaskAttemptId(): string {
        if (this.nextMaskAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select mask attempt identity cannot advance safely.'
            );
        }
        this.nextMaskAttemptOrdinal += 1;
        return `generated-view-mask-attempt-${this.nextMaskAttemptOrdinal}`;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
