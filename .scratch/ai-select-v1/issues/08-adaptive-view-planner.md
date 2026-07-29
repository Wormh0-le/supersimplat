# 08 — Adaptive progressive View planner + Stop / Generate More / Regenerate Auto Views

Status: blocked — waits for reopened 07A and Ticket 07B

Blocked by: 07B

## Final Spec mapping

- Final Spec v1.1 §§23, 27
- Final Spec v1.1 Amendment 002 — completed Anchor Mask pipeline prerequisite
- DG-13, DG-20, DG-21, DG-22
- MVP Phase 3

## Inputs / preconditions

- Confirmed Anchor produced by the completed Three-Stage Anchor Mask Pipeline
- Resolved Prompt/proposal state and current Stable Anchor Mask
- No permanent fitted-image Prompt/Edit blind region after Ticket 07B
- Published AIViews/Masks/assessment
- Compatible camera/preflight primitives
- Low-cost target support/visibility diagnostics
- Scene/Camera validity information available to the current render path

## Outputs / handoff artifacts

- Versioned adaptive planner policy
- Progressive planner jobs
- Candidate-pose validity/preflight record
- Stop Generation / Generate More / Regenerate Auto Views

## What to build

Replace the Ticket 06 fixed `±45°` pair with bounded adaptive planning. Planning may use low-cost support/visibility and render preflight before formal Lift; it must not require complete Contributor or precompute all per-view Evidence.

Planning has two distinct decisions:

```text
1. Is this camera pose a valid/plausible observation pose?
2. If valid, does it add useful target observation/diversity?
```

A high theoretical angular gain cannot make an invalid indoor/outside-room camera acceptable.

## Acceptance criteria

### Adaptive policy

- [ ] Main flow does not ask for fixed View count or expose fixed quality presets.
- [ ] Planner uses bounded min/max, target observation, diversity, marginal gain, low-gain patience, and optional calibrated resource cap.
- [ ] View candidates, RGB, Mask, and later Evidence publish independently/progressively.
- [ ] Planner uses target-scoped observation and directional gain, not whole-scene Gaussian denominator.
- [ ] Planner may use declared low-cost diagnostics before formal P/N/V exists; it does not fabricate production Evidence.

### Candidate-pose validity

- [ ] Pose validity is evaluated before information-gain ranking.
- [ ] Preflight considers target projection/visibility, clipping, expected image occupancy, surrounding scene support, and available depth/alpha/free-space diagnostics.
- [ ] Indoor candidates that move through dense scene support, behind enclosing walls, or into an observation region dominated by blank/outside content are rejected or replaced.
- [ ] When an observed/training-camera manifold or validated free-space envelope exists, it may constrain candidate poses under a versioned policy.
- [ ] Absence of reliable free-space information fails conservatively to smaller/local view moves or user-added Views rather than unconstrained large orbit jumps.
- [ ] Candidate validity and information-gain scores are recorded separately; a high gain score cannot override an invalid pose.
- [ ] Candidate rejection is not implemented by merely clamping camera position to a global Scene AABB.
- [ ] Target-only visibility is insufficient when the camera is outside the plausible observation region.

### Progressive controls

- [ ] Candidate preflight detects overly distant, low-value, or implausible orbit candidates and rejects/replaces them.
- [ ] Stop Generation cancels pending/future work without deleting completed Views/RGB/Stable Masks/review state.
- [ ] Generate More is incremental from current observation/directional gaps.
- [ ] `maxAutoViews` is a hard batch bound; user may authorize another bounded batch.
- [ ] Manual View confirmation never implicitly resumes planner.
- [ ] Regenerate Auto Views replaces planner-owned Views and preserves user-owned Views.
- [ ] Planner ownership is explicit and stable.
- [ ] Toolbar uses adaptive text and no fixed N/total wording.

### Anchor-quality dependency

- [ ] Planner starts only after Ticket 07A has completed algorithm/calibration closure.
- [ ] Planner starts only from a confirmed Anchor with no unresolved ProposalDecision.
- [ ] Ticket 07B palette behavior no longer blocks editing any fitted-image edge or corner.
- [ ] Anchor Prompt/proposal changes after confirmation follow the explicit Adjust/Restart/Recompute lifecycle; planner never consumes an unconfirmed proposal.
- [ ] Ticket 07A proposal diagnostics are not reused as formal planner Evidence.

## Failure / recovery criteria

- [ ] Render failure supports true Retry and policy-based replacement.
- [ ] Invalid/outside-room candidate rejection preserves completed Views and continues with a bounded replacement when available.
- [ ] If no valid useful candidate remains, planner stops with an actionable limited-coverage state rather than emitting invalid Views.
- [ ] Stop/cancel/restart cannot publish obsolete work into a new context.
- [ ] Missing Evidence does not classify an RGB-ready View as Render Failed.

## Validation

- `npm run test:companion`
- `npm test`
- `npm run lint`
- Locked GPU planner smoke
- Frozen-scene marginal observation/diversity/early-stop benchmark
- Indoor-room regression: candidate orbit must not place cameras outside enclosing geometry or behind walls
- Blank/outside-content low-resolution render preflight regression
- Conservative fallback when no free-space/manifold data exists
- Large-orbit regression captured from the Ticket 06 browser walkthrough (`12.918`-unit orbit, `18.269`-unit candidate separation)
- Ticket 07A confirmed-Anchor prerequisite regression
- Ticket 07B edge/corner authoring prerequisite regression

## Non-goals

- No final Lift Readiness calibration
- No User-added View UI
- No formal Direct Evidence kernel
- No general robot/navigation path planner
- No requirement to reconstruct a watertight room mesh
