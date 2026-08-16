# 16C — Mask state truth + compact current-View Inspector

Status: implemented — 2026-08-16

Blocked by: 16B, 16A, 15, 12, 07B, 07, 04

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4, 7–8, 17–19, 22, 24
- Ticket 16B single-result product contract and superseding ADR
- Ticket 16A shared presentation mapper and responsive Dock baseline
- Tickets 04, 07, 12 and 15 for Mask publication, Review, staleness and
  Correction semantics

Ticket 16B made the current specification and ADR chain authoritative before
this stage closed.

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

- [x] A Stable Mask with no Editing Mask presents as confirmed; this is the
      normal state after eligible automatic Generated-View publication.
- [x] A Stable Mask and identical retained Editing Mask also present as
      confirmed.
- [x] Starting correction from an automatically published Stable Mask creates
      an independent Editing draft and keeps the previous Stable revision
      available to Evidence/Candidate until Confirm Mask.
- [x] `hasUnconfirmedChanges` becomes true on the first real Mask or Prompt edit
      after confirmation.
- [x] Browsing, mode switching or retaining an identical Editing artifact does
      not create a false unconfirmed state.
- [x] Prompt and Mask version summaries identify the current published and
      editing revisions without exposing obsolete Proposal identities.
- [x] Publishing a changed Stable Mask or changing Participation marks the
      Candidate stale through existing Ticket 12/15 ownership.
- [x] Merely returning from Correction to Candidate preview preserves the draft
      and does not publish or discard it.

### Inspector ownership and layout

- [x] Inspector contains `Assessment and Review`, `Prompt and Mask`, and a
      collapsed `Technical Details` section.
- [x] Assessment shows Quality and one icon-based Participation control.
- [x] Participation mutation is removed from Navigator cards.
- [x] A third assessment line appears only when actionable issue reasons exist;
      normal Views reserve no empty information row.
- [x] Prompt counts, Mask publication state and version summary are grouped
      separately from assessment.
- [x] Technical identities and versions remain available but collapsed by
      default.
- [x] Required status, blocker and error content wraps fully. It is not hidden
      by ellipsis or fixed-line truncation.
- [x] Inspector does not duplicate primary confirmation, Re-Lift, planning or
      recovery actions.

### Accessibility

- [x] Participation and disclosure controls have accessible names, visible
      focus and keyboard activation.
- [x] Quality, Participation and issue state are not communicated by color
      alone.
- [x] Collapsed technical detail retains correct disclosure semantics.

## Failure / recovery criteria

- [x] A non-null Editing identity that is dangling, incompatible with the
      current View/RGB, or inconsistent with its Stable base fails closed as
      unconfirmed and exposes an actionable explanation. The intentional
      absence of Editing when Stable exists is not an error.
- [x] A failed Participation mutation leaves the previous participation and
      Candidate state unchanged.
- [x] Inspector rendering failure cannot mutate Prompt, Mask, Review,
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

## Implementation record

Implemented on 2026-08-16 as one editor/domain/UI slice:

- Mask state now separates semantic Prompt changes, semantic Editing/Stable
  Mask changes and invalid Editing identity, so identical retained Editing
  artifacts remain confirmed while the first real Prompt or Mask edit is
  unconfirmed.
- Registry lineage validation rejects dangling, View/RGB-incompatible and
  Stable-base-inconsistent Editing pointers; automatic Stable correction keeps
  the prior Stable revision until explicit Confirm.
- The current-View Inspector consumes a reusable pure presentation projection,
  owns Quality/Participation/issues plus Prompt/Mask summaries, and exposes
  fully wrapping collapsed technical identities without Navigator mutation or
  duplicated recovery actions.
- Validation: `rtk npm test` (591 browser/TypeScript tests + 446 Companion
  tests, 1 skipped), `rtk npm run lint`, `rtk npm run lint:locales`, and
  `rtk npm run build`. This Ticket owns no locked-GPU path; no external
  validation was required.
