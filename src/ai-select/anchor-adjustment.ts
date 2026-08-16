import type {
    AISelectAnchorConfirmationController,
    AISelectAnchorConfirmationState,
    ConfirmedAnchor,
    ConfirmAnchorOptions
} from './anchor-confirmation';
import {
    type AISelectAnchorController,
    type AISelectAnchorState,
    type AnchorAdjustmentRenderArtifact
} from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    evaluateAnchorValidation,
    type AnchorValidationResult
} from './anchor-validation';
import {
    assertCameraToWorldMatrix,
    cameraBindingDigest,
    copyCameraBinding,
    withCameraBindingPose,
    type CameraBinding
} from './camera-binding';
import { PerViewEvidenceRegistry } from './evidence-state';
import type { MaskAnnotation } from './mask-annotation';
import { MaskAnnotationRegistry } from './mask-registry';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse,
    PreviousPredictionLogitsRef
} from './mask-service';
import type { PromptAdapterCapabilities, PromptState } from './prompt-state';
import type {
    AISelectSupportProbeProvider,
    AnchorSupportProbeRequest
} from './support-probe';
import {
    AISelectViewMaskSession,
    type AISelectMaskAuthoring
} from './view-mask-session';

export const ANCHOR_ADJUSTMENT_DRAFT_VIEW_ID = 'anchor-adjustment-draft';

export type AnchorAdjustmentStatus = 'current' | 'adjusting' | 'changed';
export type AnchorAdjustmentRenderStatus =
    'idle' | 'rendering' | 'ready' | 'failed';
export type AnchorAdjustmentPoseOutcome = 'unchanged' | 'staged' | 'discarded';

export interface AnchorAdjustmentDraft {
    readonly adjustmentId: string;
    readonly targetContextId: string;
    readonly baselineCameraBindingDigest: string;
    readonly cameraBinding: CameraBinding;
    readonly cameraBindingDigest: string;
    readonly renderStatus: AnchorAdjustmentRenderStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly errorMessage?: string;
}

export interface AISelectAnchorAdjustmentState {
    readonly status: AnchorAdjustmentStatus;
    readonly draft: AnchorAdjustmentDraft | null;
    readonly confirmationStatus: 'idle' | 'validating' | 'failed';
    readonly validation: AnchorValidationResult | null;
    readonly errorMessage?: string;
}

export type AISelectAnchorAdjustmentListener = (
    state: AISelectAnchorAdjustmentState
) => void;

export interface AISelectAnchorAdjustmentControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly confirmation: AISelectAnchorConfirmationController;
    readonly maskProvider: AISelectMaskProvider;
    readonly getModelManifestDigest?: () => string | null;
    readonly getPromptAdapterCapabilities?: () => PromptAdapterCapabilities | null;
    readonly supportProbe: AISelectSupportProbeProvider;
    readonly getStableIdMappingValid?: () => boolean;
    readonly getRenderWorkingSetValid?: () => boolean;
    readonly commitDraft: (input: {
        readonly render: AnchorAdjustmentRenderArtifact;
        readonly stableMask: MaskAnnotation;
    }) => ConfirmedAnchor;
}

interface PendingDraftRender {
    readonly adjustmentId: string;
    readonly cameraBindingDigest: string;
}

interface PendingDraftConfirmation {
    readonly adjustmentId: string;
    readonly cameraBindingDigest: string;
    readonly stableMaskId: string;
    readonly stableMaskDigest: string;
    readonly draftMaskStateRevision: number;
    readonly request: AnchorSupportProbeRequest;
}

const copyRgb = (rgb: AnchorRgbArtifact): AnchorRgbArtifact => {
    return Object.freeze({
        pngBase64: rgb.pngBase64,
        digest: rgb.digest,
        width: rgb.width,
        height: rgb.height
    });
};

const copyDraft = (draft: AnchorAdjustmentDraft): AnchorAdjustmentDraft => {
    return Object.freeze({
        adjustmentId: draft.adjustmentId,
        targetContextId: draft.targetContextId,
        baselineCameraBindingDigest: draft.baselineCameraBindingDigest,
        cameraBinding: copyCameraBinding(draft.cameraBinding),
        cameraBindingDigest: draft.cameraBindingDigest,
        renderStatus: draft.renderStatus,
        ...(draft.rgb === undefined ? {} : { rgb: copyRgb(draft.rgb) }),
        ...(draft.errorMessage === undefined
            ? {}
            : { errorMessage: draft.errorMessage })
    });
};

const poseMatches = (left: CameraBinding, right: CameraBinding): boolean => {
    return (
        left.cameraToWorld.length === right.cameraToWorld.length &&
        left.cameraToWorld.every(
            (value, index) => value === right.cameraToWorld[index]
        )
    );
};

const confirmedIdentity = (confirmed: ConfirmedAnchor): string => {
    return [
        confirmed.targetContextId,
        confirmed.contextRevision.toString(),
        cameraBindingDigest(confirmed.cameraBinding),
        confirmed.rgbDigest,
        confirmed.stableMask.artifact.digest,
        confirmed.dependencyToken.splatId,
        confirmed.dependencyToken.renderStateToken,
        confirmed.dependencyToken.geometryToken,
        confirmed.dependencyToken.gaussianIdentityToken,
        confirmed.dependencyToken.worldTransformToken
    ].join('\u0000');
};

const errorMessage = (error: unknown): string => {
    return error instanceof Error && error.message
        ? error.message
        : 'Changed-Anchor draft rendering failed.';
};

/**
 * Owns the non-destructive changed-Anchor draft. The current confirmed Anchor
 * and every artifact derived from it remain authoritative until a later
 * coordinator validates this draft and performs the atomic cutover.
 */
export class AISelectAnchorAdjustmentController {
    private readonly anchor: AISelectAnchorController;
    private readonly confirmation: AISelectAnchorConfirmationController;
    private readonly supportProbe: AISelectSupportProbeProvider;
    private readonly getStableIdMappingValid: () => boolean;
    private readonly getRenderWorkingSetValid: () => boolean;
    private readonly commitDraft: AISelectAnchorAdjustmentControllerOptions['commitDraft'];
    private readonly listeners = new Set<AISelectAnchorAdjustmentListener>();
    private readonly maskRegistry = new MaskAnnotationRegistry();
    private readonly evidenceRegistry = new PerViewEvidenceRegistry();
    private readonly maskSession: AISelectViewMaskSession;
    readonly mask: AISelectMaskAuthoring;
    private anchorState: AISelectAnchorState = { context: null, anchor: null };
    private confirmationState: AISelectAnchorConfirmationState = {
        validation: null,
        validationStatus: 'idle',
        confirmedAnchor: null
    };
    private status: AnchorAdjustmentStatus = 'current';
    private draft: AnchorAdjustmentDraft | null = null;
    private baseline: ConfirmedAnchor | null = null;
    private baselineIdentity: string | null = null;
    private readyRender: AnchorAdjustmentRenderArtifact | null = null;
    private activeRender: PendingDraftRender | null = null;
    private nextAdjustmentOrdinal = 0;
    private nextCameraRevision = 0;
    private nextSupportProbeAttemptOrdinal = 0;
    private activeConfirmation: PendingDraftConfirmation | null = null;
    private draftMaskStateRevision = 0;
    private confirmationStatus: AISelectAnchorAdjustmentState['confirmationStatus'] =
        'idle';
    private validation: AnchorValidationResult | null = null;
    private confirmationErrorMessage: string | undefined;

    constructor(options: AISelectAnchorAdjustmentControllerOptions) {
        this.anchor = options.anchor;
        this.confirmation = options.confirmation;
        this.supportProbe = options.supportProbe;
        this.getStableIdMappingValid =
            options.getStableIdMappingValid ?? (() => true);
        this.getRenderWorkingSetValid =
            options.getRenderWorkingSetValid ?? (() => true);
        this.commitDraft = options.commitDraft;
        this.maskSession = new AISelectViewMaskSession({
            host: {
                viewId: ANCHOR_ADJUSTMENT_DRAFT_VIEW_ID,
                targetContextId: () => this.draft?.targetContextId ?? null,
                currentRgb: () => this.currentDraftRgb(),
                lockReason: () =>
                    this.readyRender === null
                        ? 'AI Select requires a ready changed-Anchor RGB draft before Mask authoring.'
                        : null,
                createMaskRequest: (
                    promptState: PromptState,
                    proposalAttemptId: string,
                    modelManifestDigest: string,
                    adapterCapabilityDigest: string,
                    proposalPolicyVersion: string,
                    requestOptions: {
                        readonly includeRgbArtifact: boolean;
                        readonly previousLogitsRef?: PreviousPredictionLogitsRef;
                    }
                ): AIViewMaskRequest | null => {
                    const ready = this.readyRender;
                    return ready === null
                        ? null
                        : this.anchor.createAnchorAdjustmentMaskRequest(
                              ready,
                              promptState,
                              proposalAttemptId,
                              modelManifestDigest,
                              adapterCapabilityDigest,
                              proposalPolicyVersion,
                              requestOptions
                          );
                },
                acceptsMaskResponse: (
                    response: MaskResultResponse,
                    request: AIViewMaskRequest
                ): boolean => {
                    const ready = this.readyRender;
                    return (
                        ready !== null &&
                        this.anchor.acceptsAnchorAdjustmentMaskResponse(
                            response,
                            request,
                            ready
                        )
                    );
                }
            },
            maskProvider: options.maskProvider,
            maskRegistry: this.maskRegistry,
            evidenceRegistry: this.evidenceRegistry,
            ...(options.getModelManifestDigest === undefined
                ? {}
                : {
                      getModelManifestDigest: options.getModelManifestDigest
                  }),
            ...(options.getPromptAdapterCapabilities === undefined
                ? {}
                : {
                      getPromptAdapterCapabilities:
                          options.getPromptAdapterCapabilities
                  })
        });
        this.mask = this.maskSession;
        this.maskSession.subscribe(() => {
            this.draftMaskStateRevision += 1;
            const pending = this.activeConfirmation;
            if (
                pending !== null &&
                pending.draftMaskStateRevision !== this.draftMaskStateRevision
            ) {
                // Prompt/Editing intent stays usable while the support probe
                // is pending. Any such revision retires that exact-bound
                // probe so its late response cannot commit obsolete pixels.
                this.activeConfirmation = null;
                this.confirmationStatus = 'failed';
                this.validation = null;
                this.confirmationErrorMessage =
                    'The changed-Anchor Mask changed during validation. Confirm the latest draft again.';
                this.publish();
            }
        });
        this.anchor.subscribe((state) => {
            this.anchorState = state;
            this.discardIfBaselineIsNoLongerCurrent();
        });
        this.confirmation.subscribe((state) => {
            this.confirmationState = state;
            this.discardIfBaselineIsNoLongerCurrent();
        });
    }

    get state(): AISelectAnchorAdjustmentState {
        return Object.freeze({
            status: this.status,
            draft: this.draft === null ? null : copyDraft(this.draft),
            confirmationStatus: this.confirmationStatus,
            validation: this.validation,
            ...(this.confirmationErrorMessage === undefined
                ? {}
                : { errorMessage: this.confirmationErrorMessage })
        });
    }

    subscribe(listener: AISelectAnchorAdjustmentListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    beginAdjustment(): void {
        const confirmed = this.confirmationState.confirmedAnchor;
        const context = this.anchorState.context;
        if (
            confirmed === null ||
            context === null ||
            context.lifecycle !== 'active' ||
            context.targetContextId !== confirmed.targetContextId
        ) {
            throw new Error(
                'AI Select requires a current confirmed Anchor before adjustment.'
            );
        }
        this.discardDraft(false);
        this.nextAdjustmentOrdinal += 1;
        this.baseline = confirmed;
        this.baselineIdentity = confirmedIdentity(confirmed);
        this.nextCameraRevision = confirmed.cameraBinding.revision;
        const cameraBinding = copyCameraBinding(confirmed.cameraBinding);
        this.status = 'adjusting';
        this.draft = Object.freeze({
            adjustmentId: `anchor-adjustment-${this.nextAdjustmentOrdinal}`,
            targetContextId: confirmed.targetContextId,
            baselineCameraBindingDigest: cameraBindingDigest(
                confirmed.cameraBinding
            ),
            cameraBinding,
            cameraBindingDigest: cameraBindingDigest(cameraBinding),
            renderStatus: 'idle'
        });
        this.maskSession.notifyHostStateChanged();
        this.publish();
    }

    updateAdjustmentPose(cameraToWorld: readonly number[]): CameraBinding {
        const draft = this.requireDraft();
        const baseline = this.requireBaseline();
        assertCameraToWorldMatrix(cameraToWorld);
        if (this.nextCameraRevision >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'Changed-Anchor draft CameraBinding revision cannot advance safely.'
            );
        }
        this.nextCameraRevision += 1;
        const cameraBinding = withCameraBindingPose(
            baseline.cameraBinding,
            Object.freeze([...cameraToWorld]),
            this.nextCameraRevision
        );
        const changed = !poseMatches(cameraBinding, baseline.cameraBinding);
        this.activeRender = null;
        this.activeConfirmation = null;
        this.confirmationStatus = 'idle';
        this.validation = null;
        this.confirmationErrorMessage = undefined;
        this.readyRender = null;
        this.status = changed ? 'changed' : 'adjusting';
        this.draft = Object.freeze({
            adjustmentId: draft.adjustmentId,
            targetContextId: draft.targetContextId,
            baselineCameraBindingDigest: draft.baselineCameraBindingDigest,
            cameraBinding: changed
                ? cameraBinding
                : copyCameraBinding(baseline.cameraBinding),
            cameraBindingDigest: cameraBindingDigest(
                changed ? cameraBinding : baseline.cameraBinding
            ),
            renderStatus: 'idle'
        });
        this.maskSession.notifyHostStateChanged();
        this.publish();
        return copyCameraBinding(this.requireDraft().cameraBinding);
    }

    async confirmAdjustmentPose(): Promise<AnchorAdjustmentPoseOutcome> {
        const draft = this.requireDraft();
        const baseline = this.requireBaseline();
        if (poseMatches(draft.cameraBinding, baseline.cameraBinding)) {
            this.cancelAdjustment();
            return 'unchanged';
        }
        const pending: PendingDraftRender = Object.freeze({
            adjustmentId: draft.adjustmentId,
            cameraBindingDigest: draft.cameraBindingDigest
        });
        this.activeRender = pending;
        this.readyRender = null;
        this.status = 'changed';
        this.draft = Object.freeze({
            ...draft,
            renderStatus: 'rendering'
        });
        this.maskSession.notifyHostStateChanged();
        this.publish();

        let rendered: AnchorAdjustmentRenderArtifact;
        try {
            rendered = await this.anchor.renderAnchorAdjustmentDraft(
                draft.cameraBinding
            );
        } catch (error) {
            if (!this.isCurrentRender(pending)) {
                return 'discarded';
            }
            this.activeRender = null;
            this.draft = Object.freeze({
                ...this.requireDraft(),
                renderStatus: 'failed',
                errorMessage: errorMessage(error)
            });
            this.maskSession.notifyHostStateChanged();
            this.publish();
            throw error;
        }
        if (!this.isCurrentRender(pending)) {
            return 'discarded';
        }
        this.activeRender = null;
        this.readyRender = rendered;
        this.draft = Object.freeze({
            ...this.requireDraft(),
            cameraBinding: copyCameraBinding(rendered.cameraBinding),
            cameraBindingDigest: cameraBindingDigest(rendered.cameraBinding),
            renderStatus: 'ready',
            rgb: copyRgb(rendered.rgb)
        });
        this.maskSession.notifyHostStateChanged();
        this.publish();
        return 'staged';
    }

    /**
     * Confirm the changed Anchor as one intent: publish a fresh draft-local
     * Stable Mask when needed, probe and validate the exact staged
     * Camera/RGB/Mask identity, then invoke the synchronous cutover seam.
     * The currently confirmed run is never touched before that final call.
     */
    async confirmAdjustment(
        options: ConfirmAnchorOptions = {}
    ): Promise<ConfirmedAnchor | null> {
        const draft = this.requireDraft();
        const render = this.readyRender;
        if (draft.renderStatus !== 'ready' || render === null) {
            throw new Error(
                'AI Select requires a ready changed-Anchor RGB draft before confirmation.'
            );
        }
        const before = this.mask.state;
        if (before.requestStatus === 'pending') {
            throw new Error(
                'AI Select must finish the current changed-Anchor Mask request before confirmation.'
            );
        }
        if (before.hasUnconfirmedMaskChanges) {
            this.mask.confirmEditingMask();
        }
        const stableMask = this.mask.state.stableMask;
        if (stableMask === null) {
            throw new Error(
                'AI Select requires a fresh Stable Mask for the changed Anchor.'
            );
        }
        const request = this.anchor.createAnchorAdjustmentSupportProbeRequest(
            render,
            stableMask.artifact,
            this.mintSupportProbeAttemptId()
        );
        if (request === null) {
            throw new Error(
                'AI Select could not bind changed-Anchor validation to the current draft.'
            );
        }
        const pending: PendingDraftConfirmation = Object.freeze({
            adjustmentId: draft.adjustmentId,
            cameraBindingDigest: draft.cameraBindingDigest,
            stableMaskId: stableMask.maskId,
            stableMaskDigest: stableMask.artifact.digest,
            draftMaskStateRevision: this.draftMaskStateRevision,
            request
        });
        this.activeConfirmation = pending;
        this.confirmationStatus = 'validating';
        this.validation = null;
        this.confirmationErrorMessage = undefined;
        this.publish();

        try {
            const response =
                await this.supportProbe.probeAnchorSupport(request);
            if (!this.isCurrentConfirmation(pending)) {
                return null;
            }
            if (
                !this.anchor.acceptsAnchorAdjustmentSupportProbeResponse(
                    response,
                    request,
                    render
                )
            ) {
                throw new Error(
                    'The Selection Service Companion returned an invalid or stale changed-Anchor support probe binding.'
                );
            }
            const validation = evaluateAnchorValidation({
                rgbReady: true,
                rgbDigest: render.rgb.digest,
                rgbWidth: render.rgb.width,
                rgbHeight: render.rgb.height,
                cameraBindingCurrent: true,
                stableMask,
                maskRevisionPending: false,
                stableIdMappingValid: this.getStableIdMappingValid(),
                renderWorkingSetValid: this.getRenderWorkingSetValid(),
                support: response.support
            });
            this.validation = validation;
            if (validation.hardBlocks.length > 0) {
                throw new Error(
                    `AI Select changed-Anchor validation blocks Confirm: ${validation.hardBlocks.join(
                        ', '
                    )}.`
                );
            }
            if (
                validation.softWarnings.length > 0 &&
                options.overrideSoftWarnings !== true
            ) {
                throw new Error(
                    'AI Select changed-Anchor validation raised soft warnings. Confirm again with an explicit override to proceed.'
                );
            }
            this.confirmationStatus = 'idle';
            this.confirmationErrorMessage = undefined;
            const confirmed = this.commitDraft({ render, stableMask });
            this.activeConfirmation = null;
            if (this.draft !== null) {
                this.discardDraft(true);
            }
            return confirmed;
        } catch (error) {
            if (!this.isCurrentConfirmation(pending)) {
                return null;
            }
            this.activeConfirmation = null;
            this.confirmationStatus = 'failed';
            this.confirmationErrorMessage = errorMessage(error);
            this.publish();
            throw error;
        }
    }

    cancelAdjustment(): void {
        this.discardDraft(true);
    }

    resetAdjustmentPose(): CameraBinding {
        const baseline = this.requireBaseline();
        this.updateAdjustmentPose(baseline.cameraBinding.cameraToWorld);
        return copyCameraBinding(this.requireDraft().cameraBinding);
    }

    handleCompanionInstanceChanged(): void {
        this.maskSession.handleCompanionInstanceChanged();
    }

    refreshAvailability(): void {
        this.maskSession.refreshAvailability();
    }

    private currentDraftRgb(): AnchorRgbArtifact | null {
        return this.draft?.renderStatus === 'ready' &&
            this.draft.rgb !== undefined
            ? this.draft.rgb
            : null;
    }

    private discardIfBaselineIsNoLongerCurrent(): void {
        if (this.draft === null) {
            return;
        }
        const confirmed = this.confirmationState.confirmedAnchor;
        const context = this.anchorState.context;
        if (
            confirmed === null ||
            context === null ||
            context.lifecycle !== 'active' ||
            context.targetContextId !== this.draft.targetContextId ||
            confirmedIdentity(confirmed) !== this.baselineIdentity
        ) {
            this.discardDraft(true);
        }
    }

    private discardDraft(publish: boolean): void {
        if (this.draft === null) {
            return;
        }
        this.activeRender = null;
        this.activeConfirmation = null;
        this.readyRender = null;
        this.status = 'current';
        this.draft = null;
        this.baseline = null;
        this.baselineIdentity = null;
        this.confirmationStatus = 'idle';
        this.validation = null;
        this.confirmationErrorMessage = undefined;
        this.maskRegistry.disposeView(ANCHOR_ADJUSTMENT_DRAFT_VIEW_ID);
        this.evidenceRegistry.disposeView(ANCHOR_ADJUSTMENT_DRAFT_VIEW_ID);
        this.maskSession.notifyHostStateChanged();
        if (publish) {
            this.publish();
        }
    }

    private isCurrentRender(pending: PendingDraftRender): boolean {
        const draft = this.draft;
        return (
            this.activeRender === pending &&
            draft !== null &&
            draft.adjustmentId === pending.adjustmentId &&
            draft.cameraBindingDigest === pending.cameraBindingDigest &&
            this.confirmationState.confirmedAnchor !== null &&
            confirmedIdentity(this.confirmationState.confirmedAnchor) ===
                this.baselineIdentity
        );
    }

    private isCurrentConfirmation(pending: PendingDraftConfirmation): boolean {
        const draft = this.draft;
        return (
            this.activeConfirmation === pending &&
            draft !== null &&
            draft.adjustmentId === pending.adjustmentId &&
            draft.cameraBindingDigest === pending.cameraBindingDigest &&
            this.draftMaskStateRevision === pending.draftMaskStateRevision &&
            this.mask.state.stableMask?.maskId === pending.stableMaskId &&
            this.mask.state.stableMask?.artifact.digest ===
                pending.stableMaskDigest &&
            this.mask.state.requestStatus !== 'pending' &&
            !this.mask.state.hasUnconfirmedChanges &&
            this.readyRender !== null &&
            this.readyRender.rgb.digest === pending.request.rgbDigest &&
            this.confirmationState.confirmedAnchor !== null &&
            confirmedIdentity(this.confirmationState.confirmedAnchor) ===
                this.baselineIdentity
        );
    }

    private mintSupportProbeAttemptId(): string {
        if (this.nextSupportProbeAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'Changed-Anchor support probe identity cannot advance safely.'
            );
        }
        this.nextSupportProbeAttemptOrdinal += 1;
        return `anchor-adjustment-support-probe-${this.nextSupportProbeAttemptOrdinal}`;
    }

    private requireDraft(): AnchorAdjustmentDraft {
        if (this.draft === null) {
            throw new Error('AI Select has no active Anchor adjustment draft.');
        }
        return this.draft;
    }

    private requireBaseline(): ConfirmedAnchor {
        if (this.baseline === null) {
            throw new Error(
                'AI Select Anchor adjustment lost its confirmed baseline.'
            );
        }
        return this.baseline;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
