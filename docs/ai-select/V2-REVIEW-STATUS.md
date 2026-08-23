# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendments 001–002: Expert Recovery, Seed/depth staging, seed-independent discovery.
- Amendments 003–006: deterministic q+s recurrence, regional Reliability, pseudo-mass/convergence, component Scope/Frontier Debt.
- Amendment 007: layered candidates + geometric pruning + shortlist ViewUtilityProbe.
- Amendment 008 / ADR 0029: hierarchical Series/Attempt/Iteration identities, Browser Decision Journal, deterministic budgets, exact replay/retry, Cancel/Suspend, and fresh Continue Attempt.

## Review order

| Step | Area | Status |
|---|---|---|
| 0–2.4 | control plane through Scope Delta/Frontier Debt | complete |
| 3 | V2F hybrid View Utility | complete at parent-decision level |
| 4 | V2G/V2I identity, budgets, Journal, replay, continuation | complete at parent-decision level |
| 5 | V2H terminal publication | **next** |
| 6 | V2J UI + Expert Recovery presentation | pending |
| 7 | parent-ticket decomposition | pending |
| 8 | calibration/promotion/release ownership | pending |

## Current frontier

```text
next review item          = Q10 Readiness × Terminal Outcome publication matrix
reviewed parent direction = V2A–V2G, V2I
accepted cross-ticket     = Q4-B through Q9-B
agent-ready stages        = none
ticket in flight          = none
```

## Q9 invariants

- Do not collapse existing endpoint attempts into one loop ID.
- Browser owns the append-only Decision Journal and product action sequence.
- Same-attempt replay never reranks or debits budget again.
- Fresh retry uses a new endpoint attempt ID and consumes declared budgets.
- Failed work is free only for Successful Observation Budget.
- Wall-clock/cache state cannot change canonical candidate ranking.
- Cancel closes publication authority immediately; late results are discarded.
- Exact resume uses the same Attempt only from a compatible journal boundary.
- Continue Acquisition is a fresh Attempt with new per-Attempt allowances and shared Series caps.
- No Companion-autonomous acquisition session.

## Known blockers

1. Readiness × terminal outcome → Candidate publication and explicit Limited consent are not closed.
2. V2J labels, availability, Candidate-while-running presentation, and recovery affordances remain open.
3. Numeric budget/cost/threshold values and GPU performance budgets need calibration owners.
4. Reviewed parent envelopes still require small TDD stage decomposition.
5. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph owners.
