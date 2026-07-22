# 21 — Cancellation/OOM/atomic-publication + calibration hardening

Status: ready-for-agent

Blocked by: 20, 18, 08, 10, 13

## Final Spec mapping

- §85 Errors/Degradation
- §89 engineering validation
- MVP Phase 7 hardening

## Inputs / preconditions

- Complete product flow
- Locked GPU runtime
- Frozen benchmark scenes
- Fault-injection hooks

## Outputs / handoff artifacts

- End-to-end failure hardening
- Calibration evidence
- Stress results
- Validated thresholds/policies

## What to build

Close the production-hardening loop with explicit failure injection and calibration. This ticket owns
cross-cutting runtime failure behavior and measured policy thresholds; it introduces no new product semantics.

## Acceptance criteria

- [ ] Companion cancellation is tested end to end and correctness never depends on cancellation completing before a stale result arrives.
- [ ] CUDA/PyTorch OOM during render/SAM/evidence/lift is surfaced as an actionable failure and never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for Anchor, Stable Mask, Repropagate, assessment, and Candidate paths.
- [ ] Preview failure preserves last valid preview and exposes retry.
- [ ] Mask generation failure preserves View/RGB and exposes retry/manual/exclude recovery.
- [ ] View render failure exposes retry / replacement-generation / exclude recovery according to current planner/participation capabilities.
- [ ] Lifting failure preserves Views/Stable Masks/Gallery and leaves Candidate unchanged/not-current.
- [ ] Repropagate failure preserves old Stable Masks and never publishes incomplete proposed masks.
- [ ] Companion Offline/upgrade/incompatible states leave native SuperSplat functional and expose recovery via existing readiness/settings flow.
- [ ] Stress test stale-result rejection across CameraBinding churn, planner Stop, Restart Target, Suspended mutation, Undo recovery, and cancellation.
- [ ] Calibrate Camera Inspection observer placement, preview throttle/debounce, and inference resolutions on representative scenes/hardware.
- [ ] Calibrate planner min/max budget, marginal target observation gain, directional diversity, and early-stop policy against frozen benchmark scenes.
- [ ] Calibrate Core/Context set construction, contributor observation strength, View Diversity bins, and Lift Readiness thresholds.
- [ ] Calibrate ViewAssessmentPolicy P0 thresholds and P1 cross-view/visible-support false-positive/false-negative behavior.
- [ ] Validate Repropagate reference-selection policy and native EditHistory/ApplicationRecord synchronization edge cases.
- [ ] Record exact locked GPU/runtime/model/renderer versions for production benchmark claims and clearly distinguish mock/CPU/reference-only checks.

## Failure / recovery criteria

- [ ] Every injected failure specifies retained state, disabled operations, and user-visible recovery action.
- [ ] No failure path may silently downgrade into a stale-but-applicable Candidate.

## Affected seams

- Companion runtime/cancellation/OOM/atomic publication
- AI Select error state UI
- Planner/assessment/readiness policies
- Benchmark/calibration harness
- Locked GPU environment

## Validation

- Full repository checks
- Locked GPU fault injection
- Frozen benchmark calibration runs
- Stale async stress suite
- Review false-positive/false-negative evaluation

## Non-goals

- No new deep model
- No identity-drift requirement
- No Candidate provenance UI
