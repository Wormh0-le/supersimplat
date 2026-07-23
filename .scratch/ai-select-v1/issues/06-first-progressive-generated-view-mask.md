# 06 — First progressive Generated AIView + Initial Auto Mask

Status: ready-for-agent — v2.2 re-audited

Blocked by: 05

## Final Spec mapping

- Final Spec v1.1 §§7, 13, 27, 28
- DG-08, DG-13, DG-20
- MVP Phase 3

## Inputs / preconditions

- Confirmed coherent Anchor revision
- Compatible Generated View planner primitives
- Authoritative gsplat RGB renderer
- SAM propagation/single-frame fallback

## Outputs / handoff artifacts

- First planner-owned Generated AIView
- Authoritative RGB identity
- Initial Auto Mask state
- Evidence=`not-requested`/later-derived state
- Generated frustum

## What to build

Prove progressive multi-view publication end to end. Publish a Generated AIView as soon as authoritative RGB is ready. Produce its Mask independently. Evidence is mask-conditioned and is not part of initial View rendering/publication.

## Acceptance criteria

- [ ] Confirm Anchor can start automatic planning without fixed user View count.
- [ ] At least one planner-owned Generated AIView publishes when authoritative gsplat RGB is ready.
- [ ] Generated AIView has stable viewId, source, CameraBinding, RGB identity, independent render/mask/evidence states, and Participation.
- [ ] RGB comes from authoritative gsplat and frustum derives from the exact CameraBinding.
- [ ] View publication does not move Editor Camera.
- [ ] Gallery may show RGB Ready while Mask is Generating and Evidence is Not Requested.
- [ ] Complete Contributor is not required for Generated View Render Ready.
- [ ] Once RGB is ready, automatic Mask production starts without blocking the View.
- [ ] Successful Mask production atomically publishes an auto Stable Mask bound to AIView/RGB.
- [ ] Publishing Stable Mask marks corresponding Evidence missing/dirty; it does not automatically perform formal Lift.
- [ ] Mask failure keeps AIView/RGB/frustum and produces RGB Ready + Mask Failed, not View Failed.
- [ ] Evidence failure, when later attempted, keeps View Render Ready.
- [ ] Render failure remains distinct and preserves a failed View record.
- [ ] Completed Views survive later planner failure.
- [ ] Late render/mask results with obsolete bindings are discarded.
- [ ] Generated frustum is selectable and read-only.

## Failure / recovery criteria

- [ ] Mask failure exposes retry/manual/exclude as later controls become available.
- [ ] View Render Failure exposes true Retry; replacement and Exclude complete in later tickets.
- [ ] No partial Mask or Evidence is published stable.

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