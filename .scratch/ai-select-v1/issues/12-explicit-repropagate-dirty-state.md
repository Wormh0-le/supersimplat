# 12 — Explicit Mask refresh + Evidence Dirty / Candidate Stale model

Status: blocked — waits for 08A and 09

Blocked by: 08A, 09, 07, 05

## Final Spec mapping

- Final Spec v1.1 §§11, 18, 24
- Final Spec v1.1 Amendments 003 and 004
- DG-10, DG-20, DG-24
- MVP Phase 4

## Inputs / preconditions

- Stable Masks and Participation
- AIView Camera/RGB identity
- Current target identity
- View registry
- immutable SparseKeyViewPlanSegment identity
- TargetBootstrapArtifact identity
- selected Mask acquisition backend/model/runtime/policy identity
- optional tracker/reference identity only when capability exists

## Outputs / handoff artifacts

- `maskAcquisitionDirtyViewIds`
- optional `propagationDirty`
- `evidenceDirtyViewIds`
- `liftDirty`
- `candidateStale`
- explicit per-view `Refresh Auto Mask`
- optional explicit `Update Multi-view Masks` only when propagation capability exists

## What to build

Implement explicit recompute semantics for the default independent per-Key-View acquisition route and capability-gated optional propagation.

Stable input changes mark only dependent Mask/Evidence/Candidate state dirty. No refresh action automatically Re-Lifts.

## Acceptance criteria

### Generic dirty-state semantics

- [ ] Domain exposes/derives `maskAcquisitionDirtyViewIds`, optional `propagationDirty`, `evidenceDirtyViewIds`, `liftDirty`, `candidateStale`, and `contextSuspended`.
- [ ] Editing an unconfirmed Mask changes none of those formal states and never mutates optional tracker memory.
- [ ] Confirming a normal View Stable Mask marks that View Evidence dirty and Lift dirty.
- [ ] Confirming changed Anchor Stable Mask invalidates TargetBootstrapArtifact, planner segments, dependent auto-acquisition work, Anchor Evidence, and Lift.
- [ ] Excluding an Included View preserves its artifacts and marks Lift dirty.
- [ ] Including a View with Stable Mask marks Lift dirty and Evidence dirty when no exact artifact exists.
- [ ] Adding a View with no Stable Mask changes neither Evidence nor Lift dirtiness.
- [ ] New CameraBinding/RGB revision marks that View acquisition and Evidence dirty and Lift dirty.
- [ ] Gallery/frustum/plan browsing changes no dirty state.
- [ ] `Generate More` appends a segment without dirtying prior completed View Masks.

### Default per-view refresh

- [ ] `Refresh Auto Mask` consumes exact View RGB/Camera, Anchor Stable Mask, TargetBootstrapArtifact, plan segment, Prompt synthesis policy, and acquisition backend identity.
- [ ] Refresh creates a new attempt and never mutates the old attempt in place.
- [ ] Same-attempt replay may be idempotent; explicit Retry creates a real new attempt.
- [ ] Refresh affects only the selected View unless the selected backend explicitly declares wider dependencies.
- [ ] A refreshed automatic result never silently overwrites a current user-confirmed Stable Mask.
- [ ] Successful Stable replacement marks only matching per-view Evidence dirty and Lift dirty.
- [ ] Failure preserves prior Stable Mask and matching Evidence/Candidate state.
- [ ] Late results with stale target/Anchor/bootstrap/segment/View/Prompt/backend identity are discarded.

### Correction semantics

- [ ] Confirming a per-view manual correction publishes a Stable Mask and dirties only that View Evidence/Lift.
- [ ] Confirming a correction does not automatically create tracker memory or dirty unrelated Views.
- [ ] If optional tracker/hybrid capability exists, `Use as Tracking Reference` is a separate explicit action.
- [ ] Only that explicit action creates/replaces a CorrectionReference and may set `propagationDirty=true`.

### Optional propagation

- [ ] `propagationDirty` and `Update Multi-view Masks` are absent/disabled when the selected route has no propagation capability.
- [ ] If enabled, Update consumes exact current Anchor, confirmed CorrectionReferences, acquisition plan, and tracker backend/model/runtime/policy identity.
- [ ] Repropagate creates a new bound run/attempt and never mutates an old run.
- [ ] Full/range/segment propagation modes are explicit policy choices.
- [ ] Repropagation never automatically produces Evidence or Candidate.
- [ ] Repropagate failure preserves prior Stable Masks and matching Evidence/Candidate.
- [ ] Tracker technical failure remains distinct from valid Review/identity-drift suspicion.

### Evidence/Candidate lifecycle

- [ ] Only confirmed Stable Mask/Participation/Camera changes invalidate formal per-view Evidence.
- [ ] Mask backend scores, optional tracker confidence, and reference status are not formal P/N/V Evidence.
- [ ] No Mask refresh or optional propagation automatically Re-Lifts.

## Failure / recovery criteria

- [ ] No partial proposed Mask or Evidence becomes stable.
- [ ] Cancellation/restart correctness relies on binding rejection, not cancellation success.
- [ ] Acquisition OOM/unavailable preserves previous Stable Masks and offers fallback/manual/exclude recovery.
- [ ] Optional identity-drift Review remains a Mask assessment state, not a technical failure.
- [ ] Stale bootstrap/segment/View/Prompt/backend result cannot attach to a newer AIView revision.

## Validation

- npm test
- npm run test:companion
- npm run lint
- Dependency-table tests matching Final Spec v1.1 §24 and Amendment 004
- Per-view Refresh attempt/replay/stale-result tests
- Correction Confirm without propagation-dirty regression
- Optional reference action / repropagate tests only when capability exists
- Failure preserving prior Stable/Evidence/Candidate
- Generate More append-only no-dirty regression

## Non-goals

- No acquisition backend implementation; Ticket 08A owns it.
- No mandatory tracker or repropagation action.
- No automatic Re-Lift.
- No Evidence computation or Candidate implementation.
- No continuous refresh while Paint/Prompt editing.
