# AI Select Domain Authority

Read this file for AI Select behavior, terminology, scope, or current authority.

## Current authority

Final Spec v2.0 Amendments 006→001, Final Spec v2.0 where not amended, current mapping, ADRs 0027→0020 where current, carried-over ADRs, Context Amendments 006→001, ticket graph, review status, then affected code/tests/runtime/benchmarks. Surface conflicts.

## Runtime versus target

Amended v2.0 is the target; implemented v1.3 remains shipped until explicit reviewed cutovers. Parent envelopes are not implementation tasks.

## Stable domain model

- Automatic acquisition is default; Expert Recovery retains Add Observation and Continue Acquisition.
- Seed is a high-precision prior, not ownership.
- TargetScopeState separates Scope Epoch/Revision, Core, bounded seed-independent Envelope ledger, active/rejected Frontier, and Context.
- Core grows but does not shrink inside a Scope Epoch; authoritative correction/removal may rotate the epoch.
- Rejected Frontier is not Context and reopens only with new evidence/provenance.
- Frontier transitions are component-level and hysteretic.
- Structured Frontier Debt distinguishes unobserved, conflict, and promotion-pending support; raw Gaussian count is not materiality.
- q is membership tendency; s is support/knownness.
- Consensus uses immutable-Evidence pseudo-mass updates, lagged regional Reliability, and bounded deterministic convergence.
- Scope remains frozen during solve. A material post-solve delta advances scope and forces a new canonical solve before Readiness/Candidate.
- Non-converged, oscillating, stale, or scope-advanced consensus cannot publish Candidate.

## Product boundaries

Browser owns user-visible target state and Native Selection. Seed, Scope, Frontier, q/s, Reliability, Utility, and Candidate are derived state and never mutate Native Selection by themselves. Raw P/N/V and Stable Masks remain observation authority. Complete Contributor, V2AX, and leave-one-out paths remain reference/debug only.

## Historical material

Implemented v1 history lives under `docs/ai-select/history/v1/`. Context overlays are temporary and supersede conflicting root glossary definitions until controlled consolidation. EvidenceWorkingSet v1 remains shipped history and must not silently acquire Frontier semantics.
