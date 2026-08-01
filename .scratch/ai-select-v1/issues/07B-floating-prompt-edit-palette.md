# 07B — Floating Prompt/Edit Palette UX Hardening

Status: implemented — floating palette + target-local state + Brush Size popover

Blocked by: 07A

Blocks: 11, 21

Runs in parallel with: 08

## Implementation record

- Pure geometry/lifecycle module `src/ai-select/floating-palette.ts` (DOM-free,
  unit-tested): `FloatingPaletteState`
  (`targetContextId` / `mode` / `edge` / `xRatio` / `yRatio` only — never RGB,
  Mask, Policy or any artifact identity), single `resolvePaletteRect`
  resolver used after drag/resize/collapse/locale change, continuous drag
  clamp via `dragPaletteTo`, release snap via `snapPalette` (versioned
  `PALETTE_SNAP_THRESHOLD_PX = 24`, deterministic tie priority
  top→right→bottom→left), `setPaletteMode` preserving position/tool/history,
  `retargetFloatingPaletteState` for target-local reset, shared
  `clampBrushSize` (1–64) and `placeBrushSizePopover` (anchored, flips
  above/below, fully clamped).
- Tool inventory constants `PALETTE_PROMPT_TOOLS` / `PALETTE_EDIT_TOOLS` are
  the single source for the v1 set (Positive/Negative Point, Positive
  Instance Box, Paint, Erase). Negative Box, Prompt Brush, Mask Constraints
  and Text Prompt are absent — asserted by test, not rendered as disabled
  placeholders.
- Reusable component `src/ui/ai-select-floating-palette.ts`: dedicated drag
  handle (pointer capture on the handle suppresses image authoring for the
  gesture; double-click resets placement), collapse to a ≥32px capsule
  showing the active tool icon/polarity with localized expand label, icon-first
  buttons with localized tooltip + aria-label + shortcut hint, Prompt/Edit
  groups separated visually, polarity identifiable by +/− glyphs (color is
  additive only), distinct selected/hover/focus-visible/unavailable styling,
  and the non-relocating DG-22 Decision 5 opacity assist while a captured
  image gesture passes within 24px.
- Space temporary hide is transient (`setTransientHidden`): presentation and
  hit testing switch off via one class, stored state is never mutated, and
  keyup/window-blur restore the exact prior state. Repeat keydowns do not
  toggle. The palette is a single absolutely positioned element — moving,
  collapsing or hiding leaves no wrapper or stale blind hit region, so the
  old location is immediately authorable.
- Brush Size popover: shared by Paint/Erase only, anchored to the active edit
  tool button, clamped and flipping via the pure placer; native range input
  (keyboard-adjustable) with aria-label and an `aria-live` value; closes on
  outside pointerdown, Escape (focus returns to the tool), collapse,
  temporary hide, context disposal and non-edit tool change; re-clicking the
  active edit tool toggles it. Changing the size only re-renders the pending
  stroke preview — it never authors pixels.
- Keyboard tool selection `1/2/3/B/E` is scoped to Anchor Dock focus
  (conflict-audited against the global ShortcutManager, which only fires for
  `document.body` targets: 1/2/3 = move/rotate/scale, B = brush selection,
  Space = timeline play remain untouched); text-entry controls, native button
  Space activation and modals keep their input. Disabled tools ignore
  shortcuts, matching the buttons.
- Anchor Dock integration: the fixed bottom toolbar is replaced by the
  palette; palette state resets on `targetContextId` rotation/disposal in the
  existing controller subscription; Dock/image resize reclamps through the
  existing ResizeObserver path without changing the tool. Prompt and Mask
  histories stay separate (prompt Undo/Redo/Clear live in the palette, mask
  Undo/Redo in the side panel; Ctrl/Cmd+Z routing unchanged). Generated and
  User-added correction surfaces (Ticket 11) reuse `AISelectFloatingPalette`
  directly.
- Localization: `ai-select.palette.label/.drag-handle/.collapse/.expand`
  and `ai-select.prompt.capabilities-unavailable` added to all 9 locales;
  `ai-select.edit.brush-size` reused.

## Review outcomes (07B self-review, two-axis)

- Brush Size popover side selection documented as fit-first (above when it
  fits, else below when it fits, else the side with more room); analysis
  showed the overlap case is only reachable on degenerate tiny surfaces
  where overlap is unavoidable, and the more-room side minimizes it.
- `isPaletteEditTool` guard and the shared `PALETTE_TOOLS` inventory removed
  duplicated casts/orderings between the pure module and the component.
- Popover auto-opens on fresh Paint/Erase activation: this preserves the
  pre-07B behavior (Brush control visible whenever an edit tool is active)
  while adding the required close triggers; re-click toggles.
- Reset placement is double-click on the handle (DG-22 offers double-click
  or a reset shortcut as alternatives; the double-click path is delivered).
- Space-hide is scoped to Mask Editor (Dock) focus — the same seam as the
  existing mask-local Ctrl/Cmd+Z routing; text-entry, native button
  activation and modals keep Space.
- DOM-level interaction validation follows the repository pattern (no DOM
  test harness exists; UI modules are excluded from tsconfig.test): pure
  geometry/state is unit-tested in
  `test/ai-select-floating-palette.test.js` (25 tests), and WF-08 browser
  walkthrough steps are listed with the ticket report.

## Follow-ups (not in scope)

- Ticket 11 instantiates the component for User-added View correction.
- Automatic relocation to the farthest edge remains deferred per DG-22
  Decision 5.

## Final Spec mapping

- Final Spec v1.3 §8, §§17–19, 26
- ADR 0016

## Purpose

Provide one draggable, collapsible, accessible palette over the fitted authoritative image without changing Prompt, Mask, Evidence or Candidate semantics.

## Current v1 tools

Prompt group:

```text
Positive Point
Negative Point
Positive Instance Box
```

Edit group:

```text
Paint
Erase
```

Negative Box, Prompt Brush, Mask Constraints and Text Prompt are absent from the current palette. They are not retained as permanently disabled discovery placeholders.

Paint/Erase share a contextual Brush Size control. There is no Prompt Brush size/state.

## Palette state

```ts
interface FloatingPaletteState {
    readonly targetContextId: string;
    readonly mode: 'expanded' | 'collapsed';
    readonly edge: 'free' | 'top' | 'right' | 'bottom' | 'left';
    readonly xRatio: number;
    readonly yRatio: number;
}
```

Palette position/mode never enters PromptState, Mask history, model request, Evidence or Candidate identity.

## Required interaction

- drag begins only from a dedicated handle;
- pointer capture suppresses image authoring for the drag gesture;
- full palette bounds remain clamped inside the fitted image;
- optional edge snap is deterministic;
- collapse/expand preserves active tool and histories;
- Space temporarily hides presentation and hit testing, then restores exact state;
- moving/collapsing/hiding leaves no stale blind hit region;
- Dock/image resize reclamps without changing tool;
- state is target-local and resets on target/context disposal.

## Tool presentation

- icon-first with localized tooltip and accessible name;
- Prompt and Edit groups are visually distinct;
- positive/negative Point polarity is identifiable without color alone;
- active, hover, focus and unavailable-service states are distinct;
- model service unavailability disables inference tools without reintroducing removed Prompt families;
- Paint/Erase remain locally usable where current product state permits.

## Brush Size popover

Only Paint and Erase use the popover.

- anchored to the active edit tool;
- fully clamped and flips to a safe side;
- keyboard adjustable and announced;
- closes on outside click, Escape, collapse, temporary hide, context disposal or tool change;
- changing size never authors pixels by itself.

## Acceptance criteria

- [x] Palette exposes exactly the current v1 Prompt/Edit tool set.
- [x] Negative Box and Prompt Brush are absent.
- [x] Prompt and Edit histories remain separate.
- [x] drag/snap/collapse/hide never authors pixels.
- [x] old palette location becomes immediately editable.
- [x] no transparent wrapper or stale hit box intercepts input.
- [x] Paint/Erase Brush Size behavior is accessible and clamped.
- [x] Point polarity is identifiable without color alone.
- [x] palette state never changes artifact identity.
- [x] Anchor, Generated and User-added correction surfaces reuse the behavior. (Anchor now; `AISelectFloatingPalette` is the shared component Ticket 11 instantiates for User-added/Generated correction surfaces.)
- [x] Ticket 08 remains parallel and unblocked after 07A.

## Validation

- drag/snap/collapse/resize tests;
- Space keydown/keyup/repeat/blur tests;
- old-location immediate authoring regression;
- tool inventory assertion proving removed Prompt tools are absent;
- Paint/Erase popover tests;
- accessibility/localization audit;
- repository test/lint/locales/build.

## Non-goals

- No model inference implementation.
- No candidate choice or Mask Review policy.
- No Prompt Brush or Negative Box compatibility UI.
- No Evidence or Candidate behavior.
