# V2H — Two-gate terminal Candidate publication and explicit consent

Status: **reviewed parent envelope — awaiting stage decomposition; not agent-ready**

Blocked by: V2E, V2G, V2I  
Blocks: V2J

## Authority

Final Spec Amendment 009; ADR 0030; Amendments 003–008; carried-over atomic production Candidate publication.

## Goal

Implement a complete fail-closed mapping from Candidate Publication Snapshot eligibility plus Readiness and terminal outcome to automatic publication, explicit Ready/Limited consent, prior-Candidate preservation, and recovery.

## Accepted contract

- A hard Publication Eligibility Gate binds exact current Stable observations, production Evidence, converged Consensus, current Scope with no pending material delta, readiness, terminal outcome, and production identity.
- Only eligible `Ready + ready-low-gain` auto-publishes.
- Eligible Ready at budget/no-feasible/failure/Cancel terminals requires `Use Ready Candidate`.
- Eligible Limited requires `Use Limited Candidate`.
- Not Ready never publishes.
- scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, and late results never publish.
- Explicit Use actions publish the frozen snapshot through a new idempotent Candidate Publication Attempt and do not recompute.
- Re-Lift recomputes exact current inputs; Ready may publish from the explicit recomputation, Limited still requires explicit Use.
- Prior Candidate is preserved until atomic replacement or staleness.
- Running acquisition temporarily blocks Candidate application but does not itself stale the prior Candidate.
- Candidate never self-applies Native Selection.

## Later decomposition must own

- Publication Snapshot and CandidatePublicationAttempt schemas/digests;
- complete matrix evaluator;
- automatic and explicit publication orchestration;
- Re-Lift compatibility migration;
- Cancel/pre-Cancel snapshot handling;
- prior-Candidate application gate integration;
- exact status/reason payload consumed by V2J.

## Validation families

Complete matrix; eligibility rejection; auto Ready-low-gain; explicit Ready/Limited without recompute; Not Ready/incompatible refusal; Cancel snapshots; Re-Lift Ready/Limited; idempotent publication replay; atomic replacement; prior Candidate and running application gate.

## Non-goals

No UI layout, Native Selection automation, quality threshold calibration, or acquisition restart.