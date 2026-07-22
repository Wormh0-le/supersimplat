# 11 — User-added AIView using current or adjusted camera

Status: ready-for-agent

Blocked by: 09, 07, 05

## Final Spec mapping

- DG-08
- DG-13 Add View
- §25–29 User-added Views
- MVP Phase 4

## Inputs / preconditions

- Current Scene View
- Camera Inspection
- AIView/Mask/Assessment/Participation contracts

## Outputs / handoff artifacts

- User-owned AIView
- Optional Auto/Manual Stable Mask
- User-added frustum

## What to build

Implement user-owned Views through exactly the same downstream View/Mask/assessment/participation
contracts used by auto-generated Views.

## Acceptance criteria

- [ ] `Use Current View` creates a user-owned AIView from Current Scene View CameraBinding without moving the Editor Camera.
- [ ] `Adjust New View…` creates a provisional user-owned frustum, enters Camera Inspection, supports live authoritative gsplat preview, and publishes only after explicit Confirm View.
- [ ] User-added RGB/Contributor comes from authoritative gsplat and shares the exact CameraBinding with its frustum.
- [ ] A user-added View may remain Ready with No Mask.
- [ ] For No Mask, UI offers Auto Generate Mask / Manual Draw / Exclude View.
- [ ] Auto Generate Mask may internally use propagation, single-frame SAM, or validated fallback without exposing unnecessary strategy details.
- [ ] Manual Draw creates an empty Editing Mask and uses the same Confirm Mask → User Confirmed Stable Mask publication contract.
- [ ] User-added View uses the same assessment, user-confirmation, Participation, Gallery, coverage, and later lifting pipeline as auto-generated/replacement Views.
- [ ] View source never directly determines trust/participation.
- [ ] User ownership means Regenerate Auto Views cannot delete or replace user-added Views.
- [ ] Adding/confirming a user View never implicitly restarts automatic planning.

## Failure / recovery criteria

- [ ] User-added render failure keeps a failed View record and supports Retry / Exclude.
- [ ] Auto-mask failure preserves the View and supports Retry Auto Mask / Manual Draw / Exclude.

## Affected seams

- src/ai-select/user-view*
- Camera Inspection
- AI View registry
- Gallery sticky add action
- Companion gsplat render
- Companion SAM/propagation

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion
- Locked GPU end-to-end user-added View

## Non-goals

- No persistent cross-target View library
