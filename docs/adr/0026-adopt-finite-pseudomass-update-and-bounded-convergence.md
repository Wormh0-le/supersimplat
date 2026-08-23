# ADR 0026: Adopt finite pseudo-mass q/s updates and bounded convergence

Status: accepted  
Date: 2026-08-23

## Context

ADR 0024 adopted a deterministic bounded q+s recurrence, and ADR 0025 adopted a multi-channel readout and regional Reliability residual. The recurrence still lacked an update equation, a robust residual-to-weight mapping, and a convergence contract. A direct hard P/N ratio cannot distinguish prior-dominated unknown support from mature conflict, while relative-only residual ranking can give acceptable weights when all Views are similarly poor. Reusing the prior q/s state as new Evidence would also double-count the same immutable observations across Solver Iterations.

## Decision

1. Every Solver Iteration reaggregates immutable per-View Evidence from finite, versioned pseudo-mass priors. Previous q/s is used only by the lagged Reliability readout and is never accumulated as new Evidence.
2. Update membership tendency with `(a+P)/(a+b+P+N)`, where finite prior masses are scope/provenance dependent and calibration owned.
3. Update support/knownness with the product of bounded semantic-support and visibility-support saturation functions, using `phi(x;tau)=1-exp(-x/tau)`.
4. Keep User Confirmed/manual, warm-up, insufficient-comparison-support, and other safely unscorable observations at neutral weight `1.0` with reasons.
5. Map eligible automatic-View residuals through median/MAD robust relative weighting with a non-zero floor and no sum-to-one normalization.
6. Add an absolute residual guard only after a versioned consensus-maturity gate; use the stricter of relative and absolute weights subject to the floor.
7. Require global q/s drift, high-percentile tail drift, and View-weight drift to remain below thresholds for consecutive iterations. Detect period-two oscillation explicitly and retain a finite maximum iteration count.
8. Non-convergence or oscillation remains Limited/fail-closed and cannot publish Candidate.

## Consequences

- Unknown and high-support conflict retain separate q/s semantics.
- Seed and scope priors influence initialization but cannot overpower increasing real Evidence.
- View count does not dilute all existing View weights merely because a new View is added.
- An immature consensus cannot activate the absolute guard and jointly reject newly revealing Views.
- More calibration parameters and diagnostics are required, but each belongs to a named versioned policy.
- Gradient/logit optimization remains an optional benchmark direction, not the v2 production solver.

## Follow-up

Scope Delta and Frontier Debt remain unresolved and are the next design review. Numerical values, GPU budgets, policy freeze, production identity, and release qualification require explicit later owners.
