# 12 — Explicit tracker Repropagate + Evidence Dirty / Candidate Stale model

Status: blocked — waits for 08A and 09

Blocked by: 08A, 09, 07, 05

## Final Spec mapping

- Final Spec v1.1 §§11, 18, 24
- Final Spec v1.1 Amendment 003
- DG-10, DG-20, DG-23
- MVP Phase 4

## Inputs / preconditions

- Stable Masks and Participation
- AIView Camera/RGB identity
- Current target/reference identity
- View registry
- TrackingSequencePlan
- MaskTrackingRun identity
- Confirmed Anchor and CorrectionReferences
- Tracker backend/model/runtime/policy identity

## Outputs / handoff artifacts

- `propagationDirty`
- `evidenceDirtyViewIds`
- `liftDirty`
- `candidateStale`
- explicit `Update Multi-view Masks`
- bound full/range tracker repropagation run

## What to build

Implement explicit recompute semantics including per-view Evidence invalidation and object-tracker repropagation. Repropagate remains explicit and never auto-Re-Lifts. Stable input changes mark only dependent tracking/Evidence/Candidate state dirty.

## Acceptance criteria

### Dirty-state semantics

- [ ] Domain exposes/derives propagationDirty, evidenceDirtyViewIds, liftDirty, candidateStale, and contextSuspended.
- [ ] Editing an unconfirmed Mask changes none of those formal states and never mutates tracker memory.
- [ ] Confirming a normal View Stable Mask marks that View Evidence dirty and Lift dirty.
- [ ] Confirming changed Anchor Stable Mask marks propagation dirty, Anchor Evidence dirty, and Lift dirty.
- [ ] Confirming a View as a CorrectionReference marks propagation dirty and records reference revision.
- [ ] Excluding an Included View preserves its artifact and marks Lift dirty.
- [ ] Including a View with Stable Mask marks Lift dirty and Evidence dirty when no exact artifact exists.
- [ ] Adding a View with no Stable Mask changes neither Evidence nor Lift dirtiness.
- [ ] New CameraBinding/RGB revision marks that View Evidence dirty and Lift dirty and invalidates dependent tracking results.
- [ ] Gallery/frustum/sequence browsing changes no dirty state.

### Explicit tracker repropagate

- [ ] `Update Multi-view Masks` consumes current Anchor Stable Mask, confirmed CorrectionReferences, TrackingSequencePlan, and tracker backend/model/runtime/policy identity.
- [ ] Repropagate creates a new MaskTrackingRun/attempt and never mutates the old run in place.
- [ ] Same-attempt replay may be idempotent; explicit Retry creates a real new attempt.
- [ ] Full-sequence and bounded-range repropagation are explicit policy modes.
- [ ] Bounded-range mode records affected sequence interval and reference dependencies.
- [ ] A Bridge View correction may become reference memory while remaining Excluded from Lift.
- [ ] Repropagate publishes replacement Mask revisions atomically under the declared publication contract.
- [ ] Repropagate may refresh assessment/Participation/readiness inputs but never auto-produces Evidence or Candidate.
- [ ] Late results with stale target/Anchor/plan/reference/backend identity are discarded.
- [ ] Repropagate failure preserves prior Stable Masks and matching Evidence/Candidate state.
- [ ] Tracker technical failure remains distinct from valid Review/identity-drift suspicion.

### Evidence/Candidate lifecycle

- [ ] Only confirmed Stable Mask/Participation/Camera changes invalidate formal per-view Evidence.
- [ ] A completed repropagate marks matching changed View Evidence dirty and Lift dirty.
- [ ] Repropagate never automatically Re-Lifts.
- [ ] Bridge role alone does not dirty or include Evidence; only Stable/Participation changes do.
- [ ] Tracker confidence/reference status is not formal P/N/V Evidence.

## Failure / recovery criteria

- [ ] No partial proposed Mask or Evidence becomes stable.
- [ ] Cancellation/restart correctness relies on binding rejection, not cancellation success.
- [ ] Tracker OOM/unavailable preserves previous Stable Masks and offers fallback/manual/exclude recovery.
- [ ] Identity-drift Review remains a Mask assessment state, not a technical failure.
- [ ] Stale sequence/reference result cannot attach to a newer AIView revision.

## Validation

- npm test
- npm run test:companion
- npm run lint
- Dependency-table tests matching Final Spec v1.1 §24 and Amendment 003
- Editing vs Confirmed CorrectionReference dirty-state tests
- Full/range repropagate atomicity tests
- Stale Anchor/plan/reference/backend result rejection
- Repropagate failure preserving prior Stable/Evidence/Candidate
- Bridge reference-memory without Participation regression

## Non-goals

- No tracker backend implementation; Ticket 08A owns it.
- No automatic Re-Lift.
- No Evidence computation or Candidate implementation.
- No continuous propagation during Paint/Prompt editing.