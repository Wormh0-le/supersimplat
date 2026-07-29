# 08A — Object-level multi-view Mask tracking + correction memory

Status: planned — architecture closed by DG-23; implementation backend remains spike-gated

Blocked by: 08

Blocks: 09

## Final Spec mapping

- Final Spec v1.1 §§18–20, 23–24, 27–32
- Final Spec v1.1 Amendment 003
- DG-23
- Ticket 06 progressive Generated View tracer bullet
- Ticket 07 ViewAssessmentPolicy

## Purpose

Turn a confirmed object-level Anchor Stable Mask and an ordered Key/Bridge TrackingSequencePlan into progressively published multi-view Masks that maintain one object identity across view changes.

Ticket 08A replaces neither final P/N/V lifting nor the current Ticket 06 baseline. It adds the production object-level tracking path and retains projected-support + single-frame SAM as a declared fallback and benchmark baseline.

## Inputs / preconditions

- confirmed Anchor Stable Mask;
- current Target Context and exact Anchor/RGB/Mask identity;
- Ticket 08 TargetBootstrapArtifact;
- Ticket 08 ordered TrackingSequencePlan;
- authoritative RGB for each sequence View;
- Ticket 07 local Mask assessment;
- Stable Mask registry and stale-result gate;
- current projected-support + single-frame SAM baseline.

## Outputs / handoff artifacts

- bounded tracker-backend spike report;
- selected tracker implementation ADR;
- versioned MaskTrackingRun;
- progressive per-view tracked Mask proposal/status;
- tracker diagnostics and identity-drift suspicion;
- confirmed CorrectionReference integration;
- single-frame fallback diagnostics;
- exact dependency and stale-result identity for Ticket 12;
- Key/Bridge Mask states for Ticket 09.

# Phase 0 — finding-the-unknowns tracker spike

Production implementation MUST NOT begin by assuming a backend.

Compare at least:

```text
A. current projected-support + independent single-frame SAM
B. SAM video/session tracking when available in the locked runtime
C. one independent object-level VOS tracker suitable for ordered rendered views
```

The spike uses frozen authoritative gsplat RGB sequences and evaluates:

- object identity-switch rate;
- neighbour-object contamination;
- Mask drift across sequence distance;
- recovery after a confirmed correction frame;
- sensitivity to Key/Bridge transition size;
- occlusion and reappearance;
- poor/fragmented 3DGS rendering;
- latency and peak VRAM;
- deterministic replay/session reset behavior;
- deployability and dependency/licensing constraints.

The spike output MUST state:

- selected backend or explicit no-go;
- tracker model/runtime identity;
- supported frame resolution and sequence length;
- maximum declared transition envelope;
- reference-memory policy;
- correction repropagation policy;
- fallback conditions;
- resource envelope;
- known identity-drift signals.

A separate ADR locks the selected backend before the production phase closes.

# Production tracking contract

## MaskTrackingRun identity

Every run binds:

```text
targetContextId
scene/splat revision
Anchor CameraBinding + RGB digest
Anchor Stable Mask digest
TargetBootstrapArtifact digest
TrackingSequencePlan digest
tracker backend/model/runtime identity
tracking policy digest
confirmed reference Stable Mask digests
attempt identity
```

Same-attempt replay may be idempotent. Explicit Retry creates a new attempt. Late results cannot publish into a newer identity.

## Ordered execution

The run consumes the exact ordered sequence from Ticket 08.

```text
Anchor reference
→ optional Bridge frames
→ Key View
→ optional Bridge frames
→ next Key View
```

The tracker cannot reorder Views independently of the bound plan. A new order requires a new plan/run identity.

## Progressive publication

Each AIView publishes RGB independently. Tracking may then produce:

```text
Mask Tracking
Tracked Mask Review
Auto Stable Mask
Mask Failed
```

A successful Mask is validated and atomically published under the existing Mask registry. Mask failure preserves View/RGB/frustum and prior Stable Mask.

Bridge Views default to Participation=`excluded` even when a Mask is published.

## One object identity

The tracker MUST follow the Anchor object instance rather than the nearest same-category or visually similar instance.

Signals such as abrupt area/position discontinuity, incompatible projected bootstrap support, loss/reappearance, or conflict with confirmed references MAY produce an identity-drift suspicion.

Identity-drift suspicion MUST yield Review/fail-closed behavior. It MUST NOT silently publish Auto Good.

## CorrectionReference integration

Only confirmed Stable Masks may become tracker references.

```text
Editing correction
→ no tracker-memory mutation

Confirm correction
→ CorrectionReference revision
→ Ticket 12 propagationDirty
→ explicit Update Multi-view Masks
```

A correction on a Bridge View may be a tracker reference while remaining Excluded from final Lift.

## Fallback

The Ticket 06 projected-support + single-frame SAM path remains available when:

- tracker backend/runtime is unavailable;
- sequence transition is outside the supported envelope;
- tracker session fails;
- the user explicitly retries one View with the fallback;
- the spike/ADR declares a scene class unsupported.

Fallback identity and diagnostics are recorded. It is never silently represented as the selected tracker backend.

# Acceptance criteria

## Spike / ADR gate

- [ ] Frozen benchmark sequences and ground-truth/review protocol are versioned.
- [ ] Baseline and candidate trackers use the same authoritative RGB sequence.
- [ ] Identity switches, contamination, drift, correction recovery, latency, and VRAM are reported.
- [ ] Transition limits and Bridge View requirements are measured rather than guessed.
- [ ] A tracker implementation ADR is accepted before production closure.

## Tracking artifacts

- [ ] MaskTrackingRun binds all required target/Anchor/bootstrap/plan/backend/reference/attempt identities.
- [ ] Same-attempt replay is idempotent; explicit Retry creates a new attempt.
- [ ] Sequence reorder, Anchor change, correction-reference change, backend/runtime change, or Restart makes stale results unpublishable.
- [ ] Tracker confidence remains a Mask diagnostic and is not P/N/V ownership Evidence.

## Progressive View/Mask lifecycle

- [ ] RGB Ready does not wait for tracking.
- [ ] Tracking success atomically publishes only a bound per-view Mask revision.
- [ ] Tracking failure preserves RGB/View/frustum/prior Stable Mask.
- [ ] No partial Mask artifact becomes Stable.
- [ ] Bridge Views default Excluded.
- [ ] Key/Bridge role does not override Ticket 07 assessment or user Participation.

## Object identity and correction

- [ ] Similar-instance benchmark detects and counts identity switches.
- [ ] Suspected drift becomes Review or failure, not silent Auto Good.
- [ ] Confirmed correction references improve or bound subsequent propagation under the declared policy.
- [ ] Unconfirmed edits never enter tracker memory.
- [ ] Correction-reference replacement invalidates only dependent tracking work and follows Ticket 12 explicit repropagate semantics.

## Fallback

- [ ] Current projected-support + single-frame SAM remains runnable as a baseline/fallback.
- [ ] Fallback use is explicit in artifacts and diagnostics.
- [ ] Fallback failure preserves prior Stable state and exposes manual correction/exclusion.

# Failure / recovery criteria

- Tracker unavailable: preserve completed Views/RGB/Masks; offer baseline fallback or manual correction.
- Tracker OOM/cancellation: publish no partial Stable replacement; retain prior artifacts; late results rejected.
- Identity drift: mark Review/fail closed; preserve prior Stable Mask where present.
- Unsupported transition: request Bridge insertion/replanning or use bounded fallback; do not fabricate a Mask.
- Correction repropagate failure: Ticket 12 preserves prior Stable Masks, Evidence, and Candidate.
- Sequence plan stale: discard the run and require a new bound attempt.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run build`
- locked-runtime tracker smoke
- frozen rendered-sequence benchmark
- similar-instance identity-switch regression
- occlusion/reappearance regression
- correction-reference repropagation regression
- Key/Bridge transition-bound regression
- stale Anchor/plan/reference/backend result rejection
- baseline fallback regression

# Non-goals

- No camera generation or sequence planning; Ticket 08 owns it.
- No Anchor ProposalDecision; Ticket 07A owns it.
- No Gallery implementation; Ticket 09 owns presentation.
- No dirty-state orchestration or Update Multi-view Masks action; Ticket 12 owns it.
- No P/N/V Evidence or Gaussian ownership.
- No whole-image object inventory.
- No requirement for arbitrary part tracking.
- No automatic Re-Lift.