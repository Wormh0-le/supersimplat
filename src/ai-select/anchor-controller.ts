import type { PackedSceneSnapshot } from '../scene-snapshot-binary';
import {
    anchorRenderResponseMatchesRequest,
    decodePngBase64,
    isAnchorRenderResponse,
    validatePngDecodable,
    type AISelectAnchorRenderer,
    type AnchorRenderRequest,
    type AnchorRgbArtifact
} from './anchor-render-service';
import {
    areCameraBindingsEqual,
    copyCameraBinding,
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

export interface AnchorAIView {
    readonly viewId: 'anchor-view';
    readonly source: 'anchor';
    readonly cameraBinding: CameraBinding;
    readonly requestBinding: AIRequestBinding;
    readonly renderStatus: AnchorRenderStatus;
    readonly rgb?: AnchorRgbArtifact;
    readonly contributorDigest?: string;
    readonly rendererId?: 'gsplat';
    readonly errorMessage?: string;
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

const copyRequestBinding = (binding: AIRequestBinding): AIRequestBinding => {
    return Object.freeze({
        targetContextId: binding.targetContextId,
        contextRevision: binding.contextRevision,
        dependencyToken: Object.freeze({
            splatId: binding.dependencyToken.splatId,
            renderStateToken: binding.dependencyToken.renderStateToken,
            geometryToken: binding.dependencyToken.geometryToken,
            gaussianIdentityToken: binding.dependencyToken.gaussianIdentityToken,
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

const copyAnchor = (anchor: AnchorAIView): AnchorAIView => {
    return Object.freeze({
        viewId: anchor.viewId,
        source: anchor.source,
        cameraBinding: copyCameraBinding(anchor.cameraBinding),
        requestBinding: copyRequestBinding(anchor.requestBinding),
        renderStatus: anchor.renderStatus,
        ...(anchor.rgb === undefined ? {} : { rgb: copyRgb(anchor.rgb) }),
        ...(anchor.contributorDigest === undefined ? {} : {
            contributorDigest: anchor.contributorDigest
        }),
        ...(anchor.rendererId === undefined ? {} : { rendererId: anchor.rendererId }),
        ...(anchor.errorMessage === undefined ? {} : { errorMessage: anchor.errorMessage })
    });
};

const copyState = (state: AISelectAnchorState): AISelectAnchorState => {
    return Object.freeze({
        context: state.context,
        anchor: state.anchor === null ? null : copyAnchor(state.anchor)
    });
};

const errorMessage = (error: unknown): string => {
    return error instanceof Error && error.message ? error.message : 'Anchor rendering failed.';
};

/**
 * The first Final Spec product controller. It owns only the one Anchor shell
 * and delegates context lifetime/stale-result correctness to the v1 kernel;
 * later AI View, Mask, and Candidate stores remain deliberately absent.
 */
export class AISelectAnchorController {
    private readonly renderer: AISelectAnchorRenderer;
    private readonly contexts = new CurrentTargetContextKernel();
    private readonly listeners = new Set<AISelectAnchorListener>();
    private anchor: AnchorAIView | null = null;
    private getCurrentDependencyToken: (() => TargetDependencyToken) | null = null;

    constructor(options: { renderer: AISelectAnchorRenderer }) {
        this.renderer = options.renderer;
    }

    get state(): AISelectAnchorState {
        return copyState({
            context: this.contexts.current,
            anchor: this.anchor
        });
    }

    subscribe(listener: AISelectAnchorListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    async start(input: StartAnchorInput): Promise<void> {
        if (this.contexts.current !== null) {
            throw new Error('AI Select already has a Current Target Context. Restart it instead.');
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
        this.publish();
    }

    private async begin(input: StartAnchorInput, restart: boolean): Promise<void> {
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
        const context = restart ?
            this.contexts.restart({
                target: input.target,
                dependencyToken: input.dependencyToken
            }) :
            this.contexts.start({
                target: input.target,
                dependencyToken: input.dependencyToken
            });
        this.getCurrentDependencyToken = input.getCurrentDependencyToken;
        const requestBinding = this.contexts.createRequestBinding();
        const request: AnchorRenderRequest = Object.freeze({
            requestBinding,
            target: Object.freeze({ splatId: input.target.splatId }),
            snapshot: input.snapshot,
            cameraBinding: copyCameraBinding(input.cameraBinding)
        });

        this.anchor = copyAnchor({
            viewId: 'anchor-view',
            source: 'anchor',
            cameraBinding: request.cameraBinding,
            requestBinding,
            renderStatus: 'rendering'
        });
        this.publish();

        try {
            const response: unknown = await this.renderer.renderAnchor(request);
            if (!this.isCurrentRequest(request, context)) {
                return;
            }
            if (
                !isAnchorRenderResponse(response) ||
                !anchorRenderResponseMatchesRequest(response, request)
            ) {
                this.failCurrentAnchor(
                    request,
                    context,
                    'The Selection Service Companion returned an invalid Anchor render binding.'
                );
                return;
            }
            try {
                await validatePngDecodable(decodePngBase64(response.rgb.pngBase64));
            } catch {
                this.failCurrentAnchor(
                    request,
                    context,
                    'The Selection Service Companion returned an invalid Anchor render binding.'
                );
                return;
            }
            if (!this.isCurrentRequest(request, context)) {
                return;
            }
            this.anchor = copyAnchor({
                viewId: 'anchor-view',
                source: 'anchor',
                cameraBinding: request.cameraBinding,
                requestBinding: request.requestBinding,
                renderStatus: 'ready',
                rgb: response.rgb,
                contributorDigest: response.contributorDigest,
                rendererId: response.rendererId
            });
            this.publish();
        } catch (error) {
            this.failCurrentAnchor(request, context, errorMessage(error));
        }
    }

    private failCurrentAnchor(
        request: AnchorRenderRequest,
        context: CurrentTargetContext,
        message: string
    ): void {
        if (!this.isCurrentRequest(request, context)) {
            return;
        }
        this.anchor = copyAnchor({
            viewId: 'anchor-view',
            source: 'anchor',
            cameraBinding: request.cameraBinding,
            requestBinding: request.requestBinding,
            renderStatus: 'failed',
            errorMessage: message
        });
        this.publish();
    }

    private isCurrentRequest(
        request: AnchorRenderRequest,
        context: CurrentTargetContext
    ): boolean {
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
            request.requestBinding,
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
            synchronizedContext !== null &&
            synchronizedContext.targetContextId === context.targetContextId &&
            currentAnchor.requestBinding.targetContextId === request.requestBinding.targetContextId &&
            currentAnchor.requestBinding.contextRevision === request.requestBinding.contextRevision &&
            areTargetDependencyTokensEqual(
                currentAnchor.requestBinding.dependencyToken,
                request.requestBinding.dependencyToken
            ) &&
            areCameraBindingsEqual(currentAnchor.cameraBinding, request.cameraBinding)
        );
    }

    private publish(): void {
        const state = this.state;
        this.listeners.forEach(listener => listener(state));
    }
}
