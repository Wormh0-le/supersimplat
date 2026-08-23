# Renderer, Evidence, and View Utility Probe

Read for gsplat, CUDA, RGB, P/N/V, CWED, Working Sets, q+s readout, Reliability, ViewUtilityProbe, or reference paths.

## Current versus target

Current Direct Evidence produces immutable single-N P/N/V. The target adds depth moments, q+s readout, TargetScopeState/Working Set v2, and a low-resolution ViewUtilityProbe. These remain unimplemented until reviewed stages land.

## Same-decision and probe boundaries

Authoritative RGB, Direct Evidence, CWED moments, and consensus readout must reuse the accepted full-resolution front-to-back decision chain. ViewUtilityProbe is a separate low-resolution prospective raster approximation: it must use complete compatible Render Working Set occlusion, but it is not formal RGB/Evidence or exact full-resolution same-decision truth.

## Probe invariants

- render-only occluders affect probe alpha/transmittance;
- semantic moments are restricted to current exact scope roles;
- probe output remains Companion-local;
- no SAM, Stable Mask, P/N/V, Coverage, Readiness, Scope mutation, or Candidate publication occurs during probing;
- only the selected winner runs full authoritative acquisition;
- cached/incremental probe scoring must equal cold full rescore for identical canonical inputs;
- deterministic cost inputs are versioned; measured wall-clock is telemetry/timeout only.

## Production claims

Pin candidate-pool, pruning, probe, utility, cost, renderer/runtime/GPU, Scope/q-s, and Render Working Set identities. Measure shortlist quality, pure-geometry failures, predicted/realized gain, latency, registers/atomics, VRAM/OOM, stale invalidation, cold/cache equivalence, and winner quality. Experimental policies cannot enter production before calibration and explicit promotion.

## Reference paths

Complete Contributor, V2AX classified N, leave-one-out Reliability, fixed-four, and full-render-all-candidates remain reference/benchmark paths. They do not silently become product authority.
