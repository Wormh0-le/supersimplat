# V2F — View Utility, exploration, and layered candidate pool

Status: **review-required parent envelope; objective reviewed, prediction seam unresolved; not agent-ready**

Blocked by: V2B, V2E  
Blocks: V2G, V2I

## Authority

- Final Spec v2.0 §6.1–§6.2 as amended by Amendment 002;
- ADR 0023;
- Observation Coverage, View Diversity, TargetGeometryHint, and feasibility carry-over contracts.

## Goal

Select the next feasible CameraBinding by prospective value while balancing exploitation of known Core support with seed-independent Frontier discovery and Uncertain resolution.

## Reviewed utility structure

The policy must be able to express separately calibrated terms for:

```text
Core Observation Coverage gain
Frontier discovery / Frontier Debt reduction
Uncertain-resolution gain
View-direction diversity
re-observation / duplication penalty
render + SAM + Evidence + revision cost
```

No single term is the publication authority. Lift Readiness remains separate.

## Required behavior

- the first post-Anchor View may use a deterministic TargetGeometryHint/Seed framing rule because iterative state does not yet exist;
- later Views consume Core, Frontier, aggregate/Uncertain, diversity, feasibility, and cost state;
- Seed influence is strongest early and declines as iterative evidence becomes available;
- a bounded exploration floor prevents the planner from only re-observing already-covered Seed/Core;
- candidate layers include existing hint offsets and reviewed local sampling, all passing existing feasibility gates;
- selection and tie-breaks are deterministic and replayable;
- predicted gain is recorded against realized Core gain and Frontier discovery for calibration.

## Review gates before decomposition

- the ViewUtilityProbe data source and approximation contract;
- candidate-pool generation and bounds;
- cost units and whether wall-clock can affect deterministic decisions;
- seed-influence decay and exploration-floor schedule;
- normalization across Core, Frontier, Uncertain, diversity, and cost;
- incremental versus full rescore equivalence.

## Validation families

- deterministic candidate sequence and tie-break;
- no-seed-lock scenarios where a Frontier View outranks Core re-observation;
- predicted versus realized gain calibration;
- simple-object early stopping and difficult-object continued exploration;
- candidate feasibility, latency, VRAM, and failure behavior.

## Non-goals

- No budget/termination implementation, Candidate publication, or fixed-four product fallback.
