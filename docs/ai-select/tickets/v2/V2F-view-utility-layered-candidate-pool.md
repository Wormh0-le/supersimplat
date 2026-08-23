# V2F — Layered candidate pool and hybrid ViewUtilityProbe

Status: **reviewed parent envelope — Q8-C accepted; awaiting stage decomposition; not agent-ready**

Blocked by: V2B, V2E  
Blocks: V2G, V2I

## Authority

Final Spec Amendment 007; ADR 0028; Amendments 002/006 and carried-over CameraBinding, TargetGeometryHint, Render Working Set, feasibility, Coverage, Diversity, and target-scope contracts.

## Goal

Choose the next feasible CameraBinding by prospective value without full-rendering or running SAM for every candidate. Balance Core gain, component Frontier Debt reduction, Uncertain resolution, diversity, duplication, and deterministic acquisition/revision cost.

## Accepted contract

### Candidate pool

- finite deterministic layers: existing hint offsets, sparse target-scope shell, bounded component-Debt-targeted candidates;
- stable candidate IDs, source layer, CameraBinding, and tie-break order;
- first post-Anchor View may use the highest-priority feasible Layer-0 candidate;
- candidate counts and quotas are calibration-owned and bounded.

### Two-stage evaluation

1. Every candidate receives cheap deterministic geometry feasibility/pruning.
2. A deterministic shortlist receives a low-resolution complete-occlusion-aware ViewUtilityProbe.
3. Only the selected winner receives full authoritative RGB, SAM, Stable Mask, Evidence, and Consensus processing.

The probe preserves render-only occluders through the complete Render Working Set and may predict Core gain, component Debt reduction, Uncertain resolution, duplication, and deterministic raster cost. It creates no RGB/Mask/P/N/V/Coverage/Readiness/Candidate authority.

### Cost and replay

- canonical ranking uses deterministic cost units;
- measured wall-clock/cache/GPU load cannot change candidate order;
- cache/incremental rescore must equal cold full rescore for identical canonical inputs;
- probe identities bind target, dependency, Scope Revision, q/s, state digests, candidate/policy identities, and Render Working Set.

### Calibration

Each selected View records predicted versus realized Core gain, component Debt reduction, Uncertain resolution, discovery/Scope Delta, cost, Candidate quality, and correction burden.

## Later decomposition families

- V2F1 layered candidate generation and identity;
- V2F2 geometry pruning and deterministic shortlist;
- V2F3 low-resolution ViewUtilityProbe/reference parity;
- V2F4 utility scoring, deterministic cost, tie-break, and rescore equivalence;
- V2F5 predicted/realized shadow benchmark and policy calibration.

## Validation families

Occlusion defeating pure geometry; deterministic pool/shortlist/order; no-seed-lock and Debt targeting; render-only occluder preservation; stale identity; cold/incremental equivalence; wall-clock invariance; probe failure/OOM/timeout; predicted/realized calibration.

## Non-goals

No budget/terminal state machine, Candidate publication, persistent camera controls, fixed-four product fallback, or full-render/SAM-all-candidates product path.
