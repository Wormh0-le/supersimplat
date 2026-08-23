# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 ticket is agent-ready**  
Updated: 2026-08-23

## Accepted cross-cutting product decision

Product orientation is now:

```text
automation-default
+
expert-recoverable
```

The automatic loop remains the normal path. After it stops, an expert may add a deliberate User-added View or start a fresh bounded continuation attempt. Final Spec Amendment 001 and ADR 0022 record the decision.

This resolves whether expert takeover exists. It does not yet resolve the exact V2G/V2I/V2J lifecycle, budget, and UI contract.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle and current/historical separation | complete | current mapping, manifest, traceability, and agent routing agree |
| 0.5 | Product orientation: automatic-only vs expert-recoverable | complete | Amendment 001 + ADR 0022 accepted |
| 1 | V2A depth readout + depth-classified N | next | data path, traversal, schema, identity, benchmark seam closed |
| 2 | V2C/V2D/V2E consensus recurrence | pending | q0/update equations, lag, denominator expansion, bounded revision closed |
| 3 | V2F View Utility | pending | probe/approximation, cost model, candidate pool, realized-gain calibration closed |
| 4 | V2G/V2I loop state, outcomes, budgets, replay, continuation | pending | outcome taxonomy, identity hierarchy, deterministic cost, cancel/suspend/continue closed |
| 5 | V2H terminal publication | pending | complete Readiness × StopReason matrix and explicit Limited consent closed |
| 6 | V2J acquisition UI + Expert Recovery | pending | secondary recovery surface, Add Observation, Continue Acquisition, stale Candidate UX closed |
| 7 | Ticket decomposition | pending | umbrella tickets split into small TDD stages |
| 8 | Calibration/promotion/release ownership | pending | explicit graph nodes own calibration, policy freeze, production identity, cutover, qualification |

## Current frontier

```text
next review item = V2A
parallel root requiring later review = V2C
agent-ready tickets = none
ticket in flight = none
```

## Rules

- Do not implement V2A–V2J from their current umbrella files.
- Do not delete the existing User-added View implementation; it is a migration foundation for Expert Recovery.
- Do not expose Expert Recovery as persistent camera management during a running loop.
- Repository facts are investigated from code/tests; product decisions are reviewed with the user.
- A stage becomes agent-ready only when this document and the current mapping change together.
- Experimental policies cannot enter the production Runtime Profile before calibration and explicit promotion.

## Known blockers carried into review

1. Current Direct Evidence CUDA ABI does not visibly carry camera-space `z`.
2. Expected depth, contribution classification, and same-decision traversal lack a closed algorithm.
3. Consensus/reliability/aggregation form an undefined recurrence.
4. View Utility lacks a prediction/probe seam and deterministic cost accounting.
5. Terminal behavior is incomplete for Readiness × StopReason combinations.
6. Whole-loop replay is not reconciled with endpoint attempt IDs or wall-clock variation.
7. Expert Recovery continuation eligibility, budget reset, and stale Candidate UX remain undefined.
8. Calibration and production promotion have no ticket owner.
