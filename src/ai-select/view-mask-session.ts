import { SelectionServiceTransportError } from '../selection-service-readiness';
import type { AnchorRgbArtifact } from './anchor-render-service';
import {
    aiSelectEvidencePolicyVersion,
    type EvidenceDependencyIdentity,
    type PerViewEvidenceRegistry,
    type ViewEvidenceState
} from './evidence-state';
import {
    type BrushStroke,
    type MaskAnnotation,
    type MaskPolarity,
    type MaskPrompt
} from './mask-annotation';
import { autoMaskProposalPolicyVersion } from './mask-proposal';
import {
    hasSemanticEditingMaskChange,
    type EditingMaskIssue,
    type MaskAnnotationRegistry
} from './mask-registry';
import {
    isMaskResultResponse,
    MaskArtifactInvalidError,
    type AISelectMaskProvider,
    type AIViewMaskRequest,
    type MaskResultResponse,
    type PreviousPredictionLogitsRef
} from './mask-service';
import {
    createEmptyPromptState,
    createPromptAdapterCapabilities,
    promptStateHasConstraints,
    promptToolCapabilityReason,
    revisePromptState,
    type BoxPrompt,
    type PointPrompt,
    type PromptAdapterCapabilities,
    type PromptState,
    type PromptTool
} from './prompt-state';
import type { ViewAssessmentShape } from './view-assessment';

export type MaskRequestStatus = 'idle' | 'pending' | 'failed';
export type MaskFailureKind = 'maskResultFailed' | 'maskArtifactInvalid';
export type AutomaticMaskStatus = 'none' | 'unavailable' | 'editing';

export interface AddMaskPromptInput {
    readonly xPx: number;
    readonly yPx: number;
    readonly polarity: MaskPolarity;
}

/** Positive Instance Box only; adding a box replaces any existing one. */
export interface AddBoxPromptInput {
    readonly x0Px: number;
    readonly y0Px: number;
    readonly x1Px: number;
    readonly y1Px: number;
}

export interface BrushGestureSample {
    readonly xPx: number;
    readonly yPx: number;
}

export interface ApplyBrushGestureInput {
    readonly mode: BrushStroke['mode'];
    readonly radiusPx: number;
    readonly samples: readonly BrushGestureSample[];
}

/** One View's current Mask/Evidence surface, composed per state read. */
export interface AISelectMaskState {
    readonly viewId: string;
    /** The unpublished Editing Mask bound to the current RGB, if any. */
    readonly editingMask: MaskAnnotation | null;
    /** The published Stable Mask bound to the current RGB, if any. */
    readonly stableMask: MaskAnnotation | null;
    readonly editingMaskIssue: EditingMaskIssue | null;
    /** The current prompt set for the current RGB identity. */
    readonly prompts: readonly MaskPrompt[];
    readonly promptState: PromptState | null;
    /** Prompt semantics published together with the current Stable Mask. */
    readonly publishedPromptState: PromptState | null;
    readonly promptCapabilities: PromptAdapterCapabilities | null;
    /** The latest automatic authoring outcome for this Prompt revision. */
    readonly automaticMaskStatus: AutomaticMaskStatus;
    /** Review metadata carried by the sole usable automatic Mask. */
    readonly automaticMaskReview: ViewAssessmentShape | null;
    /** The Companion dropped an expired/foreign logits ref and ran fresh. */
    readonly refinementFallback: boolean;
    readonly requestStatus: MaskRequestStatus;
    readonly failureKind?: MaskFailureKind;
    readonly errorMessage?: string;
    readonly evidence: ViewEvidenceState;
    /** Mask-local Undo/Redo availability for the current RGB identity. */
    readonly canUndo: boolean;
    readonly canRedo: boolean;
    readonly canUndoPrompt: boolean;
    readonly canRedoPrompt: boolean;
    /** A restorable automatic Mask version exists for the current RGB. */
    readonly canRestoreAuto: boolean;
    /**
     * Unconfirmed Prompt/Editing state a View change would discard: an
     * in-flight SAM revision, target-intent prompts with no Mask, or a draft
     * that diverges from the confirmed Stable Mask.
     */
    readonly hasUnconfirmedChanges: boolean;
    readonly hasUnconfirmedPromptChanges: boolean;
    readonly hasUnconfirmedMaskChanges: boolean;
}

export type AISelectMaskListener = (state: AISelectMaskState) => void;

/**
 * The Mask authoring surface shared by the Anchor Mask controller and the
 * per-View sessions: the Dock routes Prompt/Brush/Confirm gestures to
 * whichever View currently owns the editing surface.
 */
export interface AISelectMaskAuthoring {
    readonly state: AISelectMaskState;
    subscribe(listener: AISelectMaskListener): () => void;
    addPrompt(input: AddMaskPromptInput): Promise<void>;
    addBoxPrompt(input: AddBoxPromptInput): Promise<void>;
    clearPrompts(): void;
    undoPromptEdit(): void;
    redoPromptEdit(): void;
    applyBrushStroke(stroke: BrushStroke): void;
    applyBrushGesture(input: ApplyBrushGestureInput): void;
    confirmEditingMask(): void;
    clearEditingMask(): void;
    restoreAutoMask(): void;
    undoMaskEdit(): void;
    redoMaskEdit(): void;
    retryMaskRequest(): Promise<void>;
}

interface PendingMaskRequest {
    readonly request: AIViewMaskRequest;
    readonly editingRevision: number;
    readonly promptRevision: number;
}

/**
 * The narrow per-View glue a Mask session needs from its owner. The Anchor
 * controller binds the Anchor's RGB/lock/request seams; the user-added View
 * controller binds the same seams to one user-owned AIView. The session
 * itself is view-source agnostic: View source never determines trust.
 */
export interface ViewMaskSessionHost {
    readonly viewId: string;
    /** The Current Target Context identity, or null outside one. */
    targetContextId(): string | null;
    /**
     * The exact authoritative RGB this session authors against, or null
     * unless the View is RGB Ready inside an active context.
     */
    currentRgb(): AnchorRgbArtifact | null;
    /**
     * Why Mask authoring is currently locked (for example a confirmed
     * Anchor), or null while authoring is unlocked.
     */
    lockReason(): string | null;
    /**
     * Build the single-frame SAM mask request bound to the View's exact
     * current RGB, or null when that identity is no longer current.
     */
    createMaskRequest(
        promptState: PromptState,
        proposalAttemptId: string,
        modelManifestDigest: string,
        adapterCapabilityDigest: string,
        proposalPolicyVersion: string,
        options: {
            readonly includeRgbArtifact: boolean;
            readonly previousLogitsRef?: PreviousPredictionLogitsRef;
        }
    ): AIViewMaskRequest | null;
    /** The stale-result gate for Mask responses. */
    acceptsMaskResponse(
        response: MaskResultResponse,
        request: AIViewMaskRequest
    ): boolean;
}

export interface AISelectViewMaskSessionOptions {
    readonly host: ViewMaskSessionHost;
    readonly maskProvider: AISelectMaskProvider;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly evidenceRegistry: PerViewEvidenceRegistry;
    readonly getModelManifestDigest?: () => string | null;
    readonly getPromptAdapterCapabilities?: () => PromptAdapterCapabilities | null;
    /**
     * Fired after the Editing Mask was atomically published as the new Stable
     * Mask revision, so the View owner can apply the Ticket 07 User Confirmed
     * Participation default. Evidence staleness derives from the rotated Mask
     * identity; nothing here lifts.
     */
    readonly onStableMaskPublished?: () => void;
}

const pointOnlyCapabilities = createPromptAdapterCapabilities({
    positivePoints: true,
    negativePoints: true,
    positiveInstanceBox: false,
    previousLogitsRefinement: false,
    singlePointMultimask: false,
    negativeBox: false,
    promptBrush: false,
    maskConstraints: false,
    text: false,
    compilerPolicyVersion: 'point-mask-compiler/v1'
});

const errorMessage = (error: unknown): string => {
    // Transport failures keep the Companion's distinguishable error code and
    // message so the technical details can name the actual recovery class
    // (capability mismatch, unresolvable RGB, capacity, …) instead of a bare
    // HTTP status.
    if (
        error instanceof SelectionServiceTransportError &&
        error.serviceCode !== undefined
    ) {
        const detail = error.serviceMessage ?? '';
        return `${error.message} [${error.serviceCode}] ${detail}`.trim();
    }
    return error instanceof Error && error.message
        ? error.message
        : 'AI Select mask production failed.';
};

const immutableTransportCopy = <T>(value: T): T => {
    const copy = structuredClone(value);
    const freeze = (entry: unknown): void => {
        if (typeof entry !== 'object' || entry === null) {
            return;
        }
        Object.values(entry as Record<string, unknown>).forEach(freeze);
        Object.freeze(entry);
    };
    freeze(copy);
    return copy;
};

/**
 * Owns one View's Mask domain: prompts, single-frame SAM feedback, local
 * brush edits, and atomic Confirm Mask publication, plus the per-view
 * Evidence dependency identity those transitions invalidate. RGB/render
 * lifecycle stays in the View's owner; Mask and Evidence state here are
 * independent and never demote a ready render.
 */
export class AISelectViewMaskSession implements AISelectMaskAuthoring {
    private readonly host: ViewMaskSessionHost;
    private readonly maskProvider: AISelectMaskProvider;
    private readonly maskRegistry: MaskAnnotationRegistry;
    private readonly evidenceRegistry: PerViewEvidenceRegistry;
    private readonly getModelManifestDigest: () => string | null;
    private readonly getPromptAdapterCapabilities: () => PromptAdapterCapabilities | null;
    private readonly onStableMaskPublished: (() => void) | undefined;
    private readonly listeners = new Set<AISelectMaskListener>();
    private targetContextId: string | null = null;
    /** A session may attach after an automatic Stable Mask already exists. */
    private hasObservedHostIdentity = false;
    private lastRgbDigest: string | null = null;
    private promptState: PromptState | null = null;
    /** Prompt semantics last published together with a Stable Mask. */
    private publishedPromptState: PromptState | null = null;
    private automaticMaskStatus: AutomaticMaskStatus = 'none';
    private automaticMaskReview: ViewAssessmentShape | null = null;
    private refinementFallback = false;
    private readonly automaticMaskIdsByPromptDigest = new Map<string, string>();
    private requestStatus: MaskRequestStatus = 'idle';
    private failureKind: MaskFailureKind | undefined;
    private lastErrorMessage: string | undefined;
    private activeMaskRequest: PendingMaskRequest | null = null;
    /**
     * Bumped by every local editing mutation so a late SAM response can
     * never overwrite a newer local brush edit.
     */
    private editingRevision = 0;
    /**
     * Set when prompting arrives while a SAM attempt is still in flight. The
     * Companion reserves one global operation slot and rejects a concurrent
     * attempt with 409 capacityFull, so the latest prompt set resubmits only
     * after the in-flight attempt settles.
     */
    private resubmitMaskRequested = false;
    private nextMaskAttemptOrdinal = 0;
    private nextPromptOrdinal = 0;
    private promptUndoStack: PromptState[] = [];
    private promptRedoStack: PromptState[] = [];
    /**
     * The opaque logits reference of the sole usable automatic Mask. Held
     * only while still in Prompt mode: a subsequent Prompt
     * revision for the same View/RGB sends it as `previousLogitsRef`; a fresh
     * non-refining attempt omits it, and RGB/View/Target changes clear it.
     */
    private refinementLogitsRef: PreviousPredictionLogitsRef | null = null;
    /**
     * RGB digests whose artifact already reached the Companion in this target
     * context. Later requests for a shipped digest may omit the artifact; the
     * Companion resolves its immutable RGB cache by digest (04C contract §5).
     */
    private readonly shippedRgbDigests = new Set<string>();
    /**
     * The mask-local history: Editing-chain maskIds (or null for the empty
     * start state) for the current RGB identity. It is independent from
     * native EditHistory and resets with RGB/context identity.
     */
    private undoStack: (string | null)[] = [];
    private redoStack: (string | null)[] = [];

    constructor(options: AISelectViewMaskSessionOptions) {
        this.host = options.host;
        this.maskProvider = options.maskProvider;
        this.maskRegistry = options.maskRegistry;
        this.evidenceRegistry = options.evidenceRegistry;
        this.getModelManifestDigest =
            options.getModelManifestDigest ?? (() => null);
        this.getPromptAdapterCapabilities =
            options.getPromptAdapterCapabilities ??
            (() => pointOnlyCapabilities);
        this.onStableMaskPublished = options.onStableMaskPublished;
    }

    get state(): AISelectMaskState {
        const rgbDigest = this.currentRgbDigest();
        const view = this.maskRegistry.viewState(
            this.host.viewId,
            rgbDigest ?? ''
        );
        const currentIdentity = this.currentEvidenceIdentity(
            rgbDigest,
            view.stableMask
        );
        const restorableAutoMaskId =
            this.promptState === null
                ? null
                : (this.automaticMaskIdsByPromptDigest.get(
                      this.promptState.digest
                  ) ?? null);
        const promptCapabilities = this.getPromptAdapterCapabilities();
        const hasUnconfirmedPromptChanges = this.promptHasChanged();
        const hasUnconfirmedMaskChanges =
            view.editingMaskIssue !== null ||
            hasSemanticEditingMaskChange(view.editingMask, view.stableMask);
        return Object.freeze({
            viewId: this.host.viewId,
            editingMask: view.editingMask,
            stableMask: view.stableMask,
            editingMaskIssue: view.editingMaskIssue,
            prompts: Object.freeze(
                (this.promptState?.points ?? []).map((point) =>
                    Object.freeze({ ...point })
                )
            ),
            promptState: this.promptState,
            publishedPromptState: this.publishedPromptState,
            promptCapabilities,
            automaticMaskStatus: this.automaticMaskStatus,
            automaticMaskReview: this.automaticMaskReview,
            refinementFallback: this.refinementFallback,
            requestStatus: this.requestStatus,
            ...(this.failureKind === undefined
                ? {}
                : { failureKind: this.failureKind }),
            ...(this.lastErrorMessage === undefined
                ? {}
                : { errorMessage: this.lastErrorMessage }),
            evidence: this.evidenceRegistry.statusFor(
                this.host.viewId,
                currentIdentity
            ),
            canUndo: this.undoStack.length > 0,
            canRedo: this.redoStack.length > 0,
            canUndoPrompt: this.promptUndoStack.length > 0,
            canRedoPrompt: this.promptRedoStack.length > 0,
            canRestoreAuto:
                restorableAutoMaskId !== null &&
                restorableAutoMaskId !== view.editingMask?.maskId,
            hasUnconfirmedChanges:
                this.requestStatus === 'pending' ||
                hasUnconfirmedPromptChanges ||
                hasUnconfirmedMaskChanges,
            hasUnconfirmedPromptChanges,
            hasUnconfirmedMaskChanges
        });
    }

    subscribe(listener: AISelectMaskListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    /**
     * Release every listener. The View owner prunes the session when its View
     * leaves the Gallery; Mask/Evidence records stay registry-owned.
     */
    dispose(): void {
        this.listeners.clear();
    }

    /**
     * The host observed a target-context or RGB identity change. A rotated
     * context disposes this View's target-local Mask/Evidence records; a new
     * RGB identity makes the old prompt set and in-flight SAM work stale
     * while Mask versions stay retained but stop being current.
     */
    notifyHostStateChanged(): void {
        const contextId = this.host.targetContextId();
        const rgbDigest = this.currentRgbDigest();
        // First observation establishes the session-local Prompt/history
        // identity without disposing an automatic Stable Mask that predated
        // this explicit correction session.
        if (!this.hasObservedHostIdentity) {
            this.hasObservedHostIdentity = true;
            this.targetContextId = contextId;
            this.resetForNewRgbIdentity(rgbDigest);
            return;
        }
        if (contextId !== this.targetContextId) {
            this.targetContextId = contextId;
            this.maskRegistry.disposeView(this.host.viewId);
            this.evidenceRegistry.disposeView(this.host.viewId);
            this.resetForNewRgbIdentity(rgbDigest);
            return;
        }
        if (rgbDigest !== this.lastRgbDigest) {
            this.resetForNewRgbIdentity(rgbDigest, true);
            return;
        }
        this.publish();
    }

    /**
     * Add one prompt point and automatically request single-frame SAM
     * feedback for the full current prompt set — no extra apply action.
     */
    async addPrompt(input: AddMaskPromptInput): Promise<void> {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const tool: PromptTool =
            input.polarity === 'include' ? 'positive-point' : 'negative-point';
        this.requirePromptCapability(tool);
        if (
            !Number.isSafeInteger(input.xPx) ||
            !Number.isSafeInteger(input.yPx) ||
            input.xPx < 0 ||
            input.yPx < 0 ||
            input.xPx >= rgb.width ||
            input.yPx >= rgb.height
        ) {
            throw new Error(
                'AI Select prompts must be integer pixels inside the View RGB bounds.'
            );
        }
        const current = this.requirePromptState(rgb.digest);
        const point: PointPrompt = Object.freeze({
            promptId: this.mintPromptId(),
            xPx: input.xPx,
            yPx: input.yPx,
            polarity: input.polarity
        });
        this.publishPromptRevision(
            revisePromptState(current, {
                points: [...current.points, point]
            })
        );
        await this.submitMaskRequest();
    }

    async addBoxPrompt(input: AddBoxPromptInput): Promise<void> {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        this.requirePromptCapability('positive-box');
        const x0Px = Math.min(input.x0Px, input.x1Px);
        const y0Px = Math.min(input.y0Px, input.y1Px);
        const x1Px = Math.max(input.x0Px, input.x1Px);
        const y1Px = Math.max(input.y0Px, input.y1Px);
        if (
            ![x0Px, y0Px, x1Px, y1Px].every(Number.isSafeInteger) ||
            x0Px < 0 ||
            y0Px < 0 ||
            x1Px >= rgb.width ||
            y1Px >= rgb.height ||
            x0Px === x1Px ||
            y0Px === y1Px
        ) {
            throw new Error(
                'AI Select Box prompts must have a non-empty in-bounds pixel area.'
            );
        }
        const current = this.requirePromptState(rgb.digest);
        const box: BoxPrompt = Object.freeze({
            promptId: this.mintPromptId(),
            polarity: 'include',
            x0Px,
            y0Px,
            x1Px,
            y1Px
        });
        // At most one Positive Instance Box: a new box replaces the old one.
        this.publishPromptRevision(
            revisePromptState(current, {
                boxes: [box]
            })
        );
        await this.submitMaskRequest();
    }

    clearPrompts(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const current = this.requirePromptState(rgb.digest);
        this.publishPromptRevision(
            revisePromptState(current, {
                points: [],
                boxes: []
            })
        );
        this.refinementLogitsRef = null;
        this.requestStatus = 'idle';
        this.failureKind = undefined;
        this.resubmitMaskRequested = false;
        this.publish();
    }

    /**
     * Companion Instance replacement invalidates every Companion-local
     * reference minted by the prior Instance (02C availability lifecycle):
     * the held refinement logits ref is dropped, and the next request for an
     * already-seen RGB digest re-ships the exact artifact instead of relying
     * on the prior Instance's RGB cache. Editor-owned Prompt and Mask
     * artifacts keep their own identity and stay valid.
     */
    handleCompanionInstanceChanged(): void {
        this.refinementLogitsRef = null;
        this.shippedRgbDigests.clear();
    }

    /**
     * Prompt Adapter capabilities derive from the live readiness state, so a
     * readiness transition (first connection, recovery, Instance change) must
     * republish: Prompt tools gate on the latest negotiated capability record
     * rather than a stale snapshot from an earlier publish.
     */
    refreshAvailability(): void {
        this.publish();
    }

    undoPromptEdit(): void {
        this.restorePromptHistory(this.promptUndoStack, this.promptRedoStack);
    }

    redoPromptEdit(): void {
        this.restorePromptHistory(this.promptRedoStack, this.promptUndoStack);
    }

    /**
     * Apply one local brush stroke to the Editing Mask. Brush edits are
     * editor-local, never call SAM, and supersede any in-flight SAM response.
     */
    applyBrushStroke(stroke: BrushStroke): void {
        this.applyBrushGesture({
            mode: stroke.mode,
            radiusPx: stroke.radiusPx,
            samples: [{ xPx: stroke.xPx, yPx: stroke.yPx }]
        });
    }

    /**
     * Apply one complete pointer gesture atomically. Linear interpolation in
     * image-pixel space makes the result independent of browser event rate.
     */
    applyBrushGesture(input: ApplyBrushGestureInput): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const strokes = this.interpolateBrushGesture(input);
        const previousEditingMaskId = this.currentEditingMaskId(rgb.digest);
        this.maskRegistry.applyBrushGesture({
            viewId: this.host.viewId,
            rgbDigest: rgb.digest,
            strokes,
            width: rgb.width,
            height: rgb.height
        });
        this.undoStack.push(previousEditingMaskId);
        this.redoStack = [];
        this.supersedeLocalEditing();
    }

    /**
     * Atomically publish the current Editing Mask as the new Stable Mask
     * revision. Until this synchronous swap succeeds, observers keep seeing
     * the previous Stable Mask and current Evidence. Dependent per-view
     * Evidence derives stale by exact RGB/Mask/policy identity; publication
     * never lifts on its own.
     */
    confirmEditingMask(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        this.maskRegistry.confirm(this.host.viewId, rgb.digest);
        this.publishedPromptState = this.promptState;
        this.automaticMaskStatus = 'none';
        this.refinementLogitsRef = null;
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.publish();
        this.onStableMaskPublished?.();
    }

    /**
     * Clear replaces the Editing Mask with an empty manual draft. The Stable
     * Mask and the replaced draft are untouched; the draft stays reachable
     * through mask-local Undo.
     */
    clearEditingMask(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        this.recordEdit(rgb.digest);
        this.maskRegistry.clearEditing(
            this.host.viewId,
            rgb.digest,
            rgb.width,
            rgb.height
        );
        this.supersedeLocalEditing();
    }

    /**
     * Restore Auto brings back the automatically adopted SAM Mask for the
     * current RGB and exact Prompt identity.
     */
    restoreAutoMask(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const promptState = this.promptState;
        const latestMaskId =
            promptState === null
                ? null
                : (this.automaticMaskIdsByPromptDigest.get(
                      promptState.digest
                  ) ?? null);
        const currentEditing = this.maskRegistry.viewState(
            this.host.viewId,
            rgb.digest
        ).editingMask;
        if (latestMaskId === null || latestMaskId === currentEditing?.maskId) {
            throw new Error(
                'AI Select has no restorable automatic Mask for the current RGB and Prompt identity.'
            );
        }
        this.recordEdit(rgb.digest);
        this.maskRegistry.restoreEditing(
            this.host.viewId,
            latestMaskId,
            rgb.digest
        );
        this.supersedeLocalEditing();
    }

    /**
     * Mask-local Undo, routed explicitly by Mask Editor focus. It walks the
     * Editing chain only: Stable Mask publication is a separate atomic act
     * and is never an Undo step.
     */
    undoMaskEdit(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const target = this.undoStack.pop();
        if (target === undefined) {
            throw new Error('AI Select has no Mask edit to undo.');
        }
        this.redoStack.push(this.currentEditingMaskId(rgb.digest));
        this.maskRegistry.restoreEditing(this.host.viewId, target, rgb.digest);
        this.supersedeLocalEditing();
    }

    /** Mask-local Redo, the mirror of `undoMaskEdit`. */
    redoMaskEdit(): void {
        this.requireUnlocked();
        const rgb = this.requireReadyRgb();
        const target = this.redoStack.pop();
        if (target === undefined) {
            throw new Error('AI Select has no Mask edit to redo.');
        }
        this.undoStack.push(this.currentEditingMaskId(rgb.digest));
        this.maskRegistry.restoreEditing(this.host.viewId, target, rgb.digest);
        this.supersedeLocalEditing();
    }

    /**
     * An explicit Retry submits a new attempt for the same prompt set. Retry
     * is not a refinement: it must actually rerun the render/inference path,
     * so the held logits reference is omitted (04C contract §7).
     */
    async retryMaskRequest(): Promise<void> {
        this.requireUnlocked();
        this.requireReadyRgb();
        if (
            this.promptState === null ||
            !promptStateHasConstraints(this.promptState)
        ) {
            throw new Error('AI Select has no Mask prompt set to retry.');
        }
        await this.submitMaskRequest({ omitRefinementRef: true });
    }

    private async submitMaskRequest(
        options: { readonly omitRefinementRef?: boolean } = {}
    ): Promise<void> {
        if (this.activeMaskRequest !== null) {
            // One in-flight SAM attempt per view: a concurrent attempt would
            // hit the Companion's single operation slot as a 409. Supersede
            // the in-flight response locally and resubmit the latest prompt
            // set as a fresh attempt once the slot settles.
            this.resubmitMaskRequested = true;
            this.editingRevision += 1;
            return;
        }
        const modelManifestDigest = this.getModelManifestDigest();
        if (modelManifestDigest === null || modelManifestDigest.length === 0) {
            this.failMaskRequest(
                'AI Select requires a configured Model Manifest before SAM mask production.'
            );
            return;
        }
        const promptCapabilities = this.getPromptAdapterCapabilities();
        if (promptCapabilities === null || this.promptState === null) {
            this.failMaskRequest(
                'AI Select requires negotiated Prompt Adapter capabilities before Mask production.'
            );
            return;
        }
        const rgbDigest = this.promptState.rgbDigest;
        const refinementRef = this.currentRefinementRef(
            promptCapabilities,
            options.omitRefinementRef === true
        );
        const request = this.host.createMaskRequest(
            this.promptState,
            this.mintMaskAttemptId(),
            modelManifestDigest,
            promptCapabilities.capabilityDigest,
            autoMaskProposalPolicyVersion,
            {
                includeRgbArtifact: !this.shippedRgbDigests.has(rgbDigest),
                ...(refinementRef === null
                    ? {}
                    : { previousLogitsRef: refinementRef })
            }
        );
        if (request === null) {
            this.failMaskRequest(
                'AI Select requires an RGB Ready View before SAM mask production.'
            );
            return;
        }
        const pending: PendingMaskRequest = {
            request,
            editingRevision: this.editingRevision,
            promptRevision: this.promptState.revision
        };
        this.activeMaskRequest = pending;
        this.requestStatus = 'pending';
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.publish();

        let response: MaskResultResponse;
        try {
            response = await this.maskProvider.produceMask(request);
        } catch (error) {
            if (!this.isCurrentMaskRequest(pending)) {
                this.discardStaleMaskRequest(pending);
                return;
            }
            this.failMaskRequest(
                errorMessage(error),
                error instanceof MaskArtifactInvalidError ||
                    (error instanceof SelectionServiceTransportError &&
                        error.serviceCode === 'incompleteMaskSet')
                    ? 'maskArtifactInvalid'
                    : 'maskResultFailed'
            );
            this.resubmitLatestPromptSet();
            return;
        }
        if (!this.isCurrentMaskRequest(pending)) {
            this.discardStaleMaskRequest(pending);
            return;
        }
        if (!isMaskResultResponse(response)) {
            this.failMaskRequest(
                'The Selection Service Companion returned an invalid Mask artifact publication.',
                'maskArtifactInvalid'
            );
            this.resubmitLatestPromptSet();
            return;
        }
        if (!this.host.acceptsMaskResponse(response, request)) {
            this.failMaskRequest(
                'The Selection Service Companion returned an invalid or stale Mask binding.'
            );
            this.resubmitLatestPromptSet();
            return;
        }
        try {
            // The Companion accepted this RGB digest; later attempts in this
            // target context may reference it without reshipping the bytes.
            this.shippedRgbDigests.add(request.rgbDigest);
            this.activeMaskRequest = null;
            this.requestStatus = 'idle';
            this.refinementFallback = response.result.refinementFallback;
            if (response.result.status === 'unavailable') {
                this.automaticMaskStatus = 'unavailable';
                this.automaticMaskReview = null;
                this.refinementLogitsRef = null;
            } else {
                const promptState = this.promptState;
                if (promptState === null) {
                    throw new Error(
                        'AI Select cannot adopt a Mask without its Prompt identity.'
                    );
                }
                this.recordEdit(request.rgbDigest);
                const editing = this.maskRegistry.registerSamResult({
                    viewId: this.host.viewId,
                    rgbDigest: request.rgbDigest,
                    artifact: response.result.mask,
                    prompts: promptState.points.map((point) => ({
                        promptId: point.promptId,
                        xPx: point.xPx,
                        yPx: point.yPx,
                        polarity: point.polarity
                    }))
                });
                this.automaticMaskIdsByPromptDigest.set(
                    promptState.digest,
                    editing.maskId
                );
                this.automaticMaskStatus = 'editing';
                this.automaticMaskReview = immutableTransportCopy(
                    response.result.review
                );
                this.refinementLogitsRef =
                    response.result.logitsRef === undefined
                        ? null
                        : immutableTransportCopy(response.result.logitsRef);
                this.editingRevision += 1;
            }
        } catch (error) {
            this.failMaskRequest(errorMessage(error));
            this.resubmitLatestPromptSet();
            return;
        }
        this.activeMaskRequest = null;
        this.requestStatus = 'idle';
        this.failureKind = undefined;
        this.publish();
        this.resubmitLatestPromptSet();
    }

    /**
     * A superseded attempt settled: release the slot it held (only when the
     * tracked request is still this one) so the latest prompt set can
     * actually resubmit instead of deferring against itself.
     */
    private discardStaleMaskRequest(pending: PendingMaskRequest): void {
        if (this.activeMaskRequest === pending) {
            this.activeMaskRequest = null;
        }
        this.resubmitLatestPromptSet();
    }

    private resubmitLatestPromptSet(): void {
        if (!this.resubmitMaskRequested) {
            return;
        }
        this.resubmitMaskRequested = false;
        if (
            this.promptState === null ||
            !promptStateHasConstraints(this.promptState)
        ) {
            return;
        }
        this.submitMaskRequest().catch((error: unknown) => {
            console.error(error);
        });
    }

    private isCurrentMaskRequest(pending: PendingMaskRequest): boolean {
        return (
            this.activeMaskRequest === pending &&
            pending.editingRevision === this.editingRevision &&
            pending.promptRevision === this.promptState?.revision
        );
    }

    private failMaskRequest(
        message: string,
        failureKind: MaskFailureKind = 'maskResultFailed'
    ): void {
        this.activeMaskRequest = null;
        this.requestStatus = 'failed';
        this.failureKind = failureKind;
        this.lastErrorMessage = message;
        this.publish();
    }

    private resetForNewRgbIdentity(
        rgbDigest: string | null,
        detachSupersededEditing = false
    ): void {
        this.lastRgbDigest = rgbDigest;
        if (detachSupersededEditing) {
            this.maskRegistry.detachEditing(this.host.viewId);
        }
        this.promptState =
            rgbDigest === null
                ? null
                : createEmptyPromptState(this.host.viewId, rgbDigest);
        this.publishedPromptState = this.promptState;
        this.automaticMaskStatus = 'none';
        this.automaticMaskReview = null;
        this.refinementFallback = false;
        this.refinementLogitsRef = null;
        this.shippedRgbDigests.clear();
        this.automaticMaskIdsByPromptDigest.clear();
        this.activeMaskRequest = null;
        this.resubmitMaskRequested = false;
        this.requestStatus = 'idle';
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.editingRevision += 1;
        this.undoStack = [];
        this.redoStack = [];
        this.promptUndoStack = [];
        this.promptRedoStack = [];
        this.publish();
    }

    private currentRgbDigest(): string | null {
        return this.host.currentRgb()?.digest ?? null;
    }

    private currentEvidenceIdentity(
        rgbDigest: string | null,
        stableMask: MaskAnnotation | null
    ): EvidenceDependencyIdentity | null {
        if (rgbDigest === null || stableMask === null) {
            return null;
        }
        return {
            viewId: this.host.viewId,
            rgbDigest,
            stableMaskDigest: stableMask.artifact.digest,
            evidencePolicyDigest: aiSelectEvidencePolicyVersion
        };
    }

    private requireUnlocked(): void {
        const lockReason = this.host.lockReason();
        if (lockReason !== null) {
            throw new Error(lockReason);
        }
    }

    private currentEditingMaskId(rgbDigest: string): string | null {
        return (
            this.maskRegistry.viewState(this.host.viewId, rgbDigest).editingMask
                ?.maskId ?? null
        );
    }

    private interpolateBrushGesture(
        input: ApplyBrushGestureInput
    ): readonly BrushStroke[] {
        if (
            !Number.isSafeInteger(input.radiusPx) ||
            input.radiusPx <= 0 ||
            input.samples.length === 0
        ) {
            throw new Error(
                'AI Select brush gestures need samples and a positive integer radius.'
            );
        }
        const strokes: BrushStroke[] = [];
        let previous: BrushGestureSample | null = null;
        for (const sample of input.samples) {
            if (
                !Number.isSafeInteger(sample.xPx) ||
                !Number.isSafeInteger(sample.yPx)
            ) {
                throw new Error(
                    'AI Select brush gesture samples must use integer pixels.'
                );
            }
            if (previous === null) {
                strokes.push({
                    xPx: sample.xPx,
                    yPx: sample.yPx,
                    radiusPx: input.radiusPx,
                    mode: input.mode
                });
                previous = sample;
                continue;
            }
            const dx = sample.xPx - previous.xPx;
            const dy = sample.yPx - previous.yPx;
            const steps = Math.max(Math.abs(dx), Math.abs(dy));
            for (let step = 1; step <= steps; step += 1) {
                strokes.push({
                    xPx: Math.round(previous.xPx + (dx * step) / steps),
                    yPx: Math.round(previous.yPx + (dy * step) / steps),
                    radiusPx: input.radiusPx,
                    mode: input.mode
                });
            }
            previous = sample;
        }
        return Object.freeze(strokes);
    }

    /**
     * Every local editing mutation pushes the previous Editing-chain
     * position onto the mask-local Undo stack and clears Redo.
     */
    private recordEdit(rgbDigest: string): void {
        this.undoStack.push(this.currentEditingMaskId(rgbDigest));
        this.redoStack = [];
    }

    /**
     * A local editing change supersedes in-flight SAM work: the late
     * response must never overwrite user-authored content.
     */
    private supersedeLocalEditing(): void {
        this.editingRevision += 1;
        // A local Paint/Erase/Clear result becomes the Editing authority while
        // the adopted automatic Mask remains reachable through Restore Auto.
        this.automaticMaskStatus = 'editing';
        if (this.activeMaskRequest !== null) {
            this.requestStatus = 'idle';
        }
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.publish();
    }

    private promptHasChanged(): boolean {
        const current = this.promptState;
        const published = this.publishedPromptState;
        if (current === null || published === null) {
            return current !== published;
        }
        const pointKey = (point: PointPrompt): string =>
            `${point.polarity}:${point.xPx}:${point.yPx}`;
        const boxKey = (box: BoxPrompt): string =>
            `${box.polarity}:${box.x0Px}:${box.y0Px}:${box.x1Px}:${box.y1Px}`;
        const currentPoints = current.points.map(pointKey).sort();
        const publishedPoints = published.points.map(pointKey).sort();
        const currentBoxes = current.boxes.map(boxKey).sort();
        const publishedBoxes = published.boxes.map(boxKey).sort();
        return (
            current.rgbDigest !== published.rgbDigest ||
            currentPoints.length !== publishedPoints.length ||
            currentBoxes.length !== publishedBoxes.length ||
            currentPoints.some(
                (value, index) => value !== publishedPoints[index]
            ) ||
            currentBoxes.some((value, index) => value !== publishedBoxes[index])
        );
    }

    private requireReadyRgb(): AnchorRgbArtifact {
        const rgb = this.host.currentRgb();
        if (rgb === null) {
            throw new Error(
                'AI Select requires an RGB Ready View for Mask authoring.'
            );
        }
        return rgb;
    }

    private mintMaskAttemptId(): string {
        if (this.nextMaskAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select mask attempt identity cannot advance safely.'
            );
        }
        this.nextMaskAttemptOrdinal += 1;
        // The attempt identity is View-scoped so same-attempt replay stays
        // idempotent per View even when several Views run the 04C path.
        return `${this.host.viewId}:proposal-attempt-${this.nextMaskAttemptOrdinal}`;
    }

    private mintPromptId(): string {
        if (this.nextPromptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error('AI Select prompt identity cannot advance safely.');
        }
        this.nextPromptOrdinal += 1;
        return `${this.host.viewId}:prompt-${this.nextPromptOrdinal}`;
    }

    private requirePromptState(rgbDigest: string): PromptState {
        if (
            this.promptState === null ||
            this.promptState.rgbDigest !== rgbDigest
        ) {
            throw new Error(
                'AI Select PromptState is not bound to the current View RGB.'
            );
        }
        return this.promptState;
    }

    /**
     * The held logits reference crosses the boundary only for a same-View,
     * same-RGB, same-target refinement attempt on an adapter that advertised
     * previous-logits refinement; a fresh attempt never reuses it silently.
     */
    private currentRefinementRef(
        capabilities: PromptAdapterCapabilities,
        omitted: boolean
    ): PreviousPredictionLogitsRef | null {
        const ref = this.refinementLogitsRef;
        if (
            omitted ||
            ref === null ||
            !capabilities.previousLogitsRefinement ||
            this.promptState === null ||
            ref.viewId !== this.promptState.viewId ||
            ref.rgbDigest !== this.promptState.rgbDigest ||
            ref.targetContextId !== this.targetContextId
        ) {
            return null;
        }
        return ref;
    }

    private requirePromptCapability(tool: PromptTool): void {
        const capabilities = this.getPromptAdapterCapabilities();
        if (capabilities === null) {
            throw new Error(
                'AI Select Prompt Adapter capabilities are unavailable.'
            );
        }
        const reason = promptToolCapabilityReason(tool, capabilities);
        if (reason !== null) {
            throw new Error(reason);
        }
    }

    private publishPromptRevision(next: PromptState): void {
        if (this.promptState !== null) {
            this.promptUndoStack.push(this.promptState);
        }
        this.promptState = next;
        this.promptRedoStack = [];
        this.automaticMaskStatus = 'none';
        this.automaticMaskReview = null;
        this.refinementFallback = false;
        this.editingRevision += 1;
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.publish();
    }

    private restorePromptHistory(
        source: PromptState[],
        destination: PromptState[]
    ): void {
        this.requireUnlocked();
        this.requireReadyRgb();
        const target = source.pop();
        if (target === undefined || this.promptState === null) {
            throw new Error('AI Select has no Prompt edit to restore.');
        }
        destination.push(this.promptState);
        this.promptState = target;
        this.automaticMaskStatus = 'none';
        this.automaticMaskReview = null;
        this.refinementFallback = false;
        this.resubmitMaskRequested = false;
        this.requestStatus = 'idle';
        this.editingRevision += 1;
        this.failureKind = undefined;
        this.lastErrorMessage = undefined;
        this.publish();
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
