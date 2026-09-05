# Renderer and Evidence

Read this file for rendering, CUDA, Evidence, working sets, and lifting. Follow [Domain authority](domain.md) for which capabilities are actually adopted; experimental implementations are not production authority.

## Correctness boundaries

- Production raw Evidence retains P/N/V with one Negative Mass channel. Classified-N remains an explicitly identified experiment unless separately promoted.
- Authoritative RGB, Direct Evidence, and any adopted CWED or semantic readout use the accepted alpha/transmittance contribution decisions. Matching formulas in an independent traversal do not prove same-decision behavior.
- Render Working Set completeness preserves occlusion, incoming transmittance, and termination. Semantic write/readout roles do not remove render-only occluders.
- Stable-ID/projected-row alignment, shape, dtype, device, finiteness, source/runtime identity, and applicable support limits remain validated. Do not weaken accepted cache/tensor-integrity checks to simplify planning.
- Missing or invalid depth/support is not background. CWED is a contribution-weighted statistic, not first-hit surface truth or ownership. Seed does not bound all discoverable target membership.
- Reaggregate immutable Evidence; do not accumulate previous inferred q/s as new evidence. Reliability, when adopted, affects semantic P/N, never raw V.

## Planning and evaluation

A low-resolution ViewUtilityProbe is prospective and occlusion-aware. It does not publish RGB, Mask, P/N/V, realized Coverage, Readiness, or Candidate. Only the selected camera enters full authoritative acquisition. Failed required probes do not silently become geometry-only or fixed-four winners.

Pin applicable source/runtime/ABI/policy and declare numerical tolerance. Validate scalar/reference versus GPU behavior and measure the affected latency, VRAM, capacity, and failure paths on the supported runtime. A byte digest proves integrity of that artifact; it does not by itself promise byte-identical floating-point recomputation. Diagnose actual equivalence separately.

Keep measurements proportional to the changed mechanism and reuse the real-scene harness. Product quality and correction-burden evaluation need actual consumers; mocks and synthetic fixtures cannot establish real-scene or production GPU success. Full hash-chain replay and resource quotation are not prerequisites for renderer work.
