import type {
    AISelectAnchorController,
    AISelectAnchorState
} from './anchor-controller';
import type { AnchorRgbArtifact } from './anchor-render-service';
import { AISelectDirtyStateTracker } from './dirty-state';
import { PerViewEvidenceRegistry } from './evidence-state';
import type { BrushStroke } from './mask-annotation';
import { MaskAnnotationRegistry } from './mask-registry';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse,
    PreviousPredictionLogitsRef
} from './mask-service';
import type { PromptAdapterCapabilities, PromptState } from './prompt-state';
import {
    AISelectViewMaskSession,
    type AddBoxPromptInput,
    type AddMaskPromptInput,
    type AISelectMaskAuthoring,
    type AISelectMaskListener,
    type AISelectMaskState,
    type ApplyBrushGestureInput
} from './view-mask-session';

export type {
    AddBoxPromptInput,
    AddMaskPromptInput,
    AISelectMaskAuthoring,
    AISelectMaskListener,
    AISelectMaskState,
    ApplyBrushGestureInput,
    BrushGestureSample,
    AutomaticMaskStatus,
    MaskFailureKind,
    MaskRequestStatus
} from './view-mask-session';

const ANCHOR_VIEW_ID = 'anchor-view';

export interface AISelectMaskControllerOptions {
    readonly anchor: AISelectAnchorController;
    readonly maskProvider: AISelectMaskProvider;
    readonly getModelManifestDigest?: () => string | null;
    readonly getPromptAdapterCapabilities?: () => PromptAdapterCapabilities | null;
    /** Shared target-local recompute state for Anchor and Generated Views. */
    readonly dirtyState?: AISelectDirtyStateTracker;
    /**
     * A confirmed Anchor locks Mask authoring until an explicit adjustment or
     * restart flow unlocks it (Final Spec v1.1 §12.4).
     */
    readonly isAnchorLocked?: () => boolean;
}

/**
 * The Anchor's Mask surface: one AISelectViewMaskSession bound to the Anchor
 * host seams. The session owns the view-agnostic Mask domain (prompts,
 * single-frame SAM feedback, brush edits, Confirm publication); this wrapper
 * only binds Anchor RGB currency, the confirmed-Anchor authoring lock, and
 * the Anchor's request/response binding validation.
 */
export class AISelectMaskController implements AISelectMaskAuthoring {
    private readonly anchor: AISelectAnchorController;
    private readonly isAnchorLocked: () => boolean;
    /**
     * The one versioned Mask registry for every AI View in the Current Target
     * Context. The Generated View controller shares this instance so Mask
     * identities never fork across views.
     */
    readonly maskRegistry = new MaskAnnotationRegistry();
    /**
     * The per-view Evidence dependency registry. Nothing produces Evidence at
     * this stage; the production path (Ticket 20) drives this seam, and Mask
     * publication already derives its invalidation.
     */
    readonly evidenceRegistry = new PerViewEvidenceRegistry();
    /** The explicit Ticket 12 dirty state for this Current Target Context. */
    readonly dirtyState: AISelectDirtyStateTracker;
    private readonly session: AISelectViewMaskSession;
    private anchorState: AISelectAnchorState = { context: null, anchor: null };
    private targetContextId: string | null = null;

    constructor(options: AISelectMaskControllerOptions) {
        this.anchor = options.anchor;
        this.isAnchorLocked = options.isAnchorLocked ?? (() => false);
        this.dirtyState = options.dirtyState ?? new AISelectDirtyStateTracker();
        this.session = new AISelectViewMaskSession({
            host: {
                viewId: ANCHOR_VIEW_ID,
                targetContextId: () =>
                    this.anchorState.context?.targetContextId ?? null,
                currentRgb: () => this.currentAnchorRgb(),
                lockReason: () =>
                    this.isAnchorLocked()
                        ? 'AI Select Mask authoring is locked while the Anchor is confirmed. Adjust or restart the Anchor first.'
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
                ): AIViewMaskRequest | null =>
                    this.anchor.createAnchorMaskRequest(
                        promptState,
                        proposalAttemptId,
                        modelManifestDigest,
                        adapterCapabilityDigest,
                        proposalPolicyVersion,
                        requestOptions
                    ),
                acceptsMaskResponse: (
                    response: MaskResultResponse,
                    request: AIViewMaskRequest
                ): boolean => this.anchor.acceptsMaskResponse(response, request)
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
                  }),
            onStableMaskPublished: () => {
                // Anchor is also an Included Stable View for formal P/N/V.
                // Its Confirm atomically dirties Anchor Evidence/Candidate;
                // the generated controller separately dirties geometry/plan
                // dependencies when a confirmed Anchor run begins.
                this.dirtyState.markAnchorStableChanged([]);
                this.dirtyState.markStableMaskPublished(ANCHOR_VIEW_ID);
            }
        });
        this.anchor.subscribe((state) => {
            const targetContextId = state.context?.targetContextId ?? null;
            if (targetContextId !== this.targetContextId) {
                this.targetContextId = targetContextId;
                this.dirtyState.reset();
            }
            this.anchorState = state;
            this.session.notifyHostStateChanged();
        });
    }

    private currentAnchorRgb(): AnchorRgbArtifact | null {
        const anchor = this.anchorState.anchor;
        if (
            this.anchorState.context?.lifecycle !== 'active' ||
            anchor?.renderStatus !== 'ready' ||
            anchor.rgb === undefined
        ) {
            return null;
        }
        return anchor.rgb;
    }

    get state(): AISelectMaskState {
        return this.session.state;
    }

    subscribe(listener: AISelectMaskListener): () => void {
        return this.session.subscribe(listener);
    }

    async addPrompt(input: AddMaskPromptInput): Promise<void> {
        await this.session.addPrompt(input);
    }

    async addBoxPrompt(input: AddBoxPromptInput): Promise<void> {
        await this.session.addBoxPrompt(input);
    }

    clearPrompts(): void {
        this.session.clearPrompts();
    }

    handleCompanionInstanceChanged(): void {
        this.session.handleCompanionInstanceChanged();
    }

    refreshAvailability(): void {
        this.session.refreshAvailability();
    }

    undoPromptEdit(): void {
        this.session.undoPromptEdit();
    }

    redoPromptEdit(): void {
        this.session.redoPromptEdit();
    }

    applyBrushStroke(stroke: BrushStroke): void {
        this.session.applyBrushStroke(stroke);
    }

    applyBrushGesture(input: ApplyBrushGestureInput): void {
        this.session.applyBrushGesture(input);
    }

    confirmEditingMask(): void {
        this.session.confirmEditingMask();
    }

    clearEditingMask(): void {
        this.session.clearEditingMask();
    }

    restoreAutoMask(): void {
        this.session.restoreAutoMask();
    }

    undoMaskEdit(): void {
        this.session.undoMaskEdit();
    }

    redoMaskEdit(): void {
        this.session.redoMaskEdit();
    }

    async retryMaskRequest(): Promise<void> {
        await this.session.retryMaskRequest();
    }
}
