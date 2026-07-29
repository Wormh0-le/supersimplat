# 07B — Floating Prompt/Edit Palette UX Hardening

Status: proposed — ready-for-agent after 07A algorithm closure

Blocked by: 07A

Blocks: 08

## Final Spec mapping

- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- DG-22 — Draggable, Collapsible Prompt/Edit Palette with Temporary Hide
- Ticket 07A Phase 4 fitted-image layout foundation

## Purpose

Ticket 07A Phase 4 correctly moved Prompt/Edit controls into the authoritative fitted image surface and aligned RGB, Mask, Prompt overlays, and pointer mapping. A toolbar fixed at the fitted image bottom-center still creates a permanent non-editable blind region.

Ticket 07B replaces that fixed placement with a draggable, collapsible floating palette with a guaranteed Space temporary-hide escape hatch while preserving the fitted-image ownership rule.

The closure-critical interaction is:

```text
drag + edge snap
collapse / expand
Space temporary hide
no stale hit region
```

A non-relocating visual occlusion assist such as temporary opacity reduction is optional. Automatic palette relocation is not required for Ticket 07B closure.

This ticket is interaction hardening. It does not modify PromptState, adapter inference, proposal ranking, Stable Mask publication, or Evidence semantics.

## Inputs / preconditions

- Ticket 07A fitted-image surface and exact pointer mapping
- Existing compact Prompt/Edit toolbar controls
- Existing Prompt and Mask histories
- Existing Dock resize and `ResizeObserver` flow
- Existing active-tool state and localized tooltips
- Current Target Context lifecycle and Restart Target

## Outputs / handoff artifacts

- Target Context-scoped `FloatingPaletteState`
- Drag handle and pointer-capture interaction
- fitted-rect clamp and edge snapping
- expanded/collapsed presentation
- Space temporary hide
- optional non-relocating occlusion-assist hook
- shortcut mapping and conflict audit
- browser interaction and accessibility fixtures

# 1. Floating palette state

Introduce an editor-local state bound to the current Target Context.

Suggested shape:

```ts
interface FloatingPaletteState {
    readonly targetContextId: string;
    readonly mode: 'expanded' | 'collapsed';
    readonly edge: 'free' | 'top' | 'right' | 'bottom' | 'left';
    readonly xRatio: number;
    readonly yRatio: number;
}
```

Equivalent state is allowed when it provides:

- deterministic reflow after fitted-rect resize;
- complete clamping inside the fitted rect;
- context-local persistence;
- explicit default restoration.

The state MUST NOT enter PromptState, Mask history, Candidate provenance, or Companion requests.

# 2. Dragging and snapping

Add a dedicated drag handle at the leading edge of the expanded palette.

Required behavior:

```text
pointerdown on handle
→ palette pointer capture
→ suppress image authoring for this gesture

pointermove
→ move palette
→ continuously clamp full palette bounds to fitted image rect

pointerup
→ snap to nearest edge when inside snap threshold
→ otherwise retain free position
```

Constraints:

- tool buttons never initiate palette drag;
- palette drag never authors a Prompt or Mask stroke;
- image authoring outside the palette remains active;
- Dock/image resize reflows and clamps the palette without changing the active tool;
- dragging works at different device-pixel ratios and browser zoom levels.

Double-clicking the handle or invoking the reset shortcut restores the default placement.

# 3. Expanded and collapsed forms

Expanded form contains the current primary tools and contextual secondary actions.

Recommended information shape:

```text
[drag] [Point+] [Point−] [Paint] [Erase] [More] [Undo] [Redo] [Clear] [Collapse]
```

Exact visible tools remain capability- and active-mode-dependent.

Collapsed form is a compact capsule:

```text
[current tool icon / polarity] [Expand]
```

Requirements:

- minimum pointer target approximately `32 × 32 px`;
- current tool remains recognizable without relying on color alone;
- polarity remains recognizable for positive/negative tools;
- active tool does not change on collapse/expand;
- Prompt and Mask histories do not change;
- collapsed palette remains draggable or exposes an equivalent drag affordance;
- tooltip and accessible label identify current tool and expand action.

# 4. Space temporary hide

While image authoring focus is active:

```text
Space keydown
→ palette hidden
→ palette hit testing disabled

Space keyup
→ restore prior position and mode
```

Required safeguards:

- do not trigger while typing in text input, textarea, contenteditable, modal, or another control that owns Space;
- do not mutate stored palette state;
- repeated keydown is idempotent;
- lost focus / blur / context disposal cannot leave the palette permanently hidden;
- shortcuts and active tool remain unchanged.

# 5. Optional non-relocating occlusion assist

Ticket 07B does not require the palette to move automatically during image authoring. Automatic relocation can disrupt spatial memory and create unstable UI motion during a precision gesture.

A first implementation MAY provide a visual-only assist when an already captured Paint/Erase/Prompt-Brush/Box gesture approaches or passes beneath the palette's visible bounds:

```text
active captured image gesture near palette
→ temporarily reduce palette opacity
→ restore opacity when gesture ends
```

This assist is optional and is not a closure gate.

When implemented, it MUST:

- leave the palette position unchanged;
- leave image coordinates, PromptState, Mask pixels, and histories unchanged;
- avoid opacity-zero pointer interception outside the already captured image gesture;
- restore the exact prior opacity on pointerup, pointercancel, blur, and context disposal;
- respect reduced-motion and contrast/accessibility requirements;
- keep Space temporary hide as the guaranteed user-controlled override.

Automatic relocation to another edge is explicitly deferred. It requires a separate follow-up decision and browser evidence that it does not create oscillation, surprise, or loss of spatial memory.

# 6. No stale blind region

The palette itself intercepts pointer input while visible. Every previously covered pixel must become immediately editable after move, collapse, hide, or disposal.

Prohibited structures:

- a full-width transparent toolbar wrapper over the image;
- an invisible expanded hit box while collapsed;
- stale absolute-position overlays at the prior location;
- pointer-event interception by opacity-zero elements;
- an image-wide drag layer above Prompt/Mask input.

Required regression:

```text
move palette away from target edge
→ pointerdown at the old palette location
→ Prompt/Edit action starts immediately
```

# 7. Target Context lifecycle

Palette location and mode persist across:

- Prompt revisions;
- Retry;
- proposal state changes;
- active tool changes;
- Mask edits;
- Dock resize, after reflow/clamping.

They reset on:

- Restart Target;
- targetContextId rotation;
- target/scene replacement;
- AI Select disposal.

Do not persist one global palette location in browser storage across unrelated scenes.

# 8. Keyboard shortcuts

Preserve keyboard-first tool selection in expanded, collapsed, and temporarily hidden states.

Audit the intended mapping against existing SuperSplat shortcuts:

```text
1  Positive Point
2  Negative Point
B  Paint/Brush candidate mapping
E  Erase
```

The final mapping may change to avoid conflicts, but it MUST be:

- deterministic;
- localized in tooltips/help;
- focus-aware;
- disabled in text entry and modal contexts;
- covered by tests.

Add a shortcut to reset palette position. Do not overload Restart Target.

# 9. Accessibility and localization

- drag handle has an accessible label;
- collapse/expand state is exposed with `aria-expanded` or equivalent;
- current tool and polarity are announced;
- keyboard users can move focus through controls without triggering image authoring;
- Space temporary hide does not trap focus;
- all user-visible labels and tooltips use locale keys;
- reduced-motion preferences suppress nonessential movement animation.

# Acceptance criteria

## Placement

- [ ] Expanded and collapsed palette always remain inside the fitted image rect.
- [ ] Dragging uses a dedicated handle and cannot author Prompt/Mask input.
- [ ] Edge snapping is deterministic.
- [ ] Dock/image resize clamps and reflows the palette correctly.
- [ ] Double-click/reset shortcut restores default placement.

## Collapse and visibility

- [ ] Collapse retains current tool, polarity, position, and histories.
- [ ] Collapsed state exposes a compact accessible current-tool capsule.
- [ ] Space hides the palette only while held and restores it on release.
- [ ] Blur/context disposal cannot leave hidden state stuck.
- [ ] Expanded, collapsed, and hidden states preserve shortcut tool selection.

## Editability

- [ ] Moving the palette immediately restores Prompt/Edit at its previous location.
- [ ] Collapsing removes the expanded hit region.
- [ ] Hiding removes all palette hit testing.
- [ ] Targets touching every image edge and corner can be fully edited.
- [ ] No transparent wrapper creates a permanent blind area.

## Optional occlusion assist

- [ ] Ticket 07B can close without automatic fade or relocation when drag, collapse, Space hide, and no-stale-hit-region requirements pass.
- [ ] When opacity assist is implemented, it does not alter position, image coordinates, PromptState, Mask output, or histories.
- [ ] Optional opacity state restores on pointerup, pointercancel, blur, and disposal.
- [ ] Automatic relocation is not required and is not implemented as an undeclared closure dependency.

## Lifecycle

- [ ] Position/mode survive Prompt, proposal, tool, and Mask changes in one Target Context.
- [ ] Restart Target and targetContextId rotation restore defaults.
- [ ] No cross-scene browser-storage persistence is introduced.
- [ ] Generated View automatic publication behavior remains unchanged.

## Accessibility

- [ ] Drag, collapse, expand, reset, current tool, and polarity are accessible.
- [ ] Shortcut conflicts are audited and documented.
- [ ] Text-entry/modal focus prevents palette shortcuts.
- [ ] Locale and reduced-motion checks pass.

# Browser validation matrix

Validate at minimum:

- target touching bottom edge;
- target touching each corner;
- narrow fitted image;
- wide fitted image;
- minimum and maximum Dock height;
- browser resize while palette is snapped/free/collapsed;
- device pixel ratio 1 and 2;
- Paint/Erase stroke passing through previous palette position;
- drag, collapse, and Space hide while editing bottom-edge content;
- optional opacity assist lifecycle, only when implemented;
- Restart Target state reset;
- localized labels with wider text.

# Validation

- `npm test`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- real browser pointer-capture walkthrough
- keyboard-only walkthrough
- DPR/resize fitted-rect walkthrough
- edge/corner target regression screenshots
- PromptState/Mask artifact before-and-after equality checks for palette-only operations

# Non-goals

- No proposal-ranking changes.
- No Box/Mask adapter enablement; Ticket 04B owns it.
- No Text Prompt enablement.
- No new Stable Mask or Evidence lifecycle.
- No required automatic palette relocation during active gestures.
- No global toolbar framework rewrite outside AI Select.
- No persistence across unrelated scenes or browser sessions.
- No production animation/artwork requirement beyond clear, accessible interaction.
