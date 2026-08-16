import type { StartAnchorInput } from './ai-select/anchor-controller';
import { buildAuthoritativeRenderScopeSnapshot } from './ai-select/authoritative-render-scope';
import {
    captureEditorCameraBinding,
    type EditorCameraBindingSource
} from './ai-select/camera-binding';
import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';
import { sha256Digest } from './scene-snapshot-binary';
import type { Splat } from './splat';
import {
    SplatSceneSnapshotBinding,
    type SplatSnapshotSemanticRevision
} from './splat-scene-snapshot';

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
    private readonly getVisibleSplats: () => readonly Splat[];
    private readonly bindings = new WeakMap<Splat, SplatSceneSnapshotBinding>();

    constructor(options: {
        getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
        getVisibleSplats: () => readonly Splat[];
    }) {
        this.getRenderConfiguration = options.getRenderConfiguration;
        this.getVisibleSplats = options.getVisibleSplats;
    }

    create(
        targetSplat: Splat,
        camera: EditorCameraBindingSource,
        cameraRevision = 0
    ): AISelectEditorTargetInput {
        if (!targetSplat.visible) {
            throw new Error(
                'Select one visible Target Splat before starting AI Select.'
            );
        }
        const splatId = this.splatId(targetSplat);
        const binding = this.bindingFor(targetSplat, splatId);
        const visibleSources = this.visibleRenderSources(targetSplat);
        const snapshot = buildAuthoritativeRenderScopeSnapshot(
            { splatId, snapshot: binding.getPackedSnapshot() },
            visibleSources
        );
        const getCurrentDependencyToken = () =>
            this.currentDependencyTokenFor(targetSplat);
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
                cameraBinding: captureEditorCameraBinding(
                    camera,
                    cameraRevision
                )
            })
        });
    }

    bindingForTarget(targetSplat: Splat): SplatSceneSnapshotBinding {
        return this.bindingFor(targetSplat, this.splatId(targetSplat));
    }

    currentDependencyTokenFor(targetSplat: Splat) {
        const splatId = this.splatId(targetSplat);
        const revisions = this.visibleRenderRevisions(targetSplat);
        const digest = (field: keyof SplatSnapshotSemanticRevision) =>
            sha256Digest(
                new TextEncoder().encode(
                    JSON.stringify(
                        revisions.map((entry) => [
                            entry.splatId,
                            entry.revision[field]
                        ])
                    )
                )
            );
        return Object.freeze({
            splatId,
            renderStateToken: digest('renderStateToken'),
            geometryToken: digest('geometryToken'),
            gaussianIdentityToken: digest('gaussianIdentityToken'),
            worldTransformToken: digest('worldTransformToken')
        });
    }

    private visibleRenderSources(targetSplat: Splat) {
        return this.visibleSplats(targetSplat).map((splat) => {
            const splatId = this.splatId(splat);
            return Object.freeze({
                splatId,
                snapshot: this.bindingFor(splat, splatId).getPackedSnapshot()
            });
        });
    }

    private visibleRenderRevisions(targetSplat: Splat) {
        return this.visibleSplats(targetSplat).map((splat) => {
            const splatId = this.splatId(splat);
            return Object.freeze({
                splatId,
                revision: this.bindingFor(splat, splatId).getSemanticRevision()
            });
        });
    }

    private visibleSplats(targetSplat: Splat): readonly Splat[] {
        const visible = this.getVisibleSplats().filter(
            (splat) => splat.visible && splat !== targetSplat
        );
        visible.sort((left, right) => left.uid - right.uid);
        return Object.freeze([targetSplat, ...visible]);
    }

    private splatId(targetSplat: Splat): string {
        return `editor-splat:${targetSplat.uid}`;
    }

    private bindingFor(
        splat: Splat,
        sceneId: string
    ): SplatSceneSnapshotBinding {
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
