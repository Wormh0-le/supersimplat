# 21 — Retry / cancellation / OOM / atomic publication + calibration hardening

Status: ready-for-agent — v2.7 DG-25 aligned

Blocked by: 20, 18, 08, 08A, 10, 13

## Final Spec mapping

- Final Spec v1.1 §§8, 16.2, 22–23, 28, 30–32
- Final Spec v1.1 Amendments 001, 003, 004, and 005
- DG-24 and DG-25
- ADR 0013
- MVP Phase 7 hardening

## Inputs / preconditions

- Complete v1.1 product flow
- Production Direct Evidence path
- Locked GPU/model/route-B Mask-acquisition runtime
- Frozen benchmark scenes and sparse Key Views
- Route-A baseline fallback
- Optional future tracker/hybrid runtime only when separately adopted by ADR
- Fault-injection hooks

## Outputs / handoff artifacts

- End-to-end failure hardening
- Versioned policy thresholds/margins
- Sparse planner and route-B Mask-acquisition resource-envelope validation
- Acquisition capability/dispatch compatibility results
- Stress and repeatability results
- Locked production evidence record

## What to build

Close the production-hardening loop for the selected route-B product flow. Calibrate existing semantics and validate retained-state/recovery behavior; introduce no new product model or acquisition backend.

## Acceptance criteria

- [ ] Explicit Retry creates a true new attempt for render, route-B per-view Mask acquisition, and Evidence operations; same-attempt replay remains idempotent.
- [ ] Cancellation correctness never depends on cancellation completing before stale work returns.
- [ ] OOM/kernel/model failure during render/SAM/Evidence/Lift never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for RGB/View, Stable Mask, per-view Evidence, assessment, and Candidate.
- [ ] RGB failure preserves last valid preview only as stale/not-current and exposes Retry.
- [ ] Per-view Mask failure preserves View/RGB/prior Stable Mask and exposes Retry, route-A fallback, manual correction, or Exclude.
- [ ] Insufficient 3D-guided Prompt support fails to Review/Failed with actionable recovery, not silent oversized success.
- [ ] Corrected Stable Mask does not automatically create tracker memory or refresh unrelated Views.
- [ ] Evidence failure preserves RGB/View/Stable/Gallery/previous Candidate and exposes recovery.
- [ ] Reference Contributor failure does not block valid RGB or successful Direct Evidence.
- [ ] View Render Failure exposes retry/replacement/exclude.
- [ ] Lift failure preserves stable inputs and leaves Candidate unchanged/not-current.
- [ ] Offline/upgrade/incompatible states preserve native SuperSplat and expose recovery.
- [ ] Stress stale-result rejection across Camera churn, bootstrap/segment replacement, Prompt revision, Stop, Restart, Suspended/Undo, Evidence recomputation, and cancellation.
- [ ] Validate RGB-only versus RGB+Evidence parity for same raster identity and inputs.
- [ ] Inject Evidence RGB-digest mismatch and verify no publication/rebinding.
- [ ] Validate incompatible renderer/acquisition/runtime migration blocks stale reuse until explicit recovery.
- [ ] Validate route-A/route-B/backend identities cannot collide.
- [ ] Validate `MaskAcquisitionCapabilities` digest and backend dispatch identity.
- [ ] Validate route B rejects sequence/reference methods before inference or state mutation.
- [ ] Validate optional sequence/reference schemas remain forward-compatible with route-B artifacts.
- [ ] Calibrate Camera observer placement, preview behavior, and inference resolutions.
- [ ] Calibrate sparse planner budget, marginal gain, diversity, early stop, and Generate More segment size.
- [ ] Validate 3D-guided Prompt synthesis quality, resource envelope, route-A fallback threshold, and sparse-view budget.
- [ ] Calibrate Core/Context/Evidence Working Set and Render Working Set parity, including bootstrap-seed expansion.
- [ ] Calibrate positive/boundary/local-negative Mask policy and P/N/V classification margins.
- [ ] Validate mixed/unobserved classifications under repeated atomic accumulation.
- [ ] Calibrate Coverage, Readiness, P0/P1 assessment, and cross-view false-positive/false-negative behavior.
- [ ] Record exact raster/Evidence/runtime/model/acquisition/planner/Prompt/policy identities.
- [ ] Distinguish Mask-generation diagnostics from formal P/N/V and reference checks from production same-decision validation.

Future C/D hardening is not part of this ticket unless a separate ADR adopts one of those capabilities.

## Failure / recovery criteria

- [ ] Every injected failure documents retained state, disabled operations, and recovery.
- [ ] No failure silently downgrades to stale-but-applicable Candidate, approximate attribution, or undisclosed fallback.
- [ ] Renderer/backend/runtime incompatibility disables production application without destroying inspectable artifacts or mutating Native Selection.
- [ ] Unsupported optional extension calls produce structured capability failure and no dirty-state mutation.

## Validation

- Full repository checks
- Locked GPU/model/route-B acquisition fault injection
- Same-binding Retry/cache tests
- Bootstrap/segment/View/Prompt/backend stale-result tests
- Generate More append-only preservation tests
- Per-view correction without unrelated refresh tests
- Capability digest and dispatch tests
- Unsupported sequence/reference no-mutation tests
- RGB-only versus RGB+Evidence parity
- Stable Mask/RGB digest mismatch
- Renderer/acquisition migration invalidation and recovery
- Reference/production identity separation
- Frozen route-B benchmark calibration
- Atomic repeatability/classification stability
- Stale async stress
- Review false-positive/false-negative evaluation

## Non-goals

- No acquisition-route selection; route B is selected by DG-25 / Amendment 005.
- No A/B/C/D comparison gate.
- No tracker/hybrid implementation or hardening without a separate future ADR.
- No new generic cross-view semantic identity classifier.
- No Candidate provenance UI.
