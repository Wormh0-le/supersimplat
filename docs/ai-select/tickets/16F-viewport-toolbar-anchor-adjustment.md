# 16F — Compact 3D viewport toolbar + non-destructive Anchor adjustment

Status: implemented — 2026-08-17

Prerequisites: 16B, 16A, 16, 11, 08, 05, 03 (implemented)

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4–5, 9–10, 17–19, 22, 24–25
- Ticket 16B product contract and superseding ADR
- Ticket 16A Candidate Overlay, native operations and presentation mapper
- Tickets 03, 05, 08 and 11 for camera, Anchor, dependent Views and user-added
  View lifecycle

## Inputs / preconditions

- Existing fixed AI Select 3D viewport sub-toolbar
- Candidate Overlay and Ticket 16 native Set/Add/Remove/Intersect operations
- Anchor current/adjusting/changed identity state
- Add Current View and Add From New Pose paths
- Target-local Views, Masks, Evidence, Candidate and scroll state

## Outputs / handoff artifacts

- Compact icon-only AI Select viewport toolbar
- Combined Anchor-state/Adjust control
- Add View split control
- Staged changed-Anchor Camera/RGB/Mask draft
- Deferred Anchor-run disposal until atomic changed-Anchor confirmation
- Stable icon family and accessible toolbar state

## What to build

Keep the editor's 3D viewport toolbar focused on spatial actions. Normal mode
contains only Anchor adjustment and Add View. Candidate and adjustment modes
retain their necessary operations, but text labels and redundant lifecycle
menus are removed.

## Acceptance criteria

### Toolbar surface

- [x] Normal mode contains one combined Anchor-state/Adjust control and one Add
      View split control.
- [x] Anchor status and adjustment are not rendered as separate controls or
      repeated text.
- [x] Add Current View is the split control's primary action and Add From New
      Pose is its alternate action.
- [x] Candidate mode retains Overlay and Ticket 16 Set/Add/Remove/Intersect in
      stable order.
- [x] Adjustment and Candidate operations use one coherent custom SVG family;
      no Unicode symbols or text substitutes remain.
- [x] The leading `AI Select` label, textual Anchor status, More menu, Restart
      Current Target and Exit AI Select are removed.
- [x] The existing global AI Select tool control remains the single exit
      affordance.
- [x] No Re-Lift action appears in the 3D viewport.
- [x] Visible glyphs remain compact while interactive hit areas are at least
      `40×40px`.
- [x] Tooltips, selected/pressed state, disabled reasons, focus and keyboard
      activation are complete for every operation.

### Anchor adjustment lifecycle

- [x] Entering Adjust Anchor preserves the current run and all dependent Views.
- [x] Canceling adjustment preserves Anchor, Views, Masks, Evidence, Candidate,
      Native Selection and scroll state.
- [x] Confirming an unchanged Anchor is a no-op and preserves the same state.
- [x] Confirming an actually changed adjustment pose stages a draft Anchor
      CameraBinding and authoritative RGB without rotating the current target
      identity or clearing the current run.
- [x] The changed-Anchor draft has its own Prompt and Editing Mask state. It
      requires fresh Mask confirmation and may require modified or additional
      Prompt input.
- [x] Only Ticket 16E's combined Confirm Mask, fresh validation and atomic
      Confirm Anchor cutover rotates the relevant identity, clears dependent
      generated and user-added Views, and begins the retained initial planning
      path.
- [x] Old asynchronous render, Mask, Evidence and Candidate work cannot publish
      across the successful changed-Anchor cutover.

## Failure / recovery criteria

- [x] Failed or canceled Anchor adjustment leaves the original run usable.
- [x] Failed draft render, Mask inference or validation cannot partially replace
      the original Anchor or its dependent artifacts; cancellation discards
      only the staged draft.
- [x] A failed changed-Anchor render can be escaped by changing/resetting pose
      and starting a new normal render; no explicit Retry Preview action is
      exposed.
- [x] Add View failure leaves an inspectable failed/excluded View record when a
      record exists and does not mutate Native Selection.
- [x] Toolbar presentation failure cannot execute a hidden or disabled native
      operation.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- `rtk npm run build`
- Normal, adjustment, Candidate current/stale/updating/failed and applied
  toolbar-state tests
- Anchor enter/cancel/no-op/stage-draft/atomic-cutover lifecycle and stale-
  publication tests
- Add Current View / Add From New Pose split-control tests
- Ticket 16 native-operation regression through the real applicability gate
- Toolbar keyboard, tooltip, pressed-state and disabled-reason tests
- Browser visual inspection of icon density and popover placement

## Implementation record

- Implemented in commit `7e61cb6` through the compact Toolbar presentation,
  Add View split control and staged Anchor-adjustment controller.
- Lifecycle tests cover enter/cancel/no-op, changed-pose draft isolation,
  validation, atomic cutover and late-result rejection.
- Ticket 16G revalidated the final Toolbar seam and removed the remaining
  identical-input Anchor/View recovery commands without adding Ticket 17
  lifecycle controls.

## Non-goals

- No Ticket 17 Restart Current Target implementation
- No Undo and Fix implementation
- No Re-Lift in the 3D viewport
- No adaptive viewpoint planning
- No change to Candidate application algebra or Native EditHistory
