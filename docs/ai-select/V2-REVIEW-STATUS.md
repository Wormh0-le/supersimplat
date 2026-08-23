# AI Select v2.0 Pre-implementation Review Status

Status: **active review gate — no V2 stage is agent-ready**  
Updated: 2026-08-23

## Accepted decisions

- Amendments 001–002: Expert Recovery, Seed/depth staging, seed-independent discovery.
- Amendments 003–006: deterministic q+s recurrence, regional Reliability, pseudo-mass/convergence, component Scope/Frontier Debt.
- Amendment 007: layered candidates + geometric pruning + shortlist ViewUtilityProbe.
- Amendment 008 / ADR 0029: hierarchical identities, Browser Decision Journal, deterministic budgets, exact replay/retry, Cancel/Suspend, and fresh Continue Attempt.
- Amendment 009 / ADR 0030: Publication Eligibility plus Readiness/terminal/consent matrix, explicit Ready/Limited actions, Re-Lift separation, and running-attempt Candidate application gate.

## Review order

| Step | Area | Status |
|---|---|---|
| 0–2.4 | control plane through Scope Delta/Frontier Debt | complete |
| 3 | V2F hybrid View Utility | complete at parent-decision level |
| 4 | V2G/V2I identity, budgets, Journal, replay, continuation | complete at parent-decision level |
| 5 | V2H terminal publication | complete at parent-decision level |
| 6 | V2J UI + Expert Recovery presentation | **next** |
| 7 | parent-ticket decomposition | pending |
| 8 | calibration/promotion/release ownership | pending |

## Current frontier

```text
next review item          = Q11 V2J progressive UI + Expert Recovery availability
reviewed parent direction = V2A–V2I
accepted cross-ticket     = Q4-B through Q10-C
agent-ready stages        = none
ticket in flight          = none
```

## Q10 invariants

- Publication requires an exact current converged scope-stable snapshot and complete production identity.
- Only `Ready + ready-low-gain` auto-publishes.
- Eligible forced-terminal Ready requires `Use Ready Candidate`.
- Eligible Limited requires `Use Limited Candidate`.
- Not Ready, scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, and late results cannot publish.
- Cancel never auto-publishes; a committed eligible pre-Cancel snapshot may be explicitly used afterward through a new Candidate Publication Attempt.
- Re-Lift recomputes and is not an alias for accepting an existing snapshot.
- Running acquisition temporarily blocks AI Candidate application but does not itself stale the prior Candidate.
- Candidate never self-applies Native Selection.

## Known blockers

1. V2J action priority, labels, placement, availability matrix, Candidate/current/stale presentation, and advanced diagnostics are not closed.
2. Numeric budget/cost/quality/Scope thresholds and GPU performance budgets need calibration owners.
3. Reviewed parent envelopes still require small TDD stage decomposition.
4. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph owners.
5. Context Amendments 001–009 require one controlled glossary consolidation before v2 closeout.