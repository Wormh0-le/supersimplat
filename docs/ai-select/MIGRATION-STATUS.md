# AI Select Documentation Migration Status

Status: **v2 control plane current; pre-implementation review active**

## Completed

- Final Spec v2.0 is the target architecture; v1.3 remains the shipped baseline.
- Amendment 001 / ADR 0022 adopt automation-default Expert Recovery.
- Amendment 002 / ADR 0023 adopt CWED terminology, S0/S1 shadow Seeds, seed-independent Discovery Envelope/Frontier, separate Core Coverage/Frontier Debt, and nonblocking classified-N experimentation.
- ADR 0021 is retained and marked partially superseded rather than rewritten or deleted.
- Current mapping, traceability, manifest, review gate, graph, and agent guidance point to the amended target.
- Exact implemented v1 control-plane snapshots remain under `docs/ai-select/history/v1/`.
- Obsolete unimplemented V2A/V2B envelopes were deleted and replaced; obsolete V2J removal documentation remains deleted.
- Context amendments 002/001 explicitly override stale root glossary definitions until controlled consolidation.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = v2.0 + Amendments 001/002
planning phase         = pre-implementation review
reviewed parent scope  = V2A, V2B
agent-ready stages     = none
next review item       = V2C/V2D/V2E recurrence
```

## Remaining work

- close consensus/reliability/aggregation recurrence and scope-revision ordering;
- review View Utility probe, candidate pool, cost, and exploration schedule;
- close loop identity/budgets, terminal matrix, and Expert Recovery lifecycle;
- split parent envelopes into small TDD stages;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- fold context amendments into root `CONTEXT.md` only during a safe full-glossary consolidation.

No production code changed in these documentation decisions.
