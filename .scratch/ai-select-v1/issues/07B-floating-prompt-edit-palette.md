# 07B — Floating Prompt/Edit Palette UX Hardening

Status: proposed — unblocked (07A implemented)

Blocked by: 07A

Blocks: 11, 21

Runs in parallel with: 08

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

- [ ] Palette exposes exactly the current v1 Prompt/Edit tool set.
- [ ] Negative Box and Prompt Brush are absent.
- [ ] Prompt and Edit histories remain separate.
- [ ] drag/snap/collapse/hide never authors pixels.
- [ ] old palette location becomes immediately editable.
- [ ] no transparent wrapper or stale hit box intercepts input.
- [ ] Paint/Erase Brush Size behavior is accessible and clamped.
- [ ] Point polarity is identifiable without color alone.
- [ ] palette state never changes artifact identity.
- [ ] Anchor, Generated and User-added correction surfaces reuse the behavior.
- [ ] Ticket 08 remains parallel and unblocked after 07A.

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
