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
import { areCameraBindingsEqual, isCameraBinding } from './ai-select/camera-binding';
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
import { SelectionServiceTransportError } from './selection-service-readiness';

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
  body?: string;
}

type SelectionServiceFetch = (
  url: string,
  init: SelectionServiceFetchInit
) => Promise<FetchResponse>;

interface FetchSelectionServiceAdapterOptions {
  getConfiguration: () => SelectionServiceTransportConfiguration;
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
    readonly viewId: 'anchor-view';
    readonly cameraBinding: AnchorRenderRequest['cameraBinding'];
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

class FetchSelectionServiceAdapter implements SelectionServiceAdapter, AISelectAnchorRenderer {
    private getConfiguration: () => SelectionServiceTransportConfiguration;
    private fetch: SelectionServiceFetch;
    private registeredSnapshots = new Set<string>();
    private nextOpenRequestSequence = 0;

    constructor(options: FetchSelectionServiceAdapterOptions) {
        this.getConfiguration = options.getConfiguration;
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
                sessionId = await this.registerAndOpenSession(start, openRequestId);
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

    async renderAnchor(request: AnchorRenderRequest): Promise<AnchorRenderResponse> {
        if (!isAnchorRenderRequest(request)) {
            throw transportError(
                'invalidResponse',
                'AI Select requires a complete bound Anchor render request.'
            );
        }
        assertSceneSnapshot(request.snapshot);
        if (request.requestBinding.dependencyToken.splatId !== request.target.splatId) {
            throw transportError(
                'invalidResponse',
                'AI Select Anchor request target and dependency bindings must match.'
            );
        }

        await this.registerSnapshot(request.snapshot);
        const first = await this.sendAnchorRender(request);
        if (first.status === 'complete') {
            return first.response;
        }

        await this.registerSnapshot(request.snapshot, true);
        const retry = await this.sendAnchorRender(request);
        if (retry.status !== 'complete') {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion repeated an Anchor Scene Snapshot cache miss after the editor resent the snapshot.'
            );
        }
        return retry.response;
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
        // The Companion releases scene caches with its sole session lease, so
        // a later session must re-register rather than trusting this adapter's
        // process-local memory of an old snapshot.
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

    private async cleanupOpening(openRequestId: string, frameSetVersion: string) {
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
        request: AnchorRenderRequest
    ): Promise<
        | { readonly status: 'complete'; readonly response: AnchorRenderResponse }
        | { readonly status: 'sceneCacheMiss' }
    > {
        const result = await this.requestJson('/ai-select/anchor-renders', 'POST', {
            requestBinding: request.requestBinding,
            targetSplatId: request.target.splatId,
            sceneId: request.snapshot.sceneId,
            sceneVersion: request.snapshot.sceneVersion,
            renderConfigVersion: request.snapshot.renderConfiguration.version,
            viewId: 'anchor-view',
            cameraBinding: request.cameraBinding
        });
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
            isAIRequestBinding(value.requestBinding) &&
            value.requestBinding.targetContextId === request.requestBinding.targetContextId &&
            value.requestBinding.contextRevision === request.requestBinding.contextRevision &&
            areTargetDependencyTokensEqual(
                value.requestBinding.dependencyToken,
                request.requestBinding.dependencyToken
            ) &&
            value.targetSplatId === request.target.splatId &&
            value.sceneId === request.snapshot.sceneId &&
            value.sceneVersion === request.snapshot.sceneVersion &&
            value.renderConfigVersion === request.snapshot.renderConfiguration.version &&
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
                throw new Error('Anchor PNG dimensions do not match its bound CameraBinding.');
            }
        } catch (error) {
            if (error instanceof Error && /dimensions do not match/i.test(error.message)) {
                throw transportError('invalidResponse', error.message);
            }
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion returned an invalid Anchor PNG artifact.'
            );
        }
        const digest = await globalThis.crypto.subtle.digest('SHA-256', pngBytes);
        const digestBytes = [...new Uint8Array(digest)];
        const digestHex = digestBytes.map(byte => byte.toString(16).padStart(2, '0')).join('');
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
        const tracks = value.tracks.map(track => this.parseMaskTrack(track));
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
            frames: value.frames.map(frame => this.parseMaskFrame(frame))
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
            ...(isRecord(value.binaryMask) ? { binaryMask: value.binaryMask } : {}),
            ...(typeof value.rejectionReason === 'string' ?
                { rejectionReason: value.rejectionReason } :
                {})
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
        body?: string
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
                ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
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

    private snapshotKey(snapshot: SceneSnapshot) {
        return `${snapshot.sceneId}\u0000${snapshot.sceneVersion}`;
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
