# 16D — Canvas-first three-pane shell + stable Navigator

Status: planned — blocked by Ticket 16B

Blocked by: 16B, 16A, 11, 09, 08, 07

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4, 9–10, 17–19, 22, 24–26
- Ticket 16B product contract and superseding ADR
- Ticket 16A responsive Dock baseline
- Tickets 08, 09 and 11 for generated, inspected and user-added Views

Ticket 16B must make the current specification and ADR chain authoritative
before this stage closes.

## Inputs / preconditions

- Stable per-View creation identity and role metadata
- View RGB, Review, processing, failure and Participation presentation state
- Existing Navigator filtering, selection and scroll behavior
- Existing Dock resize and sidebar-collapse infrastructure
- Initial bounded planning and failure-only planning retry

## Outputs / handoff artifacts

- Navigator / 2D Work Area / Inspector shell with 2D canvas priority
- Persistent resizable sidebars with coherent collapse/restore controls
- Stable Gallery projection and explicit filter/sort behavior
- Compact thumbnail-only Navigator cards
- Contextual planning/loading/failure empty states

## What to build

Refit the Dock as a desktop technical workbench whose 2D Work Area receives
surplus width and height. Make the Navigator primarily a visual View list.
Filtering and sorting are explicit presentation choices; ordinary View
selection must never reorder the Gallery.

## Acceptance criteria

### Three-pane shell

- [ ] Wide layouts render Navigator, 2D Work Area and Inspector in that order.
- [ ] Navigator defaults to approximately `220px` and supports `180–280px`.
- [ ] Inspector defaults to approximately `280px` and supports `240–360px`.
- [ ] Surplus width belongs to the 2D Work Area.
- [ ] User-controlled sidebar widths and expanded states persist as local
      editor/device preferences only.
- [ ] Expanded sidebars push the Work Area instead of overlaying the
      authoritative image.
- [ ] Each expanded sidebar owns a header collapse control; a collapsed sidebar
      leaves only a small adjacent-edge restore affordance.
- [ ] Constrained layouts collapse Inspector before Navigator and always keep
      the Work Area resident.
- [ ] The authoritative RGB/Mask remains centered, aspect-preserving and
      contained with a small safety margin; it is never cropped or stretched
      to satisfy pane widths.
- [ ] Automatic fit stops after manual zoom and resumes only on explicit reset.

### Navigator controls and projection

- [ ] Navigator title row contains only `Navigator` and its collapse control.
- [ ] One compact trigger below the title displays the active Filter and Sort
      combination and opens two radio groups.
- [ ] Filter options are `All` and `Needs Review`.
- [ ] Sort options are global creation order, newest first and Needs Review
      first.
- [ ] Default order is strict global creation order across Anchor, generated
      and user-added Views.
- [ ] Selecting a View may scroll it into view but never changes its position.
- [ ] Filtering is a pure presentation projection and mutates no View state.
- [ ] If the current View no longer matches, the first matching View becomes
      current. No match shows an explicit filter-empty state.

### Navigator items and exceptional states

- [ ] Each item is a full-width 16:9 thumbnail with no multi-line metadata.
- [ ] Anchor identity is an overlay pin, workflow state is one prioritized
      badge and selection is an inset outline.
- [ ] Badge priority is failure, Needs Review, processing, then ready.
- [ ] Excluded Views are low-emphasis but remain inspectable.
- [ ] Quality, Mask, role and Participation text are absent from cards.
- [ ] Persistent Stop, Continue, Generate More and Regenerate controls are not
      rendered.
- [ ] Initial planning failure exposes one recovery icon only in the Navigator
      empty/error state.
- [ ] The retained fixed-offset initial planner may produce `1–3` automatic
      Views; this stage changes only its presentation, not its camera choices.
- [ ] No-Target, initial planning, loading, failure and filter-empty states are
      compact and do not replace an existing Anchor or completed View list.

### Accessibility

- [ ] Visible sidebar, filter/sort, retry and thumbnail controls keep at least
      a `40×40px` hit area where interactive.
- [ ] Icon controls expose accessible names, focus state and tooltips.
- [ ] Filter/sort popover closes on Escape/outside click and restores focus.

## Failure / recovery criteria

- [ ] Corrupt saved width/expanded preferences clamp to supported defaults.
- [ ] Empty filtering cannot leave a hidden View active in the Work Area.
- [ ] Initial planning retry creates a normal new planning attempt and cannot
      resurrect stale output.
- [ ] Layout, filter, sort, selection and scroll state never enter Prompt,
      Mask, Evidence, Candidate identity or project data.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- `rtk npm run build`
- Gallery order, explicit sort, filter, first-match selection and empty-state
  behavior tests
- Sidebar resize persistence, collapse/restore and invalid-preference tests
- Pure-layout checks at wide desktop, approximately `1280×720` and
  approximately `1024×720`
- Browser visual inspection of normal, loading, failure, filter-empty and
  collapsed-sidebar states

## Non-goals

- No adaptive or marginal-gain camera planner
- No generation of replacement viewpoints
- No per-View delete action
- No Participation mutation in Navigator
- No 2D palette or Re-Lift implementation; Ticket 16E owns them
