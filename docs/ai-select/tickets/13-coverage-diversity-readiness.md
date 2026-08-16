# 13 — Visible Evidence Coverage + View Diversity + Lift Readiness

Status: implemented — reference/calibration readiness path; production
same-decision Evidence remains Ticket 20

Blocked by: 14, 11, 12, 08

## Final Spec mapping

- Final Spec v1.3 §§14, 20–21, 24–26
- ADR 0013
- ADR 0016

## Purpose

Own target-scoped readiness for P/N/V Lift after Included Stable Views exist. This ticket is the sole current authority for weak Gaussian support, visibility coverage and useful view diversity.

## Inputs

- current Included Stable View Annotations;
- current per-View P/N/V or declared low-cost visibility diagnostics;
- TargetGeometryHint as a non-ownership localization seed;
- local Key-View completion/stop state;
- Evidence/Lift dirty state;
- optional Ticket 10 cross-view conflict diagnostics when available.

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
- `low-visible-support` and `weak-gaussian-support` readiness classification is owned here, not by Ticket 10;
- unobserved/insufficient Gaussians remain Uncertain, not negative Evidence;
- diversity uses useful observation directions, not raw View count;
- User Confirmed Included Views contribute regardless of historical automatic Review;
- Auto Review Excluded Views do not contribute;
- low-cost support diagnostics may provide an early Limited/Not Ready signal but cannot fabricate P/N/V;
- TargetGeometryHint may seed a working set but cannot hard-bound it;
- optional Ticket 10 conflict diagnostics may enrich inspection but are not required for base readiness or release;
- thresholds are versioned calibration inputs.

## Acceptance criteria

- [x] `weak-gaussian-support` is emitted only by Lift Readiness or related diagnostics.
- [x] MaskReviewPolicy and Ticket 10 do not emit weak/low-support readiness claims.
- [x] Observation Coverage uses valid visible mass/evidence.
- [x] View Diversity is separate from View count.
- [x] readiness is Not Ready / Limited / Ready from current exact Included inputs.
- [x] missing support fails conservatively without manufacturing coverage.
- [x] unobserved target regions remain Uncertain.
- [x] Stable Mask/Participation changes refresh readiness and dirty Lift correctly.
- [x] Generate More may respond to coverage/direction gaps without erasing current readiness.
- [x] base readiness works without Ticket 10 output.
- [x] readiness never mutates Stable Masks, Native Selection or Candidate.

## Validation

- reference V/Coverage fixtures;
- low-cost diagnostics versus formal Evidence consistency;
- weak-support ownership regression across Tickets 07/10/13;
- base readiness without Ticket 10 output;
- Not Ready/Limited/Ready calibration fixtures;
- view-direction diversity fixtures;
- TargetGeometryHint seed versus expanded Evidence Working Set fixtures;
- repository test/lint/build.

## Non-goals

- No per-View Mask quality decision.
- No production Direct Evidence kernel.
- No Candidate application.

## Implementation evidence

- `selection-service-companion/src/selection_service_companion/lift_readiness.py`
  owns the versioned `lift-readiness/reference-v1` policy and immutable
  evaluator. Formal coverage averages, over the current Core Target, the
  maximum normalized per-View effective Visible Mass. This prevents duplicate
  Views from manufacturing coverage. Formal diversity is the maximum angular
  separation between useful Included Evidence camera directions, independent
  from raw View count.
- A low-cost Anchor support diagnostic can produce only an early
  Limited/Not Ready result with `pending-formal-evidence`; it cannot publish a
  numeric Observation Coverage or P/N/V. Exact formal Evidence overrides it.
- The evaluator binds request/dependency, target splat, Evidence Working Set,
  source Evidence set, aggregation, CameraBindings, policy and result digest.
  Missing or mismatched identities fail closed.
- `src/ai-select/lift-readiness.ts` validates the untrusted Companion artifact,
  defensively copies it, and publishes target-local current/stale presentation
  state. Editing Mask changes preserve current readiness; Stable Mask or
  Participation changes reuse the Ticket 12 dirty state and keep the previous
  readiness inspectable as stale.
- The browser store provides the exact-bound current/stale presentation state
  required by a future Re-Lift vertical slice. This reference Ticket does not
  add a live Companion transport/publisher or expose an inert production Dock
  row. The store does not start Lift or mutate Stable Masks, Candidate,
  Uncertain or Native Selection.
- Cross-runtime golden-vector tests, Visible Mass calibration fixtures,
  duplicate-direction fixtures, low-cost fallback fixtures, expanded Working
  Set fixtures and atomic browser publication tests are under
  `selection-service-companion/tests/test_lift_readiness.py`,
  `test/ai-select-lift-readiness.test.js` and
  `test/fixtures/ai-select-lift-readiness-contract-vector.json`.

This closure is reference/calibration work built on Ticket 14's complete-
Contributor reference aggregation. It does not claim a production Direct
Evidence kernel, locked-GPU production validation, Ticket 10 output, or final
threshold calibration. It also does not claim a live editor workflow: the
production Evidence/Re-Lift vertical slice must invoke the evaluator and
publish its exact binding before a user-facing readiness row is shipped.
Ticket 20/21 retain those responsibilities.

## Post-16A product gate

The checked `Generate More` item above records the implemented evaluator-era
integration and is superseded as a current product control by Tickets 16B and
16G. Readiness remains diagnostic and may recommend a user-chosen replacement
or additional View, but it does not expose or invoke Generate More. Ticket 16E
maps the current exact-bound state to Re-Lift: Not Ready disables, Limited
permits with a warning, and Ready permits normally. This mapping does not
change the evaluator or fabricate readiness.
