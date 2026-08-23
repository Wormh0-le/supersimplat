# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendment 001 / ADR 0022: automation-default, expert-recoverable product.
- Amendment 002 / ADR 0023: CWED staging, S0/S1 shadow Seeds, seed-independent Envelope/Frontier, one production N channel.
- Amendment 003 / ADR 0024: continuous q+s deterministic bounded recurrence.
- Amendment 004 / ADR 0025: multi-channel same-decision readout, regional Reliability, LOO reference only.
- Amendment 005 / ADR 0026: finite pseudo-mass update, robust Reliability, bounded convergence.
- Amendment 006 / ADR 0027: component TargetScopeState, structured Frontier Debt, material Scope Delta mandatory re-solve.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle | complete | current/history separated |
| 0.5 | Product orientation | complete | Expert Recovery accepted |
| 1 | V2A/V2B depth, Seed, discovery | complete at parent-decision level | Amendment 002 |
| 2.1 | Recurrence model | complete | Q4-B / Amendment 003 |
| 2.2 | Readout + residual | complete | Q5-D / Amendment 004 |
| 2.3 | q/s update + Reliability + convergence | complete | Q6-B / Amendment 005 |
| 2.4 | Scope Delta + Frontier Debt | complete | Q7-B / Amendment 006 |
| 3 | V2F View Utility | next | probe, approximation, candidate pool, cost, exploration closed |
| 4 | V2G/V2I loop/budgets/replay | pending | taxonomy, identities, deterministic cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | Readiness × StopReason and consent closed |
| 6 | V2J UI + Expert Recovery | pending | recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | reviewed parents split into small TDD stages |
| 8 | Calibration/promotion/release | pending | explicit owners and gates |

## Current frontier

```text
next review item          = Q8 View Utility probe + cost + candidate pool
reviewed parent direction = V2A–V2E
accepted cross-ticket     = Q4-B, Q5-D, Q6-B, Q7-B
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent envelopes directly.
- Do not encode Frontier as Context or treat rejected Frontier as proven background.
- Do not promote/reject from a non-converged solve.
- Do not use a pre-delta or `scope-advanced` Consensus for Readiness/Candidate.
- Do not reopen a rejected component without new authoritative evidence/provenance.
- Do not let raw Gaussian count define component materiality or Debt.
- Do not exceed the finite Scope Revision budget or conflate it with Solver/View iterations.
- Do not accumulate previous q/s as Evidence, normalize View weights to one, mutate scope during solve, or publish from non-convergence.
- A stage becomes agent-ready only when this file and the current mapping agree.

## Known blockers

1. View Utility lacks a reviewed prediction/probe seam, approximation contract, deterministic cost model, and candidate-pool bounds.
2. Component adjacency, hysteresis, materiality, Debt, and scope-budget numbers need calibration ownership.
3. EvidenceWorkingSet v2 schema/identity migration must be decomposed.
4. Terminal behavior remains incomplete for Readiness × StopReason, including scope-budget exhaustion.
5. Loop replay remains unreconciled with endpoint attempts, scope revisions, and wall-clock variation.
6. Expert Recovery continuation budget and stale Candidate UX remain undefined.
7. Calibration, policy freeze, production promotion, cutover, and release qualification lack explicit ticket owners.
