# AI Select Domain Authority

Read this file for AI Select behavior, terminology, scope, or current authority.

## Current authority

Final Spec v2.0 Amendments 007→001, Final Spec v2.0 where not amended, current mapping, ADRs 0028→0020 where current, carried-over ADRs, Context Amendments 007→001, ticket graph, review status, then affected code/tests/runtime/benchmarks. Surface conflicts.

## Runtime versus target

Amended v2.0 is the target; implemented v1.3 remains shipped until explicit reviewed cutovers. Parent envelopes are not implementation tasks.

## Stable domain model

- Automatic acquisition is default; Expert Recovery retains Add Observation and Continue Acquisition.
- Seed is a high-precision prior, not ownership.
- Core, seed-independent Discovery Envelope, reversible Frontier, and Context are distinct.
- q is membership tendency; s is support/knownness.
- Scope is component-level; Frontier Debt distinguishes unobserved, conflict, and promotion-pending work.
- View Utility is prospective and distinct from Coverage, Debt, Readiness, and Candidate.
- ViewUtilityProbe is a low-resolution planning heuristic over a deterministic shortlist, not an observation or authority.
- Deterministic cost units may affect ranking; transient wall-clock/GPU/cache state may not.

## Product boundaries

Browser owns user-visible target state and Native Selection. Seed, Frontier, q/s, Reliability, View Utility, probe output, and Candidate are derived state and never mutate Native Selection by themselves. Raw P/N/V and Stable Masks remain observation authority. Complete Contributor, classified N, leave-one-out Reliability, fixed-four, and full-render-all-candidates remain reference/benchmark paths.

## Historical material

Implemented v1 history lives under `docs/ai-select/history/v1/`. Context overlays are temporary and supersede conflicting root glossary definitions until controlled consolidation.
