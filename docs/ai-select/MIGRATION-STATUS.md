# AI Select Documentation Migration Status

Status: **v2 control plane current; pre-implementation review active**

## Completed

- v1.3 remains the shipped baseline; amended v2.0 is the target.
- Amendments 001–005 and ADRs through 0026 record Expert Recovery, Seed/discovery/depth staging, q+s recurrence, regional Reliability, finite pseudo-mass update, and bounded convergence.
- Accepted ADR history is retained and marked superseded where necessary rather than rewritten.
- Current mapping, traceability, manifest, review gate, graph, tickets, and agent guidance are aligned.
- Implemented v1 snapshots remain under `history/v1/`.
- Obsolete unimplemented planning envelopes were deleted and replaced.
- Context overlays 005–001 temporarily override stale root glossary terms.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = v2.0 + Amendments 001–005
planning phase         = pre-implementation review
accepted cross-ticket = Q4-B, Q5-D, Q6-B
agent-ready stages     = none
next review item       = Q7 Scope Delta + Frontier Debt
```

## Remaining work

- close Scope Delta and Frontier Debt;
- review View Utility probe/cost/exploration;
- close loop identity/budgets, terminal matrix, and Expert Recovery lifecycle;
- decompose reviewed parents into small TDD stages;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- consolidate context overlays only in one safe glossary cleanup.

No production code changed in these documentation decisions.
