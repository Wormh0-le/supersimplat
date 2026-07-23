# 15 — Pre-apply Candidate correction + explicit Evidence-aware Re-Lift

Status: ready-for-agent — v2.2 re-audited

Blocked by: 14, 13, 12, 09

## Final Spec mapping

- Final Spec v1.1 §§24–25
- DG-15, DG-20
- Typical Flow G

## Inputs / preconditions

- Candidate Ready/Stale
- Gallery/Review/Mask/Participation controls
- Per-view Evidence artifacts and dirty identities
- Explicit Re-Lift

## Outputs / handoff artifacts

- Correction flow
- Candidate Stale transitions
- Evidence reuse/recompute plan
- Updated atomic Candidate

## What to build

Implement structural correction before Candidate application. Users change observations and explicitly Re-Lift. Re-Lift reuses exact matching per-view Evidence and recomputes only missing/stale artifacts before aggregation/classification.

## Acceptance criteria

- [ ] Candidate Ready exposes `Fix AI Result`.
- [ ] Correction preserves current Candidate as reference while returning to View/Mask/Participation controls.
- [ ] Browsing or editing an unconfirmed Editing Mask does not stale Candidate or Evidence.
- [ ] Confirmed Stable Mask, Camera/RGB revision, Evidence Policy/Working Set change, or Participation change updates exact dirty/stale state.
- [ ] Stale Candidate cannot execute Set/Add/Remove/Intersect.
- [ ] Candidate Stale toolbar exposes `Update 3D Candidate`.
- [ ] Update resolves exact Included Stable View set, reuses matching per-view Evidence, recomputes stale/missing P/N/V, aggregates, classifies, and publishes atomically.
- [ ] Excluded View artifacts may remain cached but do not contribute.
- [ ] Failed Re-Lift does not promote a partial artifact or stale Candidate.
- [ ] Guidance may suggest Fix Mask / Exclude / Generate More / Add View but never invents DG-14 provenance.
- [ ] Candidate cannot be directly 3D painted/patched/merged.
- [ ] Small final edits remain native-selection work after application.

## Failure / recovery criteria

- [ ] Failed Evidence recomputation or aggregation leaves previous Candidate stale/reference only.
- [ ] Correction exit preserves Stable inputs unless explicit Restart occurs.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Per-view Evidence reuse/invalidation tests
- browse/editing-no-stale versus Stable-input-stale workflows
- failed recompute preserves prior Candidate

## Non-goals

- No Applied Undo-and-Fix
- No Candidate provenance/source inspector
- No production Direct Evidence kernel