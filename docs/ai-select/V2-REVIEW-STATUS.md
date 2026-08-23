# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendment 001 / ADR 0022: automation-default, expert-recoverable product.
- Amendment 002 / ADR 0023: CWED staging, S0/S1 shadow Seeds, seed-independent Envelope/Frontier, one production N channel.
- Amendments 003–005 / ADRs 0024–0026: continuous q+s recurrence, multi-channel regional Reliability, finite pseudo-mass update, and bounded convergence.
- Amendment 006 / ADR 0027: component TargetScopeState, structured Frontier Debt, and mandatory re-solve after material Scope Delta.
- Amendment 007 / ADR 0028: finite layered candidate pool, geometry pruning, shortlist low-resolution ViewUtilityProbe, deterministic cost units, and winner-only full acquisition.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle | complete | current/history separated |
| 0.5 | Product orientation | complete | Expert Recovery accepted |
| 1 | V2A/V2B depth, Seed, discovery | complete at parent-decision level | Amendments 002 / ADR 0023 |
| 2 | V2C/V2D/V2E iterative consensus/scope | complete at parent-decision level | Q4-B through Q7-B / Amendments 003–006 |
| 3 | V2F View Utility | complete at parent-decision level | Q8-C / Amendment 007 / ADR 0028 |
| 4 | V2G/V2I budgets, outcomes, identity, replay, continuation | **next** | deterministic accounting, attempt hierarchy, journal, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | full Readiness × StopReason matrix and Limited consent closed |
| 6 | V2J UI + Expert Recovery | pending | recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | reviewed parents split into small TDD stages |
| 8 | Calibration/promotion/release | pending | explicit owners and gates |

## Current frontier

```text
next review item          = Q9 V2G/V2I budgets + identity + replay
reviewed parent direction = V2A–V2F
accepted decisions        = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent envelopes directly.
- Do not treat ViewUtilityProbe as RGB, Evidence, Coverage, Readiness, or Candidate authority.
- Do not use transient wall-clock or GPU load in canonical camera ranking.
- Do not full-render or run SAM for unselected candidates on the product path.
- Do not silently fall back to fixed-four or geometry-only winner selection when the required probe fails.
- Do not publish Candidate from non-converged, scope-advanced, stale, or otherwise incompatible state.
- Do not mutate Scope during a canonical solve.
- Do not make classified N or leave-one-out Reliability a production prerequisite.
- A stage becomes agent-ready only when this file and the current mapping agree.

## Known blockers

1. V2G/V2I do not yet define deterministic budget accounting, probe/acquisition failure taxonomy, bounded replacement, or cost-ceiling semantics.
2. Loop, acquisition-attempt, iteration, Scope Revision, Consensus Revision, probe, render, mask, Evidence, and endpoint-attempt identities are not reconciled.
3. Exact replay is not reconciled with measured latency, timeout, cache history, or partially completed products.
4. Continue Acquisition budget inheritance/reset and its identity relation to the previous terminal attempt remain undefined.
5. Terminal behavior remains incomplete for Readiness × StopReason combinations.
6. Expert Recovery stale-Candidate presentation remains undefined.
7. Calibration, policy freeze, production promotion, cutover, and release qualification lack explicit owners.
