# 11 — User-added AIView using current or adjusted camera

Status: blocked — waits for Gallery and complete correction UX

Blocked by: 09, 07B, 07, 05

## Final Spec mapping

- Final Spec v1.2 §§7, 19–21, 27–29
- DG-26 Decision 7

## Inputs / preconditions

- Current Scene View;
- Camera Inspection / true render-attempt Retry;
- AIView/Mask/Assessment/Participation contracts;
- Ticket 09 Gallery and generic acquisition states;
- Ticket 07B no-blind-spot Prompt/Edit correction UX;
- Ticket 08A/08B route-B contracts and production provider where automatic acquisition is requested.

## Outputs / handoff artifacts

- user-owned RGB-ready AIView;
- optional Auto/Manual Stable Mask;
- optional Prompt/Proposal/Decision artifacts for auto acquisition;
- Evidence=`not-requested`/later-derived state;
- user-added frustum.

## What to build

Implement user-owned Views through the same authoritative RGB, Prompt, acquisition, proposal decision, assessment, publication and Participation contracts as planner-owned Key Views.

Authoritative RGB publication remains independent from Mask and Evidence.

## Acceptance criteria

- [ ] `Use Current View` creates a user-owned AIView from Current Scene View CameraBinding without moving Editor Camera.
- [ ] `Adjust New View…` creates a provisional frustum, enters Camera Inspection, and publishes only after explicit Confirm View.
- [ ] User-added RGB comes from authoritative gsplat and shares exact CameraBinding with frustum.
- [ ] RGB Ready does not require complete Contributor, Stable Mask, acquisition, or Evidence.
- [ ] A user-added View may remain Ready with No Mask and Evidence Not Requested.
- [ ] No-Mask UI offers Auto Generate Mask / Manual Draw / Exclude.
- [ ] Auto Generate Mask uses the current backend registry and the same Prompt → ProposalSet → Decision → Assessment → Publication chain where exact support/bootstrap context is available.
- [ ] Auto acquisition never hides ambiguous proposals behind a Top-1 Mask.
- [ ] Technical route-B failure may use the same B2 route-A fallback policy; semantic Review/ambiguity does not auto-fallback.
- [ ] Manual Draw uses empty Editing Mask and normal Confirm publication.
- [ ] Ticket 07B palette behavior applies to user-added Prompt/Edit correction with no stale blind region.
- [ ] Publishing Stable Mask marks per-view Evidence dirty/missing; it does not auto-Lift.
- [ ] User-added View uses the same assessment, Participation, Gallery, readiness, Evidence, and lifting pipeline as auto Views.
- [ ] View source never determines trust.
- [ ] Regenerate Auto Views cannot remove user-owned Views.
- [ ] Adding/confirming user View never implicitly resumes planner.

## Failure / recovery criteria

- Render failure keeps failed View record and supports true Retry / Exclude.
- Prompt/acquisition failure preserves View/RGB and supports retry/manual/exclude and eligible technical fallback.
- Ambiguous retains ProposalSet and review/refinement actions; no arbitrary Stable Mask is published.
- Later Evidence failure preserves View/RGB/Stable Mask.
- Palette move/hide/disposal leaves no stale input interception.

## Validation

- `npm test`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- `npm run test:companion`
- locked GPU user-added RGB/acquisition path
- RGB Ready + No Mask + Evidence Not Requested fixture
- user-added selected/ambiguous/unavailable acquisition fixtures
- route-B technical failure/fallback fixture
- manual correction with Ticket 07B palette walkthrough

## Non-goals

- No persistent cross-target View library.
- No production Evidence kernel.
- No separate user-view acquisition architecture.
