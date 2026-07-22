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
        const snapshot = new SplatSceneSnapshotBinding({
            splat: targetSplat,
            sceneId: splatId,
            getRenderConfiguration: this.getRenderConfiguration
        }).getSnapshot();
        const snapshotToken = snapshot.sceneVersion;

        return Object.freeze({
            targetSplat,
            start: Object.freeze({
                target: Object.freeze({ splatId }),
                dependencyToken: Object.freeze({
                    splatId,
                    renderStateToken: `${snapshotToken}:${snapshot.renderConfiguration.version}`,
                    geometryToken: snapshotToken,
                    gaussianIdentityToken: snapshotToken,
                    worldTransformToken: snapshotToken
                }),
                snapshot,
                cameraBinding: captureEditorCameraBinding(camera, cameraRevision)
            })
        });
    }
}
