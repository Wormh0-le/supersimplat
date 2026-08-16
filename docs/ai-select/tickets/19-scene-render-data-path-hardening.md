# 19 — Large SceneSnapshot + authoritative RGB / Render Working Set hardening

Status: closed — 2026-08-17; Final Spec v1.3 mapped; Ticket 20 is current

Blocked by: 18, 14

## Current Final Spec mapping

- Final Spec v1.3 §§3–5, 20–21, 24–25
- ADR 0013
- Final Spec v1.1 Amendment 001 as historical renderer/Evidence identity rationale only
- FlashSplat-style full-occlusion requirement
- MVP Phase 7 performance as historical implementation provenance

Final Spec v1.3 is the only current closure source.

## Inputs / preconditions

- Complete authoritative RGB path
- Reference Evidence/Lift contract
- Representative large Gaussian scenes
- Existing spatial SceneSnapshot implementation and measured profiles
- Editor fetch-adapter scene-miss recovery loops (five near-identical copies since Ticket 06, plus any added by Tickets 07–14): fold their dedup into this ticket as a first subtask — extract one parameterized recovery loop with the existing per-route tests as the safety net (Ticket 06 handoff)

## Outputs / handoff artifacts

- Validated large SceneSnapshot layout
- Declared authoritative AI render scope
- Conservative Render Working Set resolver/parity evidence
- gsplat scene tensor and RGB cache
- Explicit reference Contributor cache boundary
- Measured CPU/GPU/browser profile
- Anchor Server-Timing phase breakdown

## What to build

Harden the scene and authoritative render data path that Ticket 20 will reuse for FlashSplat-style Direct Evidence. Production cache semantics center on SceneSnapshot, declared render scope, Render Working Set, immutable gsplat tensors, and RGB. Complete Contributor may be cached only as reference/debug data and must not be a View-ready dependency.

The key invariant is not “all target Gaussians” but “all Gaussians in the declared authoritative AI render scope that can affect RGB, occlusion, transmittance, or termination.” Target-only rasterization is invalid when another visible Splat/primitive can occlude the target.

## Acceptance criteria

- [x] Profile large SceneSnapshot creation, transfer, registration, working-set resolution, gsplat preparation, RGB, PNG, and browser costs before optimization.
- [x] Expose additive Anchor `Server-Timing` diagnostics without changing current response semantics.
- [x] Capture representative browser/Companion/GPU phase and peak-memory profiles.
- [x] Validate/improve large SceneSnapshot layout without changing Stable ID semantics.
- [x] Scene/tensor/cache identity binds exact target/render/dependency versions.
- [x] Repeated CameraBindings over the same valid snapshot reuse immutable scene tensors.
- [x] RGB cache keys include CameraBinding, raster implementation/policy/runtime, Render Working Set, and dependency identity.
- [x] Authoritative RGB artifacts expose `rasterImplementationId` and `runtimeBuildId` required by Final Spec v1.3 identity and fail-closed rules.
- [x] Complete Contributor cache, when retained, is explicitly reference/debug and independently keyed; its absence/failure does not invalidate RGB.
- [x] Define the authoritative AI render scope for Active Target Splat plus other visible Splats/scene primitives that can affect the observation.
- [x] When non-target visible Gaussians can occlude or alter T, they are present in the Render Working Set as read-only occluders even though they are absent from the target Evidence Working Set.
- [x] Render-scope identity distinguishes target Stable IDs from non-target/occluder identity and prevents cross-Splat namespace collision.
- [x] A non-target occluder fixture demonstrates parity with the displayed/declared authoritative scene and fails if only the target Splat is rasterized.
- [x] Spatial Render Working Set is conservative and passes declared full-render-scope RGB/alpha parity; uncertain chunks are included or full fallback is used.
- [x] “Full Working Set” means the complete declared render scope for that CameraBinding, not merely every chunk of the Evidence Working Set.
- [x] Same WorkingSetToken yields deterministic Gaussian membership/order/identity digest.
- [x] Cache invalidation remains compatible with Suspended/exact Undo recovery.
- [x] Incompatible `rasterImplementationId` or `runtimeBuildId` cannot reuse old RGB/Mask/Evidence cache entries as production-compatible.
- [x] Record measured before/after results; avoid speculative rewrites.
- [x] Exercise browser-created effective snapshots with delete, world transform, palette, and color-grade edits; validate authoritative RGB/alpha and target Stable ID mapping. Reference Contributor parity is diagnostic, not the production gate.
- [x] Measure browser editor memory separately from Companion CPU/GPU memory.
- [x] Leave a versioned rasterImplementationId/capability seam so Ticket 20 can make the Direct Evidence-capable rasterizer the authoritative renderer for Evidence-bound Views.

## Failure / recovery criteria

- [x] Cache mismatch fails closed to recomputation, never stale RGB/Evidence.
- [x] Scene Chunk Miss or incomplete Render Working Set never publishes Ready RGB.
- [x] Unknown/ambiguous occluder scope fails conservatively rather than silently using target-only rendering.
- [x] Renderer implementation/runtime mismatch requires explicit rerender/review rather than silent Mask rebinding.
- [x] Large-scene failure does not mutate Native Selection or publish partial artifacts.

## Validation

- Full relevant tests
- Locked GPU representative large-scene profile
- Selective/full Render Working Set parity sweep
- Cross-Splat/non-target occluder parity fixture
- Cache invalidation across Camera/dependency/runtime/raster-implementation changes
- Old/new raster implementation cache separation and rerender fixture
- Browser effective-snapshot and memory profile

## Existing observability baseline — 2026-07-23

The Anchor route already exposes `working-set`, `gpu-queue`, `gsplat`, `contributor-digest`, `png`, and `json-base64` phases. `contributor-digest` denotes legacy/reference-path instrumentation and must not define the current Final Spec v1.3 production RGB contract.

## Non-goals

- No production Direct Evidence kernel
- No Mask/Evidence artifact GC
- No generic architecture rewrite

## Closure record — 2026-08-17

- The editor now declares one deterministic visible-Splat render scope. Target
  Stable IDs remain unchanged; read-only occluders receive collision-free
  render IDs and scope-row metadata.
- Packed and spatial manifests bind render-scope identity, and the spatial
  store retains deterministic WorkingSet membership plus reusable ordered
  tensors behind a bounded camera-keyed LRU.
- Authoritative RGB admission requires a validated scope on both transports;
  target support and geometry use only target rows while read-only occluders
  remain present for RGB rasterization.
- The locked backend caches immutable scene tensors independently from
  CameraBinding tensors. Companion RGB caching binds Camera, dependency,
  WorkingSet, raster implementation and runtime; reference Contributor data is
  cached independently.
- Anchor and Generated View RGB responses plus readiness capabilities expose
  `rasterImplementationId` and `runtimeBuildId` and fail closed on old values.
- The large-scene, browser-memory and locked-GPU measurements are recorded in
  [Ticket 19 large-scene render-path validation](../benchmarks/19-large-scene-render-path.md).
- The repeated editor scene-miss recovery loops were folded into bounded,
  parameterized packed and spatial recovery methods while retaining each
  route's existing failure diagnostics and tests.
- A production effective-snapshot export is committed through the Companion
  and checked for locked-renderer RGB/alpha parity in addition to the separate
  browser heap profile.
