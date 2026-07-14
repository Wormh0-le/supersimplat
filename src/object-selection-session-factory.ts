import { EditHistory } from './edit-history';
import {
    ObjectSelectionSession,
    type ObjectSelectionPrompt,
    type ObjectSelectionSessionInterface,
    type ObjectSelectionTarget,
    type SelectionServiceAdapter
} from './object-selection-session';
import { SelectOpObjectSelectionSessionEditor } from './object-selection-session-editor';
import type { SceneSnapshotRenderConfiguration } from './scene-snapshot';
import type { Splat } from './splat';
import { SplatSceneSnapshotBinding } from './splat-scene-snapshot';

interface ObjectSelectionSessionHandle {
    readonly session: ObjectSelectionSessionInterface;
    readonly target: ObjectSelectionTarget;
    startNew(prompt: ObjectSelectionPrompt): Promise<void>;
}

// This is the one production bridge from a Target Splat to the deep session
// module. It deliberately keeps Stable IDs, Scene Snapshot construction, and
// SelectOp selection commits on the editor side of the Companion boundary.
class ObjectSelectionSessionFactory {
    private selectionService: SelectionServiceAdapter;
    private editHistory: EditHistory;
    private getModelManifestDigest: () => string | null;
    private getRenderConfiguration: () => SceneSnapshotRenderConfiguration;

    constructor(options: {
        selectionService: SelectionServiceAdapter;
        editHistory: EditHistory;
        getModelManifestDigest: () => string | null;
        getRenderConfiguration: () => SceneSnapshotRenderConfiguration;
    }) {
        this.selectionService = options.selectionService;
        this.editHistory = options.editHistory;
        this.getModelManifestDigest = options.getModelManifestDigest;
        this.getRenderConfiguration = options.getRenderConfiguration;
    }

    create(splat: Splat): ObjectSelectionSessionHandle {
        const target: ObjectSelectionTarget = {
            targetSplatId: `editor-splat:${splat.uid}`
        };
        const scene = new SplatSceneSnapshotBinding({
            splat,
            sceneId: target.targetSplatId,
            getRenderConfiguration: this.getRenderConfiguration
        });
        const session = new ObjectSelectionSession({
            selectionService: this.selectionService,
            editor: new SelectOpObjectSelectionSessionEditor({
                splat,
                editHistory: this.editHistory,
                stableIds: scene
            })
        });

        return {
            session,
            target,
            startNew: async (prompt) => {
                const modelManifestDigest = this.getModelManifestDigest();
                if (modelManifestDigest === null) {
                    throw new Error('Select a ready Companion Model Manifest before starting Object Selection.');
                }
                await session.startNew({
                    target,
                    prompt,
                    scene,
                    requestContext: {
                        deterministicSeed: `${target.targetSplatId}:${prompt.promptId}`,
                        frameSetVersion: `anchor:${prompt.viewId}`,
                        modelManifestDigest
                    }
                });
            }
        };
    }
}

export { ObjectSelectionSessionFactory };

export type { ObjectSelectionSessionHandle };
