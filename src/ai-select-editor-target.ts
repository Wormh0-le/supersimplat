import type { StartAnchorInput } from './ai-select/anchor-controller';
import {
    captureEditorCameraBinding,
    type EditorCameraBindingSource
} from './ai-select/camera-binding';
import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';
import type { Splat } from './splat';
import { SplatSceneSnapshotBinding } from './splat-scene-snapshot';

export interface AISelectEditorTargetInput {
    readonly targetSplat: Splat;
    readonly start: StartAnchorInput;
}

/**
 * Bridges the editor-owned Splat snapshot and Stable Gaussian ID mapping into
 * the narrow v1 Anchor request. It deliberately creates no service-side
 * target/session record: the WeakMap inside SplatSceneSnapshotBinding remains
 * the single owner of Stable Gaussian IDs.
 */
export class AISelectEditorTargetFactory {
    private readonly getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    private readonly bindings = new WeakMap<Splat, SplatSceneSnapshotBinding>();

    constructor(options: {
        getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    }) {
        this.getRenderConfiguration = options.getRenderConfiguration;
    }

    create(
        targetSplat: Splat,
        camera: EditorCameraBindingSource,
        cameraRevision = 0
    ): AISelectEditorTargetInput {
        if (!targetSplat.visible) {
            throw new Error('Select one visible Target Splat before starting AI Select.');
        }
        const splatId = `editor-splat:${targetSplat.uid}`;
        const binding = this.bindingFor(targetSplat, splatId);
        const snapshot = binding.getPackedSnapshot();
        const getCurrentDependencyToken = () => {
            const revision = binding.getSemanticRevision();
            return Object.freeze({
                splatId,
                renderStateToken: revision.renderStateToken,
                geometryToken: revision.geometryToken,
                gaussianIdentityToken: revision.gaussianIdentityToken,
                worldTransformToken: revision.worldTransformToken
            });
        };
        const dependencyToken = getCurrentDependencyToken();

        return Object.freeze({
            targetSplat,
            start: Object.freeze({
                target: Object.freeze({ splatId }),
                dependencyToken,
                // This callback only reads semantic editor revisions. It never
                // reconstructs or hashes the packed SceneSnapshot while an
                // asynchronous Companion result is being checked.
                getCurrentDependencyToken,
                snapshot,
                cameraBinding: captureEditorCameraBinding(camera, cameraRevision)
            })
        });
    }

    private bindingFor(splat: Splat, sceneId: string): SplatSceneSnapshotBinding {
        const existing = this.bindings.get(splat);
        if (existing) {
            return existing;
        }
        const binding = new SplatSceneSnapshotBinding({
            splat,
            sceneId,
            getRenderConfiguration: this.getRenderConfiguration
        });
        this.bindings.set(splat, binding);
        return binding;
    }
}
