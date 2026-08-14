import type {
    CandidatePublicationBinding,
    ReferenceCandidateArtifact
} from './candidate-publication';
import {
    areTargetDependencyTokensEqual,
    type CurrentTargetContext,
    type TargetDependencyToken
} from './current-target-context';

export type CandidateApplicationOperation =
    'set' | 'add' | 'remove' | 'intersect';

export type CandidateApplicationMode = 'production' | 'development-reference';

export type CandidateApplicationBlockReason =
    | 'candidate-unavailable'
    | 'candidate-stale'
    | 'context-unavailable'
    | 'context-suspended'
    | 'target-mismatch'
    | 'reference-disallowed'
    | 'runtime-unverified'
    | 'renderer-incompatible'
    | 'backend-incompatible'
    | 'runtime-incompatible'
    | 'policy-incompatible'
    | 'identity-unverified';

export type CandidateEvidenceBackendKind =
    'reference-contributor' | 'reference-autograd' | 'production-direct';

export interface CandidateApplicationBackendIdentity {
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: CandidateEvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
}

export interface ProductionCandidateApplicationArtifact {
    readonly productionReadiness: 'production-ready';
    readonly publicationBinding: Omit<
        CandidatePublicationBinding,
        'referenceBackendIdentity'
    > &
        Readonly<{
            evidenceBackendIdentity: CandidateApplicationBackendIdentity &
                Readonly<{ evidenceBackendKind: 'production-direct' }>;
        }>;
    readonly candidate: Readonly<{
        selectedStableGaussianIds: readonly number[];
    }>;
    readonly candidateDigest: string;
}

/** Validated reference or future production publisher handoff. */
export type CandidateApplicationArtifact =
    ReferenceCandidateArtifact | ProductionCandidateApplicationArtifact;

export interface CandidateApplicationSource {
    readonly presentationState: Readonly<{
        status: 'empty' | 'current' | 'stale';
    }>;
    readonly inspectableCandidate: CandidateApplicationArtifact | null;
    subscribe(
        listener: (
            state: CandidateApplicationSource['presentationState']
        ) => void
    ): () => void;
}

export interface CandidateApplicationRuntimeIdentity {
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: CandidateEvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
    readonly sourceEvidencePolicyDigest: string;
    readonly aggregationPolicyDigest: string;
}

export interface CandidateNativeHistoryCommand {
    readonly name: string;
}

export interface CandidateNativeSelection {
    apply(
        operation: CandidateApplicationOperation,
        selectedStableGaussianIds: readonly number[],
        validateCurrent: () => void
    ): Promise<CandidateNativeHistoryCommand>;
}

export interface CandidateApplicationTarget {
    readonly context: CurrentTargetContext | null;
    readonly effectiveDependencyToken: TargetDependencyToken;
}

export interface CandidateApplicationControllerOptions {
    readonly candidates: CandidateApplicationSource;
    readonly nativeSelection: CandidateNativeSelection;
    readonly applicationMode: CandidateApplicationMode;
    readonly getAcceptedRuntime: () => CandidateApplicationRuntimeIdentity | null;
    readonly getTarget: () => CandidateApplicationTarget | null;
}

export interface CandidateApplicationRecord {
    readonly candidateRevision: Readonly<{
        candidateDigest: string;
        targetContextId: string;
        contextRevision: number;
    }>;
    readonly rasterImplementationId: string;
    readonly evidenceBackendKind: CandidateEvidenceBackendKind;
    readonly evidenceBackendId: string;
    readonly runtimeBuildId: string;
    readonly policyIdentity: Readonly<{
        sourceEvidencePolicyDigest: string;
        aggregationPolicyDigest: string;
    }>;
    readonly operation: CandidateApplicationOperation;
    readonly nativeHistoryCommand: CandidateNativeHistoryCommand;
}

export type CandidateOverlayEmphasis = 'emphasized' | 'deemphasized';

export type CandidateApplicationState =
    | Readonly<{
          status: 'unavailable';
          blockReason: 'candidate-unavailable';
          applicationRecord: null;
          overlayEmphasis: 'emphasized';
      }>
    | Readonly<{
          status: 'blocked';
          blockReason: CandidateApplicationBlockReason;
          applicationRecord: CandidateApplicationRecord | null;
          overlayEmphasis: CandidateOverlayEmphasis;
      }>
    | Readonly<{
          status: 'ready' | 'applying';
          blockReason: null;
          applicationRecord: null;
          overlayEmphasis: 'emphasized';
      }>
    | Readonly<{
          status: 'applied';
          blockReason: null;
          applicationRecord: CandidateApplicationRecord;
          overlayEmphasis: CandidateOverlayEmphasis;
      }>;

export type CandidateApplicationListener = (
    state: CandidateApplicationState
) => void;

export class CandidateApplicationBlockedError extends Error {
    constructor(readonly reason: CandidateApplicationBlockReason) {
        super(`AI Select Candidate application is blocked: ${reason}.`);
        this.name = 'CandidateApplicationBlockedError';
    }
}

/** Fail-closed bridge from one published Candidate to native selection. */
export class CandidateApplicationController {
    private readonly candidates: CandidateApplicationSource;
    private readonly nativeSelection: CandidateNativeSelection;
    private readonly applicationMode: CandidateApplicationMode;
    private readonly getAcceptedRuntime: () => CandidateApplicationRuntimeIdentity | null;
    private readonly getTarget: () => CandidateApplicationTarget | null;
    private readonly listeners = new Set<CandidateApplicationListener>();
    private applying = false;
    private applicationRecord: CandidateApplicationRecord | null = null;
    private overlayEmphasis: CandidateOverlayEmphasis = 'emphasized';

    constructor(options: CandidateApplicationControllerOptions) {
        this.candidates = options.candidates;
        this.nativeSelection = options.nativeSelection;
        this.applicationMode = options.applicationMode;
        this.getAcceptedRuntime = options.getAcceptedRuntime;
        this.getTarget = options.getTarget;
        this.candidates.subscribe(() => this.notify());
    }

    get state(): CandidateApplicationState {
        const candidateState = this.candidates.presentationState;
        if (candidateState.status === 'empty') {
            return Object.freeze({
                status: 'unavailable',
                blockReason: 'candidate-unavailable',
                applicationRecord: null,
                overlayEmphasis: 'emphasized'
            });
        }
        const candidate = this.candidates.inspectableCandidate;
        const currentApplicationRecord = this.recordFor(candidate);
        const blockReason = this.applicationBlockReason(candidate);
        if (blockReason !== null) {
            return Object.freeze({
                status: 'blocked',
                blockReason,
                applicationRecord: currentApplicationRecord,
                overlayEmphasis:
                    currentApplicationRecord === null
                        ? 'emphasized'
                        : this.overlayEmphasis
            });
        }
        if (this.applying) {
            return Object.freeze({
                status: 'applying',
                blockReason: null,
                applicationRecord: null,
                overlayEmphasis: 'emphasized'
            });
        }
        if (currentApplicationRecord !== null) {
            return Object.freeze({
                status: 'applied',
                blockReason: null,
                applicationRecord: currentApplicationRecord,
                overlayEmphasis: this.overlayEmphasis
            });
        }
        return Object.freeze({
            status: 'ready',
            blockReason: null,
            applicationRecord: null,
            overlayEmphasis: 'emphasized'
        });
    }

    subscribe(listener: CandidateApplicationListener): () => void {
        this.listeners.add(listener);
        listener(this.state);
        return () => this.listeners.delete(listener);
    }

    async apply(
        operation: CandidateApplicationOperation
    ): Promise<CandidateApplicationRecord> {
        if (this.applying) {
            throw new CandidateApplicationBlockedError('identity-unverified');
        }
        const candidate = this.requireApplicableCandidate();
        this.applying = true;
        this.notify();
        try {
            const nativeHistoryCommand = await this.nativeSelection.apply(
                operation,
                candidate.candidate.selectedStableGaussianIds,
                () => {
                    this.requireApplicableCandidate(candidate.candidateDigest);
                }
            );
            const backend = this.backendFor(candidate);
            const request = candidate.publicationBinding.requestBinding;
            const applicationRecord = Object.freeze({
                candidateRevision: Object.freeze({
                    candidateDigest: candidate.candidateDigest,
                    targetContextId: request.targetContextId,
                    contextRevision: request.contextRevision
                }),
                rasterImplementationId: backend.rasterImplementationId,
                evidenceBackendKind: backend.evidenceBackendKind,
                evidenceBackendId: backend.evidenceBackendId,
                runtimeBuildId: backend.runtimeBuildId,
                policyIdentity: Object.freeze({
                    sourceEvidencePolicyDigest:
                        candidate.publicationBinding.sourceEvidencePolicyDigest,
                    aggregationPolicyDigest:
                        candidate.publicationBinding.aggregationPolicyDigest
                }),
                operation,
                nativeHistoryCommand
            });
            this.applicationRecord = applicationRecord;
            this.overlayEmphasis = 'deemphasized';
            return applicationRecord;
        } finally {
            this.applying = false;
            this.notify();
        }
    }

    refresh(): void {
        this.notify();
    }

    showAIResult(): void {
        if (this.state.status !== 'applied') {
            throw new CandidateApplicationBlockedError('candidate-unavailable');
        }
        this.overlayEmphasis = 'emphasized';
        this.notify();
    }

    private requireApplicableCandidate(
        expectedCandidateDigest?: string
    ): CandidateApplicationArtifact {
        const candidate = this.candidates.inspectableCandidate;
        const reason = this.applicationBlockReason(candidate);
        if (
            reason !== null ||
            candidate === null ||
            (expectedCandidateDigest !== undefined &&
                candidate.candidateDigest !== expectedCandidateDigest)
        ) {
            throw new CandidateApplicationBlockedError(
                reason ?? 'identity-unverified'
            );
        }
        return candidate;
    }

    private applicationBlockReason(
        candidate: CandidateApplicationArtifact | null
    ): CandidateApplicationBlockReason | null {
        const presentation = this.candidates.presentationState;
        if (candidate === null || presentation.status === 'empty') {
            return 'candidate-unavailable';
        }
        if (presentation.status === 'stale') {
            return 'candidate-stale';
        }
        const target = this.getTarget();
        if (target === null || target.context === null) {
            return 'context-unavailable';
        }
        if (target.context.lifecycle !== 'active') {
            return 'context-suspended';
        }
        const publication = candidate.publicationBinding;
        if (
            target.context.target.splatId !== publication.targetSplatId ||
            target.context.targetContextId !==
                publication.requestBinding.targetContextId ||
            !areTargetDependencyTokensEqual(
                target.effectiveDependencyToken,
                publication.requestBinding.dependencyToken
            )
        ) {
            return 'target-mismatch';
        }
        if (
            candidate.productionReadiness === 'reference-only' &&
            this.applicationMode === 'production'
        ) {
            return 'reference-disallowed';
        }
        const backend = this.backendFor(candidate);
        if (
            (candidate.productionReadiness === 'production-ready') !==
            (backend.evidenceBackendKind === 'production-direct')
        ) {
            return 'identity-unverified';
        }
        const accepted = this.getAcceptedRuntime();
        if (accepted === null) {
            return 'runtime-unverified';
        }
        if (
            accepted.rasterImplementationId !== backend.rasterImplementationId
        ) {
            return 'renderer-incompatible';
        }
        if (
            accepted.evidenceBackendKind !== backend.evidenceBackendKind ||
            accepted.evidenceBackendId !== backend.evidenceBackendId
        ) {
            return 'backend-incompatible';
        }
        if (accepted.runtimeBuildId !== backend.runtimeBuildId) {
            return 'runtime-incompatible';
        }
        if (
            accepted.sourceEvidencePolicyDigest !==
                publication.sourceEvidencePolicyDigest ||
            accepted.aggregationPolicyDigest !==
                publication.aggregationPolicyDigest
        ) {
            return 'policy-incompatible';
        }
        return null;
    }

    private recordFor(
        candidate: CandidateApplicationArtifact | null
    ): CandidateApplicationRecord | null {
        return candidate !== null &&
            this.applicationRecord?.candidateRevision.candidateDigest ===
                candidate.candidateDigest
            ? this.applicationRecord
            : null;
    }

    private backendFor(
        candidate: CandidateApplicationArtifact
    ): CandidateApplicationBackendIdentity {
        return candidate.productionReadiness === 'reference-only'
            ? candidate.publicationBinding.referenceBackendIdentity
            : candidate.publicationBinding.evidenceBackendIdentity;
    }

    private notify(): void {
        const state = this.state;
        this.listeners.forEach((listener) => {
            try {
                listener(state);
            } catch (error) {
                console.error(error);
            }
        });
    }
}
