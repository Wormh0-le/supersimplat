import { WebPCodec, WorkerQueue } from '@playcanvas/splat-transform';
import { Color, Mat4, Quat, Vec3, createGraphicsDevice } from 'playcanvas';

import { AISelectAnchorAdjustmentController } from './ai-select/anchor-adjustment';
import { AISelectAnchorConfirmationController } from './ai-select/anchor-confirmation';
import { AISelectAnchorController } from './ai-select/anchor-controller';
import { AISelectAnchorCutoverCoordinator } from './ai-select/anchor-cutover';
import {
    captureEditorCameraBinding,
    playCanvasWorldTransformFromCameraBinding
} from './ai-select/camera-binding';
import {
    CameraInspectionController,
    isAnchorAdjustmentInspectionTarget,
    isAnchorInspectionTarget
} from './ai-select/camera-inspection';
import { AnchorFrustumManipulator } from './ai-select/camera-inspection-manipulator';
import { CandidateApplicationController } from './ai-select/candidate-application';
import { createAISelectCandidateCorrectionController } from './ai-select/candidate-correction-composition';
import { CandidateOverlayController } from './ai-select/candidate-overlay';
import { CandidatePresentationCoordinator } from './ai-select/candidate-presentation';
import { CandidatePublicationStore } from './ai-select/candidate-publication';
import { pickGeneratedViewFrustum } from './ai-select/generated-frustum-picking';
import { AISelectGeneratedViewController } from './ai-select/generated-view-controller';
import { LiftReadinessStore } from './ai-select/lift-readiness';
import { AISelectMaskController } from './ai-select/mask-controller';
import { createPromptAdapterCapabilities } from './ai-select/prompt-state';
import { isCurrentTargetDependencyChange } from './ai-select/target-dependency-routing';
import { AISelectTargetLifecycleController } from './ai-select/target-lifecycle';
import { AISelectUserViewMaskController } from './ai-select/user-view-mask-controller';
import { AnchorFrustum } from './ai-select-anchor-frustum';
import { SelectOpCandidateNativeSelection } from './ai-select-candidate-application';
import { CandidateViewportOverlay } from './ai-select-candidate-viewport-overlay';
import { AISelectEditorTargetFactory } from './ai-select-editor-target';
import { GeneratedViewFrustums } from './ai-select-generated-frustums';
import { registerCameraPosesEvents } from './camera-poses';
import { CommandQueue } from './command-queue';
import { registerDocEvents } from './doc';
import { EditHistory } from './edit-history';
import { registerEditorEvents } from './editor';
import { ElementType, type Element } from './element';
import { Events } from './events';
import { initFileHandler } from './file-handler';
import { registerIframeApi } from './iframe-api';
import { registerPreferences } from './preferences';
import { registerPublishEvents } from './publish';
import { registerRenderEvents } from './render';
import { Scene } from './scene';
import { getSceneConfig } from './scene-config';
import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';
import { registerSelectionEvents } from './selection';
import { FetchSelectionServiceAdapter } from './selection-service-fetch-adapter';
import { FetchSelectionServiceReadinessProbe } from './selection-service-fetch-readiness-probe';
import {
    ReadinessGatedSelectionServiceAdapter,
    SelectionServiceReadiness
} from './selection-service-readiness';
import { registerSelectionServiceReadinessEvents } from './selection-service-readiness-events';
import { registerSequenceEvents } from './sequence';
import { ShortcutManager } from './shortcut-manager';
import type { Splat } from './splat';
import { registerTimelineEvents } from './timeline';
import { BoxSelection } from './tools/box-selection';
import { BrushSelection } from './tools/brush-selection';
import { EyedropperSelection } from './tools/eyedropper-selection';
import { FloodSelection } from './tools/flood-selection';
import { LassoSelection } from './tools/lasso-selection';
import { MeasureTool } from './tools/measure-tool';
import { MoveTool } from './tools/move-tool';
import { PolygonSelection } from './tools/polygon-selection';
import { RectSelection } from './tools/rect-selection';
import { RotateTool } from './tools/rotate-tool';
import { ScaleTool } from './tools/scale-tool';
import { SphereSelection } from './tools/sphere-selection';
import { ToolManager } from './tools/tool-manager';
import { registerTrackManagerEvents } from './track-manager';
import { registerTransformHandlerEvents } from './transform-handler';
import { AISelectAnchorDock } from './ui/ai-select-anchor-dock';
import { AISelectToolbar } from './ui/ai-select-toolbar';
import { BoundDimensionsOverlay } from './ui/bound-dimensions-overlay';
import { EditorUI } from './ui/editor';
import { i18n } from './ui/localization';
import { registerSelectCursor } from './ui/select-cursor';

declare global {
    interface LaunchParams {
        readonly files: FileSystemFileHandle[];
    }

    interface Window {
        launchQueue: {
            setConsumer: (
                callback: (launchParams: LaunchParams) => void
            ) => void;
        };
        scene: Scene;
    }
}

const getURLArgs = () => {
    // extract settings from command line in non-prod builds only
    const config = {};

    const apply = (key: string, value: string) => {
        let obj: any = config;
        key.split('.').forEach((k, i, a) => {
            if (i === a.length - 1) {
                obj[k] = value;
            } else {
                if (!obj.hasOwnProperty(k)) {
                    obj[k] = {};
                }
                obj = obj[k];
            }
        });
    };

    const params = new URLSearchParams(window.location.search.slice(1));
    params.forEach((value: string, key: string) => {
        apply(key, value);
    });

    return config;
};

const main = async () => {
    // root events object
    const events = new Events();

    // url
    const url = new URL(window.location.href);

    // shared command queue for all async splat work (GPU readbacks + history mutations).
    // every consumer that needs ordering relative to other commands enqueues here.
    const commandQueue = new CommandQueue();

    // edit history (uses the shared queue internally)
    const editHistory = new EditHistory(events, commandQueue);

    // expose the queue as an event for any module that needs to serialise async work
    // alongside history mutations.
    events.function('queue', (fn: () => Promise<void> | void) =>
        commandQueue.enqueue(fn)
    );

    // init localization
    await i18n.init();

    // Configure WebP WASM for SOG format (used for both reading and writing)
    WebPCodec.wasmUrl = new URL(
        'static/lib/webp/webp.wasm',
        document.baseURI
    ).toString();

    // Run SOG writing inline rather than in worker threads. We don't ship
    // splat-transform's worker.mjs, so leaving the pool enabled makes it try to
    // spawn a worker that 404s; under SOG's parallel task load it then hangs
    // instead of falling back, producing an empty export.
    WorkerQueue.maxWorkers = 0;

    // register events that only need the events object (before UI is created)
    registerTimelineEvents(events);
    registerCameraPosesEvents(events);
    registerTrackManagerEvents(events);
    registerTransformHandlerEvents(events);
    registerPublishEvents(events);
    registerIframeApi(events);

    // The editor reads the operator-configured Companion state but never owns
    // its installation, model downloads, start, stop, or upgrade lifecycle.
    const selectionServiceReadiness = new SelectionServiceReadiness({
        probe: new FetchSelectionServiceReadinessProbe(),
        onCompanionInstanceChanged: (previousInstanceId, currentInstanceId) => {
            events.fire(
                'selectionService.companionInstanceChanged',
                previousInstanceId,
                currentInstanceId
            );
        }
    });
    // The concrete scene/session transport is attached only through the
    // readiness gate, so no ObjectSelectionSession can bypass the
    // operator-visible Companion compatibility decision.
    const selectionServiceAdapter = new ReadinessGatedSelectionServiceAdapter({
        readiness: selectionServiceReadiness
    });
    selectionServiceAdapter.setAdapter(
        new FetchSelectionServiceAdapter({
            getConfiguration: () =>
                selectionServiceReadiness.state.configuration,
            // Spatial working sets are additive to the 02A full packed
            // registration path. A compatible older Companion remains usable
            // through that reference/fallback path.
            supportsCameraAwareSpatialWorkingSet: () =>
                selectionServiceReadiness.state.capabilities?.supportedOperations.includes(
                    'cameraAwareSpatialWorkingSetV1'
                ) ?? false
        })
    );
    registerSelectionServiceReadinessEvents(events, selectionServiceReadiness);
    events.function('selectionService.adapter', () => selectionServiceAdapter);

    // initialize shortcuts
    const shortcutManager = new ShortcutManager(events);
    events.function('shortcutManager', () => shortcutManager);

    // editor ui
    const editorUI = new EditorUI(events, selectionServiceReadiness);
    // UI construction mounts the ordinary three-state Availability surface.
    // The first compatibility check starts only after that mount and never
    // blocks native editor startup.
    selectionServiceReadiness.start();

    // create the graphics device
    const graphicsDevice = await createGraphicsDevice(editorUI.canvas, {
        deviceTypes: ['webgl2'],
        antialias: false,
        depth: false,
        stencil: false,
        xrCompatible: false,
        powerPreference: 'high-performance'
    });

    const urlArgs = getURLArgs();

    const overrides = [urlArgs];

    // resolve scene config
    const sceneConfig = getSceneConfig(overrides);

    // construct the manager
    const scene = new Scene(
        events,
        sceneConfig,
        editorUI.canvas,
        graphicsDevice,
        commandQueue
    );

    // colors
    const bgClr = new Color();
    const selectedClr = new Color();
    const unselectedClr = new Color();
    const lockedClr = new Color();

    const setClr = (target: Color, value: Color, event: string) => {
        if (!target.equals(value)) {
            target.copy(value);
            events.fire(event, target);
        }
    };

    const setBgClr = (clr: Color) => {
        setClr(bgClr, clr, 'bgClr');
    };
    const setSelectedClr = (clr: Color) => {
        setClr(selectedClr, clr, 'selectedClr');
    };
    const setUnselectedClr = (clr: Color) => {
        setClr(unselectedClr, clr, 'unselectedClr');
    };
    const setLockedClr = (clr: Color) => {
        setClr(lockedClr, clr, 'lockedClr');
    };

    events.on('setBgClr', (clr: Color) => {
        setBgClr(clr);
    });
    events.on('setSelectedClr', (clr: Color) => {
        setSelectedClr(clr);
    });
    events.on('setUnselectedClr', (clr: Color) => {
        setUnselectedClr(clr);
    });
    events.on('setLockedClr', (clr: Color) => {
        setLockedClr(clr);
    });

    events.function('bgClr', () => {
        return bgClr;
    });
    events.function('selectedClr', () => {
        return selectedClr;
    });
    events.function('unselectedClr', () => {
        return unselectedClr;
    });
    events.function('lockedClr', () => {
        return lockedClr;
    });

    events.on('bgClr', (clr: Color) => {
        const cnv = (v: number) =>
            `${Math.max(0, Math.min(255, v * 255)).toFixed(0)}`;
        document.body.style.backgroundColor = `rgba(${cnv(clr.r)},${cnv(clr.g)},${cnv(clr.b)},1)`;
    });
    events.on('selectedClr', (clr: Color) => {
        scene.forceRender = true;
    });
    events.on('unselectedClr', (clr: Color) => {
        scene.forceRender = true;
    });
    events.on('lockedClr', (clr: Color) => {
        scene.forceRender = true;
    });

    // initialize colors from application config
    const toColor = (value: { r: number; g: number; b: number; a: number }) => {
        return new Color(value.r, value.g, value.b, value.a);
    };
    setBgClr(toColor(sceneConfig.bgClr));
    setSelectedClr(toColor(sceneConfig.selectedClr));
    setUnselectedClr(toColor(sceneConfig.unselectedClr));
    setLockedClr(toColor(sceneConfig.lockedClr));

    // create the mask selection canvas
    const maskCanvas = document.createElement('canvas');
    const maskContext = maskCanvas.getContext('2d');
    maskCanvas.setAttribute('id', 'mask-canvas');
    maskContext.globalCompositeOperation = 'copy';

    const mask = {
        canvas: maskCanvas,
        context: maskContext
    };

    // tool manager
    const toolManager = new ToolManager(events);
    toolManager.register(
        'rectSelection',
        new RectSelection(events, editorUI.toolsContainer.dom)
    );
    toolManager.register(
        'brushSelection',
        new BrushSelection(events, editorUI.toolsContainer.dom, mask)
    );
    toolManager.register(
        'floodSelection',
        new FloodSelection(
            events,
            editorUI.toolsContainer.dom,
            mask,
            editorUI.canvasContainer
        )
    );
    toolManager.register(
        'polygonSelection',
        new PolygonSelection(events, editorUI.toolsContainer.dom, mask)
    );
    toolManager.register(
        'lassoSelection',
        new LassoSelection(events, editorUI.toolsContainer.dom, mask)
    );
    toolManager.register(
        'sphereSelection',
        new SphereSelection(events, scene, editorUI.canvasContainer)
    );
    toolManager.register(
        'boxSelection',
        new BoxSelection(events, scene, editorUI.canvasContainer)
    );
    toolManager.register(
        'eyedropperSelection',
        new EyedropperSelection(
            events,
            editorUI.toolsContainer.dom,
            editorUI.canvasContainer
        )
    );
    toolManager.register('move', new MoveTool(events, scene));
    toolManager.register('rotate', new RotateTool(events, scene));
    toolManager.register('scale', new ScaleTool(events, scene));
    toolManager.register(
        'measure',
        new MeasureTool(
            events,
            scene,
            editorUI.toolsContainer.dom,
            editorUI.canvasContainer
        )
    );

    const boundDimensionsOverlay = new BoundDimensionsOverlay(
        events,
        scene,
        editorUI.canvasContainer
    );

    editorUI.toolsContainer.dom.appendChild(maskCanvas);

    // show the active selection op (add/remove/intersect) at the cursor
    registerSelectCursor(events, editorUI.toolsContainer.dom);

    window.scene = scene;

    // register events that need scene or other dependencies
    registerEditorEvents(events, editHistory, scene);
    registerSelectionEvents(events, scene);
    registerSequenceEvents(events, scene);
    registerDocEvents(scene, events);
    registerRenderEvents(scene, events);
    initFileHandler(scene, events, editorUI.appContainer.dom);

    // AI Select v1 is a native tool. Its Anchor begins with the visible editor
    // camera, but the RGB image itself is requested only from the Companion's
    // locked gsplat renderer; no PlayCanvas framebuffer is observed here.
    const getAISelectRenderConfiguration =
        (): SceneSnapshotRenderConfiguration => {
            const background = events.invoke('bgClr') as Color;
            return {
                version: 'supersplat-effective-rgb-v1',
                backgroundRgba: [
                    background.r,
                    background.g,
                    background.b,
                    background.a
                ],
                alphaMode: 'opaque-background',
                shBands: events.invoke('view.bands') as number,
                rasterizer: 'playcanvas-gsplat-classic'
            };
        };
    const aiSelectTargetFactory = new AISelectEditorTargetFactory({
        getRenderConfiguration: getAISelectRenderConfiguration,
        // Hidden Splats must remain observable to the dependency token so a
        // hide/show transition cannot remove the changed Splat before the
        // synchronizer sees it. The render-scope builder filters visibility.
        getVisibleSplats: () => events.invoke('scene.allSplats') as Splat[]
    });
    // The confirmed current Anchor stays locked while adjustment is staged in
    // an isolated draft; the confirmation controller is composed just below,
    // so the live-Anchor lock reads through a lazy reference.
    let aiSelectConfirmation: AISelectAnchorConfirmationController | null =
        null;
    let aiSelectAnchorAdjustment: AISelectAnchorAdjustmentController | null =
        null;
    let aiSelectCandidateCorrection: ReturnType<
        typeof createAISelectCandidateCorrectionController
    > | null = null;
    let aiSelectTargetSplat: Splat | null = null;
    // Declared ahead of the readiness/Instance event registrations; assigned
    // once the Generated View controller exists below.
    let aiSelectUserViewMasks: AISelectUserViewMaskController | null = null;
    const isAISelectAnchorLocked = () => aiSelectConfirmation?.locked ?? false;
    const isAISelectAnchorMaskLocked = () =>
        (aiSelectConfirmation?.locked ?? false) &&
        aiSelectCandidateCorrection?.state.mode !== 'correcting';
    const getAISelectModelManifestDigest = () =>
        selectionServiceReadiness.state.configuration.modelManifestDigest;
    const getAISelectPromptAdapterCapabilities = () => {
        // Rebuild the exact Prompt Adapter capability record from the
        // ready provider's advertised flags and compiler policy, and
        // trust it only when the recomputed digest matches the
        // advertised adapter capability digest (04C contract §3).
        const readiness = selectionServiceReadiness.state;
        const provider = readiness.capabilities?.imageInstanceProvider;
        if (
            readiness.status !== 'available' ||
            provider === undefined ||
            provider.status !== 'ready' ||
            provider.compilerPolicyVersion === undefined ||
            provider.adapterCapabilityDigest === undefined
        ) {
            return null;
        }
        const capabilities = createPromptAdapterCapabilities({
            ...provider.promptCapabilities,
            compilerPolicyVersion: provider.compilerPolicyVersion
        });
        return capabilities.capabilityDigest ===
            provider.adapterCapabilityDigest
            ? capabilities
            : null;
    };
    const aiSelectController = new AISelectAnchorController({
        renderer: selectionServiceAdapter,
        isAnchorLocked: isAISelectAnchorMaskLocked
    });
    const synchronizeAISelectTargetDependency = (
        changedSplat?: Splat
    ): void => {
        if (
            !isCurrentTargetDependencyChange(
                aiSelectTargetSplat,
                changedSplat,
                events.invoke('scene.allSplats') as Splat[]
            )
        ) {
            return;
        }
        aiSelectController.synchronizeTargetDependency();
    };
    events.on(
        'splat.aiSelectDependencyChanged',
        synchronizeAISelectTargetDependency
    );
    const synchronizeAISelectSceneMembership = (element: Element): void => {
        if (element.type === ElementType.splat) {
            synchronizeAISelectTargetDependency();
        }
    };
    events.on('scene.elementAdded', synchronizeAISelectSceneMembership);
    events.on('scene.elementRemoved', synchronizeAISelectSceneMembership);
    // Background and SH-band changes affect authoritative AI RGB even though
    // they do not belong to one Splat. Editor-only colors and UI state do not.
    events.on('bgClr', () => synchronizeAISelectTargetDependency());
    events.on('view.bands', () => synchronizeAISelectTargetDependency());
    const aiSelectMaskController = new AISelectMaskController({
        anchor: aiSelectController,
        maskProvider: selectionServiceAdapter,
        getModelManifestDigest: getAISelectModelManifestDigest,
        getPromptAdapterCapabilities: getAISelectPromptAdapterCapabilities,
        isAnchorLocked: isAISelectAnchorLocked
    });
    const aiSelectCandidatePublications = new CandidatePublicationStore(
        aiSelectMaskController.dirtyState
    );
    const aiSelectLiftReadiness = new LiftReadinessStore(
        aiSelectMaskController.dirtyState
    );
    let aiSelectCandidateContextId: string | null = null;
    aiSelectController.subscribe((state) => {
        const contextId = state.context?.targetContextId ?? null;
        if (contextId !== aiSelectCandidateContextId) {
            aiSelectCandidatePublications.reset();
            aiSelectLiftReadiness.reset();
            aiSelectCandidateContextId = contextId;
        }
    });
    // Companion Instance replacement invalidates the prior Instance's
    // Companion-local RGB/logits references (02C); editor-owned Prompt and
    // Mask artifacts keep their own identity and are not touched.
    events.on('selectionService.companionInstanceChanged', () => {
        aiSelectMaskController.handleCompanionInstanceChanged();
        aiSelectAnchorAdjustment?.handleCompanionInstanceChanged();
        aiSelectUserViewMasks?.handleCompanionInstanceChanged();
    });
    // Prompt Adapter capabilities derive from live readiness; a readiness
    // transition must republish or Prompt tools keep a stale gating snapshot.
    events.on('selectionService.readinessChanged', () => {
        aiSelectMaskController.refreshAvailability();
        aiSelectAnchorAdjustment?.refreshAvailability();
        aiSelectUserViewMasks?.refreshAvailability();
    });
    aiSelectConfirmation = new AISelectAnchorConfirmationController({
        anchor: aiSelectController,
        mask: aiSelectMaskController,
        supportProbe: selectionServiceAdapter
    });
    const aiSelectAnchorCutover = new AISelectAnchorCutoverCoordinator({
        anchor: aiSelectController,
        mask: aiSelectMaskController,
        confirmation: aiSelectConfirmation,
        releaseDependentProducts: () => {
            aiSelectCandidateCorrection?.reset();
            aiSelectCandidatePublications.reset();
            aiSelectLiftReadiness.reset();
        }
    });
    aiSelectAnchorAdjustment = new AISelectAnchorAdjustmentController({
        anchor: aiSelectController,
        confirmation: aiSelectConfirmation,
        maskProvider: selectionServiceAdapter,
        supportProbe: selectionServiceAdapter,
        commitDraft: (input) => aiSelectAnchorCutover.commit(input),
        getModelManifestDigest: getAISelectModelManifestDigest,
        getPromptAdapterCapabilities: getAISelectPromptAdapterCapabilities
    });
    // Confirm Anchor starts automatic Key View planning: the Companion owns
    // the Target Geometry Hint and the bounded local Key-View batches, the
    // editor publishes each View progressively as authoritative RGB arrives,
    // and automatic Mask production follows independently per View. Older
    // Companions without the additive capabilities fail planning closed with
    // an actionable diagnostic.
    const aiSelectGeneratedViews = new AISelectGeneratedViewController({
        anchor: aiSelectController,
        confirmation: aiSelectConfirmation,
        maskRegistry: aiSelectMaskController.maskRegistry,
        evidenceRegistry: aiSelectMaskController.evidenceRegistry,
        dirtyState: aiSelectMaskController.dirtyState,
        geometryHints: selectionServiceAdapter,
        planner: selectionServiceAdapter,
        renderer: selectionServiceAdapter,
        promptSynthesizer: selectionServiceAdapter,
        maskProvider: selectionServiceAdapter,
        reviewProvider: selectionServiceAdapter,
        getImageInstanceRuntimeBinding: () => {
            const readiness = selectionServiceReadiness.state;
            const capabilities = readiness.capabilities;
            const provider = capabilities?.imageInstanceProvider;
            const manifest = capabilities?.activeModelManifest;
            if (
                readiness.status !== 'available' ||
                capabilities === undefined ||
                provider === undefined ||
                manifest === undefined ||
                provider.status !== 'ready' ||
                provider.adapterCapabilityDigest === undefined ||
                provider.adapterId !== manifest.adapterId
            ) {
                return null;
            }
            return {
                adapterId: provider.adapterId,
                modelManifestDigest: manifest.digest,
                runtimeDigest: manifest.runtimeConfigDigest,
                companionInstanceId: capabilities.companionInstanceId,
                adapterCapabilityDigest: provider.adapterCapabilityDigest
            };
        },
        supportsGeneratedViews: () => {
            const operations =
                selectionServiceReadiness.state.capabilities
                    ?.supportedOperations;
            return (
                operations !== undefined &&
                operations.includes('aiSelectTargetGeometryHint') &&
                operations.includes('aiSelectLocalKeyViewPlanning') &&
                operations.includes('aiSelectGeneratedViewPromptSynthesis') &&
                operations.includes('aiSelectImageInstanceMasks') &&
                operations.includes('aiSelectImageInstanceMaskReview')
            );
        }
    });
    // User-added AIVews (Ticket 11): their 04C Mask authoring sessions share
    // the Anchor's Mask/Evidence registries and provider bindings; only the
    // RGB/binding seams route through the Generated View run identity.
    aiSelectUserViewMasks = new AISelectUserViewMaskController({
        generatedViews: aiSelectGeneratedViews,
        maskProvider: selectionServiceAdapter,
        maskRegistry: aiSelectMaskController.maskRegistry,
        evidenceRegistry: aiSelectMaskController.evidenceRegistry,
        getModelManifestDigest: getAISelectModelManifestDigest,
        getPromptAdapterCapabilities: getAISelectPromptAdapterCapabilities
    });
    aiSelectCandidateCorrection = createAISelectCandidateCorrectionController({
        anchor: aiSelectController,
        masks: aiSelectMaskController,
        generatedViews: aiSelectGeneratedViews,
        candidatePublications: aiSelectCandidatePublications,
        liftReadiness: aiSelectLiftReadiness,
        getProductionIdentityDigest: () => {
            const identity =
                selectionServiceReadiness.state.capabilities
                    ?.productionIdentity;
            return identity?.status === 'ready'
                ? identity.record.identityDigest
                : null;
        },
        provider: selectionServiceAdapter
    });
    aiSelectController.subscribe((state) => {
        if (state.context?.lifecycle === 'suspended') {
            aiSelectCandidateCorrection.discardPendingUpdate();
        }
    });
    const referenceCandidateApplicationEnabled =
        (
            urlArgs as {
                aiSelect?: { referenceCandidateApplication?: string };
            }
        ).aiSelect?.referenceCandidateApplication === 'development';
    const aiSelectCandidateApplication = new CandidateApplicationController({
        candidates: aiSelectCandidatePublications,
        nativeSelection: new SelectOpCandidateNativeSelection({
            editHistory,
            getTarget: () =>
                aiSelectTargetSplat === null
                    ? null
                    : {
                          targetSplat: aiSelectTargetSplat,
                          stableIds:
                              aiSelectTargetFactory.bindingForTarget(
                                  aiSelectTargetSplat
                              )
                      }
        }),
        beginCorrection: () => aiSelectCandidateCorrection.beginCorrection(),
        applicationMode: referenceCandidateApplicationEnabled
            ? 'development-reference'
            : 'production',
        getAcceptedRuntime: () => {
            const readiness = selectionServiceReadiness.state;
            const capability = referenceCandidateApplicationEnabled
                ? readiness.capabilities?.referenceCandidateReLift
                : readiness.capabilities?.productionCandidateReLift;
            if (
                readiness.status !== 'available' ||
                capability === undefined ||
                ('status' in capability && capability.status !== 'ready')
            ) {
                return null;
            }
            return {
                rasterImplementationId: capability.rasterImplementationId,
                evidenceBackendKind: capability.evidenceBackendKind,
                evidenceBackendId: capability.evidenceBackendId,
                runtimeBuildId: capability.runtimeBuildId,
                sourceEvidencePolicyDigest: capability.evidencePolicyDigest,
                aggregationPolicyDigest: capability.aggregationPolicyDigest,
                productionIdentityDigest: referenceCandidateApplicationEnabled
                    ? null
                    : readiness.capabilities?.productionIdentity.status ===
                        'ready'
                      ? readiness.capabilities.productionIdentity.record
                            .identityDigest
                      : null
            };
        },
        getTarget: () =>
            aiSelectTargetSplat === null
                ? null
                : {
                      context: aiSelectController.state.context,
                      effectiveDependencyToken:
                          aiSelectTargetFactory.currentDependencyTokenFor(
                              aiSelectTargetSplat
                          )
                  }
    });
    aiSelectController.subscribe(() => aiSelectCandidateApplication.refresh());
    events.on('selectionService.readinessChanged', () =>
        aiSelectCandidateApplication.refresh()
    );
    events.on('edit.apply', () => aiSelectCandidateApplication.refresh());
    const aiSelectCandidatePresentation = new CandidatePresentationCoordinator({
        candidates: aiSelectCandidatePublications,
        correction: aiSelectCandidateCorrection,
        application: aiSelectCandidateApplication
    });
    const aiSelectCandidateOverlay = new CandidateOverlayController({
        presentation: aiSelectCandidatePresentation,
        getCandidateRevision: () =>
            aiSelectCandidatePublications.inspectableCandidate
                ?.candidateDigest ?? null
    });
    const aiSelectCandidateViewportOverlay = new CandidateViewportOverlay(
        aiSelectCandidateOverlay,
        {
            getTarget: () =>
                aiSelectTargetSplat === null
                    ? null
                    : {
                          splat: aiSelectTargetSplat,
                          stableIds:
                              aiSelectTargetFactory.bindingForTarget(
                                  aiSelectTargetSplat
                              )
                      },
            onFailure: (error) => {
                console.error(error);
                aiSelectCandidatePresentation.setOverlayAvailable(false);
            },
            onRecovered: () =>
                aiSelectCandidatePresentation.setOverlayAvailable(true)
        }
    );
    let aiSelectOverlayContextId: string | null = null;
    aiSelectController.subscribe((state) => {
        const contextId = state.context?.targetContextId ?? null;
        if (contextId !== aiSelectOverlayContextId) {
            aiSelectCandidateOverlay.reset();
            aiSelectOverlayContextId = contextId;
        }
    });
    editorUI.statusBar.bindCandidatePresentation(aiSelectCandidatePresentation);
    const cameraInspection = new CameraInspectionController({
        anchor: aiSelectController,
        anchorAdjustment: aiSelectAnchorAdjustment,
        editor: {
            captureSceneView: () => {
                const snapshot = scene.camera.captureSceneView();
                return {
                    sceneView: snapshot.sceneView,
                    restore: () => {
                        scene.camera.restoreSceneView(snapshot);
                        scene.forceRender = true;
                    }
                };
            },
            setSceneView: (view) => {
                scene.camera.setSceneView(view);
                scene.forceRender = true;
            },
            setCameraBindingView: (binding) => {
                const transform = new Mat4();
                transform.data.set(
                    playCanvasWorldTransformFromCameraBinding(binding)
                );
                const projection = binding.projection;
                const horizontal = scene.camera.camera.horizontalFov;
                const sensorSize = horizontal
                    ? projection.width
                    : projection.height;
                const focalLength = horizontal ? projection.fx : projection.fy;
                const fov =
                    (2 * Math.atan(sensorSize / (2 * focalLength)) * 180) /
                    Math.PI;
                scene.camera.ortho = false;
                scene.camera.setPoseOverride(
                    {
                        position: transform.getTranslation(),
                        rotation: new Quat().setFromMat4(transform),
                        fov,
                        near: projection.near,
                        far: projection.far
                    },
                    transform
                );
                scene.forceRender = true;
            }
        }
    });
    aiSelectAnchorAdjustment.subscribe((state) => {
        if (
            state.status === 'current' &&
            isAnchorAdjustmentInspectionTarget(cameraInspection.state)
        ) {
            cameraInspection.returnToSceneView();
        }
    });
    const anchorFrustum = new AnchorFrustum();
    await scene.add(anchorFrustum);
    const updateAnchorFrustum = () => {
        const anchor = aiSelectController.state.anchor;
        // The Anchor frustum appears only while the Anchor itself is
        // inspected; Generated View inspection highlights that View's own
        // frustum through the Gallery selection instead. The provisional
        // Adjust New View draft reuses this manipulable frustum display.
        const draftTarget = cameraInspection.state.target;
        if (
            draftTarget?.kind === 'user-view-draft' ||
            draftTarget?.kind === 'anchor-adjustment-draft'
        ) {
            anchorFrustum.setCameraBinding(draftTarget.cameraBinding);
            anchorFrustum.setVisible(true);
            return;
        }
        const inspectingAnchor = isAnchorInspectionTarget(
            cameraInspection.state
        );
        anchorFrustum.setCameraBinding(
            inspectingAnchor ? (anchor?.cameraBinding ?? null) : null
        );
        anchorFrustum.setVisible(inspectingAnchor && anchor !== null);
    };
    aiSelectController.subscribe(updateAnchorFrustum);
    cameraInspection.subscribe(updateAnchorFrustum);
    const anchorFrustumManipulator = new AnchorFrustumManipulator({
        scene,
        controller: aiSelectController,
        inspection: cameraInspection
    });

    // Generated Frustums derive from the exact planner-owned CameraBindings,
    // stay read-only, and highlight the Gallery selection in 3D.
    const generatedFrustums = new GeneratedViewFrustums();
    await scene.add(generatedFrustums);
    const updateGeneratedFrustums = () => {
        const generated = aiSelectGeneratedViews.state;
        generatedFrustums.setViews(
            generated.views.map((view) => ({
                viewId: view.viewId,
                cameraBinding: view.cameraBinding,
                selected: generated.selectedViewId === view.viewId
            }))
        );
        generatedFrustums.setVisible(
            aiSelectController.state.context !== null &&
                generated.views.length > 0
        );
    };
    aiSelectGeneratedViews.subscribe(updateGeneratedFrustums);
    aiSelectController.subscribe(updateGeneratedFrustums);
    // Generated Frustum picking: a click (not an orbit drag) near a frustum's
    // lines selects its View for Gallery ↔ Frustum sync; all other pointer
    // work passes through untouched.
    const pickWorld = new Vec3();
    const pickProjected = new Vec3();
    const pickOffset = new Vec3();
    let pickStart: { x: number; y: number } | null = null;
    editorUI.canvasContainer.dom.addEventListener('pointerdown', (event) => {
        if (event.button === 0) {
            pickStart = { x: event.clientX, y: event.clientY };
        }
    });
    editorUI.canvasContainer.dom.addEventListener('pointerup', (event) => {
        const start = pickStart;
        pickStart = null;
        if (
            start === null ||
            event.button !== 0 ||
            Math.abs(event.clientX - start.x) +
                Math.abs(event.clientY - start.y) >
                4 ||
            aiSelectController.state.context === null ||
            aiSelectGeneratedViews.state.views.length === 0
        ) {
            return;
        }
        const rect = editorUI.canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            return;
        }
        const cameraPosition = scene.camera.mainCamera.getPosition();
        const cameraForward = scene.camera.mainCamera.forward;
        const viewportSpan = Math.max(rect.width, rect.height);
        const viewId = pickGeneratedViewFrustum(
            aiSelectGeneratedViews.state.views.map((view) => ({
                viewId: view.viewId,
                cameraBinding: view.cameraBinding
            })),
            (x, y, z) => {
                pickWorld.set(x, y, z);
                pickOffset.sub2(pickWorld, cameraPosition);
                const inFront = pickOffset.dot(cameraForward) > 0;
                scene.camera.worldToScreen(pickWorld, pickProjected);
                return { x: pickProjected.x, y: pickProjected.y, inFront };
            },
            (event.clientX - rect.left) / rect.width,
            (event.clientY - rect.top) / rect.height,
            10 / viewportSpan,
            32 / viewportSpan
        );
        if (viewId === null) {
            return;
        }
        try {
            aiSelectGeneratedViews.selectView(viewId);
        } catch (error) {
            console.error(error);
        }
    });

    let nextCameraBindingRevision = 0;
    const reportAISelectError = (error: unknown) => {
        console.error(error);
        events.invoke('showPopup', {
            type: 'error',
            header: i18n.t('popup.error'),
            message: i18n.t('ai-select.start-error')
        });
    };
    const reportAISelectUserViewError = (error: unknown) => {
        console.error(error);
        events.invoke('showPopup', {
            type: 'error',
            header: i18n.t('popup.error'),
            message: i18n.t('ai-select.user-view.error')
        });
    };
    // Add Current View / Confirm View share one entry point: the captured or
    // adjusted CameraBinding becomes a user-owned AIView whose authoritative
    // render starts immediately. The Editor Camera is never moved. If Camera
    // Inspection is active, the visible camera is the external observer — the
    // saved Scene View is restored first so the capture binds the real
    // Current Editor Camera.
    const addAISelectUserViewFromCurrentCamera = () => {
        try {
            cameraInspection.returnToSceneView();
            aiSelectGeneratedViews.addUserView(
                captureEditorCameraBinding(
                    scene.camera,
                    nextCameraBindingRevision++
                )
            );
        } catch (error) {
            reportAISelectUserViewError(error);
        }
    };
    const startAISelect = async (restart: boolean) => {
        if (restart) {
            // Restart must use the saved Scene View as its baseline. The
            // external inspection observer is never an implicit new Anchor.
            cameraInspection.returnToSceneView();
        }
        const selectedSplat = restart
            ? aiSelectTargetSplat
            : (events.invoke('selection') as Splat | null);
        if (!selectedSplat || !selectedSplat.visible) {
            throw new Error(
                'Select one visible Target Splat before starting AI Select.'
            );
        }
        const input = aiSelectTargetFactory.create(
            selectedSplat,
            scene.camera,
            nextCameraBindingRevision++
        );
        const queued = await commandQueue.enqueue(() => {
            // Keep the durable Splat owner and context transition atomic with a
            // queued tool exit. A rapid deactivate/reactivate must not let the
            // old exit clear the owner of the newly started context.
            aiSelectTargetSplat = selectedSplat;
            return {
                completion:
                    restart || aiSelectController.state.context !== null
                        ? aiSelectController.restart(input.start)
                        : aiSelectController.start(input.start)
            };
        });
        await queued.completion;
    };
    const aiSelectTargetLifecycle = new AISelectTargetLifecycleController({
        getSnapshot: () => ({
            hasContext: aiSelectController.state.context !== null,
            hasUnconfirmedChanges:
                aiSelectMaskController.state.hasUnconfirmedChanges ||
                aiSelectAnchorAdjustment.state.status === 'changed' ||
                aiSelectAnchorAdjustment.mask.state.hasUnconfirmedChanges ||
                cameraInspection.state.target?.kind === 'user-view-draft' ||
                aiSelectGeneratedViews.state.views.some(
                    (view) =>
                        aiSelectUserViewMasks.stateFor(view.viewId)
                            ?.hasUnconfirmedChanges ?? false
                ),
            hasConfirmedTargetState:
                aiSelectConfirmation.state.confirmedAnchor !== null ||
                aiSelectGeneratedViews.state.views.length > 0 ||
                aiSelectCandidatePublications.presentationState.status !==
                    'empty',
            candidateApplied:
                aiSelectCandidateApplication.state.status === 'applied'
        }),
        confirmRestart: async () => {
            const result = await events.invoke('showPopup', {
                type: 'yesno',
                header: i18n.t('ai-select.restart-current-target'),
                message: i18n.t('ai-select.restart-confirm-message')
            });
            return result.action === 'yes';
        },
        restartCurrentTarget: () => startAISelect(true)
    });
    events.on('aiSelect.chooseAnotherObject', () => {
        aiSelectTargetLifecycle
            .chooseAnotherObject()
            .catch((error) => reportAISelectError(error));
    });
    const beginAnchorAdjustment = (): void => {
        cameraInspection.returnToSceneView();
        aiSelectAnchorAdjustment.beginAdjustment();
        const draft = aiSelectAnchorAdjustment.state.draft;
        if (draft === null) {
            throw new Error('AI Select failed to create an Anchor adjustment.');
        }
        cameraInspection.enter({
            kind: 'anchor-adjustment-draft',
            cameraBinding: draft.cameraBinding
        });
    };
    const cancelInspection = (): void => {
        if (isAnchorAdjustmentInspectionTarget(cameraInspection.state)) {
            aiSelectAnchorAdjustment.cancelAdjustment();
        }
        cameraInspection.returnToSceneView();
    };
    const resetAnchorAdjustment = (): void => {
        const binding = aiSelectAnchorAdjustment.resetAdjustmentPose();
        cameraInspection.syncAnchorAdjustmentDraft(binding);
    };
    const aiSelectDock = new AISelectAnchorDock(
        aiSelectController,
        aiSelectMaskController,
        aiSelectConfirmation,
        {
            anchorAdjustment: aiSelectAnchorAdjustment,
            generatedViews: aiSelectGeneratedViews,
            candidateCorrection: aiSelectCandidateCorrection,
            candidatePresentation: aiSelectCandidatePresentation,
            maskRegistry: aiSelectMaskController.maskRegistry,
            userViewMasks: aiSelectUserViewMasks,
            onInspectCamera: (viewId) => {
                if (
                    isAnchorAdjustmentInspectionTarget(cameraInspection.state)
                ) {
                    aiSelectAnchorAdjustment.cancelAdjustment();
                }
                if (viewId === null) {
                    cameraInspection.returnToSceneView();
                    return;
                }
                const view = aiSelectGeneratedViews.state.views.find(
                    (entry) => entry.viewId === viewId
                );
                if (view === undefined) {
                    return;
                }
                // Navigator selection adopts the planner-owned CameraBinding
                // exactly, including roll, so the main viewport matches the
                // authoritative 2D RGB. The binding remains read-only.
                cameraInspection.enter({
                    kind: 'view',
                    viewId,
                    cameraBinding: view.cameraBinding
                });
            },
            readiness: selectionServiceReadiness,
            liftReadiness: aiSelectLiftReadiness,
            tooltips: editorUI.tooltips,
            canUndoSceneChange: () => editHistory.canUndo(),
            onUndoSceneChange: async () => {
                await editHistory.undo();
                synchronizeAISelectTargetDependency();
            },
            onConfirmAnchor: async () => {
                try {
                    await aiSelectConfirmation.confirmAnchor();
                } catch (error) {
                    const warnings =
                        aiSelectConfirmation.state.validation?.softWarnings ??
                        [];
                    if (warnings.length === 0) {
                        throw error;
                    }
                    // Soft warnings stay user-overridable; hard blocks already
                    // rejected above and never reach this override.
                    const result = await events.invoke('showPopup', {
                        type: 'yesno',
                        header: i18n.t('ai-select.anchor.confirm'),
                        message: `${warnings
                            .map((warning) =>
                                i18n.t(`ai-select.validation.soft.${warning}`)
                            )
                            .join('\n')}\n${i18n.t(
                            'ai-select.validation.soft-confirm'
                        )}`
                    });
                    if (result.action !== 'yes') {
                        return;
                    }
                    await aiSelectConfirmation.confirmAnchor({
                        overrideSoftWarnings: true
                    });
                }
            },
            onConfirmAnchorAdjustment: async () => {
                try {
                    await aiSelectAnchorAdjustment.confirmAdjustment();
                } catch (error) {
                    const warnings =
                        aiSelectAnchorAdjustment.state.validation
                            ?.softWarnings ?? [];
                    if (warnings.length === 0) {
                        throw error;
                    }
                    const result = await events.invoke('showPopup', {
                        type: 'yesno',
                        header: i18n.t('ai-select.anchor.confirm'),
                        message: `${warnings
                            .map((warning) =>
                                i18n.t(`ai-select.validation.soft.${warning}`)
                            )
                            .join('\n')}\n${i18n.t(
                            'ai-select.validation.soft-confirm'
                        )}`
                    });
                    if (result.action !== 'yes') {
                        return;
                    }
                    await aiSelectAnchorAdjustment.confirmAdjustment({
                        overrideSoftWarnings: true
                    });
                }
            }
        }
    );
    const aiSelectToolbar = new AISelectToolbar(
        aiSelectController,
        cameraInspection,
        aiSelectConfirmation,
        aiSelectAnchorAdjustment,
        {
            candidatePresentation: aiSelectCandidatePresentation,
            candidateOverlay: aiSelectCandidateOverlay,
            candidateApplication: aiSelectCandidateApplication,
            onCandidateApplicationFailure: (error) => console.error(error),
            onBeginAnchorAdjustment: () => {
                try {
                    beginAnchorAdjustment();
                } catch (error) {
                    reportAISelectError(error);
                }
            },
            onCancelInspection: cancelInspection,
            onResetAnchorAdjustment: resetAnchorAdjustment,
            onAddCurrentView: addAISelectUserViewFromCurrentCamera,
            onAdjustNewView: () => {
                try {
                    // A live inspection observes through the external
                    // observer camera; restore the real Scene View first so
                    // the provisional draft starts from it.
                    cameraInspection.returnToSceneView();
                    cameraInspection.enter({
                        kind: 'user-view-draft',
                        cameraBinding: captureEditorCameraBinding(
                            scene.camera,
                            nextCameraBindingRevision++
                        )
                    });
                } catch (error) {
                    reportAISelectUserViewError(error);
                }
            },
            onConfirmDraftView: () => {
                try {
                    const binding = cameraInspection.confirmDraftView();
                    aiSelectGeneratedViews.addUserView(binding);
                } catch (error) {
                    reportAISelectUserViewError(error);
                }
            }
        }
    );
    let lastAISelectPanelContextId: string | null = null;
    aiSelectController.subscribe((state) => {
        const targetContextId = state.context?.targetContextId ?? null;
        if (
            targetContextId !== null &&
            targetContextId !== lastAISelectPanelContextId
        ) {
            events.fire('statusBar.setPanel', 'aiSelect');
        }
        lastAISelectPanelContextId = targetContextId;
    });
    editorUI.aiSelectPanel.append(aiSelectDock);
    editorUI.canvasContainer.append(aiSelectToolbar);
    toolManager.register('aiSelect', {
        activate: () => {
            startAISelect(false).catch((error) => {
                reportAISelectError(error);
                events.fire('tool.deactivate');
            });
        },
        deactivate: () => {
            cameraInspection.returnToSceneView();
            commandQueue
                .enqueue(() => {
                    aiSelectController.exit();
                    aiSelectTargetSplat = null;
                    aiSelectCandidateViewportOverlay.destroy();
                })
                .catch((error) => console.error(error));
            events.fire('statusBar.closePanel', 'aiSelect');
        }
    });

    // apply stored user preferences and start capturing changes to them.
    // registered after the boot-time initialization events above so they are
    // never captured as user changes.
    registerPreferences(events, sceneConfig, urlArgs);

    // load async models
    scene.start();

    // handle load params
    const loadList = url.searchParams.getAll('load');
    const filenameList = url.searchParams.getAll('filename');
    for (const [i, value] of loadList.entries()) {
        const decoded = decodeURIComponent(value);
        const filename =
            i < filenameList.length
                ? decodeURIComponent(filenameList[i])
                : decoded.split('/').pop();

        await events.invoke('import', [
            {
                filename,
                url: decoded
            }
        ]);
    }

    // handle OS-based file association in PWA mode
    if ('launchQueue' in window) {
        window.launchQueue.setConsumer(async (launchParams: LaunchParams) => {
            for (const file of launchParams.files) {
                await events.invoke('import', [
                    {
                        filename: file.name,
                        contents: await file.getFile()
                    }
                ]);
            }
        });
    }
};

export { main };
