# 21 — Retry / cancellation / OOM / atomic publication + calibration hardening

Status: ready-for-agent — v2.2 re-audited

Blocked by: 20, 18, 08, 10, 13

## Final Spec mapping

- Final Spec v1.1 §§8, 16.2, 22–23, 28, 30–32
- Final Spec v1.1 Amendment 001 — Renderer / Evidence Implementation Identity and RGB Continuity
- ADR 0013
- MVP Phase 7 hardening

## Inputs / preconditions

- Complete v1.1 product flow
- Production Direct Evidence path
- Locked GPU runtime
- Frozen benchmark scenes
- Fault-injection hooks

## Outputs / handoff artifacts

- End-to-end failure hardening
- Calibrated policy margins/thresholds
- Stress and repeatability results
- Locked production evidence record

## What to build

Close the production-hardening loop. This ticket calibrates existing semantics and validates retained-state/recovery behavior; it introduces no new product model.

## Acceptance criteria

- [ ] Explicit Retry creates a true new render attempt for the same CameraBinding; same-attempt replay remains idempotent.
- [ ] Cancellation correctness never depends on cancellation completing before stale work returns.
- [ ] OOM/kernel failure during render/SAM/Evidence/Lift never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for RGB/View, Stable Mask, per-view Evidence, Repropagate, assessment, and Candidate.
- [ ] RGB failure preserves last valid preview only as stale/not-current and exposes true Retry.
- [ ] Evidence failure preserves RGB/View/Stable Mask/Gallery/previous Candidate and exposes Retry Lift / inspect Mask / Exclude / adjust-add View.
- [ ] Reference Contributor failure does not block valid RGB or successful Direct Evidence.
- [ ] Mask failure preserves View/RGB and exposes retry/manual/exclude.
- [ ] View Render Failure exposes retry/replacement/exclude.
- [ ] Lift failure preserves stable inputs and leaves Candidate unchanged/not-current.
- [ ] Repropagate failure preserves old Stable Masks and matching Evidence/Candidate.
- [ ] Offline/upgrade/incompatible states preserve native SuperSplat and expose readiness/settings recovery.
- [ ] Stress stale-result rejection across Camera churn, planner Stop, Restart, Suspended/Undo, Evidence recomputation, and cancellation.
- [ ] Validate RGB-only versus RGB+Evidence parity for the same `rasterImplementationId`, exact inputs, and compatible `runtimeBuildId`.
- [ ] Inject an Evidence traversal RGB-digest mismatch and verify no Evidence publishes, the Stable Mask is not silently rebound, and historical RGB remains inspectable.
- [ ] Validate incompatible renderer/runtime migration: old RGB/Mask/Evidence/Candidate reuse is blocked until explicit rerender/review/recompute recovery.
- [ ] Validate reference and production backend identities cannot collide in cache, Candidate readiness, or Native application state.
- [ ] Calibrate Camera observer placement, preview behavior, and inference resolutions.
- [ ] Calibrate planner budget, marginal Visible Evidence gain, diversity, and early stop.
- [ ] Calibrate Core/Context/Evidence Working Set construction and Render Working Set parity gate.
- [ ] Calibrate positive/boundary/local-negative Mask policy and P/N/V classification margins.
- [ ] Validate mixed and unobserved remain stable classifications under repeated atomic accumulation.
- [ ] Calibrate Observation Coverage, Lift Readiness, P0/P1 assessment, and cross-view false-positive/false-negative behavior.
- [ ] Record exact `rasterImplementationId`, `evidenceBackendId`, `runtimeBuildId`, source/build/CUDA/PyTorch/GPU/model/renderer/Evidence policy identities.
- [ ] Clearly distinguish reference/autograd checks from production same-decision GPU validation.

## Failure / recovery criteria

- [ ] Every injected failure documents retained state, disabled operations, and recovery action.
- [ ] No failure silently downgrades to a stale-but-applicable Candidate or approximate attribution.
- [ ] Renderer/backend/runtime incompatibility disables production application without destroying inspectable artifacts or mutating Native Selection.

## Validation

- Full repository checks
- Locked GPU fault injection
- Same-CameraBinding Retry/cache tests
- RGB-only versus RGB+Evidence parity test
- Stable Mask/RGB digest mismatch test
- Renderer migration invalidation and explicit recovery test
- Reference-versus-production backend identity separation test
- Frozen benchmark calibration
- Atomic repeatability/classification stability suite
- Stale async stress suite
- Review false-positive/false-negative evaluation

## Non-goals

- No new deep model
- No identity-drift requirement
- No Candidate provenance UI