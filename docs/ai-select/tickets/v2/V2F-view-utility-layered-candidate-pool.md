# V2F — View Utility probe, exploration, and candidate pool

Status: **review-required parent envelope — current review frontier; not agent-ready**

Blocked by: V2B, V2E  
Blocks: V2G, V2I

## Authority

Final Spec Amendments 002 and 006; ADRs 0023 and 0027; carried-over CameraBinding, TargetGeometryHint, feasibility, Observation Coverage, and View Diversity contracts.

## Goal

Choose the next feasible CameraBinding by prospective value while balancing Core exploitation, component Frontier Debt reduction, Uncertain resolution, directional diversity, duplication, and total acquisition/revision cost.

## Accepted inputs

- current exact TargetScopeState and Scope Revision;
- Core Observation Coverage;
- structured Frontier Debt and component materiality;
- final current q/s and Uncertain diagnostics;
- View Diversity and prior CameraBindings;
- TargetGeometryHint/Seed framing for the first View;
- feasibility and cost state.

A `scope-advanced`, non-converged, or stale Consensus result is not a valid utility state; orchestration first completes the required canonical re-solve.

## Required behavior

- first post-Anchor View may use deterministic hint/Seed framing;
- later Views consume Core, component Debt, Uncertain, diversity, feasibility, and cost;
- Seed influence declines as current iterative state matures;
- bounded exploration prevents only re-observing covered Core;
- predicted gain records realized Core gain, Debt reduction, and new discovery;
- selection/tie-break is deterministic and replayable;
- no utility term publishes Candidate or changes scope directly.

## Q8 review gates

- ViewUtilityProbe data source and approximation authority;
- candidate-pool layers and finite bounds;
- whether candidate scoring uses low-resolution raster probes, geometric approximation, or staged hybrid probing;
- deterministic cost units and treatment of measured wall-clock;
- normalization across Core gain, component Debt, Uncertain, diversity, duplication, and cost;
- seed decay/exploration floor;
- incremental/full rescore equivalence and prediction/realization calibration.

## Validation families

Deterministic candidates/tie-break; no-seed-lock; component Debt targeting; predicted/realized gain; simple-object early stop; difficult-object exploration; probe latency/VRAM/OOM; scope-revision identity rejection.

## Non-goals

No budget/termination implementation, Candidate publication, or fixed-four product fallback.
