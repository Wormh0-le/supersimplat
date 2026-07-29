# DG-22 — Draggable, Collapsible Prompt/Edit Palette with Temporary Hide

- **Status:** CLOSED
- **Date:** 2026-07-29
- **Applies to:** `ai-select-v1`
- **Normative context:** Final Spec v1.1 + Amendment 002
- **Implementation owner:** Ticket 07B

## Decision question

How should the Prompt/Edit toolbar remain inside the authoritative fitted image surface without creating a permanent, non-editable blind spot over targets that touch the image edge?

## Context

Ticket 07A Phase 4 correctly moved Prompt/Edit controls from the dense right-side panel into the fitted image surface. A toolbar fixed at the image bottom-center still intercepts pointer input over a permanent rectangular region. This is especially harmful when the target extends to the bottom edge or a corner.

The fitted image principle remains correct:

```text
RGB image
Mask overlay
Prompt overlay
pointer mapping
Prompt/Edit controls
```

must all use the same authoritative image rectangle. Moving the toolbar outside that rectangle would separate the controls from the interaction context and reintroduce layout pressure in the information panel.

The remaining problem is occlusion, not coordinate authority.

## Decision

Adopt a movable floating Prompt/Edit palette that:

- remains fully constrained to the current fitted image rectangle;
- can be dragged by an explicit handle;
- snaps to image edges;
- can collapse to a compact current-tool capsule;
- can be temporarily hidden while Space is held;
- may provide a non-relocating visual occlusion assist, but does not require automatic movement;
- remembers its position and collapsed state only within the current Target Context;
- restores its default state when Target Context rotates, the scene changes, or Restart Target runs.

The minimum closure-critical interaction model is:

```text
Expanded
[drag] [Point+] [Point−] [Paint] [Erase] [More] [Undo] [Redo] [Clear] [Collapse]

Collapsed
[current tool icon / polarity] [Expand]

Temporary access
hold Space → palette hidden and non-hit-testable
```

The exact artwork is not normative. Drag, collapse, temporary hide, and hit-testing semantics are normative.

## Decision 1 — The palette stays inside the fitted image rect

The entire visible palette bounding box MUST remain inside the fitted image rectangle after:

- drag;
- Dock resize;
- image aspect-ratio change;
- browser resize;
- expand/collapse;
- locale/text-width change.

The palette position is represented relative to the fitted rectangle, not the Dock or browser viewport.

A recommended state model is:

```ts
interface FloatingPaletteState {
    mode: 'expanded' | 'collapsed';
    edge: 'free' | 'top' | 'right' | 'bottom' | 'left';
    xRatio: number;
    yRatio: number;
    hiddenWhileSpaceHeld: boolean;
}
```

Equivalent representations are allowed if they preserve deterministic reflow.

## Decision 2 — Drag and edge snapping

The palette has a dedicated drag handle. Tool buttons must not accidentally initiate palette movement.

During drag:

- pointer capture belongs to the palette;
- image Prompt/Edit input is suppressed only for the palette interaction;
- the palette is clamped continuously to the fitted rectangle;
- releasing within a versioned snap threshold anchors it to the nearest image edge;
- free placement remains allowed when outside the snap threshold.

Double-clicking the handle or invoking the reset shortcut restores the default placement.

The default placement may remain bottom-center, but it is never permanent.

## Decision 3 — Collapse is a first-class state

Collapse reduces the palette to a compact capsule with a minimum target near `32 × 32 px`.

The collapsed state MUST expose:

- current tool identity;
- current polarity where relevant;
- an expand action;
- tooltip/accessibility label.

A text label may be shown when space permits, but the capsule must remain compact on small fitted images.

Click expands. Collapse/expand must not change the active Prompt/Edit tool or either history.

## Decision 4 — Space provides a guaranteed temporary escape hatch

While image authoring focus is active:

```text
Space keydown
→ palette becomes non-visible and non-hit-testable

Space keyup
→ palette returns to its prior position and collapsed state
```

This behavior is temporary and does not mutate stored palette state.

Space handling must not steal input from a focused text field, modal, or native editor operation that already owns Space.

## Decision 5 — Automatic relocation is not a closure requirement

Automatic movement during a precision gesture can disrupt spatial memory and produce unstable UI motion. Ticket 07B therefore does not require the palette to relocate itself while the user draws or drags a Box.

A first implementation MAY provide a non-relocating visual assist:

```text
active captured image gesture near palette
→ temporarily reduce palette opacity
→ restore opacity when gesture ends
```

When implemented, the assist must be deterministic and must never alter:

- palette position;
- image coordinates;
- PromptState;
- Mask pixels;
- Prompt or Mask history.

Drag, collapse, and Space temporary hide remain the guaranteed controls. Automatic relocation to the farthest edge is deferred to a separate follow-up decision backed by browser evidence that it does not cause surprise, oscillation, or loss of spatial memory.

## Decision 6 — Hit-testing has no stale blind region

The palette itself intercepts pointer input while visible.

Every area it previously covered MUST become immediately available to Prompt/Edit interaction after the palette:

- moves;
- collapses;
- hides;
- is removed during context disposal.

No invisible wrapper, full-width toolbar container, stale bounding box, opacity-zero pointer target, or overlay may continue intercepting image input.

## Decision 7 — State is Target Context scoped

Palette placement and collapse state persist only for the active `targetContextId`.

They survive:

- Prompt revisions;
- proposal Retry;
- tool changes;
- Mask edits;
- Dock resize, after clamping/reflow.

They reset on:

- Restart Target;
- targetContextId rotation;
- scene/target replacement;
- AI Select disposal.

Persistent browser storage across unrelated scenes is out of scope.

## Decision 8 — Keyboard tool selection remains available

The palette is not the only way to select tools.

Ticket 07B must define and conflict-audit shortcuts, including the intended examples:

```text
1  Positive Point
2  Negative Point
B  Paint / Brush, according to the final conflict-audited mapping
E  Erase
```

The implementation may adjust specific keys to avoid existing SuperSplat conflicts, but the resulting mapping must be visible, localized, deterministic, and tested.

Shortcuts work in expanded, collapsed, and temporarily hidden states.

## Decision 9 — Domain and lifecycle semantics do not change

This decision affects presentation and pointer routing only.

It does not change:

- PromptState;
- adapter capabilities;
- proposal generation;
- ProposalDecision;
- Editing/Stable Mask separation;
- Confirm-only Stable publication;
- Evidence/Candidate invalidation;
- Generated View automatic publication;
- Ticket 07A ranking ownership.

## Rejected alternatives

### Keep the toolbar fixed at bottom-center

Rejected because it creates a permanent non-editable region over valid image content.

### Allow drag only

Rejected because drag alone does not sufficiently address small images or immediate edge/corner editing. Collapse and Space temporary hide are also required.

### Require automatic relocation during every nearby gesture

Rejected because self-moving controls can disrupt spatial memory and introduce unpredictable movement during precise authoring. It may be reconsidered only as a separately validated enhancement.

### Move the toolbar outside the fitted image

Rejected because it reintroduces information-panel crowding and weakens the contextual relationship between tools and image interaction.

### Make the palette click-through

Rejected because controls require reliable pointer interaction and ambiguous click-through behavior risks unintended Prompt/Mask edits.

### Persist one global position across scenes

Rejected because fitted image geometry and task context differ, producing stale or invalid placement.

## Consequences

### Positive

- no permanent image blind spot;
- full edge/corner editability;
- compact operation on small Dock sizes;
- deterministic temporary access through Space;
- reduced need to keep the palette expanded;
- fitted-image coordinate authority remains intact;
- no mandatory self-moving UI during precision gestures.

### Costs

- new Target Context-scoped UI state;
- drag/snap/reflow logic;
- shortcut conflict audit;
- additional pointer-capture and accessibility tests;
- optional opacity assist, when implemented, requires lifecycle and pointer-event validation.

## Required implementation sequence

```text
07A Phase 4 fitted-image layout foundation
    ↓
07B Floating Prompt/Edit Palette
    ↓
08 Adaptive Generated View Planner
```

Ticket 07B is the implementation owner. Ticket 07A remains the algorithmic Three-Stage Pipeline completion owner.
