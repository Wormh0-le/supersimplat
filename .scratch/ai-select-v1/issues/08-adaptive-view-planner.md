# 08 — Adaptive progressive View planner + Stop / Generate More / Regenerate Auto Views

Status: ready-for-agent

Blocked by: 07

## Final Spec mapping

- DG-13
- §19–24 Adaptive planning
- MVP Phase 3

## Inputs / preconditions

- Confirmed Anchor
- Existing published AIViews/masks/assessment
- Compatible orbit/preflight primitives

## Outputs / handoff artifacts

- Adaptive planner policy
- Progressive planner jobs
- Stop Generation
- Generate More
- Regenerate Auto Views

## What to build

Replace fixed user-facing View-count semantics with bounded adaptive planning. Reuse validated camera
geometry/preflight primitives, but use target-observation and directional-gain semantics rather than
whole-scene Gaussian denominator.

## Acceptance criteria

- [ ] Planner does not ask the user for a fixed View count and does not expose Fast/Balanced/High presets in the main v1.0 flow.
- [ ] Planner uses bounded policy inputs including min/max auto views, target observation, target diversity, marginal gain threshold, low-gain patience, and optional calibrated time/resource cap.
- [ ] View candidates/render/mask pipeline publishes progressively rather than waiting for one complete immutable batch.
- [ ] Stopping decisions use usable target observation plus View Diversity/directional gain; raw whole-scene Gaussian count is not the observation denominator.
- [ ] `Stop Generation` remains visible while planner is active and cancels pending/future work without deleting completed Views/RGB/Stable Masks/review state.
- [ ] `Generate More Views` is incremental and plans from current observation/directional gaps rather than regenerating the current set.
- [ ] Reaching maxAutoViews stops automatically and offers Review / Generate More / Add View rather than exceeding the hard bound.
- [ ] A user-triggered Generate More after cap authorizes a new bounded incremental batch.
- [ ] Manual/user-added View confirmation never implicitly resumes the automatic planner.
- [ ] `Regenerate Auto Views` is a separate low-frequency destructive action that replaces planner-owned auto views while preserving user-owned Views.
- [ ] Planner-owned vs user-owned View ownership is explicit and stable.
- [ ] Contextual toolbar uses adaptive text such as `Generating AI Views… N views ready` and never fixed `N / total` wording.

## Failure / recovery criteria

- [ ] Render failure supports Retry and, where planning policy can do so, Generate Replacement View.
- [ ] Stopping/canceling planner work never publishes a late obsolete View into a new target context.

## Affected seams

- Companion generated_views.py policy layer
- src/ai-select/planner*
- AI View registry
- Contextual toolbar

## Validation

- npm run test:companion
- npm test
- npm run lint
- Locked GPU planner smoke
- Frozen-scene marginal target observation/diversity/early-stop benchmark

## Non-goals

- No final Lift Readiness thresholds
- No User-added camera UI yet
