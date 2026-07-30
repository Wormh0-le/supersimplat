# 21 — Retry / cancellation / OOM / atomic publication + calibration hardening

Status: ready-for-agent — v2.6 DG-24 aligned

Blocked by: 20, 18, 08, 08A, 10, 13

## Final Spec mapping

- Final Spec v1.1 §§8, 16.2, 22–23, 28, 30–32
- Final Spec v1.1 Amendments 001, 003, and 004
- DG-24
- ADR 0013
- MVP Phase 7 hardening

## Inputs / preconditions

- Complete v1.1 product flow
- Production Direct Evidence path
- Locked GPU/model/Mask-acquisition runtime
- Frozen benchmark scenes and sparse Key Views
- Optional tracker/hybrid runtime only when selected by ADR
- Fault-injection hooks

## Outputs / handoff artifacts

- End-to-end failure hardening
- Versioned policy thresholds/margins
- Sparse planner and Mask-acquisition resource-envelope validation
- Stress and repeatability results
- Locked production evidence record

## What to build

Close the production-hardening loop. Calibrate existing semantics and validate retained-state/recovery behavior; introduce no new product model or acquisition backend.

## Acceptance criteria

- [ ] Explicit Retry creates a true new attempt for render, per-view Mask acquisition, optional tracker, and Evidence operations; same-attempt replay remains idempotent.
- [ ] Cancellation correctness never depends on cancellation completing before stale work returns.
- [ ] OOM/kernel/model failure during render/SAM/optional tracking/Evidence/Lift never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for RGB/View, Stable Mask, optional propagation batch, per-view Evidence, assessment, and Candidate.
- [ ] RGB failure preserves last valid preview only as stale/not-current and exposes Retry.
- [ ] Per-view Mask failure preserves View/RGB/prior Stable Mask and exposes Retry, declared fallback, manual correction, or Exclude.
- [ ] Insufficient 3D-guided Prompt support fails to Review/Failed with actionable recovery, not silent oversized success.
- [ ] Optional tracker instance-switch suspicion is Review/fail-closed, never silent Auto Good.
- [ ] Corrected Stable Mask does not automatically create tracker memory or refresh unrelated Views.
- [ ] Optional propagation failure preserves old Stable Masks and matching Evidence/Candidate.
- [ ] Evidence failure preserves RGB/View/Stable/Gallery/previous Candidate and exposes recovery.
- [ ] Reference Contributor failure does not block valid RGB or successful Direct Evidence.
- [ ] View Render Failure exposes retry/replacement/exclude.
- [ ] Lift failure preserves stable inputs and leaves Candidate unchanged/not-current.
- [ ] Offline/upgrade/incompatible states preserve native SuperSplat and expose recovery.
- [ ] Stress stale-result rejection across Camera churn, bootstrap/segment replacement, Prompt revision, Stop, Restart, Suspended/Undo, Evidence recomputation, and cancellation.
- [ ] Validate RGB-only versus RGB+Evidence parity for same raster identity and inputs.
- [ ] Inject Evidence RGB-digest mismatch and verify no publication/rebinding.
- [ ] Validate incompatible renderer/acquisition/runtime migration blocks stale reuse until explicit recovery.
- [ ] Validate baseline/default/optional backend identities cannot collide.
- [ ] Calibrate Camera observer placement, preview behavior, and inference resolutions.
- [ ] Calibrate sparse planner budget, marginal gain, diversity, early stop, and Generate More segment size.
- [ ] Validate 3D-guided Prompt synthesis quality, resource envelope, fallback threshold, and sparse-view budget.
- [ ] If tracker/hybrid is selected, validate its transition/resource envelope and correction recovery separately.
- [ ] Calibrate Core/Context/Evidence Working Set and Render Working Set parity, including bootstrap-seed expansion.
- [ ] Calibrate positive/boundary/local-negative Mask policy and P/N/V classification margins.
- [ ] Validate mixed/unobserved classifications under repeated atomic accumulation.
- [ ] Calibrate Coverage, Readiness, P0/P1 assessment, and cross-view false-positive/false-negative behavior.
- [ ] Record exact raster/Evidence/runtime/model/acquisition/planner/Prompt/policy identities.
- [ ] Distinguish Mask-generation diagnostics from formal P/N/V and reference checks from production same-decision validation.

## Failure / recovery criteria

- [ ] Every injected failure documents retained state, disabled operations, and recovery.
- [ ] No failure silently downgrades to stale-but-applicable Candidate, approximate attribution, or undisclosed fallback.
- [ ] Renderer/backend/runtime incompatibility disables production application without destroying inspectable artifacts or mutating Native Selection.

## Validation

- Full repository checks
- Locked GPU/model/acquisition fault injection
- Same-binding Retry/cache tests
- Bootstrap/segment/View/Prompt/backend stale-result tests
- Generate More append-only preservation tests
- Per-view correction without unrelated refresh tests
- Optional propagation tests only when capability exists
- RGB-only versus RGB+Evidence parity
- Stable Mask/RGB digest mismatch
- Renderer/acquisition migration invalidation and recovery
- Reference/production identity separation
- Frozen benchmark calibration
- Atomic repeatability/classification stability
- Stale async stress
- Review false-positive/false-negative evaluation

## Non-goals

- No new deep model or acquisition-route selection; Ticket 08A spike/ADR owns route selection.
- No mandatory tracker hardening when v1 selects independent per-view SAM.
- No new generic cross-view semantic identity classifier.
- No Candidate provenance UI.
