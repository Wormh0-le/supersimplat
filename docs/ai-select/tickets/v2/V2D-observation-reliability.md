# V2D — Observation Reliability

Status: **review-required parent envelope — Q4 lagged recurrence accepted; Q5 residual contract pending; not agent-ready**

Blocked by: V2C  
Blocks: V2E

## Authority

- Final Spec v2.0 Amendment 003;
- ADR 0024;
- Amendment 002 / ADR 0023;
- Stable Mask, Participation, User Confirmed, and raw P/N/V carry-over contracts.

## Goal

Compute deterministic view-level semantic Reliability inside each bounded canonical consensus solve, using only the lagged q/s state and never requiring depth-classified Negative Evidence.

## Inputs / preconditions

- V2C q/s state from Solver Iteration `r-1`;
- reviewed consensus readout under each Included View;
- current immutable per-View single-N P/N/V;
- Stable Mask identity and provenance;
- frozen Core / Discovery Envelope / Frontier scope;
- visibility/trust support from the same-decision raster family.

## Outputs / handoff

- one versioned view-level reliability weight per Included observation and Solver Iteration;
- residual and reason diagnostics;
- warm-up, floor, exemption, and Frontier-protection state;
- deterministic reliability set consumed by V2E;
- policy identity staged under `experimental-v*` until calibration.

## Accepted recurrence invariants

- `ω^(r)` may consume only `q^(r-1), s^(r-1)`.
- Same-round q/s feedback is forbidden.
- Reliability weights semantic P/N only; raw V remains unweighted.
- Reliability never mutates Stable Mask, equals Participation, or triggers Excluded.
- User Confirmed/manual Stable Masks remain exempt from automatic downweighting.
- Newly revealed Frontier foreground must not be punished as contradiction merely because the previous consensus did not contain it.
- Contradiction in well-observed, high-support Core may receive normal penalty.
- Low-weight Views remain inspectable.
- Canonical reliability is recomputed from the complete current input set; arrival order does not define it.

## Remaining review gates before decomposition

- Q5 residual equation and readout channels;
- trusted-pixel / visibility / boundary support;
- warm-up and no-prior-consensus behavior;
- robust center/scale and degenerate-view handling;
- exact Frontier protection condition;
- non-zero floor and maximum-revision calibration;
- leave-one-out offline reference scope, if any.

## Validation families

- lag ordering and same-round feedback prohibition;
- View-order permutation equivalence;
- User Confirmed/manual exemption;
- new-Frontier true-positive adversarial fixture;
- high-support-Core contradiction fixture;
- P/N-only weighting and raw-V invariant;
- degenerate residual handling;
- deterministic identity invalidation.

## Non-goals

- No Stable Mask mutation, Participation automation, region/per-pixel product weight, classified-N production dependency, or Candidate publication.
