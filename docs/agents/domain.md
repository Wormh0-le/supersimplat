# AI Select Domain Authority

Read this file when work changes AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Current authority

Read sources in this order:

1. Final Spec v2.0 Amendment 004
2. Amendment 003
3. Amendment 002
4. Amendment 001
5. Final Spec v2.0 where not amended
6. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
7. ADR 0025, ADR 0024, ADR 0023, ADR 0022, residual ADR 0021, ADR 0020
8. carried-over nonconflicting ADRs
9. context amendments 004/003/002/001, then root `CONTEXT.md`
10. `docs/ai-select/TICKET-GRAPH-V2.md`
11. `docs/ai-select/V2-REVIEW-STATUS.md`
12. affected ticket, implementation, tests, runtime declarations, and benchmark records

Surface conflicts rather than silently choosing one source.

## Runtime versus target

- Amended Final Spec v2.0 is the target.
- Shipped behavior remains implemented v1.3 until explicit reviewed cutovers.
- Parent envelopes and accepted cross-ticket decisions are not agent-ready implementation tasks.

## Product orientation

- Automatic acquisition is default.
- Expert Recovery is secondary after the loop stops.
- Recovery retains Add Observation and Continue Acquisition.
- Recovery never bypasses Stable Mask, Participation, Direct Evidence, Candidate identity, or Native operations.

## Seed and discovery vocabulary

- Conservative Seed is a high-precision bootstrap prior, not ownership.
- S0 and S1 are shadow variants; no production winner is assumed.
- Core Target is high-confidence support for Core Coverage.
- Discovery Envelope is seed-independent potential support.
- Discovery Frontier is reversible and cannot directly become Candidate.
- Frontier Debt is distinct from Core Observation Coverage.
- CWED is internal, not authoritative surface depth.
- Classified Negative Evidence is experimental.

## Consensus and Reliability vocabulary

- `q` is membership tendency, not calibrated probability or Candidate membership.
- `s` is support/knownness and separates unknown from high-support conflict.
- a Solver Iteration is private; a Consensus Revision is one atomic canonical result.
- Support-aware Membership is `q̃=0.5+s(q-0.5)`.
- Consensus Readout is Companion-internal same-decision semantic projection, not visibility truth.
- Trusted Comparison Support requires valid semantic-scope mass and knownness.
- Positive Frontier Protection is bounded and asymmetric.
- Regional Reliability excludes Far Neutral and normalizes positive/negative/boundary regions separately.
- leave-one-out Reliability is reference-only unless later promoted.
- non-converged consensus cannot establish Ready or Candidate.

## Product boundaries

AI Select remains a native SuperSplat Selection Tool. Browser owns user-visible target state and Native Selection. Seed, Frontier, consensus, Reliability, View Utility, and Candidate are derived state and do not mutate Native Selection by themselves. Complete Contributor remains reference/debug only.

## Historical material

Implemented v1 history lives under `docs/ai-select/history/v1/`. Root glossary terms conflicting with current context amendments are deprecated pending consolidation.
