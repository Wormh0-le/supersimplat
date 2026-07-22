# 06 — First progressive Generated AIView + Initial Auto Mask

Status: ready-for-agent

Blocked by: 05

## Final Spec mapping

- §19 Initial Auto Complete
- §20 Progressive Generated Views
- §21 Generated Frustums
- MVP Phase 3

## Inputs / preconditions

- Confirmed coherent Anchor revision
- Existing compatible Generated View planner primitives
- gsplat renderer
- SAM propagation/single-frame fallback

## Outputs / handoff artifacts

- First planner-owned Generated AIView
- RGB/Contributor
- Initial Auto Mask state
- Generated frustum

## What to build

Prove the new progressive multi-view artifact path end to end. Publish the Generated AIView as soon as
RGB/Contributor is ready, then independently run Initial Mask Propagation (or validated internal fallback)
and publish an auto Stable Mask or a Mask Failed state without delaying/removing the View.

## Acceptance criteria

- [ ] Confirm Anchor can start initial automatic view planning without asking the user for a fixed view count.
- [ ] At least one planner-owned Generated AIView publishes progressively when authoritative gsplat RGB/Contributor is ready.
- [ ] Generated AIView has stable viewId, source=`auto-generated`, CameraBinding, RGB identity, Contributor identity, and independent render/mask lifecycle state.
- [ ] Generated RGB comes from authoritative gsplat and its viewport frustum is derived from the exact same CameraBinding.
- [ ] Generated View publication does not move the visible Editor Camera.
- [ ] Gallery/UI may show the Generated View at RGB Ready while its mask is still Generating.
- [ ] Once RGB is ready, initial automatic Mask production begins using propagation / single-frame SAM / validated fallback policy without blocking View publication.
- [ ] Successful initial mask production atomically publishes an auto Stable Mask bound to that AIView/RGB revision.
- [ ] Mask failure keeps the AIView, RGB, Contributor, and frustum; View status becomes RGB Ready + Mask Failed rather than View Failed.
- [ ] Generated View render failure is distinct from Mask failure and preserves a failed View record for recovery/diagnostics.
- [ ] Published/completed Views survive failure of later planner jobs.
- [ ] Late render or mask results from obsolete target/view/dependency revisions are discarded.
- [ ] Generated frustum is selectable but not pose-editable in MVP.

## Failure / recovery criteria

- [ ] Mask Generation Failure keeps the View and exposes retry/manual/exclude recovery as those controls become available in Tickets 07/09.
- [ ] View Render Failure exposes Retry immediately; replacement-generation and Exclude complete in Tickets 08/07 respectively.
- [ ] No partial auto mask is published as Stable Mask.

## Affected seams

- src/ai-select/ai-view*
- src/ai-select/view-registry*
- Companion generated_views.py compatible primitives
- Companion gsplat renderer
- Companion initial mask propagation/SAM
- Viewport generated frustum

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Locked GPU end-to-end: RGB Ready → mask Generating → Auto Stable/Failed

## Non-goals

- No full adaptive stop policy
- No scalable Gallery yet
- No cross-view assessment
