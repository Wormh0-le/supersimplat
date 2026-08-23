# AI Select Documentation Migration Status

Status: **v2 control plane current; pre-implementation review active**

## Completed

- Final Spec v2.0 is the target; v1.3 remains the shipped baseline.
- Amendment 001 / ADR 0022 adopt automation-default Expert Recovery.
- Amendment 002 / ADR 0023 adopt CWED, S0/S1 shadow Seeds, seed-independent Envelope/Frontier, separate Coverage/Debt, and nonblocking classified-N experimentation.
- Amendment 003 / ADR 0024 adopt continuous q+s consensus, deterministic bounded recurrence, lagged Reliability, frozen scope, and post-solve Scope Delta.
- Amendment 004 / ADR 0025 adopt multi-channel same-decision readout, trusted regional Reliability, asymmetric Positive Frontier Protection, and offline leave-one-out reference benchmarking.
- ADR 0021 is retained and marked partially superseded rather than rewritten or deleted.
- Current mapping, traceability, manifest, review gate, graph, and agent guidance point to the amended target.
- Implemented v1 control-plane snapshots remain under `docs/ai-select/history/v1/`.
- Obsolete unimplemented V2A/V2B envelopes were deleted and replaced; obsolete V2J removal documentation remains deleted.
- Context amendments 004/003/002/001 override stale glossary definitions until controlled consolidation.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = v2.0 + Amendments 001–004
planning phase         = pre-implementation review
reviewed parent scope  = V2A, V2B
accepted cross-ticket  = Q4-B, Q5-D
agent-ready stages     = none
next review item       = Q6 q/s update + Reliability normalization + convergence
```

## Remaining work

- close q/s transforms, robust Reliability normalization, convergence, and Scope Delta thresholds;
- review View Utility probe, candidate pool, cost, and exploration schedule;
- close loop identity/budgets, terminal matrix, and Expert Recovery lifecycle;
- split parent envelopes into small TDD stages;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- fold context amendments into root `CONTEXT.md` only during a safe full-glossary consolidation.

No production code changed in these documentation decisions.
