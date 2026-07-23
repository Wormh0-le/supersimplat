# 11 — User-added AIView using current or adjusted camera

Status: ready-for-agent — v2.2 re-audited

Blocked by: 09, 07, 05

## Final Spec mapping

- Final Spec v1.1 §§7, 9, 13, 27–28
- DG-08, DG-13, DG-20
- MVP Phase 4

## Inputs / preconditions

- Current Scene View
- Camera Inspection / true render-attempt Retry
- AIView/Mask/Assessment/Participation contracts

## Outputs / handoff artifacts

- User-owned RGB-ready AIView
- Optional Auto/Manual Stable Mask
- Evidence=`not-requested`/later-derived state
- User-added frustum

## What to build

Implement user-owned Views through the same View/Mask/assessment/Participation contracts as planner Views. Authoritative RGB publication is independent from Mask and Evidence.

## Acceptance criteria

- [ ] `Use Current View` creates a user-owned AIView from Current Scene View CameraBinding without moving Editor Camera.
- [ ] `Adjust New View…` creates a provisional frustum, enters Camera Inspection, and publishes only after explicit Confirm View.
- [ ] User-added RGB comes from authoritative gsplat and shares exact CameraBinding with frustum.
- [ ] RGB Ready does not require complete Contributor, Stable Mask, or Evidence.
- [ ] A user-added View may remain Ready with No Mask and Evidence Not Requested.
- [ ] No-Mask UI offers Auto Generate Mask / Manual Draw / Exclude.
- [ ] Auto Mask may use propagation/SAM/fallback without exposing unnecessary strategy detail.
- [ ] Manual Draw uses empty Editing Mask and normal Confirm Mask publication.
- [ ] Publishing Stable Mask marks per-view Evidence dirty/missing; it does not auto-Lift.
- [ ] User-added View uses the same assessment, Participation, Gallery, readiness, Evidence, and lifting pipeline as auto/replacement Views.
- [ ] View source never determines trust.
- [ ] Regenerate Auto Views cannot remove user-owned Views.
- [ ] Adding/confirming user View never implicitly resumes planner.

## Failure / recovery criteria

- [ ] Render failure keeps failed View record and supports true Retry / Exclude.
- [ ] Auto-mask failure preserves View/RGB and supports retry/manual/exclude.
- [ ] Later Evidence failure preserves View/RGB/Stable Mask.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion
- Locked GPU user-added RGB path
- RGB Ready + No Mask + Evidence Not Requested fixture

## Non-goals

- No persistent cross-target View library
- No production Evidence kernel