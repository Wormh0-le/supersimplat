# V2E — Weighted aggregation, q/s update, convergence, and two-phase scope revision

Status: **review-required parent envelope — Q4/Q5/Q6 accepted; Q7 Scope Delta pending; not agent-ready**

Blocked by: V2B, V2D  
Blocks: V2F, V2H

## Authority

- Final Spec Amendments 002–005;
- ADRs 0023–0026;
- immutable single-N P/N/V and Lift Readiness contracts.

## Goal

Generalize one-shot aggregation into the deterministic aggregation/update step of the bounded recurrence, preserving immutable Evidence and raw visibility while producing q/s, convergence diagnostics, and a post-solve target-scope proposal.

## Accepted update contract

For each iteration, use versioned per-View normalized masses:

```text
P_i = sum_c omega_c * Pbar_ic
N_i = sum_c omega_c * Nbar_ic
V_i = sum_c Vbar_ic

q_i = (a_i + P_i) / (a_i + b_i + P_i + N_i)
E_i = P_i + N_i
s_i = (1 - exp(-E_i/tau_E)) * (1 - exp(-V_i/tau_V))
```

- finite priors are fixed by frozen scope/provenance and yield to real Evidence;
- every iteration reaggregates immutable Evidence and never adds previous q/s as Evidence;
- current production retains one Negative Mass channel;
- Reliability changes P/N only; V is not multiplied by Reliability;
- missing/unusable/excluded observations remain unobserved, never negative;
- canonical convergence uses material mean drift, high-percentile tail drift, View-weight drift, consecutive satisfaction, period-two detection, and a finite maximum;
- Core/Envelope/Frontier are frozen during the solve;
- Scope Delta is proposed only after the final converged state and commits separately;
- non-converged/oscillating results cannot establish Ready or publish Candidate;
- warm/incremental output must equal cold full recomputation within declared tolerance.

## Remaining review gates before decomposition

- Q7 Core promotion, Frontier retention/rejection, Envelope expansion, and Frontier Debt;
- exact material-support and target-scope delta representations;
- Selected/Rejected/Uncertain diagnostics derived from final q/s;
- numerical reduction/tolerance and memory/performance budget;
- calibration, policy freeze, production promotion, and cutover ownership.

## Validation families

- immutable reaggregation / no double counting;
- finite prior yields to growing Evidence;
- unknown versus conflict q/s fixtures;
- raw-V unchanged under Reliability;
- robust/absolute Reliability integration;
- warm versus cold and input-permutation equivalence;
- convergence, false-convergence, tail-drift, and period-two fixtures;
- scope freeze and post-solve atomic delta;
- non-convergence/stale dependency handling;
- production identity fail closed.

## Non-goals

No classified-N migration, View Utility, terminal Candidate publication, Native Selection mutation, or gradient/logit optimization.
