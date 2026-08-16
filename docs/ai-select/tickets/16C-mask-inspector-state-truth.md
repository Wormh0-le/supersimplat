# 16C — Mask state truth + compact current-View Inspector

Status: planned — blocked by Ticket 16B

Blocked by: 16B, 16A, 15, 12, 07B, 07, 04

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4, 7–8, 17–19, 22, 24
- Ticket 16B single-result product contract and superseding ADR
- Ticket 16A shared presentation mapper and responsive Dock baseline
- Tickets 04, 07, 12 and 15 for Mask publication, Review, staleness and
  Correction semantics

Ticket 16B must make the current specification and ADR chain authoritative
before this stage closes.

## Inputs / preconditions

- Editing Mask and Stable Mask identities and versions
- PromptState and Mask authoring history
- Review, Participation and issue-reason state
- Candidate current/stale/correcting presentation state
- Ticket 16A Inspector and shared presentation mapper

## Outputs / handoff artifacts

- Authoritative `hasUnconfirmedChanges` presentation projection
- Compact three-section Inspector
- Inspector-owned Participation control
- Fully wrapping actionable issue and error content
- Reusable state consumed by the 16E Re-Lift gate and floating palette

## What to build

Make the Inspector the sole owner of current-View assessment and authoring
explanation. Correct the confirmed-Mask defect by deriving the visible draft
state from a real semantic difference between Editing and Stable artifacts,
not from the mere presence of a retained Editing Mask.

## Acceptance criteria

### Mask and Prompt truth

- [ ] A Stable Mask with no Editing Mask presents as confirmed; this is the
      normal state after eligible automatic Generated-View publication.
- [ ] A Stable Mask and identical retained Editing Mask also present as
      confirmed.
- [ ] Starting correction from an automatically published Stable Mask creates
      an independent Editing draft and keeps the previous Stable revision
      available to Evidence/Candidate until Confirm Mask.
- [ ] `hasUnconfirmedChanges` becomes true on the first real Mask or Prompt edit
      after confirmation.
- [ ] Browsing, mode switching or retaining an identical Editing artifact does
      not create a false unconfirmed state.
- [ ] Prompt and Mask version summaries identify the current published and
      editing revisions without exposing obsolete Proposal identities.
- [ ] Publishing a changed Stable Mask or changing Participation marks the
      Candidate stale through existing Ticket 12/15 ownership.
- [ ] Merely returning from Correction to Candidate preview preserves the draft
      and does not publish or discard it.

### Inspector ownership and layout

- [ ] Inspector contains `Assessment and Review`, `Prompt and Mask`, and a
      collapsed `Technical Details` section.
- [ ] Assessment shows Quality and one icon-based Participation control.
- [ ] Participation mutation is removed from Navigator cards.
- [ ] A third assessment line appears only when actionable issue reasons exist;
      normal Views reserve no empty information row.
- [ ] Prompt counts, Mask publication state and version summary are grouped
      separately from assessment.
- [ ] Technical identities and versions remain available but collapsed by
      default.
- [ ] Required status, blocker and error content wraps fully. It is not hidden
      by ellipsis or fixed-line truncation.
- [ ] Inspector does not duplicate primary confirmation, Re-Lift, planning or
      recovery actions.

### Accessibility

- [ ] Participation and disclosure controls have accessible names, visible
      focus and keyboard activation.
- [ ] Quality, Participation and issue state are not communicated by color
      alone.
- [ ] Collapsed technical detail retains correct disclosure semantics.

## Failure / recovery criteria

- [ ] A non-null Editing identity that is dangling, incompatible with the
      current View/RGB, or inconsistent with its Stable base fails closed as
      unconfirmed and exposes an actionable explanation. The intentional
      absence of Editing when Stable exists is not an error.
- [ ] A failed Participation mutation leaves the previous participation and
      Candidate state unchanged.
- [ ] Inspector rendering failure cannot mutate Prompt, Mask, Review,
      Participation, Evidence or Candidate state.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- Stable-without-Editing, identical Editing/Stable and first-real-edit
  presentation tests
- Participation and Candidate-staleness integration tests
- Inspector conditional-row, wrapping, disclosure and accessibility tests
- View A draft → View B → View A state-preservation regression

## Non-goals

- No Re-Lift control implementation; Ticket 16E owns it
- No Navigator layout or filtering; Ticket 16D owns it
- No Candidate classification or Evidence-policy change
- No recovery-action menu in Inspector
- No Ticket 17 Restart or multi-target lifecycle
