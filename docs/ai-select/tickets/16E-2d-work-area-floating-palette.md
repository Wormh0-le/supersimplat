# 16E — 2D Work Area chrome + floating-palette actions + explicit Re-Lift

Status: planned — blocked by Tickets 16C and 16D

Blocked by: 16C, 16D, 16B, 16A, 15, 11, 07B, 05

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

- [ ] The Dock-wide status/availability header is removed.
- [ ] The selected-work metadata header is removed.
- [ ] The bottom View Action Bar is removed.
- [ ] Service availability remains owned by the existing editor Status Bar and
      contextual disabled-control explanations.
- [ ] No-Target guidance, planning/loading feedback and Work Area failures use
      compact canvas states rather than persistent bars.
- [ ] The authoritative image receives the released vertical space and retains
      Ticket 16D contain/zoom behavior.

### Candidate Re-Lift

- [ ] Re-Lift is placed in the upper-right chrome of the AI Select Panel's 2D
      Work Area, outside the authoritative image.
- [ ] It is never placed in the editor's 3D viewport or Inspector.
- [ ] The visible glyph is approximately `18–20px` inside a hit area of at
      least `40×40px`.
- [ ] Re-Lift is the only emphasized target-level action in the Dock.
- [ ] It is available when usable Included Stable inputs exist and no Candidate
      exists, when Candidate is stale, or when the last replacement failed.
- [ ] Current exact-bound Lift Readiness gates the otherwise available action:
      Not Ready disables Re-Lift with an actionable reason; Limited permits
      Re-Lift with warning styling, tooltip and accessible description; Ready
      permits the normal path without a readiness warning. Limited does not add
      a second confirmation step by itself.
- [ ] Missing, stale or identity-mismatched Lift Readiness cannot be presented
      as Ready and disables Re-Lift until the current state is resolved.
- [ ] It shows updating progress and is disabled during an active update.
- [ ] It is hidden when Candidate is current.
- [ ] It is blocked when any Included View has unconfirmed Mask changes.
- [ ] Every unavailable or disabled reason is exposed through the project
      tooltip service and accessible description.
- [ ] Successful Re-Lift reuses Ticket 15's exact Evidence-aware atomic update;
      no alternate Candidate publication path is introduced.

### Floating palette

- [ ] The existing floating palette remains the only 2D Mask toolbar.
- [ ] One stable slot resolves in priority order to Confirm Mask, confirm Review
      as-is, and Confirm Anchor.
- [ ] Initial Anchor Mask confirmation composes Confirm Mask, fresh Anchor
      validation and atomic Confirm Anchor as one user intent.
- [ ] Changed-Anchor confirmation uses the same combined intent against the
      staged draft Camera/RGB/Mask. Only its successful atomic Confirm Anchor
      rotates identity, clears old dependent Views, and starts initial
      planning.
- [ ] While a changed-Anchor draft is rendered, reviewed or edited, the
      original Anchor run remains current and usable. Draft confirmation never
      publishes an intermediate Stable Mask into the original run.
- [ ] If Stable Mask already exists but Anchor is unconfirmed, the same slot
      validates and confirms the Anchor.
- [ ] An automatically published Stable Mask may enter correction from this
      palette; doing so creates Editing and retains the Stable revision until
      Confirm Mask.
- [ ] Standalone Validate Anchor and Confirm Anchor controls are removed;
      validation remains an internal correctness gate and its blocker is shown
      in Inspector.
- [ ] One stable contextual slot enters View-input Correction or returns to the
      current Candidate preview.
- [ ] Returning to Candidate preview retains unconfirmed edits and does not
      publish or discard them.
- [ ] Palette controls use coherent custom SVG icons, accessible tooltips and
      stable placement without adding a second toolbar.

## Failure / recovery criteria

- [ ] Failed Re-Lift preserves the previous stale Candidate atomically and
      reports the failure without partial publication.
- [ ] Failed Anchor validation preserves the current Stable Mask and exposes a
      retryable confirmation state in the same palette slot. For a changed-
      Anchor draft, failure also preserves the entire original run and retains
      the draft for correction or cancellation.
- [ ] Switching to Candidate preview during Correction cannot silently publish
      or discard an Editing draft.
- [ ] A missing target or unavailable service cannot leave an enabled action
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

## Non-goals

- No Candidate operation in the 2D Work Area
- No second Mask sub-toolbar
- No change to P/N/V Evidence, Lift Readiness evaluation or Candidate
  classification; this stage only maps readiness to Re-Lift enablement
- No new planning or retry control
- No 3D viewport toolbar redesign; Ticket 16F owns it
