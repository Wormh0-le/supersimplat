import type { PackedSceneSnapshot } from '../scene-snapshot-binary';
import {
    anchorRenderResponseMatchesRequest,
    decodePngBase64,
    isAnchorRenderResponse,
    validatePngDecodable,
    type AISelectAnchorRenderer,
    type AnchorRenderRequest,
    type AnchorRenderResponse,
    type AnchorRgbArtifact
} from './anchor-render-service';
import {
    areCameraBindingsEqual,
    copyCameraBinding,
    scaleCameraBindingForPreview,
    withCameraBindingPose,
    type CameraBinding
} from './camera-binding';
import {
    CurrentTargetContextKernel,
    areTargetDependencyTokensEqual,
    type AIRequestBinding,
    type AITarget,
    type CurrentTargetContext,
    type TargetDependencyToken
} from './current-target-context';

export type AnchorRenderStatus = 'rendering' | 'ready' | 'failed';
export type AnchorPreviewKind = 'interactive' | 'final';

/** A transient display artifact; it is never a formal inference input. */
export interface AnchorPreviewArtifact {
    readonly cameraBinding: CameraBinding;
    readonly rgb: AnchorRgbArtifact;
}

export interface AnchorPreview {
    readonly kind: AnchorPreviewKind;
    readonly cameraBinding: CameraBinding;
    readonly requestBinding: AIRequestBinding;
    readonly renderStatus: AnchorRenderStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly errorMessage?: string;
}

export interface AnchorAIView {
    readonly viewId: 'anchor-view';
    readonly source: 'anchor';
    /** The current full-resolution Anchor CameraBinding. */
    readonly cameraBinding: CameraBinding;
    readonly requestBinding: AIRequestBinding;
    readonly renderStatus: AnchorRenderStatus;
    /** Present only when this exact full-resolution binding is ready. */
    readonly rgb?: AnchorRgbArtifact;
    readonly rendererId?: 'gsplat';
    readonly errorMessage?: string;
    readonly preview?: AnchorPreview;
    /** Retained for display/retry only, never for inference. */
    readonly lastValidPreview?: AnchorPreviewArtifact;
}

export interface AISelectAnchorState {
    readonly context: CurrentTargetContext | null;
    readonly anchor: AnchorAIView | null;
}

export interface StartAnchorInput {
    readonly target: AITarget;
    readonly dependencyToken: TargetDependencyToken;
    readonly getCurrentDependencyToken: () => TargetDependencyToken;
    readonly snapshot: PackedSceneSnapshot;
    readonly cameraBinding: CameraBinding;
}

export type AISelectAnchorListener = (state: AISelectAnchorState) => void;

interface PendingAnchorRender {
    readonly kind: AnchorPreviewKind;
    readonly request: AnchorRenderRequest;
    readonly anchorCameraBinding: CameraBinding;
    readonly context: CurrentTargetContext;
}

interface AnchorViewDetails {
    readonly rgb?: AnchorRgbArtifact;
    readonly rendererId?: 'gsplat';
    readonly errorMessage?: string;
    readonly preview?: AnchorPreview;
    readonly lastValidPreview?: AnchorPreviewArtifact;
}

const copyRequestBinding = (binding: AIRequestBinding): AIRequestBinding => {
    return Object.freeze({
        targetContextId: binding.targetContextId,
        contextRevision: binding.contextRevision,
        dependencyToken: Object.freeze({
            splatId: binding.dependencyToken.splatId,
            renderStateToken: binding.dependencyToken.renderStateToken,
            geometryToken: binding.dependencyToken.geometryToken,
            gaussianIdentityToken:
                binding.dependencyToken.gaussianIdentityToken,
            worldTransformToken: binding.dependencyToken.worldTransformToken
        })
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

const copyPreviewArtifact = (
    preview: AnchorPreviewArtifact
): AnchorPreviewArtifact => {
    return Object.freeze({
        cameraBinding: copyCameraBinding(preview.cameraBinding),
        rgb: copyRgb(preview.rgb)
    });
};

const copyPreview = (preview: AnchorPreview): AnchorPreview => {
    return Object.freeze({
        kind: preview.kind,
        cameraBinding: copyCameraBinding(preview.cameraBinding),
        requestBinding: copyRequestBinding(preview.requestBinding),
        renderStatus: preview.renderStatus,
        ...(preview.rgb === undefined ? {} : { rgb: copyRgb(preview.rgb) }),
        ...(preview.errorMessage === undefined
            ? {}
            : { errorMessage: preview.errorMessage })
    });
};

const copyAnchor = (anchor: AnchorAIView): AnchorAIView => {
    return Object.freeze({
        viewId: anchor.viewId,
        source: anchor.source,
        cameraBinding: copyCameraBinding(anchor.cameraBinding),
        requestBinding: copyRequestBinding(anchor.requestBinding),
        renderStatus: anchor.renderStatus,
        ...(anchor.rgb === undefined ? {} : { rgb: copyRgb(anchor.rgb) }),
        ...(anchor.rendererId === undefined
            ? {}
            : { rendererId: anchor.rendererId }),
        ...(anchor.errorMessage === undefined
            ? {}
            : { errorMessage: anchor.errorMessage }),
        ...(anchor.preview === undefined
            ? {}
            : { preview: copyPreview(anchor.preview) }),
        ...(anchor.lastValidPreview === undefined
            ? {}
            : {
                  lastValidPreview: copyPreviewArtifact(anchor.lastValidPreview)
              })
    });
};

const createAnchor = (
    cameraBinding: CameraBinding,
    requestBinding: AIRequestBinding,
    renderStatus: AnchorRenderStatus,
    details: AnchorViewDetails = {}
): AnchorAIView => {
    return copyAnchor({
        viewId: 'anchor-view',
        source: 'anchor',
        cameraBinding,
        requestBinding,
        renderStatus,
        ...details
    });
};

const copyState = (state: AISelectAnchorState): AISelectAnchorState => {
    return Object.freeze({
        context: state.context,
        anchor: state.anchor === null ? null : copyAnchor(state.anchor)
    });
};

const errorMessage = (error: unknown): string => {
    return error instanceof Error && error.message
        ? error.message
        : 'Anchor rendering failed.';
};

const snapshotLeaseKey = (request: AnchorRenderRequest): string => {
    return [
        request.target.splatId,
        request.snapshot.sceneId,
        request.snapshot.sceneVersion,
        request.snapshot.contentDigest
    ].join('\u0000');
};

const formalDetails = (anchor: AnchorAIView): AnchorViewDetails => {
    if (anchor.renderStatus !== 'ready' || anchor.rgb === undefined) {
        return {};
    }
    return {
        rgb: anchor.rgb,
        ...(anchor.rendererId === undefined
            ? {}
            : { rendererId: anchor.rendererId })
    };
};

const latestValidPreview = (
    anchor: AnchorAIView
): AnchorPreviewArtifact | undefined => {
    if (anchor.renderStatus === 'ready' && anchor.rgb !== undefined) {
        return {
            cameraBinding: anchor.cameraBinding,
            rgb: anchor.rgb
        };
    }
    return anchor.lastValidPreview;
};

/**
 * The first Final Spec product controller. It owns one Anchor and separates
 * transient Camera Inspection previews from fixed-resolution inference RGB.
 */
export class AISelectAnchorController {
    private readonly renderer: AISelectAnchorRenderer;
    private readonly contexts = new CurrentTargetContextKernel();
    private readonly listeners = new Set<AISelectAnchorListener>();
    private anchor: AnchorAIView | null = null;
    private getCurrentDependencyToken: (() => TargetDependencyToken) | null =
        null;
    /** The current full-resolution Anchor request template. */
    private activeRequest: AnchorRenderRequest | null = null;
    /** The one latest-only render that may publish for the current revision. */
    private activeRender: PendingAnchorRender | null = null;
    private initialAnchorCameraBinding: CameraBinding | null = null;
    private retainedSnapshots = new Map<string, AnchorRenderRequest>();
    private pendingSnapshotRenders = new Map<string, number>();
    /**
     * Mint one fresh render-attempt identity per actual render execution. It
     * never resets within this controller so a late replay of an older
     * context cannot collide with a newer attempt.
     */
    private nextRenderAttemptOrdinal = 0;

    constructor(options: { renderer: AISelectAnchorRenderer }) {
        this.renderer = options.renderer;
    }

    get state(): AISelectAnchorState {
        return copyState({
            context: this.contexts.current,
            anchor: this.anchor
        });
    }

    getAnchorCameraBinding(): CameraBinding | null {
        return this.anchor === null
            ? null
            : copyCameraBinding(this.anchor.cameraBinding);
    }

    subscribe(listener: AISelectAnchorListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    async start(input: StartAnchorInput): Promise<void> {
        if (this.contexts.current !== null) {
            throw new Error(
                'AI Select already has a Current Target Context. Restart it instead.'
            );
        }
        await this.begin(input, false);
    }

    async restart(input: StartAnchorInput): Promise<void> {
        await this.begin(input, true);
    }

    exit(): void {
        this.contexts.dispose();
        this.getCurrentDependencyToken = null;
        this.anchor = null;
        this.activeRequest = null;
        this.activeRender = null;
        this.initialAnchorCameraBinding = null;
        this.releaseIdleSnapshots();
        this.publish();
    }

    /** Update only the Anchor pose; projection stays fixed for formal renders. */
    updateAnchorCameraPose(cameraToWorld: readonly number[]): void {
        const anchor = this.requireAnchor();
        if (anchor.cameraBinding.revision >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'Anchor CameraBinding revision cannot advance safely.'
            );
        }
        const nextBinding = withCameraBindingPose(
            anchor.cameraBinding,
            cameraToWorld,
            anchor.cameraBinding.revision + 1
        );
        this.reviseAnchor(nextBinding);
    }

    async renderInteractivePreview(): Promise<void> {
        const anchor = this.requireAnchor();
        await this.submitRender(
            'interactive',
            scaleCameraBindingForPreview(anchor.cameraBinding)
        );
    }

    async renderFinalPreview(): Promise<void> {
        const anchor = this.requireAnchor();
        await this.submitRender('final', anchor.cameraBinding);
    }

    async resetAnchor(): Promise<void> {
        const initial = this.initialAnchorCameraBinding;
        if (initial === null) {
            throw new Error(
                'AI Select has no initial Anchor CameraBinding to reset.'
            );
        }
        this.updateAnchorCameraPose(initial.cameraToWorld);
        await this.renderFinalPreview();
    }

    async retryAnchorPreview(): Promise<void> {
        if (this.anchor?.preview?.kind === 'interactive') {
            await this.renderInteractivePreview();
            return;
        }
        await this.renderFinalPreview();
    }

    private async begin(
        input: StartAnchorInput,
        restart: boolean
    ): Promise<void> {
        const effectiveDependencyToken = input.getCurrentDependencyToken();
        if (
            !areTargetDependencyTokensEqual(
                input.dependencyToken,
                effectiveDependencyToken
            )
        ) {
            throw new Error(
                'The Target Splat changed while its Anchor SceneSnapshot was being prepared.'
            );
        }
        const context = restart
            ? this.contexts.restart({
                  target: input.target,
                  dependencyToken: input.dependencyToken
              })
            : this.contexts.start({
                  target: input.target,
                  dependencyToken: input.dependencyToken
              });
        this.getCurrentDependencyToken = input.getCurrentDependencyToken;
        const requestBinding = this.contexts.createRequestBinding();
        const cameraBinding = copyCameraBinding(input.cameraBinding);
        this.initialAnchorCameraBinding = cameraBinding;
        this.activeRequest = this.createRequest(
            input.target,
            input.snapshot,
            requestBinding,
            cameraBinding
        );
        this.activeRender = null;
        this.anchor = createAnchor(cameraBinding, requestBinding, 'rendering');
        this.releaseIdleSnapshots();
        this.publish();
        await this.submitRender('final', cameraBinding, context);
    }

    private reviseAnchor(cameraBinding: CameraBinding): void {
        const activeRequest = this.activeRequest;
        if (activeRequest === null) {
            throw new Error(
                'AI Select requires an active Anchor render request.'
            );
        }
        this.contexts.revise();
        const requestBinding = this.contexts.createRequestBinding();
        this.activeRequest = this.createRequest(
            activeRequest.target,
            activeRequest.snapshot,
            requestBinding,
            cameraBinding
        );
        this.activeRender = null;
        const previous = this.requireAnchor();
        const lastValid = latestValidPreview(previous);
        this.anchor = createAnchor(
            cameraBinding,
            requestBinding,
            'rendering',
            lastValid === undefined ? {} : { lastValidPreview: lastValid }
        );
        this.publish();
    }

    private createRequest(
        target: AITarget,
        snapshot: PackedSceneSnapshot,
        requestBinding: AIRequestBinding,
        cameraBinding: CameraBinding
    ): AnchorRenderRequest {
        return Object.freeze({
            requestBinding: copyRequestBinding(requestBinding),
            target: Object.freeze({ splatId: target.splatId }),
            snapshot,
            cameraBinding: copyCameraBinding(cameraBinding),
            renderAttemptId: this.mintRenderAttemptId()
        });
    }

    private mintRenderAttemptId(): string {
        if (this.nextRenderAttemptOrdinal >= Number.MAX_SAFE_INTEGER) {
            throw new Error(
                'AI Select render attempt identity cannot advance safely.'
            );
        }
        this.nextRenderAttemptOrdinal += 1;
        return `anchor-render-attempt-${this.nextRenderAttemptOrdinal}`;
    }

    private async submitRender(
        kind: AnchorPreviewKind,
        renderCameraBinding: CameraBinding,
        initialContext?: CurrentTargetContext
    ): Promise<void> {
        const activeRequest = this.activeRequest;
        const anchor = this.requireAnchor();
        const context = initialContext ?? this.contexts.current;
        if (activeRequest === null || context === null) {
            throw new Error(
                'AI Select requires an active Anchor render request.'
            );
        }
        const request = this.createRequest(
            activeRequest.target,
            activeRequest.snapshot,
            activeRequest.requestBinding,
            renderCameraBinding
        );
        const pending = Object.freeze({
            kind,
            request,
            anchorCameraBinding: copyCameraBinding(anchor.cameraBinding),
            context
        });
        this.activeRender = pending;
        this.retainSnapshot(request);
        const lastValid = latestValidPreview(anchor);
        const preview: AnchorPreview = {
            kind,
            cameraBinding: request.cameraBinding,
            requestBinding: request.requestBinding,
            renderStatus: 'rendering'
        };
        this.anchor = createAnchor(
            anchor.cameraBinding,
            anchor.requestBinding,
            kind === 'final' ? 'rendering' : anchor.renderStatus,
            {
                ...(kind === 'interactive' ? formalDetails(anchor) : {}),
                preview,
                ...(lastValid === undefined
                    ? {}
                    : { lastValidPreview: lastValid })
            }
        );
        this.publish();

        try {
            const response: unknown = await this.renderer.renderAnchor(request);
            if (!this.isCurrentRender(pending)) {
                return;
            }
            if (
                !isAnchorRenderResponse(response) ||
                !anchorRenderResponseMatchesRequest(response, request)
            ) {
                this.failCurrentRender(
                    pending,
                    'The Selection Service Companion returned an invalid Anchor render binding.'
                );
                return;
            }
            try {
                await validatePngDecodable(
                    decodePngBase64(response.rgb.pngBase64)
                );
            } catch {
                this.failCurrentRender(
                    pending,
                    'The Selection Service Companion returned an invalid Anchor render binding.'
                );
                return;
            }
            if (!this.isCurrentRender(pending)) {
                return;
            }
            this.publishCurrentRender(pending, response);
        } catch (error) {
            this.failCurrentRender(pending, errorMessage(error));
        } finally {
            this.completeSnapshotRender(request);
        }
    }

    private publishCurrentRender(
        pending: PendingAnchorRender,
        response: AnchorRenderResponse
    ): void {
        const anchor = this.requireAnchor();
        const lastValidPreview: AnchorPreviewArtifact = {
            cameraBinding: response.cameraBinding,
            rgb: response.rgb
        };
        if (pending.kind === 'final') {
            this.anchor = createAnchor(
                anchor.cameraBinding,
                anchor.requestBinding,
                'ready',
                {
                    rgb: response.rgb,
                    rendererId: response.rendererId,
                    lastValidPreview
                }
            );
            this.publish();
            return;
        }
        this.anchor = createAnchor(
            anchor.cameraBinding,
            anchor.requestBinding,
            anchor.renderStatus,
            {
                ...formalDetails(anchor),
                preview: {
                    kind: pending.kind,
                    cameraBinding: response.cameraBinding,
                    requestBinding: response.requestBinding,
                    renderStatus: 'ready',
                    rgb: response.rgb
                },
                lastValidPreview
            }
        );
        this.publish();
    }

    private retainSnapshot(request: AnchorRenderRequest): void {
        const key = snapshotLeaseKey(request);
        this.retainedSnapshots.set(key, request);
        this.pendingSnapshotRenders.set(
            key,
            (this.pendingSnapshotRenders.get(key) ?? 0) + 1
        );
    }

    private completeSnapshotRender(request: AnchorRenderRequest): void {
        const key = snapshotLeaseKey(request);
        const pending = (this.pendingSnapshotRenders.get(key) ?? 1) - 1;
        if (pending > 0) {
            this.pendingSnapshotRenders.set(key, pending);
        } else {
            this.pendingSnapshotRenders.delete(key);
        }
        this.releaseIdleSnapshots();
    }

    private releaseIdleSnapshots(): void {
        const activeKey =
            this.activeRequest === null
                ? null
                : snapshotLeaseKey(this.activeRequest);
        for (const [key, request] of this.retainedSnapshots) {
            if (
                key === activeKey ||
                (this.pendingSnapshotRenders.get(key) ?? 0) > 0
            ) {
                continue;
            }
            this.retainedSnapshots.delete(key);
            if (this.renderer.releaseSceneSnapshot === undefined) {
                continue;
            }
            // Cleanup is a resource policy only. The disposed context cannot
            // publish again, and a failed DELETE is bounded by Companion-side
            // cleanup rather than becoming a new user-visible Anchor failure.
            this.renderer.releaseSceneSnapshot!(request).catch(
                (): void => undefined
            );
        }
    }

    private failCurrentRender(
        pending: PendingAnchorRender,
        message: string
    ): void {
        if (!this.isCurrentRender(pending)) {
            return;
        }
        const anchor = this.requireAnchor();
        const lastValid = latestValidPreview(anchor);
        this.anchor = createAnchor(
            anchor.cameraBinding,
            anchor.requestBinding,
            pending.kind === 'final' ? 'failed' : anchor.renderStatus,
            {
                ...(pending.kind === 'interactive'
                    ? formalDetails(anchor)
                    : {}),
                preview: {
                    kind: pending.kind,
                    cameraBinding: pending.request.cameraBinding,
                    requestBinding: pending.request.requestBinding,
                    renderStatus: 'failed',
                    errorMessage: message
                },
                ...(lastValid === undefined
                    ? {}
                    : { lastValidPreview: lastValid }),
                ...(pending.kind === 'final' ? { errorMessage: message } : {})
            }
        );
        this.publish();
    }

    private isCurrentRender(pending: PendingAnchorRender): boolean {
        const currentAnchor = this.anchor;
        const currentContext = this.contexts.current;
        const effectiveDependencyToken = this.getCurrentDependencyToken?.();
        if (
            currentAnchor === null ||
            currentContext === null ||
            effectiveDependencyToken === undefined
        ) {
            return false;
        }
        const acceptsResult = this.contexts.acceptsResult(
            pending.request.requestBinding,
            effectiveDependencyToken
        );
        const synchronizedContext = this.contexts.current;
        if (
            !acceptsResult &&
            synchronizedContext !== null &&
            synchronizedContext.lifecycle === 'suspended'
        ) {
            this.publish();
        }
        return (
            acceptsResult &&
            this.activeRender === pending &&
            synchronizedContext !== null &&
            synchronizedContext.targetContextId ===
                pending.context.targetContextId &&
            currentAnchor.requestBinding.targetContextId ===
                pending.request.requestBinding.targetContextId &&
            currentAnchor.requestBinding.contextRevision ===
                pending.request.requestBinding.contextRevision &&
            areTargetDependencyTokensEqual(
                currentAnchor.requestBinding.dependencyToken,
                pending.request.requestBinding.dependencyToken
            ) &&
            areCameraBindingsEqual(
                currentAnchor.cameraBinding,
                pending.anchorCameraBinding
            )
        );
    }

    private requireAnchor(): AnchorAIView {
        if (
            this.anchor === null ||
            this.contexts.current?.lifecycle !== 'active'
        ) {
            throw new Error(
                'AI Select requires an active Anchor CameraBinding.'
            );
        }
        return this.anchor;
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach((listener) => listener(state));
    }
}
