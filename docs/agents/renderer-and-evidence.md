# Renderer and Evidence

Read for gsplat, CUDA, RGB, P/N/V, CWED, Working Sets, q+s readout, Reliability, or reference Contributor.

## Current versus target

Current Direct Evidence produces immutable single-N P/N/V. Pinned gsplat exposes projected depth, but the project CUDA ABI does not yet consume it. The target adds internal depth moments and q+s readout; classified N is experimental only.

## Same-decision rule

Authoritative RGB, Direct Evidence, CWED moments, and consensus readout must reuse the accepted front-to-back alpha/transmittance decision chain. Independently re-deciding formulas do not establish same-decision behavior.

## Consensus/update contract

- q/s readout uses `M_scope/M_fg/M_known/M_core/M_frontier` and derives P/K/C/F.
- Render-only occluders still affect transmittance but not semantic moments.
- Each iteration reaggregates immutable normalized per-View masses.
- `q=(a+P)/(a+b+P+N)` with finite priors.
- `s=(1-exp(-E/tau_E))*(1-exp(-V/tau_V))`.
- Reliability multiplies P/N only; V is never multiplied by Reliability.
- View weights are independent `[r_min,1]`, not sum-normalized.
- Absolute residual guarding is maturity-gated.
- Non-convergence and period-two oscillation cannot publish Candidate.

## Production claims

Pin source/runtime/GPU/schema/policy/reduction order. Measure readout channels, q/s memory, atomics/registers, latency, VRAM/OOM, warm/cold equivalence, residual stability, convergence, and oscillation. Experimental identities cannot enter production before calibration and explicit promotion.

## Reference paths

Complete Contributor, V2AX classified N, and leave-one-out Reliability remain reference/benchmark paths. They do not silently become product authority.
