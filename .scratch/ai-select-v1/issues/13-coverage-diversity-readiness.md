# 13 — Visible Evidence Coverage + View Diversity + Lift Readiness

Status: planned — v1.3 responsibility clarified

Blocked by: 14, 11, 12, 08

## Final Spec mapping

- Final Spec v1.3 §§14, 20–21, 24–26
- ADR 0013
- ADR 0016

## Purpose

Own target-scoped readiness for P/N/V Lift after Included Stable Views exist. This ticket is the correct home for weak Gaussian support, visibility coverage and useful view diversity.

## Inputs

- current Included Stable View Annotations;
- current per-View P/N/V or declared low-cost visibility diagnostics;
- TargetGeometryHint as a non-ownership localization seed;
- local Key-View completion/stop state;
- Evidence/Lift dirty state;
- optional cross-view diagnostics.

## Outputs

```text
Observation Coverage
View Diversity
Weak / sufficient Gaussian visibility support
Not Ready / Limited / Ready
```

## Rules

- coverage derives from valid V/visible Evidence over the target working set, not whole-scene Gaussian count or frustum inclusion;
- insufficient or weak Gaussian support is a Lift Readiness condition, never a MaskReview reason;
- unobserved/insufficient Gaussians remain Uncertain, not negative Evidence;
- diversity uses useful observation directions, not raw View count;
- User Confirmed Included Views contribute regardless of historical automatic Review;
- Auto Review Excluded Views do not contribute;
- low-cost support diagnostics may provide an early Limited/Not Ready signal but cannot fabricate P/N/V;
- TargetGeometryHint may seed a working set but cannot hard-bound it;
- thresholds are versioned calibration inputs.

## Acceptance criteria

- [ ] `weak-gaussian-support` is emitted only by Lift Readiness or related diagnostics.
- [ ] MaskReviewPolicy does not emit it.
- [ ] Observation Coverage uses valid visible mass/evidence.
- [ ] View Diversity is separate from View count.
- [ ] readiness is Not Ready / Limited / Ready from current exact Included inputs.
- [ ] missing support fails conservatively without manufacturing coverage.
- [ ] unobserved target regions remain Uncertain.
- [ ] Stable Mask/Participation changes refresh readiness and dirty Lift correctly.
- [ ] Generate More may respond to coverage/direction gaps without erasing current readiness.
- [ ] readiness never mutates Stable Masks, Native Selection or Candidate.

## Validation

- reference V/Coverage fixtures;
- low-cost diagnostics versus formal Evidence consistency;
- weak-support ownership regression;
- Not Ready/Limited/Ready calibration fixtures;
- view-direction diversity fixtures;
- TargetGeometryHint seed versus expanded Evidence Working Set fixtures;
- repository test/lint/build.

## Non-goals

- No per-View Mask quality decision.
- No production Direct Evidence kernel.
- No Candidate application.
