# AI Select Documentation Migration Status

Status: **v2 control plane current; pre-implementation review active**

## Completed

- v1.3 remains shipped; amended v2.0 is the target.
- Amendments 001–006 and ADRs through 0027 record Expert Recovery, staged depth/Seed discovery, q+s recurrence/readout/update, component Target Scope, mandatory re-solve, and structured Frontier Debt.
- Accepted history is retained and marked superseded where necessary rather than rewritten.
- Current mapping, traceability, manifest, review gate, graph, tickets, and agent guidance are aligned.
- Implemented v1 snapshots remain under `history/v1/`; obsolete unimplemented planning envelopes were deleted/replaced.
- Context overlays 006–001 temporarily override stale root glossary terms.
- EvidenceWorkingSet v1 remains the runtime baseline and has not been silently repurposed.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = v2.0 + Amendments 001–006
planning phase         = pre-implementation review
reviewed parent scope  = V2A–V2E
accepted cross-ticket = Q4-B, Q5-D, Q6-B, Q7-B
agent-ready stages     = none
next review item       = Q8 View Utility probe + cost + candidate pool
```

## Remaining work

- review View Utility probe/cost/candidate pool/exploration;
- close loop identity/budgets, terminal matrix, and Expert Recovery lifecycle;
- decompose reviewed parents into small TDD stages, including TargetScopeState and EvidenceWorkingSet v2 migration;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- consolidate Context overlays only in one safe glossary cleanup.

No production code changed in these documentation decisions.
