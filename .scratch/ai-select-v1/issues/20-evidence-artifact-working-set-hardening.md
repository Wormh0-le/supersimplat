# 20 — FlashSplat-style same-decision GPU Evidence + artifact / working-set hardening

Status: ready-for-agent — v2.2 FlashSplat-alignment review

Blocked by: 19, 14, 09

## Final Spec mapping

- Final Spec v1.1 §§14–19, 30 Stage 3–5, 31–32
- ADR 0013
- FlashSplat-style direct Evidence accumulation design
- DG-20
- MVP Phase 7 production Evidence

## Inputs / preconditions

- Reference P/N/V policy, metrics, and fixtures from Ticket 14
- Validated authoritative RGB/render scope/Render Working Set path from Ticket 19
- Stable Mask artifacts and exact RGB binding
- 10–20+ View Gallery
- Locked/pinned CUDA runtime ownership
- Known contributor-alpha mismatch CameraBinding regression fixture

## Outputs / handoff artifacts

- Production FlashSplat-style Direct Evidence raster path
- Versioned rasterImplementationId / Evidence backend capability
- Versioned per-view GaussianEvidenceArtifact/cache
- Target Evidence Working Set mapping
- Complete Contributor debug/reference boundary
- Mask/Evidence/thumbnail lifecycle and memory profile

## What to build

Implement the production path described by the uploaded FlashSplat-style design: during the authoritative front-to-back Gaussian pixel traversal, the same accepted contribution `w = alpha × incoming T` is used for RGB and directly accumulated into per-Gaussian P/N/V. Do not build or publish complete per-pixel Contributor IDs/weights in the normal product path.

This is a single **decision-source** requirement, not merely reuse of the same formulas in another kernel. The implementation may be a project-owned pinned CUDA extension or a controlled pinned gsplat fork, but its source/build/runtime identity is part of the artifact contract.

## Acceptance criteria

### Authoritative same-decision raster path

- [ ] Production Evidence uses the same projected data, front-to-back order, sigma, alpha, validity decision, incoming T, `alpha × T`, and termination decision as authoritative RGB.
- [ ] One literal CUDA launch is not required, but no later pass independently re-decides boundary-sensitive acceptance/termination.
- [ ] The implementation is a project-owned pinned CUDA extension or controlled pinned gsplat fork with explicit source revision, ABI/build identity, supported runtime/GPU policy, and readiness capability.
- [ ] Raw P/N/V are emitted by the raster/Evidence path; multi-view aggregation and classification remain outside CUDA in a versioned Evidence Policy.
- [ ] Production output is per-view Stable-ID-indexed P/N/V plus optional boundaryMass, not complete per-pixel Contributor data.
- [ ] P/N/V use independent positive/negative/visible weights from Ticket 14. The production path does not assume `P + N = V` and does not use RGB/contributor-alpha mass-conservation as a P/N/V admission gate.
- [ ] Far-neutral pixels produce no writes; work is limited to the declared positive/boundary/local-negative ROI without changing render traversal/occlusion semantics.

### RGB and Stable Mask binding

- [ ] A View used for production Direct Evidence has an authoritative RGB produced by the same `rasterImplementationId` and compatible render policy as the Direct Evidence traversal.
- [ ] The initial RGB-only mode and later mask-conditioned Evidence mode use the same Direct-Evidence-capable raster implementation; enabling Evidence writes must not change RGB for identical inputs.
- [ ] The Evidence attempt reuses the exact CameraBinding/render scope/Render Working Set and produces or verifies the same authoritative RGB digest bound to the Stable Mask.
- [ ] If the Evidence traversal RGB digest differs from the Stable Mask's bound RGB, no Evidence artifact publishes and the Mask is not silently rebound. Recovery is explicit rerender/review/regeneration under the new implementation identity.
- [ ] Migrating from the old stock RGB implementation to the Direct-Evidence-capable implementation bumps renderer identity and invalidates incompatible RGB/Mask/Evidence bindings rather than claiming equivalence without proof.
- [ ] Ticket 03's RGB-only path can switch to this implementation through the versioned renderer seam without changing Camera Inspection product semantics.

### Render and Evidence Working Sets

- [ ] Render Working Set contains every Gaussian in the declared authoritative render scope needed for RGB, occlusion, T, and termination.
- [ ] Evidence Working Set contains only target-local Core+Context Stable Gaussian IDs that receive P/N/V writes.
- [ ] Target and non-target/out-of-scope occluders remain in the raster traversal and map to `localEvidenceId = -1` or equivalent, so they affect RGB/T but receive no Evidence writes.
- [ ] Stable global-render identity → target Stable ID → Evidence-local mapping rejects missing, duplicate, colliding, and out-of-range identities.
- [ ] Full-render-scope and spatial Render Working Set produce equivalent RGB and production Evidence under the declared parity gate.
- [ ] Rasterizing only the Evidence Working Set is explicitly tested and rejected as incorrect.

### Artifact and incremental lifecycle

- [ ] GaussianEvidenceArtifact binds target/dependency identity, Camera, authoritative RGB digest, Stable Mask, Evidence Policy, Render/Evidence Working Sets, target Stable IDs, rasterImplementationId, Evidence backend identity, and runtime/build identity.
- [ ] Per-view artifact reuse validates every dependency and supports Exclude/reinclude, Stable Mask replacement, and incremental Re-Lift.
- [ ] Views may be processed sequentially; production does not require all Views' GPU P/N/V buffers resident simultaneously.
- [ ] GPU buffer scale is O(|Evidence Working Set| × channels) per processed View, excluding required renderer state; measured memory matches this contract.
- [ ] Restart Target and Regenerate Auto Views release unreferenced target-local artifacts without invalidating exact shared caches.

### Numerical and reference validation

- [ ] Reference-vs-production P/N/V agrees under a declared numeric policy and yields stable final classification.
- [ ] Compare max/p95/p99 absolute error, relative error, support differences, threshold-near Gaussians, and final class differences.
- [ ] The known CameraBinding that can fail complete Contributor/raster-alpha alignment produces stable Direct Evidence without invoking Contributor reconciliation.
- [ ] Repeat identical inputs enough times to characterize atomicAdd reduction-order variation; classification margins prevent flips.
- [ ] Strong positive/background classes agree with trusted reference; differences are limited to declared low-mass/boundary/threshold regions.
- [ ] Mixed large-footprint and unobserved fixtures preserve Uncertain semantics.

### Performance implementation order

- [ ] Begin with a simple global-atomic baseline after semantics are validated.
- [ ] Measure atomic contention, latency, VRAM, write bandwidth, and register pressure before adding tile/block reductions or sparse intermediates.
- [ ] Optimization order follows measured need: ROI restriction → Evidence Working Set writes → tile/block reduction → sparse intermediate/special high-contention handling.
- [ ] Every optimized path remains equivalent to the baseline Evidence semantics and Stable ID mapping.
- [ ] No silent truncation, overflow, nearest/top-k/distance/center/visibility-only fallback, or best-effort publication.

### Reference/debug boundary and resource lifecycle

- [ ] Complete Contributor remains available only behind explicit debug/reference capability and may fail without blocking successful RGB/Direct Evidence.
- [ ] The normal Direct Evidence request does not allocate, count, prefix-sum, serialize, hash, cache, or wait for complete Contributor output.
- [ ] Mask and Evidence artifact storage has explicit ownership/GC; current/referenced Stable Mask and Candidate inputs are never prematurely collected.
- [ ] Gallery thumbnail/texture lifecycle is bounded under 10–20+ Views.
- [ ] Working-set memory for RGB/Mask/Evidence/reference Contributor/thumbnail artifacts is measured separately.

## Failure / recovery criteria

- [ ] Evidence OOM/kernel/artifact failure preserves RGB/View/Stable Mask/Gallery and previous Candidate; no partial Evidence publishes.
- [ ] Same-pass RGB digest mismatch fails Evidence closed and does not silently mutate the Stable Mask binding.
- [ ] Identity/mapping/overflow failure never emits partial target Evidence.
- [ ] GC failure cannot delete current Stable Mask, current per-view Evidence, or current Candidate inputs.
- [ ] Reference Contributor failure affects diagnostics only.

## Validation

- Locked GPU same-decision tests
- RGB-only versus RGB+Evidence same-implementation digest test
- Old-renderer identity migration/invalidation test
- Known contributor-alpha mismatch CameraBinding regression
- Reference-vs-production P/N/V and classification fixtures
- Target plus non-target occluder fixture
- Full versus spatial Render Working Set RGB/Evidence parity
- P/N/V independence/no-mass-conservation tests
- Repeated-run classification stability
- Global-atomic baseline versus optimized implementation equivalence
- Large-scene memory/latency profile
- Mask/Evidence GC lifecycle tests
- Gallery resource stress

## Non-goals

- No hard-coded final classification inside CUDA
- No planner/assessment threshold calibration; Ticket 21 owns calibration
- No complete pixel-level provenance in the normal product artifact
- No DG-14 provenance UI