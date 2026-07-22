# 05 — Anchor editing completeness + validation + atomic Confirm Anchor + early Restart

Status: ready-for-agent

Blocked by: 03, 04

## Final Spec mapping

- DG-09
- DG-11
- DG-12
- §15–18 Anchor editing/validation
- §68 Mask Undo/Redo
- §69 Restart
- MVP Phase 2

## Inputs / preconditions

- Anchor AIView
- Editing/Stable Mask
- Camera Inspection
- CurrentTargetContext

## Outputs / handoff artifacts

- Complete Anchor authoring flow
- Validated/confirmed Anchor revision
- Early Restart flow

## What to build

Complete Anchor authoring and recovery: Prompt refine, Brush Add/Erase, Clear, Restore Auto, manual mask,
mask-local history/focus routing, Hard/Soft Anchor Validation, atomic Confirm Anchor, and Restart Current
Target available before Generated Views.

## Acceptance criteria

- [ ] Prompt refine, Brush Add, and Brush Erase modify only the Editing Mask until Confirm Mask.
- [ ] `Clear Mask` creates an empty Editing Mask; `Restore Auto` restores the most recent valid auto mask and is disabled if none has ever existed.
- [ ] A user can Clear → Brush Add/Erase → Confirm Mask to create a fully manual User Confirmed Stable Mask.
- [ ] Mask Editor maintains independent lightweight Undo/Redo history.
- [ ] Mask Editor focus routes Undo/Redo to mask history; normal 3D/editor focus routes Native Undo/Redo.
- [ ] UI gives explicit focus feedback so the Undo target is not ambiguous.
- [ ] Anchor Validation is computational suitability, not a semantic object-confidence score.
- [ ] Hard validation blocks Confirm Anchor for unavailable final gsplat RGB, empty/nearly-empty mask, no valid Gaussian contributor support, latest mask/SAM revision still computing, or mismatched CameraBinding/RGB/Mask binding.
- [ ] Soft warnings such as boundary contact, extreme size, fragmentation, occlusion/support concerns remain user-overridable and do not block Confirm Anchor.
- [ ] Validation refreshes automatically with the latest relevant revision and never confirms stale SAM/mask output.
- [ ] After first Prompt/Mask target intent, changing Anchor warns before discarding affected unconfirmed Prompt/Editing Mask state.
- [ ] Confirm Anchor atomically publishes one coherent Anchor revision containing CameraBinding, RGB digest, Stable Mask, Contributor binding, TargetDependencyToken, and Scene/Splat version identity.
- [ ] After Confirm Anchor, that coherent Anchor revision is locked as the current reference until an explicit permitted Anchor-adjust/restart flow changes it.
- [ ] `Restart Current Target` is available during Anchor Draft, Camera Inspection, Mask Editing, validation, and confirmed-Anchor early stages.
- [ ] Early Restart disposes target-local Anchor/View/Mask/review/readiness state, rotates targetContextId, preserves Native Selection/EditHistory/planner policy/shared runtime cache, and creates the new Anchor from Current Scene View.
- [ ] If Restart occurs during Camera Inspection, restore the saved Scene View first; inspection observer pose can never become the new Anchor.
- [ ] Restart confirmation policy distinguishes no meaningful draft, unconfirmed draft, and confirmed AI context, and clearly states that Native Selection will not change.
- [ ] Contextual toolbar exposes Anchor Invalid / Valid-with-warning / Valid states and enables Confirm Anchor only when allowed.

## Failure / recovery criteria

- [ ] Mask/SAM failure preserves the View and supports Retry Auto Mask / Manual Draw / Exclude once participation controls exist.
- [ ] Validation failure provides actionable recovery: Fix Mask, Adjust Anchor, or Restart Current Target.

## Affected seams

- src/ai-select/mask*
- src/ai-select/anchor-validation*
- src/ai-select/current-target-context*
- AI View Dock Mask Editor
- Contextual toolbar
- Editor focus/shortcut routing

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion for SAM/validation changes
- Manual focus-routing + restart confirmation walkthrough

## Non-goals

- No Generated Views beyond the Confirm Anchor transition
- No Candidate
