# V2E — Weighted aggregation, q/s update, and two-phase target-scope revision

Status: **review-required parent envelope — Q4 recurrence/order model accepted; transforms and Q5 inputs pending; not agent-ready**

Blocked by: V2B, V2D  
Blocks: V2F, V2H

## Authority

- Final Spec v2.0 Amendment 003;
- ADR 0024;
- Amendment 002 / ADR 0023;
- current immutable P/N/V and Lift Readiness seams.

## Goal

Generalize current one-shot aggregation into the deterministic aggregation/update step of the bounded consensus recurrence, preserving single-N P/N/V, weighting semantic P/N only, and committing Core/Frontier changes only after the solve.

## Inputs / preconditions

- immutable per-View `positiveMass`, `negativeMass`, `visibleMass`;
- iteration Reliability weights from V2D;
- q/s prior state and frozen scope revision from V2C;
- Core / Discovery Envelope / Frontier state from V2B;
- exact policy and canonical input identities.

## Outputs / handoff

- iteration weighted aggregate with raw V preserved;
- updated q/s state for the next Solver Iteration;
- final Selected/Rejected/Uncertain diagnostics after bounded solve;
- Core Observation Coverage and separate Frontier Debt inputs;
- proposed post-solve Scope Delta;
- exact revision/policy identities;
- incremental implementation equivalent to cold full recomputation.

## Accepted recurrence and scope invariants

- Aggregate iteration `r` consumes Reliability `ω^(r)` derived from lagged q/s.
- Missing, unusable, or excluded observations remain unobserved, never negative.
- Current production keeps one Negative Mass channel.
- Reliability changes P/N only; raw V is unchanged.
- Core, Envelope, and Frontier are frozen for every Solver Iteration in one revision.
- Core promotion, Frontier rejection/retention, and Envelope expansion are proposed only after final convergence status.
- Scope Delta commits atomically after Consensus Revision and cannot recursively retrigger the same solve.
- Frontier remains reversible; Core is monotonic only inside the stable input revision.
- Arrival order and cache history do not change canonical output.
- Non-converged output cannot establish Ready or publish Candidate.
- Lift Readiness remains the publication authority.

## Remaining review gates before decomposition

- exact q/s update transform and support calculation;
- Q5 readout/residual inputs consumed by Reliability;
- convergence metric and numerical tolerance;
- Scope Delta promotion/rejection thresholds;
- Frontier Debt representation;
- incremental cache decomposition and canonical equivalence checks;
- policy identity and later production-promotion owner.

## Validation families

- incremental/warm versus cold canonical equivalence;
- input permutation equivalence;
- raw-V unchanged under Reliability weighting;
- q/s unknown-versus-conflict fixtures;
- scope freeze and post-solve two-phase commit;
- Core promotion and Frontier rejection adversarial fixtures;
- non-convergence and stale dependency handling;
- production identity fail-closed tests.

## Non-goals

- No classified-N production migration, View Utility scoring, terminal Candidate publication, or Native Selection mutation.
