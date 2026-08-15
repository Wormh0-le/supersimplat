# 16A — AI View Dock + Candidate viewport presentation

Status: ready-for-agent — Final Spec v1.3 mapped

Blocked by: 16, 15

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§22, 24
- Final Spec v1.3 §§4, 17–19 for target-local View/Correction and presentation lifecycle
- [AI Select Toolbar 布局与交互设计](../ai-select-toolbar-layout.md)
- [AI View Dock 布局设计](../ai-view-dock-layout.md)
- Ticket 15 Correction semantics and Ticket 16 native application semantics

Final Spec v1.3 remains the current product authority. The Toolbar design is
the presentation contract for this execution stage and does not redefine
Candidate, Native Selection, Evidence or EditHistory semantics.

## Inputs / preconditions

- Inspectable Candidate publication with Selected and optional Uncertain IDs
- Candidate current/stale/updating/update-failed state
- Ticket 15 Candidate Correction controller
- Ticket 16 Candidate Application controller and applicability gate
- Native Selection, `SelectOp` and `EditHistory`
- Existing fixed AI Select Toolbar, AI View Dock and Status Bar
- Existing splat sorting, transform and overlay rendering infrastructure
- Per-View Prompt, Proposal, Editing/Stable Mask, Review and Participation
  presentation state

## Outputs / handoff artifacts

- Non-destructive main-viewport Candidate Overlay
- Responsive three-column AI View Dock
- Fixed Candidate Operation Group in the AI Select Toolbar
- AI Candidate count and lifecycle status in the Status Bar
- Shared Dock/Toolbar/Status Bar presentation mapper
- `Back to Candidate` Correction transition
- Ticket 17 extension seam for `Undo and Fix` and Native history tracking

## What to build

Rebuild the AI View Dock around the accepted Navigator / selected View Work
Area / Inspector layout, then move Candidate inspection and native application
to the main-viewport AI Select Toolbar without reopening Ticket 16's
implemented application core. Replace the Dock's minimal Candidate-status
emphasis with a real, presentation-only 3D Candidate Overlay, and project the
same authoritative Candidate/Correction/Application state into the Dock,
Toolbar and Status Bar.

The cutover is one vertical slice. Implementation commits may build the new
renderer and surfaces incrementally, but Ticket closure must not leave two
supported application entry points or a Candidate that cannot be applied.

## Acceptance criteria

### AI View Dock

- [ ] Wide Dock renders View Navigator, Selected AI View Work Area and Current
      View Inspector as three columns under one compact top bar.
- [ ] Initial Navigator width remains within `190–238px` and Inspector width
      within `280–350px`. The Work Area uses authoritative RGB aspect ratio,
      available height and sidebar constraints to determine an ideal width;
      excess width is not converted into larger empty image letterboxing.
- [ ] RGB/Mask uses complete, centered, aspect-preserving contain semantics;
      it is never cropped or stretched merely to fill the Work Area.
- [ ] At approximately `1280×720`, all three columns are available. At
      approximately `1024×720`, Navigator and Work Area remain resident while
      Inspector may collapse. Below the supported narrow threshold, Work Area
      remains resident and either sidebar may collapse.
- [ ] Expanded sidebars push rather than cover the Work Area. Escape, close or
      the trigger collapses them, returns focus to the trigger and preserves the
      current View, drafts and per-region scroll positions.
- [ ] Dock defaults to `420px` high, clamps to a `300px` minimum and the main
      editor height minus `160px` maximum, and saves user-resized height only as
      a device/editor preference.
- [ ] Top bar, image and View Action Bar remain fixed. Navigator and Inspector
      scroll independently; the image never enters their scroll containers.
- [ ] The compact top bar combines availability, Candidate-production summary
      and Included View count with at most one contextual action. It never
      contains Native Candidate Operations.
- [ ] Navigator fixes the current View above filtered results without
      duplication, provides `All Views` and the one resident `Review N` filter,
      and keeps Participation control only on View cards.
- [ ] View switching preserves per-View Prompt, Proposal, Editing Mask and
      Prompt/Mask undo history; it cancels only an uncommitted pointer gesture
      and does not show a confirmation dialog for ordinary navigation.
- [ ] The Work Area contains a lightweight View header, non-overlapping Tool
      Rail, authoritative RGB/Prompt/Mask canvas and one View Action Bar. Around
      `1024px`, the Tool Rail may become horizontal.
- [ ] Proposal choice uses previous/next controls over the image, revealed on
      hover or keyboard focus only when more than one Proposal exists. One
      Proposal has no switcher; zero Proposals expose no counter or action; no
      uncalibrated raw model score is shown. Accept Proposal is a compact image
      overlay instead of a dedicated action row. Each View state exposes exactly
      one primary action: Accept Proposal, Confirm Mask, Confirm As Is, Retry
      Mask or explicit Next Review. An empty View Action Bar is hidden.
- [ ] Inspector owns current-View explanations and low-frequency/recovery
      actions. It does not duplicate the primary action or Participation toggle.
- [ ] Planner Planning/Failed/exhausted status never replaces Anchor or
      completed Views. Generate More, Stop and Regenerate remain progressive,
      contextual capabilities rather than permanent buttons.
- [ ] Layout/filter/collapse/resize state never enters PromptState, model
      requests, Mask/Evidence/Candidate identity or project data.

### Candidate Overlay

- [ ] Candidate Selected renders in the main 3D viewport without mutating
      Native Selection, native `SplatState`, project data or `EditHistory`.
- [ ] Candidate membership uses a dedicated transient presentation GPU state;
      existing splat sorting, transforms and overlay drawing infrastructure may
      be reused, but native selected/locked/deleted bits are not borrowed.
- [ ] Native Selection retains its native orange fill while Candidate Selected
      uses a distinguishable cyan outer edge/halo that does not cover the native
      fill.
- [ ] Uncertain is an optional low-opacity amber dotted diagnostic layer,
      disabled by default.
- [ ] The split Overlay control uses its eye button to show/hide Candidate
      Selected and its adjacent arrow to open Uncertain, legend and count.
- [ ] Candidate current publishes with Overlay shown. Successful native
      application hides it; failure preserves it; the eye control can re-show
      it.
- [ ] A stale Candidate stays inspectable with a desaturated, static sparse
      treatment. Updating with an old Candidate retains that stale treatment
      until atomic replacement.
- [ ] Overlay visibility is scoped to Candidate revision. Uncertain preference
      persists within the current Target and resets on Restart.

### Fixed AI Select Toolbar

- [ ] The AI Select Toolbar remains a fixed, non-draggable, single-row
      main-viewport subtoolbar.
- [ ] Once an inspectable Candidate exists, the Candidate context uses this
      order with no repeated leading `AI Select` label:
      `Overlay 👁 ▾ | Set | Add | Remove | Intersect | Undo and Fix* | More`.
- [ ] Ticket 16's Set/Add/Remove/Intersect execute immediately through the
      existing applicability gate, `SelectOp` and `EditHistory`; there is no
      separate Apply step or confirmation dialog.
- [ ] Normal local application adds no spinner or persistent applying state.
      Duplicate submission is guarded internally; success is shown by Native
      Selection, and exceptional failure reports `Selection unchanged` without
      changing Selection or history.
- [ ] Before the first inspectable Candidate, no empty Candidate Operation Group
      is shown. Once shown, the group keeps a stable position through current,
      stale, updating-with-old-result, update-failed, correcting and applied
      states.
- [ ] Current Candidate enables all four operations. Stale,
      updating-with-old-result, update-failed, correcting and globally blocked
      Candidate disables all four with one shared actionable reason.
- [ ] Blocked reasons are grouped by recovery action: wait for update, complete
      or exit Correction in the Dock, update the 3D Candidate in the Dock, or
      restart the Target. Technical blocker identity remains in tooltip/details.
- [ ] `More` contains low-frequency View actions, Restart and Exit. Candidate
      Overlay and the four native operations never enter overflow; `Undo and
  Fix` may enter `More` on narrow layouts.
- [ ] Narrow layouts remain one row and fall back to native operation icons with
      accessible tooltips before allowing overflow or wrapping.

### Status Bar and shared presentation

- [ ] Existing `SPLATS`, `SELECTED`, `LOCKED` and `DELETED` retain their native
      meanings. AI Candidate count never replaces Native `SELECTED`.
- [ ] Candidate work adds one contextual Status Bar item such as
      `AI CANDIDATE 222 · CURRENT`; first update may show
      `AI CANDIDATE — · UPDATING`.
- [ ] The item reports Candidate Selected count plus current, stale, updating,
      update-failed, correcting or durable application outcome. Uncertain count
      remains in the Overlay menu.
- [ ] Restart clears and hides the item until another Candidate request starts.
- [ ] Candidate status is read-only and is not an alternate Dock navigation
      control. The existing Status Bar AI Select button remains the Dock toggle.
- [ ] Dock, Toolbar and Status Bar consume one presentation mapper composed from
      Candidate Publication, Correction and Application state; none owns a
      duplicate lifecycle state.
- [ ] Dock owns Candidate-production and Correction actions. Toolbar owns
      Candidate Overlay and Native Candidate Operations. Status Bar owns the
      compact Candidate count/lifecycle projection.

### Correction and surface cutover

- [ ] `Back to Candidate` exits Correction without publishing the retained
      editing draft. If Stable inputs did not change, the current Candidate
      becomes applicable again; otherwise it remains stale until explicit
      `Update 3D Candidate` succeeds.
- [ ] Correction keeps the Candidate Overlay inspectable as reference and
      disables the four native operations with the shared Dock-editing reason.
- [ ] Set/Add/Remove/Intersect and the old `Show AI Result` are removed from the
      Dock in the same closure that makes their Toolbar/Overlay replacements
      usable.
- [ ] Dock may read-only echo durable Application outcome, but it does not host
      Native Candidate Operations or transient applying feedback.
- [ ] Ticket 16A does not render a placeholder `Undo and Fix`. Ticket 17 adds
      that control only when its associated native-history behavior exists.

### Accessibility

- [ ] Toolbar controls support Tab, Enter and Space. Overlay toggle exposes
      `aria-pressed`; menus close on Escape/outside click and restore focus.
- [ ] Disabled reasons are available to keyboard and assistive-technology users,
      not only through pointer hover or color.

## Failure / recovery criteria

- [ ] Overlay allocation/render failure preserves Candidate and Native Selection,
      disables misleading application affordances, and leaves the Dock recovery
      path available.
- [ ] Failed Candidate update preserves the prior stale Overlay atomically and
      never presents a partial replacement as current.
- [ ] Application failure preserves Native Selection/EditHistory and restores
      the operation buttons immediately.
- [ ] Tool exit, Target disposal and Restart release transient Candidate Overlay
      state; late publications cannot reattach to a new target context.

## Validation

- [ ] `rtk npm test`
- [ ] `rtk npm run lint`
- [ ] `rtk npm run lint:locales`
- [ ] `rtk npm run build`
- [ ] Presentation mapper and lifecycle matrix tests
- [ ] Overlay toggle never mutates Native Selection/EditHistory
- [ ] Candidate Selected/Uncertain/stale GPU membership and disposal tests
- [ ] Toolbar, Status Bar and Dock ownership/enablement tests
- [ ] Set/Add/Remove/Intersect regression tests through the real Ticket 16 adapter
- [ ] Browser viewport walkthrough proves Candidate, Uncertain, stale and Native
      Selection remain distinguishable when shown together
- [ ] Dock pure-layout tests cover column mode, ideal image width and height
      clamping at the accepted size matrix
- [ ] View A draft → View B → View A preserves Prompt, Proposal, Editing
      Mask and history; filtering keeps the current View fixed and visible
- [ ] Browser screenshots or walkthrough evidence cover the accepted Dock size
      and lifecycle matrices
- [ ] Browser validation may use a deterministic development Candidate fixture;
      it does not require production same-decision GPU Evidence

## Non-goals

- No reimplementation of Ticket 16 set algebra or Native EditHistory adapter
- No `Undo and Fix`, Native Undo/Redo/Diverged tracking, Restart completion or
  multi-target lifecycle; Ticket 17 owns these
- No Candidate 3D paint, merge or Gaussian Evidence inspector
- No project persistence for Candidate Overlay visibility
- No production Direct Evidence or release-calibration claim
