# AI Select Domain Authority

Read this file when work changes AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Current authority

Read sources in this order:

1. Final Spec v2.0 Amendment 003
2. Final Spec v2.0 Amendment 002
3. Final Spec v2.0 Amendment 001
4. Final Spec v2.0 where not amended
5. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
6. ADR 0024, ADR 0023, ADR 0022, residual ADR 0021, ADR 0020
7. carried-over nonconflicting ADRs
8. context amendments 003/002/001, then root `CONTEXT.md`
9. `docs/ai-select/TICKET-GRAPH-V2.md`
10. `docs/ai-select/V2-REVIEW-STATUS.md`
11. affected ticket, implementation, tests, runtime declarations, and benchmark records

Surface conflicts rather than silently choosing one source.

## Runtime versus target

- Amended Final Spec v2.0 is the target.
- Shipped behavior remains implemented v1.3 until explicit reviewed cutovers.
- Parent envelopes and accepted cross-ticket decisions are not agent-ready implementation tasks.

## Product orientation

- Automatic acquisition is default.
- Expert Recovery is secondary and available only when no loop runs and the target is active.
- Recovery retains Add Observation and Continue Acquisition.
- Recovery never bypasses Stable Mask, Participation, Direct Evidence, Candidate identity, or explicit Native operations.

## Seed and discovery vocabulary

- Conservative Seed is a high-precision bootstrap prior, not ownership.
- S0 and S1 are shadow variants; no production winner is assumed.
- Core Target is high-confidence support for Core Coverage.
- Discovery Envelope is seed-independent potential support.
- Discovery Frontier is reversible and cannot directly become Candidate.
- Frontier Debt is distinct from Core Observation Coverage.
- CWED is an internal statistic, not authoritative surface depth.
- Depth-classified Negative Evidence is experimental; current production has one N channel.

## Consensus vocabulary

- `q` is continuous membership tendency, not a calibrated probability or Candidate membership.
- `s` is support/knownness and distinguishes unknown from high-support conflict.
- A Solver Iteration is private; a Consensus Revision is one atomic canonical result.
- The canonical full solve is deterministic, bounded, and independent of View arrival order.
- Scope is frozen during a solve; Scope Delta commits only afterward.
- Non-converged consensus cannot establish Ready or publish Candidate.

## Product boundaries

AI Select remains a native SuperSplat Selection Tool. Browser owns user-visible target state and Native Selection. Seed, Frontier, consensus, reliability, View Utility, and Candidate are derived state and do not mutate Native Selection by themselves. Complete Contributor remains reference/debug only.

## Historical material

Implemented v1 history lives under `docs/ai-select/history/v1/`. Root glossary terms conflicting with current context amendments are deprecated pending consolidation.
