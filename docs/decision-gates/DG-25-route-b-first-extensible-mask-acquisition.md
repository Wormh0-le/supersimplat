# DG-25 — Route-B-First Mask Acquisition with C/D Extension Seams

- **Status:** CLOSED
- **Date:** 2026-07-30
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendments 001–005
- **Supersedes:** DG-24 requirements that made an A/B/C/D comparison or acquisition-route ADR a prerequisite for Ticket 08A production closure
- **Default acquisition owner:** Ticket 08A
- **Future tracker/hybrid decision owner:** separate future experiment + ADR, not Ticket 08A's current closure gate

## Decision question

Should Ticket 08A first compare four acquisition routes before implementation, or should AI Select implement enhanced 3D-guided independent SAM per Key View now while preserving clean extension points for later tracker and hybrid experiments?

## Decision

Adopt a route-B-first implementation:

```text
Confirmed object-level Anchor Stable Mask
→ TargetBootstrapArtifact
→ adaptive sparse Key Views
→ deterministic 3D-guided Prompt synthesis
→ independent prompt-conditioned SAM inference per Key View
→ per-view assessment / correction / Participation
→ Included Stable View Annotations
→ final P/N/V Gaussian lifting
```

Route B is no longer a candidate awaiting comparison. It is the selected v1 production route.

The existing projected-support + single-frame SAM path remains route A as a regression baseline and fallback. Routes C and D remain future experiments:

```text
C = object-level VOS tracker over an ordered/dense rendered sequence
D = independent Key-View SAM references + tracker propagation
```

C or D may be adopted only through a later experiment-backed ADR. Their evaluation does not block implementation or closure of route B.

## Decision 1 — no route-selection spike gate

Ticket 08A MUST NOT require an A/B/C/D comparison before implementing or closing route B.

Ticket 08A still validates route B against locked quality, latency, resource, contamination, and downstream Gaussian metrics. This is production validation, not route selection.

## Decision 2 — backend-neutral core contract

The implementation MUST introduce a backend-neutral acquisition seam rather than embedding route-B logic directly into Gallery, planner, or Mask-registry state.

The required base contract is equivalent to:

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

interface MultiViewMaskAcquisitionProvider {
    getCapabilities(): MaskAcquisitionCapabilities;

    acquireView(
        request: PerViewMaskAcquisitionRequest
    ): Promise<PerViewMaskAcquisitionResult>;
}
```

Route B MUST fully implement `acquireView` and advertise:

```text
supportsIndependentViews = true
supportsSequenceSessions = false
supportsReferenceUpdates = false
supportsAuxiliaryFrames = false
supportsRepropagation = false
```

Unsupported operations fail closed. They are never silently emulated, ignored, or represented as successful no-ops.

## Decision 3 — optional sequence/reference extension contract

The codebase MUST define an optional extension contract sufficient for future C and D experiments without requiring a route-B rewrite.

The extension is equivalent to:

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
= MultiViewMaskAcquisitionProvider.acquireView

Route C
= SequenceMaskAcquisitionExtension
  + optional per-view recovery through acquireView

Route D
= acquireView for Key-View references
  + SequenceMaskAcquisitionExtension for propagation between references
```

The extension contract is defined and wired through capability negotiation now. A tracker implementation, sequence session, Bridge View generation, reference memory UI, and repropagation behavior are not implemented unless a later ADR selects C or D.

## Decision 4 — common identity envelope

Every route MUST use a common immutable identity envelope so results remain comparable and stale-safe:

```text
targetContextId + contextRevision
scene / splat dependency identity
Anchor CameraBinding + RGB + Stable Mask digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
View CameraBinding + RGB digest
Prompt / reference-set digest
backend kind / backend ID
model / adapter / runtime identity
policy digest
attempt or sequence-run identity
result artifact digest
```

Sequence-only fields remain absent for route B rather than populated with invented values.

## Decision 5 — orchestration boundary

Ticket 08A MUST separate:

```text
RGB rendering jobs
per-view Mask acquisition jobs
optional future sequence-session orchestration
Mask publication / assessment
```

The route-B controller may schedule independent per-view jobs. It must not assume that all future backends are stateless or per-view-only.

The Companion scheduler and protocol layer must therefore support backend dispatch and capability checking without requiring Gallery or Mask registry to understand tracker internals.

## Decision 6 — future C/D experimentation

A future C/D experiment may reuse:

- the same authoritative RGB and CameraBinding artifacts;
- the same acquisition-result envelope;
- the same per-view Mask publication and assessment path;
- the same stale-result and attempt identity rules;
- optional sequence/reference methods;
- the same final P/N/V downstream evaluation.

A later ADR is required before C or D becomes a production capability. That ADR must define sequence ordering, auxiliary/Bridge frames, transition/resource limits, reference memory, drift handling, propagation atomicity, fallback, and lifecycle cost.

## Decision 7 — validation scope for Ticket 08A

Ticket 08A validates route B directly:

- deterministic 3D-guided Prompt synthesis;
- per-Key-View acceptable-mask rate;
- neighbouring-object contamination;
- manual correction burden;
- latency and peak VRAM;
- stale-result rejection and replay;
- final Gaussian precision / recall;
- background Gaussian contamination;
- Mixed / Uncertain ratio;
- user Add / Remove burden proxy.

It does not need to implement or benchmark routes C and D to close.

## Consequences

Positive:

- removes a speculative research gate from the current product path;
- delivers the simplest D-double-prime implementation first;
- keeps route A available as a known fallback;
- prevents tracker-specific lifecycle complexity from leaking into v1 by default;
- preserves clean future experiment seams for C and D;
- keeps final Gaussian quality as the downstream acceptance criterion.

Costs:

- acquisition protocols become slightly more abstract than a route-B-only function;
- capability and backend identity must be explicit from the start;
- optional sequence methods require contract tests even though no sequence backend is currently enabled.

## Required implementation sequence

```text
08 sparse Key-View planner
→ 08A acquisition contracts + route-B implementation
→ 09 Gallery / acquisition-status presentation
→ 12 per-view refresh / dirty lifecycle
→ 14 reference P/N/V Lift
```

Future, independently scheduled:

```text
C/D experiment
→ downstream comparison
→ optional adoption ADR
→ optional sequence/reference implementation
```

## Non-goals

DG-25 does not:

- choose or implement a tracker;
- require A/B/C/D comparison before route B;
- require Bridge Views or dense trajectories;
- create tracker memory from ordinary correction Confirm;
- make backend confidence formal P/N/V Evidence;
- change final Gaussian ownership semantics;
- require whole-image object inventory or part-level selection.
