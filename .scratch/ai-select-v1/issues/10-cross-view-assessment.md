# 10 — Cross-view Review assessment + visible-support reasons

Status: ready-for-agent — v2.6 DG-24 aligned

Blocked by: 14, 09, 07

## Final Spec mapping

- Final Spec v1.1 §§18, 20, 22, 26
- Final Spec v1.1 Amendments 003 and 004
- DG-19 P1, DG-20, DG-24
- MVP Phase 4 P1

## Inputs / preconditions

- Version-bound per-view P/N/V Evidence from Ticket 14
- AIView assessments and Participation
- Gallery/Review UI
- Mask acquisition backend/status as separate upstream diagnostics
- Optional tracker-local status only when advertised

## Outputs / handoff artifacts

- cross-view-inconsistency reason
- low-visible-support reason
- P1 diagnostics
- Updated Review queue

## What to build

Add P1 cross-view assessment over per-view Gaussian Evidence. It follows Ticket 14 because cross-view P/N/V cannot be consumed before the reference Evidence contract exists.

Optional tracker identity-drift diagnostics are not computed here. Ticket 10 must neither duplicate backend-local signals nor infer semantic identity drift from raw P/N/V alone.

## Acceptance criteria

- [ ] Cross-view assessment consumes Stable Mask-bound per-view P/N/V/visibility and policy identities.
- [ ] Complete per-pixel Contributor is not required.
- [ ] `cross-view-inconsistency` is emitted only from validated Gaussian support/conflict logic, not raw 2D area.
- [ ] `low-visible-support` is used instead of claiming semantic occlusion when only V is available.
- [ ] Diagnostics may include cross-view precision/recall, visible target ratio, supporting/conflicting View counts, or calibrated equivalents.
- [ ] Raw Mask-area outlier remains internal unless perspective/visibility normalization supports an action.
- [ ] A generic P/N/V-derived `identity-drift` reason remains out of scope for v1.1.
- [ ] Optional backend-local drift suspicion remains distinct and is not renamed/recomputed here.
- [ ] Assessment refreshes when matching per-view Evidence becomes available but never triggers Mask refresh, optional propagation, or Re-Lift.
- [ ] User Confirmed authority cannot be silently revoked or down-weighted.
- [ ] UI shows only actionable reasons through static localized Reason→Action mapping.
- [ ] Key-View role, backend score, and optional tracker confidence cannot substitute for P/N/V support/conflict logic.

## Failure / recovery criteria

- [ ] Insufficient/missing Evidence yields no fabricated cross-view reason.
- [ ] P1 failure does not corrupt P0 assessment, backend-local status, Participation, View RGB, Stable Mask, or Candidate.

## Validation

- npm run test:companion
- npm test
- P/N/V cross-view fixtures
- Missing/stale Evidence fixtures
- Locked GPU/reference visibility smoke
- Backend-local diagnostic versus P/N/V inconsistency separation fixture
- False-positive/false-negative benchmark inputs for Ticket 21

## Non-goals

- No new deep model.
- No Mask acquisition backend or identity-drift detector.
- No production Direct Evidence kernel.
