import type { AnchorRgbArtifact } from './anchor-render-service';
import type { PerViewEvidenceRegistry } from './evidence-state';
import type { AISelectGeneratedViewController } from './generated-view-controller';
import type { MaskAnnotationRegistry } from './mask-registry';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse,
    PreviousPredictionLogitsRef
} from './mask-service';
import type { PromptAdapterCapabilities, PromptState } from './prompt-state';
import {
    AISelectViewMaskSession,
    type AISelectMaskState
} from './view-mask-session';

export interface AISelectUserViewMaskControllerOptions {
    readonly generatedViews: AISelectGeneratedViewController;
    readonly maskProvider: AISelectMaskProvider;
    readonly maskRegistry: MaskAnnotationRegistry;
    readonly evidenceRegistry: PerViewEvidenceRegistry;
    readonly getModelManifestDigest?: () => string | null;
    readonly getPromptAdapterCapabilities?: () => PromptAdapterCapabilities | null;
}

/**
 * Owns explicit Mask authoring sessions for Gallery Views. A user-added View
 * and a manually corrected Generated View share the same exact-RGB
 * Prompt/Brush/Confirm path; automatic Route-B acquisition remains owned by
 * the Generated View controller. Sessions are created when a View is first
 * opened for editing and leave with that View.
 */
export class AISelectUserViewMaskController {
    private readonly generatedViews: AISelectGeneratedViewController;
    private readonly maskProvider: AISelectMaskProvider;
    private readonly maskRegistry: MaskAnnotationRegistry;
    private readonly evidenceRegistry: PerViewEvidenceRegistry;
    private readonly getModelManifestDigest: (() => string | null) | undefined;
    private readonly getPromptAdapterCapabilities:
        (() => PromptAdapterCapabilities | null) | undefined;
    private readonly sessions = new Map<string, AISelectViewMaskSession>();
    private readonly sessionUnsubscribes = new Map<string, () => void>();
    private readonly listeners = new Set<() => void>();

    constructor(options: AISelectUserViewMaskControllerOptions) {
        this.generatedViews = options.generatedViews;
        this.maskProvider = options.maskProvider;
        this.maskRegistry = options.maskRegistry;
        this.evidenceRegistry = options.evidenceRegistry;
        this.getModelManifestDigest = options.getModelManifestDigest;
        this.getPromptAdapterCapabilities =
            options.getPromptAdapterCapabilities;
        this.generatedViews.subscribe(() => this.syncSessions());
    }

    /** Return or lazily create the Mask authoring session for one Gallery View. */
    sessionFor(viewId: string): AISelectViewMaskSession | null {
        const existing = this.sessions.get(viewId);
        if (existing !== undefined) {
            return existing;
        }
        if (
            !this.generatedViews.state.views.some(
                (view) => view.viewId === viewId
            )
        ) {
            return null;
        }
        const session = this.createSession(viewId);
        this.sessions.set(viewId, session);
        // Establish identity before this controller forwards the session's
        // first publication to the Dock.
        session.notifyHostStateChanged();
        this.sessionUnsubscribes.set(
            viewId,
            session.subscribe(() => this.notify())
        );
        return session;
    }

    stateFor(viewId: string): AISelectMaskState | null {
        return this.sessions.get(viewId)?.state ?? null;
    }

    /**
     * Observe any Gallery View Mask session publication (session-local Mask
     * work does not pass through the Generated View controller's state).
     */
    subscribe(listener: () => void): () => void {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    private notify(): void {
        this.listeners.forEach((listener) => listener());
    }

    /** 02C Instance replacement invalidates every session's held refs. */
    handleCompanionInstanceChanged(): void {
        for (const session of this.sessions.values()) {
            session.handleCompanionInstanceChanged();
        }
    }

    /** Readiness transitions republish capability gating in every session. */
    refreshAvailability(): void {
        for (const session of this.sessions.values()) {
            session.refreshAvailability();
        }
    }

    private syncSessions(): void {
        const views = this.generatedViews.state.views;
        const viewIds = new Set(views.map((view) => view.viewId));
        for (const [viewId, session] of this.sessions) {
            if (!viewIds.has(viewId)) {
                this.sessionUnsubscribes.get(viewId)?.();
                this.sessionUnsubscribes.delete(viewId);
                session.dispose();
                this.sessions.delete(viewId);
            }
        }
        for (const session of this.sessions.values()) {
            session.notifyHostStateChanged();
        }
        this.notify();
    }

    private currentRgbFor(viewId: string): AnchorRgbArtifact | null {
        const view = this.generatedViews.state.views.find(
            (entry) => entry.viewId === viewId
        );
        if (
            view === undefined ||
            view.renderStatus !== 'ready' ||
            view.rgb === undefined
        ) {
            return null;
        }
        return view.rgb;
    }

    private createSession(viewId: string): AISelectViewMaskSession {
        return new AISelectViewMaskSession({
            host: {
                viewId,
                targetContextId: () =>
                    this.generatedViews.getRunTargetContextId(),
                currentRgb: () => this.currentRgbFor(viewId),
                // View correction is always target-local; run currency is
                // enforced again when the exact request is built.
                lockReason: () => null,
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
                    this.generatedViews.createViewMaskRequest(
                        viewId,
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
                ): boolean =>
                    this.generatedViews.acceptsViewMaskResponse(
                        response,
                        request
                    )
            },
            maskProvider: this.maskProvider,
            maskRegistry: this.maskRegistry,
            evidenceRegistry: this.evidenceRegistry,
            ...(this.getModelManifestDigest === undefined
                ? {}
                : { getModelManifestDigest: this.getModelManifestDigest }),
            ...(this.getPromptAdapterCapabilities === undefined
                ? {}
                : {
                      getPromptAdapterCapabilities:
                          this.getPromptAdapterCapabilities
                  }),
            onStableMaskPublished: () =>
                this.generatedViews.noteViewStablePublication(viewId)
        });
    }
}
