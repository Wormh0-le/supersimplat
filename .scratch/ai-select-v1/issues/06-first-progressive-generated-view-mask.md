# 06 — First progressive Generated AIView + Initial Auto Mask

Status: complete

Blocked by: 05

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27, 28
- Final Spec v1.1 Amendments 003 and 004 handoff
- DG-08, DG-13, DG-20, DG-24
- MVP Phase 3

## Inputs / preconditions

- Confirmed coherent Anchor revision
- Compatible Generated View planner primitives
- Authoritative gsplat RGB renderer
- Projected-support + single-frame SAM baseline

## Outputs / handoff artifacts

- First planner-owned Generated AIView
- Authoritative RGB identity
- Initial Auto Mask state
- Evidence=`not-requested`/later-derived state
- Generated frustum

## What to build

Prove progressive multi-view publication end to end. Publish a Generated AIView as soon as authoritative RGB is ready. Produce its Mask independently. Evidence is mask-conditioned and is not part of initial View rendering/publication.

## Acceptance criteria

- [x] Confirm Anchor can start automatic planning without fixed user View count.
- [x] At least one planner-owned Generated AIView publishes when authoritative gsplat RGB is ready.
- [x] Generated AIView has stable viewId, source, CameraBinding, RGB identity, independent render/mask/evidence states, and Participation.
- [x] RGB comes from authoritative gsplat and frustum derives from the exact CameraBinding.
- [x] View publication does not move Editor Camera.
- [x] Gallery may show RGB Ready while Mask is Generating and Evidence is Not Requested.
- [x] Complete Contributor is not required for Generated View Render Ready.
- [x] Once RGB is ready, automatic Mask production starts without blocking the View.
- [x] Successful Mask production atomically publishes an auto Stable Mask bound to AIView/RGB.
- [x] Publishing Stable Mask marks corresponding Evidence missing/dirty; it does not automatically perform formal Lift.
- [x] Mask failure keeps AIView/RGB/frustum and produces RGB Ready + Mask Failed, not View Failed.
- [x] Evidence failure, when later attempted, keeps View Render Ready.
- [x] Render failure remains distinct and preserves a failed View record.
- [x] Completed Views survive later planner failure.
- [x] Late render/mask results with obsolete bindings are discarded.
- [x] Generated frustum is selectable and read-only.

## Failure / recovery criteria

- [x] Mask failure exposes retry/manual/exclude as later controls become available.
- [x] View Render Failure exposes true Retry; replacement and Exclude complete in later tickets.
- [x] No partial Mask or Evidence is published stable.

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Locked GPU: RGB Ready → Mask Generating → Auto Stable/Failed
- RGB Ready without Contributor/Evidence fixture

## Non-goals

- No full adaptive stop policy
- No scalable Gallery
- No formal Evidence production or cross-view assessment

## Implementation recorded — 2026-07-25

Editor (TypeScript):

- `src/ai-select/generated-view-service.ts` — versioned protocol contracts `generated-view-planner/v1` and `generated-view-mask/v1`.
- `src/ai-select/generated-view-controller.ts` — progressive View publication, exact run identity, per-view render/Mask failure isolation, and true Retry.
- `src/ai-select/mask-registry.ts` — atomic automatic Stable Mask publication.
- `src/ai-select/anchor-controller.ts` — shared target stale-result gate and Scene Snapshot seam.
- `src/ai-select/generated-frustum-picking.ts` / `src/ai-select-generated-frustums.ts` — exact CameraBinding frustums and selection.
- UI / transport / readiness — Generated View cards, routes, cache-miss recovery, and capability gate.

Companion (Python):

- `generated_view_planning.py` — pure-CPU robust seed, deterministic fixed-pair tracer planner, and projected Prompt synthesis.
- `state.py` / `server.py` — plan/render/mask routes, replay/Retry identity, single operation admission, and failure mapping.
- The Mask route projects Anchor support into each Generated View, synthesizes positive points, and runs one independent single-frame SAM pass.

## Validation recorded — 2026-07-25

- `npm test` — 268 editor tests passed.
- `npm run test:companion` — 232 tests passed.
- `npm run lint`, locale lint, and build passed.
- Browser/frustum and renderer re-verification passed.

## DG-24 handoff — 2026-07-30

Ticket 06 remains complete. Its projected-support + one independent single-frame SAM pass is classified as:

- the progressive publication tracer bullet;
- route A in Ticket 08A's multi-view Mask acquisition spike;
- a production fallback when the selected route fails or is unavailable;
- a foundation for enhanced 3D-guided per-Key-View Prompt synthesis.

Ticket 08 replaces the fixed pair with non-ownership 2.5D sparse Key-View planning. Ticket 08A compares and implements acquisition routes. Object tracking is optional and must not be inferred from Ticket 06's completion.
