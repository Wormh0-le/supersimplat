# V2G — Dual budget, failure semantics, termination

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2F
Blocks: V2H, V2I

## Final Spec v2.0 mapping

- Final Spec v2.0 §6.3–6.4; supersedes ADR 0018 `4–8` range with the dual budget
  (single-result authoring part of ADR 0018 carries over)

## Goal

Implement the dual budget, failure semantics (failed Views free, bounded
replacement, stage-failure circuit breaker) and the tightened-gain
termination rule of the acquisition loop.

## Inputs / preconditions

- View Utility + candidate pool (V2F);
- readiness authority (Ticket 13, carried over);
- loop stop-reason working set from spec §6.3.

## Outputs / handoff

- Dual budget accounting: View-count hard maximum + latency/cost ceiling;
  either exhaustion stops the loop;
- failure semantics: a failed View consumes no View budget; consecutive
  same-stage failures reach a small cap → bounded replacement with the
  next-best utility candidate; continued failure → stage-failure circuit
  breaker;
- structured stop-reason working set:
  `ready-and-low-marginal-gain`, `marginal-gain-exhausted`,
  `view-budget-exhausted`, `cost-budget-exhausted`, `no-feasible-view`,
  `stage-failure`, `stale/cancelled/suspended`;
- tightened-gain termination: reaching Ready does not stop; the marginal-gain
  threshold tightens once Ready and the loop terminates only below the
  tightened threshold.

## Acceptance criteria

- [ ] Both budget dimensions enforced; either exhaustion produces the correct
      stop reason.
- [ ] Failed Views never consume View budget; replacement ordering follows
      utility; circuit breaker fires after the bounded cap.
- [ ] Stop reasons are structured, machine-readable, and carry enough context
      for the UI surface (V2J); canonical naming is recorded as the working
      set pending the domain-modeling naming pass — no premature freeze.
- [ ] Ready does not immediately stop; tightened-threshold logic is tested
      (gain above tightened threshold continues, below terminates).
- [ ] All budget/threshold values are named calibration inputs (spec §12),
      not hardcoded constants.
- [ ] Fixed-four / `4–8` planning is no longer on the product path; it
      survives only as frozen regression/ablation baseline.

## Validation

- Budget exhaustion tests (each dimension, each stop reason);
- failure/replacement/circuit-breaker sequence tests;
- tightened-threshold state machine tests;
- determinism of stop-reason emission for replayed attempts.

## Non-goals

- No publication semantics (V2H), no browser state machine (V2I), no numeric
  values (calibration round owns them).
