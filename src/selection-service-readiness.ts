import type {
    AISelectAnchorRenderer,
    AnchorRenderRequest,
    AnchorRenderResponse
} from './ai-select/anchor-render-service';
import type {
    AIViewRenderRequest,
    AIViewRenderResponse,
    AISelectGeneratedViewMaskProvider,
    AISelectGeneratedViewPlanner,
    AISelectViewRenderer,
    GeneratedViewMaskRequest,
    GeneratedViewMaskResponse,
    GeneratedViewPlanRequest,
    GeneratedViewPlanResponse
} from './ai-select/generated-view-service';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse
} from './ai-select/mask-service';
import type {
    AISelectSupportProbeProvider,
    AnchorSupportProbeRequest,
    AnchorSupportProbeResponse
} from './ai-select/support-probe';
import type { SelectionServiceAdapter } from './object-selection-session';

const selectionServiceProtocolVersion = '2';
const defaultSelectionServiceEndpoint = 'http://127.0.0.1:8787';
const currentRuntimeProfileId = 'ai-select-static-image-instance/v1';
const currentImageInstanceAdapterId = 'sam3-image-instance/v1';

type SelectionServiceTransportProfile = 'loopback' | 'trustedLan';
type SelectionServiceReadinessStatus =
    'connecting' | 'available' | 'unavailable';
type SelectionServiceRendererStatus = 'ready' | 'unavailable';
type SelectionServiceImageInstanceProviderStatus = 'ready' | 'unavailable';
type SelectionServiceTransportErrorCode =
    | 'localNetworkPermissionDenied'
    | 'insecureEditorContext'
    | 'browserTransport'
    | 'invalidResponse'
    | 'http';
type SelectionServiceReadinessDiagnosticCode =
    | 'connecting'
    | 'available'
    | 'invalidEndpoint'
    | 'invalidEditorOrigin'
    | 'loopbackEndpointRequired'
    | 'trustedLanHttpsRequired'
    | 'trustedLanEndpointRequired'
    | 'healthUnavailable'
    | 'capabilitiesUnavailable'
    | 'localNetworkPermissionDenied'
    | 'insecureEditorContext'
    | 'browserTransport'
    | 'invalidResponse'
    | 'companionRejectedRequest'
    | 'companionInstanceMismatch'
    | 'protocolMismatch'
    | 'runtimeProfileMismatch'
    | 'rendererUnavailable'
    | 'rendererMismatch'
    | 'rgbResolutionUnsupported'
    | 'imageInstanceProviderUnavailable'
    | 'imageInstanceCapabilityMismatch'
    | 'aiSelectAnchorUnsupported'
    | 'maskProposalUnsupported'
    | 'binarySceneSnapshotRegistrationUnsupported'
    | 'modelUnavailable'
    | 'modelWeightsBundled'
    | 'modelAdapterMismatch'
    | 'editorOriginDenied'
    | 'invalidCapabilities';

interface SelectionServiceConfiguration {
    endpoint: string;
    profile: SelectionServiceTransportProfile;
    editorOrigin: string;
    // This identity is resolved by the Companion and copied here only so
    // task requests bind the one process-lifetime Active Model Manifest.
    modelManifestDigest: string | null;
}

interface SelectionServiceReadinessRequest {
    endpoint: string;
    profile: SelectionServiceTransportProfile;
    editorOrigin: string;
}

interface SelectionServiceHealth {
    status: 'ok';
    serviceBuild: string;
    companionInstanceId: string;
}

interface SelectionServiceRendererCapability {
    id: string;
    status: SelectionServiceRendererStatus;
    cudaVersion?: string;
    rgbRendererVersion?: string;
    message?: string;
}

interface SelectionServiceImageInstancePromptCapabilities {
    positivePoints: boolean;
    negativePoints: boolean;
    positiveInstanceBox: boolean;
    previousLogitsRefinement: boolean;
    singlePointMultimask: boolean;
    negativeBox: boolean;
    promptBrush: boolean;
    maskConstraints: boolean;
    text: boolean;
}

interface SelectionServiceAuthoritativeRgbCapabilities {
    artifact: boolean;
    companionReference: boolean;
}

interface SelectionServiceImageInstanceProviderCapability {
    status: SelectionServiceImageInstanceProviderStatus;
    adapterId: string;
    authoritativeRgb: SelectionServiceAuthoritativeRgbCapabilities;
    promptCapabilities: SelectionServiceImageInstancePromptCapabilities;
    message?: string;
}

interface SelectionServiceModelManifest {
    digest: string;
    adapterId: string;
    modelName: string;
    checkpointDigest: string;
    sourceCommit: string;
    runtimeConfigDigest: string;
    weightsBundled: boolean;
    initialized: boolean;
}

interface SelectionServiceCapabilities {
    protocolVersion: string;
    serviceBuild: string;
    companionInstanceId: string;
    runtimeProfileId: string;
    renderer: SelectionServiceRendererCapability;
    imageInstanceProvider: SelectionServiceImageInstanceProviderCapability;
    supportedOperations: readonly string[];
    activeModelManifest: SelectionServiceModelManifest;
    allowedEditorOrigins: readonly string[];
}

interface SelectionServiceReadinessProbe {
    checkHealth(
        request: SelectionServiceReadinessRequest
    ): Promise<SelectionServiceHealth>;
    getCapabilities(
        request: SelectionServiceReadinessRequest
    ): Promise<SelectionServiceCapabilities>;
}

interface SelectionServiceReadinessRequirements {
    protocolVersion: string;
    runtimeProfileId: string;
    rendererId: string;
    rgbRendererVersion: string;
    modelAdapterId: string;
    aiSelectAnchorOperation: string;
    maskProposalOperation: string;
    maskProposalSetSchemaOperation: string;
    binarySceneSnapshotRegistrationOperation: string;
}

interface SelectionServiceReadinessDiagnostic {
    code: SelectionServiceReadinessDiagnosticCode;
    message: string;
    action: string;
}

interface SelectionServiceReadinessState {
    status: SelectionServiceReadinessStatus;
    configuration: SelectionServiceConfiguration;
    health: SelectionServiceHealth | null;
    capabilities: SelectionServiceCapabilities | null;
    diagnostic: SelectionServiceReadinessDiagnostic;
}

type SelectionServiceReadinessListener = (
    state: SelectionServiceReadinessState
) => void;

interface SelectionServiceReadinessInterface {
    readonly state: SelectionServiceReadinessState;

    subscribe(listener: SelectionServiceReadinessListener): () => void;
    start(): void;
    stop(): void;
    refresh(): Promise<void>;
    recoverSameInstance(
        companionInstanceId: string,
        isBindingCurrent: () => boolean
    ): Promise<boolean>;
    requireReady(): void;
}

interface SelectionServiceReadinessClock {
    setTimeout(callback: () => void, delayMs: number): unknown;
    clearTimeout(handle: unknown): void;
}

interface SelectionServiceReadinessTransition {
    readonly previous: SelectionServiceReadinessStatus;
    readonly current: SelectionServiceReadinessStatus;
    readonly diagnosticCode: SelectionServiceReadinessDiagnosticCode;
    readonly companionInstanceId: string | null;
}

interface SelectionServiceTransportErrorDetails {
    status?: number;
    serviceMessage?: string;
    serviceCode?: string;
}

class SelectionServiceTransportError extends Error {
    readonly code: SelectionServiceTransportErrorCode;
    readonly status?: number;
    readonly serviceMessage?: string;
    readonly serviceCode?: string;

    constructor(
        code: SelectionServiceTransportErrorCode,
        message?: string,
        details: SelectionServiceTransportErrorDetails = {}
    ) {
        super(message ?? `Selection Service transport failed: ${code}.`);
        this.name = 'SelectionServiceTransportError';
        this.code = code;
        this.status = details.status;
        this.serviceMessage = details.serviceMessage;
        this.serviceCode = details.serviceCode;
    }
}

class SelectionServiceNotReadyError extends Error {
    readonly diagnostic: SelectionServiceReadinessDiagnostic;

    constructor(diagnostic: SelectionServiceReadinessDiagnostic) {
        super(
            `Object Selection cannot start: ${diagnostic.message} ${diagnostic.action}`.trim()
        );
        this.name = 'SelectionServiceNotReadyError';
        this.diagnostic = {
            code: diagnostic.code,
            message: diagnostic.message,
            action: diagnostic.action
        };
    }
}

class SelectionServiceAdapterNotConfiguredError extends Error {
    constructor() {
        super(
            'The Selection Service Companion transport is not configured yet. Configure the operator-managed Companion transport before starting Object Selection.'
        );
        this.name = 'SelectionServiceAdapterNotConfiguredError';
    }
}

const defaultConfiguration = (
    editorOrigin: string
): SelectionServiceConfiguration => ({
    endpoint: defaultSelectionServiceEndpoint,
    profile: 'loopback',
    editorOrigin,
    modelManifestDigest: null
});

const defaultRequirements: SelectionServiceReadinessRequirements = {
    protocolVersion: selectionServiceProtocolVersion,
    runtimeProfileId: currentRuntimeProfileId,
    rendererId: 'gsplat',
    rgbRendererVersion: 'gsplat-rgb/v1',
    modelAdapterId: currentImageInstanceAdapterId,
    aiSelectAnchorOperation: 'aiSelectAnchorRender',
    maskProposalOperation: 'aiSelectMaskProposals',
    maskProposalSetSchemaOperation: 'autoMaskProposalSetSchemaV2',
    binarySceneSnapshotRegistrationOperation:
        'binarySceneSnapshotRegistrationV1'
};

const defaultEditorOrigin = () => {
    if (typeof location !== 'undefined' && location.origin) {
        return location.origin;
    }
    return 'https://editor.invalid';
};

const copyConfiguration = (
    configuration: SelectionServiceConfiguration
): SelectionServiceConfiguration => ({
    endpoint: configuration.endpoint,
    profile: configuration.profile,
    editorOrigin: configuration.editorOrigin,
    modelManifestDigest: configuration.modelManifestDigest
});

const copyHealth = (
    health: SelectionServiceHealth
): SelectionServiceHealth => ({
    status: health.status,
    serviceBuild: health.serviceBuild,
    companionInstanceId: health.companionInstanceId
});

const copyCapabilities = (
    capabilities: SelectionServiceCapabilities
): SelectionServiceCapabilities => ({
    protocolVersion: capabilities.protocolVersion,
    serviceBuild: capabilities.serviceBuild,
    companionInstanceId: capabilities.companionInstanceId,
    runtimeProfileId: capabilities.runtimeProfileId,
    renderer: {
        id: capabilities.renderer.id,
        status: capabilities.renderer.status,
        cudaVersion: capabilities.renderer.cudaVersion,
        rgbRendererVersion: capabilities.renderer.rgbRendererVersion,
        message: capabilities.renderer.message
    },
    imageInstanceProvider: {
        status: capabilities.imageInstanceProvider.status,
        adapterId: capabilities.imageInstanceProvider.adapterId,
        authoritativeRgb: {
            artifact:
                capabilities.imageInstanceProvider.authoritativeRgb.artifact,
            companionReference:
                capabilities.imageInstanceProvider.authoritativeRgb
                    .companionReference
        },
        promptCapabilities: {
            ...capabilities.imageInstanceProvider.promptCapabilities
        },
        message: capabilities.imageInstanceProvider.message
    },
    supportedOperations: [...capabilities.supportedOperations],
    activeModelManifest: {
        digest: capabilities.activeModelManifest.digest,
        adapterId: capabilities.activeModelManifest.adapterId,
        modelName: capabilities.activeModelManifest.modelName,
        checkpointDigest: capabilities.activeModelManifest.checkpointDigest,
        sourceCommit: capabilities.activeModelManifest.sourceCommit,
        runtimeConfigDigest:
            capabilities.activeModelManifest.runtimeConfigDigest,
        weightsBundled: capabilities.activeModelManifest.weightsBundled,
        initialized: capabilities.activeModelManifest.initialized
    },
    allowedEditorOrigins: [...capabilities.allowedEditorOrigins]
});

const copyDiagnostic = (
    diagnostic: SelectionServiceReadinessDiagnostic
): SelectionServiceReadinessDiagnostic => ({
    code: diagnostic.code,
    message: diagnostic.message,
    action: diagnostic.action
});

const copyState = (
    state: SelectionServiceReadinessState
): SelectionServiceReadinessState => ({
    status: state.status,
    configuration: copyConfiguration(state.configuration),
    health: state.health ? copyHealth(state.health) : null,
    capabilities: state.capabilities
        ? copyCapabilities(state.capabilities)
        : null,
    diagnostic: copyDiagnostic(state.diagnostic)
});

const diagnostic = (
    code: SelectionServiceReadinessDiagnosticCode,
    message: string,
    action: string
): SelectionServiceReadinessDiagnostic => ({ code, message, action });

const isLoopbackHost = (hostname: string) => {
    const host = hostname.toLowerCase().replace(/^\[|\]$/g, '');
    return host === '127.0.0.1' || host === '::1' || host === 'localhost';
};

const parseEditorOrigin = (editorOrigin: string) => {
    try {
        const url = new URL(editorOrigin);
        if (
            (url.protocol !== 'http:' && url.protocol !== 'https:') ||
            url.origin === 'null'
        ) {
            return null;
        }
        return url.origin;
    } catch (error) {
        return null;
    }
};

const validateConfiguration = (
    configuration: SelectionServiceConfiguration
): SelectionServiceReadinessDiagnostic | null => {
    const editorOrigin = parseEditorOrigin(configuration.editorOrigin);
    if (editorOrigin === null) {
        return diagnostic(
            'invalidEditorOrigin',
            'The configured editor origin is not a valid HTTP(S) origin.',
            'Open the editor from its configured HTTP(S) origin, then refresh Companion readiness.'
        );
    }

    let endpoint: URL;
    try {
        endpoint = new URL(configuration.endpoint);
    } catch (error) {
        return diagnostic(
            'invalidEndpoint',
            'The Selection Service endpoint is not a valid URL.',
            'Enter the exact endpoint started by the operator, then refresh Companion readiness.'
        );
    }

    if (
        endpoint.username ||
        endpoint.password ||
        endpoint.search ||
        endpoint.hash ||
        endpoint.pathname !== '/'
    ) {
        return diagnostic(
            'invalidEndpoint',
            'The Selection Service endpoint must be an origin without credentials, a path, query, or fragment.',
            'Enter the Companion origin only, for example http://127.0.0.1:8787.'
        );
    }

    if (configuration.profile === 'loopback') {
        if (
            (endpoint.protocol !== 'http:' && endpoint.protocol !== 'https:') ||
            !isLoopbackHost(endpoint.hostname)
        ) {
            return diagnostic(
                'loopbackEndpointRequired',
                'The loopback profile only accepts a loopback HTTP(S) Companion endpoint.',
                'Use 127.0.0.1, localhost, or ::1, or explicitly select the trusted-LAN HTTPS profile.'
            );
        }
        return null;
    }

    if (endpoint.protocol !== 'https:') {
        return diagnostic(
            'trustedLanHttpsRequired',
            'The trusted-LAN profile requires an HTTPS Companion endpoint.',
            'Configure the Companion with a browser-trusted certificate and enter its https:// endpoint.'
        );
    }

    if (isLoopbackHost(endpoint.hostname)) {
        return diagnostic(
            'trustedLanEndpointRequired',
            'The trusted-LAN profile requires an explicitly configured LAN endpoint, not loopback.',
            'Use the operator-configured private-network HTTPS endpoint or select the loopback profile.'
        );
    }

    return null;
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === 'object' && value !== null;
};

const isNonEmptyString = (value: unknown): value is string => {
    return typeof value === 'string' && value.length > 0;
};

const validateHealth = (value: unknown): value is SelectionServiceHealth => {
    return (
        isRecord(value) &&
        value.status === 'ok' &&
        isNonEmptyString(value.serviceBuild) &&
        isNonEmptyString(value.companionInstanceId)
    );
};

const validateCapabilities = (
    value: unknown
): value is SelectionServiceCapabilities => {
    if (
        !isRecord(value) ||
        !isNonEmptyString(value.protocolVersion) ||
        !isNonEmptyString(value.serviceBuild) ||
        !isNonEmptyString(value.companionInstanceId) ||
        !isNonEmptyString(value.runtimeProfileId)
    ) {
        return false;
    }
    if (
        !isRecord(value.renderer) ||
        typeof value.renderer.id !== 'string' ||
        (value.renderer.status !== 'ready' &&
            value.renderer.status !== 'unavailable')
    ) {
        return false;
    }
    if (
        !isRecord(value.imageInstanceProvider) ||
        (value.imageInstanceProvider.status !== 'ready' &&
            value.imageInstanceProvider.status !== 'unavailable') ||
        !isNonEmptyString(value.imageInstanceProvider.adapterId) ||
        !isRecord(value.imageInstanceProvider.authoritativeRgb) ||
        typeof value.imageInstanceProvider.authoritativeRgb.artifact !==
            'boolean' ||
        typeof value.imageInstanceProvider.authoritativeRgb
            .companionReference !== 'boolean' ||
        !isRecord(value.imageInstanceProvider.promptCapabilities)
    ) {
        return false;
    }
    const promptCapabilities = value.imageInstanceProvider.promptCapabilities;
    const promptCapabilityKeys = [
        'positivePoints',
        'negativePoints',
        'positiveInstanceBox',
        'previousLogitsRefinement',
        'singlePointMultimask',
        'negativeBox',
        'promptBrush',
        'maskConstraints',
        'text'
    ];
    if (
        !promptCapabilityKeys.every(
            (key) => typeof promptCapabilities[key] === 'boolean'
        )
    ) {
        return false;
    }
    if (
        !Array.isArray(value.supportedOperations) ||
        !value.supportedOperations.every(
            (operation) => typeof operation === 'string'
        )
    ) {
        return false;
    }
    if (
        !isRecord(value.activeModelManifest) ||
        !isNonEmptyString(value.activeModelManifest.digest) ||
        !isNonEmptyString(value.activeModelManifest.adapterId) ||
        !isNonEmptyString(value.activeModelManifest.modelName) ||
        !isNonEmptyString(value.activeModelManifest.checkpointDigest) ||
        !isNonEmptyString(value.activeModelManifest.sourceCommit) ||
        !isNonEmptyString(value.activeModelManifest.runtimeConfigDigest) ||
        typeof value.activeModelManifest.weightsBundled !== 'boolean' ||
        typeof value.activeModelManifest.initialized !== 'boolean'
    ) {
        return false;
    }
    return (
        Array.isArray(value.allowedEditorOrigins) &&
        value.allowedEditorOrigins.every((origin) => typeof origin === 'string')
    );
};

const requestFromConfiguration = (
    configuration: SelectionServiceConfiguration
): SelectionServiceReadinessRequest => ({
    endpoint: configuration.endpoint,
    profile: configuration.profile,
    editorOrigin:
        parseEditorOrigin(configuration.editorOrigin) ??
        configuration.editorOrigin
});

const browserReadinessClock: SelectionServiceReadinessClock = {
    setTimeout: (callback, delayMs) => globalThis.setTimeout(callback, delayMs),
    clearTimeout: (handle) =>
        globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>)
};

class SelectionServiceReadiness implements SelectionServiceReadinessInterface {
    private readonly probe: SelectionServiceReadinessProbe;
    private readonly requirements: SelectionServiceReadinessRequirements;
    private readonly clock: SelectionServiceReadinessClock;
    private readonly heartbeatIntervalMs: number;
    private readonly retryInitialMs: number;
    private readonly retryMaximumMs: number;
    private readonly isForeground: () => boolean;
    private readonly logTransition: (
        transition: SelectionServiceReadinessTransition
    ) => void;
    private readonly onCompanionInstanceChanged: (
        previousInstanceId: string,
        currentInstanceId: string
    ) => void;
    private readinessState: SelectionServiceReadinessState;
    private readonly listeners = new Set<SelectionServiceReadinessListener>();
    private running = false;
    private generation = 0;
    private failureCount = 0;
    private scheduledCheck: unknown | null = null;
    private inFlight: Promise<boolean> | null = null;

    constructor(options: {
        probe: SelectionServiceReadinessProbe;
        configuration?: SelectionServiceConfiguration;
        requirements?: Partial<SelectionServiceReadinessRequirements>;
        clock?: SelectionServiceReadinessClock;
        heartbeatIntervalMs?: number;
        retryInitialMs?: number;
        retryMaximumMs?: number;
        isForeground?: () => boolean;
        logTransition?: (
            transition: SelectionServiceReadinessTransition
        ) => void;
        onCompanionInstanceChanged?: (
            previousInstanceId: string,
            currentInstanceId: string
        ) => void;
    }) {
        this.probe = options.probe;
        this.requirements = {
            ...defaultRequirements,
            ...options.requirements
        };
        this.clock = options.clock ?? browserReadinessClock;
        this.heartbeatIntervalMs = options.heartbeatIntervalMs ?? 10_000;
        this.retryInitialMs = options.retryInitialMs ?? 1_000;
        this.retryMaximumMs = options.retryMaximumMs ?? 30_000;
        this.isForeground =
            options.isForeground ??
            (() =>
                typeof document === 'undefined' ||
                document.visibilityState === 'visible');
        this.logTransition =
            options.logTransition ??
            ((transition) => {
                console.info('AI Select availability transition', transition);
            });
        this.onCompanionInstanceChanged =
            options.onCompanionInstanceChanged ?? (() => {});
        const configuration = options.configuration
            ? copyConfiguration(options.configuration)
            : defaultConfiguration(defaultEditorOrigin());
        this.readinessState = {
            status: 'connecting',
            configuration: {
                ...configuration,
                modelManifestDigest: null
            },
            health: null,
            capabilities: null,
            diagnostic: diagnostic(
                'connecting',
                'AI Select is connecting to the Selection Service Companion.',
                'Native SuperSplat tools remain available.'
            )
        };
    }

    get state() {
        return copyState(this.readinessState);
    }

    subscribe(listener: SelectionServiceReadinessListener) {
        this.listeners.add(listener);
        listener(this.state);

        return () => {
            this.listeners.delete(listener);
        };
    }

    start() {
        if (this.running) {
            return;
        }
        this.running = true;
        this.runCheck('full').catch((error) => console.error(error));
    }

    stop() {
        this.running = false;
        ++this.generation;
        this.clearScheduledCheck();
    }

    async refresh() {
        await this.runCheck('full');
    }

    async recoverSameInstance(
        companionInstanceId: string,
        isBindingCurrent: () => boolean
    ) {
        if (
            !isBindingCurrent() ||
            this.readinessState.health?.companionInstanceId !==
                companionInstanceId
        ) {
            return false;
        }
        if (this.inFlight) {
            await this.inFlight;
        }
        if (
            !isBindingCurrent() ||
            this.readinessState.health?.companionInstanceId !==
                companionInstanceId
        ) {
            return false;
        }
        const recovered = await this.runCheck('full', companionInstanceId);
        return (
            recovered &&
            isBindingCurrent() &&
            this.readinessState.status === 'available' &&
            this.readinessState.health?.companionInstanceId ===
                companionInstanceId
        );
    }

    requireReady() {
        if (this.readinessState.status !== 'available') {
            throw new SelectionServiceNotReadyError(
                this.readinessState.diagnostic
            );
        }
    }

    private runCheck(
        mode: 'heartbeat' | 'full',
        expectedInstanceId?: string
    ): Promise<boolean> {
        if (this.inFlight) {
            return this.inFlight;
        }
        this.clearScheduledCheck();
        const generation = ++this.generation;
        const check = this.performCheck(
            mode,
            generation,
            expectedInstanceId
        ).finally(() => {
            if (this.inFlight === check) {
                this.inFlight = null;
            }
            if (this.running && generation === this.generation) {
                this.scheduleNextCheck();
            }
        });
        this.inFlight = check;
        return check;
    }

    private async performCheck(
        mode: 'heartbeat' | 'full',
        generation: number,
        expectedInstanceId?: string
    ): Promise<boolean> {
        const configuration = copyConfiguration(
            this.readinessState.configuration
        );
        const validationDiagnostic = validateConfiguration(configuration);
        if (validationDiagnostic) {
            this.failureCount += 1;
            this.publish({
                ...this.readinessState,
                status: 'unavailable',
                diagnostic: validationDiagnostic
            });
            return false;
        }

        if (mode === 'full') {
            this.publish({
                ...this.readinessState,
                status: 'connecting',
                diagnostic: diagnostic(
                    'connecting',
                    'AI Select is validating the Selection Service Companion.',
                    'Native SuperSplat tools remain available.'
                )
            });
        }

        let health: SelectionServiceHealth;
        try {
            health = await this.probe.checkHealth(
                requestFromConfiguration(configuration)
            );
        } catch (error) {
            if (!this.isCurrent(generation)) {
                return false;
            }
            this.failureCount += 1;
            this.publishUnavailable(
                this.diagnosticForProbeError(error, 'health')
            );
            return false;
        }

        if (!this.isCurrent(generation)) {
            return false;
        }
        if (!validateHealth(health)) {
            this.failureCount += 1;
            this.publishUnavailable(
                diagnostic(
                    'invalidResponse',
                    'The Companion returned an invalid lightweight health response.',
                    'Use a compatible locked Companion release.'
                )
            );
            return false;
        }

        const previousInstanceId =
            this.readinessState.health?.companionInstanceId ?? null;
        const instanceChanged =
            previousInstanceId !== null &&
            previousInstanceId !== health.companionInstanceId;
        if (instanceChanged) {
            this.onCompanionInstanceChanged(
                previousInstanceId,
                health.companionInstanceId
            );
        }
        if (
            expectedInstanceId !== undefined &&
            health.companionInstanceId !== expectedInstanceId
        ) {
            this.failureCount += 1;
            this.publish({
                status: 'unavailable',
                configuration: {
                    ...configuration,
                    modelManifestDigest: null
                },
                health: copyHealth(health),
                capabilities: null,
                diagnostic: diagnostic(
                    'companionInstanceMismatch',
                    'The Companion process changed during connection recovery.',
                    'Retry the task from current AI Select state.'
                )
            });
            return false;
        }

        if (
            mode === 'heartbeat' &&
            !instanceChanged &&
            this.readinessState.status === 'available' &&
            this.readinessState.capabilities?.companionInstanceId ===
                health.companionInstanceId
        ) {
            this.failureCount = 0;
            this.publish({
                ...this.readinessState,
                health: copyHealth(health)
            });
            return true;
        }

        this.publish({
            ...this.readinessState,
            status: 'connecting',
            configuration: {
                ...configuration,
                modelManifestDigest: null
            },
            health: copyHealth(health),
            capabilities: null,
            diagnostic: diagnostic(
                'connecting',
                'AI Select is validating Companion compatibility.',
                'Native SuperSplat tools remain available.'
            )
        });

        let capabilities: SelectionServiceCapabilities;
        try {
            capabilities = await this.probe.getCapabilities(
                requestFromConfiguration(configuration)
            );
        } catch (error) {
            if (!this.isCurrent(generation)) {
                return false;
            }
            this.failureCount += 1;
            this.publishUnavailable(
                this.diagnosticForProbeError(error, 'capabilities'),
                health
            );
            return false;
        }

        if (!this.isCurrent(generation)) {
            return false;
        }
        if (!validateCapabilities(capabilities)) {
            this.failureCount += 1;
            this.publishUnavailable(
                diagnostic(
                    'invalidCapabilities',
                    'The Companion returned an incomplete Runtime Profile response.',
                    'Use a compatible locked Companion release.'
                ),
                health
            );
            return false;
        }
        if (capabilities.companionInstanceId !== health.companionInstanceId) {
            this.failureCount += 1;
            this.publishUnavailable(
                diagnostic(
                    'companionInstanceMismatch',
                    'Health and compatibility responses came from different Companion processes.',
                    'Wait for automatic reconnection.'
                ),
                health
            );
            return false;
        }

        const capabilityDiagnostic = this.evaluateCapabilities(
            capabilities,
            configuration
        );
        const activeModelManifest = capabilities.activeModelManifest;
        this.publish({
            status: capabilityDiagnostic ? 'unavailable' : 'available',
            configuration: {
                ...configuration,
                modelManifestDigest: activeModelManifest.digest
            },
            health: copyHealth(health),
            capabilities: copyCapabilities(capabilities),
            diagnostic:
                capabilityDiagnostic ??
                diagnostic('available', 'AI Select is available.', '')
        });
        if (capabilityDiagnostic) {
            this.failureCount += 1;
            return false;
        }
        this.failureCount = 0;
        return true;
    }

    private evaluateCapabilities(
        capabilities: SelectionServiceCapabilities,
        configuration: SelectionServiceConfiguration
    ): SelectionServiceReadinessDiagnostic | null {
        if (
            capabilities.protocolVersion !== this.requirements.protocolVersion
        ) {
            return diagnostic(
                'protocolMismatch',
                'The Companion protocol is incompatible with this editor.',
                'Use the locked compatible Companion release.'
            );
        }
        if (
            capabilities.runtimeProfileId !== this.requirements.runtimeProfileId
        ) {
            return diagnostic(
                'runtimeProfileMismatch',
                'The Companion does not implement the current AI Select Runtime Profile.',
                'Use the current static-image Companion profile.'
            );
        }
        if (capabilities.renderer.status !== 'ready') {
            return diagnostic(
                'rendererUnavailable',
                capabilities.renderer.message ??
                    'The Companion renderer is unavailable.',
                'Resolve the operator-side renderer/runtime diagnostic.'
            );
        }
        if (
            capabilities.renderer.id !== this.requirements.rendererId ||
            capabilities.renderer.rgbRendererVersion !==
                this.requirements.rgbRendererVersion
        ) {
            return diagnostic(
                'rendererMismatch',
                'The Companion authoritative renderer identity is incompatible.',
                'Use the locked compatible Companion release.'
            );
        }

        const modelManifest = capabilities.activeModelManifest;
        if (!modelManifest.initialized) {
            return diagnostic(
                'modelUnavailable',
                'The Active Model Manifest is not initialized.',
                'Resolve the operator-side model diagnostic.'
            );
        }
        if (modelManifest.weightsBundled) {
            return diagnostic(
                'modelWeightsBundled',
                'The Active Model Manifest reports bundled model weights.',
                'Use a separately installed, manifest-verified model artifact.'
            );
        }
        if (modelManifest.adapterId !== this.requirements.modelAdapterId) {
            return diagnostic(
                'modelAdapterMismatch',
                'The Active Model Manifest is not the current SAM 3 Image instance adapter.',
                'Install and activate the current SAM 3 Image Model Manifest.'
            );
        }

        const provider = capabilities.imageInstanceProvider;
        if (
            provider.status !== 'ready' ||
            provider.adapterId !== modelManifest.adapterId
        ) {
            return diagnostic(
                'imageInstanceProviderUnavailable',
                provider.message ??
                    'The current SAM 3 Image provider is unavailable.',
                'Resolve the operator-side model/provider diagnostic.'
            );
        }
        if (
            !provider.authoritativeRgb.artifact &&
            !provider.authoritativeRgb.companionReference
        ) {
            return diagnostic(
                'rgbResolutionUnsupported',
                'The image provider cannot resolve authoritative RGB input.',
                'Use a provider with exact RGB artifact or Companion-reference resolution.'
            );
        }
        const prompts = provider.promptCapabilities;
        if (
            !prompts.positivePoints ||
            !prompts.negativePoints ||
            !prompts.positiveInstanceBox ||
            !prompts.previousLogitsRefinement ||
            !prompts.singlePointMultimask ||
            prompts.negativeBox ||
            prompts.promptBrush ||
            prompts.maskConstraints ||
            prompts.text
        ) {
            return diagnostic(
                'imageInstanceCapabilityMismatch',
                'The image provider Prompt/refinement capabilities do not match the current profile.',
                'Use the current SAM 3 Image instance adapter.'
            );
        }

        if (
            !capabilities.supportedOperations.includes(
                this.requirements.aiSelectAnchorOperation
            )
        ) {
            return diagnostic(
                'aiSelectAnchorUnsupported',
                'Authoritative AI Select Anchor rendering is unavailable.',
                'Use the compatible locked Companion release.'
            );
        }
        if (
            !capabilities.supportedOperations.includes(
                this.requirements.maskProposalOperation
            ) ||
            !capabilities.supportedOperations.includes(
                this.requirements.maskProposalSetSchemaOperation
            )
        ) {
            return diagnostic(
                'maskProposalUnsupported',
                'Current image-instance Mask production is unavailable.',
                'Use the compatible locked Companion release.'
            );
        }
        if (
            !capabilities.supportedOperations.includes(
                this.requirements.binarySceneSnapshotRegistrationOperation
            )
        ) {
            return diagnostic(
                'binarySceneSnapshotRegistrationUnsupported',
                'Binary SceneSnapshot Registration v1 is unavailable.',
                'Use the compatible locked Companion release.'
            );
        }

        const editorOrigin = parseEditorOrigin(configuration.editorOrigin);
        if (
            editorOrigin === null ||
            !capabilities.allowedEditorOrigins.includes(editorOrigin)
        ) {
            return diagnostic(
                'editorOriginDenied',
                'The Companion does not allow this exact editor origin.',
                'Update the operator-owned Companion origin allowlist.'
            );
        }
        return null;
    }

    private diagnosticForProbeError(
        error: unknown,
        operation: 'health' | 'capabilities'
    ): SelectionServiceReadinessDiagnostic {
        if (error instanceof SelectionServiceTransportError) {
            switch (error.code) {
                case 'localNetworkPermissionDenied':
                    return diagnostic(
                        'localNetworkPermissionDenied',
                        'The browser denied local-network access to the Companion.',
                        'Allow Local Network Access for this editor origin.'
                    );
                case 'insecureEditorContext':
                    return diagnostic(
                        'insecureEditorContext',
                        'This editor origin cannot securely access the Companion.',
                        'Use a secure editor deployment.'
                    );
                case 'browserTransport':
                    return diagnostic(
                        'browserTransport',
                        'The browser could not reach the Companion.',
                        'Automatic reconnection will continue.'
                    );
                case 'invalidResponse':
                    return diagnostic(
                        'invalidResponse',
                        `The Companion returned an invalid ${operation} response.`,
                        'Use a compatible locked Companion release.'
                    );
                case 'http':
                    return diagnostic(
                        'companionRejectedRequest',
                        `The Companion rejected the ${operation} check.`,
                        error.serviceMessage ??
                            'Resolve the operator-side Companion diagnostic.'
                    );
                default:
                    break;
            }
        }
        return diagnostic(
            operation === 'health'
                ? 'healthUnavailable'
                : 'capabilitiesUnavailable',
            operation === 'health'
                ? 'The Companion is not reachable.'
                : 'The Companion Runtime Profile could not be read.',
            'Automatic reconnection will continue.'
        );
    }

    private publishUnavailable(
        readinessDiagnostic: SelectionServiceReadinessDiagnostic,
        health: SelectionServiceHealth | null = this.readinessState.health
    ) {
        this.publish({
            ...this.readinessState,
            status: 'unavailable',
            health: health ? copyHealth(health) : null,
            diagnostic: readinessDiagnostic
        });
    }

    private publish(state: SelectionServiceReadinessState) {
        const previous = this.readinessState.status;
        this.readinessState = copyState(state);
        if (previous !== state.status) {
            this.logTransition({
                previous,
                current: state.status,
                diagnosticCode: state.diagnostic.code,
                companionInstanceId: state.health?.companionInstanceId ?? null
            });
        }
        const published = this.state;
        this.listeners.forEach((listener) => listener(published));
    }

    private isCurrent(generation: number) {
        return generation === this.generation;
    }

    private scheduleNextCheck() {
        const delay =
            this.readinessState.status === 'available'
                ? this.heartbeatIntervalMs
                : Math.min(
                      this.retryInitialMs *
                          2 ** Math.max(0, this.failureCount - 1),
                      this.retryMaximumMs
                  );
        this.scheduledCheck = this.clock.setTimeout(() => {
            this.scheduledCheck = null;
            if (!this.running) {
                return;
            }
            if (!this.isForeground()) {
                this.scheduleNextCheck();
                return;
            }
            this.runCheck(
                this.readinessState.status === 'available'
                    ? 'heartbeat'
                    : 'full'
            ).catch((error) => console.error(error));
        }, delay);
    }

    private clearScheduledCheck() {
        if (this.scheduledCheck === null) {
            return;
        }
        this.clock.clearTimeout(this.scheduledCheck);
        this.scheduledCheck = null;
    }
}

// This decorator preserves the ObjectSelectionSession seam: the session still
// knows only its injected SelectionServiceAdapter, while no New session can
// bypass the operator-visible readiness decision.
class ReadinessGatedSelectionServiceAdapter
    implements
        SelectionServiceAdapter,
        AISelectAnchorRenderer,
        AISelectMaskProvider,
        AISelectSupportProbeProvider,
        AISelectGeneratedViewPlanner,
        AISelectViewRenderer,
        AISelectGeneratedViewMaskProvider
{
    private readiness: SelectionServiceReadinessInterface;
    private adapter: SelectionServiceAdapter | null;

    constructor(options: {
        readiness: SelectionServiceReadinessInterface;
        adapter?: SelectionServiceAdapter;
    }) {
        this.readiness = options.readiness;
        this.adapter = options.adapter ?? null;
    }

    setAdapter(adapter: SelectionServiceAdapter) {
        if (this.adapter !== null) {
            throw new Error(
                'The Selection Service Companion transport is already configured.'
            );
        }
        this.adapter = adapter;
    }

    async openSession(
        ...args: Parameters<SelectionServiceAdapter['openSession']>
    ) {
        this.readiness.requireReady();
        return await this.requireAdapter().openSession(...args);
    }

    updatePreview(
        ...args: Parameters<SelectionServiceAdapter['updatePreview']>
    ) {
        return this.requireAdapter().updatePreview(...args);
    }

    cancelUpdate(...args: Parameters<SelectionServiceAdapter['cancelUpdate']>) {
        return this.requireAdapter().cancelUpdate(...args);
    }

    closeSession(...args: Parameters<SelectionServiceAdapter['closeSession']>) {
        return this.requireAdapter().closeSession(...args);
    }

    async renderAnchor(
        request: AnchorRenderRequest
    ): Promise<AnchorRenderResponse> {
        this.readiness.requireReady();
        return await this.requireAnchorRenderer().renderAnchor(request);
    }

    async produceMaskProposals(
        request: AIViewMaskRequest
    ): Promise<MaskResultResponse> {
        this.readiness.requireReady();
        return await this.requireMaskProvider().produceMaskProposals(request);
    }

    async probeAnchorSupport(
        request: AnchorSupportProbeRequest
    ): Promise<AnchorSupportProbeResponse> {
        this.readiness.requireReady();
        return await this.requireSupportProbeProvider().probeAnchorSupport(
            request
        );
    }

    async planGeneratedViews(
        request: GeneratedViewPlanRequest
    ): Promise<GeneratedViewPlanResponse> {
        this.readiness.requireReady();
        return await this.requireGeneratedViewPlanner().planGeneratedViews(
            request
        );
    }

    async renderView(
        request: AIViewRenderRequest
    ): Promise<AIViewRenderResponse> {
        this.readiness.requireReady();
        return await this.requireViewRenderer().renderView(request);
    }

    async produceGeneratedViewMask(
        request: GeneratedViewMaskRequest
    ): Promise<GeneratedViewMaskResponse> {
        this.readiness.requireReady();
        return await this.requireGeneratedViewMaskProvider().produceGeneratedViewMask(
            request
        );
    }

    private requireAdapter() {
        if (this.adapter === null) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return this.adapter;
    }

    private requireAnchorRenderer(): AISelectAnchorRenderer {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectAnchorRenderer>).renderAnchor !==
            'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & AISelectAnchorRenderer;
    }

    private requireMaskProvider(): AISelectMaskProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectMaskProvider>)
                .produceMaskProposals !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & AISelectMaskProvider;
    }

    private requireSupportProbeProvider(): AISelectSupportProbeProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectSupportProbeProvider>)
                .probeAnchorSupport !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectSupportProbeProvider;
    }

    private requireGeneratedViewPlanner(): AISelectGeneratedViewPlanner {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectGeneratedViewPlanner>)
                .planGeneratedViews !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectGeneratedViewPlanner;
    }

    private requireViewRenderer(): AISelectViewRenderer {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectViewRenderer>).renderView !==
            'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & AISelectViewRenderer;
    }

    private requireGeneratedViewMaskProvider(): AISelectGeneratedViewMaskProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectGeneratedViewMaskProvider>)
                .produceGeneratedViewMask !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectGeneratedViewMaskProvider;
    }
}

export {
    ReadinessGatedSelectionServiceAdapter,
    SelectionServiceAdapterNotConfiguredError,
    SelectionServiceNotReadyError,
    SelectionServiceReadiness,
    SelectionServiceTransportError,
    defaultSelectionServiceEndpoint,
    selectionServiceProtocolVersion
};

export type {
    SelectionServiceCapabilities,
    SelectionServiceConfiguration,
    SelectionServiceHealth,
    SelectionServiceImageInstancePromptCapabilities,
    SelectionServiceImageInstanceProviderCapability,
    SelectionServiceModelManifest,
    SelectionServiceReadinessClock,
    SelectionServiceReadinessDiagnostic,
    SelectionServiceReadinessDiagnosticCode,
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessListener,
    SelectionServiceReadinessProbe,
    SelectionServiceReadinessRequirements,
    SelectionServiceReadinessRequest,
    SelectionServiceReadinessState,
    SelectionServiceReadinessStatus,
    SelectionServiceReadinessTransition,
    SelectionServiceRendererCapability,
    SelectionServiceRendererStatus,
    SelectionServiceTransportErrorCode,
    SelectionServiceTransportProfile
};
