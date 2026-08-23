# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendments 008 → 001
→ Final Spec v2.0
→ ADR 0029 → 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

Runtime remains implemented v1.3; no V2 stage is agent-ready.

## Accepted v2 architecture

```text
Seed / component Scope / Frontier Debt
→ bounded q+s Consensus and regional Reliability
→ hybrid ViewUtilityProbe
→ Browser-owned Acquisition Series/Attempts/Iterations
→ append-only Decision Journal + deterministic budgets
→ terminal publication matrix (next review)
→ Expert Recovery
```

Same-attempt replay, fresh retry, exact resume, and Continue Acquisition are distinct. Failed work is free only for the usable-observation allowance. Wall-clock never redefines canonical candidate ranking.

Implemented v1 history remains under `history/v1/`. Context overlays 008–001 must eventually be consolidated into root `CONTEXT.md` in one controlled cleanup.
