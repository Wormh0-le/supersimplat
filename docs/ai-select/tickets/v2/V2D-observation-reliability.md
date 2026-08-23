# V2D — Observation Reliability

Status: **review-required parent envelope — Q4 lagged recurrence and Q5 residual baseline accepted; robust normalization/calibration pending; not agent-ready**

Blocked by: V2C  
Blocks: V2E

## Authority

- Final Spec v2.0 Amendments 004 and 003;
- ADR 0025 and ADR 0024;
- Amendment 002 / ADR 0023;
- Stable Mask, Participation, User Confirmed, and raw P/N/V carry-over contracts.

## Goal

Compute deterministic view-level semantic Reliability inside each bounded canonical consensus solve, using only the lagged q/s readout, trusted region-normalized disagreement, and current single-N P/N/V. Maintain a nonblocking leave-one-out reference benchmark for self-influence measurement.

## Inputs / preconditions

- V2C q/s state from Solver Iteration `r-1`;
- V2C readout maps `P`, `K`, `C`, `F`, and semantic-scope validity;
- current immutable per-View single-N P/N/V;
- Stable Mask identity, Evidence-region partition, and provenance;
- frozen Core / Discovery Envelope / Frontier / Context scope.

## Outputs / handoff

- one versioned view-level reliability weight per Included observation and Solver Iteration;
- separately normalized positive-interior, negative-ring, and boundary residual diagnostics;
- trusted comparison support and concrete degenerate reasons;
- warm-up, floor, exemption, and Positive Frontier Protection state;
- deterministic reliability set consumed by V2E;
- nonblocking leave-one-out reference benchmark records;
- policy identity staged under `experimental-v*` until calibration.

## Accepted recurrence invariants

- `ω^(r)` may consume only `q^(r-1), s^(r-1)`.
- Same-round q/s feedback is forbidden.
- Reliability weights semantic P/N only; raw V remains unweighted.
- Reliability never mutates Stable Mask, equals Participation, or triggers Excluded.
- User Confirmed/manual Stable Masks remain fixed at semantic weight `1.0`.
- Canonical reliability is recomputed from the complete current input set; arrival order does not define it.

## Accepted residual contract

- Reliability reuses Strong Positive Interior, Local Negative Context Ring, Boundary Band, and Far Neutral Stable Mask regions.
- Far Neutral never enters the residual.
- Trusted pixels require valid semantic-scope mass and sufficient knownness under the versioned policy.
- Insufficient trusted comparison support returns neutral weight `1.0` with reason `insufficient-comparison-support`.
- Positive-interior disagreement receives bounded asymmetric Frontier/unknown protection.
- Negative-ring disagreement receives no symmetric Frontier exemption.
- Boundary residual is separately normalized and low-weight or diagnostic-only.
- Region means are combined into one view-level residual; raw pixel counts, frame resolution, or ring area cannot dominate by themselves.
- Reliability remains view-level; per-pixel maps are internal diagnostics, not product weights.

## Leave-one-out reference

For offline/reference evaluation, one View may be scored against consensus recomputed without that View. The reference measures self-influence gap, reliability ranking changes, Candidate quality, latency, and memory. It is nonblocking and cannot enter the production Runtime Profile without a later accepted promotion decision.

## Remaining review gates before decomposition

- robust residual-to-weight mapping across Views, including median/MAD or alternative normalization;
- warm-up count and no-prior-consensus behavior;
- non-zero floor and degenerate robust-scale handling;
- exact valid-mass/knownness and Frontier-protection calibration parameters;
- maximum-revision/calibration ownership shared with V2C/V2E;
- leave-one-out fixture set and promotion rejection/acceptance criteria.

## Validation families

- lag ordering and same-round feedback prohibition;
- View-order permutation equivalence;
- User Confirmed/manual exemption;
- positive Frontier true-discovery adversarial fixture;
- high-support-Core contradiction fixture;
- negative-ring conflict without symmetric exemption;
- boundary/far-neutral isolation;
- insufficient-comparison-support neutral behavior;
- P/N-only weighting and raw-V invariant;
- production versus leave-one-out self-influence comparison;
- deterministic identity invalidation.

## Non-goals

- No Stable Mask mutation, Participation automation, region/per-pixel product weight, classified-N production dependency, production leave-one-out path, or Candidate publication.
