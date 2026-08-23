# V2J — Progressive acquisition UI + Expert Recovery

Status: **reviewed parent envelope — Q11 accepted; awaiting decomposition; not agent-ready**

Blocked by: V2H, V2I  
Blocks: none

## Authority

Final Spec Amendments 001, 008, and 009; ADRs 0022, 0029, and 0030; existing AI Select Dock/toolbar/status patterns; and the accepted Q11 interface contract recorded here. Reusable surface rules are mirrored in [`.interface-design/system.md`](../../../../.interface-design/system.md), but this ticket remains authoritative for V2J lifecycle, availability, and acceptance behavior.

## Goal

Present automatic acquisition, Candidate publication/consent, and secondary Expert Recovery with progressive disclosure. Preserve a canvas-first selection workflow without exposing persistent planner management or internal algorithm dashboards.

Q11 treats Evidence/Workflow, Spatial Authoring, and Selection Application as responsibility layers inside one continuous editor workspace. It does not create three parallel products or duplicate commands across the Dock and main 3D viewport.

## Accepted Q11 design contract

Numbering preserves the reviewed draft: clause 8 is an existing-behavior regression guard; draft clauses 9, 11, and 12 are removed rather than renumbered into new requirements.

**1 — Responsibility layers are not new surfaces.** The design coordinates existing editor surfaces instead of adding a planner page, wizard, or second spatial toolbar.

**2 — Surface ownership is explicit.**

- AI View Dock + Session Strip own rendered Evidence, 2D Prompt/Mask authoring, workflow state, publication consent, and explanations.
- Main 3D viewport + its contextual toolbar own Anchor/View spatial authoring.
- The Candidate group in that same toolbar owns Overlay and Native `Set/Add/Remove/Intersect`.

**3 — Restore one compact Session Strip.** It is a single-line, cross-View workflow projection with at most one contextual action. It never duplicates Anchor/View manipulation controls.

**4 — Authoritative editing auto-pauses acquisition.** The initiating intent is queued, acquisition reaches a safe boundary, and the requested edit starts after pause acknowledgement without requiring a second click. Passive inspection never pauses. Completion or cancellation never resumes acquisition implicitly.

**5 — Spatial commands stay in the main 3D toolbar.** `Adjust Anchor`, `Use Current View`, `Add Observation…`, Move/Rotate mode, Render/Confirm, Return to Scene View, and Cancel remain viewport-owned.

**6 — Navigator ↔ camera-frustum linkage remains the signature cross-surface interaction.** Selection, hover, camera jump, and Dock View switching share one View identity and one presentation state.

**7 — Anchor/Observation adjustment adds a transparent Spatial Edit HUD.** The HUD keeps attention in the 3D viewport and presents immediate, non-interactive feedback; it does not become another command surface.

**8 — Existing behavior is a regression baseline, not new implementation scope.** The draft camera frustum already updates continuously while it is translated or rotated, and the Dock does not re-render for every manipulation frame. Preserve both behaviors.

**10 — Rendered Evidence changes only at stable boundaries.** Draft motion never replaces the Dock image. A successful staged Anchor render or completed Observation render may update the Dock atomically; authoritative Anchor/Candidate identity changes only through the corresponding commit gate.

## Surface ownership

| Surface | Owns | Must not duplicate |
| --- | --- | --- |
| Session Strip | Attempt/session phase, compact progress, pause/cancel/publication status, at most one lifecycle or consent action | Move/Rotate, Adjust Anchor, Use Current View, Add Observation, Candidate set operations |
| Navigator | View list, active/hover identity, status badge, keyboard equivalent for frustum selection | Spatial manipulation and Attempt controls |
| Work Area | Authoritative or explicitly staged RGB/Mask, 2D authoring, Re-Lift | Per-frame camera draft preview and Native set operations |
| Inspector | Explanation, blockers, collapsed diagnostics, secondary recovery guidance | Primary publication action and duplicate spatial commands |
| Main 3D viewport toolbar | Anchor/View authoring, Return/Cancel, Candidate Overlay and Native operations | Prompt/Mask editing, Re-Lift, Attempt dashboard |
| Spatial Edit HUD | Read-only feedback for the active spatial draft | Buttons, menus, rendered image preview, publication or lifecycle actions |
| Global AI Select menu | Target restart/disposal and tool exit | Current viewport manipulation |

### Progressive-disclosure hierarchy

1. **Primary:** the one action required by the current lifecycle state appears in the Session Strip or its already-owned surface.
2. **Secondary recovery:** appears only when no Attempt is actively running. Non-spatial recovery is disclosed in the Dock/Inspector; spatial recovery is explained there but executed from the main 3D toolbar.
3. **Advanced diagnostics:** remain collapsed in Inspector technical details. There is no default Utility/Coverage/Frontier dashboard.

## Acquisition and editing coordination

### Passive inspection does not pause

The following remain available without changing Attempt state:

- select or hover a Navigator View;
- select or hover an existing 3D camera frustum;
- jump the editor camera to an Observation;
- return to the scene camera;
- orbit, pan, or zoom for inspection;
- switch RGB/Mask or diagnostic overlays;
- inspect Candidate, assessment, provenance, or technical details.

### Authoritative authoring requests a safe pause

The following first request an operator-edit pause when acquisition is running:

- Positive/Negative Point, Paint, Erase, or Instance Box authoring;
- participation Include/Exclude changes;
- `Adjust Anchor`;
- `Use Current View`;
- `Add Observation…`;
- any other command that changes Stable Mask, Anchor identity, Observation set, or Evidence inputs.

The transition is:

```text
operator invokes authoring action
        ↓
pause-pending; mutation is still blocked
        ↓
orchestrator acknowledges a safe committed boundary
        ↓
the original action is replayed once into editing/spatial-authoring mode
```

- The user does not click twice.
- Repeated authoring while already paused does not request another pause.
- If pause fails, the Attempt remains authoritative, the queued mutation is discarded, and contextual failure is shown.
- Candidate Native operations remain blocked while the Attempt is running or pause-pending.
- Toolbar spatial entries may remain visible for location stability, but they cannot mutate camera/target state before pause acknowledgement.
- The Session Strip and Dock do not expose duplicate `Add Observation` or camera-management buttons while an Attempt runs.

### Explicit continuation only

- **Return to Scene View** changes only the inspection camera. It preserves the spatial draft and paused workflow state.
- **Cancel adjustment** discards the current spatial draft and restores the prior Anchor/Observation state. It does not resume acquisition.
- If no authoritative input changed and the journal boundary remains compatible, the explicit action is `Resume Acquisition`.
- After an authoritative edit advances inputs, the explicit action is `Continue Acquisition`; it creates a fresh bounded Attempt under the existing Series contract.
- The UI never implies that a changed-input Attempt can secretly resume from the old identity.

## Session Strip

The Session Strip is a compact context bar at the top of the AI View Dock. It replaces neither the Navigator nor the Work Area title, and it collapses when no active target/session state needs explanation.

Rules:

This is a deliberate v2 revision to the implemented v1.3 rule that omitted a Dock-wide status header. The Session Strip is not a selected-View title or permanent dashboard: it appears only when target/session state needs cross-View explanation and otherwise collapses.

- single line; stable height; no wrapping;
- status/phase on the left, optional one action on the right;
- tabular numerals for progress counts;
- phase text may elide before the action at narrow widths;
- no spatial authoring, Candidate set operation, target restart, or technical metrics;
- state changes announce through a polite live region without stealing focus;
- the action slot stays fixed so labels do not shift the Dock layout.

### Canonical state examples

| State | Strip copy | One action |
| --- | --- | --- |
| Running | `Building selection · 4 valid observations` | `Cancel Acquisition` |
| Pause pending | `Pausing acquisition before editing…` | `Cancel Acquisition` |
| Paused, no input change | `Paused for 3D adjustment` or `Paused for Mask editing` | `Resume Acquisition` |
| Stable input changed | `Evidence changed · a fresh Attempt is required` | `Continue Acquisition` |
| Adjusting Anchor | `Adjusting Anchor in 3D · Dock image is unchanged` | none |
| Rendering Anchor draft | `Rendering Anchor View · prior result preserved` | none |
| Adding Observation | `Adding Observation · prior result preserved` | none |
| Normal Ready-low-gain | `Ready · Candidate updated` | none |
| Eligible forced-terminal Ready | `Ready · explicit publication required` | `Use Ready Candidate` |
| Eligible Limited | `Limited · explicit consent required` | `Use Limited Candidate` |
| Not Ready/ineligible | `Not Ready · no Candidate can be published` | none |
| Cancelled | `Acquisition cancelled · prior Candidate preserved` | `Continue Acquisition` when allowed |
| Suspended, compatible | `Acquisition suspended` | `Resume Acquisition` |
| Candidate stale after Stable-input change | `Candidate is out of date · Re-Lift is available in the Work Area` | none |

A state with no strip action may expose secondary explanation/recovery in Inspector, but it must not fill the empty action slot with a low-priority command.

## Main 3D toolbar modes

The toolbar remains fixed, single-line, non-draggable, and contextual. Labels below describe command semantics; implementation may use the established icon + tooltip treatment.

### Stable / scene-inspection mode

```text
[Return to Scene View]*  [Adjust Anchor]  [Use Current View ▾]
                                             └─ Add Observation…
```

`Return to Scene View` appears only while inspecting an Observation camera. `Use Current View` is the fast path; `Add Observation…` creates an adjustable draft frustum.

### Candidate mode

```text
[Adjust Anchor]  [Use Current View ▾]  │  [Overlay ▾] [Set] [Add] [Remove] [Intersect] [Undo and Fix]
                        └─ Add Observation…
```

Spatial authoring and Candidate operations share the toolbar but remain visibly grouped. Entering an adjustment replaces the Candidate group rather than appending another row.

### Anchor adjustment mode

```text
[Return to Scene View] │ [Move ●] [Rotate] [Reset] │ [Render Anchor View] [Use Rendered View] │ [Cancel]
```

- `Use Rendered View` is disabled until the staged render matches the current draft pose.
- Moving the draft after a successful render marks that staged render out of date and requires a new normal render intent.
- The prior authoritative Anchor, Dock image, Views, and Candidate remain intact until commit succeeds.

### Observation adjustment mode

```text
[Return to Scene View] │ [Move ●] [Rotate] [Reset] │ [Confirm and Add Observation] │ [Cancel]
```

Confirm freezes the exact draft pose and starts the normal render/acquisition path. Success publishes the View, activates it in Navigator, switches the Dock Work Area to its RGB/Mask, and changes its frustum from draft to committed presentation.

## Spatial Edit HUD

The HUD is a translucent, read-only viewport overlay positioned near the active draft frustum with a fixed offset.

```text
┌────────────────────────────────────┐
│ Adjust Anchor · Draft              │
│ Move                               │
│                                    │
│ ✓ Target is inside the frustum     │
│ △ Framing is close to the edge     │
│   View changed · render required   │
│                                    │
│ T Move   R Rotate                  │
└────────────────────────────────────┘
```

Placement and behavior:

- follows the active frustum in screen space, not the pointer;
- flips sides and clamps to a viewport-safe area to avoid covering the target;
- uses gentle positional smoothing only; high-frequency camera manipulation itself has no decorative animation;
- defaults to `pointer-events: none`;
- exposes the same facts through accessible description associated with the active toolbar mode;
- contains no primary/secondary actions and no remotely rendered image.

Permitted content is limited to facts directly useful for the current spatial operation and backed by available data: task, draft/staged state, Move/Rotate mode, target framing/clipping, changed/render-required state, render progress/failure, and keyboard hints. Internal Attempt IDs, raw utility scores, planner budgets, and uncalibrated quality percentages are not displayed.

## Navigator ↔ 3D evidence linkage

The existing bidirectional linkage is preserved and visually tightened:

```text
Navigator hover  → highlight matching frustum; do not move camera
Navigator click  → activate View and jump to its camera
Frustum hover    → highlight matching Navigator item
Frustum click    → activate View and switch Dock RGB/Mask
```

All paths resolve the same View identity. Presentation states:

- committed: normal solid frustum;
- active: stronger outline/emphasis;
- hover: temporary emphasis only;
- spatial draft: translucent/dashed;
- successfully rendered but not committed: solid draft with a clear staged marker;
- failed Observation: inspectable failed/excluded state, never masquerading as committed evidence.

Keyboard users receive the equivalent activation path through Navigator cards.

## Stable render and publication boundaries

### Draft manipulation

```text
Move/Rotate draft
→ update 3D frustum continuously (existing behavior)
→ update local HUD facts
→ keep Dock Work Area on the last authoritative or explicitly staged image
```

No manipulation frame starts a remote gsplat render or replaces RGB/Mask identity.

### Anchor

```text
draft pose
→ Render Anchor View
→ successful staged RGB/Mask published atomically to Dock as “not applied”
→ Use Rendered View
→ validation / re-lift / atomic Anchor cutover
```

Failure preserves the prior authoritative result and the editable draft. A late render whose draft identity no longer matches cannot replace the Dock.

### Observation

```text
draft pose
→ Confirm and Add Observation
→ freeze exact pose
→ render/acquire
→ publish one pending View identity
→ success: stable View + active Navigator item + committed frustum + Dock switch
```

Failure preserves existing results and leaves the failed/excluded Observation inspectable according to the existing View contract.

## Candidate presentation and action priority

A prior Candidate can be inspected while acquisition runs. Running acquisition blocks Native application but does not itself make that Candidate stale.

| Candidate/session state | Presentation | Primary lifecycle/publication action | Native operations |
| --- | --- | --- | --- |
| Prior Candidate + running Attempt | inspectable; marked temporarily blocked, not stale | `Cancel Acquisition` | disabled with one shared reason |
| Normal Ready-low-gain | new Candidate auto-published | none | enabled when otherwise applicable |
| Eligible forced-terminal Ready | terminal snapshot not yet published | `Use Ready Candidate` | prior Candidate follows its own state |
| Eligible Limited | terminal snapshot not yet published | `Use Limited Candidate` | prior Candidate follows its own state |
| Not Ready/ineligible | reason visible; no publishable Candidate action | none | no operation for the terminal result |
| Stable inputs changed | prior Candidate shown stale | `Re-Lift` when ready | disabled |
| Replacement failed | prior Candidate preserved with update-failed explanation | recovery according to current inputs | prior Candidate follows stale/applicability rules |

`Use Ready Candidate` and `Use Limited Candidate` publish an AI Candidate for inspection. Neither applies Native Selection. `Re-Lift` recomputes from exact current Stable inputs and never accepts an old terminal snapshot.

## Expert Recovery placement

Expert Recovery appears only when no Attempt is actively running.

- **Session Strip:** at most the one highest-priority lifecycle/publication action.
- **Inspector recovery disclosure:** explanation plus non-spatial secondary recovery that is actually available.
- **Work Area:** `Re-Lift`, retaining its existing target-level ownership.
- **Main 3D toolbar:** `Use Current View`, `Add Observation…`, and `Adjust Anchor`.
- **Global AI Select lifecycle menu:** destructive `Restart Target`.

Inspector may say, for example, `Add evidence from the 3D toolbar: Use Current View or Add Observation…`; it must not clone those commands as a second primary button group.

### Canonical labels

| Label | Meaning |
| --- | --- |
| `Cancel Acquisition` | close the running Attempt, reject late results, and preserve the prior Candidate |
| `Resume Acquisition` | resume the same compatible suspended Attempt |
| `Continue Acquisition` | create a fresh bounded Attempt under the current Series |
| `Use Ready Candidate` | explicitly publish an eligible forced-terminal Ready snapshot |
| `Use Limited Candidate` | explicitly publish an eligible Limited snapshot |
| `Use Current View` | capture the current editor camera as an Observation after safe pause |
| `Add Observation…` | create and adjust a new draft camera frustum after safe pause |
| `Adjust Anchor` | create a non-authoritative Anchor pose draft after safe pause |
| `Render Anchor View` | render the exact current Anchor draft into staged Evidence |
| `Use Rendered View` | commit the current matching staged Anchor result through its validation gate |
| `Re-Lift` | recompute Candidate from exact current Stable Evidence |
| `Restart Target` | discard the current AI target workflow through the global lifecycle menu |

Do not use persistent `Generate More`, `Regenerate`, or ambiguous `Use Result` labels.

## Interface sketches

### Wide / 1280×720 composition

```text
┌────────────────────────────── Main 3D Viewport ──────────────────────────────┐
│                                                                              │
│                         ┌─ Spatial Edit HUD ─────────────┐                    │
│                         │ Add Observation · Draft        │                    │
│                         │ Move · target in frame         │                    │
│                         │ View changed                   │                    │
│                         └────────────────────────────────┘                    │
│                                ╲ camera frustum                              │
│                                                                              │
│ [Return]* [Adjust Anchor] [Use Current View ▾] │ [Overlay ▾][Set][Add]…     │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────── AI View Dock ────────────────────────────────┐
│ Building selection · 4 valid observations                     [Cancel]       │
├──────────────┬──────────────────────────────────────┬────────────────────────┤
│ Navigator    │ Work Area                            │ Inspector              │
│              │                                      │                        │
│ [Anchor]     │       authoritative RGB / Mask       │ Assessment             │
│ [View 02]    │       + floating edit palette        │ Participation          │
│ [View 03]    │                                      │ Recovery / Details     │
└──────────────┴──────────────────────────────────────┴────────────────────────┘
```

### 1024×720 composition

```text
┌──────────────────────────── Main 3D Viewport ────────────────────────────────┐
│  HUD clamps inside the safe area; contextual toolbar remains one line       │
└──────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────── AI View Dock ────────────────────────────────┐
│ Evidence changed · fresh Attempt required              [Continue Acquisition]│
├──────────────┬───────────────────────────────────────────────┬───────────────┤
│ Navigator    │ Work Area                                     │ [Inspector >] │
│ single list  │ authoritative RGB / Mask                      │ restore edge  │
└──────────────┴───────────────────────────────────────────────┴───────────────┘
```

At narrow widths, status text elides before the fixed action slot; the action does not wrap. Inspector collapses before Navigator. The HUD clamps or flips; it never covers the entire target or forces a second toolbar row.

### Cross-surface interaction sketch

```text
Navigator item ── hover/select identity ── Camera frustum
       │                                      │
       └──── active View identity ────────────┘
                         │
                         ├─ Dock Work Area RGB/Mask
                         └─ viewport camera inspection pose
```

## Accessibility and responsive requirements

- Session changes use `aria-live="polite"`; errors may use an assertive channel only when immediate action is required.
- The queued authoring trigger retains visible focus during pause-pending; after acknowledgement, focus moves to the first meaningful control in the entered mode.
- Toolbar toggles expose `aria-pressed`; disabled reasons are keyboard- and screen-reader-accessible.
- HUD is not a keyboard stop. Its information is available through the active mode description.
- Navigator cards provide the keyboard route for selecting camera frustums.
- Popovers support Escape/outside click and restore focus.
- Locale expansion must be checked for the canonical labels and strip copy.
- Visual walkthroughs are required at wide, `1280×720`, and `1024×720`, with collapsed Inspector and long localized strings.
- Reduced-motion settings disable HUD positional smoothing and nonessential transitions.

## Validation families

- state/action availability matrix for Running, pause-pending, paused, changed-input, Ready, Limited, Not Ready, Cancelled, stale, Suspended, and failure;
- one-click auto-pause handoff, pause failure, repeated authoring, no-op/cancel adjustment, explicit Resume/Continue, and late callbacks;
- Candidate inspectable-but-application-blocked behavior while running;
- exact Ready/Limited publication consent and no automatic Native operation;
- toolbar ownership and absence of duplicate spatial commands in Session Strip/Dock;
- Session Strip single-action, focus, ARIA, locale, and no-wrap behavior;
- Spatial Edit HUD content, clamping, reduced motion, and non-interactivity;
- existing continuous frustum transform update regression;
- existing Navigator/frustum hover/select/jump/Dock-switch regression;
- no per-frame remote render or Dock replacement;
- staged Anchor identity, stale staged result rejection, atomic cutover, and failure preservation;
- Observation pending/success/failure publication and exact pose identity;
- wide, `1280×720`, and `1024×720` visual walkthrough;
- full repository test/lint/locales/build gates.

## Decomposition requirements

Do not implement this parent envelope directly. Split it into small TDD stages that separately own:

1. Session Strip state projection and responsive/accessibility behavior;
2. safe auto-pause intent handoff and explicit Resume/Continue semantics;
3. spatial toolbar state projection without duplicate Dock actions;
4. Spatial Edit HUD presentation;
5. stable Anchor/Observation Dock publication boundaries;
6. Candidate terminal/blocked/stale presentation and action matrix;
7. integration visual walkthroughs and regression guards for existing frustum linkage/manipulation.

Every stage must be jointly marked `agent-ready` by `CURRENT-TICKET-SPEC-MAPPING.md` and `V2-REVIEW-STATUS.md`.

## Non-goals

No new wizard, planner page, second spatial toolbar, interactive HUD command surface, per-frame remote camera render, persistent Generate More/Regenerate controls, default algorithm dashboard, Candidate provenance browser, camera mutation before pause acknowledgement, direct Candidate patching, automatic Native operation, or duplicated target restart/exit controls.
