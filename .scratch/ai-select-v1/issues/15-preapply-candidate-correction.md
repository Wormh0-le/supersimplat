# 15 — Pre-apply Candidate correction + explicit Re-Lift

Status: ready-for-agent

Blocked by: 14, 12, 09

## Final Spec mapping

- DG-15
- §59–63 Candidate correction
- Typical Flow G

## Inputs / preconditions

- Candidate Ready/Stale
- Gallery/Review/Mask/Participation controls
- Explicit Re-Lift

## Outputs / handoff artifacts

- Correction mode
- Candidate Stale transitions
- Updated Candidate

## What to build

Implement structural AI-result correction before Candidate application. Users fix observations and
explicitly Re-Lift; they never directly paint/patch the Candidate Gaussian set in v1.0.

## Acceptance criteria

- [ ] Candidate Ready exposes secondary `Fix AI Result` action.
- [ ] Entering correction preserves the current Candidate as a 3D reference while returning focus to Gallery/View/Mask/Participation controls.
- [ ] Browsing Views or editing an unconfirmed Editing Mask alone does not stale Candidate.
- [ ] Confirming changed Stable Mask, changing Participation, or otherwise changing Included Stable Inputs makes Candidate Stale.
- [ ] Stale Candidate cannot execute Set/Add/Remove/Intersect.
- [ ] Candidate Stale contextual toolbar shows `Update 3D Candidate`.
- [ ] `Update 3D Candidate` performs explicit Re-Lift and atomically publishes a new current Candidate.
- [ ] Correction guidance may suggest Fix Mask / Exclude View / Generate More / Add View but never claims exact Candidate/Gaussian provenance unsupported by DG-14.
- [ ] AI Candidate cannot be directly 3D painted/patched/merged as a correction mechanism.
- [ ] Small final local edits remain the responsibility of native SuperSplat selection tools after application.

## Failure / recovery criteria

- [ ] Failed Re-Lift leaves the previous Candidate available only as stale/reference and never marks it current.
- [ ] Correction-mode exit does not discard Stable inputs unless the user explicitly Restarts target.

## Affected seams

- src/ai-select/candidate*
- src/ai-select/correction*
- AI View Dock
- Contextual toolbar
- Candidate visualization

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Workflow tests for browse/editing-no-stale vs Stable-input-stale

## Non-goals

- No Applied Undo-and-Fix yet
- No Candidate provenance/source inspector
