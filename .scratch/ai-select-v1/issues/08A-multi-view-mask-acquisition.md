# 08A — 3D-guided per-Key-View SAM + extensible acquisition backend seam

Status: planned — route B selected by DG-25 / Amendment 005

Blocked by: 08

Blocks: 09

## Final Spec mapping

- Final Spec v1.1 §§18–20, 23–24, 27–32
- Final Spec v1.1 Amendments 003–005
- DG-24 and DG-25
- Ticket 06 progressive Generated View baseline
- Ticket 07 ViewAssessmentPolicy

## Purpose

Turn a confirmed object-level Anchor Stable Mask, a TargetBootstrapArtifact, and sparse authoritative Key-View RGBs into reliable per-view object Masks for final P/N/V lifting.

Proceed directly with route B:

```text
enhanced 3D-guided independent SAM inference per Key View
```

Do not block this ticket on an A/B/C/D comparison. Route A remains a regression baseline and fallback. Routes C and D are future experiments, but this ticket must implement the interfaces and orchestration seams needed to add them without rewriting the route-B pipeline.

## Inputs / preconditions

- confirmed Anchor Stable Mask;
- current Target Context and exact Anchor/RGB/Mask identity;
- Ticket 08 TargetBootstrapArtifact;
- Ticket 08 immutable SparseKeyViewPlanSegment artifacts;
- authoritative RGB for every Key View;
- Ticket 04B truthful visual-Prompt capabilities;
- Ticket 07 local Mask assessment;
- Stable Mask registry and stale-result gate;
- current projected-support + single-frame SAM baseline.

## Outputs / handoff artifacts

- versioned backend-neutral acquisition capability contract;
- route-B `MultiViewMaskAcquisitionProvider` implementation;
- optional `SequenceMaskAcquisitionExtension` contract for future C/D experiments;
- versioned 3D-guided Prompt synthesis policy;
- per-Key-View acquisition attempts and diagnostics;
- progressive per-view Mask proposal / Stable / Review / Failed states;
- explicit backend/model/runtime/fallback identity;
- route-B quality, latency, resource, and downstream Gaussian validation report;
- exact dirty/stale dependencies for Ticket 12;
- generic acquisition status for Ticket 09.

# Phase 0 — acquisition contracts and extension seams

## Backend capabilities

Define a versioned capability contract equivalent to:

```ts
type MaskAcquisitionBackendKind =
    | 'per-view-sam'
    | 'sequence-tracker'
    | 'hybrid';

interface MaskAcquisitionCapabilities {
    schemaVersion: number;
    backendKind: MaskAcquisitionBackendKind;
    backendId: string;
    modelId: string;
    runtimeBuildId: string;

    supportsIndependentViews: boolean;
    supportsSequenceSessions: boolean;
    supportsReferenceUpdates: boolean;
    supportsAuxiliaryFrames: boolean;
    supportsRepropagation: boolean;

    capabilityDigest: string;
}
```

Route B advertises:

```text
backendKind = per-view-sam
supportsIndependentViews = true
supportsSequenceSessions = false
supportsReferenceUpdates = false
supportsAuxiliaryFrames = false
supportsRepropagation = false
```

Capabilities are authoritative. Unsupported operations fail closed before inference or state mutation.

## Base per-view provider

Define and implement:

```ts
interface MultiViewMaskAcquisitionProvider {
    getCapabilities(): MaskAcquisitionCapabilities;

    acquireView(
        request: PerViewMaskAcquisitionRequest
    ): Promise<PerViewMaskAcquisitionResult>;
}
```

`PerViewMaskAcquisitionRequest` binds:

```text
targetContextId + contextRevision
scene / splat dependency identity
Anchor CameraBinding + RGB digest
Anchor Stable Mask digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
Key-View CameraBinding + RGB digest
adapter capability digest
Prompt synthesis policy digest
PromptState digest
backend / model / adapter / runtime identity
attempt identity
```

The result binds the same identity plus Mask artifact, assessment/diagnostic, fallback, and result digests.

## Optional sequence/reference extension

Define, validate, and route an optional extension contract equivalent to:

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

Intended future mapping:

```text
Route B
= acquireView only

Route C
= sequence extension
  + optional acquireView fallback/recovery

Route D
= acquireView for Key-View references
  + sequence extension between references
```

Route B must not create fake sequence sessions or no-op reference updates. It advertises no sequence capability and returns a structured unsupported-capability result.

Phase 0 implements contracts, validators, dispatch seams, and capability negotiation. It does not implement a tracker.

# Phase 1 — route-B 3D-guided Prompt synthesis

For every Key View, synthesize a deterministic PromptState from supported inputs such as:

- projected Anchor visible-support positive points;
- projected target center and extent;
- positive Box / ROI;
- local negative points or negative region outside the projected target;
- compatible projected Mask input when supported;
- object scale, clipping, and boundary diagnostics.

Prompt synthesis binds:

```text
targetContextId
scene / splat revision
Anchor CameraBinding + RGB digest
Anchor Stable Mask digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
Key-View CameraBinding + RGB digest
adapter capability digest
Prompt synthesis policy digest
PromptState digest
model / adapter / runtime identity
attempt identity
```

Unsupported Prompt types fail closed and are never silently dropped or converted.

Bootstrap support is localization context. It is not ownership and does not hard-bound the later Evidence Working Set.

# Phase 2 — independent route-B execution

Each Key View runs one independent prompt-conditioned route-B attempt. It does not require adjacent frames, tracker memory, Bridge Views, or a dense sequence.

The route may produce:

```text
Mask Generating
Auto Stable Mask
Mask Review
Mask Failed
```

RGB Ready never waits for Mask acquisition.

Each attempt is independently retryable. Same-attempt replay is idempotent; explicit Retry creates a new attempt.

# Phase 3 — publication and assessment

Successful output is validated and atomically published as one bound per-view Mask revision under the existing Mask registry.

Automatic acquisition must not silently replace a current user-confirmed Stable Mask. It may publish a Review proposal or require explicit refresh/acceptance under the selected policy.

Mask failure preserves View/RGB/frustum and prior Stable Mask.

Acquisition provenance records the generic identity envelope. Gallery and Mask registry do not need to understand tracker internals.

# Route-A fallback

The Ticket 06 projected-support + single-frame SAM route remains runnable as:

- regression baseline;
- declared fallback when route-B Prompt synthesis or inference is unavailable;
- manual recovery initializer where useful.

Fallback identity and diagnostics are explicit. A fallback result is not represented as route B.

# Future route-C / route-D experiments

C and D are not implemented by this ticket.

A future experiment may plug into the capability and sequence/reference seams without replacing:

- authoritative RGB and CameraBinding artifacts;
- route-B `acquireView` contract;
- common result identity envelope;
- Mask artifact validation;
- per-view Stable publication and assessment;
- Ticket 09 generic acquisition status;
- Ticket 12 generic dirty-state lifecycle;
- final P/N/V downstream evaluation.

A separate experiment-backed ADR is required before C or D becomes a production capability. It must define auxiliary frames, transition/resource envelope, sequence lifecycle, reference memory, identity drift, propagation atomicity, fallback, and teardown.

Confirming a per-view correction does not automatically enter future tracker memory. `Use as Tracking Reference` remains a separate capability-gated action if a later backend supports it.

# Acceptance criteria

## Route-B implementation

- [ ] Route B is implemented without an A/B/C/D comparison gate.
- [ ] 3D-guided Prompt synthesis is deterministic and artifact-bound.
- [ ] Positive support is visibility-aware and clipped to the exact Key View.
- [ ] Box/ROI and local-negative constraints are used only when adapter capabilities support them.
- [ ] Prompt diagnostics explain insufficient support, projection loss, edge clipping, and likely neighbour contamination.
- [ ] Each Key View has an independent attempt and Retry identity.
- [ ] Same-attempt replay is idempotent; explicit Retry creates a real new attempt.
- [ ] RGB Ready does not wait for acquisition.
- [ ] Success atomically publishes only a bound per-view Mask revision.
- [ ] Failure preserves RGB/View/frustum/prior Stable Mask.
- [ ] No partial Mask artifact becomes Stable.
- [ ] User-confirmed Stable Mask is not overwritten silently.
- [ ] Key-View role and backend score do not override Ticket 07 assessment or Participation.

## Extension readiness

- [ ] `MaskAcquisitionCapabilities` is versioned, digest-bound, and truthfully advertised.
- [ ] Route B implements `MultiViewMaskAcquisitionProvider.acquireView`.
- [ ] Optional sequence/reference request and result schemas have structural validators and identity golden vectors.
- [ ] Backend dispatch distinguishes per-view, sequence, and hybrid kinds without route-specific Gallery or Mask-registry branching.
- [ ] Unsupported sequence/reference operations fail closed before state mutation.
- [ ] Route B never fabricates session/reference/auxiliary-frame fields.
- [ ] Controller orchestration separates RGB rendering, per-view acquisition, optional future sequence dispatch, and Mask publication.
- [ ] Companion scheduling supports backend dispatch, replay, cancellation, and cleanup without assuming every backend is stateless.

## Validation

- [ ] Frozen sparse-Key-View scenes and review protocol are versioned.
- [ ] Route-B per-view acceptable-mask rate and neighbour contamination are reported.
- [ ] Manual correction burden, latency, peak VRAM, fallback rate, and failure recovery are reported.
- [ ] Final Gaussian precision/recall, background contamination, Mixed/Uncertain ratio, and Add/Remove burden proxy are reported.
- [ ] Route A remains a tested fallback.
- [ ] C/D implementation or comparison is not required for closure.

## Affected implementation seams

- [ ] `generated-view-controller.ts` separates RGB rendering from acquisition jobs and exposes an optional future sequence-orchestration seam.
- [ ] `generated-view-service.ts` exposes per-view contracts, backend capability identity, and optional sequence/reference schemas.
- [ ] Companion state owns bounded model scheduling, backend dispatch, replay, cancellation, and cleanup.
- [ ] `mask-registry.ts` records generic acquisition provenance without tracker-specific semantics.
- [ ] readiness/capability negotiation reports route B and optional sequence/reference support.

# Failure / recovery criteria

- Acquisition backend unavailable: preserve completed Views/RGB/Masks; offer route-A fallback/manual correction/Exclude.
- OOM/cancellation: publish no partial Stable Mask; retain prior artifacts; reject late results.
- Insufficient projected support: mark Review/Failed with retry, adjusted View, manual Prompt, or Exclude recovery.
- Neighbour-instance risk: fail closed to Review, not silent Auto Good.
- Stale Anchor/bootstrap/segment/View/Prompt/backend result: discard.
- Unsupported sequence/reference method: return structured capability failure with no state mutation.

# Validation commands and fixtures

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run build`
- locked-runtime route-B acquisition smoke
- frozen sparse-Key-View route-B benchmark
- table/chairs and similar-instance contamination regression
- occlusion/reappearance and poor-render regression
- Prompt synthesis digest golden vectors
- capability and optional sequence/reference schema golden vectors
- stale Anchor/bootstrap/segment/View/Prompt/backend rejection
- route-A fallback regression
- final P/N/V Gaussian outcome validation

# Non-goals

- No camera generation; Ticket 08 owns it.
- No Anchor ProposalDecision; Ticket 07A owns it.
- No A/B/C/D route-selection spike.
- No tracker, Bridge View, dense trajectory, reference memory, or repropagation implementation.
- No Gallery implementation; Ticket 09 owns presentation.
- No dirty-state orchestration; Ticket 12 owns it.
- No P/N/V Evidence or Gaussian ownership.
- No whole-image object inventory.
- No arbitrary part-level selection requirement.
- No automatic Re-Lift.
