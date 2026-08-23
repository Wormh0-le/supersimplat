# V2D — Observation Reliability

Status: **review-required parent envelope; not agent-ready**

Blocked by: V2C  
Blocks: V2E

## Authority

- Final Spec v2.0 §7.2 as amended by Amendment 002;
- ADR 0023;
- Stable Mask, Participation, User Confirmed, and raw P/N/V carry-over contracts.

## Goal

Compute versioned view-level semantic reliability from the residual between a lagged provisional-consensus soft mask and each Included Stable Mask, without requiring depth-classified Negative Evidence.

## Inputs / preconditions

- V2C consensus state and reviewed soft-mask readout;
- current immutable per-View P/N/V artifact with one production `negativeMass`;
- Stable Mask identity and provenance;
- same-decision visibility/transmittance trust information;
- Discovery Frontier context sufficient to distinguish newly revealed support from contradiction in well-observed Core.

## Outputs / handoff

- versioned view-level weight per Included observation;
- visibility-gated residual diagnostics;
- lag/warm-up/floor/frontier-protection revision state;
- policy identity staged under `experimental-v*` until calibration.

## Required invariants

- Reliability weights semantic P/N only; raw V remains the realized-visibility source.
- Reliability never mutates a Stable Mask, equals Participation, or triggers Excluded by itself.
- User Confirmed/manual Stable Masks are exempt from automatic downweighting.
- Newly revealed Frontier foreground is protected from confirmation-bias punishment.
- Contradiction in well-observed high-confidence Core may receive normal penalty.
- Low-weight Views remain inspectable with concrete reasons.
- Depth-classified N may be observed by V2AX diagnostics later but is not a prerequisite or product input.

## Review gates before decomposition

- exact consensus state consumed at revision `k-1`;
- residual equation and visibility/boundary support;
- initialization/warm-up and no-prior-consensus behavior;
- Frontier protection definition;
- robust center/scale and degenerate-view handling;
- bounded revision/convergence ownership shared with V2C/V2E.

## Validation families

- lag ordering and same-round feedback prohibition;
- User Confirmed/manual exemption;
- new-Frontier true-positive adversarial fixture;
- high-confidence-Core contradiction fixture;
- P/N-only weighting and raw-V invariant;
- deterministic replay and identity invalidation.

## Non-goals

- No Stable Mask mutation, Participation automation, region/per-pixel weight, or production classified-N dependency.
