# ADR 0027: Component-level Target Scope, structured Frontier Debt, and mandatory re-solve

Status: accepted  
Date: 2026-08-23

## Context

The accepted v2 architecture separates Conservative Seed, Core Target, Discovery Envelope, and Frontier, then solves q+s under frozen scope. It did not define safe Core promotion, reversible rejection, completeness debt, or whether a Candidate could use a Consensus solved before a scope change. Per-Gaussian thresholds and a single debt scalar would be unstable under non-uniform 3DGS density and would let early scope errors influence Coverage, Utility, and publication.

## Decision

1. Maintain a Companion-local `TargetScopeState` with Scope Epoch, Scope Revision, Core, bounded Envelope ledger, component-level active/rejected/reopened Frontier, Context, provenance, and policy identity.
2. Core is monotonic inside a Scope Epoch. Authoritative correction/removal of existing evidence or incompatible target identity rotates or invalidates the epoch.
3. Promotion, retention, rejection, and reopening are component-level, hysteretic, diagnosable, and based on converged q/s plus raw visibility and observation provenance.
4. Rejected Frontier is not Context. Reopening requires new authoritative evidence or discovery provenance.
5. A material Scope Delta commits after a converged solve and always requires a new canonical solve. Readiness/Candidate publication cannot use the pre-delta result.
6. Scope churn has a finite per-attempt revision budget and fails Limited/closed when exhausted.
7. Frontier Debt remains structured by component and distinguishes unobserved, conflict, and promotion-pending debt. Raw Gaussian count is not a valid materiality measure.
8. A future EvidenceWorkingSet v2 projects Core, active Frontier, and required Context while preserving roles and binding exact scope identity. The v1 schema is not silently reinterpreted.

## Consequences

- The planner can recover support omitted by Seed without allowing unstable per-Gaussian scope flicker.
- Candidate, Readiness, and Coverage always bind the scope under which consensus was solved.
- Difficult scenes may require extra canonical solves after scope growth.
- Componentization, lineage, debt calibration, scope journals, and a Working Set schema migration add implementation and testing cost.
- V2F consumes structured Frontier Debt; V2G/V2I own scope-revision budgeting/orchestration; V2H owns terminal consent.

## Rejected alternatives

- Per-Gaussian promotion/rejection with one scalar Debt: density-sensitive, fragmented, and unsafe for monotonic Core.
- Freezing scope for the whole acquisition loop: simpler but preserves Seed lock and prevents iterative acquisition from using discovered support.
- Treating rejected Frontier as Context: creates a negative prior from an uncertain early decision and amplifies confirmation bias.
