import type { PackedSceneSnapshot } from '../scene-snapshot-binary';
import type { AIViewParticipation, AIViewSource } from './ai-view';
import type {
    AISelectAnchorConfirmationController,
    AISelectAnchorConfirmationState,
    ConfirmedAnchor
} from './anchor-confirmation';
import type { AISelectAnchorController } from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import { copyCameraBinding, type CameraBinding } from './camera-binding';
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
    aiSelectGeneratedViewPlannerVersion,
    generatedViewMaskResponseMatchesRequest,
    generatedViewPlanResponseMatchesRequest,
    isAIViewRenderResponse,
    isGeneratedViewMaskResponse,
    isGeneratedViewPlanResponse,
    viewRenderResponseMatchesRequest,
    type AIViewRenderRequest,
    type AIViewRenderResponse,
    type AISelectGeneratedViewMaskProvider,
    type AISelectGeneratedViewPlanner,
    type AISelectViewRenderer,
    type GeneratedViewMaskRequest,
    type GeneratedViewMaskResponse,
    type GeneratedViewPlanRequest,
    type GeneratedViewPlanResponse
} from './generated-view-service';
import type { MaskAnnotationRegistry } from './mask-registry';
import type { ReviewReason, ViewAssessmentResult } from './view-assessment';

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
 * authority (Final Spec v1.1 §§13, 26).
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
}

export interface AISelectGeneratedViewState {
    readonly plannerStatus: GeneratedViewPlannerStatus;
    readonly plannerErrorMessage?: string;
    readonly views: readonly GeneratedAIView[];
    readonly selectedViewId: string | null;
}

export type AISelectGeneratedViewListener = (
    state: AISelectGeneratedViewState
) => void;

export interface AISelectGeneratedViewControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly confirmation: AISelectAnchorConfirmationController;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly evidenceRegistry: PerViewEvidenceRegistry;
    readonly planner: AISelectGeneratedViewPlanner;
    readonly renderer: AISelectViewRenderer;
    readonly maskProvider: AISelectGeneratedViewMaskProvider;
    readonly getModelManifestDigest?: () => string | null;
    /**
     * The additive Companion capability gate: an older Companion without
     * Generated View planning keeps the Anchor flow usable, and planning
     * fails closed with an actionable diagnostic instead of a transport 404.
     */
    readonly supportsGeneratedViews?: () => boolean;
}

interface GeneratedViewRecord {
    readonly viewId: string;
    readonly cameraBinding: CameraBinding;
    renderStatus: GeneratedViewRenderStatus;
    rgb?: AnchorRgbArtifact;
    rendererId?: 'gsplat';
    renderErrorMessage?: string;
    maskStatus: GeneratedViewMaskStatus;
    maskErrorMessage?: string;
    assessment?: ViewAssessmentResult;
    participation: AIViewParticipation;
    userConfirmed: boolean;
}

const copyRgb = (rgb: AnchorRgbArtifact): AnchorRgbArtifact => {
    return Object.freeze({
        pngBase64: rgb.pngBase64,
        digest: rgb.digest,
        width: rgb.width,
        height: rgb.height
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
                assessment.inputIdentity.assessmentPolicyVersion,
            supportPolicyVersion: assessment.inputIdentity.supportPolicyVersion,
            propagationPolicyVersion:
                assessment.inputIdentity.propagationPolicyVersion
        }),
        ...(assessment.diagnostics === undefined
            ? {}
            : {
                  diagnostics: Object.freeze({
                      foregroundPixels: assessment.diagnostics.foregroundPixels,
                      boundaryContactRatio:
                          assessment.diagnostics.boundaryContactRatio,
                      connectedComponents:
                          assessment.diagnostics.connectedComponents,
                      largestComponentRatio:
                          assessment.diagnostics.largestComponentRatio,
                      observedGaussianCount:
                          assessment.diagnostics.observedGaussianCount,
                      projectedSupportCount:
                          assessment.diagnostics.projectedSupportCount,
                      promptCount: assessment.diagnostics.promptCount
                  })
              })
    });
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
    private readonly planner: AISelectGeneratedViewPlanner;
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
    private queue: Promise<void> = Promise.resolve();
    private nextPlanAttemptOrdinal = 0;
    private nextRenderAttemptOrdinal = 0;
    private nextMaskAttemptOrdinal = 0;

    constructor(options: AISelectGeneratedViewControllerOptions) {
        this.anchor = options.anchor;
        this.maskRegistry = options.maskRegistry;
        this.evidenceRegistry = options.evidenceRegistry;
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
            selectedViewId: this.selectedViewId
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
        this.enqueue((run) => this.renderAndMaskView(run, viewId));
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
     * rotates the Stable Mask revision to User Confirmed and grants Included
     * participation; the original assessment remains inspectable.
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
        view.userConfirmed = true;
        view.participation = 'included';
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
                'The Selection Service Companion does not advertise Generated View planning. Install the compatible locked Companion release, then refresh readiness.'
            );
            return;
        }
        const snapshot = this.anchor.getAnchorSnapshot();
        if (snapshot === null) {
            this.failPlanning(
                'AI Select requires the confirmed Anchor Scene Snapshot before Generated View planning.'
            );
            return;
        }
        const request: GeneratedViewPlanRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({
                splatId: confirmed.dependencyToken.splatId
            }),
            snapshot,
            sceneId: confirmed.sceneId,
            sceneVersion: confirmed.sceneVersion,
            planAttemptId: this.mintPlanAttemptId(),
            anchorCameraBinding: copyCameraBinding(confirmed.cameraBinding),
            anchorRgbDigest: confirmed.rgbDigest,
            anchorStableMask: confirmed.stableMask.artifact,
            plannerPolicyVersion: aiSelectGeneratedViewPlannerVersion
        });

        let response: GeneratedViewPlanResponse;
        try {
            response = await this.planner.planGeneratedViews(request);
        } catch (error) {
            if (!this.isRunCurrent(run)) {
                return;
            }
            this.failPlanning(
                errorMessage(error, 'AI Select Generated View planning failed.')
            );
            return;
        }
        if (!this.isRunCurrent(run)) {
            return;
        }
        if (
            !isGeneratedViewPlanResponse(response) ||
            !generatedViewPlanResponseMatchesRequest(response, request)
        ) {
            this.failPlanning(
                'The Selection Service Companion returned an invalid or stale Generated View plan binding.'
            );
            return;
        }
        this.views = response.views.map((planned) => ({
            viewId: planned.viewId,
            cameraBinding: copyCameraBinding(planned.cameraBinding),
            renderStatus: 'pending',
            maskStatus: 'none',
            participation: 'excluded',
            userConfirmed: false
        }));
        this.plannerStatus = 'active';
        this.publish();
        for (const view of this.views) {
            this.enqueue((stepRun) =>
                this.renderAndMaskView(stepRun, view.viewId)
            );
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
            if (!this.isRunCurrent(run)) {
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
        if (!this.isRunCurrent(run)) {
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
            requestBinding === null
        ) {
            return;
        }
        view.maskStatus = 'generating';
        view.maskErrorMessage = undefined;
        if (!view.userConfirmed) {
            view.assessment = undefined;
            view.participation = 'excluded';
        }
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
            if (!this.isRunCurrent(run)) {
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
        if (!this.isRunCurrent(run)) {
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
            this.maskRegistry.publishAutoStable({
                viewId: view.viewId,
                rgbDigest: rgb.digest,
                artifact: response.mask,
                source: 'propagated',
                status:
                    response.assessment.status === 'good'
                        ? 'auto-good'
                        : 'auto-review'
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
        view.participation =
            response.assessment.status === 'good' ? 'included' : 'excluded';
        view.userConfirmed = false;
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
        view.userConfirmed = false;
        this.publish();
    }

    private failViewMask(view: GeneratedViewRecord, message: string): void {
        view.maskStatus = 'failed';
        view.maskErrorMessage = message;
        view.assessment = undefined;
        view.participation = 'excluded';
        view.userConfirmed = false;
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
        return Object.freeze({
            viewId: view.viewId,
            source: 'auto-generated',
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
            participation: view.participation,
            maskStatus: view.maskStatus,
            ...(view.maskErrorMessage === undefined
                ? {}
                : { maskErrorMessage: view.maskErrorMessage }),
            ...(stableMask === null ? {} : { stableMaskId: stableMask.maskId }),
            maskQuality:
                view.renderStatus === 'failed' || view.maskStatus === 'failed'
                    ? 'failed'
                    : stableMask === null
                      ? 'none'
                      : stableMask.status === 'user-confirmed'
                        ? 'user-confirmed'
                        : view.assessment?.status === 'good'
                          ? 'auto-good'
                          : view.assessment?.status === 'review'
                            ? 'auto-review'
                            : 'failed',
            ...(view.assessment === undefined
                ? {}
                : { assessment: copyAssessment(view.assessment) }),
            evidenceStatus: this.evidenceStatusFor(
                view,
                stableMask?.artifact.digest ?? null
            ),
            selected: this.selectedViewId === view.viewId
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

    private mintPlanAttemptId(): string {
        if (this.nextPlanAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select plan attempt identity cannot advance safely.'
            );
        }
        this.nextPlanAttemptOrdinal += 1;
        return `generated-view-plan-attempt-${this.nextPlanAttemptOrdinal}`;
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
