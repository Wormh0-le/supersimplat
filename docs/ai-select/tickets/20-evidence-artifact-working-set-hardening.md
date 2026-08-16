# 20 — FlashSplat-style same-decision GPU Evidence + artifact / working-set hardening

Status: current — ready after implemented Ticket 19; Final Spec v1.3 aligned

Blocked by: 19, 14, 09

## Current Final Spec mapping

- Final Spec v1.3 §§4–5, 20–22, 24–25
- ADR 0013
- ADR 0016 TargetGeometryHint and bounded local-view boundary
- Final Spec v1.1 Amendments 001/004 and DG-20/DG-24 as historical renderer/Evidence rationale only where not superseded
- FlashSplat-style direct Evidence accumulation design
- MVP Phase 7 production Evidence as historical staging provenance

Final Spec v1.3 is the only current closure source.

## Inputs / preconditions

- Reference P/N/V policy, metrics, and fixtures from Ticket 14
- Validated authoritative RGB/render scope/Render Working Set path from Ticket 19
- Stable Mask artifacts and exact RGB binding
- 10–20+ View Gallery
- `TargetGeometryHintArtifact` only as an optional Working Set seed
- Locked/pinned CUDA runtime ownership
- Known contributor-alpha mismatch CameraBinding regression fixture

## Outputs / handoff artifacts

- Production FlashSplat-style Direct Evidence raster path
- Versioned rasterImplementationId / Evidence backend capability
- Versioned per-view GaussianEvidenceArtifact/cache
- Expandable target Evidence Working Set mapping
- Complete Contributor debug/reference boundary
- Mask/Evidence/thumbnail lifecycle and memory profile

## What to build

Implement the production path described by the FlashSplat-style design: during the authoritative front-to-back Gaussian pixel traversal, the same accepted contribution `w = alpha × incoming T` is used for RGB and directly accumulated into per-Gaussian P/N/V. Do not build or publish complete per-pixel Contributor IDs/weights in the normal product path.

This is a single decision-source requirement, not merely reuse of the same formulas in another kernel. The implementation may be a project-owned pinned CUDA extension or a controlled pinned gsplat fork, but its source/build/runtime identity is part of the artifact contract.

## Acceptance criteria

### Authoritative same-decision raster path

- [ ] Production Evidence uses the same projected data, front-to-back order, sigma, alpha, validity decision, incoming T, `alpha × T`, and termination decision as authoritative RGB.
- [ ] One literal CUDA launch is not required, but no later pass independently re-decides boundary-sensitive acceptance/termination.
- [ ] The implementation is a project-owned pinned CUDA extension or controlled pinned gsplat fork with explicit source revision, ABI/build identity, supported runtime/GPU policy, and readiness capability.
- [ ] Raw P/N/V are emitted by the raster/Evidence path; multi-view aggregation and classification remain outside CUDA in a versioned Evidence Policy.
- [ ] Production output is per-view Stable-ID-indexed P/N/V plus optional boundaryMass, not complete per-pixel Contributor data.
- [ ] P/N/V use independent positive/negative/visible weights from Ticket 14. The production path does not assume `P + N = V`.
- [ ] Far-neutral pixels produce no writes; work is limited to the declared positive/boundary/local-negative ROI without changing render traversal/occlusion semantics.

### RGB and Stable Mask binding

- [ ] A View used for production Direct Evidence has authoritative RGB from the same `rasterImplementationId` and compatible render policy.
- [ ] RGB-only and later mask-conditioned Evidence modes use the same Direct-Evidence-capable raster implementation; enabling Evidence writes must not change RGB for identical inputs.
- [ ] The Evidence attempt reuses the exact CameraBinding/render scope/Render Working Set and produces or verifies the same authoritative RGB digest bound to the Stable Mask.
- [ ] RGB digest mismatch publishes no Evidence and never silently rebinds a Mask.
- [ ] Renderer migration bumps identity and invalidates incompatible RGB/Mask/Evidence bindings.

### Render and Evidence Working Sets

- [ ] Render Working Set contains every Gaussian needed for RGB, occlusion, incoming T, and termination.
- [ ] Evidence Working Set contains target-local Core+Context Stable Gaussian IDs that receive P/N/V writes.
- [ ] `TargetGeometryHintArtifact` may seed initial Core/Context construction but is never the final upper bound.
- [ ] Later Included Stable View support can expand the Evidence Working Set beyond the Anchor-visible geometry seed.
- [ ] A Gaussian is not Rejected/Out of Scope solely because `TargetGeometryHintArtifact` did not include it.
- [ ] Evidence touching the current Working Set boundary triggers declared expansion or fails closed with diagnostics; it never silently truncates support.
- [ ] Target and non-target/out-of-scope occluders remain in traversal and map to `localEvidenceId = -1` or equivalent.
- [ ] Stable global-render identity → target Stable ID → Evidence-local mapping rejects missing, duplicate, colliding, and out-of-range identities.
- [ ] Full-render-scope and spatial Render Working Set produce equivalent RGB and production Evidence under the declared parity gate.
- [ ] Rasterizing only the Evidence Working Set is explicitly tested and rejected as incorrect.

### Artifact and incremental lifecycle

- [ ] GaussianEvidenceArtifact binds target/dependency identity, Camera, RGB digest, Stable Mask, Evidence Policy, Render/Evidence Working Sets, target Stable IDs, `rasterImplementationId`, `evidenceBackendKind=production-direct`, `evidenceBackendId`, and `runtimeBuildId`.
- [ ] Per-view artifact reuse validates every dependency and supports Exclude/reinclude, Stable Mask replacement, Working Set expansion, and incremental Re-Lift.
- [ ] Reference and production artifacts cannot collide in cache or Candidate readiness.
- [ ] Views may be processed sequentially; all per-view GPU P/N/V buffers need not be resident simultaneously.
- [ ] GPU buffer scale is O(|Evidence Working Set| × channels) per processed View, excluding renderer state.
- [ ] `选择另一个对象`, successful changed-Anchor atomic cutover, and explicit
      View replacement/disposal release unreferenced target-local artifacts
      without invalidating exact shared caches. No Regenerate Auto Views
      product command is required.

### Numerical and reference validation

- [ ] Reference-vs-production P/N/V agrees under a declared numeric policy and yields stable final classification.
- [ ] Compare max/p95/p99 absolute error, relative error, support differences, threshold-near Gaussians, and final class differences.
- [ ] Known Contributor/raster-alpha mismatch fixture produces stable Direct Evidence without Contributor reconciliation.
- [ ] Repeat identical inputs to characterize atomicAdd variation; classification margins prevent flips.
- [ ] Strong positive/background classes agree with trusted reference; differences are limited to declared low-mass/boundary/threshold regions.
- [ ] Mixed large-footprint and unobserved fixtures preserve Uncertain semantics.
- [ ] TargetGeometryHint-seed expansion fixture recovers Gaussians visible only from later Included local/User-added Views.

### Performance implementation order

- [ ] Begin with a simple global-atomic baseline after semantics are validated.
- [ ] Measure atomic contention, latency, VRAM, write bandwidth, and register pressure before optimization.
- [ ] Optimization order follows measured need: ROI restriction → expandable Evidence Working Set writes → tile/block reduction → sparse intermediate/special handling.
- [ ] Every optimized path remains equivalent to baseline Evidence semantics and Stable ID mapping.
- [ ] No silent truncation, overflow, nearest/top-k/distance/center/visibility-only fallback, or best-effort publication.

### Reference/debug boundary and resource lifecycle

- [ ] Complete Contributor remains available only behind explicit debug/reference capability and may fail without blocking RGB/Direct Evidence.
- [ ] Normal Direct Evidence does not allocate, serialize, hash, cache, or wait for complete Contributor output.
- [ ] Mask and Evidence artifact storage has explicit ownership/GC; current/referenced Stable Mask and Candidate inputs are never prematurely collected.
- [ ] Gallery thumbnail/texture lifecycle is bounded under 10–20+ Views.
- [ ] Working-set memory for RGB/Mask/Evidence/reference Contributor/thumbnail artifacts is measured separately.

## Failure / recovery criteria

- [ ] Evidence OOM/kernel/artifact failure preserves RGB/View/Stable Mask/Gallery and previous Candidate; no partial Evidence publishes.
- [ ] Same-pass RGB digest mismatch fails Evidence closed and does not mutate Stable Mask binding.
- [ ] Identity/mapping/overflow/expansion failure never emits partial target Evidence.
- [ ] Incompatible rasterImplementationId/runtimeBuildId/evidenceBackendId blocks artifact reuse and Candidate publication without relabeling historical RGB as Render Failed.
- [ ] GC failure cannot delete current Stable Mask, current per-view Evidence, or current Candidate inputs.
- [ ] Reference Contributor failure affects diagnostics only.

## Validation

- Locked GPU same-decision tests
- RGB-only versus RGB+Evidence same-implementation digest test
- Old-renderer identity migration/invalidation test
- Reference-versus-production backend cache/readiness separation test
- Known Contributor-alpha mismatch CameraBinding regression
- Reference-vs-production P/N/V and classification fixtures
- Target plus non-target occluder fixture
- Full versus spatial Render Working Set RGB/Evidence parity
- TargetGeometryHint-seed expansion / boundary-triggered expansion fixture
- P/N/V independence tests
- Repeated-run classification stability
- Global-atomic baseline versus optimized implementation equivalence
- Large-scene memory/latency profile
- Mask/Evidence GC lifecycle tests
- Gallery resource stress

## Non-goals

- No hard-coded final classification inside CUDA
- No planner/MaskReview/Lift-readiness threshold calibration; Ticket 21 owns calibration
- No complete pixel-level provenance in the normal product artifact
- No DG-14 provenance UI
