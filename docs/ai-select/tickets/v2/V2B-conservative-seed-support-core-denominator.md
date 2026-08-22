# V2B — Conservative Seed Support + Core Target denominator

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: V2A
Blocks: V2E, V2F

## Final Spec v2.0 mapping

- Final Spec v2.0 §4; `CONTEXT.md` non-normative "Conservative Seed Support"
- Carry-over: v1.3 Stable Gaussian IDs, SceneSnapshot identity

## Goal

Derive the precision-first 3D Conservative Seed Support from Anchor production
Direct Evidence immediately after Anchor Confirm, and establish the seed-based
monotonic Core Target denominator with shadow-phase dual coverage reporting.

## Inputs / preconditions

- Anchor production Direct P/N/V run at Confirm (early GPU Evidence stage);
- V2A expected-depth channel;
- Stable Gaussian IDs + per-Gaussian scale and position data.

## Outputs / handoff

- Companion-internal seed artifact: Stable Gaussian IDs + per-seed diagnostics
  (support ratio, visible mass, filtering reasons);
- scale-aware adjacency construction (pair distance < k × larger Gaussian
  scale, depth-consistency gated) with connectivity analysis;
- Core Target denominator state: starts from the seed, monotonic expansion
  within a target lifecycle, never shrinks;
- shadow-phase dual coverage report: seed base and whole-Target-Splat base
  reported side by side (calibration input);
- versioned policy identity `seed-policy/experimental-v*`.

## Acceptance criteria

- [ ] Precision filters implemented as parameterized stages: high positive
      ratio, sufficient visible mass, low conflicting mass — all thresholds are
      named calibration inputs (spec §12), not hardcoded constants.
- [ ] Depth-consistency filtering against the V2A expected-depth channel
      excludes floater/penetration attribution.
- [ ] Connectivity filter: primary component forms the core; above-threshold
      non-primary components join marked `satellite`; below-threshold ones are
      recorded `filtered` with reasons; no component disappears without a
      diagnosable reason.
- [ ] Quality states `usable / limited / unavailable` are recorded diagnostics
      that never block the flow; unavailable falls back to the broad
      denominator while the loop proceeds on per-View Evidence.
- [ ] The seed artifact never crosses the Browser/Companion boundary.
- [ ] Seed is not TargetGeometryHint, not ownership, not an AI Candidate, not
      Native Selection, and never a hard bound on Evidence expansion.
- [ ] Denominator expansion is monotonic within a target lifecycle; regression
      test proves no shrink path exists.
- [ ] Policy runs under `seed-policy/experimental-v*`; promotion to production
      identity happens only by explicit key change after calibration.
- [ ] Existing first-hit support collection (`target_geometry.py::
    _collect_first_hit_support`) is not repurposed as an ownership source.

## Validation

- Companion unit tests for each filter stage and satellite/filtered bookkeeping;
- monotonicity regression fixture;
- fallback-broad-denominator fixture;
- identity/staleness tests.

## Non-goals

- No View selection or utility scoring (V2F).
- No consensus/reliability consumption yet; seed filters use Anchor Evidence
  only.
- No numeric threshold values — calibration round owns them (spec §12).
