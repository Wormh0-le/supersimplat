# 08A — Multi-view Mask acquisition contracts + backend registry

Status: planned — contract foundation

Blocked by: 08

Blocks: 08B

## Final Spec mapping

- Final Spec v1.2 §§11, 14–18, 26–29
- DG-26 Decisions 2–6 and 8
- ADR 0014 as subordinate Route-B-first rationale

## Purpose

Define the stable, backend-neutral artifacts and runtime extension seams used by route-B production acquisition and future route-C/route-D experiments.

This ticket is a protocol and registry foundation. It does not implement production SAM inference, Prompt synthesis, proposal decision, View Assessment, Stable Mask publication, route-A fallback execution, Gallery, or tracker behavior.

## Inputs / preconditions

- Ticket 08 `VisibleTargetSupportArtifact` contract;
- Ticket 08 `TargetBootstrapArtifact` contract;
- Ticket 08 `SparseKeyViewPlanSegment` contract;
- authoritative RGB and CameraBinding contracts;
- existing PromptState, MaskArtifact, Stable Mask and attempt identity primitives;
- current Companion readiness/capability protocol.

## Outputs / handoff artifacts

- canonical acquisition identity envelope;
- `KeyViewPromptArtifact` schema;
- `KeyViewMaskProposalSet` schema;
- `PerViewMaskAcquisitionResult` schema;
- `KeyViewMaskDecision` schema bound to an exact ProposalSet;
- acquisition request/result schemas;
- attempt and fallback identity schemas;
- Mask publication command/result schemas;
- `MaskAcquisitionBackendDescriptor`;
- `MaskAcquisitionBackend` bundle;
- `MaskAcquisitionBackendRegistry`;
- `MultiViewMaskAcquisitionProvider` contract;
- optional `SequenceMaskAcquisitionExtension` contract;
- structural validators, canonical digest rules, compatibility tests and golden vectors.

# 1. Common identity envelope

Every artifact binds the exact current dependency identities applicable to it:

```text
targetContextId + contextRevision
scene / splat dependency identity
Anchor CameraBinding + RGB + Stable Mask digest
VisibleTargetSupportArtifact digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
Key-View CameraBinding + RGB digest
adapter capability digest
Prompt synthesis policy digest
KeyViewPromptArtifact digest
backend descriptor/capability digest
model / adapter / runtime identity
decision / assessment / publication policy identity
attempt / fallback / sequence-run identity
result artifact digest
```

Sequence-only fields remain absent when no sequence backend exists. They are never populated with invented values.

# 2. KeyViewPromptArtifact contract

Define a model-independent artifact equivalent to:

```ts
interface KeyViewPromptArtifact {
    schemaVersion: number;
    targetContextId: string;
    contextRevision: number;
    viewId: string;

    sceneDependencyDigest: string;
    anchorStableMaskDigest: string;
    visibleTargetSupportArtifactDigest: string;
    targetBootstrapArtifactDigest: string;
    sparseKeyViewPlanSegmentDigest: string;
    keyViewCameraBindingDigest: string;
    keyViewRgbDigest: string;

    adapterCapabilityDigest: string;
    promptSynthesisPolicyDigest: string;
    prompts: readonly MaskPrompt[];
    diagnostics: PromptSynthesisDiagnostics;
    artifactDigest: string;
}
```

Requirements:

- ordered Prompt payload is immutable and canonical-digestable;
- unsupported Prompt families cannot appear after capability validation;
- geometry/support diagnostics remain non-ownership metadata;
- Prompt artifact can be inspected, replayed, cached, and independently regenerated;
- acquisition providers do not receive raw support payload as an alternate source of truth.

# 3. KeyViewMaskProposalSet contract

```ts
interface KeyViewMaskProposalSet {
    schemaVersion: number;
    targetContextId: string;
    contextRevision: number;
    viewId: string;

    promptArtifactDigest: string;
    backendId: string;
    modelId: string;
    runtimeBuildId: string;
    attemptId: string;

    proposals: readonly KeyViewMaskProposal[];
    artifactDigest: string;
}

interface KeyViewMaskProposal {
    proposalId: string;
    mask: MaskArtifact;
    rawModelScore?: number;
    projectedPositiveRecall?: number;
    localNegativeViolation?: number;
    projectedRoiCoverage?: number;
    boundaryClipping?: number;
    fragmentation?: number;
    artifactDigest: string;
}
```

A proposal set may be empty. The provider does not hide Top-1 selection inside this contract.

`KeyViewMaskProposalSet` contains candidate artifacts only. Attempt-level timing, resource, compatibility, warning, and technical-failure diagnostics belong exclusively to `PerViewMaskAcquisitionResult`; they MUST NOT be duplicated inside the ProposalSet.

# 4. PerViewMaskAcquisitionResult contract

```ts
interface PerViewMaskAcquisitionResult {
    schemaVersion: number;
    requestIdentity: PerViewMaskAcquisitionRequestIdentity;
    proposalSet: KeyViewMaskProposalSet;
    backendDiagnostics: AcquisitionBackendDiagnostics;
    resultDigest: string;
}
```

Rules:

- `requestIdentity` exactly echoes the accepted request identity;
- `proposalSet.attemptId`, backend/model/runtime identity, target, View, and Prompt digest match the request;
- `backendDiagnostics` is the only attempt-level diagnostics authority;
- diagnostics never select a proposal, publish Stable state, set Participation, or authorize P/N/V;
- a successful result may contain an empty ProposalSet;
- technical dispatch/inference failure produces no partial `PerViewMaskAcquisitionResult` or ProposalSet.

# 5. KeyViewMaskDecision contract

Every Decision variant binds the exact ProposalSet it evaluates:

```ts
interface KeyViewMaskDecisionIdentity {
    schemaVersion: number;
    targetContextId: string;
    contextRevision: number;
    viewId: string;
    acquisitionAttemptId: string;
    proposalSetArtifactDigest: string;
    decisionPolicyDigest: string;
    artifactDigest: string;
}

type KeyViewMaskDecision =
    | (KeyViewMaskDecisionIdentity & {
          status: 'selected';
          selectedProposalId: string;
          reasons: readonly string[];
      })
    | (KeyViewMaskDecisionIdentity & {
          status: 'ambiguous';
          candidateProposalIds: readonly string[];
          reasons: readonly string[];
      })
    | (KeyViewMaskDecisionIdentity & {
          status: 'unavailable';
          reasons: readonly string[];
      });
```

Contract invariants:

- Decision target/context/View/attempt exactly match the bound ProposalSet;
- `proposalSetArtifactDigest` is required and current;
- selected proposal exists in the exact ProposalSet;
- ambiguous IDs are unique and exist in the exact ProposalSet;
- unavailable selects nothing;
- Decision does not contain View Assessment or Participation;
- raw model score is never represented as correctness probability.

# 6. Attempt and fallback identity

```ts
interface AcquisitionAttemptIdentity {
    attemptId: string;
    route: 'A' | 'B' | 'C' | 'D';
    backendId: string;
    backendDescriptorDigest: string;
    modelId: string;
    runtimeBuildId: string;
    fallbackOfAttemptId?: string;
    fallbackReason?: AcquisitionTechnicalFailureReason;
}
```

Rules:

- explicit Retry creates a new `attemptId`;
- same-attempt replay may be idempotent;
- fallback attempt is distinct and binds its parent attempt;
- fallback reason is restricted to declared technical/capability categories;
- semantic/quality outcomes cannot be encoded as technical fallback reasons.

# 7. Backend descriptor, bundle, and registry

```ts
type MaskAcquisitionBackendKind =
    | 'per-view-sam'
    | 'sequence-tracker'
    | 'hybrid';

interface MaskAcquisitionBackendDescriptor {
    schemaVersion: number;
    backendKind: MaskAcquisitionBackendKind;
    backendId: string;
    modelId: string;
    runtimeBuildId: string;

    perView?: {
        contractVersion: string;
    };

    sequence?: {
        contractVersion: string;
        supportsReferenceUpdates: boolean;
        supportsAuxiliaryFrames: boolean;
        supportsRepropagation: boolean;
    };

    capabilityDigest: string;
}

interface MaskAcquisitionBackend {
    readonly descriptor: MaskAcquisitionBackendDescriptor;
    readonly perView?: MultiViewMaskAcquisitionProvider;
    readonly sequence?: SequenceMaskAcquisitionExtension;
}

interface MaskAcquisitionBackendRegistry {
    resolveBackend(backendId: string): MaskAcquisitionBackend;
}
```

Bundle validation:

```text
per-view-sam
→ perView required
→ sequence absent

sequence-tracker
→ sequence required
→ perView optional

hybrid
→ perView required
→ sequence required
```

Descriptor capabilities MUST match actual extension presence. A contradiction fails readiness and registration.

# 8. Per-view provider contract

```ts
interface MultiViewMaskAcquisitionProvider {
    acquireView(
        request: PerViewMaskAcquisitionRequest
    ): Promise<PerViewMaskAcquisitionResult>;
}
```

The request consumes authoritative RGB plus an immutable `KeyViewPromptArtifact` and exact backend/attempt identity.

The result returns:

- exact echoed request identity;
- `KeyViewMaskProposalSet`;
- one attempt-level `backendDiagnostics` authority;
- result digest.

It MUST NOT return:

- `KeyViewMaskDecision`;
- `ViewAssessmentResult`;
- Stable Mask status;
- Participation;
- Candidate or P/N/V;
- publication side effects.

# 9. Optional sequence extension

```ts
interface SequenceMaskAcquisitionExtension {
    openSequence(
        request: OpenMaskSequenceRequest
    ): Promise<OpenMaskSequenceResult>;

    acquireSequenceRange(
        request: AcquireMaskSequenceRangeRequest
    ): Promise<AcquireMaskSequenceRangeResult>;

    updateReferences(
        request: UpdateMaskSequenceReferencesRequest
    ): Promise<UpdateMaskSequenceReferencesResult>;

    closeSequence(
        request: CloseMaskSequenceRequest
    ): Promise<void>;
}
```

Intended mapping:

```text
Route B
= perView only

Route C
= sequence
+ optional perView recovery

Route D
= perView Key-View references
+ sequence propagation
```

Ticket 08A defines and validates these schemas but does not implement a tracker, sequence session, Bridge View, reference memory UI, or propagation.

# 10. Publication contracts

Define backend-neutral commands/results for `MaskPublicationCoordinator`.

Publication input binds:

- exact ProposalSet and `proposalSetArtifactDigest`;
- exact Decision and Decision artifact digest;
- exact selected proposal where applicable;
- exact ViewAssessmentResult where applicable;
- current RGB/Stable authority;
- publication policy identity.

Publication result can express:

```text
published-auto-good
published-auto-review
retained-ambiguous-review
retained-unavailable-no-mask
rejected-stale
blocked-user-confirmed
```

`retained-unavailable-no-mask` means acquisition completed successfully but no eligible proposal was selected. It is distinct from backend/protocol/inference failure.

The contract does not implement the coordinator; Ticket 08B owns execution.

# Acceptance criteria

## Schemas and identity

- [ ] Every public artifact is versioned.
- [ ] Every artifact has structural validator and canonical digest rules.
- [ ] Cross-artifact references validate exact digests and View identity.
- [ ] Sequence-only fields are absent for per-view route B.
- [ ] Prompt, ProposalSet, acquisition result, Decision, Assessment, Publication, Participation, and P/N/V remain distinct types.
- [ ] `KeyViewMaskDecision` requires exact `proposalSetArtifactDigest`, target/context/View, and acquisition attempt identity.
- [ ] Golden vectors cover valid and invalid identity combinations.

## Diagnostics authority

- [ ] `backendDiagnostics` exists only on `PerViewMaskAcquisitionResult`.
- [ ] ProposalSet contains candidate artifacts and candidate-local metrics only.
- [ ] Duplicate or conflicting attempt diagnostics are rejected.
- [ ] Attempt diagnostics cannot authorize Decision, Stable publication, Participation, or Evidence.

## Backend registry

- [ ] Bundle structure is the capability truth source.
- [ ] Descriptor/bundle contradictions fail registration/readiness.
- [ ] Route-B fixture has perView and no sequence extension.
- [ ] Route-C fixture has sequence and optional perView.
- [ ] Route-D fixture has both.
- [ ] Unknown backend IDs fail closed.
- [ ] Registry resolution has no Gallery/Mask-registry side effects.

## Provider boundary

- [ ] Provider result contains ProposalSet, not one hidden final Mask.
- [ ] Provider result contains no Decision, Assessment, Stable publication, Participation, Evidence, or Candidate.
- [ ] Request requires immutable Prompt artifact rather than raw support reinterpretation.
- [ ] Same-attempt replay and new Retry identities are distinguishable.
- [ ] Fallback parent/reason identity validates.
- [ ] A successful empty ProposalSet is representable without being mislabeled as technical failure.

## Decision binding

- [ ] selected/ambiguous/unavailable Decisions bind the exact ProposalSet artifact digest.
- [ ] Proposal membership is rejected across a different attempt or ProposalSet even when proposal IDs collide.
- [ ] Publication rejects missing, stale, or mismatched Decision-to-ProposalSet identity.

## Optional extension readiness

- [ ] Sequence/reference request and result schemas have validators and identity golden vectors.
- [ ] Route B exposes no sequence implementation.
- [ ] Unsupported extension dispatch fails before inference or mutation.
- [ ] No fake session/reference/auxiliary-frame artifact is created.

# Failure / recovery criteria

- Invalid schema/digest: reject before dispatch.
- Contradictory backend descriptor/bundle: backend Not Ready.
- Unknown/stale backend identity: no inference or state mutation.
- Invalid fallback reason or missing parent attempt: reject.
- ProposalSet/Decision digest, attempt, target, or View mismatch: reject publication command.
- Duplicate/conflicting diagnostics authority: reject result.
- Unsupported sequence/reference operation: structured capability failure, no state mutation.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run build`
- Prompt/Proposal/Decision canonical digest golden vectors
- backend bundle/descriptor matrix tests
- route-B no-sequence fixture
- route-C/D schema-only fixtures
- stale target/support/bootstrap/segment/View/Prompt/backend rejection
- fallback identity/reason validation
- provider result boundary tests
- single diagnostics authority tests
- Decision-to-ProposalSet digest/attempt membership tests
- proposal ID collision across attempts regression
- unavailable-versus-technical-failure contract tests
- publication command membership tests

# Non-goals

- No production KeyViewPromptSynthesizer implementation.
- No SAM inference.
- No ProposalDecision algorithm implementation.
- No ViewAssessment algorithm changes.
- No Stable Mask publication execution.
- No route-A fallback execution.
- No controller/scheduler migration.
- No Gallery implementation.
- No tracker, Bridge View, reference memory, or repropagation.
- No P/N/V or Gaussian ownership.
