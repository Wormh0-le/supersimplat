# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 ticket is agent-ready**  
Updated: 2026-08-23

## Purpose

Final Spec v2.0 product scope is accepted, but the implementation graph still contains unresolved algorithm, ABI, lifecycle, recovery, and release-ownership decisions. This file is the human-readable gate preventing accepted scope from being mistaken for executable work.

## Review order

| Step | Area | Status | Exit condition |
|---|---|---|---|
| 0 | Control-plane lifecycle and current/historical separation | complete | current mapping, manifest, traceability and agent routing agree |
| 1 | V2A depth readout + depth-classified N | next | data path, traversal, schema, identity and benchmark seam closed |
| 2 | V2C/V2D/V2E consensus recurrence | pending | q0/update equations, lag, denominator expansion and bounded revision closed |
| 3 | V2F View Utility | pending | probe/approximation, cost model, candidate pool and realized-gain calibration closed |
| 4 | V2G/V2I loop state, outcomes, budgets and replay | pending | outcome taxonomy, identity hierarchy, deterministic cost and cancel/suspend semantics closed |
| 5 | V2H terminal publication | pending | complete Readiness × StopReason matrix and explicit Limited consent closed |
| 6 | V2J recovery and User-added View decision | pending | failure recovery remains usable; capability-removal decision independently justified |
| 7 | Ticket decomposition | pending | umbrella tickets split into small TDD stages |
| 8 | Calibration/promotion/release ownership | pending | explicit graph nodes own calibration, policy freeze, production identity, cutover and qualification |

## Current frontier

```text
next review item = V2A
parallel root requiring later review = V2C
agent-ready tickets = none
ticket in flight = none
```

## Rules

- Do not implement V2A–V2J from their current umbrella files.
- Do not modify production code merely to make the target spec look implemented.
- Repository facts are investigated from code/tests; product decisions are reviewed with the user.
- Each review step may amend the spec, supersede/create an ADR, refine terminology, and split tickets.
- A ticket becomes agent-ready only after this document and the current mapping are updated in the same reviewed commit.
- Experimental implementation may not enter the production Runtime Profile until calibrated and explicitly promoted.

## Known blockers carried into review

1. Current Direct Evidence CUDA ABI does not visibly carry camera-space `z`; V2A must define the real data path.
2. Expected depth, contribution classification, and same-decision traversal have no closed implementation algorithm.
3. Consensus/reliability/aggregation form a recurrence that the current linear ticket descriptions do not define.
4. View Utility lacks a defined prediction/probe seam and deterministic cost accounting.
5. Terminal behavior is not defined for every Readiness × StopReason combination.
6. Whole-loop replay is not reconciled with existing endpoint attempt IDs or wall-clock variation.
7. Removing User-added View may weaken recovery and needs an independent decision.
8. Calibration and production-promotion work currently has no ticket owner.
