import type {
    AISelectAnchorController,
    AISelectAnchorState
} from './anchor-controller';
import {
    evaluateAnchorValidation,
    type AnchorValidationResult
} from './anchor-validation';
import { copyCameraBinding, type CameraBinding } from './camera-binding';
import {
    copyDependencyToken,
    type TargetDependencyToken
} from './current-target-context';
import { aiSelectEvidencePolicyVersion } from './evidence-state';
import type { MaskAnnotation } from './mask-annotation';
import type {
    AISelectMaskController,
    AISelectMaskState
} from './mask-controller';
import type {
    AISelectSupportProbeProvider,
    AnchorSupportProbeRequest,
    AnchorSupportProbeSupport
} from './support-probe';

/**
 * The atomically published Confirm Anchor record (Final Spec v1.1 §12.4). It
 * binds exactly CameraBinding, RGB digest, Stable Mask + digest, Mask
 * Evidence Policy version, Target Dependency Token, and Scene/Splat
 * identity. Complete Contributor identity is deliberately absent.
 */
export interface ConfirmedAnchor {
    readonly targetContextId: string;
    readonly contextRevision: number;
    readonly cameraBinding: CameraBinding;
    readonly rgbDigest: string;
    readonly stableMask: MaskAnnotation;
    readonly maskEvidencePolicyVersion: string;
    readonly dependencyToken: TargetDependencyToken;
    readonly sceneId: string;
    readonly sceneVersion: string;
}

export type AnchorValidationStatus = 'idle' | 'validating' | 'failed';

export interface AISelectAnchorConfirmationState {
    /** The latest validation whose exact input identity is still current. */
    readonly validation: AnchorValidationResult | null;
    readonly validationStatus: AnchorValidationStatus;
    readonly errorMessage?: string;
    readonly confirmedAnchor: ConfirmedAnchor | null;
}

export type AISelectAnchorConfirmationListener = (
    state: AISelectAnchorConfirmationState
) => void;

export interface ConfirmAnchorOptions {
    /** Soft warnings are user-overridable; hard blocks never are. */
    readonly overrideSoftWarnings?: boolean;
}

export interface AISelectAnchorConfirmationControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly mask: AISelectMaskController;
    readonly supportProbe: AISelectSupportProbeProvider;
    readonly getStableIdMappingValid?: () => boolean;
    readonly getRenderWorkingSetValid?: () => boolean;
}

interface PendingSupportProbe {
    readonly request: AnchorSupportProbeRequest;
    readonly stableMaskDigest: string;
}

const errorMessage = (error: unknown): string => {
    return error instanceof Error && error.message
        ? error.message
        : 'AI Select Anchor validation failed.';
};

/**
 * Orchestrates Anchor Validation and Confirm Anchor. Validation evaluates
 * computational suitability and proves Gaussian support through the
 * versioned low-cost support probe — never through complete Contributor
 * publication or formal P/N/V Evidence. Confirm re-validates against the
 * latest exact revisions and then publishes the bound record atomically;
 * the confirmed Anchor stays locked until Adjust Anchor or Restart.
 */
export class AISelectAnchorConfirmationController {
    private readonly anchor: AISelectAnchorController;
    private readonly mask: AISelectMaskController;
    private readonly supportProbe: AISelectSupportProbeProvider;
    private readonly getStableIdMappingValid: () => boolean;
    private readonly getRenderWorkingSetValid: () => boolean;
    private readonly listeners = new Set<AISelectAnchorConfirmationListener>();
    private anchorState: AISelectAnchorState = { context: null, anchor: null };
    private maskState: AISelectMaskState | null = null;
    private targetContextId: string | null = null;
    private trackedRgbDigest: string | null = null;
    private trackedStableMaskDigest: string | null = null;
    private validation: AnchorValidationResult | null = null;
    private validationStatus: AnchorValidationStatus = 'idle';
    private lastErrorMessage: string | undefined;
    private confirmedAnchor: ConfirmedAnchor | null = null;
    private activeProbe: PendingSupportProbe | null = null;
    private nextSupportProbeAttemptOrdinal = 0;

    constructor(options: AISelectAnchorConfirmationControllerOptions) {
        this.anchor = options.anchor;
        this.mask = options.mask;
        this.supportProbe = options.supportProbe;
        this.getStableIdMappingValid =
            options.getStableIdMappingValid ?? (() => true);
        this.getRenderWorkingSetValid =
            options.getRenderWorkingSetValid ?? (() => true);
        this.anchor.subscribe((state) => {
            this.anchorState = state;
            this.trackInputIdentity();
        });
        this.mask.subscribe((state) => {
            this.maskState = state;
            this.trackInputIdentity();
        });
    }

    get state(): AISelectAnchorConfirmationState {
        return Object.freeze({
            validation: this.validation,
            validationStatus: this.validationStatus,
            ...(this.lastErrorMessage === undefined
                ? {}
                : { errorMessage: this.lastErrorMessage }),
            confirmedAnchor: this.confirmedAnchor
        });
    }

    /** A confirmed Anchor locks CameraBinding and Mask authoring. */
    get locked(): boolean {
        return this.confirmedAnchor !== null;
    }

    subscribe(listener: AISelectAnchorConfirmationListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    /**
     * Evaluate Anchor computational suitability against the latest exact
     * revisions. The support probe runs only when every local prerequisite
     * holds; its verdict never classifies ownership. Returns null when the
     * probe itself failed — RGB, Mask, and View state stay untouched.
     */
    async validate(): Promise<AnchorValidationResult | null> {
        const local = this.evaluate(null);
        if (
            local.hardBlocks.some(
                (block) => block !== 'gaussian-support-unproven'
            )
        ) {
            this.publishValidation(local);
            return local;
        }
        const stableMask = this.maskState?.stableMask ?? null;
        const request =
            stableMask === null
                ? null
                : this.anchor.createAnchorSupportProbeRequest(
                      stableMask.artifact,
                      this.mintSupportProbeAttemptId()
                  );
        if (request === null) {
            this.publishValidation(local);
            return local;
        }
        const pending: PendingSupportProbe = {
            request,
            stableMaskDigest: request.stableMask.digest
        };
        this.activeProbe = pending;
        this.validation = null;
        this.validationStatus = 'validating';
        this.lastErrorMessage = undefined;
        this.publish();

        let support: AnchorSupportProbeSupport;
        try {
            const response =
                await this.supportProbe.probeAnchorSupport(request);
            if (this.activeProbe !== pending) {
                // A newer revision superseded this probe; its verdict is
                // discarded, not applied.
                return null;
            }
            if (!this.anchor.acceptsSupportProbeResponse(response, request)) {
                this.failValidation(
                    'The Selection Service Companion returned an invalid or stale support probe binding.'
                );
                return null;
            }
            support = response.support;
        } catch (error) {
            if (this.activeProbe !== pending) {
                return null;
            }
            this.failValidation(errorMessage(error));
            return null;
        }
        this.activeProbe = null;
        const result = this.evaluate(support);
        this.publishValidation(result);
        return result;
    }

    /**
     * Confirm Anchor re-validates against the latest exact revisions — never
     * confirming stale output — then atomically publishes the bound record.
     */
    async confirmAnchor(
        options: ConfirmAnchorOptions = {}
    ): Promise<ConfirmedAnchor> {
        if (this.locked) {
            throw new Error(
                'AI Select Anchor is already confirmed. Adjust or restart the Anchor first.'
            );
        }
        const result = await this.validate();
        if (result === null) {
            throw new Error(
                this.lastErrorMessage ?? 'AI Select Anchor validation failed.'
            );
        }
        if (result.hardBlocks.length > 0) {
            throw new Error(
                `AI Select Anchor validation blocks Confirm: ${result.hardBlocks.join(
                    ', '
                )}.`
            );
        }
        if (
            result.softWarnings.length > 0 &&
            options.overrideSoftWarnings !== true
        ) {
            throw new Error(
                'AI Select Anchor validation raised soft warnings. Confirm again with an explicit override to proceed.'
            );
        }
        const context = this.anchorState.context;
        const anchor = this.anchorState.anchor;
        const stableMask = this.maskState?.stableMask ?? null;
        const sceneIdentity = this.anchor.getAnchorSceneIdentity();
        if (
            context === null ||
            anchor?.renderStatus !== 'ready' ||
            anchor.rgb === undefined ||
            stableMask === null ||
            sceneIdentity === null
        ) {
            throw new Error(
                'AI Select requires a fully bound RGB Ready Anchor with a Stable Mask to Confirm.'
            );
        }
        const confirmed: ConfirmedAnchor = Object.freeze({
            targetContextId: context.targetContextId,
            contextRevision: context.revision,
            cameraBinding: copyCameraBinding(anchor.cameraBinding),
            rgbDigest: anchor.rgb.digest,
            stableMask,
            maskEvidencePolicyVersion: aiSelectEvidencePolicyVersion,
            dependencyToken: copyDependencyToken(context.dependencyToken),
            sceneId: sceneIdentity.sceneId,
            sceneVersion: sceneIdentity.sceneVersion
        });
        // One synchronous swap: observers see either no confirmed Anchor or
        // the fully bound record, never a partial publication.
        this.confirmedAnchor = confirmed;
        this.publish();
        return confirmed;
    }

    /**
     * The explicit adjustment flow: discard the confirmation record (and its
     * lock) while keeping Anchor, RGB, and Mask state intact.
     */
    adjustAnchor(): void {
        if (this.confirmedAnchor === null) {
            return;
        }
        this.confirmedAnchor = null;
        this.publish();
    }

    private evaluate(
        support: AnchorSupportProbeSupport | null
    ): AnchorValidationResult {
        const context = this.anchorState.context;
        const anchor = this.anchorState.anchor;
        const contextActive = context?.lifecycle === 'active';
        const rgbReady =
            contextActive === true &&
            anchor?.renderStatus === 'ready' &&
            anchor.rgb !== undefined;
        const stableMask = this.maskState?.stableMask ?? null;
        return evaluateAnchorValidation({
            rgbReady,
            rgbDigest: rgbReady ? (anchor?.rgb?.digest ?? null) : null,
            rgbWidth: anchor?.rgb?.width ?? 0,
            rgbHeight: anchor?.rgb?.height ?? 0,
            cameraBindingCurrent: contextActive === true,
            stableMask,
            maskRevisionPending: this.maskState?.requestStatus === 'pending',
            proposalDecisionResolved:
                this.maskState?.proposalDecision?.status !== 'ambiguous' ||
                this.maskState.acceptedProposalId !== null ||
                this.maskState.editingMask?.source === 'manual' ||
                this.maskState.editingMask?.source === 'hybrid',
            stableIdMappingValid: this.getStableIdMappingValid(),
            renderWorkingSetValid: this.getRenderWorkingSetValid(),
            support
        });
    }

    /**
     * Input-identity tracking: a newer RGB or Stable Mask revision makes any
     * completed or in-flight validation stale; a rotated target context
     * disposes every target-local confirmation record.
     */
    private trackInputIdentity(): void {
        const contextId = this.anchorState.context?.targetContextId ?? null;
        if (contextId !== this.targetContextId) {
            this.targetContextId = contextId;
            this.trackedRgbDigest = this.currentRgbDigest();
            this.trackedStableMaskDigest = this.currentStableMaskDigest();
            this.reset();
            return;
        }
        if (this.confirmedAnchor !== null) {
            return;
        }
        const rgbDigest = this.currentRgbDigest();
        const stableMaskDigest = this.currentStableMaskDigest();
        if (
            rgbDigest !== this.trackedRgbDigest ||
            stableMaskDigest !== this.trackedStableMaskDigest
        ) {
            this.trackedRgbDigest = rgbDigest;
            this.trackedStableMaskDigest = stableMaskDigest;
            this.activeProbe = null;
            this.validation = null;
            this.validationStatus = 'idle';
            this.lastErrorMessage = undefined;
        }
        this.publish();
    }

    private currentRgbDigest(): string | null {
        const anchor = this.anchorState.anchor;
        return anchor?.renderStatus === 'ready' && anchor.rgb !== undefined
            ? anchor.rgb.digest
            : null;
    }

    private currentStableMaskDigest(): string | null {
        return this.maskState?.stableMask?.artifact.digest ?? null;
    }

    private reset(): void {
        this.activeProbe = null;
        this.validation = null;
        this.validationStatus = 'idle';
        this.lastErrorMessage = undefined;
        this.confirmedAnchor = null;
        this.publish();
    }

    private publishValidation(result: AnchorValidationResult): void {
        this.validation = result;
        this.validationStatus = 'idle';
        this.lastErrorMessage = undefined;
        this.publish();
    }

    private failValidation(message: string): void {
        this.activeProbe = null;
        this.validation = null;
        this.validationStatus = 'failed';
        this.lastErrorMessage = message;
        this.publish();
    }

    private mintSupportProbeAttemptId(): string {
        if (this.nextSupportProbeAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select support probe identity cannot advance safely.'
            );
        }
        this.nextSupportProbeAttemptOrdinal += 1;
        return `support-probe-attempt-${this.nextSupportProbeAttemptOrdinal}`;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
