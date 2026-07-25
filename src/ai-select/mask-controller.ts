import type {
    AISelectAnchorController,
    AISelectAnchorState
} from './anchor-controller';
import {
    aiSelectEvidencePolicyVersion,
    PerViewEvidenceRegistry,
    type EvidenceDependencyIdentity,
    type ViewEvidenceState
} from './evidence-state';
import type {
    BrushStroke,
    MaskAnnotation,
    MaskPolarity,
    MaskPrompt
} from './mask-annotation';
import { MaskAnnotationRegistry } from './mask-registry';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse
} from './mask-service';

const ANCHOR_VIEW_ID = 'anchor-view';

export type MaskRequestStatus = 'idle' | 'pending' | 'failed';

export interface AddMaskPromptInput {
    readonly xPx: number;
    readonly yPx: number;
    readonly polarity: MaskPolarity;
}

/** The Anchor's current Mask/Evidence surface, composed per state read. */
export interface AISelectMaskState {
    readonly viewId: string;
    /** The unpublished Editing Mask bound to the current RGB, if any. */
    readonly editingMask: MaskAnnotation | null;
    /** The published Stable Mask bound to the current RGB, if any. */
    readonly stableMask: MaskAnnotation | null;
    /** The current prompt set for the current RGB identity. */
    readonly prompts: readonly MaskPrompt[];
    readonly requestStatus: MaskRequestStatus;
    readonly errorMessage?: string;
    readonly evidence: ViewEvidenceState;
}

export type AISelectMaskListener = (state: AISelectMaskState) => void;

interface PendingMaskRequest {
    readonly request: AIViewMaskRequest;
    readonly editingRevision: number;
}

export interface AISelectMaskControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly maskProvider: AISelectMaskProvider;
    readonly getModelManifestDigest?: () => string | null;
}

const errorMessage = (error: unknown): string => {
    return error instanceof Error && error.message
        ? error.message
        : 'AI Select mask production failed.';
};

/**
 * Owns the Anchor's Mask domain: prompts, single-frame SAM feedback, local
 * brush edits, and atomic Confirm Mask publication, plus the per-view
 * Evidence dependency identity those transitions invalidate. RGB/render
 * lifecycle stays in the Anchor controller; Mask and Evidence state here are
 * independent and never demote a ready render.
 */
export class AISelectMaskController {
    private readonly anchor: AISelectAnchorController;
    private readonly maskProvider: AISelectMaskProvider;
    private readonly getModelManifestDigest: () => string | null;
    private readonly registry = new MaskAnnotationRegistry();
    /**
     * The per-view Evidence dependency registry. Nothing produces Evidence at
     * this stage; the production path (Ticket 20) drives this seam, and Mask
     * publication already derives its invalidation.
     */
    readonly evidenceRegistry = new PerViewEvidenceRegistry();
    private readonly listeners = new Set<AISelectMaskListener>();
    private anchorState: AISelectAnchorState = { context: null, anchor: null };
    private targetContextId: string | null = null;
    private lastRgbDigest: string | null = null;
    private prompts: MaskPrompt[] = [];
    private requestStatus: MaskRequestStatus = 'idle';
    private lastErrorMessage: string | undefined;
    private activeMaskRequest: PendingMaskRequest | null = null;
    /**
     * Bumped by every local editing mutation so a late SAM response can
     * never overwrite a newer local brush edit.
     */
    private editingRevision = 0;
    private nextMaskAttemptOrdinal = 0;
    private nextPromptOrdinal = 0;

    constructor(options: AISelectMaskControllerOptions) {
        this.anchor = options.anchor;
        this.maskProvider = options.maskProvider;
        this.getModelManifestDigest =
            options.getModelManifestDigest ?? (() => null);
        this.anchor.subscribe((state) => this.handleAnchorState(state));
    }

    get state(): AISelectMaskState {
        const rgbDigest = this.currentRgbDigest();
        const view = this.registry.viewState(ANCHOR_VIEW_ID, rgbDigest ?? '');
        const currentIdentity = this.currentEvidenceIdentity(
            rgbDigest,
            view.stableMask
        );
        return Object.freeze({
            viewId: ANCHOR_VIEW_ID,
            editingMask: view.editingMask,
            stableMask: view.stableMask,
            prompts: Object.freeze([...this.prompts]),
            requestStatus: this.requestStatus,
            ...(this.lastErrorMessage === undefined
                ? {}
                : { errorMessage: this.lastErrorMessage }),
            evidence: this.evidenceRegistry.statusFor(
                ANCHOR_VIEW_ID,
                currentIdentity
            )
        });
    }

    subscribe(listener: AISelectMaskListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    /**
     * Add one prompt point and automatically request single-frame SAM
     * feedback for the full current prompt set — no extra apply action.
     */
    async addPrompt(input: AddMaskPromptInput): Promise<void> {
        const rgb = this.requireReadyRgb();
        if (
            !Number.isSafeInteger(input.xPx) ||
            !Number.isSafeInteger(input.yPx) ||
            input.xPx < 0 ||
            input.yPx < 0 ||
            input.xPx >= rgb.width ||
            input.yPx >= rgb.height
        ) {
            throw new Error(
                'AI Select prompts must be integer pixels inside the Anchor RGB bounds.'
            );
        }
        this.prompts = [
            ...this.prompts,
            Object.freeze({
                promptId: this.mintPromptId(),
                xPx: input.xPx,
                yPx: input.yPx,
                polarity: input.polarity
            })
        ];
        await this.submitMaskRequest();
    }

    /**
     * Apply one local brush stroke to the Editing Mask. Brush edits are
     * editor-local, never call SAM, and supersede any in-flight SAM response.
     */
    applyBrushStroke(stroke: BrushStroke): void {
        const rgb = this.requireReadyRgb();
        this.registry.applyBrush({
            viewId: ANCHOR_VIEW_ID,
            rgbDigest: rgb.digest,
            stroke,
            width: rgb.width,
            height: rgb.height
        });
        this.editingRevision += 1;
        if (this.activeMaskRequest !== null) {
            this.activeMaskRequest = null;
            this.requestStatus = 'idle';
        }
        this.lastErrorMessage = undefined;
        this.publish();
    }

    /**
     * Atomically publish the current Editing Mask as the new Stable Mask
     * revision. Until this synchronous swap succeeds, observers keep seeing
     * the previous Stable Mask and current Evidence. Dependent per-view
     * Evidence derives stale by exact RGB/Mask/policy identity.
     */
    confirmEditingMask(): void {
        const rgb = this.requireReadyRgb();
        this.registry.confirm(ANCHOR_VIEW_ID, rgb.digest);
        this.lastErrorMessage = undefined;
        this.publish();
    }

    /** An explicit Retry submits a new attempt for the same prompt set. */
    async retryMaskRequest(): Promise<void> {
        this.requireReadyRgb();
        if (this.prompts.length === 0) {
            throw new Error('AI Select has no Mask prompt set to retry.');
        }
        await this.submitMaskRequest();
    }

    private async submitMaskRequest(): Promise<void> {
        const modelManifestDigest = this.getModelManifestDigest();
        if (modelManifestDigest === null || modelManifestDigest.length === 0) {
            this.failMaskRequest(
                'AI Select requires a configured Model Manifest before SAM mask production.'
            );
            return;
        }
        const request = this.anchor.createAnchorMaskRequest(
            this.prompts,
            this.mintMaskAttemptId(),
            modelManifestDigest
        );
        if (request === null) {
            this.failMaskRequest(
                'AI Select requires an RGB Ready Anchor before SAM mask production.'
            );
            return;
        }
        const pending: PendingMaskRequest = {
            request,
            editingRevision: this.editingRevision
        };
        this.activeMaskRequest = pending;
        this.requestStatus = 'pending';
        this.lastErrorMessage = undefined;
        this.publish();

        let response: MaskResultResponse;
        try {
            response = await this.maskProvider.produceMask(request);
        } catch (error) {
            if (!this.isCurrentMaskRequest(pending)) {
                return;
            }
            this.failMaskRequest(errorMessage(error));
            return;
        }
        if (!this.isCurrentMaskRequest(pending)) {
            return;
        }
        if (!this.anchor.acceptsMaskResponse(response, request)) {
            this.failMaskRequest(
                'The Selection Service Companion returned an invalid or stale Mask binding.'
            );
            return;
        }
        try {
            this.registry.registerSamResult({
                viewId: request.viewId,
                rgbDigest: request.rgb.digest,
                artifact: response.mask,
                prompts: request.prompts
            });
        } catch (error) {
            this.failMaskRequest(errorMessage(error));
            return;
        }
        this.activeMaskRequest = null;
        this.requestStatus = 'idle';
        this.publish();
    }

    private isCurrentMaskRequest(pending: PendingMaskRequest): boolean {
        return (
            this.activeMaskRequest === pending &&
            pending.editingRevision === this.editingRevision
        );
    }

    private failMaskRequest(message: string): void {
        this.activeMaskRequest = null;
        this.requestStatus = 'failed';
        this.lastErrorMessage = message;
        this.publish();
    }

    private handleAnchorState(state: AISelectAnchorState): void {
        this.anchorState = state;
        const contextId = state.context?.targetContextId ?? null;
        const rgbDigest = this.currentRgbDigest();
        if (contextId !== this.targetContextId) {
            // Restart/exit rotates targetContextId and disposes every
            // target-local Mask/Evidence record.
            this.targetContextId = contextId;
            this.registry.disposeView(ANCHOR_VIEW_ID);
            this.evidenceRegistry.disposeView(ANCHOR_VIEW_ID);
            this.resetForNewRgbIdentity(rgbDigest);
            return;
        }
        if (rgbDigest !== this.lastRgbDigest) {
            // A new RGB identity makes the old prompt set and in-flight SAM
            // work stale; Mask versions stay retained but stop being current.
            this.resetForNewRgbIdentity(rgbDigest);
            return;
        }
        this.publish();
    }

    private resetForNewRgbIdentity(rgbDigest: string | null): void {
        this.lastRgbDigest = rgbDigest;
        this.prompts = [];
        this.activeMaskRequest = null;
        this.requestStatus = 'idle';
        this.lastErrorMessage = undefined;
        this.editingRevision += 1;
        this.publish();
    }

    private currentRgbDigest(): string | null {
        const anchor = this.anchorState.anchor;
        if (anchor?.renderStatus !== 'ready' || anchor.rgb === undefined) {
            return null;
        }
        return anchor.rgb.digest;
    }

    private currentEvidenceIdentity(
        rgbDigest: string | null,
        stableMask: MaskAnnotation | null
    ): EvidenceDependencyIdentity | null {
        if (rgbDigest === null || stableMask === null) {
            return null;
        }
        return {
            viewId: ANCHOR_VIEW_ID,
            rgbDigest,
            stableMaskDigest: stableMask.artifact.digest,
            evidencePolicyDigest: aiSelectEvidencePolicyVersion
        };
    }

    private requireReadyRgb() {
        const anchor = this.anchorState.anchor;
        if (
            this.anchorState.context?.lifecycle !== 'active' ||
            anchor?.renderStatus !== 'ready' ||
            anchor.rgb === undefined
        ) {
            throw new Error(
                'AI Select requires an RGB Ready Anchor for Mask authoring.'
            );
        }
        return anchor.rgb;
    }

    private mintMaskAttemptId(): string {
        if (this.nextMaskAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select mask attempt identity cannot advance safely.'
            );
        }
        this.nextMaskAttemptOrdinal += 1;
        return `mask-attempt-${this.nextMaskAttemptOrdinal}`;
    }

    private mintPromptId(): string {
        if (this.nextPromptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error('AI Select prompt identity cannot advance safely.');
        }
        this.nextPromptOrdinal += 1;
        return `mask-prompt-${this.nextPromptOrdinal}`;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
