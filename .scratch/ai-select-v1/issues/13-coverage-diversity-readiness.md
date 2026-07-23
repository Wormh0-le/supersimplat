# 13 — Visible Evidence Coverage + View Diversity + Lift Readiness

Status: ready-for-agent — v2.2 re-audited

Blocked by: 14, 11, 12, 08

## Final Spec mapping

- Final Spec v1.1 §§17, 22–23, 27
- DG-04, DG-20
- MVP Phase 5 readiness

## Inputs / preconditions

- Reference P/N/V and Evidence Working Set from Ticket 14
- Current Included Stable View Annotations
- Planner completion/stop state
- Dirty-state model
- Optional P1 cross-view diagnostics when Ticket 10 is available

## Outputs / handoff artifacts

- Observation Coverage
- View Diversity
- Not Ready / Limited / Ready
- Planner/readiness shared observation seam

## What to build

Implement target-scoped readiness after the Evidence contract exists. Coverage uses valid Visible Mass over the Core Target Set. Readiness may use declared low-cost support/visibility diagnostics before all formal per-view Evidence artifacts are computed, but it must not invent production Evidence or require complete Contributor. P1 cross-view assessment may enrich diagnostics but is not a hard prerequisite for basic readiness.

## Acceptance criteria

- [ ] Observation Coverage derives from valid V/visible Evidence over Core Target Set, not whole-scene Gaussian count or frustum inclusion.
- [ ] Context Set does not directly lower target Coverage.
- [ ] Unobserved/insufficient Gaussians remain Uncertain and do not become negative Coverage evidence.
- [ ] View Diversity is separate from View count and uses useful observation directions.
- [ ] Lift Readiness is Not Ready / Limited / Ready from current Included Stable inputs.
- [ ] Hard gates cover confirmed Anchor, usable Included Views, valid RGB/Stable Mask identity, Stable IDs/Render Working Set, and nondegenerate diversity.
- [ ] Readiness may use low-cost versioned support/visibility diagnostics before formal Lift; it does not require complete Contributor or all P/N/V artifacts in advance.
- [ ] P1 cross-view diagnostics are consumed when available but absence of Ticket 10 output does not block the base readiness state.
- [ ] Auto Review Excluded never secretly contributes.
- [ ] User Confirmed Included contributes regardless of historical machine Review.
- [ ] Stable Mask/Participation changes refresh derived readiness and mark appropriate Evidence/Lift dirty.
- [ ] Review does not globally block Lift when remaining Included evidence satisfies policy.
- [ ] Planner early-stop and readiness share target-scoped observation semantics.
- [ ] Stop Generation, planner completion, or max-budget stop immediately refreshes readiness.
- [ ] Generate More uses current observation/directional gaps without erasing current readiness.
- [ ] Thresholds are versioned policy inputs and not product constants.

## Failure / recovery criteria

- [ ] Missing/invalid support or visibility fails readiness conservatively without manufacturing Coverage.
- [ ] Readiness failure does not mutate Native Selection, Stable Masks, Evidence, or Candidate.

## Validation

- npm test
- npm run test:companion
- npm run lint
- Reference V/Coverage fixtures
- Low-cost diagnostic versus formal Evidence consistency fixtures
- Base readiness without P1 and enriched readiness with P1 fixtures
- Not Ready/Limited/Ready calibration inputs

## Non-goals

- No production Direct Evidence kernel
- No Candidate application