# AI Select Documentation Migration Status

Status: **v2 control plane current; pre-implementation review active**

## Completed

- v1.3 remains the shipped baseline; amended v2.0 is the target.
- Amendments 001–007 and ADRs through 0028 record Expert Recovery, Seed/discovery/depth staging, q+s recurrence, regional Reliability, pseudo-mass convergence, component Scope/Frontier Debt, and the hybrid ViewUtilityProbe.
- Accepted ADR history is retained and marked superseded where necessary rather than rewritten.
- Current mapping, traceability, manifest, review gate, graph, tickets, and agent guidance are aligned.
- Implemented v1 snapshots remain under `history/v1/`; obsolete unimplemented planning envelopes were deleted and replaced.
- Context overlays 007–001 temporarily override stale root glossary terms.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = v2.0 + Amendments 001–007
planning phase         = pre-implementation review
reviewed parent scope  = V2A–V2F
accepted decisions     = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C
agent-ready stages     = none
next review item       = Q9 V2G/V2I budgets + identity + replay
```

## Remaining work

- close loop budget/outcome/identity/journal/replay/continuation semantics;
- close terminal publication and Expert Recovery UX;
- decompose reviewed parent envelopes into small TDD stages;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- consolidate context overlays only in one safe glossary cleanup.

No production code changed in these documentation decisions.
