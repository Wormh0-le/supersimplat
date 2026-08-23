# V2C — Provisional Consensus state + canonical bounded solve

Status: **review-required parent envelope — Q4 recurrence and Q5 readout accepted; Q6 transforms/convergence pending; not agent-ready**

Blocked by: none  
Blocks: V2D

## Authority

- Final Spec v2.0 Amendments 004 and 003;
- ADR 0025 and ADR 0024;
- Amendments 002/001 and Final Spec v2.0 where not superseded;
- current immutable P/N/V and target-scope contracts.

## Goal

Introduce a Companion-local Provisional Consensus represented by continuous membership tendency `q`, independent support/knownness `s`, and an exact frozen scope binding. Compute the canonical state through a deterministic bounded batch recurrence over the exact current Included Stable observation set, with a multi-channel same-decision readout for lagged Reliability.

## Inputs / preconditions

- current exact Included Stable Views, Participation, and immutable P/N/V;
- finite Conservative Seed prior and current stable input revision;
- frozen Core / Discovery Envelope / Frontier / Context revision;
- same-decision raster family;
- exact target, dependency, artifact, and policy identities.

## Outputs / handoff

- per-Stable-ID q/s state plus frozen scope binding;
- deterministic canonical input/output digests;
- one atomic public Consensus Revision per current input-set change;
- bounded private Solver Iterations;
- convergence or non-convergence status;
- proposed post-solve Scope Delta;
- cache/journal seam equivalent to a cold canonical full solve;
- Companion-internal same-decision moments per evaluated View:
  `M_scope`, `M_fg`, `M_known`, `M_core`, and `M_frontier`.

## Accepted recurrence invariants

- `q` is continuous membership tendency, not a calibrated probability or Candidate.
- `s` distinguishes weakly observed unknown support from high-support conflict.
- q/s initialize from a finite Seed prior plus a uniform aggregate over all current Included Evidence.
- View arrival order and cache history do not define canonical output.
- Reliability iteration `r` consumes q/s from iteration `r-1` only.
- Core/Envelope/Frontier/Context remain frozen during the solve.
- Scope Delta commits only after the solve and affects a later solve.
- One public revision may contain multiple private iterations.
- Non-convergence cannot establish Ready or publish Candidate.
- Consensus stays Companion-local and never mutates Native Selection or Stable observation authority.

## Accepted readout contract

- Support-aware membership is `q̃ = 0.5 + s(q - 0.5)`.
- Semantic readout scope is frozen `Core ∪ Frontier ∪ Context`.
- Out-of-Scope/render-only Gaussians continue to affect occlusion, transmittance, accepted weights, and termination but do not write semantic moments.
- `P=M_fg/M_scope`, `K=M_known/M_scope`, `C=M_core/M_scope`, and `F=M_frontier/M_scope` are derived only under valid scope mass.
- Low/invalid scope mass is insufficient comparison support, not background.
- Readout maps remain Companion-local and do not replace raw V or create a Browser protocol artifact.
- GPU/reference implementation identity and parity are explicit.

## Remaining review gates before decomposition

- Q6: exact q0/s0 transform and finite Seed-prior strength;
- q/s update transform from weighted P/N and raw V;
- robust residual-to-weight normalization shared with V2D;
- convergence metric, tolerance, and maximum iterations;
- output representation, channel layout, memory/performance gates, and numerical parity;
- journal lifetime and identity fields shared with V2I.

## Validation families

- arrival-order permutation equivalence;
- warm/incremental versus cold canonical full solve;
- unknown (`q≈0.5,s low`) versus conflict (`q≈0.5,s high`);
- same-round feedback prohibition;
- same-decision readout parity and low-scope-mass invalidity;
- render-only occluder preservation;
- support-aware membership fixtures;
- scope freeze and two-phase Scope Delta;
- non-convergence preserves prior Candidate and blocks Ready;
- identity invalidation and deterministic replay.

## Non-goals

- No production numerical thresholds, Browser consensus artifact, Candidate publication, Native Selection mutation, or production leave-one-out solve.
