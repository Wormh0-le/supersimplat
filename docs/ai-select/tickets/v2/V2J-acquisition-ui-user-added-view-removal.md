# V2J — Acquisition UI + User-added View removal

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2H, V2I
Blocks: none

Additional gate: the User-added View runtime removal executes as this
ticket's cutover — spec-level supersession is done (2026-08-22); shipped
behavior remains v1.3 until this ticket lands.

## Final Spec v2.0 mapping

- Final Spec v2.0 §10; ADR 0020 (consent presentation);
  `CONTEXT.md` non-normative "Acquisition UI (next architecture)"

## Goal

Present the minimal acquisition status surface with a dedicated Cancel
control, and execute the User-added View capability removal as part of the
supersession cutover.

## Inputs / preconditions

- Loop state machine + stop reasons (V2I/V2G);
- auto-publish terminal behavior + consent structure (V2H, ADR 0020);
- retired planning-control contract (Tickets 16B–16G, 17): persistent
  Stop/Generate More stay retired.

## Outputs / handoff

- Minimal status surface during the loop: current phase (View k /
  evaluating), existing View inspector entries, terminal stop reason,
  readiness state;
- dedicated Cancel control terminating the current loop immediately while
  preserving all completed artifacts;
- User-added View capability removed (Anchor becomes the only user-placed
  camera); manual Mask edits on Generated Views keep the User Confirmed
  reliability exemption;
- consent-presentation updates implied by automatic publication (ADR 0020).

## Acceptance criteria

- [ ] Live coverage/utility numbers are absent from the default presentation;
      a diagnostics mode may expose them during calibration only.
- [ ] Status surface shows phase, stop reason and readiness without new
      duplicated ownership against Inspector/Dock/Toolbar contracts (R058–
      R062 style ownership rules carry over).
- [ ] Dedicated Cancel control works immediately, preserves artifacts, and is
      not reachable through any retired planning command.
- [ ] No persistent Stop/Continue/Generate More/Regenerate control reappears;
      post-loop "continue acquisition" remains unset and unshipped.
- [ ] User-added View entry points, commands, locale strings, public APIs and
      tests are removed in the supersession cutover; Anchor is the only
      user-placed camera.
- [ ] Manual Paint/Erase edits on Generated Views retain the User Confirmed
      exemption end to end.
- [ ] Accessibility/responsive contracts of Tickets 16D–16G remain satisfied
      for the new status surface (accessible names, focus, reduced motion,
      ~1280×720 / ~1024×720 layouts).
- [ ] Final Spec (v2.0), mapping, traceability, ticket graph and locales agree
      with the shipped surface.

## Validation

- `rtk npm test`; `rtk npm run lint`; `rtk npm run lint:locales`;
  `rtk npm run build`;
- UI contract tests for absence of live numbers and retired controls;
- operator visual walkthrough including running loop, cancel mid-loop,
  auto-publish terminal, Limited terminal states.

## Non-goals

- No new coverage/utility visualization; no "continue acquisition" control;
  no planning-control revival; no Candidate provenance browser.
