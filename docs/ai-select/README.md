# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendments 005 → 001
→ Final Spec v2.0
→ ADR 0026 → 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

No V2 stage is agent-ready. Runtime remains implemented v1.3.

## Accepted architecture

```text
Conservative Seed
→ Core + seed-independent Envelope / reversible Frontier
→ deterministic bounded q+s Consensus
→ same-decision P/K/C/F readout
→ regional Reliability
→ immutable P/N reaggregation + unweighted V
→ finite-posterior q + semantic/visible support s
→ bounded convergence / oscillation diagnostics
→ post-solve Scope Delta (next review)
→ View Utility and bounded acquisition
```

Reliability weights are independent `[r_min,1]`, not sum-normalized. The absolute residual guard is enabled only after consensus maturity. Non-converged/oscillating solves cannot publish Candidate.

## Documentation lifecycle

Amendments and later ADRs supersede conflicting clauses without rewriting accepted history. Implemented v1 snapshots stay under `history/v1/`. Unimplemented superseded envelope files are deleted and replaced. Context overlays 005–001 must eventually be folded into root `CONTEXT.md` in one controlled cleanup and then removed.

## Next review

```text
Q7 — Scope Delta and Frontier Debt
Core promotion, Frontier retention/rejection,
Discovery Envelope expansion, and Readiness integration
```
