import {
    type BinarySceneSnapshotManifest,
    type PackedSceneSnapshot
} from './scene-snapshot-binary';

interface BinarySceneSnapshotUploadAdmission {
    readonly status: 'staged' | 'alreadyCommitted';
    readonly uploadId?: string;
    readonly missingChunkIndices: readonly number[];
}

interface BinarySceneSnapshotRegistrationResult {
    readonly status: 'committed' | 'alreadyCommitted';
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly contentDigest: string;
}

interface BinarySceneSnapshotRegistrationTransport {
    begin(
        manifest: BinarySceneSnapshotManifest
    ): Promise<BinarySceneSnapshotUploadAdmission>;
    uploadChunk(
        uploadId: string,
        index: number,
        bytes: Uint8Array,
        digest: string
    ): Promise<void>;
    commit(uploadId: string): Promise<BinarySceneSnapshotRegistrationResult>;
    abort(uploadId: string): Promise<void>;
}

/**
 * The editor-side registration seam. Callers use one operation; retry,
 * missing-chunk replay, abort, and commit ordering remain implementation work.
 */
class BinarySceneSnapshotRegistrar {
    private readonly transport: BinarySceneSnapshotRegistrationTransport;

    constructor(transport: BinarySceneSnapshotRegistrationTransport) {
        this.transport = transport;
    }

    register(
        _snapshot: PackedSceneSnapshot,
        _options?: { readonly chunkByteLength?: number }
    ): Promise<BinarySceneSnapshotRegistrationResult> {
        return this.notImplemented(this.transport);
    }

    private notImplemented(
        _transport: BinarySceneSnapshotRegistrationTransport
    ): Promise<BinarySceneSnapshotRegistrationResult> {
        return Promise.reject(
            new Error(
                'Binary SceneSnapshot Registration v1 is not implemented.'
            )
        );
    }
}

export { BinarySceneSnapshotRegistrar };

export type {
    BinarySceneSnapshotRegistrationResult,
    BinarySceneSnapshotRegistrationTransport,
    BinarySceneSnapshotUploadAdmission
};
