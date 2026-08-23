# ADR 0028: Adopt a bounded hybrid View Utility probe

Status: accepted  
Date: 2026-08-23

## Context

AI Select v2 must choose useful cameras without returning to fixed 4–8 View execution. Pure center/frustum geometry is inexpensive and deterministic but misses occlusion, Gaussian footprint, opacity, transmittance, and render-only blockers. Probing every candidate with full RGB and SAM would erase the latency advantage of active acquisition. Probing every candidate with a raster pass can also cost more than acquiring one View.

View Utility is prospective planning state, not Evidence or Readiness authority. Its cost model must remain replayable and cannot depend on transient GPU load.

## Decision

Adopt a finite layered candidate pool followed by:

1. deterministic geometric feasibility/pruning for every candidate;
2. a deterministic shortlist;
3. a low-resolution, complete-occlusion-aware ViewUtilityProbe for the shortlist;
4. full authoritative RGB/SAM/Evidence only for the selected winner.

The pool combines carried-over hint offsets, a sparse target-scope shell, and bounded component-Debt-targeted candidates. Canonical scoring uses deterministic cost units. Actual wall-clock is telemetry/operational safety only.

Probe outputs are Companion-local heuristics. They never become RGB, Stable Mask, P/N/V, Coverage, Readiness, Candidate, or Native Selection authority. Predicted gains are recorded against realized gains for calibration.

## Consequences

- The planner can reject geometrically plausible but occluded Views without rendering/SAM for all candidates.
- New candidate/probe/utility/cost identities and GPU performance gates are required.
- Low-resolution prediction will be imperfect and requires real-scene calibration.
- Candidate counts, shortlist size, probe resolution, weights, exploration, and seed decay remain calibration-owned.
- Fixed-four and full-render-all-candidates remain offline baselines/oracles, not product fallbacks.
- V2G/V2I must own probe failure, budget, timeout, replay, and attempt semantics.
