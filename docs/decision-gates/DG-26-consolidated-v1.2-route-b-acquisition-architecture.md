# DG-26 — Consolidated v1.2 Route-B Acquisition Architecture

- **Status:** CLOSED
- **Date:** 2026-07-30
- **Applies to:** `ai-select-v1`
- **Normative spec:** `docs/specs/ai-select-final-spec-v1.2.md`
- **Supersedes for implementation:** DG-23 through DG-25 where they conflict with this decision
- **Historical inputs:** Final Spec v1.1 + Amendments 001–005

## Decision question

How should the selected route-B sparse-Key-View architecture be made implementation-ready while preserving a clean future path for route-C tracker and route-D hybrid experiments?

## Decision

Adopt the following production chain:

```text
Confirmed object-level Anchor Stable Mask
→ VisibleTargetSupportArtifact
→ TargetBootstrapArtifact
→ adaptive sparse Key Views
→ KeyViewPromptSynthesizer
→ KeyViewPromptArtifact
→ route-B per-view SAM provider
→ KeyViewMaskProposalSet
→ KeyViewMaskDecisionPolicy
→ ViewAssessmentPolicy
→ MaskPublicationCoordinator
→ Included Stable View Annotations
→ final P/N/V Gaussian lifting
```

Route B is the selected v1 production route. Route A remains a technical fallback and regression baseline. Routes C and D remain future experiments behind explicit backend extension contracts and a later experiment-backed ADR.

## Decision 1 — explicit visible-support artifact

Ticket 08 MUST publish a versioned `VisibleTargetSupportArtifact` containing bounded, replayable Anchor-visible 3D support samples.

`TargetBootstrapArtifact` remains a light summary and references the support artifact by digest.

The support artifact:

- may contain world positions, source pixels, depth, sample weight, and optional stable-Gaussian provenance;
- may guide framing, planning, Prompt synthesis, and conservative Working Set seeding;
- is not Gaussian ownership;
- cannot classify a Gaussian as Selected, Rejected, Uncertain, or Out of Scope;
- cannot hard-bound the later Evidence Working Set.

## Decision 2 — independent Prompt synthesis layer

Ticket 08B MUST implement `KeyViewPromptSynthesizer` as a layer separate from orchestration and inference.

```text
VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
+ Key-View CameraBinding
+ adapter capabilities
+ Prompt synthesis policy
→ KeyViewPromptArtifact
```

The acquisition provider consumes an immutable `KeyViewPromptArtifact`. It does not recompute or reinterpret raw 3D support.

## Decision 3 — candidates before decision

A per-view acquisition provider returns `KeyViewMaskProposalSet`, not one hidden Top-1 Mask.

A separate `KeyViewMaskDecisionPolicy` produces:

```text
selected
ambiguous
unavailable
```

Rules:

- exact and near-duplicate proposals are clustered before decision;
- raw model score is a representative/tie-break diagnostic, not correctness probability;
- materially distinct plausible proposals remain `ambiguous`;
- ambiguous output does not publish an arbitrary Stable Mask;
- only `selected` proceeds to `ViewAssessmentPolicy`.

## Decision 4 — backend bundle and registry

Use an explicit backend bundle:

```ts
interface MaskAcquisitionBackend {
    readonly descriptor: MaskAcquisitionBackendDescriptor;
    readonly perView?: MultiViewMaskAcquisitionProvider;
    readonly sequence?: SequenceMaskAcquisitionExtension;
}

interface MaskAcquisitionBackendRegistry {
    resolveBackend(backendId: string): MaskAcquisitionBackend;
}
```

Route mapping:

```text
B = perView required, sequence absent
C = sequence required, perView optional fallback/recovery
D = perView required, sequence required
```

Capabilities MUST be derived from and validated against the actual bundle structure. Independent booleans cannot contradict the implemented extensions.

## Decision 5 — route-A fallback B2

Automatic route-A fallback is permitted only after a route-B technical or capability failure, including:

- backend unavailable;
- required route-B Prompt capability unavailable;
- route-B request explicitly rejected for technical compatibility;
- recoverable inference failure;
- route-B OOM when route A can run within a declared lower-resource envelope.

Automatic fallback is prohibited for semantic or quality outcomes, including:

- ambiguous proposals;
- neighbour-object contamination;
- Prompt inconsistency;
- fragmentation or boundary clipping;
- `ViewAssessment = Review`;
- an existing User Confirmed Stable Mask.

Fallback creates a distinct attempt with `fallbackOfAttemptId` and a structured reason. Route-A output traverses the same ProposalSet → Decision → Assessment → Publication chain. It may become Auto Good only under the same or stricter quality and contamination thresholds.

## Decision 6 — split 08A and 08B

Ticket ownership is:

```text
08
= VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
+ SparseKeyViewPlanSegment

08A
= acquisition artifact/interface contracts
+ Backend Bundle / Registry
+ per-view and sequence extension schemas
+ validators, digests, golden vectors

08B
= KeyViewPromptSynthesizer
+ route-B SAM provider
+ KeyViewMaskDecisionPolicy
+ ViewAssessment integration
+ MaskPublicationCoordinator
+ route-A B2 fallback
+ controller/scheduler integration
+ production validation
```

Dependency chain:

```text
08 → 08A → 08B → 09 → 12 → 14
```

## Decision 7 — 07B and 08 run in parallel

Ticket 07B is interaction hardening and does not produce an artifact consumed by Ticket 08.

After Ticket 07A:

```text
07A → 07B
07A → 08
```

Ticket 07B remains a prerequisite for complete Generated/User-added View Prompt/Edit correction UX and final release hardening, but it does not block bootstrap, planning, contracts, or route-B backend development.

## Decision 8 — complete layer separation

The following are distinct components:

```text
Prompt synthesis
≠ model candidate generation
≠ target-instance proposal decision
≠ Mask quality assessment
≠ Stable Mask publication
≠ Participation
```

The provider returns proposals and backend diagnostics only. It does not return `ViewAssessmentResult` or publish a Stable Mask.

`MaskPublicationCoordinator` applies the state transition:

```text
selected + Good
→ Auto Good Stable Mask + Included

selected + Review
→ Auto Review Stable Mask + Excluded

ambiguous
→ retain ProposalSet for Review, no new Stable Mask, Excluded

unavailable
→ Mask Failed, no new Stable Mask
```

A current User Confirmed Stable Mask cannot be silently replaced.

## Decision 9 — one current normative specification

`Final Spec v1.2` is the only current product/engineering specification.

Final Spec v1.1 and Amendments 001–005 remain historical records. DGs remain decision rationale. Implementation agents and ticket acceptance MUST use Final Spec v1.2 directly rather than merging the historical supersession chain.

Traceability is rebuilt as one v1.2 mapping. The v2.7 overlay is retired.

## Required implementation order

```text
04B
→ 07A
→ parallel: 07B and 08
→ 08A
→ 08B
→ 09
→ 11 / 12
→ 14
→ downstream hardening
```

## Future C/D boundary

A later C/D experiment may reuse:

- authoritative RGB and CameraBinding artifacts;
- backend registry and identity envelope;
- per-view proposal, decision, assessment, and publication contracts;
- Stable Mask registry;
- final downstream P/N/V metrics.

A separate ADR is mandatory before production adoption. It must define sequence ordering, auxiliary/Bridge frames, resource envelope, session identity, reference-memory semantics, correction references, propagation atomicity, drift handling, fallback, retry, cancellation, teardown, and migration.

## Non-goals

DG-26 does not:

- choose or implement a tracker;
- require an A/B/C/D comparison before route B;
- make 3D support or acquisition confidence ownership Evidence;
- require Bridge Views or dense trajectories;
- create correction reference memory from ordinary Confirm;
- change final P/N/V Gaussian ownership semantics;
- require arbitrary part-level selection or whole-image inventory.
