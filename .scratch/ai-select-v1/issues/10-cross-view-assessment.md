# 10 — Cross-view Review assessment + visible-support reasons

Status: ready-for-agent

Blocked by: 09, 07

## Final Spec mapping

- DG-19 P1
- §32 ViewAssessmentPolicy P1
- MVP Phase 4

## Inputs / preconditions

- Stable cross-view Gaussian evidence/visibility
- AIView assessments
- Gallery/Review UI

## Outputs / handoff artifacts

- cross-view-inconsistency reason
- low-visible-support reason
- P1 diagnostics
- Updated Review queue

## What to build

Add the P1 cross-view assessment layer as a separate, testable Companion policy slice. Use Gaussian
evidence/visibility semantics rather than raw 2D mask-area or image IoU heuristics.

## Acceptance criteria

- [ ] Cross-view assessment computes only from version-bound Stable Mask, Contributor/Visibility, and cross-view Gaussian evidence.
- [ ] `cross-view-inconsistency` is emitted only from validated Gaussian-evidence consistency logic, not raw 2D area comparison alone.
- [ ] `low-visible-support` is preferred over claiming semantic strong-occlusion when only visibility evidence is available.
- [ ] P1 diagnostics may include crossViewPrecision, crossViewRecall, visibleTargetRatio or equivalent calibrated measures.
- [ ] Raw mask-area outlier remains internal diagnostic unless perspective/visibility normalization justifies a user-visible reason.
- [ ] `identity-drift` remains future taxonomy and is not emitted in v1.0 without a separately validated detector.
- [ ] P1 assessment automatically refreshes metadata when enough stable evidence becomes available but does not trigger Repropagate or Re-Lift.
- [ ] User Confirmed authority remains dominant; P1 assessment cannot silently re-exclude or down-weight a user-confirmed Included View.
- [ ] Gallery/Selected View Detail displays only the top actionable P1 reason(s) with the same static frontend Reason→Action mapping.

## Failure / recovery criteria

- [ ] Insufficient cross-view evidence yields no fabricated cross-view reason.
- [ ] Policy failure does not corrupt existing local/P0 assessment or participation.

## Affected seams

- Companion ViewAssessmentPolicy P1
- Companion visibility/evidence primitives
- src/ai-select assessment presentation

## Validation

- npm run test:companion
- npm test
- Cross-view fixture tests
- Locked GPU visibility/evidence smoke
- False-positive/false-negative benchmark inputs prepared for Ticket 21

## Non-goals

- No new deep model inference
- No identity-drift requirement
