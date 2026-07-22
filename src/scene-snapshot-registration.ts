import {
    createBinarySceneSnapshotManifest,
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

class BinarySceneSnapshotRegistrar {
    private readonly transport: BinarySceneSnapshotRegistrationTransport;

    constructor(transport: BinarySceneSnapshotRegistrationTransport) {
        this.transport = transport;
    }

    async register(
        snapshot: PackedSceneSnapshot,
        options?: { readonly chunkByteLength?: number }
    ): Promise<BinarySceneSnapshotRegistrationResult> {
        const manifest = createBinarySceneSnapshotManifest(
            snapshot,
            options?.chunkByteLength
        );
        const admission = await this.retry(() => this.transport.begin(manifest));
        if (admission.status === 'alreadyCommitted') {
            if (admission.missingChunkIndices.length !== 0) {
                throw new Error(
                    'A committed Binary Scene Snapshot cannot report missing upload chunks.'
                );
            }
            return {
                status: 'alreadyCommitted',
                sceneId: snapshot.sceneId,
                sceneVersion: snapshot.sceneVersion,
                contentDigest: snapshot.contentDigest
            };
        }
        if (!admission.uploadId) {
            throw new Error(
                'The Selection Service Companion did not bind a staged Snapshot upload ID.'
            );
        }
        const chunksByIndex = new Map(
            manifest.transfer.chunks.map(chunk => [chunk.index, chunk])
        );
        const missingIndices = new Set<number>();
        admission.missingChunkIndices.forEach((index) => {
            if (
                !Number.isInteger(index) ||
                !chunksByIndex.has(index) ||
                missingIndices.has(index)
            ) {
                throw new Error(
                    'The Selection Service Companion returned invalid missing Snapshot chunk indices.'
                );
            }
            missingIndices.add(index);
        });
        try {
            for (const index of admission.missingChunkIndices) {
                const chunk = chunksByIndex.get(index);
                if (!chunk) {
                    throw new Error(
                        'The Selection Service Companion requested an unknown Snapshot chunk.'
                    );
                }
                const bytes = snapshot.readPayloadRange(
                    chunk.offset,
                    chunk.byteLength
                );
                await this.retry(() => this.transport.uploadChunk(
                        admission.uploadId as string,
                        chunk.index,
                        bytes,
                        chunk.digest
                ));
            }
            const result = await this.retry(() => this.transport.commit(admission.uploadId as string));
            this.assertResult(snapshot, result);
            return result;
        } catch (error) {
            try {
                await this.transport.abort(admission.uploadId);
            } catch {
                // The caller needs the original upload/commit failure. Abort is
                // best-effort because Companion TTL cleanup also owns staging.
            }
            throw error;
        }
    }

    private async retry<T>(operation: () => Promise<T>): Promise<T> {
        try {
            return await operation();
        } catch (firstError) {
            return operation();
        }
    }

    private assertResult(
        snapshot: PackedSceneSnapshot,
        result: BinarySceneSnapshotRegistrationResult
    ): void {
        if (
            (result.status !== 'committed' &&
                result.status !== 'alreadyCommitted') ||
            result.sceneId !== snapshot.sceneId ||
            result.sceneVersion !== snapshot.sceneVersion ||
            result.contentDigest !== snapshot.contentDigest
        ) {
            throw new Error(
                'The Selection Service Companion returned an invalid committed Snapshot binding.'
            );
        }
    }
}

export { BinarySceneSnapshotRegistrar };

export type {
    BinarySceneSnapshotRegistrationResult,
    BinarySceneSnapshotRegistrationTransport,
    BinarySceneSnapshotUploadAdmission
};
