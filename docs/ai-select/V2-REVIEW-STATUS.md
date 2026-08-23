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

- CWED is internal, not surface truth;
- S0/S1 Seeds are compared in parallel;
- Core, seed-independent Discovery Envelope, and reversible Frontier are distinct;
- Core Coverage and Frontier Debt are separate;
- classified N is nonblocking V2AX.

### Deterministic bounded consensus recurrence

Recorded by Amendment 003 / ADR 0024:

- consensus state is continuous q plus support/knownness s;
- canonical output is a deterministic bounded batch solve;
- Reliability is lagged by one Solver Iteration;
- scope is frozen and commits by post-solve Scope Delta;
- non-convergence is Limited/fail-closed.

### Consensus readout and regional Reliability

Recorded by Amendment 004 / ADR 0025:

- production uses same-decision `M_scope/M_fg/M_known/M_core/M_frontier` readout moments;
- support-aware membership is `q̃=0.5+s(q-0.5)`;
- residuals are trusted and separately normalized by positive interior, negative ring, and boundary;
- Far Neutral is excluded;
- positive Frontier protection is asymmetric;
- insufficient comparison support is neutral, not a penalty;
- User Confirmed/manual observations retain full semantic weight;
- leave-one-out is offline/reference-only.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle and current/historical separation | complete | current and historical authority separated |
| 0.5 | Product orientation | complete | Amendment 001 + ADR 0022 accepted |
| 1 | V2A/V2B depth, Seed, and discovery model | complete at parent-decision level | Amendment 002 + ADR 0023 accepted |
| 2.1 | V2C/V2D/V2E recurrence model | complete | Q4-B; Amendment 003 + ADR 0024 accepted |
| 2.2 | Consensus readout + Reliability residual | complete | Q5-D; Amendment 004 + ADR 0025 accepted |
| 2.3 | q/s transforms + Reliability normalization + convergence | next | q0/update equations, robust weight mapping, tolerance, max iterations closed |
| 2.4 | Scope Delta + Frontier Debt thresholds | pending | promotion/rejection, envelope expansion, debt representation closed |
| 3 | V2F View Utility implementation seam | pending | probe, candidate pool, cost model, exploration/decay structure closed |
| 4 | V2G/V2I loop state, outcomes, budgets, replay, continuation | pending | taxonomy, identities, deterministic cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | Readiness × StopReason matrix and Limited consent closed |
| 6 | V2J UI + Expert Recovery | pending | recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | reviewed envelopes split into small TDD stages |
| 8 | Calibration/promotion/release ownership | pending | explicit nodes own calibration, policy freeze, identity, cutover, qualification |

## Current frontier

```text
next review item          = Q6 q/s update + Reliability normalization + convergence
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B and Q5-D across V2C/V2D/V2E
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent V2 envelopes directly.
- Do not reduce consensus to hard classes or a single unqualified soft mask.
- Do not treat low semantic-scope mass as background disagreement.
- Do not let Reliability consume same-iteration q/s.
- Do not let arrival order or cache history define canonical output.
- Do not mutate scope during a Solver Iteration.
- Do not use non-converged output to establish Ready or Candidate.
- Do not apply Reliability to raw V.
- Do not downweight User Confirmed/manual observations.
- Do not use symmetric Frontier exemption for negative-ring conflict.
- Do not put leave-one-out consensus on the production critical path.
- Do not make classified N a production requirement.
- Do not use Seed as sole Discovery/Coverage/Utility/stop authority.
- Do not delete User-added View implementation.
- A stage becomes agent-ready only when this file and current mapping change together.
- Experimental policies cannot enter the production Runtime Profile before calibration and explicit promotion.

## Known blockers carried into next reviews

1. Exact q0/s0 and q/s update transforms are not closed.
2. Robust residual-to-weight normalization, warm-up, floor, and degenerate robust scale are not closed.
3. Convergence metric, numerical tolerance, maximum iterations, and non-convergence diagnostics need calibration ownership.
4. Core promotion, Frontier rejection, Envelope expansion, and Frontier Debt thresholds remain undefined.
5. GPU channel layout, memory/performance budget, and reference parity remain decomposition gates.
6. View Utility lacks a reviewed prediction/probe seam and deterministic cost accounting.
7. Terminal behavior is incomplete for Readiness × StopReason.
8. Whole-loop replay is not reconciled with endpoint attempts or wall-clock variation.
9. Expert Recovery continuation eligibility, budget reset, and stale Candidate UX remain undefined.
10. Calibration and production promotion have no ticket owner.
