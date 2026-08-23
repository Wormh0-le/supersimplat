# AI Select Domain Authority

Read this file for AI Select behavior, terminology, scope, or current authority.

## Current authority

Final Spec v2.0 Amendments 005→001, Final Spec v2.0 where not amended, current mapping, ADRs 0026→0020 where current, carried-over ADRs, context overlays 005→001, ticket graph, review status, then affected code/tests/runtime/benchmarks. Surface conflicts.

## Runtime versus target

Amended v2.0 is the target; implemented v1.3 remains shipped until explicit reviewed cutovers. Parent envelopes are not implementation tasks.

## Stable domain model

- Automatic acquisition is default; Expert Recovery retains Add Observation and Continue Acquisition.
- Seed is a high-precision prior, not ownership.
- Core, seed-independent Discovery Envelope, and reversible Frontier are distinct.
- Core Coverage and Frontier Debt are distinct.
- q is membership tendency, not calibrated probability or Candidate.
- s is support/knownness and separates unknown from conflict.
- q/s uses finite pseudo-mass priors and immutable-Evidence reaggregation.
- Reliability may downweight eligible automatic Views, but User Confirmed/manual and safely unscorable cases remain neutral `1.0`.
- Robust relative weights are independent rather than sum-normalized; absolute guarding is maturity-gated.
- Convergence includes global, tail, and View-weight stability plus oscillation detection.
- Scope stays frozen during a solve; Scope Delta commits afterward.
- Non-converged consensus cannot establish Ready or publish Candidate.

## Product boundaries

Browser owns user-visible target state and Native Selection. Seed, Frontier, q/s, Reliability, Utility, and Candidate are derived state and never mutate Native Selection by themselves. Raw P/N/V and Stable Masks remain observation authority. Complete Contributor and leave-one-out paths remain reference/debug only.

## Historical material

Implemented v1 history lives under `docs/ai-select/history/v1/`. Context overlays are temporary and supersede conflicting root glossary definitions until controlled consolidation.
