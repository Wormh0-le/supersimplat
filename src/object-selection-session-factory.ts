import { EditHistory } from './edit-history';
import {
    ObjectSelectionSession,
    anchorFrameSetId,
    anchorFrameSetVersion,
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
  startNew(prompt: ObjectSelectionAnchorPrompt): Promise<void>;
}

// PNG bytes belong to the immutable Anchor Frame Set, not to the point-only
// Prompt Log accepted by ObjectSelectionSession.
interface ObjectSelectionAnchorPrompt extends ObjectSelectionPrompt {
  imagePngBase64: string;
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
                    throw new Error(
                        'Select a ready Companion Model Manifest before starting Object Selection.'
                    );
                }
                if (!prompt.imagePngBase64) {
                    throw new Error(
                        'Capture the visible Anchor View PNG before starting Object Selection.'
                    );
                }
                const frameSetId = anchorFrameSetId(target.targetSplatId);
                // Frame Set versions are Companion-cache keys, so they must be
                // globally unique rather than only image-content-addressed.
                const frameSetVersion = anchorFrameSetVersion(
                    target.targetSplatId,
                    prompt.frameDigest
                );
                await session.startNew({
                    target,
                    prompt: {
                        promptId: prompt.promptId,
                        viewId: prompt.viewId,
                        frameDigest: prompt.frameDigest,
                        frameWidth: prompt.frameWidth,
                        frameHeight: prompt.frameHeight,
                        xPx: prompt.xPx,
                        yPx: prompt.yPx,
                        polarity: prompt.polarity
                    },
                    scene,
                    requestContext: {
                        deterministicSeed: `${target.targetSplatId}:${prompt.promptId}`,
                        frameSetVersion,
                        frameSet: {
                            frameSetId,
                            frameSetVersion,
                            orderedViews: [
                                {
                                    viewId: prompt.viewId,
                                    frameDigest: prompt.frameDigest,
                                    width: prompt.frameWidth,
                                    height: prompt.frameHeight,
                                    imagePngBase64: prompt.imagePngBase64
                                }
                            ]
                        },
                        modelManifestDigest
                    }
                });
            }
        };
    }
}

export { ObjectSelectionSessionFactory };

export type { ObjectSelectionAnchorPrompt, ObjectSelectionSessionHandle };
