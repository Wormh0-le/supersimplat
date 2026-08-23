# Renderer and Evidence

Current runtime produces immutable single-N Direct P/N/V. The v2 target adds internal CWED/readout moments, q+s recurrence, component scope, and hybrid ViewUtilityProbe; experimental paths are not production authority.

## Same-decision and probe boundaries

- Authoritative RGB, Direct Evidence, CWED, and consensus readout reuse the accepted alpha/transmittance chain.
- ViewUtilityProbe is low-resolution prospective planning only; complete Render Working Set occluders remain active.
- Only the selected candidate receives formal authoritative RGB/SAM/Evidence.
- Probe output is not RGB, Mask, Evidence, Coverage, Readiness, or Candidate.

## Cost/replay

- Probe and formal renderer work debit deterministic versioned cost units before dispatch through the Browser journal.
- Actual latency/cache/GPU load is telemetry and operational safety, never canonical ranking input.
- Replayed exact requests do not debit again; fresh retries do.
- A recomputed result under replay must match the journal-bound digest or fail closed.

Pin source/runtime/GPU/schema/policy/reduction order. Measure probe prediction error, latency/VRAM/OOM, q/s/readout cost, deterministic replay, and warm/cold equivalence before promotion.
