# AI Select Final Spec v2.0 Amendment 005 — Finite pseudo-mass update, robust Reliability, and bounded convergence

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–004  
**Decision record:** `docs/adr/0026-adopt-finite-pseudomass-update-and-bounded-convergence.md`

## 1. Purpose

Amendments 003 and 004 defined the deterministic bounded q+s recurrence and the regional Reliability readout, but left three coupled seams open:

1. how immutable P/N/V and the finite Seed/scope prior produce the next q/s state;
2. how one View residual becomes a view-level Reliability weight;
3. how the private solver determines convergence or oscillation.

This amendment adopts a finite pseudo-mass posterior, independent semantic/visibility support, robust relative Reliability with a maturity-gated absolute guard, and a multi-condition bounded convergence contract.

Runtime behavior remains the implemented v1.3 baseline until reviewed implementation stages are calibrated and explicitly promoted.

## 2. Canonical reaggregation; no iterative double counting

For one frozen canonical input, each Solver Iteration recomputes from:

- immutable per-View P/N/V Evidence;
- fixed finite prior masses bound to the frozen scope/provenance revision;
- the current iteration Reliability weights.

The previous q/s state is consumed only by the lagged readout that produces the next Reliability set. It is not added back as Evidence.

For Gaussian `i` and iteration `r`, let the versioned per-View normalization produce `P̄_ic`, `N̄_ic`, and `V̄_ic`. Then:

```text
P_i^(r) = Σ_c ω_c^(r) P̄_ic
N_i^(r) = Σ_c ω_c^(r) N̄_ic
V_i     = Σ_c V̄_ic
```

Reliability changes semantic P/N only. Source raw V remains immutable, and the policy-normalized visible mass used by the solver is not multiplied by Reliability.

A solver that repeatedly accumulates its own prior q/s output as new semantic Evidence is invalid.

## 3. Finite pseudo-mass prior

Each Gaussian receives finite prior masses:

```text
a_i >= 0  positive prior mass
b_i >= 0  negative prior mass
```

The prior is versioned and may depend on frozen scope/provenance:

- Seed/Core: finite weak-positive prior;
- Frontier or otherwise unknown plausible support: finite neutral prior;
- Context: finite weak-negative prior;
- Out-of-Scope: no semantic solve state.

No prior may be infinite or dominate increasing real Evidence. Exact strengths are calibration-owned.

## 4. Membership tendency q

The canonical update family is:

```text
q_i^(r) = (a_i + P_i^(r)) /
          (a_i + b_i + P_i^(r) + N_i^(r))
```

The denominator must be finite and strictly positive under the policy. `q` remains a membership tendency, not a calibrated probability and not Candidate membership.

This update preserves the intended distinctions:

- high P / low N -> foreground tendency;
- low P / high N -> background tendency;
- high P and high N -> high-support semantic conflict near the middle;
- little P and N -> prior-dominated unknown state, interpreted together with `s`.

## 5. Support / knownness s

Define semantic support:

```text
E_i^(r) = P_i^(r) + N_i^(r)
```

Use the bounded monotone saturation family:

```text
phi(x; tau) = 1 - exp(-x / tau)

s_i^(r) = phi(E_i^(r); tau_E) * phi(V_i; tau_V)
```

`tau_E` and `tau_V` are finite positive calibration parameters.

Consequences:

- little semantic Evidence or little realized visibility keeps `s` low;
- substantial conflicting P and N can produce `q≈0.5, s high`;
- unobserved/weak support can produce `q≈prior, s low`;
- Reliability cannot manufacture visibility because V is not weighted.

## 6. Reliability eligibility and neutral cases

The following observations retain semantic weight `1.0` and do not enter automatic robust downweighting:

- User Confirmed or manually edited Stable Masks;
- warm-up observations while no mature lagged consensus exists;
- Views with insufficient trusted comparison support;
- solves with too few eligible automatic Views for robust comparison;
- other explicitly versioned degenerate cases where Reliability cannot be estimated safely.

Each neutral case records a concrete reason. Neutral means unknown reliability, not proven correctness.

## 7. Robust relative Reliability

For eligible automatic Views with regional residual `D_c`, compute:

```text
m_D       = median(D_c)
MAD       = median(abs(D_c - m_D))
sigma_D   = max(1.4826 * MAD, sigma_min)
```

The relative weight family is:

```text
omega_rel_c = r_min + (1 - r_min) * sigmoid(
    (m_D + kappa * sigma_D - D_c) / (lambda * sigma_D)
)
```

Requirements:

- `0 < r_min <= omega_rel_c <= 1`;
- `sigma_min`, `kappa`, and `lambda` are finite calibration parameters;
- weights are not normalized to sum to one;
- adding one neutral View must not mechanically reduce every existing View's absolute semantic mass;
- degenerate robust scale is handled by the declared floor, not division by zero.

## 8. Maturity-gated absolute residual guard

Relative ranking alone cannot detect a set in which all automatic Views are similarly poor. After the consensus satisfies a versioned maturity gate, compute:

```text
omega_abs_c = r_min + (1 - r_min) * exp(-D_c / tau_abs)
```

and use:

```text
omega_c = max(r_min, min(omega_rel_c, omega_abs_c))
```

The absolute guard is disabled before all of the following versioned conditions hold:

- warm-up complete;
- minimum consensus knownness reached;
- minimum Core observation support reached;
- enough eligible automatic Views exist.

This gate prevents an immature consensus from jointly downweighting correct newly revealing observations. Exact maturity thresholds and `tau_abs` are calibration-owned.

## 9. Convergence contract

Convergence is evaluated only over a deterministic material-support set derived from the frozen solve input and policy. It must include at least:

### 9.1 Global material drift

A bounded support-weighted mean of:

```text
abs(q_i^(r) - q_i^(r-1)) + abs(s_i^(r) - s_i^(r-1))
```

### 9.2 Tail drift

A declared high percentile of per-Gaussian q/s change over the same material set. This prevents a small but important handle, boundary, or Frontier component from disappearing inside a small global mean.

### 9.3 View-weight drift

```text
max_c abs(omega_c^(r) - omega_c^(r-1))
```

### 9.4 Consecutive satisfaction

All declared metrics must remain below their thresholds for a declared number of consecutive iterations; the production baseline requires at least two consecutive satisfied iterations.

### 9.5 Period-two oscillation

If the current state is close to iteration `r-2` but materially different from iteration `r-1`, the solver records an `oscillating-period-2` diagnostic rather than treating the threshold crossing as convergence.

### 9.6 Finite maximum

`maximumSolverIterations` is finite and policy-bound. Reaching the maximum without convergence remains Limited/non-converged, preserves the prior complete Candidate, and cannot publish a replacement Candidate.

## 10. Determinism, numerical tolerance, and identity

The policy identity binds at least:

- prior family and scope/provenance mapping;
- per-View normalization policy;
- q and s transforms;
- Reliability neutral/exemption rules;
- robust relative mapping;
- absolute-guard maturity contract;
- material-set definition;
- convergence metrics, percentile, consecutive-count, oscillation rule, and maximum iterations;
- declared numerical tolerance and reduction order.

Warm/incremental execution must agree with a cold canonical full solve within the declared tolerance. Material disagreement fails closed.

## 11. Authority and failure boundaries

This amendment does not change the authority hierarchy:

- Stable Masks and raw Evidence remain immutable observation truth;
- q/s and Reliability remain Companion-local derived state;
- raw V remains realized visibility truth;
- non-converged or failed private iterations do not replace the previous complete Consensus Revision;
- Candidate and Native Selection authority remain unchanged.

## 12. Remaining review gates

Before V2C/V2D/V2E decomposition, review must still close:

- Scope Delta promotion, retention, rejection, and Discovery Envelope expansion;
- Frontier Debt representation and its use by Lift Readiness;
- exact material-set and scope-delta identities;
- GPU/CPU memory layout and performance budget;
- calibration, policy-freeze, production-promotion, cutover, and release-qualification ownership.

## 13. Non-goals

This amendment does not:

- choose production numeric thresholds;
- adopt per-Gaussian gradient/logit optimization as the production solver;
- normalize View weights to sum to one;
- make q a calibrated probability;
- change the current one-channel Negative Mass contract;
- publish q/s, residual maps, or Reliability as Browser authority;
- modify Stable Mask, Participation, Candidate, Native Selection, or EditHistory authority.
