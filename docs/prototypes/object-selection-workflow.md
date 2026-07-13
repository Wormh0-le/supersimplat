# Object Selection Workflow Prototype

## Decision answered

This low-fidelity prototype defines how a beginner creates, corrects, reviews, confirms, or cancels a Candidate Object Selection without seeing Generated Views or algorithm internals. It describes observable editor behavior, not production implementation.

## Entry and session boundary

Object Selection is a dedicated bottom-toolbar tool. Activating it suspends the active ordinary selection tool and opens a compact session panel. The Gaussian Selection that existed on entry is preserved but its highlight is temporarily hidden.

```text
┌ Object Selection ──────────────────────┐
│ [New] [Add] [Remove] [Refine]          │
│                                        │
│ Status: Waiting for a prompt           │
│                                        │
│ ■ Selected                       —     │
│ ░ Uncertain                      —     │
│                                        │
│ [Cancel]                    [Confirm]  │
└────────────────────────────────────────┘
```

Only `New` is available before the first Candidate Object Selection exists. `Confirm` is unavailable until a preview succeeds.

## Prompt and update cycle

Every mode uses an explicit update rather than inference on click:

```text
┌ Object Selection ──────────────────────┐
│ [New] [Add] [Remove] [Refine]          │
│                                        │
│ Mode: Refine                           │
│ Prompt: [＋ Include] [－ Exclude]       │
│ Pending prompts: 2                     │
│ [Undo Last] [Clear Prompts]            │
│                                        │
│ Correction rounds: 2 / 5               │
│                       [Update Preview] │
│ [Cancel]                    [Confirm]  │
└────────────────────────────────────────┘
```

The first pending prompt freezes the visible camera. The camera unlocks after `Update Preview`, after all pending prompts are cleared, or after undo removes the last prompt. One submitted inference-and-preview refresh is one Correction Round; placing, moving, clearing, or undoing pending prompts is not.

The initial valid `New` prompt fixes the Target Splat for the session. A prompt that hits empty space or another loaded splat is rejected locally with `Prompt must hit the current Target Splat.` It never changes the target implicitly.

## Mode semantics

- `New` starts a new session candidate from prompts on one target. If a candidate or correction history already exists, it first asks the user to choose `Keep Current` or `Start New`.
- `Add` segments another prompted region or part and unions its result with the candidate.
- `Remove` segments an unwanted prompted region or part and subtracts its result from the candidate.
- `Refine` recomputes the current target evidence using explicit `Include` and `Exclude` prompts. Canvas markers display `＋` and `－`; mouse buttons and keyboard modifiers do not carry hidden polarity.

`Add` and `Remove` do not show the Refine polarity switch. They remain distinct from ordinary Gaussian selection modifiers.

## Preview

The visible editor camera never moves to a Generated View. The current view overlays:

- selected Gaussians with the editor's stable, solid selection highlight;
- uncertain Gaussians with an amber sparse animated or stippled pattern;
- rejected Gaussians with the scene's normal appearance.

The panel repeats the distinction in text and counts so it is not color-only:

```text
Preview
■ Selected     128,420
░ Uncertain      6,731
```

The Candidate Object Selection remains separate from the editor's Gaussian Selection until confirm.

## Updating and recovery

During inference, the previous preview remains visible with `Updating preview…`. Camera inspection stays enabled; prompts, mode switching, and `Confirm` are disabled. `Cancel Update` aborts only the pending refresh and returns to the prior candidate.

A successful response atomically replaces the preview. A failed or disconnected request preserves the prior candidate, prompts, camera, and Correction Round count:

```text
Preview update failed: Selection Service unavailable.
[Retry]  [Edit Prompts]  [Cancel Session]
```

`Retry` repeats the same request. `Edit Prompts` returns to the unsubmitted prompt state. A failed initial `New` keeps its prompts even though no candidate exists yet.

## Five-round boundary

The panel always shows `Correction rounds: n / 5` and warns before the fifth refresh. After five successful Correction Rounds, it disables further preview updates:

```text
Correction rounds: 5 / 5
No more preview updates are available for this session.
[Start New]  [Cancel]  [Confirm Current]
```

Camera inspection remains available. `Start New` uses the same discard confirmation as any replacement of an active candidate.

## Confirm

With no uncertain Gaussians, `Confirm` performs a Selection Commit directly. With uncertainty, it requires explicit acknowledgement:

```text
6,731 uncertain Gaussians will NOT be selected.
The committed selection may be incomplete.

[Continue Reviewing]  [Confirm Selected Only]
```

Selection Commit atomically replaces the entry-time Gaussian Selection with only the candidate's selected Gaussians as one history operation. Uncertain Gaussians are never committed.

After confirm, the session panel closes, the prior ordinary editor tool is restored, and the committed Gaussian Selection remains highlighted. Existing delete, duplicate, separate, undo, and redo behavior owns all subsequent actions.

## Cancel

Cancel is immediate only when no candidate, correction history, or pending prompts exist. Otherwise it asks `Discard Object Selection Session?` Running inference is stopped before that confirmation completes.

Confirmed cancellation discards the candidate and restores the entry-time Gaussian Selection and prior editor tool unchanged. `Escape` only undoes the last pending prompt; it never silently discards a session.

## State flow

```text
ordinary editor
      │ enter Object Selection
      ▼
waiting for New ── Cancel ───────────────► restore ordinary editor
      │ place prompt + Update Preview
      ▼
updating ── failure/cancel update ───────► prior prompt/candidate state
      │ success
      ▼
candidate preview ◄──── Add/Remove/Refine update
      │    │
      │    ├── New ── discard confirmation ──► waiting for New
      │    └── Cancel ─ discard confirmation ─► restore entry selection
      │
      └── Confirm ─ uncertainty acknowledgement ─► Selection Commit
                                                       │
                                                       ▼
                                                  ordinary editor
```

## Prototype acceptance scenarios

The workflow is internally consistent if all of these are true:

1. An accidental prompt can be removed without consuming a Correction Round.
2. Moving the camera cannot silently change the meaning of pending screen-space prompts.
3. A slow or failed service request cannot erase the last usable candidate.
4. `New`, `Cancel`, and a failed request cannot modify the entry-time Gaussian Selection.
5. `Confirm` produces one ordinary Gaussian Selection and never includes uncertain Gaussians.
6. A beginner can distinguish Add, Remove, and positive/negative Refine without keyboard modifiers.
7. No path can submit more than five Correction Rounds in one Object Selection Session.
8. No prompt can add Gaussian indices from a second loaded splat.
