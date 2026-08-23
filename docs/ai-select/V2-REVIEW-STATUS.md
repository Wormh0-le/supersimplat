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

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle and current/historical separation | complete | current and historical authority separated |
| 0.5 | Product orientation | complete | Amendment 001 + ADR 0022 accepted |
| 1 | V2A/V2B depth, Seed, and discovery model | complete at parent-decision level | Amendment 002 + ADR 0023 accepted; parent envelopes replaced |
| 2 | V2C/V2D/V2E consensus recurrence | next | q0/update equations, lag, scope-revision ordering, convergence closed |
| 3 | V2F View Utility implementation seam | pending | probe, candidate pool, cost model, exploration/decay calibration structure closed |
| 4 | V2G/V2I loop state, outcomes, budgets, replay, continuation | pending | taxonomy, identities, deterministic cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | complete Readiness × StopReason matrix and Limited consent closed |
| 6 | V2J UI + Expert Recovery | pending | secondary recovery surface and stale Candidate UX closed |
| 7 | Ticket decomposition | pending | reviewed envelopes split into small TDD stages |
| 8 | Calibration/promotion/release ownership | pending | explicit nodes own calibration, policy freeze, identity, cutover, qualification |

## Current frontier

```text
next review item          = V2C/V2D/V2E recurrence
reviewed parent direction = V2A, V2B
agent-ready stages        = none
ticket in flight          = none
```

## Rules

- Do not implement parent V2 envelopes directly.
- Do not make classified N a production or critical-path requirement.
- Do not use Seed as the sole Discovery Envelope, Coverage truth, Utility input, or stop authority.
- Do not allow failed S1 depth consistency to erase plausible Frontier support.
- Do not collapse Core Coverage and Frontier Debt.
- Do not delete User-added View implementation; it is Expert Recovery foundation.
- Repository facts come from code/tests; product decisions are reviewed with the user.
- A stage becomes agent-ready only when this file and current mapping change together.
- Experimental policies cannot enter the production Runtime Profile before calibration and explicit promotion.

## Known blockers carried into next reviews

1. Provisional Consensus representation, q0, and revision equation are undefined.
2. Reliability, aggregation, and consensus form a recurrence whose ordering and convergence are not closed.
3. Core promotion / Frontier rejection ordering relative to one consensus revision is undefined.
4. View Utility still lacks a reviewed prediction/probe seam and deterministic cost accounting.
5. Terminal behavior is incomplete for Readiness × StopReason combinations.
6. Whole-loop replay is not reconciled with endpoint attempts or wall-clock variation.
7. Expert Recovery continuation eligibility, budget reset, and stale Candidate UX remain undefined.
8. Calibration and production promotion have no ticket owner.
