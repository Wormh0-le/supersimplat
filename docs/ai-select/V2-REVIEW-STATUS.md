# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendment 001 / ADR 0022: automation-default, expert-recoverable product.
- Amendment 002 / ADR 0023: CWED staging, S0/S1 shadow Seeds, seed-independent Envelope/Frontier, one production N channel.
- Amendment 003 / ADR 0024: continuous q+s deterministic bounded recurrence.
- Amendment 004 / ADR 0025: multi-channel same-decision readout, regional Reliability, LOO reference only.
- Amendment 005 / ADR 0026: finite pseudo-mass q/s update, robust relative Reliability, maturity-gated absolute guard, and multi-condition bounded convergence.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle | complete | current/history separated |
| 0.5 | Product orientation | complete | expert recovery accepted |
| 1 | V2A/V2B depth, Seed, discovery | complete at parent-decision level | Amendments 002 / ADR 0023 |
| 2.1 | Recurrence model | complete | Q4-B / Amendment 003 |
| 2.2 | Readout + residual | complete | Q5-D / Amendment 004 |
| 2.3 | q/s update + Reliability normalization + convergence | complete | Q6-B / Amendment 005 |
| 2.4 | Scope Delta + Frontier Debt | next | promotion/retention/rejection/Envelope expansion/readiness semantics closed |
| 3 | V2F View Utility | pending | probe, candidate pool, cost, exploration closed |
| 4 | V2G/V2I loop/budgets/replay | pending | taxonomy, identity, cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | Readiness × StopReason and consent closed |
| 6 | V2J UI + Expert Recovery | pending | recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | small TDD stages |
| 8 | Calibration/promotion/release | pending | explicit owners and gates |

## Current frontier

```text
next review item          = Q7 Scope Delta + Frontier Debt
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B, Q5-D, Q6-B
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent envelopes directly.
- Do not accumulate previous q/s as new Evidence.
- Do not normalize Reliability weights to sum to one.
- Do not activate the absolute residual guard before the declared maturity gate.
- Do not conflate low-support unknown with high-support conflict.
- Do not let Reliability change raw V or consume same-iteration q/s.
- Do not let cache history or View arrival order define canonical output.
- Do not mutate scope during a solve.
- Do not publish Candidate from non-converged or oscillating consensus.
- Do not make classified N a production prerequisite.
- A stage becomes agent-ready only when this file and the current mapping agree.

## Known blockers

1. Core promotion, Frontier retention/rejection, and Discovery Envelope expansion are not closed.
2. Frontier Debt representation and its Lift Readiness effect are undefined.
3. Exact calibration values, material-support set, GPU layout, tolerance, and performance budgets remain unowned.
4. View Utility lacks a reviewed probe and deterministic cost model.
5. Terminal behavior is incomplete for Readiness × StopReason.
6. Loop replay remains unreconciled with endpoint attempts and wall-clock variation.
7. Expert Recovery continuation budget and stale Candidate UX remain undefined.
8. Calibration, policy freeze, production promotion, cutover, and release qualification lack explicit ticket owners.
