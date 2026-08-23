# V2C — Provisional Consensus state + canonical bounded solve

Status: **review-required parent envelope — Q4/Q5/Q6 accepted; Q7 scope semantics pending; not agent-ready**

Blocked by: none  
Blocks: V2D

## Authority

- Final Spec Amendments 003–005;
- ADRs 0024–0026;
- Amendments 001/002 and Final Spec v2.0 where not superseded.

## Goal

Introduce Companion-local Provisional Consensus represented by membership tendency `q`, independent support/knownness `s`, and an exact frozen scope binding. Compute one canonical Consensus Revision through a deterministic bounded batch solve over the exact current Included Stable observation set.

## Accepted contract

- Canonical input is independent of View arrival order and cache history.
- `q` is continuous derived tendency, not a calibrated probability or Candidate.
- `s` distinguishes weakly observed unknown support from high-support conflict.
- Initialization uses finite scope/provenance pseudo-mass priors plus a uniform aggregate over all current Included Evidence.
- Each iteration reaggregates immutable Evidence; prior q/s is not double-counted.
- Reliability iteration `r` consumes q/s from iteration `r-1` only.
- Production readout uses same-decision `M_scope/M_fg/M_known/M_core/M_frontier` moments and derived `P/K/C/F` maps.
- One public atomic Consensus Revision may contain multiple private Solver Iterations.
- Scope remains frozen during the solve; Scope Delta commits afterward and affects a later solve.
- Warm/incremental execution must match a cold canonical full solve within declared tolerance.
- Convergence uses material mean q/s drift, tail drift, View-weight drift, consecutive satisfaction, period-two detection, and a finite maximum iteration count.
- Non-convergence/oscillation cannot establish Ready or publish Candidate.

## Remaining review gates before decomposition

- Q7 Scope Delta: Core promotion, Frontier retention/rejection, Envelope expansion, and Frontier Debt;
- exact material-set and Scope Delta identity;
- GPU/CPU q/s and readout memory layout;
- reference parity and performance/OOM gates;
- journal lifetime/identity shared with V2I;
- calibration and production-promotion owners.

## Validation families

- View-order permutation equivalence;
- warm/incremental versus cold canonical solve;
- no iterative Evidence double counting;
- unknown versus high-support conflict;
- same-round feedback prohibition;
- same-decision readout parity;
- consecutive convergence and period-two oscillation fixtures;
- scope freeze/two-phase commit;
- non-convergence preserves prior Candidate and blocks Ready;
- identity invalidation and deterministic replay.

## Non-goals

No production numeric thresholds, Browser consensus artifact, Candidate publication, Native Selection mutation, classified-N dependency, or gradient/logit optimizer.
