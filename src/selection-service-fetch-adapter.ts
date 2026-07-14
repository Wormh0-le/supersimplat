import {
    previewBindingsFromRequest,
    previewBindingsMatch,
    type ObjectSelectionPreviewBindings,
    type ObjectSelectionPreviewRequest,
    type ObjectSelectionServiceSessionStart,
    type SelectionServiceAdapter,
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

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null;
};

const isSelectionOperation = (
    value: unknown
): value is ObjectSelectionPreviewRequest['operation'] => {
    return value === 'New' || value === 'Add' || value === 'Remove' || value === 'Refine';
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

class FetchSelectionServiceAdapter implements SelectionServiceAdapter {
    private getConfiguration: () => SelectionServiceTransportConfiguration;
    private fetch: SelectionServiceFetch;
    private registeredSnapshots = new Set<string>();

    constructor(options: FetchSelectionServiceAdapterOptions) {
        this.getConfiguration = options.getConfiguration;
        this.fetch = options.fetch ?? browserFetch;
    }

    async openSession(start: ObjectSelectionServiceSessionStart) {
        assertSceneSnapshot(start.snapshot);
        this.assertConfiguredModelManifest(start.requestContext.modelManifestDigest);
        const result = await this.requestJson('/object-selection-sessions', 'POST', {
            target: start.target,
            prompt: start.prompt,
            sceneId: start.snapshot.sceneId,
            sceneVersion: start.snapshot.sceneVersion,
            renderConfigVersion: start.snapshot.renderConfiguration.version,
            modelManifestDigest: start.requestContext.modelManifestDigest
        });
        if (!isRecord(result) || typeof result.sessionId !== 'string' || !result.sessionId) {
            throw transportError(
                'invalidResponse',
                'The Selection Service Companion did not return an Object Selection session ID.'
            );
        }

        const sessionId = result.sessionId;
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

    private async sendPreview(request: ObjectSelectionPreviewRequest): Promise<SelectionServicePreviewResponse | SceneCacheMissResponse> {
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
        const complete = this.parseCompletePreview(result);
        this.assertPreviewBindings(complete, request, 'preview');
        return complete;
    }

    private parseCacheMiss(value: Record<string, unknown>): SceneCacheMissResponse {
        return {
            status: 'sceneCacheMiss',
            ...this.parsePreviewBindings(value, 'cache-miss')
        };
    }

    private parseCompletePreview(value: Record<string, unknown>): SelectionServicePreviewResponse {
        if (
            !Array.isArray(value.selectedIds) ||
            !Array.isArray(value.uncertainIds) ||
            !Array.isArray(value.rejectedIds)
        ) {
            throw transportError('invalidResponse', 'The Companion preview response is missing required result fields.');
        }
        return {
            status: 'complete',
            ...this.parsePreviewBindings(value, 'preview'),
            selectedIds: value.selectedIds,
            uncertainIds: value.uncertainIds,
            rejectedIds: value.rejectedIds
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

    private async requestJson(path: string, method: 'POST' | 'PUT', body: unknown) {
        const response = await this.request(path, method, JSON.stringify(body));
        if (!response.ok) {
            throw await this.httpError(response);
        }
        try {
            return await response.json();
        } catch (error) {
            throw transportError('invalidResponse', 'The Selection Service Companion returned invalid JSON.');
        }
    }

    private async requestNoContent(path: string, method: 'DELETE') {
        const response = await this.request(path, method);
        if (!response.ok) {
            throw await this.httpError(response);
        }
    }

    private async request(path: string, method: SelectionServiceFetchInit['method'], body?: string) {
        let endpoint: URL;
        try {
            endpoint = new URL(this.getConfiguration().endpoint);
        } catch (error) {
            throw transportError('browserTransport', 'The configured Selection Service endpoint is invalid.');
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
