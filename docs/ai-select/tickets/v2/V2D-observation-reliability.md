# V2D — Observation Reliability

Status: **review-required parent envelope — Q4/Q5/Q6 accepted; calibration/decomposition pending; not agent-ready**

Blocked by: V2C  
Blocks: V2E

## Authority

- Final Spec Amendments 003–005;
- ADRs 0024–0026;
- Stable Mask, Participation, User Confirmed, and immutable P/N/V contracts.

## Goal

Compute deterministic view-level semantic Reliability inside each canonical solve from lagged q/s readouts and trusted regional residuals, without changing raw visibility or requiring depth-classified Negative Evidence.

## Accepted contract

- Reliability iteration `r` consumes q/s from iteration `r-1` only.
- Production uses multi-channel same-decision readout and region-normalized positive-interior / negative-ring / low-weight-boundary residuals; Far Neutral is excluded.
- Positive Frontier Protection is bounded and asymmetric; negative-ring conflict has no symmetric Frontier exemption.
- User Confirmed/manual observations retain weight `1.0`.
- Warm-up, insufficient comparison support, immature consensus, too few eligible automatic Views, and declared degenerate cases use neutral weight `1.0` with reasons.
- Eligible automatic Views use median/MAD robust relative weighting with a non-zero floor and no sum-to-one normalization.
- After a versioned maturity gate, an absolute residual guard may further cap Reliability.
- Reliability affects semantic P/N only; source raw V and policy-normalized visibility remain unweighted by Reliability.
- Low-weight Views remain inspectable and Reliability never mutates Stable Mask, Participation, or Candidate.
- Leave-one-out consensus is offline/reference-only and nonblocking.

## Remaining review/decomposition gates

- numeric calibration of region coefficients, trusted support, warm-up, `r_min`, robust scale, sigmoid parameters, maturity gate, and absolute guard;
- exact diagnostic/reason schema and robust eligible-View set;
- GPU/reference readout cost and LOO benchmark owner;
- policy freeze and production-identity owner.

## Validation families

- lag/same-round prohibition;
- View-order permutation equivalence;
- User Confirmed/manual exemption;
- insufficient-support neutral reason;
- new-Frontier true-positive adversarial fixture;
- high-knownness Core contradiction fixture;
- all-Views-poor absolute-guard fixture after maturity;
- immature-consensus guard-disabled fixture;
- non-zero floor and no sum-normalization;
- P/N-only weighting and raw-V invariant;
- full-set versus LOO reference gap benchmark.

## Non-goals

No Stable Mask mutation, Participation automation, per-pixel product weight, classified-N production dependency, or Candidate publication.
