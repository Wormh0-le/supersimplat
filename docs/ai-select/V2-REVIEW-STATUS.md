# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted cross-cutting decisions

### Product orientation

```text
automation-default + expert-recoverable
```

Recorded by Amendment 001 / ADR 0022.

### Seed, discovery, and depth staging

Recorded by Amendment 002 / ADR 0023:

- CWED is an internal contribution-weighted statistic, not surface truth;
- S0/S1 Seed variants are compared in parallel;
- Gaussian-center depth consistency is a soft feature;
- Core, seed-independent Discovery Envelope, and reversible Frontier are distinct;
- Core Coverage and Frontier Debt are separate;
- View Utility must include exploitation and exploration;
- current production retains one N channel;
- classified N moves to nonblocking V2AX.

### Deterministic bounded consensus recurrence

Recorded by Amendment 003 / ADR 0024:

- consensus state is continuous q plus independent support/knownness s;
- canonical output is a deterministic bounded batch solve over exact current Included Stable Evidence;
- Reliability is lagged by one Solver Iteration;
- one public Consensus Revision may contain multiple private iterations;
- scope is frozen during the solve and commits by post-solve two-phase Scope Delta;
- cache/arrival order cannot define canonical semantics;
- non-convergence is Limited/fail-closed and cannot publish Candidate.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle and current/historical separation | complete | current and historical authority separated |
| 0.5 | Product orientation | complete | Amendment 001 + ADR 0022 accepted |
| 1 | V2A/V2B depth, Seed, and discovery model | complete at parent-decision level | Amendment 002 + ADR 0023 accepted |
| 2.1 | V2C/V2D/V2E recurrence model | complete | Q4-B; Amendment 003 + ADR 0024 accepted |
| 2.2 | Consensus readout + Reliability residual | next | readout channels, visibility/trust gating, residual, Frontier protection closed |
| 2.3 | q/s transforms + convergence + scope thresholds | pending | q0/update equations, tolerance, max iterations, Scope Delta criteria closed |
| 3 | V2F View Utility implementation seam | pending | probe, candidate pool, cost model, exploration/decay calibration structure closed |
| 4 | V2G/V2I loop state, outcomes, budgets, replay, continuation | pending | taxonomy, identities, deterministic cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | complete Readiness × StopReason matrix and Limited consent closed |
| 6 | V2J UI + Expert Recovery | pending | secondary recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | reviewed envelopes split into small TDD stages |
| 8 | Calibration/promotion/release ownership | pending | explicit nodes own calibration, policy freeze, identity, cutover, qualification |

## Current frontier

```text
next review item          = Q5 consensus readout + reliability residual
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B recurrence for V2C/V2D/V2E
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent V2 envelopes directly.
- Do not reduce consensus to hard Selected/Rejected/Uncertain values.
- Do not conflate low-support unknown with high-support conflict.
- Do not let Reliability consume same-iteration q/s.
- Do not let View arrival order or cache history define canonical output.
- Do not mutate Core/Frontier during a Solver Iteration.
- Do not use a non-converged revision to establish Ready or publish Candidate.
- Do not make classified N a production or critical-path requirement.
- Do not use Seed as the sole Discovery Envelope, Coverage truth, Utility input, or stop authority.
- Do not delete User-added View implementation; it is Expert Recovery foundation.
- A stage becomes agent-ready only when this file and current mapping change together.
- Experimental policies cannot enter the production Runtime Profile before calibration and explicit promotion.

## Known blockers carried into next reviews

1. The q/s consensus readout under one View is not yet defined.
2. Reliability residual, visibility/trust gating, boundary treatment, and robust normalization are not closed.
3. Exact q0/s0 and q/s update transforms are not closed.
4. Convergence metric, numerical tolerance, maximum iterations, and non-convergence diagnostic schema need calibration ownership.
5. Core promotion, Frontier rejection, and Frontier Debt thresholds remain undefined.
6. View Utility still lacks a reviewed prediction/probe seam and deterministic cost accounting.
7. Terminal behavior is incomplete for Readiness × StopReason combinations.
8. Whole-loop replay is not reconciled with endpoint attempts or wall-clock variation.
9. Expert Recovery continuation eligibility, budget reset, and stale Candidate UX remain undefined.
10. Calibration and production promotion have no ticket owner.
