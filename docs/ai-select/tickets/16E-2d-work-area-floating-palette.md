# 16E — 2D Work Area chrome + floating-palette actions + explicit Re-Lift

Status: implemented — 2026-08-17

Implemented from: 16C, 16D, 16B, 16A, 15, 11, 07B, 05 and the
Ticket 16F staged changed-Anchor draft

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4–8, 17–19, 21–22, 24–26
- Ticket 16B product contract and superseding ADR
- Ticket 16C Mask/Inspector state truth
- Ticket 16D three-pane shell
- Tickets 05, 07B and 15 for Anchor confirmation, floating authoring and
  Correction/Re-Lift semantics

## Inputs / preconditions

- Authoritative selected-View RGB and Mask canvas
- Ticket 16C `hasUnconfirmedChanges` and Inspector projection
- Candidate initial/current/stale/updating/failed/correcting state
- Existing floating authoring palette and Anchor validation gate
- Existing Ticket 15 explicit Evidence-aware Re-Lift controller
- Current exact-bound Lift Readiness projection from Ticket 13
- Ticket 16F staged changed-Anchor Camera/RGB/Mask draft

## Outputs / handoff artifacts

- Header-free, action-bar-free 2D Work Area
- Compact upper-right Candidate Re-Lift control
- One dynamic confirmation slot in the floating palette
- One dynamic Correction/Candidate-preview slot in the floating palette
- Compact no-Target/loading/failure canvas states

## What to build

Return permanent chrome height to the authoritative 2D canvas. Keep all
View-input authoring in the existing floating palette, and place the one
target-level 2D-to-3D action in compact Work Area chrome outside the image.

## Acceptance criteria

### Work Area hierarchy

- [x] The Dock-wide status/availability header is removed.
- [x] The selected-work metadata header is removed.
- [x] The bottom View Action Bar is removed.
- [x] Service availability remains owned by the existing editor Status Bar and
      contextual disabled-control explanations.
- [x] No-Target guidance, planning/loading feedback and Work Area failures use
      compact canvas states rather than persistent bars.
- [x] The authoritative image receives the released vertical space and retains
      Ticket 16D contain/zoom behavior.

### Candidate Re-Lift

- [x] Re-Lift is placed in the upper-right chrome of the AI Select Panel's 2D
      Work Area, outside the authoritative image.
- [x] It is never placed in the editor's 3D viewport or Inspector.
- [x] The visible glyph is approximately `18–20px` inside a hit area of at
      least `40×40px`.
- [x] Re-Lift is the only emphasized target-level action in the Dock.
- [x] It is available when usable Included Stable inputs exist and no Candidate
      exists, when Candidate is stale, or when the last replacement failed.
- [x] Current exact-bound Lift Readiness gates the otherwise available action:
      Not Ready disables Re-Lift with an actionable reason; Limited permits
      Re-Lift with warning styling, tooltip and accessible description; Ready
      permits the normal path without a readiness warning. Limited does not add
      a second confirmation step by itself.
- [x] Missing, stale or identity-mismatched Lift Readiness cannot be presented
      as Ready and disables Re-Lift until the current state is resolved.
- [x] It shows updating progress and is disabled during an active update.
- [x] It is hidden when Candidate is current.
- [x] It is blocked when any Included View has unconfirmed Mask changes.
- [x] Every unavailable or disabled reason is exposed through the project
      tooltip service and accessible description.
- [x] Successful Re-Lift reuses Ticket 15's exact Evidence-aware atomic update;
      no alternate Candidate publication path is introduced.

### Floating palette

- [x] The existing floating palette remains the only 2D Mask toolbar.
- [x] One stable slot resolves in priority order to Confirm Mask, confirm Review
      as-is, and Confirm Anchor.
- [x] Initial Anchor Mask confirmation composes Confirm Mask, fresh Anchor
      validation and atomic Confirm Anchor as one user intent.
- [x] Changed-Anchor confirmation uses the same combined intent against the
      staged draft Camera/RGB/Mask. Only its successful atomic Confirm Anchor
      rotates identity, clears old dependent Views, and starts initial
      planning.
- [x] While a changed-Anchor draft is rendered, reviewed or edited, the
      original Anchor run remains current and usable. Draft confirmation never
      publishes an intermediate Stable Mask into the original run.
- [x] If Stable Mask already exists but Anchor is unconfirmed, the same slot
      validates and confirms the Anchor.
- [x] An automatically published Stable Mask may enter correction from this
      palette; doing so creates Editing and retains the Stable revision until
      Confirm Mask.
- [x] Standalone Validate Anchor and Confirm Anchor controls are removed;
      validation remains an internal correctness gate and its blocker is shown
      in Inspector.
- [x] One stable contextual slot enters View-input Correction or returns to the
      current Candidate preview.
- [x] Returning to Candidate preview retains unconfirmed edits and does not
      publish or discard them.
- [x] Palette controls use coherent custom SVG icons, accessible tooltips and
      stable placement without adding a second toolbar.

## Failure / recovery criteria

- [x] Failed Re-Lift preserves the previous stale Candidate atomically and
      reports the failure without partial publication.
- [x] Failed Anchor validation preserves the current Stable Mask and exposes a
      retryable confirmation state in the same palette slot. For a changed-
      Anchor draft, failure also preserves the entire original run and retains
      the draft for correction or cancellation.
- [x] Switching to Candidate preview during Correction cannot silently publish
      or discard an Editing draft.
- [x] A missing target or unavailable service cannot leave an enabled action
      that will mutate state.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- `rtk npm run build`
- Re-Lift absent-input, Not Ready, Limited-warning, Ready, current, stale,
  updating, failed and unconfirmed-input-blocked tests
- Confirm Mask, Review as-is, automatic-Stable correction and initial/changed-
  Anchor atomic confirmation tests
- Correction entry and return-to-Candidate-with-retained-draft tests
- Style/behavior contracts proving removed headers/action bar and stable palette
  slots
- Browser visual inspection of no-Target, planning, failure, Mask, Review,
  Candidate and Correction states

## Implementation record

- `src/ai-select/work-area-presentation.ts` is the fail-closed mapping seam for
  Candidate lifecycle, Included Stable inputs, unconfirmed Masks and current
  exact-bound Lift Readiness. It does not evaluate readiness or publish a
  Candidate.
- `src/ui/ai-select-anchor-dock.ts` removes the two headers and bottom action
  bar, owns compact canvas states, and routes the upper-right Re-Lift control
  through Ticket 15's `updateCandidate()` path.
- The floating palette owns stable confirmation and correction slots. Entering
  Correction branches an Editing Mask from the current Stable artifact without
  replacing Stable authority; Back to Candidate remains presentation-only.
- Changed-Anchor confirmation is a fresh support-probe validation followed by
  the synchronous `AISelectAnchorCutoverCoordinator` boundary. Live Anchor and
  Stable Mask publish before the new ConfirmedAnchor releases old Generated
  Views; Candidate and Lift Readiness products reset only after that rotation.
- Lifecycle tests prove old-run retention during draft work and failed
  validation, successful cutover ordering, and late-response inertness.

## Non-goals

- No Candidate operation in the 2D Work Area
- No second Mask sub-toolbar
- No change to P/N/V Evidence, Lift Readiness evaluation or Candidate
  classification; this stage only maps readiness to Re-Lift enablement
- No new planning or retry control
- No 3D viewport toolbar redesign; Ticket 16F owns it
