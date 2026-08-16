# 16G — Obsolete-control removal + post-16A integration closure

Status: implemented — 2026-08-17

Prerequisites: 16C, 16D, 16E, 16F, 16B, 16A (implemented)

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§3–8, 16–19, 21–22, 24–26
- Ticket 16B superseding ADR and updated current product contract
- Tickets 16C–16F as the complete post-visual-review surface
- Tickets 03, 04C, 08B, 12 and 21 for retained attempt/replay correctness

## Inputs / preconditions

- Completed 16C Inspector/state projection
- Completed 16D shell/Navigator
- Completed 16E Work Area/Re-Lift/floating palette
- Completed 16F viewport toolbar and Anchor-adjustment lifecycle
- Existing explicit recovery and planning commands across presentation,
  controllers, public APIs, locales, styles, tests and documents

## Outputs / handoff artifacts

- One coherent AI Select surface with no obsolete duplicate entry points
- Deleted explicit recovery and persistent planning product logic
- Preserved internal attempt, replay and protocol correctness infrastructure
- Updated local documentation and reusable UI contract
- Automated and operator visual-validation evidence
- Ticket 17-ready Toolbar/presentation/lifecycle seam

## What to build

Complete the post-16A cutover atomically. Remove obsolete product controls and
their editor-facing logic after the replacement surfaces are usable, preserve
the lower-level correctness infrastructure explicitly retained by Ticket 16B,
and validate the final workspace across representative states and sizes.

## Acceptance criteria

### Planning-control retirement

- [x] Persistent Stop, Continue, Generate More and Regenerate Plan controls are
      absent from Navigator, Work Area, Inspector, toolbar and hidden menus.
- [x] Their editor-side commands, presentation flags, public methods, locale
      strings, recovery-only styles and behavior tests are removed.
- [x] Initial bounded planning remains intact and schedules `4–8` fixed local-
      offset automatic Generated Views, excluding the Anchor and User-added
      Views; validity failures may leave fewer usable Views.
- [x] Initial planning failure retains exactly one failure-only retry icon in
      the Navigator empty/error state.
- [x] Companion batch/ordinal planning protocol remains available for future
      planner work.

### Explicit recovery-command retirement

- [x] Retry Render, Regenerate Prompt, Retry Mask and Retry Auto Segmentation
      are absent from Inspector actions, cards, bottom actions, Anchor Preview,
      menus and other product surfaces.
- [x] Corresponding editor presentation flags, controller commands, public
      authoring wrappers, locale strings, recovery-only styling and direct
      behavior tests are removed.
- [x] A failed generated or user-added render remains inspectable, failed and
      excluded; users may add a replacement View.
- [x] Prompt/Mask failure recovery uses changed PromptState or manual
      Paint/Erase, creating a normal new intent rather than identical-input
      explicit retry.
- [x] Anchor render failure recovery uses changed/reset pose and a normal new
      render.

### Retained correctness infrastructure

- [x] Normal execution attempt identity, stale-result rejection, cancellation
      boundaries and distinct normal attempts remain tested.
- [x] Idempotent same-attempt replay, transport cache-miss resubmission and
      Companion admission/cache remain intact.
- [x] Removing product Retry commands does not weaken atomic publication or
      allow late work to attach to a new identity.

### Integrated surface and documentation

- [x] Navigator, 2D Work Area and Inspector have one non-duplicated ownership
      model and the 2D canvas remains visually dominant.
- [x] No Dock-wide status header, selected-work header or bottom Action Bar is
      rendered.
- [x] No obsolete Proposal, planning or recovery terminology remains in current
      UI/locales.
- [x] Icon controls use existing PCUI/editor controls, semantic tokens, tooltip
      service, focus behavior and custom SVG conventions.
- [x] Compact action buttons prefer icon-only presentation with a mandatory
      tooltip and accessible name; persistent text buttons remain only where an
      icon would not provide a safely recognizable action.
- [x] The final surface preserves the restrained dark technical-workbench
      language; no new UI framework, icon library or theme is introduced.
- [x] Final Spec, ADR index, domain/lifecycle guidance, reusable interface
      documentation, mapping, traceability, Ticket graph and migration status
      agree with the implemented result.
- [x] Ticket 17 consumes the final 16G toolbar/presentation seam and remains the
      owner of Undo and Fix, complete Restart and multi-target/tool-switch
      lifecycle.
- [x] The 3D viewport does not regain Restart/Exit/More. Ticket 17 receives a
      global AI Select lifecycle-menu seam for target disposal and tool exit.

### Accessibility and responsive closure

- [x] Every icon control has an accessible name, visible focus, keyboard
      activation and an accessible disabled reason where applicable.
- [x] Menus/popovers close on Escape/outside click and restore focus.
- [x] Reduced-motion preferences are respected.
- [x] Wide desktop, approximately `1280×720` and approximately `1024×720`
      layouts preserve image fidelity, canvas priority and non-overlapping
      controls.

## Failure / recovery criteria

- [x] No removed control can remain callable through an undocumented UI or
      public editor API.
- [x] A failed replacement Candidate preserves the prior stale Candidate and
      never enables native application of partial/currently invalid data.
- [x] Companion unavailable/incompatible states preserve inspectable local
      work and expose actionable disabled reasons without a duplicate Dock
      availability header.
- [x] Tool disposal still releases target-local transient state and blocks late
      publication.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- `rtk npm run build`
- Style/locale contracts prohibiting obsolete Proposal, recovery and planning
  text/actions
- Initial planner `4–8` schedule and partial usable-output regression tests
- External failure-state tests proving supported replacement recovery paths
- Retained attempt/replay/cache/stale-response regression tests
- Full Dock/Toolbar ownership and lifecycle matrix
- Operator visual walkthrough at wide desktop, approximately `1280×720` and
  approximately `1024×720`
- Operator walkthrough covers service unavailable/incompatible, no Target,
  planning/failure, RGB Ready, confirmed/unconfirmed Mask, Review, Excluded,
  Candidate current/stale/updating/failed, adjustment, filter-empty and
  collapsed-sidebar states

Completion reporting must distinguish editor UI/state, Companion capability,
documentation and validation. It must not claim production GPU behavior or
camera-planner quality improvement.

## Non-goals

- No new adaptive, Evidence-aware or replacement-view planner
- No removal of the internal Proposal compatibility wire
- No renderer, CUDA, P/N/V Evidence, Lift Readiness or Candidate-classification
  change
- No Candidate provenance/history browser
- No per-View delete action
- No Ticket 17 Undo and Fix, Restart or multi-target lifecycle

## Implementation record

- Removed persistent Stop/Continue/Generate More/Regenerate product state and
  editor commands while retaining the initial bounded plan, its sole
  failure-only planning retry and Companion batch/ordinal protocol.
- Removed identical-input Render, Prompt and Mask recovery commands from the
  controller, presentation, Dock, locale and style surfaces. Changed Prompt,
  manual Paint/Erase, changed/reset Anchor pose, exclusion and replacement
  Views now provide normal-intent recovery without weakening attempt identity,
  replay, cancellation, stale-result rejection or atomic publication.
- Synchronized the Final Spec, ADR index in the manifest, reusable Dock and
  Toolbar contracts, design system, ticket mapping, traceability, graph,
  migration status, walkthrough matrix and audit bundle to v2.32 with Ticket
  17 as the current frontier. `CONTEXT.md`, ADR 0018 and lifecycle/protocol
  guidance already stated the accepted contract and required no semantic
  amendment.
- The fresh production bundle contained no retired Dock header or recovery
  control, imported the tracked controlled-overlap fixture as 16,384 splats
  and opened AI Select. Wide desktop, `1280×720` and `1024×720` inspection
  preserved the canvas-first layout; deterministic tests cover the remaining
  state matrix that the unavailable local Companion could not drive live.
- Formal Standards and Spec reviews ran against `b82b9a8`. Their two findings
  were closed by expanding the negative source contract and replacing the last
  user-visible `regenerate the Prompt` instruction with changed-Prompt or
  replacement-View guidance.
- Validation passed: `rtk npm test` (607 editor tests and 446 Companion tests,
  with one existing Companion skip), `rtk npm run lint`,
  `rtk npm run lint:locales` (8 locales synchronized with 557 English keys),
  `rtk npm run build`, focused UI style-contract tests, touched-document link
  checks, manifest closure checks and `rtk git diff --check`.
- Ticket 16G changes editor UI/state and documentation only. It changes no
  Companion capability, protocol, renderer, CUDA, Evidence or planner-quality
  behavior, and adds no production GPU validation claim.
