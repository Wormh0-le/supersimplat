# 04 — Anchor AIView + independent Editing / Stable Mask / Evidence lifecycle

Status: ready-for-agent — v2.2 re-audited

Blocked by: 02

## Final Spec mapping

- Final Spec v1.1 §§7, 10, 11, 18, 24
- DG-08, DG-09, DG-20
- MVP Phase 2

## Inputs / preconditions

- Anchor AIView/RGB identity
- Single-frame SAM runtime
- CurrentTargetContext

## Outputs / handoff artifacts

- AIView render/mask/evidence state separation
- MaskAnnotation versions
- editingMaskId / stableMaskId
- Atomic Confirm Mask publication
- Per-view Evidence invalidation identity

## What to build

Introduce the current per-view Mask domain. AIView, Mask, and Evidence are independently versioned: RGB Ready does not require a Mask or Evidence; Stable Mask is the formal annotation input; Evidence is a later derived artifact.

## Acceptance criteria

- [ ] AIView may be RGB Ready with no Mask and Evidence=`not-requested`.
- [ ] AIView may remain RGB Ready when Evidence is stale or failed.
- [ ] Mask identity/lifecycle is independent from View identity/lifecycle.
- [ ] Anchor exposes independent editingMaskId and stableMaskId.
- [ ] SAM output creates/replaces Editing Mask and never silently overwrites Stable Mask.
- [ ] Prompt changes trigger single-frame SAM feedback without an extra apply action.
- [ ] Brush strokes update Editing Mask locally.
- [ ] Confirm Mask atomically publishes the current Editing Mask as a new Stable Mask revision.
- [ ] Until Confirm succeeds, downstream users continue seeing the previous Stable Mask and Evidence/Candidate remain current.
- [ ] Publishing a new Stable Mask invalidates only dependent per-view Evidence by exact RGB/Mask/policy identity; if Included, Candidate becomes stale.
- [ ] Automatic and fully manual masks use the same publication contract.
- [ ] Mask artifacts bind to AIView/RGB identity so stale output cannot attach to changed RGB/CameraBinding.
- [ ] Render, Mask, Evidence, and Candidate statuses remain distinct.

## Failure / recovery criteria

- [ ] Mask generation failure keeps View/RGB available and permits retry/manual recovery.
- [ ] Partial/stale SAM output is not published as Stable Mask.
- [ ] Evidence failure never mutates Stable Mask or View render status.

## Affected seams

- src/ai-select/ai-view*
- src/ai-select/mask*
- src/ai-select/evidence-state*
- AI View Dock selected-view/mask surface
- Companion SAM adapter/runtime

## Validation

- npm test
- npm run lint
- npm run test:companion
- Atomic Stable publication tests
- Editing-no-stale versus Confirm-invalidates-Evidence tests
- Stale RGB/mask binding rejection tests

## Non-goals

- No multi-view propagation
- No production Evidence kernel
- No Candidate/lifting
- No full mask-history UX