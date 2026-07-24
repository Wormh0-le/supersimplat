# 19 — Large SceneSnapshot + authoritative RGB / Render Working Set hardening

Status: ready-for-agent — v2.2 FlashSplat-alignment review; prior 02B observability baseline retained

Blocked by: 18, 14

## Final Spec mapping

- Final Spec v1.1 §§5, 17–19, 30 Stage 4, 31
- Final Spec v1.1 Amendment 001 — Renderer / Evidence Implementation Identity and RGB Continuity
- ADR 0013
- FlashSplat-style full-occlusion requirement
- MVP Phase 7 performance

## Inputs / preconditions

- Complete authoritative RGB path
- Reference Evidence/Lift contract
- Representative large Gaussian scenes
- Existing spatial SceneSnapshot implementation and measured profiles

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

- [ ] Profile large SceneSnapshot creation, transfer, registration, working-set resolution, gsplat preparation, RGB, PNG, and browser costs before optimization.
- [x] Expose additive Anchor `Server-Timing` diagnostics without changing current response semantics.
- [ ] Capture representative browser/Companion/GPU phase and peak-memory profiles.
- [ ] Validate/improve large SceneSnapshot layout without changing Stable ID semantics.
- [ ] Scene/tensor/cache identity binds exact target/render/dependency versions.
- [ ] Repeated CameraBindings over the same valid snapshot reuse immutable scene tensors.
- [ ] RGB cache keys include CameraBinding, raster implementation/policy/runtime, Render Working Set, and dependency identity.
- [ ] Authoritative RGB artifacts expose `rasterImplementationId` and `runtimeBuildId` required by Final Spec v1.1 Amendment 001.
- [ ] Complete Contributor cache, when retained, is explicitly reference/debug and independently keyed; its absence/failure does not invalidate RGB.
- [ ] Define the authoritative AI render scope for Active Target Splat plus other visible Splats/scene primitives that can affect the observation.
- [ ] When non-target visible Gaussians can occlude or alter T, they are present in the Render Working Set as read-only occluders even though they are absent from the target Evidence Working Set.
- [ ] Render-scope identity distinguishes target Stable IDs from non-target/occluder identity and prevents cross-Splat namespace collision.
- [ ] A non-target occluder fixture demonstrates parity with the displayed/declared authoritative scene and fails if only the target Splat is rasterized.
- [ ] Spatial Render Working Set is conservative and passes declared full-render-scope RGB/alpha parity; uncertain chunks are included or full fallback is used.
- [ ] “Full Working Set” means the complete declared render scope for that CameraBinding, not merely every chunk of the Evidence Working Set.
- [ ] Same WorkingSetToken yields deterministic Gaussian membership/order/identity digest.
- [ ] Cache invalidation remains compatible with Suspended/exact Undo recovery.
- [ ] Incompatible `rasterImplementationId` or `runtimeBuildId` cannot reuse old RGB/Mask/Evidence cache entries as production-compatible.
- [ ] Record measured before/after results; avoid speculative rewrites.
- [ ] Exercise browser-created effective snapshots with delete, world transform, palette, and color-grade edits; validate authoritative RGB/alpha and target Stable ID mapping. Reference Contributor parity is diagnostic, not the production gate.
- [ ] Measure browser editor memory separately from Companion CPU/GPU memory.
- [ ] Leave a versioned rasterImplementationId/capability seam so Ticket 20 can make the Direct Evidence-capable rasterizer the authoritative renderer for Evidence-bound Views.

## Failure / recovery criteria

- [ ] Cache mismatch fails closed to recomputation, never stale RGB/Evidence.
- [ ] Scene Chunk Miss or incomplete Render Working Set never publishes Ready RGB.
- [ ] Unknown/ambiguous occluder scope fails conservatively rather than silently using target-only rendering.
- [ ] Renderer implementation/runtime mismatch requires explicit rerender/review rather than silent Mask rebinding.
- [ ] Large-scene failure does not mutate Native Selection or publish partial artifacts.

## Validation

- Full relevant tests
- Locked GPU representative large-scene profile
- Selective/full Render Working Set parity sweep
- Cross-Splat/non-target occluder parity fixture
- Cache invalidation across Camera/dependency/runtime/raster-implementation changes
- Old/new raster implementation cache separation and rerender fixture
- Browser effective-snapshot and memory profile

## Existing observability baseline — 2026-07-23

The Anchor route already exposes `working-set`, `gpu-queue`, `gsplat`, `contributor-digest`, `png`, and `json-base64` phases. `contributor-digest` denotes legacy/reference-path instrumentation and must not define the v1.1 production RGB contract.

## Non-goals

- No production Direct Evidence kernel
- No Mask/Evidence artifact GC
- No generic architecture rewrite