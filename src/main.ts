import { WebPCodec, WorkerQueue } from '@playcanvas/splat-transform';
import { Color, createGraphicsDevice } from 'playcanvas';

import { registerCameraPosesEvents } from './camera-poses';
import { CommandQueue } from './command-queue';
import { registerDocEvents } from './doc';
import { EditHistory } from './edit-history';
import { registerEditorEvents } from './editor';
import { Events } from './events';
import { initFileHandler } from './file-handler';
import { registerIframeApi } from './iframe-api';
import {
    ObjectSelectionSessionFactory,
    type ObjectSelectionSessionHandle
} from './object-selection-session-factory';
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
import { BoundDimensionsOverlay } from './ui/bound-dimensions-overlay';
import { EditorUI } from './ui/editor';
import { i18n } from './ui/localization';
import { ObjectSelectionPanel } from './ui/object-selection-panel';
import { ObjectSelectionToolbar } from './ui/object-selection-toolbar';
import { registerSelectCursor } from './ui/select-cursor';

declare global {
    interface LaunchParams {
        readonly files: FileSystemFileHandle[];
    }

    interface Window {
        launchQueue: {
            setConsumer: (callback: (launchParams: LaunchParams) => void) => void;
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
    events.function('queue', (fn: () => Promise<void> | void) => commandQueue.enqueue(fn));

    // init localization
    await i18n.init();

    // Configure WebP WASM for SOG format (used for both reading and writing)
    WebPCodec.wasmUrl = new URL('static/lib/webp/webp.wasm', document.baseURI).toString();

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
    selectionServiceAdapter.setAdapter(new FetchSelectionServiceAdapter({
        getConfiguration: () => selectionServiceReadiness.state.configuration
    }));
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
    const scene = new Scene(events, sceneConfig, editorUI.canvas, graphicsDevice, commandQueue);

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
        const cnv = (v: number) => `${Math.max(0, Math.min(255, v * 255)).toFixed(0)}`;
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
    toolManager.register('rectSelection', new RectSelection(events, editorUI.toolsContainer.dom));
    toolManager.register('brushSelection', new BrushSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register(
        'floodSelection',
        new FloodSelection(events, editorUI.toolsContainer.dom, mask, editorUI.canvasContainer)
    );
    toolManager.register('polygonSelection', new PolygonSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register('lassoSelection', new LassoSelection(events, editorUI.toolsContainer.dom, mask));
    toolManager.register('sphereSelection', new SphereSelection(events, scene, editorUI.canvasContainer));
    toolManager.register('boxSelection', new BoxSelection(events, scene, editorUI.canvasContainer));
    toolManager.register(
        'eyedropperSelection',
        new EyedropperSelection(events, editorUI.toolsContainer.dom, editorUI.canvasContainer)
    );
    toolManager.register('move', new MoveTool(events, scene));
    toolManager.register('rotate', new RotateTool(events, scene));
    toolManager.register('scale', new ScaleTool(events, scene));
    toolManager.register(
        'measure',
        new MeasureTool(events, scene, editorUI.toolsContainer.dom, editorUI.canvasContainer)
    );

    const boundDimensionsOverlay = new BoundDimensionsOverlay(events, scene, editorUI.canvasContainer);

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

    // UI workflows obtain a fresh handle for their one selected Target Splat.
    // The handle owns the real Scene Snapshot/Stable-ID/SelectOp bridge; its
    // session still uses the readiness-gated transport published above.
    const objectSelectionSessions = new ObjectSelectionSessionFactory({
        selectionService: selectionServiceAdapter,
        editHistory,
        getModelManifestDigest: () => selectionServiceReadiness.state.configuration.modelManifestDigest,
        getRenderConfiguration: (): SceneSnapshotRenderConfiguration => {
            const background = events.invoke('bgClr') as Color;
            return {
                version: 'supersplat-effective-rgb-v1',
                backgroundRgba: [background.r, background.g, background.b, background.a],
                alphaMode: 'opaque-background',
                shBands: events.invoke('view.bands') as number,
                rasterizer: 'playcanvas-gsplat-classic'
            };
        }
    });
    events.function('objectSelection.createSession', (requestedSplat?: Splat) => {
        const splat = requestedSplat ?? events.invoke('selection') as Splat | null;
        if (!splat || !splat.visible) {
            throw new Error('Select one visible Target Splat before starting Object Selection.');
        }
        return objectSelectionSessions.create(splat);
    });

    let anchorPromptPoint: { xPx: number; yPx: number } | null = null;
    let anchorPromptCount = 0;
    let objectSelectionHandle: ObjectSelectionSessionHandle | null = null;
    let objectSelectionToolbar: ObjectSelectionToolbar | null = null;
    let objectSelectionPanel: ObjectSelectionPanel | null = null;

    editorUI.canvas.addEventListener('pointerdown', (event) => {
        if (event.button !== 0) {
            return;
        }
        const rect = editorUI.canvas.getBoundingClientRect();
        anchorPromptPoint = {
            xPx: Math.round((event.clientX - rect.left) * editorUI.canvas.width / rect.width),
            yPx: Math.round((event.clientY - rect.top) * editorUI.canvas.height / rect.height)
        };
    });

    const reportObjectSelectionError = (error: unknown) => {
        console.error(error);
    };

    const mountObjectSelection = (splat: Splat | null) => {
        // Keep an active Target Splat and its controls intact until the user
        // confirms or cancels; a normal editor selection change cannot retarget
        // a live Companion session.
        if (objectSelectionHandle?.session.state.status !== 'idle') {
            return;
        }
        if (!splat) {
            objectSelectionToolbar?.destroy();
            objectSelectionPanel?.destroy();
            objectSelectionHandle = null;
            objectSelectionToolbar = null;
            objectSelectionPanel = null;
            return;
        }
        if (objectSelectionHandle?.target.targetSplatId === `editor-splat:${splat.uid}`) {
            return;
        }

        objectSelectionToolbar?.destroy();
        objectSelectionPanel?.destroy();
        const handle = events.invoke(
            'objectSelection.createSession', splat
        ) as ObjectSelectionSessionHandle;
        const startNew = () => {
            if (anchorPromptPoint === null) {
                return Promise.reject(new Error('Click an Anchor View point before starting Object Selection.'));
            }
            return handle.startNew({
                promptId: `anchor-prompt-${++anchorPromptCount}`,
                viewId: 'anchor-view',
                xPx: anchorPromptPoint.xPx,
                yPx: anchorPromptPoint.yPx,
                polarity: 'include'
            });
        };
        objectSelectionHandle = handle;
        objectSelectionToolbar = new ObjectSelectionToolbar(handle.session, {
            startNew,
            onError: reportObjectSelectionError
        });
        objectSelectionPanel = new ObjectSelectionPanel(handle.session, {
            onError: reportObjectSelectionError
        });
        editorUI.canvasContainer.append(objectSelectionToolbar);
        editorUI.canvasContainer.append(objectSelectionPanel);

        handle.session.subscribe((state) => {
            if (state.status === 'idle') {
                mountObjectSelection(events.invoke('selection') as Splat | null);
            }
        });
    };

    events.on('selection.changed', (splat: Splat | null) => mountObjectSelection(splat));
    mountObjectSelection(events.invoke('selection') as Splat | null);

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
        const filename = i < filenameList.length ? decodeURIComponent(filenameList[i]) : decoded.split('/').pop();

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
