# V2C — Provisional Consensus state + canonical bounded solve

Status: **review-required parent envelope — Q4 recurrence model accepted; Q5 readout/residual pending; not agent-ready**

Blocked by: none  
Blocks: V2D

## Authority

- Final Spec v2.0 Amendment 003;
- ADR 0024;
- Amendments 002/001 and Final Spec v2.0 where not superseded;
- current immutable P/N/V and target-scope contracts.

## Goal

Introduce a Companion-local Provisional Consensus represented by continuous membership tendency `q`, independent support/knownness `s`, and an exact frozen scope binding. Compute the canonical state through a deterministic bounded batch recurrence over the exact current Included Stable observation set.

## Inputs / preconditions

- current exact Included Stable Views, Participation, and immutable P/N/V;
- finite Conservative Seed prior and current stable input revision;
- frozen Core / Discovery Envelope / Frontier revision;
- same-decision raster family for the later reviewed consensus readout;
- exact target, dependency, artifact, and policy identities.

## Outputs / handoff

- per-Stable-ID q/s state plus frozen scope binding;
- deterministic canonical input/output digests;
- one atomic public Consensus Revision per current input-set change;
- bounded private Solver Iterations;
- convergence or non-convergence status;
- proposed post-solve Scope Delta;
- cache/journal seam whose warm/incremental result is equivalent to a cold canonical full solve.

## Accepted recurrence invariants

- `q` is continuous membership tendency, not a calibrated probability or Candidate.
- `s` distinguishes weakly observed unknown support from high-support conflict.
- q/s initialize from a finite Seed prior plus a uniform aggregate over all current Included Evidence.
- View arrival order and cache history do not define canonical output.
- Reliability iteration `r` consumes q/s from iteration `r-1` only.
- Core/Envelope/Frontier remain frozen during the solve.
- Scope Delta commits only after the solve and affects a later solve.
- One public revision may contain multiple private iterations.
- Non-convergence cannot establish Ready or publish Candidate.
- Consensus stays Companion-local and never mutates Native Selection or Stable observation authority.

## Remaining review gates before decomposition

- Q5: exact same-decision soft foreground / support / Frontier readout;
- visibility and trust gating for residual computation;
- exact q0/s0 transform and finite Seed-prior strength;
- q/s update transform from weighted P/N and raw V;
- convergence metric, tolerance, and maximum iterations;
- output representation, memory layout, and GPU/reference parity;
- journal lifetime and identity fields shared with V2I.

## Validation families

- arrival-order permutation equivalence;
- warm/incremental versus cold canonical full solve;
- unknown (`q≈0.5,s low`) versus conflict (`q≈0.5,s high`);
- same-round feedback prohibition;
- scope freeze and two-phase Scope Delta;
- non-convergence preserves prior Candidate and blocks Ready;
- identity invalidation and deterministic replay.

## Non-goals

- No final residual equation (Q5/V2D), calibration numbers, Candidate publication, Browser consensus artifact, or Native Selection mutation.
