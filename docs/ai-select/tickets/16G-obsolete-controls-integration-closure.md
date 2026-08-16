# 16G — Obsolete-control removal + post-16A integration closure

Status: planned — blocked by Tickets 16C, 16D, 16E and 16F

Blocked by: 16C, 16D, 16E, 16F, 16B, 16A

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

- [ ] Persistent Stop, Continue, Generate More and Regenerate Plan controls are
      absent from Navigator, Work Area, Inspector, toolbar and hidden menus.
- [ ] Their editor-side commands, presentation flags, public methods, locale
      strings, recovery-only styles and behavior tests are removed.
- [ ] Initial bounded planning remains intact and schedules `4–8` fixed local-
      offset automatic Generated Views, excluding the Anchor and User-added
      Views; validity failures may leave fewer usable Views.
- [ ] Initial planning failure retains exactly one failure-only retry icon in
      the Navigator empty/error state.
- [ ] Companion batch/ordinal planning protocol remains available for future
      planner work.

### Explicit recovery-command retirement

- [ ] Retry Render, Regenerate Prompt, Retry Mask and Retry Auto Segmentation
      are absent from Inspector actions, cards, bottom actions, Anchor Preview,
      menus and other product surfaces.
- [ ] Corresponding editor presentation flags, controller commands, public
      authoring wrappers, locale strings, recovery-only styling and direct
      behavior tests are removed.
- [ ] A failed generated or user-added render remains inspectable, failed and
      excluded; users may add a replacement View.
- [ ] Prompt/Mask failure recovery uses changed PromptState or manual
      Paint/Erase, creating a normal new intent rather than identical-input
      explicit retry.
- [ ] Anchor render failure recovery uses changed/reset pose and a normal new
      render.

### Retained correctness infrastructure

- [ ] Normal execution attempt identity, stale-result rejection, cancellation
      boundaries and distinct normal attempts remain tested.
- [ ] Idempotent same-attempt replay, transport cache-miss resubmission and
      Companion admission/cache remain intact.
- [ ] Removing product Retry commands does not weaken atomic publication or
      allow late work to attach to a new identity.

### Integrated surface and documentation

- [ ] Navigator, 2D Work Area and Inspector have one non-duplicated ownership
      model and the 2D canvas remains visually dominant.
- [ ] No Dock-wide status header, selected-work header or bottom Action Bar is
      rendered.
- [ ] No obsolete Proposal, planning or recovery terminology remains in current
      UI/locales.
- [ ] Icon controls use existing PCUI/editor controls, semantic tokens, tooltip
      service, focus behavior and custom SVG conventions.
- [ ] Compact action buttons prefer icon-only presentation with a mandatory
      tooltip and accessible name; persistent text buttons remain only where an
      icon would not provide a safely recognizable action.
- [ ] The final surface preserves the restrained dark technical-workbench
      language; no new UI framework, icon library or theme is introduced.
- [ ] Final Spec, ADR index, domain/lifecycle guidance, reusable interface
      documentation, mapping, traceability, Ticket graph and migration status
      agree with the implemented result.
- [ ] Ticket 17 consumes the final 16G toolbar/presentation seam and remains the
      owner of Undo and Fix, complete Restart and multi-target/tool-switch
      lifecycle.
- [ ] The 3D viewport does not regain Restart/Exit/More. Ticket 17 receives a
      global AI Select lifecycle-menu seam for target disposal and tool exit.

### Accessibility and responsive closure

- [ ] Every icon control has an accessible name, visible focus, keyboard
      activation and an accessible disabled reason where applicable.
- [ ] Menus/popovers close on Escape/outside click and restore focus.
- [ ] Reduced-motion preferences are respected.
- [ ] Wide desktop, approximately `1280×720` and approximately `1024×720`
      layouts preserve image fidelity, canvas priority and non-overlapping
      controls.

## Failure / recovery criteria

- [ ] No removed control can remain callable through an undocumented UI or
      public editor API.
- [ ] A failed replacement Candidate preserves the prior stale Candidate and
      never enables native application of partial/currently invalid data.
- [ ] Companion unavailable/incompatible states preserve inspectable local
      work and expose actionable disabled reasons without a duplicate Dock
      availability header.
- [ ] Tool disposal still releases target-local transient state and blocks late
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
