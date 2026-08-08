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
 * Owns the 04C Mask authoring sessions of user-added AIVews. Each user-owned
 * View gets one session bound to its exact authoritative RGB and CameraBinding
 * through the Generated View controller's run identity; sessions appear with
 * their View and are pruned when the View leaves the Gallery. View source
 * never determines trust: a user View's Prompt/Brush/Confirm flow is the
 * Anchor's flow, minus the confirmed-Anchor authoring lock.
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

    /** The Mask authoring session of one user-owned View, if it exists. */
    sessionFor(viewId: string): AISelectViewMaskSession | null {
        return this.sessions.get(viewId) ?? null;
    }

    stateFor(viewId: string): AISelectMaskState | null {
        return this.sessions.get(viewId)?.state ?? null;
    }

    /**
     * Observe any user View Mask session publication (session-local Mask
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
        const userViewIds = new Set(
            views
                .filter((view) => view.source === 'user-added')
                .map((view) => view.viewId)
        );
        for (const [viewId, session] of this.sessions) {
            if (!userViewIds.has(viewId)) {
                this.sessionUnsubscribes.get(viewId)?.();
                this.sessionUnsubscribes.delete(viewId);
                session.dispose();
                this.sessions.delete(viewId);
            }
        }
        for (const viewId of userViewIds) {
            if (!this.sessions.has(viewId)) {
                const session = this.createSession(viewId);
                this.sessions.set(viewId, session);
                this.sessionUnsubscribes.set(
                    viewId,
                    session.subscribe(() => this.notify())
                );
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
            view.source !== 'user-added' ||
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
                // User-owned Views are never locked by the Anchor
                // confirmation; run currency is enforced at request build.
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
                    this.generatedViews.createUserViewMaskRequest(
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
                    this.generatedViews.acceptsUserViewMaskResponse(
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
                this.generatedViews.noteUserViewStablePublication(viewId)
        });
    }
}
