import {
    anchorRenderResponseMatchesRequest,
    decodePngBase64,
    isAnchorRenderRequest,
    isAnchorRenderResponse,
    parsePngDimensions,
    validatePngDecodable,
    type AISelectAnchorRenderer,
    type AnchorRenderRequest,
    type AnchorRenderResponse
} from './ai-select/anchor-render-service';
import {
    areCameraBindingsEqual,
    isCameraBinding
} from './ai-select/camera-binding';
import {
    areTargetDependencyTokensEqual,
    isAIRequestBinding
} from './ai-select/current-target-context';
import {
    assertCompleteMaskSet,
    assertCoverageReport,
    assertEvidenceSnapshot,
    assertPreviewFrameSet,
    previewBindingsFromRequest,
    previewBindingsMatch,
    requestWithFrameSet,
    type ObjectSelectionFrameSet,
    type ObjectSelectionPreviewBindings,
    type ObjectSelectionPreviewRequest,
    type ObjectSelectionServiceSessionStart,
    type SelectionServiceAdapter,
    type SelectionServiceEvidenceSnapshot,
    type SelectionServiceMaskFrame,
    type SelectionServiceMaskSet,
    type SelectionServiceMaskTrack,
    type SelectionServiceCoverageReport,
    type SelectionServicePreviewResponse
} from './object-selection-session';
import { assertSceneSnapshot, type SceneSnapshot } from './scene-snapshot';
import {
    isPackedSceneSnapshot,
    type BinarySceneSnapshotManifest,
    type PackedSceneSnapshot
} from './scene-snapshot-binary';
import {
    BinarySceneSnapshotRegistrar,
    type BinarySceneSnapshotRegistrationResult,
    type BinarySceneSnapshotRegistrationTransport,
    type BinarySceneSnapshotUploadAdmission
} from './scene-snapshot-registration';
import { SelectionServiceTransportError } from './selection-service-readiness';
import {
    buildSpatialSceneSnapshot,
    type SpatialSceneChunkDescriptor,
    type SpatialSceneManifest,
    type SpatialSceneSnapshot
} from './spatial-scene-snapshot';

interface SelectionServiceTransportConfiguration {
    endpoint: string;
    modelManifestDigest: string | null;
}

interface FetchResponse {
    readonly ok: boolean;
    readonly status: number;
    json(): Promise<unknown>;
}

interface SelectionServiceFetchInit {
    method: 'POST' | 'PUT' | 'DELETE';
    headers: Record<string, string>;
    mode: 'cors';
    credentials: 'omit';
    cache: 'no-store';
    body?: string | ArrayBuffer;
}

type SelectionServiceFetch = (
    url: string,
    init: SelectionServiceFetchInit
) => Promise<FetchResponse>;

interface FetchSelectionServiceAdapterOptions {
    getConfiguration: () => SelectionServiceTransportConfiguration;
    supportsCameraAwareSpatialWorkingSet?: () => boolean;
    fetch?: SelectionServiceFetch;
}

interface SceneCacheMissResponse extends ObjectSelectionPreviewBindings {
    status: 'sceneCacheMiss';
}

interface AnchorRenderCacheMissResponse extends Record<string, unknown> {
    readonly status: 'sceneCacheMiss';
    readonly requestBinding: AnchorRenderRequest['requestBinding'];
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly renderAttemptId: string;
    readonly viewId: 'anchor-view';
    readonly cameraBinding: AnchorRenderRequest['cameraBinding'];
}

interface AnchorRenderSceneChunkMissResponse extends Record<string, unknown> {
    readonly status: 'sceneChunkMiss';
    readonly requestBinding: AnchorRenderRequest['requestBinding'];
    readonly targetSplatId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly renderConfigVersion: string;
    readonly renderAttemptId: string;
    readonly viewId: 'anchor-view';
    readonly cameraBinding: AnchorRenderRequest['cameraBinding'];
    readonly workingSetToken: string;
    readonly missingChunkIds: readonly string[];
}

interface SpatialSceneManifestRegistrationResponse {
    readonly status: 'registered' | 'alreadyRegistered';
    readonly registrationId: string;
    readonly sceneId: string;
    readonly sceneVersion: string;
    readonly contentDigest: string;
}

interface SpatialSceneChunkUploadAdmission {
    readonly status: 'staged' | 'alreadyCommitted';
    readonly uploadId?: string;
    readonly missingChunkIds: readonly string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const isSelectionOperation = (
    value: unknown
): value is ObjectSelectionPreviewRequest['operation'] => {
    return (
        value === 'New' ||
        value === 'Add' ||
        value === 'Remove' ||
        value === 'Refine'
    );
};

const isNonNegativeInteger = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isInteger(value) && value >= 0;
};

const isSha256Digest = (value: unknown): value is string => {
    return typeof value === 'string' && /^sha256:[0-9a-f]{64}$/i.test(value);
};

const isSortedUniqueChunkIds = (
    value: unknown,
    requireNonEmpty = false
): value is readonly string[] => {
    return (
        Array.isArray(value) &&
        (!requireNonEmpty || value.length > 0) &&
        value.every(
            (chunkId, index) =>
                typeof chunkId === 'string' &&
                chunkId.length > 0 &&
                (index === 0 || value[index - 1] < chunkId)
        )
    );
};

const browserFetch: SelectionServiceFetch = (url, init) => {
    if (typeof globalThis.fetch !== 'function') {
        throw new SelectionServiceTransportError(
            'browserTransport',
            'Fetch is unavailable in this editor context.'
        );
    }
    return globalThis.fetch(url, init);
};

const transportError = (
    code: 'browserTransport' | 'invalidResponse' | 'http',
    message: string,
    details: { status?: number; serviceMessage?: string } = {}
) => new SelectionServiceTransportError(code, message, details);

class FetchSelectionServiceAdapter
    implements SelectionServiceAdapter, AISelectAnchorRenderer
{
    private getConfiguration: () => SelectionServiceTransportConfiguration;
    private supportsCameraAwareSpatialWorkingSet: () => boolean;
    private fetch: SelectionServiceFetch;
    private registeredSnapshots = new Set<string>();
    private spatialSnapshots = new Map<string, SpatialSceneSnapshot>();
    private spatialManifestRegistrationIds = new Map<string, string>();
    private nextOpenRequestSequence = 0;

    constructor(options: FetchSelectionServiceAdapterOptions) {
        this.getConfiguration = options.getConfiguration;
        this.supportsCameraAwareSpatialWorkingSet =
            options.supportsCameraAwareSpatialWorkingSet ?? (() => false);
        this.fetch = options.fetch ?? browserFetch;
    }

    async openSession(start: ObjectSelectionServiceSessionStart) {
        assertSceneSnapshot(start.snapshot);
        this.assertConfiguredModelManifest(
            start.requestContext.modelManifestDigest
        );
        const openRequestId = this.openRequestId();
        let sessionId: string;
        try {
            sessionId = await this.registerAndOpenSession(start, openRequestId);
        } catch (firstError) {
            try {
                // A lost response can leave a successful admission on the
                // Companion. Replaying the same request ID recovers its
                // session rather than consuming a second model lease.
                sessionId = await this.registerAndOpenSession(
                    start,
                    openRequestId
                );
            } catch (cleanupError) {
                await this.cleanupOpening(
                    openRequestId,
                    start.requestContext.frameSetVersion
                );
                throw firstError;
            }
        }
        try {
            await this.registerSnapshot(start.snapshot);
        } catch (error) {
            try {
                await this.closeSession(sessionId);
            } catch (cleanupError) {
                // The original registration error carries the actionable cause;
                // retain it while making a best-effort capacity cleanup.
            }
            throw error;
        }
        return sessionId;
    }

    async updatePreview(request: ObjectSelectionPreviewRequest) {
        const first = await this.sendPreview(request);
        if (first.status === 'complete') {
            return first;
        }

        this.assertPreviewBindings(first, request, 'cache-miss');
        await this.registerSnapshot(request.snapshot, true);
        const retry = await this.sendPreview(request);
        if (retry.status !== 'complete') {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion repeated a Scene Snapshot cache miss after the editor resent the snapshot.'
            );
        }
        return retry;
    }

    async renderAnchor(
        request: AnchorRenderRequest
    ): Promise<AnchorRenderResponse> {
        if (!isAnchorRenderRequest(request)) {
            throw transportError(
                'invalidResponse',
                'AI Select requires a complete bound Anchor render request.'
            );
        }
        if (!isPackedSceneSnapshot(request.snapshot)) {
            throw transportError(
                'invalidResponse',
                'AI Select requires a Binary SceneSnapshot Registration v1 payload.'
            );
        }
        if (
            request.requestBinding.dependencyToken.splatId !==
            request.target.splatId
        ) {
            throw transportError(
                'invalidResponse',
                'AI Select Anchor request target and dependency bindings must match.'
            );
        }

        if (this.supportsCameraAwareSpatialWorkingSet()) {
            return this.renderSpatialAnchor(request);
        }

        await this.registerPackedSnapshot(request.snapshot);
        const first = await this.sendAnchorRender(request);
        if (first.status === 'complete') {
            return first.response;
        }

        await this.registerPackedSnapshot(request.snapshot, true);
        const retry = await this.sendAnchorRender(request);
        if (retry.status !== 'complete') {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion repeated an Anchor Scene Snapshot cache miss after the editor resent the snapshot.'
            );
        }
        return retry.response;
    }

    private async renderSpatialAnchor(
        request: AnchorRenderRequest
    ): Promise<AnchorRenderResponse> {
        const spatialSnapshot = this.spatialSnapshotFor(request);
        await this.registerSpatialSceneManifest(spatialSnapshot);

        let manifestRecoveryAttempts = 0;
        let chunkRecoveryAttempts = 0;
        for (;;) {
            const result = await this.sendAnchorRender(request, 'spatial-v1');
            if (result.status === 'complete') {
                return result.response;
            }
            if (result.status === 'sceneCacheMiss') {
                if (manifestRecoveryAttempts >= 1) {
                    throw transportError(
                        'invalidResponse',
                        'The Selection Service Companion repeated an Anchor Spatial Scene manifest cache miss after the editor resent the manifest.'
                    );
                }
                manifestRecoveryAttempts += 1;
                await this.registerSpatialSceneManifest(spatialSnapshot, true);
                continue;
            }
            if (chunkRecoveryAttempts >= 1) {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion repeated an Anchor Spatial Scene chunk miss after the editor uploaded its validated working set.'
                );
            }
            chunkRecoveryAttempts += 1;
            await this.uploadSpatialSceneChunks(
                spatialSnapshot,
                result.missingChunkIds
            );
        }
    }

    async releaseSceneSnapshot(request: AnchorRenderRequest): Promise<void> {
        if (!isPackedSceneSnapshot(request.snapshot)) {
            return;
        }
        const key = this.spatialSnapshotKey(
            request.snapshot,
            request.target.splatId
        );
        const registrationId = this.spatialManifestRegistrationIds.get(key);
        if (!registrationId) {
            return;
        }
        await this.requestNoContent(
            `/spatial-scene-manifests/v1/${encodeURIComponent(registrationId)}`,
            'DELETE'
        );
        this.spatialManifestRegistrationIds.delete(key);
        this.spatialSnapshots.delete(key);
    }

    async cancelUpdate(sessionId: string, requestId: string) {
        await this.requestNoContent(
            `/object-selection-sessions/${encodeURIComponent(sessionId)}/previews/${encodeURIComponent(requestId)}`,
            'DELETE'
        );
    }

    async closeSession(sessionId: string) {
        await this.requestNoContent(
            `/object-selection-sessions/${encodeURIComponent(sessionId)}`,
            'DELETE'
        );
        // A later target must revalidate registration rather than trusting this
        // adapter's process-local memory. The Companion may reuse a committed
        // binary runtime cache, but Begin is its authority boundary.
        this.registeredSnapshots.clear();
    }

    private async registerSnapshot(snapshot: SceneSnapshot, force = false) {
        assertSceneSnapshot(snapshot);
        const key = this.snapshotKey(snapshot);
        if (!force && this.registeredSnapshots.has(key)) {
            return;
        }
        const result = await this.requestJson(
            `/scene-snapshots/${encodeURIComponent(snapshot.sceneId)}/${encodeURIComponent(snapshot.sceneVersion)}`,
            'PUT',
            snapshot
        );
        if (
            !isRecord(result) ||
            result.status !== 'registered' ||
            result.sceneId !== snapshot.sceneId ||
            result.sceneVersion !== snapshot.sceneVersion
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not acknowledge the registered Scene Snapshot bindings.'
            );
        }
        this.registeredSnapshots.add(key);
    }

    private async registerPackedSnapshot(
        snapshot: PackedSceneSnapshot,
        force = false
    ): Promise<void> {
        if (!isPackedSceneSnapshot(snapshot)) {
            throw transportError(
                'invalidResponse',
                'AI Select requires a complete packed Scene Snapshot binding.'
            );
        }
        const key = this.snapshotKey(snapshot);
        if (!force && this.registeredSnapshots.has(key)) {
            return;
        }
        const registrar = new BinarySceneSnapshotRegistrar(
            this.binarySnapshotTransport()
        );
        let result: BinarySceneSnapshotRegistrationResult;
        try {
            result = await registrar.register(snapshot);
        } catch (error) {
            if (error instanceof SelectionServiceTransportError) {
                throw error;
            }
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not complete Binary SceneSnapshot Registration v1.'
            );
        }
        if (
            (result.status !== 'committed' &&
                result.status !== 'alreadyCommitted') ||
            result.sceneId !== snapshot.sceneId ||
            result.sceneVersion !== snapshot.sceneVersion ||
            result.contentDigest !== snapshot.contentDigest
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid packed Scene Snapshot binding.'
            );
        }
        this.registeredSnapshots.add(key);
    }

    private binarySnapshotTransport(): BinarySceneSnapshotRegistrationTransport {
        return {
            begin: (manifest) => this.beginPackedSnapshotUpload(manifest),
            uploadChunk: (uploadId, index, bytes, digest) =>
                this.uploadPackedSnapshotChunk(uploadId, index, bytes, digest),
            commit: (uploadId) => this.commitPackedSnapshotUpload(uploadId),
            abort: (uploadId) => this.abortPackedSnapshotUpload(uploadId)
        };
    }

    private async beginPackedSnapshotUpload(
        manifest: BinarySceneSnapshotManifest
    ): Promise<BinarySceneSnapshotUploadAdmission> {
        const result = await this.requestJson(
            '/scene-snapshot-uploads/v1',
            'POST',
            manifest
        );
        if (!isRecord(result) || !Array.isArray(result.missingChunkIndices)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not acknowledge the staged Binary Scene Snapshot upload.'
            );
        }
        const missingChunkIndices = result.missingChunkIndices;
        if (!missingChunkIndices.every(isNonNegativeInteger)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned invalid Binary Scene Snapshot chunk bindings.'
            );
        }
        if (result.status === 'alreadyCommitted') {
            return {
                status: 'alreadyCommitted',
                missingChunkIndices
            };
        }
        if (
            result.status !== 'staged' ||
            typeof result.uploadId !== 'string' ||
            !result.uploadId
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return a Binary Scene Snapshot upload ID.'
            );
        }
        return {
            status: 'staged',
            uploadId: result.uploadId,
            missingChunkIndices
        };
    }

    private async uploadPackedSnapshotChunk(
        uploadId: string,
        index: number,
        bytes: Uint8Array,
        digest: string
    ): Promise<void> {
        const response = await this.request(
            `/scene-snapshot-uploads/v1/${encodeURIComponent(uploadId)}/chunks/${index}`,
            'PUT',
            bytes.slice().buffer,
            {
                'Content-Type': 'application/octet-stream',
                'X-SceneSnapshot-Chunk-Digest': digest
            }
        );
        if (!response.ok) {
            throw await this.httpError(response);
        }
        let result: unknown;
        try {
            result = await response.json();
        } catch {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned invalid Binary Scene Snapshot chunk acknowledgement JSON.'
            );
        }
        if (
            !isRecord(result) ||
            (result.status !== 'stored' && result.status !== 'alreadyStored') ||
            result.uploadId !== uploadId ||
            result.index !== index
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Binary Scene Snapshot chunk acknowledgement.'
            );
        }
    }

    private async commitPackedSnapshotUpload(
        uploadId: string
    ): Promise<BinarySceneSnapshotRegistrationResult> {
        const result = await this.requestJson(
            `/scene-snapshot-uploads/v1/${encodeURIComponent(uploadId)}/commit`,
            'POST',
            {}
        );
        if (
            !isRecord(result) ||
            (result.status !== 'committed' &&
                result.status !== 'alreadyCommitted') ||
            typeof result.sceneId !== 'string' ||
            typeof result.sceneVersion !== 'string' ||
            typeof result.contentDigest !== 'string'
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Binary Scene Snapshot commit acknowledgement.'
            );
        }
        return {
            status: result.status,
            sceneId: result.sceneId,
            sceneVersion: result.sceneVersion,
            contentDigest: result.contentDigest
        };
    }

    private async abortPackedSnapshotUpload(uploadId: string): Promise<void> {
        await this.requestNoContent(
            `/scene-snapshot-uploads/v1/${encodeURIComponent(uploadId)}`,
            'DELETE'
        );
    }

    private spatialSnapshotFor(
        request: AnchorRenderRequest
    ): SpatialSceneSnapshot {
        const key = this.spatialSnapshotKey(
            request.snapshot,
            request.target.splatId
        );
        const existing = this.spatialSnapshots.get(key);
        if (existing) {
            return existing;
        }
        let spatialSnapshot: SpatialSceneSnapshot;
        try {
            spatialSnapshot = buildSpatialSceneSnapshot(request.snapshot, {
                targetSplatId: request.target.splatId
            });
        } catch {
            throw transportError(
                'invalidResponse',
                'AI Select could not construct a complete typed Spatial Scene manifest from the effective editor SceneSnapshot.'
            );
        }
        if (
            spatialSnapshot.manifest.sceneId !== request.snapshot.sceneId ||
            spatialSnapshot.manifest.sceneVersion !==
                request.snapshot.sceneVersion ||
            spatialSnapshot.manifest.contentDigest !==
                request.snapshot.contentDigest ||
            spatialSnapshot.manifest.targetSplatId !== request.target.splatId
        ) {
            throw transportError(
                'invalidResponse',
                'AI Select constructed an invalid Spatial Scene manifest binding.'
            );
        }
        this.spatialSnapshots.set(key, spatialSnapshot);
        return spatialSnapshot;
    }

    private async registerSpatialSceneManifest(
        spatialSnapshot: SpatialSceneSnapshot,
        force = false
    ): Promise<void> {
        const { manifest } = spatialSnapshot;
        const key = this.spatialSnapshotKeyFromManifest(manifest);
        if (!force && this.spatialManifestRegistrationIds.has(key)) {
            return;
        }
        const result = await this.retrySpatialTransport(() =>
            this.requestJson('/spatial-scene-manifests/v1', 'POST', manifest)
        );
        if (
            !isRecord(result) ||
            (result.status !== 'registered' &&
                result.status !== 'alreadyRegistered') ||
            typeof result.registrationId !== 'string' ||
            !result.registrationId ||
            result.sceneId !== manifest.sceneId ||
            result.sceneVersion !== manifest.sceneVersion ||
            result.contentDigest !== manifest.contentDigest
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid immutable Spatial Scene manifest registration.'
            );
        }
        const registration: SpatialSceneManifestRegistrationResponse = {
            status: result.status,
            registrationId: result.registrationId,
            sceneId: result.sceneId,
            sceneVersion: result.sceneVersion,
            contentDigest: result.contentDigest
        };
        this.spatialManifestRegistrationIds.set(
            key,
            registration.registrationId
        );
    }

    private async uploadSpatialSceneChunks(
        spatialSnapshot: SpatialSceneSnapshot,
        requestedChunkIds: readonly string[]
    ): Promise<void> {
        if (!isSortedUniqueChunkIds(requestedChunkIds, true)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned invalid Anchor Spatial Scene chunk IDs.'
            );
        }
        const descriptors = new Map<string, SpatialSceneChunkDescriptor>(
            spatialSnapshot.manifest.chunks.map((chunk) => [
                chunk.chunkId,
                chunk
            ])
        );
        if (!requestedChunkIds.every((chunkId) => descriptors.has(chunkId))) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion requested an unknown Anchor Spatial Scene chunk.'
            );
        }
        const admission = await this.beginSpatialSceneChunkUpload(
            spatialSnapshot,
            requestedChunkIds
        );
        if (admission.status === 'alreadyCommitted') {
            if (admission.missingChunkIds.length !== 0) {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion returned contradictory committed Spatial Scene chunk bindings.'
                );
            }
            return;
        }
        const uploadId = admission.uploadId;
        if (!uploadId) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return a Spatial Scene chunk upload ID.'
            );
        }
        if (
            !admission.missingChunkIds.every((chunkId) =>
                descriptors.has(chunkId)
            )
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an unknown staged Spatial Scene chunk ID.'
            );
        }
        try {
            for (const chunkId of admission.missingChunkIds) {
                const descriptor = descriptors.get(chunkId);
                if (!descriptor) {
                    throw transportError(
                        'invalidResponse',
                        'The Selection Service Companion requested an unknown staged Spatial Scene chunk.'
                    );
                }
                await this.uploadSpatialSceneChunk(
                    uploadId,
                    descriptor,
                    spatialSnapshot.readChunkPayload(chunkId)
                );
            }
            await this.commitSpatialSceneChunkUpload(
                uploadId,
                spatialSnapshot,
                requestedChunkIds
            );
        } catch (error) {
            try {
                await this.abortSpatialSceneChunkUpload(uploadId);
            } catch {
                // A failed cleanup is safe: the Companion bounds and expires
                // incomplete idempotent staging records independently.
            }
            throw error;
        }
    }

    private async beginSpatialSceneChunkUpload(
        spatialSnapshot: SpatialSceneSnapshot,
        requestedChunkIds: readonly string[]
    ): Promise<SpatialSceneChunkUploadAdmission> {
        const result = await this.retrySpatialTransport(() =>
            this.requestJson('/spatial-scene-chunk-uploads/v1', 'POST', {
                sceneId: spatialSnapshot.manifest.sceneId,
                sceneVersion: spatialSnapshot.manifest.sceneVersion,
                chunkIds: requestedChunkIds
            })
        );
        if (
            !isRecord(result) ||
            !isSortedUniqueChunkIds(result.missingChunkIds) ||
            !result.missingChunkIds.every((chunkId) =>
                requestedChunkIds.includes(chunkId)
            )
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned invalid Spatial Scene chunk upload admission bindings.'
            );
        }
        if (result.status === 'alreadyCommitted') {
            return {
                status: 'alreadyCommitted',
                missingChunkIds: result.missingChunkIds
            };
        }
        if (
            result.status !== 'staged' ||
            typeof result.uploadId !== 'string' ||
            !result.uploadId
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return a Spatial Scene chunk upload ID.'
            );
        }
        return {
            status: 'staged',
            uploadId: result.uploadId,
            missingChunkIds: result.missingChunkIds
        };
    }

    private async uploadSpatialSceneChunk(
        uploadId: string,
        descriptor: SpatialSceneChunkDescriptor,
        bytes: Uint8Array
    ): Promise<void> {
        if (bytes.byteLength !== descriptor.byteLength) {
            throw transportError(
                'invalidResponse',
                'The editor Spatial Scene chunk payload no longer matches its immutable descriptor.'
            );
        }
        await this.retrySpatialTransport(async (): Promise<void> => {
            const response = await this.request(
                `/spatial-scene-chunk-uploads/v1/${encodeURIComponent(uploadId)}/chunks/${encodeURIComponent(descriptor.chunkId)}`,
                'PUT',
                bytes.slice().buffer,
                {
                    'Content-Type': 'application/octet-stream',
                    'X-Spatial-Scene-Chunk-Digest': descriptor.chunkDigest
                }
            );
            if (!response.ok) {
                throw await this.httpError(response);
            }
            let result: unknown;
            try {
                result = await response.json();
            } catch {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion returned invalid Spatial Scene chunk acknowledgement JSON.'
                );
            }
            if (
                !isRecord(result) ||
                (result.status !== 'stored' &&
                    result.status !== 'alreadyStored') ||
                result.uploadId !== uploadId ||
                result.chunkId !== descriptor.chunkId
            ) {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion returned an invalid Spatial Scene chunk acknowledgement.'
                );
            }
        });
    }

    private async commitSpatialSceneChunkUpload(
        uploadId: string,
        spatialSnapshot: SpatialSceneSnapshot,
        requestedChunkIds: readonly string[]
    ): Promise<void> {
        const result = await this.retrySpatialTransport(() =>
            this.requestJson(
                `/spatial-scene-chunk-uploads/v1/${encodeURIComponent(uploadId)}/commit`,
                'POST',
                {}
            )
        );
        if (
            !isRecord(result) ||
            (result.status !== 'committed' &&
                result.status !== 'alreadyCommitted') ||
            result.sceneId !== spatialSnapshot.manifest.sceneId ||
            result.sceneVersion !== spatialSnapshot.manifest.sceneVersion ||
            !isSortedUniqueChunkIds(result.committedChunkIds) ||
            result.committedChunkIds.length !== requestedChunkIds.length ||
            result.committedChunkIds.some(
                (chunkId, index) => chunkId !== requestedChunkIds[index]
            )
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Spatial Scene chunk commit acknowledgement.'
            );
        }
    }

    private async abortSpatialSceneChunkUpload(
        uploadId: string
    ): Promise<void> {
        await this.requestNoContent(
            `/spatial-scene-chunk-uploads/v1/${encodeURIComponent(uploadId)}`,
            'DELETE'
        );
    }

    private async retrySpatialTransport<T>(
        operation: () => Promise<T>
    ): Promise<T> {
        try {
            return await operation();
        } catch {
            return operation();
        }
    }

    private async registerFrameSet(frameSet: ObjectSelectionFrameSet) {
        const result = await this.requestJson(
            `/frame-sets/${encodeURIComponent(frameSet.frameSetVersion)}`,
            'PUT',
            frameSet
        );
        if (
            !isRecord(result) ||
            result.status !== 'registered' ||
            result.frameSetVersion !== frameSet.frameSetVersion
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not acknowledge the registered Frame Set bindings.'
            );
        }
    }

    private async releaseFrameSet(frameSetVersion: string) {
        await this.requestNoContent(
            `/frame-sets/${encodeURIComponent(frameSetVersion)}`,
            'DELETE'
        );
    }

    private async registerAndOpenSession(
        start: ObjectSelectionServiceSessionStart,
        openRequestId: string
    ): Promise<string> {
        await this.registerFrameSet(start.requestContext.frameSet);
        const result = await this.requestJson(
            '/object-selection-sessions',
            'POST',
            {
                target: start.target,
                prompt: start.prompt,
                sceneId: start.snapshot.sceneId,
                sceneVersion: start.snapshot.sceneVersion,
                renderConfigVersion: start.snapshot.renderConfiguration.version,
                frameSetVersion: start.requestContext.frameSetVersion,
                modelManifestDigest: start.requestContext.modelManifestDigest,
                openRequestId
            }
        );
        if (
            !isRecord(result) ||
            result.status !== 'accepted' ||
            typeof result.sessionId !== 'string' ||
            !result.sessionId ||
            result.openRequestId !== openRequestId
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return the requested Object Selection session ID.'
            );
        }
        return result.sessionId;
    }

    private async cleanupOpening(
        openRequestId: string,
        frameSetVersion: string
    ) {
        try {
            await this.requestNoContent(
                `/object-selection-sessions/open-requests/${encodeURIComponent(openRequestId)}`,
                'DELETE'
            );
        } catch (cleanupError) {
            // Preserve the admission failure: this is a best-effort fallback
            // for a response the browser never received.
        }
        try {
            await this.releaseFrameSet(frameSetVersion);
        } catch (cleanupError) {
            // A closing inference can briefly retain its Frame Set lease; the
            // server-side close has already made it drain and reclaimable.
        }
    }

    private async sendPreview(
        request: ObjectSelectionPreviewRequest
    ): Promise<SelectionServicePreviewResponse | SceneCacheMissResponse> {
        this.assertConfiguredModelManifest(request.modelManifestDigest);
        const result = await this.requestJson(
            `/object-selection-sessions/${encodeURIComponent(request.sessionId)}/previews`,
            'POST',
            {
                ...previewBindingsFromRequest(request),
                target: request.target,
                promptLog: request.promptLog
            }
        );
        if (!isRecord(result)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid preview response.'
            );
        }
        if (result.status === 'sceneCacheMiss') {
            const cacheMiss = this.parseCacheMiss(result);
            this.assertPreviewBindings(cacheMiss, request, 'cache-miss');
            return cacheMiss;
        }
        if (result.status !== 'complete') {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return a complete preview response.'
            );
        }
        return this.parseCompletePreview(result, request);
    }

    private async sendAnchorRender(
        request: AnchorRenderRequest,
        sceneTransport: 'packed-v1' | 'spatial-v1' = 'packed-v1'
    ): Promise<
        | {
              readonly status: 'complete';
              readonly response: AnchorRenderResponse;
          }
        | { readonly status: 'sceneCacheMiss' }
        | {
              readonly status: 'sceneChunkMiss';
              readonly missingChunkIds: readonly string[];
          }
    > {
        const result = await this.requestJson(
            '/ai-select/anchor-renders',
            'POST',
            {
                requestBinding: request.requestBinding,
                targetSplatId: request.target.splatId,
                sceneId: request.snapshot.sceneId,
                sceneVersion: request.snapshot.sceneVersion,
                renderConfigVersion:
                    request.snapshot.renderConfiguration.version,
                renderAttemptId: request.renderAttemptId,
                viewId: 'anchor-view',
                cameraBinding: request.cameraBinding,
                ...(sceneTransport === 'spatial-v1' ? { sceneTransport } : {})
                // The production preview never sets the explicit
                // referenceContributor debug capability: complete per-pixel
                // Contributor data stays off the Anchor RGB critical path.
            }
        );
        if (!isRecord(result)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Anchor render response.'
            );
        }
        if (result.status === 'sceneCacheMiss') {
            if (!this.isMatchingAnchorCacheMiss(result, request)) {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion returned stale Anchor cache-miss bindings.'
                );
            }
            return { status: 'sceneCacheMiss' };
        }
        if (result.status === 'sceneChunkMiss') {
            if (
                sceneTransport !== 'spatial-v1' ||
                !this.isMatchingAnchorSceneChunkMiss(result, request)
            ) {
                throw transportError(
                    'invalidResponse',
                    'The Selection Service Companion returned stale or invalid Anchor Spatial Scene chunk-miss bindings.'
                );
            }
            return {
                status: 'sceneChunkMiss',
                missingChunkIds: result.missingChunkIds
            };
        }
        if (result.status !== 'complete' || !isAnchorRenderResponse(result)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an incomplete or stale Anchor render.'
            );
        }
        await this.assertAnchorRgbDigest(result, request);
        if (!anchorRenderResponseMatchesRequest(result, request)) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an incomplete or stale Anchor render.'
            );
        }
        return {
            status: 'complete',
            response: result
        };
    }

    private isMatchingAnchorCacheMiss(
        value: Record<string, unknown>,
        request: AnchorRenderRequest
    ): value is AnchorRenderCacheMissResponse {
        return (
            value.status === 'sceneCacheMiss' &&
            this.hasMatchingAnchorBindings(value, request)
        );
    }

    private isMatchingAnchorSceneChunkMiss(
        value: Record<string, unknown>,
        request: AnchorRenderRequest
    ): value is AnchorRenderSceneChunkMissResponse {
        return (
            value.status === 'sceneChunkMiss' &&
            this.hasMatchingAnchorBindings(value, request) &&
            isSha256Digest(value.workingSetToken) &&
            isSortedUniqueChunkIds(value.missingChunkIds, true)
        );
    }

    private hasMatchingAnchorBindings(
        value: Record<string, unknown>,
        request: AnchorRenderRequest
    ): boolean {
        return (
            isAIRequestBinding(value.requestBinding) &&
            value.requestBinding.targetContextId ===
                request.requestBinding.targetContextId &&
            value.requestBinding.contextRevision ===
                request.requestBinding.contextRevision &&
            areTargetDependencyTokensEqual(
                value.requestBinding.dependencyToken,
                request.requestBinding.dependencyToken
            ) &&
            value.targetSplatId === request.target.splatId &&
            value.sceneId === request.snapshot.sceneId &&
            value.sceneVersion === request.snapshot.sceneVersion &&
            value.renderConfigVersion ===
                request.snapshot.renderConfiguration.version &&
            value.renderAttemptId === request.renderAttemptId &&
            value.viewId === 'anchor-view' &&
            isCameraBinding(value.cameraBinding) &&
            areCameraBindingsEqual(value.cameraBinding, request.cameraBinding)
        );
    }

    private async assertAnchorRgbDigest(
        response: AnchorRenderResponse,
        request: AnchorRenderRequest
    ): Promise<void> {
        if (
            typeof globalThis.atob !== 'function' ||
            globalThis.crypto?.subtle === undefined
        ) {
            throw transportError(
                'browserTransport',
                'This editor context cannot verify the authoritative Anchor PNG digest.'
            );
        }
        let pngBytes: Uint8Array<ArrayBuffer>;
        try {
            pngBytes = decodePngBase64(response.rgb.pngBase64);
            const dimensions = parsePngDimensions(pngBytes);
            if (
                dimensions.width !== response.rgb.width ||
                dimensions.height !== response.rgb.height ||
                dimensions.width !== request.cameraBinding.projection.width ||
                dimensions.height !== request.cameraBinding.projection.height
            ) {
                throw new Error(
                    'Anchor PNG dimensions do not match its bound CameraBinding.'
                );
            }
        } catch (error) {
            if (
                error instanceof Error &&
                /dimensions do not match/i.test(error.message)
            ) {
                throw transportError('invalidResponse', error.message);
            }
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Anchor PNG artifact.'
            );
        }
        const digest = await globalThis.crypto.subtle.digest(
            'SHA-256',
            pngBytes
        );
        const digestBytes = [...new Uint8Array(digest)];
        const digestHex = digestBytes
            .map((byte) => byte.toString(16).padStart(2, '0'))
            .join('');
        if (response.rgb.digest.toLowerCase() !== `sha256:${digestHex}`) {
            throw transportError(
                'invalidResponse',
                'The authoritative Anchor PNG digest does not match the returned bytes.'
            );
        }
        try {
            await validatePngDecodable(pngBytes);
        } catch {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Anchor PNG artifact.'
            );
        }
    }

    private parseCacheMiss(
        value: Record<string, unknown>
    ): SceneCacheMissResponse {
        return {
            status: 'sceneCacheMiss',
            ...this.parsePreviewBindings(value, 'cache-miss')
        };
    }

    private parseCompletePreview(
        value: Record<string, unknown>,
        request: ObjectSelectionPreviewRequest
    ): SelectionServicePreviewResponse {
        if (
            !Array.isArray(value.selectedIds) ||
            !Array.isArray(value.uncertainIds) ||
            !Array.isArray(value.rejectedIds)
        ) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing required result fields.'
            );
        }
        let frameSet: ObjectSelectionFrameSet;
        let effectiveRequest: ObjectSelectionPreviewRequest;
        try {
            assertPreviewFrameSet(value.frameSet, request);
            frameSet = value.frameSet;
            effectiveRequest = requestWithFrameSet(request, frameSet);
        } catch (error) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing a complete, version-bound Frame Set.'
            );
        }
        const bindings = this.parsePreviewBindings(value, 'preview');
        this.assertPreviewBindings(bindings, effectiveRequest, 'preview');
        let evidenceSnapshot: SelectionServiceEvidenceSnapshot;
        try {
            assertEvidenceSnapshot(value.evidenceSnapshot, effectiveRequest);
            evidenceSnapshot = value.evidenceSnapshot;
        } catch (error) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing a complete, version-bound Evidence Snapshot.'
            );
        }
        let coverageReport: SelectionServiceCoverageReport;
        try {
            assertCoverageReport(value.coverageReport, effectiveRequest);
            coverageReport = value.coverageReport;
        } catch (error) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing a complete, version-bound Coverage Report.'
            );
        }
        const complete: SelectionServicePreviewResponse = {
            status: 'complete',
            ...bindings,
            selectedIds: value.selectedIds,
            uncertainIds: value.uncertainIds,
            rejectedIds: value.rejectedIds,
            frameSet,
            maskSet: this.parseMaskSet(value.maskSet, bindings),
            evidenceSnapshot,
            coverageReport
        };
        try {
            assertCompleteMaskSet(complete.maskSet, effectiveRequest);
        } catch (error) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing a complete, version-bound Mask Set.'
            );
        }
        return complete;
    }

    private parseMaskSet(
        value: unknown,
        bindings: ObjectSelectionPreviewBindings
    ): SelectionServiceMaskSet {
        if (
            !isRecord(value) ||
            value.status !== 'complete' ||
            value.requestId !== bindings.requestId ||
            value.sessionId !== bindings.sessionId ||
            value.promptLogRevision !== bindings.promptLogRevision ||
            value.frameSetVersion !== bindings.frameSetVersion ||
            value.modelManifestDigest !== bindings.modelManifestDigest ||
            !Array.isArray(value.tracks) ||
            value.tracks.length === 0
        ) {
            throw transportError(
                'invalidResponse',
                'The Companion preview response is missing a complete, version-bound Mask Set.'
            );
        }
        const threshold = value.threshold;
        if (
            typeof threshold !== 'number' ||
            !Number.isFinite(threshold) ||
            threshold < 0 ||
            threshold > 1
        ) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Mask Set threshold.'
            );
        }
        const tracks = value.tracks.map((track) => this.parseMaskTrack(track));
        return {
            status: 'complete',
            requestId: bindings.requestId,
            sessionId: bindings.sessionId,
            promptLogRevision: bindings.promptLogRevision,
            frameSetVersion: bindings.frameSetVersion,
            modelManifestDigest: bindings.modelManifestDigest,
            threshold,
            tracks
        };
    }

    private parseMaskTrack(value: unknown): SelectionServiceMaskTrack {
        if (
            !isRecord(value) ||
            typeof value.trackId !== 'string' ||
            !value.trackId ||
            (value.role !== 'include' && value.role !== 'exclude') ||
            !Array.isArray(value.frames) ||
            value.frames.length === 0
        ) {
            throw transportError(
                'invalidResponse',
                'The Companion Mask Set contains an invalid Mask Track.'
            );
        }
        return {
            trackId: value.trackId,
            role: value.role,
            frames: value.frames.map((frame) => this.parseMaskFrame(frame))
        };
    }

    private parseMaskFrame(value: unknown): SelectionServiceMaskFrame {
        if (
            !isRecord(value) ||
            typeof value.viewId !== 'string' ||
            !value.viewId ||
            !['accepted', 'not_found', 'rejected', 'error'].includes(
                String(value.status)
            )
        ) {
            throw transportError(
                'invalidResponse',
                'The Companion Mask Set contains an invalid frame outcome.'
            );
        }
        if (value.status === 'accepted' && !isRecord(value.binaryMask)) {
            throw transportError(
                'invalidResponse',
                'An accepted Companion Mask Set frame is missing its binary mask.'
            );
        }
        if (value.status !== 'accepted' && value.binaryMask !== undefined) {
            throw transportError(
                'invalidResponse',
                'A neutral Companion Mask Set frame must not encode a binary mask.'
            );
        }
        return {
            viewId: value.viewId,
            status: value.status as SelectionServiceMaskFrame['status'],
            ...(isRecord(value.binaryMask)
                ? { binaryMask: value.binaryMask }
                : {}),
            ...(typeof value.rejectionReason === 'string'
                ? { rejectionReason: value.rejectionReason }
                : {})
        };
    }

    private assertPreviewBindings(
        response: ObjectSelectionPreviewBindings,
        request: ObjectSelectionPreviewRequest,
        context: string
    ) {
        if (!previewBindingsMatch(response, request)) {
            throw transportError(
                'invalidResponse',
                `The Selection Service Companion returned stale ${context} bindings.`
            );
        }
    }

    private parsePreviewBindings(
        value: Record<string, unknown>,
        responseKind: 'cache-miss' | 'preview'
    ): ObjectSelectionPreviewBindings {
        if (
            typeof value.requestId !== 'string' ||
            typeof value.sessionId !== 'string' ||
            typeof value.targetSplatId !== 'string' ||
            typeof value.sceneId !== 'string' ||
            typeof value.sceneVersion !== 'string' ||
            !isSelectionOperation(value.operation) ||
            !isNonNegativeInteger(value.correctionRound) ||
            typeof value.deterministicSeed !== 'string' ||
            !isNonNegativeInteger(value.promptLogRevision) ||
            typeof value.frameSetVersion !== 'string' ||
            typeof value.renderConfigVersion !== 'string' ||
            typeof value.modelManifestDigest !== 'string'
        ) {
            throw transportError(
                'invalidResponse',
                `The Companion ${responseKind} response is missing complete request bindings.`
            );
        }
        return {
            requestId: value.requestId,
            sessionId: value.sessionId,
            targetSplatId: value.targetSplatId,
            sceneId: value.sceneId,
            sceneVersion: value.sceneVersion,
            operation: value.operation,
            correctionRound: value.correctionRound,
            deterministicSeed: value.deterministicSeed,
            promptLogRevision: value.promptLogRevision,
            frameSetVersion: value.frameSetVersion,
            renderConfigVersion: value.renderConfigVersion,
            modelManifestDigest: value.modelManifestDigest
        };
    }

    private async requestJson(
        path: string,
        method: 'POST' | 'PUT',
        body: unknown
    ) {
        const response = await this.request(path, method, JSON.stringify(body));
        if (!response.ok) {
            throw await this.httpError(response);
        }
        try {
            return await response.json();
        } catch (error) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned invalid JSON.'
            );
        }
    }

    private async requestNoContent(path: string, method: 'DELETE') {
        const response = await this.request(path, method);
        if (!response.ok) {
            throw await this.httpError(response);
        }
    }

    private async request(
        path: string,
        method: SelectionServiceFetchInit['method'],
        body?: string | ArrayBuffer,
        additionalHeaders: Record<string, string> = {}
    ) {
        let endpoint: URL;
        try {
            endpoint = new URL(this.getConfiguration().endpoint);
        } catch (error) {
            throw transportError(
                'browserTransport',
                'The configured Selection Service endpoint is invalid.'
            );
        }
        const url = new URL(path, endpoint).toString();
        const init: SelectionServiceFetchInit = {
            method,
            headers: {
                Accept: 'application/json',
                ...(body === undefined ||
                additionalHeaders['Content-Type'] !== undefined
                    ? {}
                    : { 'Content-Type': 'application/json' }),
                ...additionalHeaders
            },
            mode: 'cors',
            credentials: 'omit',
            cache: 'no-store',
            ...(body === undefined ? {} : { body })
        };
        try {
            return await this.fetch(url, init);
        } catch (error) {
            if (error instanceof SelectionServiceTransportError) {
                throw error;
            }
            throw transportError(
                'browserTransport',
                'The browser could not complete the Selection Service Companion request.'
            );
        }
    }

    private async httpError(response: FetchResponse) {
        let serviceMessage: string | undefined;
        try {
            const body = await response.json();
            if (isRecord(body) && typeof body.message === 'string') {
                serviceMessage = body.message;
            }
        } catch (error) {
            // A non-JSON response still has a useful HTTP status diagnostic.
        }
        return transportError(
            'http',
            `The Selection Service Companion returned HTTP ${response.status}.`,
            { status: response.status, serviceMessage }
        );
    }

    private snapshotKey(
        snapshot: Pick<SceneSnapshot, 'sceneId' | 'sceneVersion'>
    ) {
        return `${snapshot.sceneId}\u0000${snapshot.sceneVersion}`;
    }

    private spatialSnapshotKey(
        snapshot: PackedSceneSnapshot,
        targetSplatId: string
    ): string {
        return `${this.snapshotKey(snapshot)}\u0000${snapshot.contentDigest}\u0000${targetSplatId}`;
    }

    private spatialSnapshotKeyFromManifest(
        manifest: SpatialSceneManifest
    ): string {
        return `${this.snapshotKey(manifest)}\u0000${manifest.contentDigest}\u0000${manifest.targetSplatId}`;
    }

    private openRequestId() {
        this.nextOpenRequestSequence += 1;
        if (typeof globalThis.crypto?.randomUUID === 'function') {
            return `open:${globalThis.crypto.randomUUID()}`;
        }
        // Every browser supported by the editor provides Web Crypto. This
        // fallback still distinguishes logical opens in constrained test or
        // embedded contexts, while retries reuse the one value created above.
        return `open:${Date.now().toString(36)}:${this.nextOpenRequestSequence}:${Math.random().toString(36).slice(2)}`;
    }

    private assertConfiguredModelManifest(modelManifestDigest: string) {
        const configuration = this.getConfiguration();
        if (
            !modelManifestDigest ||
            configuration.modelManifestDigest === null ||
            configuration.modelManifestDigest !== modelManifestDigest
        ) {
            throw transportError(
                'invalidResponse',
                'The Object Selection request Model Manifest does not match the current Companion readiness configuration.'
            );
        }
    }
}

export { FetchSelectionServiceAdapter };

export type {
    FetchSelectionServiceAdapterOptions,
    SelectionServiceFetch,
    SelectionServiceFetchInit,
    SelectionServiceTransportConfiguration
};
