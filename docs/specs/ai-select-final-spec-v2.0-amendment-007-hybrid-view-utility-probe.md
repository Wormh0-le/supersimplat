# AI Select Final Spec v2.0 Amendment 007 — Hybrid View Utility Probe and bounded candidate pool

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–006  
**Decision record:** `docs/adr/0028-adopt-hybrid-view-utility-probe.md`

## 1. Purpose

Amendments 002 and 006 require View Utility to balance Core exploitation, seed-independent Frontier discovery, Uncertain resolution, diversity, duplication, and cost. They did not define how a candidate CameraBinding is generated or how prospective value is measured before the expensive authoritative RGB → SAM → Evidence path.

This amendment adopts a finite layered candidate pool and a two-stage hybrid probe:

```text
finite layered candidates
→ cheap deterministic geometry pruning
→ low-resolution occlusion-aware probe for a deterministic shortlist
→ full authoritative acquisition for the winner only
```

Runtime remains the implemented v1.3 baseline until reviewed stages are calibrated and explicitly promoted.

## 2. View Utility authority boundary

`ViewUtilityProbe` is Companion-local prospective derived state. It is not:

- authoritative RGB;
- a Stable Mask or observation;
- raw P/N/V Evidence;
- Observation Coverage or Frontier Debt truth;
- Lift Readiness;
- Candidate or Native Selection authority.

Probe output may rank feasible candidate cameras. Only the selected winner enters the ordinary authoritative RGB, SAM 3 Image, Stable Mask, Participation, Direct Evidence, Consensus, Scope, and Readiness pipeline.

## 3. Finite layered candidate pool

The pool is deterministic, versioned, finite, and target-local. Every candidate has a stable candidate identity, declared source layer, CameraBinding, and deterministic tie-break position.

### 3.1 Layer 0 — carried-over hint offsets

Retain the reviewed local TargetGeometryHint/Seed offset family as the stable basis and initial-view source. The first post-Anchor View may select the highest-priority feasible Layer-0 candidate because iterative q/s and structured Frontier Debt do not yet exist.

### 3.2 Layer 1 — target-scope shell

Generate a bounded set of azimuth/elevation candidates around a robust target-scope center and extent. This is a sparse deterministic shell, not a dense orbit or fixed view-count product contract.

### 3.3 Layer 2 — debt-targeted candidates

Generate a bounded number of candidates aimed at material Unobserved, Conflict, or Promotion-pending Frontier components. A debt-targeted camera must still preserve valid whole-target framing and pass the ordinary feasibility policy.

Candidate counts, shell bands, shortlist size, and layer quotas are calibration-owned. Candidate generation must remain bounded even when Frontier component count is large.

## 4. Stage 1 — deterministic geometric pruning

All candidates first pass cheap deterministic checks and approximations:

- finite CameraBinding and valid projection;
- near/far and target-local distance bounds;
- target projected-size and framing bounds;
- frustum inclusion and gross invalid-placement checks;
- direction duplication against current Included observations;
- coarse center/extent estimates of potential Core and Frontier visibility.

Stage 1 may reject clearly infeasible or dominated candidates and construct a deterministic shortlist. Its center/extent approximation is not visibility truth and cannot by itself publish the final winner once Stage 2 is available.

## 5. Stage 2 — low-resolution occlusion-aware ViewUtilityProbe

Only the deterministic shortlist receives a low-resolution raster probe. The probe uses:

- the complete compatible Render Working Set;
- the same camera conventions and front-to-back alpha/transmittance family;
- current exact Scope Epoch/Revision;
- Core, active Frontier, required Context, and final current q/s/Uncertain state;
- current Core Coverage, structured Frontier Debt, and View Diversity identities.

Render-only occluders remain in the raster chain. The probe may accumulate compact prospective moments such as:

- predicted Core visible-mass gain;
- predicted per-component Frontier visibility and Debt reduction;
- predicted support for resolving Uncertain/conflicted components;
- duplication/re-observation cost;
- deterministic raster-work cost units.

The probe does not run SAM, publish an RGB artifact, create P/N/V, or mutate TargetScopeState.

Low-resolution probe decisions are planning approximations. They do not claim exact equivalence to the final full-resolution authoritative render.

## 6. Utility structure

The versioned policy combines separately inspectable terms:

```text
U(v) = Core-gain
     + Frontier/Debt-reduction gain
     + Uncertain-resolution gain
     + directional-diversity gain
     - duplication penalty
     - deterministic acquisition/revision cost
```

Seed/TargetGeometryHint influence is strongest for the first View and declines as current q/s, Core, Frontier, and Debt become available. A bounded exploration floor prevents the policy from selecting only already-covered Core re-observations.

Exact normalization, coefficients, seed decay, exploration schedule, and marginal-gain thresholds are calibration-owned.

## 7. Deterministic cost units

Canonical ranking uses versioned deterministic cost units derived from declared inputs, for example:

- probe resolution and pixel count;
- Render Working Set size;
- projected/tile-intersection work reported by the probe;
- active scope/component counts;
- fixed SAM resolution class;
- declared Consensus/Scope revision cost class.

Measured wall-clock latency, GPU occupancy, cache hit rate, or host load are telemetry and operational safety inputs only. They must not change canonical candidate ordering or replay semantics.

Operational timeout, OOM, cancellation, and probe failure may stop or fail an attempt under V2G/V2I, but cannot silently substitute wall-clock ranking or a geometry-only winner.

## 8. Selection and acquisition

After Stage 2, candidates are scored and tie-broken deterministically. Only one selected winner proceeds to:

```text
full authoritative RGB
→ SAM 3 Image
→ Stable Mask / Participation
→ Direct Evidence
→ canonical Consensus / Scope
```

Unselected candidates do not run full RGB/SAM merely to evaluate Utility. Full-render/SAM-all-candidates remains an offline oracle benchmark only.

If the shortlist has no usable probe result, V2G/V2I own `no-feasible-view`, bounded replacement, or stage-failure behavior. The product must not silently restore fixed-four or choose an unprobed geometry-only candidate as if it had equivalent authority.

## 9. Identity, cache, and replay

Each probe and score binds at least:

- target/dependency identity;
- Scope Epoch/Revision and TargetScopeState digest;
- current converged Consensus Revision/q/s digest;
- Core Coverage, Frontier Debt, Uncertain, and View Diversity digests;
- candidate-pool, pruning, probe, utility, tie-break, and deterministic-cost policy identities;
- candidate CameraBinding identity;
- Render Working Set identity.

A scope, q/s, observation, or policy change invalidates incompatible probe results. Cached/incremental rescoring is an optimization only and must agree with a cold full rescore for the same canonical inputs.

## 10. Predicted-versus-realized calibration

For each selected View, the system records prospective predictions against realized outcomes after Stable Mask, Evidence, Consensus, and Scope processing:

- predicted versus realized Core Coverage gain;
- predicted versus realized Frontier visibility and Debt reduction;
- predicted versus realized Uncertain resolution;
- predicted versus realized discovery/Scope Delta;
- probe and full acquisition cost;
- final Candidate quality and human Add/Remove burden in release benchmarks.

Promotion requires calibration over simple and difficult real scenes, not only synthetic camera fixtures.

## 11. Validation

Later stages must cover:

- deterministic layered candidate IDs and bounds;
- geometric-pruning and shortlist permutation equivalence;
- occlusion cases where pure geometry is wrong;
- complete Render Working Set and render-only occluder preservation;
- no-seed-lock and Debt-targeted candidate fixtures;
- cold/full versus cached/incremental rescore equivalence;
- wall-clock variation does not change candidate order;
- probe stale identity, failure, OOM, and timeout handling;
- predicted-versus-realized calibration;
- fixed-four remains an ablation baseline only.

## 12. Remaining review gates

This amendment does not choose shortlist size, probe resolution, pool quotas, coefficients, exploration floor, seed-decay curve, cost-unit scales, or production thresholds. V2G/V2I must next define budgets, failure accounting, identity hierarchy, replay, cancellation, suspension, and Continue Acquisition semantics. Calibration and production promotion still require explicit owners.
