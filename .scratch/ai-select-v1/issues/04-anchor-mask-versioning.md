# 04 — Anchor AIView + independent Editing / Stable Mask lifecycle

Status: ready-for-agent

Blocked by: 02

## Final Spec mapping

- DG-08
- DG-09
- §13–17 Mask model
- MVP Phase 2

## Inputs / preconditions

- Anchor AIView/RGB identity
- Single-frame SAM runtime
- CurrentTargetContext

## Outputs / handoff artifacts

- MaskAnnotation versions
- editingMaskId
- stableMaskId
- Atomic Confirm Mask publication

## What to build

Introduce the Final Spec mask domain for the Anchor. Product/domain truth is per-view versioned mask
annotation; PromptLog/MaskTrack may remain only as lower-level adapter compatibility details while
migration proceeds.

## Acceptance criteria

- [ ] An AIView may be RGB/Contributor-ready with no Mask.
- [ ] Mask identity/lifecycle is independent from View identity/lifecycle.
- [ ] Anchor mask state exposes independent editingMaskId and stableMaskId.
- [ ] Single-frame SAM output creates/replaces an Editing Mask; it never silently overwrites Stable Mask.
- [ ] Prompt changes trigger single-frame SAM feedback automatically without an extra Apply Mask Edit action.
- [ ] Brush strokes update the Editing Mask locally and immediately.
- [ ] Confirm Mask atomically publishes the current Editing Mask as a new Stable Mask revision.
- [ ] Until Confirm Mask succeeds, downstream consumers continue to see the previous Stable Mask revision.
- [ ] Automatic and fully manual masks share the same Stable publication contract.
- [ ] Mask artifacts bind to AIView/RGB identity so stale mask output cannot attach to changed RGB/CameraBinding.
- [ ] View render state, mask generation state, and mask quality remain separate concepts.

## Failure / recovery criteria

- [ ] Anchor mask generation failure keeps the Anchor View/RGB available and allows retry/manual recovery.
- [ ] Partial/stale SAM output is not published as Stable Mask.

## Affected seams

- src/ai-select/ai-view*
- src/ai-select/mask*
- AI View Dock selected-view/mask surface
- Companion SAM single-frame adapter/runtime
- Legacy masking internals as compatibility seam only

## Validation

- npm test
- npm run lint
- npm run test:companion
- Atomic Stable publication tests
- Stale RGB/mask-binding rejection tests

## Non-goals

- No multi-view propagation
- No Candidate/lifting
- No full mask-history UX yet
