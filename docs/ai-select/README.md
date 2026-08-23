# AI Select Documentation

## Current control plane

```text
Final Spec v2.0 Amendments 006 → 001
→ Final Spec v2.0
→ ADR 0027 → 0020
→ CURRENT-TICKET-SPEC-MAPPING.md
→ V2-REVIEW-STATUS.md
→ TICKET-GRAPH-V2.md
→ tickets/v2/
```

No V2 stage is agent-ready. Runtime remains implemented v1.3.

## Accepted architecture

```text
Conservative Seed
→ component TargetScopeState
   Core + bounded Envelope ledger + reversible Frontier
→ deterministic bounded q+s Consensus
→ regional Reliability and immutable-Evidence update
→ converged component Scope Delta
   ├─ empty: structured Frontier Debt → Readiness/Utility
   └─ material: new Scope Revision → mandatory new solve
→ View Utility and bounded acquisition
```

Core is monotonic inside a Scope Epoch. Rejected Frontier is not Context. Scope-advanced/non-converged output cannot publish Candidate. EvidenceWorkingSet v1 remains the shipped contract; v2 role semantics require an explicit migration.

## Documentation lifecycle

Amendments and later ADRs supersede conflicting clauses without rewriting accepted history. Implemented v1 snapshots stay under `history/v1/`. Unimplemented superseded envelope files are deleted and replaced. Context overlays 006–001 must be folded into root `CONTEXT.md` only during one controlled cleanup and then removed.

## Next review

```text
Q8 — View Utility
prediction probe, candidate-pool bounds,
deterministic cost, exploration, and realized-gain calibration
```
