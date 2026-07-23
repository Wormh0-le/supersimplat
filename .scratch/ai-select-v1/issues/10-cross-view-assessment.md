# 10 — Cross-view Review assessment + visible-support reasons

Status: ready-for-agent — v2.2 re-audited

Blocked by: 14, 09, 07

## Final Spec mapping

- Final Spec v1.1 §§18, 20, 22, 26
- DG-19 P1, DG-20
- MVP Phase 4 P1

## Inputs / preconditions

- Version-bound per-view P/N/V Evidence from Ticket 14
- AIView assessments and Participation
- Gallery/Review UI

## Outputs / handoff artifacts

- cross-view-inconsistency reason
- low-visible-support reason
- P1 diagnostics
- Updated Review queue

## What to build

Add P1 cross-view assessment over per-view Gaussian Evidence. The v2.2 reverse dependency audit moves this ticket after Ticket 14 because cross-view P/N/V cannot be consumed before the reference Evidence contract exists.

## Acceptance criteria

- [ ] Cross-view assessment consumes Stable Mask-bound per-view P/N/V/visibility and policy identities.
- [ ] Complete per-pixel Contributor is not a required production input.
- [ ] `cross-view-inconsistency` is emitted only from validated Gaussian ownership/conflict logic, not raw 2D area alone.
- [ ] `low-visible-support` is used instead of claiming semantic occlusion when only V evidence is available.
- [ ] Diagnostics may include cross-view precision/recall, visible target ratio, supporting/conflicting View counts, or calibrated equivalents.
- [ ] Raw Mask-area outlier remains internal unless perspective/visibility normalization supports a user reason.
- [ ] `identity-drift` remains future taxonomy and is not emitted in v1.1.
- [ ] Assessment refreshes when matching per-view Evidence becomes available but never triggers Repropagate or Re-Lift.
- [ ] User Confirmed authority cannot be silently revoked or down-weighted.
- [ ] UI shows only actionable reason(s) through static localized Reason→Action mapping.

## Failure / recovery criteria

- [ ] Insufficient/missing Evidence yields no fabricated cross-view reason.
- [ ] P1 failure does not corrupt P0 assessment, Participation, View RGB, Stable Mask, or Candidate.

## Validation

- npm run test:companion
- npm test
- P/N/V cross-view fixtures
- Missing/stale Evidence fixtures
- Locked GPU/reference visibility smoke
- False-positive/false-negative benchmark inputs for Ticket 21

## Non-goals

- No new deep model
- No identity-drift requirement
- No production Direct Evidence kernel