# 19 — Large SceneSnapshot + gsplat render/contributor cache hardening

Status: ready-for-agent — 02B browser-validation transfer and Anchor timing baseline added

Blocked by: 18, 14

## Final Spec mapping

- §89 engineering items 2/3/11/13/14/19
- MVP Phase 7 performance

## Inputs / preconditions

- Complete Final Spec render/lift path
- Representative large Gaussian scenes
- Measured profiling data

## Outputs / handoff artifacts

- Validated large SceneSnapshot layout
- gsplat scene tensor cache
- render/contributor cache
- Measured profile
- Anchor `Server-Timing` phase breakdown

## What to build

Harden only the scene/render data path. Measure first, then change data layout/cache semantics required
for representative large scenes while preserving Stable IDs and exact dependency/version binding.

## Acceptance criteria

- [ ] Profile representative large SceneSnapshot creation, serialization/transfer, registration, and gsplat preparation costs before optimization.
- [x] Expose additive `Server-Timing` diagnostics on accepted Anchor-route
      responses:
      `working-set`, `gpu-queue`, `gsplat`, `contributor-digest`, `png`, and
      `json-base64`; preserve the existing JSON body and Selection Service
      protocol version.
- [ ] Capture a representative browser DevTools/response-header phase profile
      before using the timing data to justify an optimization.
- [ ] Validate or improve large SceneSnapshot data layout without changing Stable Gaussian ID semantics.
- [ ] SceneSnapshot/cache identity remains bound to scene/render/dependency versions and cannot reuse stale content after relevant mutation.
- [ ] Establish or reuse gsplat scene-tensor cache so repeated CameraBindings over the same valid snapshot do not redundantly rebuild immutable scene tensors.
- [ ] Establish render/contributor cache semantics keyed by CameraBinding/render/dependency identity and incapable of returning data for mismatched revisions.
- [ ] Clarify/validate Active Splat vs multi-visible-Splat AI render/contributor dependency scope.
- [ ] Cache invalidation works through semantic dependency identity and remains compatible with Suspended/exact-Undo recovery.
- [ ] Record measured before/after profile data and avoid speculative rewrites with no demonstrated bottleneck.
- [ ] **Transferred from 02B:** exercise a browser-created effective
      SceneSnapshot with delete, world-transform, transform-palette, and
      color-grade edits; establish selective/full RGB, alpha, contributor
      Stable-ID stream, and weight parity.
- [ ] **Transferred from 02B:** record browser editor peak memory for the real
      path separately from Companion CPU/GPU memory. Do not use direct typed-
      PLY harness RSS as an editor-memory surrogate.

## Failure / recovery criteria

- [ ] Cache mismatch fails closed to recomputation rather than serving stale RGB/Contributor.
- [ ] Large-scene preparation failure does not mutate Native Selection or publish partial AI artifacts.

## Affected seams

- src/splat-scene-snapshot.ts
- Companion SceneSnapshot registration/cache
- Companion gsplat tensor/runtime cache
- Contributor render/cache
- Profiling harness
- Anchor HTTP response timing instrumentation

## Validation

- Full relevant tests
- Locked GPU representative large-scene profile
- Cache invalidation tests across CameraBinding/dependency mutations
- Browser effective-snapshot/edit-mutation parity and browser-memory profile

## Initial observability baseline — 2026-07-23

`POST /ai-select/anchor-renders` now returns a standard `Server-Timing` header
without changing its JSON response body or protocol version. `working-set`
measures scene lookup/resolution; `gsplat`, `contributor-digest`, and `png`
measure the locked renderer's publication phases; `json-base64` aggregates
response base64 and JSON work; `gpu-queue` measures the Companion's single
Anchor admission/replay wait. The current Companion fails different concurrent
Anchor keys with `capacityFull` rather than queuing them, so this is not a CUDA
hardware scheduler measurement.

The baseline is instrumentation, not an optimization result. Use it with the
transferred browser fixture and memory measurements before selecting a Ticket 19
cache or data-path change.

## Non-goals

- No Evidence aggregation optimization
- No mask artifact GC
- No generic architecture rewrite
