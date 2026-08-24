import {
    aiSelectRasterImplementationId,
    aiSelectRuntimeBuildId,
    aiSelectRgbRendererVersion,
    type AISelectAnchorRenderer,
    type AnchorRenderRequest,
    type AnchorRenderResponse
} from './ai-select/anchor-render-service';
import {
    productionAggregationPolicyDigest,
    productionDirectEvidenceBackendId,
    productionEvidencePolicyDigest,
    productionEvidenceRasterImplementationId,
    productionEvidenceRuntimeBuildId,
    type AISelectCandidateReLiftProvider,
    type CandidateReLiftRequest,
    type CandidateReLiftResponse
} from './ai-select/candidate-re-lift';
import type {
    AISelectDirectEvidenceProvider,
    DirectEvidenceRequest,
    DirectEvidenceResponse
} from './ai-select/direct-evidence-service';
import {
    aiSelectImageInstancePromptSynthesisPolicyDigest,
    aiSelectImageInstancePromptSynthesisPolicyVersion,
    type AIViewRenderRequest,
    type AIViewRenderResponse,
    type AISelectGeneratedViewPromptSynthesizer,
    type AISelectImageInstanceMaskReviewProvider,
    type AISelectViewRenderer,
    type GeneratedViewPromptSynthesisRequest,
    type GeneratedViewPromptSynthesisResponse,
    type ImageInstanceMaskReviewRequest,
    type ImageInstanceMaskReviewResponse
} from './ai-select/generated-view-service';
import type {
    ImageInstanceMaskProvider,
    ImageInstanceMaskRequest,
    ImageInstanceMaskResult
} from './ai-select/image-instance-mask';
import { defaultLiftReadinessPolicy } from './ai-select/lift-readiness';
import {
    aiSelectLocalKeyViewPlannerVersion,
    aiSelectLocalKeyViewPolicyDigest,
    type AISelectLocalKeyViewPlanner,
    type LocalKeyViewPlanRequest,
    type LocalKeyViewPlanResponse
} from './ai-select/local-key-view-plan';
import type {
    AISelectMaskProvider,
    AIViewMaskRequest,
    MaskResultResponse
} from './ai-select/mask-service';
import { createPromptAdapterCapabilities } from './ai-select/prompt-state';
import type {
    AISelectSupportProbeProvider,
    AnchorSupportProbeRequest,
    AnchorSupportProbeResponse
} from './ai-select/support-probe';
import {
    aiSelectTargetGeometryPolicyDigest,
    aiSelectTargetGeometryPolicyVersion,
    type AISelectTargetGeometryProvider,
    type TargetGeometryHintRequest,
    type TargetGeometryHintResponse
} from './ai-select/target-geometry-hint';
import {
    aiSelectViewAssessmentPolicyDigest,
    aiSelectViewAssessmentPolicyVersion
} from './ai-select/view-assessment';
import { sha256Digest } from './scene-snapshot-binary';

const selectionServiceProtocolVersion = '2';
const defaultSelectionServiceEndpoint = 'http://127.0.0.1:8787';
const currentRuntimeProfileId = 'ai-select-static-image-instance/v1';
const currentImageInstanceAdapterId = 'sam3-image-instance/v1';
const currentPromptCompilerPolicyVersion = 'sam3-image-instance-compiler/v1';

type SelectionServiceTransportProfile = 'loopback' | 'trustedLan';
type SelectionServiceReadinessStatus =
    'connecting' | 'available' | 'unavailable';
type SelectionServiceRendererStatus = 'ready' | 'unavailable';
type SelectionServiceImageInstanceProviderStatus = 'ready' | 'unavailable';
interface SelectionServiceAdapter
    extends
        Omit<AISelectAnchorRenderer, 'releaseSceneSnapshot'>,
        AISelectMaskProvider,
        AISelectSupportProbeProvider,
        AISelectTargetGeometryProvider,
        AISelectLocalKeyViewPlanner,
        Omit<AISelectViewRenderer, 'releaseSceneSnapshot'>,
        AISelectGeneratedViewPromptSynthesizer,
        ImageInstanceMaskProvider,
        AISelectImageInstanceMaskReviewProvider,
        AISelectCandidateReLiftProvider,
        AISelectDirectEvidenceProvider {
    releaseSceneSnapshot?(
        request: AnchorRenderRequest | AIViewRenderRequest
    ): Promise<void>;
}
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
    | 'candidateReLiftUnsupported'
    | 'directEvidenceUnsupported'
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
    rasterImplementationId?: string;
    runtimeBuildId?: string;
    message?: string;
}

interface SelectionServiceImageInstancePromptCapabilities {
    positivePoints: boolean;
    negativePoints: boolean;
    positiveInstanceBox: boolean;
    previousLogitsRefinement: boolean;
    singlePointMultimask: boolean;
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
    /** Present only when the provider reports ready (04C contract §3). */
    compilerPolicyVersion?: string;
    adapterCapabilityDigest?: string;
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
    directEvidence: SelectionServiceDirectEvidenceCapability;
    productionCandidateReLift: SelectionServiceProductionCandidateReLiftCapability;
    productionIdentity: SelectionServiceProductionIdentityCapability;
    supportedOperations: readonly string[];
    activeModelManifest: SelectionServiceModelManifest;
    allowedEditorOrigins: readonly string[];
}

interface SelectionServiceDirectEvidenceCapability {
    readonly status: 'ready' | 'unavailable';
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: 'production-direct';
    readonly evidenceBackendId: string;
    readonly sourceRevision: string;
    readonly expectedSourceRevision: string;
    readonly abiVersion: string;
    readonly runtimeBuildId: string;
    readonly torchVersion: string;
    readonly cudaVersion: string;
    readonly gsplatSourceCommit: string;
    readonly supportedComputeCapabilities: readonly string[];
    readonly accumulation: 'global-atomic-baseline';
    readonly buildFlags: readonly string[];
    readonly detectedComputeCapability?: string;
}

interface SelectionServiceProductionCandidateReLiftCapability {
    readonly status: 'ready' | 'unavailable';
    readonly evidencePolicyDigest: string;
    readonly aggregationPolicyDigest: string;
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: 'production-direct';
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
}

interface SelectionServiceProductionIdentityRecord {
    readonly schemaVersion: 1;
    readonly renderer: Readonly<{
        rgbRendererVersion: string;
        rasterImplementationId: string;
        runtimeBuildId: string;
    }>;
    readonly model: Readonly<{
        adapterId: string;
        manifestId: string;
        manifestRecordDigest: string;
        checkpointDigest: string;
        runtimeConfigDigest: string;
    }>;
    readonly prompt: Readonly<{
        compilerPolicyVersion: string;
        adapterCapabilityDigest: string;
        synthesisPolicyVersion: string;
        synthesisPolicyDigest: string;
    }>;
    readonly geometry: Readonly<{
        targetGeometryPolicyVersion: string;
        targetGeometryPolicyDigest: string;
        localViewPolicyVersion: string;
        localViewPolicyDigest: string;
    }>;
    readonly maskReview: Readonly<{
        policyVersion: string;
        policyDigest: string;
    }>;
    readonly evidence: Readonly<{
        policyDigest: string;
        aggregationPolicyDigest: string;
        rasterImplementationId: string;
        evidenceBackendKind: 'production-direct';
        evidenceBackendId: string;
        runtimeBuildId: string;
    }>;
    readonly liftReadiness: Readonly<{
        policyId: string;
        policyDigest: string;
    }>;
    readonly identityDigest: string;
}

type SelectionServiceProductionIdentityCapability =
    | Readonly<{ status: 'unavailable' }>
    | Readonly<{
          status: 'ready';
          record: SelectionServiceProductionIdentityRecord;
      }>;

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
    rasterImplementationId: string;
    runtimeBuildId: string;
    modelAdapterId: string;
    aiSelectAnchorOperation: string;
    candidateReLiftOperation: string;
    directEvidenceOperation: string;
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
    rgbRendererVersion: aiSelectRgbRendererVersion,
    rasterImplementationId: aiSelectRasterImplementationId,
    runtimeBuildId: aiSelectRuntimeBuildId,
    modelAdapterId: currentImageInstanceAdapterId,
    aiSelectAnchorOperation: 'aiSelectAnchorRender',
    candidateReLiftOperation: 'aiSelectProductionCandidateReLift',
    directEvidenceOperation: 'aiSelectProductionDirectEvidence',
    maskProposalOperation: 'aiSelectMaskProposals',
    maskProposalSetSchemaOperation: 'autoMaskProposalSetSchemaV3',
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
        rasterImplementationId: capabilities.renderer.rasterImplementationId,
        runtimeBuildId: capabilities.renderer.runtimeBuildId,
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
        // The adapter capability identity must survive the copy: the Prompt
        // capability derivation in main.ts trusts the advertised record only
        // when the recomputed digest matches these fields.
        compilerPolicyVersion:
            capabilities.imageInstanceProvider.compilerPolicyVersion,
        adapterCapabilityDigest:
            capabilities.imageInstanceProvider.adapterCapabilityDigest,
        message: capabilities.imageInstanceProvider.message
    },
    directEvidence: {
        ...capabilities.directEvidence,
        buildFlags: [...capabilities.directEvidence.buildFlags],
        supportedComputeCapabilities: [
            ...capabilities.directEvidence.supportedComputeCapabilities
        ]
    },
    productionCandidateReLift: {
        ...capabilities.productionCandidateReLift
    },
    productionIdentity:
        capabilities.productionIdentity.status === 'unavailable'
            ? { status: 'unavailable' }
            : {
                  status: 'ready',
                  record: {
                      ...capabilities.productionIdentity.record,
                      renderer: {
                          ...capabilities.productionIdentity.record.renderer
                      },
                      model: {
                          ...capabilities.productionIdentity.record.model
                      },
                      prompt: {
                          ...capabilities.productionIdentity.record.prompt
                      },
                      geometry: {
                          ...capabilities.productionIdentity.record.geometry
                      },
                      maskReview: {
                          ...capabilities.productionIdentity.record.maskReview
                      },
                      evidence: {
                          ...capabilities.productionIdentity.record.evidence
                      },
                      liftReadiness: {
                          ...capabilities.productionIdentity.record
                              .liftReadiness
                      }
                  }
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

const hasExactKeys = (
    value: Record<string, unknown>,
    keys: readonly string[]
): boolean =>
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key));

const isDigest = (value: unknown): value is string =>
    typeof value === 'string' && /^sha256:[a-f0-9]{64}$/i.test(value);

const canonicalIdentityJson = (value: unknown): string => {
    if (value === null || typeof value !== 'object') {
        return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
        return `[${value.map(canonicalIdentityJson).join(',')}]`;
    }
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
        .sort()
        .map(
            (key) =>
                `${JSON.stringify(key)}:${canonicalIdentityJson(record[key])}`
        )
        .join(',')}}`;
};

const modelManifestIdentityDigest = (
    manifest: SelectionServiceModelManifest
): string =>
    sha256Digest(
        new TextEncoder().encode(
            canonicalIdentityJson({
                adapterId: manifest.adapterId,
                digest: manifest.digest,
                modelName: manifest.modelName,
                checkpointDigest: manifest.checkpointDigest,
                sourceCommit: manifest.sourceCommit,
                runtimeConfigDigest: manifest.runtimeConfigDigest,
                weightsBundled: manifest.weightsBundled
            })
        )
    );

const validateProductionIdentity = (
    value: unknown
): value is SelectionServiceProductionIdentityCapability => {
    if (
        !isRecord(value) ||
        (value.status !== 'ready' && value.status !== 'unavailable')
    ) {
        return false;
    }
    if (value.status === 'unavailable') {
        return Object.keys(value).length === 1;
    }
    if (!hasExactKeys(value, ['status', 'record'])) {
        return false;
    }
    const record = value.record;
    if (
        !isRecord(record) ||
        !hasExactKeys(record, [
            'schemaVersion',
            'renderer',
            'model',
            'prompt',
            'geometry',
            'maskReview',
            'evidence',
            'liftReadiness',
            'identityDigest'
        ]) ||
        record.schemaVersion !== 1 ||
        !isRecord(record.renderer) ||
        !hasExactKeys(record.renderer, [
            'rgbRendererVersion',
            'rasterImplementationId',
            'runtimeBuildId'
        ]) ||
        !isRecord(record.model) ||
        !hasExactKeys(record.model, [
            'adapterId',
            'manifestId',
            'manifestRecordDigest',
            'checkpointDigest',
            'runtimeConfigDigest'
        ]) ||
        !isRecord(record.prompt) ||
        !hasExactKeys(record.prompt, [
            'compilerPolicyVersion',
            'adapterCapabilityDigest',
            'synthesisPolicyVersion',
            'synthesisPolicyDigest'
        ]) ||
        !isRecord(record.geometry) ||
        !hasExactKeys(record.geometry, [
            'targetGeometryPolicyVersion',
            'targetGeometryPolicyDigest',
            'localViewPolicyVersion',
            'localViewPolicyDigest'
        ]) ||
        !isRecord(record.maskReview) ||
        !hasExactKeys(record.maskReview, ['policyVersion', 'policyDigest']) ||
        !isRecord(record.evidence) ||
        !hasExactKeys(record.evidence, [
            'policyDigest',
            'aggregationPolicyDigest',
            'rasterImplementationId',
            'evidenceBackendKind',
            'evidenceBackendId',
            'runtimeBuildId'
        ]) ||
        !isRecord(record.liftReadiness) ||
        !hasExactKeys(record.liftReadiness, ['policyId', 'policyDigest']) ||
        !isDigest(record.identityDigest)
    ) {
        return false;
    }
    const requiredStrings = [
        record.renderer.rgbRendererVersion,
        record.renderer.rasterImplementationId,
        record.renderer.runtimeBuildId,
        record.model.adapterId,
        record.model.manifestId,
        record.model.manifestRecordDigest,
        record.model.checkpointDigest,
        record.model.runtimeConfigDigest,
        record.prompt.compilerPolicyVersion,
        record.prompt.adapterCapabilityDigest,
        record.prompt.synthesisPolicyVersion,
        record.prompt.synthesisPolicyDigest,
        record.geometry.targetGeometryPolicyVersion,
        record.geometry.targetGeometryPolicyDigest,
        record.geometry.localViewPolicyVersion,
        record.geometry.localViewPolicyDigest,
        record.maskReview.policyVersion,
        record.maskReview.policyDigest,
        record.evidence.policyDigest,
        record.evidence.aggregationPolicyDigest,
        record.evidence.rasterImplementationId,
        record.evidence.evidenceBackendId,
        record.evidence.runtimeBuildId,
        record.liftReadiness.policyId,
        record.liftReadiness.policyDigest
    ];
    if (
        !requiredStrings.every(isNonEmptyString) ||
        ![
            record.prompt.adapterCapabilityDigest,
            record.model.manifestRecordDigest,
            record.model.checkpointDigest,
            record.model.runtimeConfigDigest,
            record.renderer.runtimeBuildId,
            record.prompt.synthesisPolicyDigest,
            record.geometry.targetGeometryPolicyDigest,
            record.geometry.localViewPolicyDigest,
            record.maskReview.policyDigest,
            record.evidence.policyDigest,
            record.evidence.aggregationPolicyDigest,
            record.evidence.runtimeBuildId,
            record.liftReadiness.policyDigest
        ].every(isDigest) ||
        record.evidence.evidenceBackendKind !== 'production-direct'
    ) {
        return false;
    }
    const payload = Object.fromEntries(
        Object.entries(record).filter(([key]) => key !== 'identityDigest')
    );
    return (
        record.identityDigest ===
        sha256Digest(new TextEncoder().encode(canonicalIdentityJson(payload)))
    );
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
        !isRecord(value.directEvidence) ||
        !isRecord(value.productionCandidateReLift) ||
        !validateProductionIdentity(value.productionIdentity) ||
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
    const productionCandidate = value.productionCandidateReLift;
    if (
        (productionCandidate.status !== 'ready' &&
            productionCandidate.status !== 'unavailable') ||
        !isDigest(productionCandidate.evidencePolicyDigest) ||
        !isDigest(productionCandidate.aggregationPolicyDigest) ||
        !isNonEmptyString(productionCandidate.rasterImplementationId) ||
        productionCandidate.evidenceBackendKind !== 'production-direct' ||
        !isNonEmptyString(productionCandidate.evidenceBackendId) ||
        !isNonEmptyString(productionCandidate.runtimeBuildId)
    ) {
        return false;
    }
    const directEvidence = value.directEvidence;
    if (
        (directEvidence.status !== 'ready' &&
            directEvidence.status !== 'unavailable') ||
        !isNonEmptyString(directEvidence.rasterImplementationId) ||
        directEvidence.evidenceBackendKind !== 'production-direct' ||
        !isNonEmptyString(directEvidence.evidenceBackendId) ||
        typeof directEvidence.sourceRevision !== 'string' ||
        !/^sha256:[a-f0-9]{64}$/i.test(directEvidence.sourceRevision) ||
        directEvidence.expectedSourceRevision !==
            directEvidence.sourceRevision ||
        !isNonEmptyString(directEvidence.abiVersion) ||
        !isNonEmptyString(directEvidence.runtimeBuildId) ||
        directEvidence.torchVersion !== '2.11.0+cu128' ||
        directEvidence.cudaVersion !== '12.8' ||
        directEvidence.gsplatSourceCommit !==
            '77ab983ffe43420b2131669cb35776b883ca4c3c' ||
        !Array.isArray(directEvidence.supportedComputeCapabilities) ||
        !directEvidence.supportedComputeCapabilities.every(
            (value) => typeof value === 'string' && /^\d+\.\d+$/.test(value)
        ) ||
        directEvidence.accumulation !== 'global-atomic-baseline' ||
        !Array.isArray(directEvidence.buildFlags) ||
        directEvidence.buildFlags.length === 0 ||
        !directEvidence.buildFlags.every(
            (value) => typeof value === 'string' && value.length > 0
        )
    ) {
        return false;
    }
    const promptCapabilities = value.imageInstanceProvider.promptCapabilities;
    const promptCapabilityKeys = [
        'positivePoints',
        'negativePoints',
        'positiveInstanceBox',
        'previousLogitsRefinement',
        'singlePointMultimask'
    ];
    if (
        !hasExactKeys(promptCapabilities, promptCapabilityKeys) ||
        !promptCapabilityKeys.every(
            (key) => typeof promptCapabilities[key] === 'boolean'
        )
    ) {
        return false;
    }
    if (
        (value.imageInstanceProvider.compilerPolicyVersion !== undefined &&
            typeof value.imageInstanceProvider.compilerPolicyVersion !==
                'string') ||
        (value.imageInstanceProvider.adapterCapabilityDigest !== undefined &&
            (typeof value.imageInstanceProvider.adapterCapabilityDigest !==
                'string' ||
                !/^sha256:[a-f0-9]{64}$/i.test(
                    value.imageInstanceProvider.adapterCapabilityDigest
                )))
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
        !isDigest(value.activeModelManifest.checkpointDigest) ||
        !isNonEmptyString(value.activeModelManifest.sourceCommit) ||
        !isDigest(value.activeModelManifest.runtimeConfigDigest) ||
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
                this.requirements.rgbRendererVersion ||
            capabilities.renderer.rasterImplementationId !==
                this.requirements.rasterImplementationId ||
            capabilities.renderer.runtimeBuildId !==
                this.requirements.runtimeBuildId
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
            prompts.singlePointMultimask
        ) {
            return diagnostic(
                'imageInstanceCapabilityMismatch',
                'The image provider Prompt/refinement capabilities do not match the current profile.',
                'Use the current SAM 3 Image instance adapter.'
            );
        }
        // A ready provider must advertise the compiler policy and the exact
        // adapter capability digest so the editor can rebuild and verify the
        // Prompt Adapter capability record locally (04C contract §3).
        if (
            !isNonEmptyString(provider.compilerPolicyVersion) ||
            typeof provider.adapterCapabilityDigest !== 'string' ||
            !/^sha256:[a-f0-9]{64}$/i.test(provider.adapterCapabilityDigest)
        ) {
            return diagnostic(
                'imageInstanceCapabilityMismatch',
                'The image provider does not advertise its compiler policy and adapter capability digest.',
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
            capabilities.directEvidence.status !== 'ready' ||
            capabilities.directEvidence.rasterImplementationId !==
                this.requirements.rasterImplementationId ||
            capabilities.directEvidence.evidenceBackendKind !==
                'production-direct' ||
            capabilities.directEvidence.evidenceBackendId !==
                'global-atomic/direct-v1' ||
            capabilities.directEvidence.abiVersion !==
                'supersimplat-direct-evidence-abi/v2' ||
            capabilities.directEvidence.runtimeBuildId !==
                this.requirements.runtimeBuildId ||
            !capabilities.directEvidence.supportedComputeCapabilities.includes(
                '8.9'
            ) ||
            !capabilities.supportedOperations.includes(
                this.requirements.directEvidenceOperation
            )
        ) {
            return diagnostic(
                'directEvidenceUnsupported',
                'Production Direct Evidence is unavailable.',
                'Use the locked compatible Companion release.'
            );
        }
        if (
            !capabilities.supportedOperations.includes(
                this.requirements.candidateReLiftOperation
            ) ||
            capabilities.productionCandidateReLift.status !== 'ready' ||
            capabilities.productionCandidateReLift.evidencePolicyDigest !==
                productionEvidencePolicyDigest ||
            capabilities.productionCandidateReLift.aggregationPolicyDigest !==
                productionAggregationPolicyDigest ||
            capabilities.productionCandidateReLift.rasterImplementationId !==
                productionEvidenceRasterImplementationId ||
            capabilities.productionCandidateReLift.evidenceBackendKind !==
                'production-direct' ||
            capabilities.productionCandidateReLift.evidenceBackendId !==
                productionDirectEvidenceBackendId ||
            capabilities.productionCandidateReLift.runtimeBuildId !==
                productionEvidenceRuntimeBuildId
        ) {
            return diagnostic(
                'candidateReLiftUnsupported',
                'Evidence-aware Candidate Re-Lift is unavailable.',
                'Use the compatible locked Companion release.'
            );
        }
        const productionIdentity = capabilities.productionIdentity;
        if (productionIdentity.status !== 'ready') {
            return diagnostic(
                'candidateReLiftUnsupported',
                'The production AI Select identity is unavailable.',
                'Use the fully calibrated locked Companion release.'
            );
        }
        const record = productionIdentity.record;
        const expectedPromptCapabilities = createPromptAdapterCapabilities({
            ...provider.promptCapabilities,
            compilerPolicyVersion: currentPromptCompilerPolicyVersion
        });
        if (
            record.renderer.rgbRendererVersion !==
                capabilities.renderer.rgbRendererVersion ||
            record.renderer.rasterImplementationId !==
                capabilities.directEvidence.rasterImplementationId ||
            record.renderer.runtimeBuildId !==
                capabilities.directEvidence.runtimeBuildId ||
            record.model.adapterId !== modelManifest.adapterId ||
            record.model.manifestId !== modelManifest.digest ||
            record.model.manifestRecordDigest !==
                modelManifestIdentityDigest(modelManifest) ||
            record.model.checkpointDigest !== modelManifest.checkpointDigest ||
            record.model.runtimeConfigDigest !==
                modelManifest.runtimeConfigDigest ||
            record.prompt.compilerPolicyVersion !==
                currentPromptCompilerPolicyVersion ||
            provider.compilerPolicyVersion !==
                currentPromptCompilerPolicyVersion ||
            record.prompt.adapterCapabilityDigest !==
                expectedPromptCapabilities.capabilityDigest ||
            provider.adapterCapabilityDigest !==
                expectedPromptCapabilities.capabilityDigest ||
            record.prompt.synthesisPolicyVersion !==
                aiSelectImageInstancePromptSynthesisPolicyVersion ||
            record.prompt.synthesisPolicyDigest !==
                aiSelectImageInstancePromptSynthesisPolicyDigest ||
            record.geometry.targetGeometryPolicyVersion !==
                aiSelectTargetGeometryPolicyVersion ||
            record.geometry.targetGeometryPolicyDigest !==
                aiSelectTargetGeometryPolicyDigest ||
            record.geometry.localViewPolicyVersion !==
                aiSelectLocalKeyViewPlannerVersion ||
            record.geometry.localViewPolicyDigest !==
                aiSelectLocalKeyViewPolicyDigest ||
            record.maskReview.policyVersion !==
                aiSelectViewAssessmentPolicyVersion ||
            record.maskReview.policyDigest !==
                aiSelectViewAssessmentPolicyDigest ||
            record.evidence.policyDigest !== productionEvidencePolicyDigest ||
            record.evidence.aggregationPolicyDigest !==
                productionAggregationPolicyDigest ||
            record.evidence.rasterImplementationId !==
                productionEvidenceRasterImplementationId ||
            record.evidence.evidenceBackendKind !== 'production-direct' ||
            record.evidence.evidenceBackendId !==
                productionDirectEvidenceBackendId ||
            record.evidence.runtimeBuildId !==
                productionEvidenceRuntimeBuildId ||
            record.liftReadiness.policyId !== 'lift-readiness/production-v1' ||
            record.liftReadiness.policyDigest !==
                defaultLiftReadinessPolicy().readinessPolicyDigest
        ) {
            return diagnostic(
                'candidateReLiftUnsupported',
                'The production AI Select identity is incompatible.',
                'Use the fully calibrated locked Companion release.'
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

// This decorator is the current AI Select transport boundary. Every product
// operation passes the operator-visible readiness decision before reaching the
// Companion adapter.
class ReadinessGatedSelectionServiceAdapter implements SelectionServiceAdapter {
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

    async renderAnchor(
        request: AnchorRenderRequest
    ): Promise<AnchorRenderResponse> {
        this.readiness.requireReady();
        return await this.requireAnchorRenderer().renderAnchor(request);
    }

    async produceMask(request: AIViewMaskRequest): Promise<MaskResultResponse> {
        this.readiness.requireReady();
        return await this.requireMaskProvider().produceMask(request);
    }

    async probeAnchorSupport(
        request: AnchorSupportProbeRequest
    ): Promise<AnchorSupportProbeResponse> {
        this.readiness.requireReady();
        return await this.requireSupportProbeProvider().probeAnchorSupport(
            request
        );
    }

    async produceTargetGeometryHint(
        request: TargetGeometryHintRequest
    ): Promise<TargetGeometryHintResponse> {
        this.readiness.requireReady();
        return await this.requireTargetGeometryProvider().produceTargetGeometryHint(
            request
        );
    }

    async planLocalKeyViews(
        request: LocalKeyViewPlanRequest
    ): Promise<LocalKeyViewPlanResponse> {
        this.readiness.requireReady();
        return await this.requireLocalKeyViewPlanner().planLocalKeyViews(
            request
        );
    }

    async renderView(
        request: AIViewRenderRequest
    ): Promise<AIViewRenderResponse> {
        this.readiness.requireReady();
        return await this.requireViewRenderer().renderView(request);
    }

    async synthesizeGeneratedViewPrompt(
        request: GeneratedViewPromptSynthesisRequest
    ): Promise<GeneratedViewPromptSynthesisResponse> {
        this.readiness.requireReady();
        return await this.requireGeneratedViewPromptSynthesizer().synthesizeGeneratedViewPrompt(
            request
        );
    }

    async infer(
        request: ImageInstanceMaskRequest
    ): Promise<ImageInstanceMaskResult> {
        this.readiness.requireReady();
        return await this.requireImageInstanceMaskProvider().infer(request);
    }

    async reviewImageInstanceMask(
        request: ImageInstanceMaskReviewRequest
    ): Promise<ImageInstanceMaskReviewResponse> {
        this.readiness.requireReady();
        return await this.requireImageInstanceMaskReviewProvider().reviewImageInstanceMask(
            request
        );
    }

    async produceCandidateReLift(
        request: CandidateReLiftRequest
    ): Promise<CandidateReLiftResponse> {
        this.readiness.requireReady();
        return await this.requireCandidateReLiftProvider().produceCandidateReLift(
            request
        );
    }

    async produceDirectEvidence(
        request: DirectEvidenceRequest
    ): Promise<DirectEvidenceResponse> {
        this.readiness.requireReady();
        return await this.requireDirectEvidenceProvider().produceDirectEvidence(
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
            typeof (adapter as Partial<AISelectMaskProvider>).produceMask !==
            'function'
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

    private requireTargetGeometryProvider(): AISelectTargetGeometryProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectTargetGeometryProvider>)
                .produceTargetGeometryHint !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectTargetGeometryProvider;
    }

    private requireLocalKeyViewPlanner(): AISelectLocalKeyViewPlanner {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectLocalKeyViewPlanner>)
                .planLocalKeyViews !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & AISelectLocalKeyViewPlanner;
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

    private requireGeneratedViewPromptSynthesizer(): AISelectGeneratedViewPromptSynthesizer {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectGeneratedViewPromptSynthesizer>)
                .synthesizeGeneratedViewPrompt !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectGeneratedViewPromptSynthesizer;
    }

    private requireImageInstanceMaskProvider(): ImageInstanceMaskProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<ImageInstanceMaskProvider>).infer !==
            'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter & ImageInstanceMaskProvider;
    }

    private requireImageInstanceMaskReviewProvider(): AISelectImageInstanceMaskReviewProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectImageInstanceMaskReviewProvider>)
                .reviewImageInstanceMask !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectImageInstanceMaskReviewProvider;
    }

    private requireCandidateReLiftProvider(): AISelectCandidateReLiftProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectCandidateReLiftProvider>)
                .produceCandidateReLift !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectCandidateReLiftProvider;
    }

    private requireDirectEvidenceProvider(): AISelectDirectEvidenceProvider {
        const adapter = this.requireAdapter();
        if (
            typeof (adapter as Partial<AISelectDirectEvidenceProvider>)
                .produceDirectEvidence !== 'function'
        ) {
            throw new SelectionServiceAdapterNotConfiguredError();
        }
        return adapter as SelectionServiceAdapter &
            AISelectDirectEvidenceProvider;
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
    SelectionServiceAdapter,
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
