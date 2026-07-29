# 21 — Retry / cancellation / OOM / atomic publication + calibration hardening

Status: ready-for-agent — v2.5 DG-23 aligned

Blocked by: 20, 18, 08, 08A, 10, 13

## Final Spec mapping

- Final Spec v1.1 §§8, 16.2, 22–23, 28, 30–32
- Final Spec v1.1 Amendments 001 and 003
- DG-23
- ADR 0013
- MVP Phase 7 hardening

## Inputs / preconditions

- Complete v1.1 product flow
- Production Direct Evidence path
- Locked GPU/model/tracker runtime
- Frozen benchmark scenes and tracking sequences
- Fault-injection hooks

## Outputs / handoff artifacts

- End-to-end failure hardening
- Versioned policy thresholds/margins
- Tracking transition/resource envelope validation
- Stress and repeatability results
- Locked production evidence record

## What to build

Close the production-hardening loop. Calibrate existing semantics and validate retained-state/recovery behavior; introduce no new product model or tracker backend.

## Acceptance criteria

- [ ] Explicit Retry creates a true new attempt for render, tracker, and Evidence operations; same-attempt replay remains idempotent.
- [ ] Cancellation correctness never depends on cancellation completing before stale work returns.
- [ ] OOM/kernel/model failure during render/SAM/tracking/Evidence/Lift never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for RGB/View, Stable Mask, tracking run/repropagate, per-view Evidence, assessment, and Candidate.
- [ ] RGB failure preserves last valid preview only as stale/not-current and exposes Retry.
- [ ] Tracker/Mask failure preserves View/RGB/prior Stable Mask and exposes tracker Retry, declared fallback, manual correction, or Exclude.
- [ ] Suspected instance switch is Review/fail-closed, never silent Auto Good.
- [ ] Unsupported Key/Bridge transition preserves completed artifacts and triggers bounded replanning/fallback.
- [ ] Correction repropagate failure preserves old Stable Masks and matching Evidence/Candidate.
- [ ] Evidence failure preserves RGB/View/Stable/Gallery/previous Candidate and exposes recovery.
- [ ] Reference Contributor failure does not block valid RGB or successful Direct Evidence.
- [ ] View Render Failure exposes retry/replacement/exclude.
- [ ] Lift failure preserves stable inputs and leaves Candidate unchanged/not-current.
- [ ] Offline/upgrade/incompatible states preserve native SuperSplat and expose recovery.
- [ ] Stress stale-result rejection across Camera churn, plan replacement, tracker reference revision, Stop, Restart, Suspended/Undo, Evidence recomputation, and cancellation.
- [ ] Validate RGB-only versus RGB+Evidence parity for same raster identity and inputs.
- [ ] Inject Evidence RGB-digest mismatch and verify no publication/rebinding.
- [ ] Validate incompatible renderer/tracker/runtime migration blocks stale reuse until explicit recovery.
- [ ] Validate reference/production Evidence identities and baseline/production tracking identities cannot collide.
- [ ] Calibrate Camera observer placement, preview behavior, and inference resolutions.
- [ ] Calibrate planner budget, marginal gain, diversity, early stop, and Key/Bridge transition envelope.
- [ ] Validate tracker resource envelope, sequence length/resolution limits, correction recovery, and fallback threshold.
- [ ] Calibrate Core/Context/Evidence Working Set and Render Working Set parity.
- [ ] Calibrate positive/boundary/local-negative Mask policy and P/N/V classification margins.
- [ ] Validate mixed/unobserved classifications under repeated atomic accumulation.
- [ ] Calibrate Coverage, Readiness, P0/P1 assessment, and cross-view false-positive/false-negative behavior.
- [ ] Record exact raster/Evidence/runtime/model/tracker/planner/policy identities.
- [ ] Distinguish tracker diagnostics from formal P/N/V and reference checks from production same-decision validation.

## Failure / recovery criteria

- [ ] Every injected failure documents retained state, disabled operations, and recovery.
- [ ] No failure silently downgrades to stale-but-applicable Candidate, approximate attribution, or untracked fallback.
- [ ] Renderer/backend/tracker/runtime incompatibility disables production application without destroying inspectable artifacts or mutating Native Selection.

## Validation

- Full repository checks
- Locked GPU/model/tracker fault injection
- Same-binding Retry/cache tests
- Tracker run/reference/plan stale-result tests
- Key/Bridge transition and fallback tests
- correction-repropagate atomicity tests
- RGB-only versus RGB+Evidence parity
- Stable Mask/RGB digest mismatch
- Renderer/tracker migration invalidation and recovery
- Reference/production identity separation
- Frozen benchmark calibration
- Atomic repeatability/classification stability
- Stale async stress
- Review false-positive/false-negative evaluation

## Non-goals

- No new deep model or tracker selection; Ticket 08A spike/ADR owns backend selection.
- No new generic cross-view semantic identity classifier.
- No Candidate provenance UI.