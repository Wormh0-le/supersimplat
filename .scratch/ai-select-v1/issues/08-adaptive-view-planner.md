# 08 — Adaptive progressive View planner + Stop / Generate More / Regenerate Auto Views

Status: ready-for-agent — v2.2 re-audited

Blocked by: 07

## Final Spec mapping

- Final Spec v1.1 §§23, 27
- DG-13, DG-20
- MVP Phase 3

## Inputs / preconditions

- Confirmed Anchor
- Published AIViews/Masks/assessment
- Compatible camera/preflight primitives
- Low-cost target support/visibility diagnostics

## Outputs / handoff artifacts

- Adaptive planner policy
- Progressive planner jobs
- Stop Generation / Generate More / Regenerate Auto Views

## What to build

Replace fixed View-count UX with bounded adaptive planning. Planning may use low-cost support/visibility diagnostics before formal Lift; it must not require complete Contributor or precompute all per-view Evidence.

## Acceptance criteria

- [ ] Main flow does not ask for fixed View count or expose fixed quality presets.
- [ ] Planner uses bounded min/max, target observation, diversity, marginal gain, low-gain patience, and optional calibrated resource cap.
- [ ] View candidates, RGB, Mask, and later Evidence publish independently/progressively.
- [ ] Planner uses target-scoped observation and directional gain, not whole-scene Gaussian denominator.
- [ ] Planner may use declared low-cost diagnostics before formal P/N/V exists; it does not fabricate production Evidence.
- [ ] Stop Generation cancels pending/future work without deleting completed Views/RGB/Stable Masks/review state.
- [ ] Generate More is incremental from current observation/directional gaps.
- [ ] maxAutoViews is a hard batch bound; user may authorize another bounded batch.
- [ ] Manual View confirmation never implicitly resumes planner.
- [ ] Regenerate Auto Views replaces planner-owned Views and preserves user-owned Views.
- [ ] Ownership is explicit and stable.
- [ ] Toolbar uses adaptive text and no fixed N/total wording.

## Failure / recovery criteria

- [ ] Render failure supports true Retry and policy-based replacement.
- [ ] Stop/cancel/restart cannot publish obsolete work into a new context.
- [ ] Missing Evidence does not classify an RGB-ready View as Render Failed.

## Validation

- npm run test:companion
- npm test
- npm run lint
- Locked GPU planner smoke
- Frozen-scene marginal observation/diversity/early-stop benchmark

## Non-goals

- No final readiness calibration
- No User-added View UI
- No formal Direct Evidence kernel