# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

Read Final Spec Amendments 008→001, then Final Spec v2.0 where not amended; this mapping; ADRs 0029→0020 where current; carried-over nonconflicting ADRs; context overlays 008→001 then root `CONTEXT.md`; graph/review/tickets; affected code/tests/runtime/benchmarks.

Runtime remains implemented v1.3. Accepted design is not implementation readiness.

## Planning status

```text
normative target          = Final Spec v2.0 + Amendments 001–008
shipped runtime baseline  = implemented Final Spec v1.3
planning phase            = pre-implementation review
reviewed parent direction = V2A–V2G and V2I
accepted cross-ticket     = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C, Q9-B
agent-ready V2 stages     = none
next review item          = Q10 Readiness × Terminal Outcome publication matrix
```

## Accepted architecture summary

- automation-default with terminal Expert Recovery;
- S0/S1 Seed shadow evaluation and seed-independent component Frontier;
- deterministic bounded q+s Consensus with regional Reliability;
- finite pseudo-mass update, robust weights, bounded convergence;
- component TargetScopeState, structured Frontier Debt, mandatory re-solve after material Scope Delta;
- finite layered candidates with geometric pruning and shortlist raster probes;
- Browser-owned hierarchical Series/Attempt/Iteration identity and append-only Decision Journal;
- deterministic multi-budget ledger; wall-clock never changes canonical ranking;
- exact replay/fresh retry distinction, fail-closed Cancel/Suspend, and fresh Continue Attempt under a Series cap.

## Current ticket lifecycle

| Ticket | Scope | Lifecycle | Remaining gate |
|---|---|---|---|
| V2A | projected depth/CWED/V2AX | reviewed-awaiting-decomposition | stage split, calibration/GPU gates |
| V2B | Seed + TargetScopeState foundation | reviewed-awaiting-decomposition | stage split and shadow benchmark owner |
| V2C | q+s solve/readout | reviewed-awaiting-decomposition | memory/reference/performance decomposition |
| V2D | regional Reliability | reviewed-awaiting-decomposition | calibration/LOO owner and stage split |
| V2E | weighted update/convergence/Scope Delta | reviewed-awaiting-decomposition | stage split and calibration |
| V2F | hybrid View Utility | reviewed-awaiting-decomposition | stage split and predicted/realized calibration |
| V2G | deterministic budgets/outcomes/termination | reviewed-awaiting-decomposition | numeric policy calibration; Q10 publication mapping |
| V2H | terminal Candidate publication | review-required / next | complete Readiness × terminal outcome matrix and Limited consent |
| V2I | Browser Journal/identity/replay/orchestration | reviewed-awaiting-decomposition | stage split, endpoint schemas, persistence boundary |
| V2J | acquisition UI + Expert Recovery | review-required | presentation/availability after Q10 |

## Documentation lifecycle

Current authority is Amendments 001–008 and ADRs through 0029. Implemented v1 snapshots remain under `history/v1/`. Superseded unimplemented planning files are deleted rather than archived. Context overlays remain temporary until one controlled glossary consolidation.

## Implementation gate

An exact V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark it `agent-ready`.
