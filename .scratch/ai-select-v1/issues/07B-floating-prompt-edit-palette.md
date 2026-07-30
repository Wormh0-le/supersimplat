# 07B — Floating Prompt/Edit Palette UX Hardening

Status: proposed — ready-for-agent after 07A algorithm closure

Blocked by: 07A

Blocks: 11, 21

Runs in parallel with: 08

## Final Spec mapping

- Final Spec v1.2 §7, §§20 and 28–29
- DG-22
- DG-26 Decision 7

## Purpose

Replace the fixed fitted-image toolbar with a draggable, collapsible floating Prompt/Edit palette and a guaranteed Space temporary-hide escape hatch.

This is interaction hardening. It does not modify PromptState, adapter inference, proposal ranking, Stable Mask publication, acquisition, Evidence, or Candidate semantics.

Ticket 07B does not block Ticket 08 geometry/planning. It remains mandatory before complete Generated/User-added correction UX and final release validation.

## Inputs / preconditions

- Ticket 07A fitted authoritative image surface;
- exact RGB/Mask/Prompt coordinate mapping;
- existing Prompt and Mask histories;
- Dock resize / `ResizeObserver` flow;
- current active tool, shortcuts, tooltips and localization;
- Current Target Context lifecycle.

## Outputs / handoff artifacts

- Target Context-scoped `FloatingPaletteState`;
- drag handle and pointer-capture interaction;
- fitted-rect clamp and edge snapping;
- expanded/collapsed forms;
- Space temporary hide;
- optional non-relocating visual occlusion assist;
- shortcut conflict audit;
- browser interaction and accessibility fixtures.

# 1. State

Suggested contract:

```ts
interface FloatingPaletteState {
    readonly targetContextId: string;
    readonly mode: 'expanded' | 'collapsed';
    readonly edge: 'free' | 'top' | 'right' | 'bottom' | 'left';
    readonly xRatio: number;
    readonly yRatio: number;
}
```

Equivalent state is allowed when it provides deterministic reflow, complete fitted-rect clamping, target-local persistence and explicit reset.

Palette state MUST NOT enter PromptState, Mask history, acquisition requests, Evidence, Candidate, or Companion state.

# 2. Dragging and snapping

Required behavior:

```text
pointerdown on dedicated handle
→ palette pointer capture
→ suppress image authoring for that gesture

pointermove
→ move and continuously clamp full palette bounds

pointerup
→ snap to nearest edge inside threshold
→ otherwise retain free position
```

Tool buttons never initiate drag. Palette drag never authors Prompt/Mask pixels. Image authoring outside current visible palette bounds remains active.

Dock/image resize reflows and clamps without changing the active tool.

# 3. Expanded and collapsed forms

Expanded form contains current primary tools and contextual secondary actions.

Collapsed form is a compact draggable capsule showing current tool/polarity and Expand.

Requirements:

- minimum practical pointer target around `32 × 32 px`;
- current tool and polarity identifiable without color alone;
- collapse/expand changes no Prompt/Mask history or active tool;
- accessible label and expanded state;
- tooltips/localization remain complete.

# 4. Space temporary hide

While image authoring focus is active:

```text
Space keydown
→ palette hidden
→ palette hit testing disabled

Space keyup
→ exact prior position/mode restored
```

Safeguards:

- no trigger in text input, textarea, contenteditable, modal or another Space-owning control;
- repeated keydown is idempotent;
- blur/lost focus/context disposal cannot leave palette hidden;
- stored palette state is unchanged;
- active tool and histories are unchanged.

# 5. No stale blind region

Every previously covered pixel becomes immediately editable after move, collapse, hide or disposal.

Prohibited:

- full-width transparent wrapper over image;
- invisible expanded hit box while collapsed;
- stale overlay at old position;
- opacity-zero pointer interception;
- image-wide drag layer above authoring input.

Required regression:

```text
move palette away
→ pointerdown at old palette location
→ Prompt/Edit action starts immediately
```

# 6. Optional occlusion assist

Automatic palette relocation is not required.

An optional assist may temporarily reduce visible opacity during an already captured image gesture near the palette, but it must not change position, coordinates, Prompt/Mask pixels, histories, or hit testing outside the captured gesture.

Space hide remains the guaranteed user-controlled override.

# 7. Lifecycle

Palette location/mode persist across Prompt revisions, model Retry, proposal changes, active tool changes, Mask edits and Dock resize.

They reset on Restart Target, targetContextId rotation, target/scene replacement, or AI Select disposal.

Do not persist one global palette location across unrelated targets/scenes.

# 8. Shortcuts and accessibility

- preserve keyboard-first tool selection in expanded/collapsed/hidden states;
- audit conflicts with existing SuperSplat shortcuts;
- disable image-tool shortcuts in text/modal contexts;
- add explicit reset-position shortcut;
- drag handle has accessible label;
- current tool/polarity and collapse state are announced;
- Space hide does not trap focus;
- reduced-motion preferences suppress nonessential animation;
- all user-visible strings use locale keys.

# Acceptance criteria

- [ ] Palette remains completely inside fitted image after drag, zoom and resize.
- [ ] Drag starts only from the handle/equivalent affordance.
- [ ] Palette drag never authors image content.
- [ ] Expanded/collapsed state preserves current tool and histories.
- [ ] Collapsed palette remains draggable.
- [ ] Space keydown hides presentation and hit testing; keyup/blur/disposal restores safely.
- [ ] Old palette position becomes immediately editable.
- [ ] No transparent wrapper or stale hit region intercepts input.
- [ ] Target-local persistence and reset behavior are deterministic.
- [ ] Palette state does not enter algorithm or artifact identity.
- [ ] Anchor, Generated View and User-added View correction surfaces reuse the same behavior.
- [ ] Ticket 08 can proceed independently after 07A.
- [ ] Ticket 11 and Ticket 21 do not close until this interaction is validated.

# Failure / recovery criteria

- Pointer capture loss restores a consistent clamped position.
- `pointercancel`, blur and disposal clear transient drag/hide/opacity state.
- Invalid stored ratios fall back to default placement.
- Resize that cannot preserve exact position clamps without changing tool state.
- Shortcut conflict is resolved explicitly and localized.
- No failure mutates Prompt, Mask, acquisition, Evidence, Candidate or Native Selection state.

# Validation

- `npm test`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- browser drag/snap/collapse tests
- Space keydown/keyup/repeat/blur tests
- old-location immediate authoring regression
- Dock resize / DPR / browser zoom matrix
- Anchor/Generated/User-added correction walkthrough
- accessibility keyboard/focus/label audit
- reduced-motion and localization checks

# Non-goals

- No PromptState changes.
- No adapter/model changes.
- No proposal ranking or ambiguity changes.
- No Stable Mask or acquisition lifecycle changes.
- No Evidence/Candidate changes.
- No automatic palette relocation requirement.
- No blocker relationship from 07B to Ticket 08.
