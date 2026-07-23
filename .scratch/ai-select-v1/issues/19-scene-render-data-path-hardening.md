# 19 — Large SceneSnapshot + authoritative RGB / Render Working Set hardening

Status: ready-for-agent — v2.2 re-audited; prior 02B observability baseline retained

Blocked by: 18, 14

## Final Spec mapping

- Final Spec v1.1 §§5, 17–19, 30 Stage 4, 31
- ADR 0013
- MVP Phase 7 performance

## Inputs / preconditions

- Complete authoritative RGB path
- Reference Evidence/Lift contract
- Representative large Gaussian scenes
- Existing spatial SceneSnapshot implementation and measured profiles

## Outputs / handoff artifacts

- Validated large SceneSnapshot layout
- Conservative Render Working Set resolver/parity evidence
- gsplat scene tensor and RGB cache
- Explicit reference Contributor cache boundary
- Measured CPU/GPU/browser profile
- Anchor Server-Timing phase breakdown

## What to build

Harden the scene and authoritative render data path. Production cache semantics center on SceneSnapshot, Render Working Set, immutable gsplat tensors, and RGB. Complete Contributor may be cached only as reference/debug data and must not be a View-ready dependency.

## Acceptance criteria

- [ ] Profile large SceneSnapshot creation, transfer, registration, working-set resolution, gsplat preparation, RGB, PNG, and browser costs before optimization.
- [x] Expose additive Anchor `Server-Timing` diagnostics without changing current response semantics.
- [ ] Capture representative browser/Companion/GPU phase and peak-memory profiles.
- [ ] Validate/improve large SceneSnapshot layout without changing Stable ID semantics.
- [ ] Scene/tensor/cache identity binds exact target/render/dependency versions.
- [ ] Repeated CameraBindings over the same valid snapshot reuse immutable scene tensors.
- [ ] RGB cache keys include CameraBinding, render policy/runtime, Render Working Set, and dependency identity.
- [ ] Complete Contributor cache, when retained, is explicitly reference/debug and independently keyed; its absence/failure does not invalidate RGB.
- [ ] Define Active Splat versus other visible-Splat dependency scope for authoritative occlusion/rendering.
- [ ] Spatial Render Working Set is conservative and passes declared full-scene RGB/alpha parity; uncertain chunks are included or full fallback is used.
- [ ] Same WorkingSetToken yields deterministic Gaussian membership/order/Stable ID digest.
- [ ] Cache invalidation remains compatible with Suspended/exact Undo recovery.
- [ ] Record measured before/after results; avoid speculative rewrites.
- [ ] Exercise browser-created effective snapshots with delete, world transform, palette, and color-grade edits; validate authoritative RGB/alpha and Stable ID mapping. Reference Contributor parity is diagnostic, not the production gate.
- [ ] Measure browser editor memory separately from Companion CPU/GPU memory.

## Failure / recovery criteria

- [ ] Cache mismatch fails closed to recomputation, never stale RGB/Evidence.
- [ ] Scene Chunk Miss or incomplete Render Working Set never publishes Ready RGB.
- [ ] Large-scene failure does not mutate Native Selection or publish partial artifacts.

## Validation

- Full relevant tests
- Locked GPU representative large-scene profile
- Selective/full Render Working Set parity sweep
- Cache invalidation across Camera/dependency/runtime changes
- Browser effective-snapshot and memory profile

## Existing observability baseline — 2026-07-23

The Anchor route already exposes `working-set`, `gpu-queue`, `gsplat`, `contributor-digest`, `png`, and `json-base64` phases. `contributor-digest` now denotes legacy/reference-path instrumentation and must not define the v1.1 production RGB contract.

## Non-goals

- No production Direct Evidence kernel
- No Mask/Evidence artifact GC
- No generic architecture rewrite