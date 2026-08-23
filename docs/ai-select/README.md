# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendments 009 → 001
→ Final Spec v2.0
→ ADR 0030 → 0020
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
→ Publication Eligibility
→ normal Ready auto-publication or explicit Ready/Limited consent
→ progressive UI + Expert Recovery (next review)
```

Re-Lift recomputes; it does not accept an existing terminal snapshot. A running Attempt keeps the prior Candidate inspectable but temporarily blocks applying it. Not Ready, stale, scope-advanced, non-converged, Suspended, and incomplete results cannot publish.

Implemented v1 history remains under `history/v1/`. ADR 0020 is retained and marked partially superseded. Context overlays 009–001 must eventually be consolidated into root `CONTEXT.md` in one controlled cleanup.