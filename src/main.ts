import { WebPCodec, WorkerQueue } from '@playcanvas/splat-transform';
import { Color, Vec3, createGraphicsDevice } from 'playcanvas';

import { AISelectAnchorController } from './ai-select/anchor-controller';
import { CameraInspectionController } from './ai-select/camera-inspection';
import { AnchorFrustumManipulator } from './ai-select/camera-inspection-manipulator';
import { AnchorFrustum } from './ai-select-anchor-frustum';
import { AISelectEditorTargetFactory } from './ai-select-editor-target';
import { registerCameraPosesEvents } from './camera-poses';
import { CommandQueue } from './command-queue';
import { registerDocEvents } from './doc';
import { EditHistory } from './edit-history';
import { registerEditorEvents } from './editor';
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
        probe: new FetchSelectionServiceReadinessProbe()
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
        getRenderConfiguration: getAISelectRenderConfiguration
    });
    const aiSelectController = new AISelectAnchorController({
        renderer: selectionServiceAdapter
    });
    const cameraInspection = new CameraInspectionController({
        anchor: aiSelectController,
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
            }
        }
    });
    const anchorFrustum = new AnchorFrustum();
    await scene.add(anchorFrustum);
    const updateAnchorFrustum = () => {
        const anchor = aiSelectController.state.anchor;
        const inspecting = cameraInspection.state.mode === 'active';
        anchorFrustum.setCameraBinding(
            inspecting ? (anchor?.cameraBinding ?? null) : null
        );
        anchorFrustum.setVisible(inspecting && anchor !== null);
    };
    aiSelectController.subscribe(updateAnchorFrustum);
    cameraInspection.subscribe(updateAnchorFrustum);
    const anchorFrustumManipulator = new AnchorFrustumManipulator({
        scene,
        controller: aiSelectController,
        inspection: cameraInspection
    });

    let aiSelectTargetSplat: Splat | null = null;
    let nextCameraBindingRevision = 0;
    const reportAISelectError = (error: unknown) => {
        console.error(error);
        events.invoke('showPopup', {
            type: 'error',
            header: i18n.t('popup.error'),
            message: i18n.t('ai-select.start-error')
        });
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
        aiSelectTargetSplat = selectedSplat;
        if (restart || aiSelectController.state.context !== null) {
            await aiSelectController.restart(input.start);
        } else {
            await aiSelectController.start(input.start);
        }
    };
    const exitAISelect = () => {
        cameraInspection.returnToSceneView();
        aiSelectController.exit();
        aiSelectTargetSplat = null;
        events.fire('tool.deactivate');
    };
    const aiSelectDock = new AISelectAnchorDock(aiSelectController, {
        onRetry: () => aiSelectController.retryAnchorPreview(),
        onReconnect: async () => {
            await selectionServiceReadiness.refresh();
            if (selectionServiceReadiness.state.status !== 'ready') {
                const { diagnostic } = selectionServiceReadiness.state;
                throw new Error(
                    `${diagnostic.message} ${diagnostic.action}`.trim()
                );
            }
            await startAISelect(true);
        },
        onOpenSettings: () => events.fire('settingsPanel.setVisible', true)
    });
    const aiSelectToolbar = new AISelectToolbar(
        aiSelectController,
        cameraInspection,
        {
            onRestart: () => startAISelect(true),
            onExit: exitAISelect,
            onEnterInspection: () => {
                try {
                    cameraInspection.enter();
                } catch (error) {
                    reportAISelectError(error);
                }
            },
            onReturnToSceneView: () => cameraInspection.returnToSceneView(),
            onResetAnchor: () => cameraInspection.resetAnchor()
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
            aiSelectController.exit();
            aiSelectTargetSplat = null;
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
