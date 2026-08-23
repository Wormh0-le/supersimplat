# AI Select Context Amendment 005 — q/s update and convergence

Status: current vocabulary overlay  
Authority: Final Spec Amendment 005 / ADR 0026

This file temporarily overrides conflicting or underspecified root `CONTEXT.md` terms until the controlled glossary consolidation.

## Finite Pseudo-mass Prior

A versioned pair of finite positive/negative prior masses used to initialize or regularize one Gaussian's consensus update. It is scope/provenance dependent, is not Evidence, and must yield to increasing real Evidence.

## Canonical Reaggregation

The rule that each Solver Iteration recomputes semantic aggregates from immutable per-View Evidence, fixed finite priors, and that iteration's Reliability weights. Previous q/s is not re-added as Evidence.

## Membership Tendency q

The finite pseudo-mass posterior ratio `(a+P)/(a+b+P+N)`. It is continuous derived state, not a calibrated probability, Candidate membership, or ownership.

## Support / Knownness s

A bounded derived measure requiring both semantic Evidence and realized visibility. Low `s` means weakly known; high `s` with `q≈0.5` means material conflict.

## Neutral Reliability

View weight `1.0` used when automatic downweighting is not authoritative or safely computable, including User Confirmed/manual observations, warm-up, and insufficient comparison support. Neutral is not proof of correctness.

## Robust Relative Reliability

An independent per-View weight in `[r_min,1]` derived from a median/MAD residual comparison. Weights are not normalized to sum to one.

## Absolute Residual Guard

A maturity-gated upper bound on Reliability derived from the absolute residual. It is disabled while consensus maturity is insufficient to avoid collective confirmation bias.

## Material Drift

Deterministic q/s change evaluated over policy-defined materially supported Gaussians. Convergence includes global mean drift, high-percentile tail drift, and View-weight drift.

## Period-two Oscillation

A non-converged solver pattern in which iteration `r` returns near `r-2` while remaining materially different from `r-1`. It is diagnosed explicitly and cannot publish Candidate.
