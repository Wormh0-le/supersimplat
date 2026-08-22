# V2H — Terminal publication semantics (auto-publish / Limited)

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2E, V2G
Blocks: V2J

## Final Spec v2.0 mapping

- Final Spec v2.0 §6.4; ADR 0020 (consent-structure change)

## Goal

Implement the terminal publication semantics: automatic atomic Candidate
publication at `ready-and-low-marginal-gain`, no-Candidate publication for
`Limited` + budget exhaustion, and unchanged explicit Re-Lift semantics.

## Inputs / preconditions

- Stop reasons + tightened-gain terminal (V2G);
- revised aggregate + readiness (V2E, Ticket 13 authority);
- production publication gate (Ticket 21):
  `selection-service-companion/src/selection_service_companion/candidate_re_lift.py`
  currently blocks only on readiness == `not-ready` (~L455).

## Outputs / handoff

- Automatic atomic Candidate publication at the
  `ready-and-low-marginal-gain` terminal (consent-structure change per ADR
  0020);
- Limited + budget-exhausted path: publishes readiness + structured reason,
  NO Candidate; explicit user Re-Lift can still publish Limited (explicit
  consent preserved);
- Re-Lift unchanged: user-triggered re-evaluation against exact current
  Evidence, atomic publication attempt, never restarts acquisition, stale
  identity publishes staleness;
- consent/presentation hooks for V2J.

## Acceptance criteria

- [ ] At `ready-and-low-marginal-gain` the Candidate is published
      automatically and atomically; no partial or non-current publication is
      possible.
- [ ] The auto-published Candidate is inspectable and replaceable and never
      self-executes Native operations; Native operations remain user-only.
- [ ] `Limited` + budget exhaustion publishes readiness + reason without a
      Candidate; the explicit Re-Lift Limited path is preserved.
- [ ] Explicit Re-Lift keeps v1.3 semantics: re-evaluates exact current
      Evidence, attempts atomic publication, never restarts the loop, stale
      identity yields stale result not Candidate.
- [ ] Publication still requires exact Direct Evidence + checksum-bound
      production identity (ADR 0019 carry-over).
- [ ] The publication gate change (previously blocking only on `not-ready`)
      is covered by regression tests including the new auto-publish branch.

## Validation

- Terminal publication tests for each stop-reason branch;
- atomicity/failure tests (no partial publication on cancel/OOM/failure);
- Re-Lift regression suite (v1.3 semantics unchanged);
- stale-identity publication tests.

## Non-goals

- No UI surface (V2J), no readiness threshold values (calibration), no Native
  operation automation.
