import type {
    AISelectAnchorRenderer,
    AnchorRenderRequest,
    AnchorRenderResponse
} from './ai-select/anchor-render-service';
import type { SelectionServiceAdapter } from './object-selection-session';

const selectionServiceProtocolVersion = '1';
const defaultSelectionServiceEndpoint = 'http://127.0.0.1:8787';

type SelectionServiceTransportProfile = 'loopback' | 'trustedLan';
type SelectionServiceReadinessStatus =
  'unchecked' | 'checking' | 'unavailable' | 'reachable' | 'ready';
type SelectionServiceRendererStatus = 'ready' | 'unavailable';
type SelectionServiceTransportErrorCode =
  | 'localNetworkPermissionDenied'
  | 'insecureEditorContext'
  | 'browserTransport'
  | 'invalidResponse'
  | 'http';
type SelectionServiceReadinessDiagnosticCode =
  | 'unchecked'
  | 'checking'
  | 'ready'
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
  | 'protocolMismatch'
  | 'rendererUnavailable'
  | 'rendererMismatch'
  | 'pointPromptUnsupported'
  | 'aiSelectAnchorUnsupported'
  | 'modelNotSelected'
  | 'modelUnavailable'
  | 'modelWeightsBundled'
  | 'modelAdapterMismatch'
  | 'editorOriginDenied'
  | 'capacityMismatch'
  | 'capacityBusy'
  | 'invalidCapabilities';

interface SelectionServiceConfiguration {
  endpoint: string;
  profile: SelectionServiceTransportProfile;
  editorOrigin: string;
  modelManifestDigest: string | null;
}

interface SelectionServiceReadinessRequest {
  endpoint: string;
  profile: SelectionServiceTransportProfile;
  editorOrigin: string;
}

interface SelectionServiceHealth {
  serviceBuild?: string;
}

interface SelectionServiceRendererCapability {
  id: string;
  status: SelectionServiceRendererStatus;
  cudaVersion?: string;
  message?: string;
}

interface SelectionServiceModelManifest {
  digest: string;
  adapterId: string;
  modelName: string;
  weightsBundled: boolean;
}

interface SelectionServiceCapacity {
  maximumActiveSessions: number;
  activeSessions: number;
}

interface SelectionServiceCapabilities {
  protocolVersion: string;
  serviceBuild: string;
  renderer: SelectionServiceRendererCapability;
  supportedPromptKinds: readonly string[];
  supportedOperations: readonly string[];
  modelManifests: readonly SelectionServiceModelManifest[];
  capacity: SelectionServiceCapacity;
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
  rendererId: string;
  modelAdapterId: string;
  aiSelectAnchorOperation: string;
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
  setConfiguration(configuration: SelectionServiceConfiguration): void;
  updateConfiguration(partial: Partial<SelectionServiceConfiguration>): void;
  refresh(): Promise<void>;
  requireReady(): void;
}

interface SelectionServiceTransportErrorDetails {
    status?: number;
    serviceMessage?: string;
}

class SelectionServiceTransportError extends Error {
    readonly code: SelectionServiceTransportErrorCode;
    readonly status?: number;
    readonly serviceMessage?: string;

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
    rendererId: 'gsplat',
    modelAdapterId: 'sam3.1',
    aiSelectAnchorOperation: 'aiSelectAnchorRender'
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
    serviceBuild: health.serviceBuild
});

const copyCapabilities = (
    capabilities: SelectionServiceCapabilities
): SelectionServiceCapabilities => ({
    protocolVersion: capabilities.protocolVersion,
    serviceBuild: capabilities.serviceBuild,
    renderer: {
        id: capabilities.renderer.id,
        status: capabilities.renderer.status,
        cudaVersion: capabilities.renderer.cudaVersion,
        message: capabilities.renderer.message
    },
    supportedPromptKinds: [...capabilities.supportedPromptKinds],
    supportedOperations: [...capabilities.supportedOperations],
    modelManifests: capabilities.modelManifests.map(manifest => ({
        digest: manifest.digest,
        adapterId: manifest.adapterId,
        modelName: manifest.modelName,
        weightsBundled: manifest.weightsBundled
    })),
    capacity: {
        maximumActiveSessions: capabilities.capacity.maximumActiveSessions,
        activeSessions: capabilities.capacity.activeSessions
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
    capabilities: state.capabilities ?
        copyCapabilities(state.capabilities) :
        null,
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

const isNonNegativeInteger = (value: unknown): value is number => {
    return typeof value === 'number' && Number.isInteger(value) && value >= 0;
};

const validateCapabilities = (
    value: unknown
): value is SelectionServiceCapabilities => {
    if (
        !isRecord(value) ||
    typeof value.protocolVersion !== 'string' ||
    typeof value.serviceBuild !== 'string'
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
        !Array.isArray(value.supportedPromptKinds) ||
    !value.supportedPromptKinds.every(kind => typeof kind === 'string')
    ) {
        return false;
    }
    if (
        !Array.isArray(value.supportedOperations) ||
        !value.supportedOperations.every(operation => typeof operation === 'string')
    ) {
        return false;
    }
    if (
        !Array.isArray(value.modelManifests) ||
    !value.modelManifests.every((manifest) => {
        return (
            isRecord(manifest) &&
        typeof manifest.digest === 'string' &&
        typeof manifest.adapterId === 'string' &&
        typeof manifest.modelName === 'string' &&
        typeof manifest.weightsBundled === 'boolean'
        );
    })
    ) {
        return false;
    }
    if (
        !isRecord(value.capacity) ||
    !isNonNegativeInteger(value.capacity.maximumActiveSessions) ||
    !isNonNegativeInteger(value.capacity.activeSessions)
    ) {
        return false;
    }
    return (
        Array.isArray(value.allowedEditorOrigins) &&
    value.allowedEditorOrigins.every(origin => typeof origin === 'string')
    );
};

const requestFromConfiguration = (
    configuration: SelectionServiceConfiguration
): SelectionServiceReadinessRequest => ({
    endpoint: configuration.endpoint,
    profile: configuration.profile,
    editorOrigin:
    parseEditorOrigin(configuration.editorOrigin) ?? configuration.editorOrigin
});

class SelectionServiceReadiness implements SelectionServiceReadinessInterface {
    private probe: SelectionServiceReadinessProbe;
    private requirements: SelectionServiceReadinessRequirements;
    private readinessState: SelectionServiceReadinessState;
    private listeners = new Set<SelectionServiceReadinessListener>();
    private refreshVersion = 0;

    constructor(options: {
    probe: SelectionServiceReadinessProbe;
    configuration?: SelectionServiceConfiguration;
    requirements?: Partial<SelectionServiceReadinessRequirements>;
  }) {
        this.probe = options.probe;
        this.requirements = {
            ...defaultRequirements,
            ...options.requirements
        };
        const configuration = options.configuration ?
            copyConfiguration(options.configuration) :
            defaultConfiguration(defaultEditorOrigin());
        this.readinessState = {
            status: 'unchecked',
            configuration,
            health: null,
            capabilities: null,
            diagnostic: diagnostic(
                'unchecked',
                'The Selection Service Companion has not been checked.',
                'Start the operator-managed Companion, select its endpoint and Model Manifest, then check readiness.'
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

    setConfiguration(configuration: SelectionServiceConfiguration) {
        ++this.refreshVersion;
        this.setState({
            status: 'unchecked',
            configuration: copyConfiguration(configuration),
            health: null,
            capabilities: null,
            diagnostic: diagnostic(
                'unchecked',
                'The Selection Service configuration changed.',
                'Check Companion readiness before starting Object Selection.'
            )
        });
    }

    updateConfiguration(partial: Partial<SelectionServiceConfiguration>) {
        this.setConfiguration({
            ...this.readinessState.configuration,
            ...partial
        });
    }

    async refresh() {
        const configuration = copyConfiguration(this.readinessState.configuration);
        const validationDiagnostic = validateConfiguration(configuration);
        const refreshVersion = ++this.refreshVersion;

        if (validationDiagnostic) {
            this.setState({
                status: 'unavailable',
                configuration,
                health: null,
                capabilities: null,
                diagnostic: validationDiagnostic
            });
            return;
        }

        this.setState({
            status: 'checking',
            configuration,
            health: null,
            capabilities: null,
            diagnostic: diagnostic(
                'checking',
                'Checking the configured Selection Service Companion.',
                'Keep this editor open while readiness is checked.'
            )
        });

        let health: SelectionServiceHealth;
        try {
            health = await this.probe.checkHealth(
                requestFromConfiguration(configuration)
            );
        } catch (error) {
            if (!this.isCurrentRefresh(refreshVersion)) {
                return;
            }
            this.setState({
                status: this.isReachableProbeError(error) ? 'reachable' : 'unavailable',
                configuration,
                health: null,
                capabilities: null,
                diagnostic: this.diagnosticForProbeError(error, 'health')
            });
            return;
        }

        if (!this.isCurrentRefresh(refreshVersion)) {
            return;
        }

        this.setState({
            status: 'reachable',
            configuration,
            health: copyHealth(health),
            capabilities: null,
            diagnostic: diagnostic(
                'checking',
                'The Selection Service Companion is reachable. Checking capabilities.',
                'Wait for the capability check before starting Object Selection.'
            )
        });

        let capabilities: SelectionServiceCapabilities;
        try {
            capabilities = await this.probe.getCapabilities(
                requestFromConfiguration(configuration)
            );
        } catch (error) {
            if (!this.isCurrentRefresh(refreshVersion)) {
                return;
            }
            this.setState({
                status: 'reachable',
                configuration,
                health: copyHealth(health),
                capabilities: null,
                diagnostic: this.diagnosticForProbeError(error, 'capabilities')
            });
            return;
        }

        if (!this.isCurrentRefresh(refreshVersion)) {
            return;
        }

        if (!validateCapabilities(capabilities)) {
            this.setState({
                status: 'reachable',
                configuration,
                health: copyHealth(health),
                capabilities: null,
                diagnostic: diagnostic(
                    'invalidCapabilities',
                    'The reachable Companion returned an incomplete capability response.',
                    'Use a compatible locked Companion release and refresh readiness.'
                )
            });
            return;
        }

        const capabilityDiagnostic = this.evaluateCapabilities(
            capabilities,
            configuration
        );
        this.setState({
            status: capabilityDiagnostic ? 'reachable' : 'ready',
            configuration,
            health: copyHealth(health),
            capabilities: copyCapabilities(capabilities),
            diagnostic:
        capabilityDiagnostic ??
        diagnostic(
            'ready',
            'The Selection Service Companion is ready for one new Object Selection Session.',
            'Start New to begin Object Selection.'
        )
        });
    }

    requireReady() {
        if (this.readinessState.status !== 'ready') {
            throw new SelectionServiceNotReadyError(this.readinessState.diagnostic);
        }
    }

    private evaluateCapabilities(
        capabilities: SelectionServiceCapabilities,
        configuration: SelectionServiceConfiguration
    ): SelectionServiceReadinessDiagnostic | null {
        if (capabilities.protocolVersion !== this.requirements.protocolVersion) {
            return diagnostic(
                'protocolMismatch',
                `The Companion protocol ${capabilities.protocolVersion} is incompatible with editor protocol ${this.requirements.protocolVersion}.`,
                'Stop the Companion, install the compatible locked release, start it again, then refresh readiness.'
            );
        }

        if (capabilities.renderer.status !== 'ready') {
            return diagnostic(
                'rendererUnavailable',
                capabilities.renderer.message ??
          'The Companion renderer or CUDA runtime is unavailable.',
                'Resolve the Companion renderer or CUDA diagnostic with the operator-managed installation, then refresh readiness.'
            );
        }

        if (capabilities.renderer.id !== this.requirements.rendererId) {
            return diagnostic(
                'rendererMismatch',
                `The Companion renderer ${capabilities.renderer.id} is not the required ${this.requirements.rendererId} renderer.`,
                'Start a Companion release configured with the required renderer, then refresh readiness.'
            );
        }

        if (!capabilities.supportedPromptKinds.includes('point')) {
            return diagnostic(
                'pointPromptUnsupported',
                'The Companion does not advertise the required point-prompt capability.',
                'Install a compatible promptable-mask adapter and refresh readiness.'
            );
        }

        if (
            !capabilities.supportedOperations.includes(
                this.requirements.aiSelectAnchorOperation
            )
        ) {
            return diagnostic(
                'aiSelectAnchorUnsupported',
                'The Companion does not advertise authoritative AI Select Anchor rendering.',
                'Install the compatible locked Companion release, then refresh readiness.'
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
                'Add this editor origin to the Companion CORS allowlist, restart it under operator control, then refresh readiness.'
            );
        }

        if (capabilities.capacity.maximumActiveSessions !== 1) {
            return diagnostic(
                'capacityMismatch',
                `The Companion advertises a capacity of ${capabilities.capacity.maximumActiveSessions} active sessions; this PoC requires exactly one.`,
                'Configure the Companion for one active session, then refresh readiness.'
            );
        }

        if (capabilities.capacity.activeSessions !== 0) {
            return diagnostic(
                'capacityBusy',
                'The Companion is already serving another Object Selection Session.',
                'Finish or cancel the active session in its editor, then refresh readiness. The Companion does not queue sessions.'
            );
        }

        if (configuration.modelManifestDigest === null) {
            return diagnostic(
                'modelNotSelected',
                'The Companion is reachable, but no separately installed Model Manifest is selected.',
                'Select an installed Model Manifest explicitly, then refresh readiness.'
            );
        }

        const modelManifest = capabilities.modelManifests.find(
            manifest => manifest.digest === configuration.modelManifestDigest
        );
        if (!modelManifest) {
            return diagnostic(
                'modelUnavailable',
                'The selected Model Manifest is not installed in this Companion.',
                'Install the selected model through the Companion operator workflow, then refresh readiness.'
            );
        }

        if (modelManifest.weightsBundled) {
            return diagnostic(
                'modelWeightsBundled',
                'The selected Model Manifest reports bundled weights, which this editor does not accept.',
                'Use a separately installed, manifest-verified model artifact, then refresh readiness.'
            );
        }

        if (modelManifest.adapterId !== this.requirements.modelAdapterId) {
            return diagnostic(
                'modelAdapterMismatch',
                `The selected Model Manifest uses adapter ${modelManifest.adapterId}, not ${this.requirements.modelAdapterId}.`,
                'Select a compatible separately installed Model Manifest, then refresh readiness.'
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
                        'Allow Local Network Access for this editor origin in Chromium, then refresh readiness.'
                    );
                case 'insecureEditorContext':
                    return diagnostic(
                        'insecureEditorContext',
                        'This editor origin is not a secure context for local-network access.',
                        'Serve the editor over HTTPS, or use a standards-defined loopback development origin, then refresh readiness.'
                    );
                case 'browserTransport':
                    return diagnostic(
                        'browserTransport',
                        'The browser could not complete the Companion request.',
                        'Check the endpoint, exact CORS allowlist, Local Network Access permission, and trusted-LAN certificate, then refresh readiness.'
                    );
                case 'invalidResponse':
                    return diagnostic(
                        'invalidResponse',
                        `The reachable Companion returned an invalid ${operation} response.`,
                        'Use a compatible locked Companion release and refresh readiness.'
                    );
                case 'http':
                    return diagnostic(
                        'companionRejectedRequest',
                        `The reachable Companion rejected the ${operation} check${
                            error.status === undefined ? '' : ` with HTTP ${error.status}`
                        }.`,
                        error.serviceMessage ??
                            'Resolve the Companion-reported error, then refresh readiness.'
                    );
                default:
                    break;
            }
        }

        return diagnostic(
            operation === 'health' ? 'healthUnavailable' : 'capabilitiesUnavailable',
            operation === 'health' ?
                'The configured Selection Service Companion is not reachable.' :
                'The Companion is reachable, but its capabilities could not be read.',
            operation === 'health' ?
                'Verify the operator-started Companion endpoint, then refresh readiness.' :
                'Check the Companion protocol and browser transport configuration, then refresh readiness.'
        );
    }

    private isReachableProbeError(error: unknown) {
        return (
            error instanceof SelectionServiceTransportError &&
            (error.code === 'http' || error.code === 'invalidResponse')
        );
    }

    private isCurrentRefresh(refreshVersion: number) {
        return refreshVersion === this.refreshVersion;
    }

    private setState(state: SelectionServiceReadinessState) {
        this.readinessState = copyState(state);
        const published = this.state;
        this.listeners.forEach(listener => listener(published));
    }
}

// This decorator preserves the ObjectSelectionSession seam: the session still
// knows only its injected SelectionServiceAdapter, while no New session can
// bypass the operator-visible readiness decision.
class ReadinessGatedSelectionServiceAdapter implements SelectionServiceAdapter, AISelectAnchorRenderer {
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
            throw new Error('The Selection Service Companion transport is already configured.');
        }
        this.adapter = adapter;
    }

    async openSession(
        ...args: Parameters<SelectionServiceAdapter['openSession']>
    ) {
        this.readiness.requireReady();
        return await this.requireAdapter().openSession(...args);
    }

    updatePreview(...args: Parameters<SelectionServiceAdapter['updatePreview']>) {
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

    private requireAdapter() {
        if (this.adapter === null) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return this.adapter;
    }

    private requireAnchorRenderer(): AISelectAnchorRenderer {
        const adapter = this.requireAdapter();
        if (typeof (adapter as Partial<AISelectAnchorRenderer>).renderAnchor !== 'function') {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & AISelectAnchorRenderer;
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
    SelectionServiceCapacity,
    SelectionServiceConfiguration,
    SelectionServiceHealth,
    SelectionServiceModelManifest,
    SelectionServiceReadinessDiagnostic,
    SelectionServiceReadinessDiagnosticCode,
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessListener,
    SelectionServiceReadinessProbe,
    SelectionServiceReadinessRequirements,
    SelectionServiceReadinessRequest,
    SelectionServiceReadinessState,
    SelectionServiceReadinessStatus,
    SelectionServiceRendererCapability,
    SelectionServiceRendererStatus,
    SelectionServiceTransportErrorCode,
    SelectionServiceTransportProfile
};
