# 19 — Large SceneSnapshot + gsplat render/contributor cache hardening

Status: ready-for-agent

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

## What to build

Harden only the scene/render data path. Measure first, then change data layout/cache semantics required
for representative large scenes while preserving Stable IDs and exact dependency/version binding.

## Acceptance criteria

- [ ] Profile representative large SceneSnapshot creation, serialization/transfer, registration, and gsplat preparation costs before optimization.
- [ ] Validate or improve large SceneSnapshot data layout without changing Stable Gaussian ID semantics.
- [ ] SceneSnapshot/cache identity remains bound to scene/render/dependency versions and cannot reuse stale content after relevant mutation.
- [ ] Establish or reuse gsplat scene-tensor cache so repeated CameraBindings over the same valid snapshot do not redundantly rebuild immutable scene tensors.
- [ ] Establish render/contributor cache semantics keyed by CameraBinding/render/dependency identity and incapable of returning data for mismatched revisions.
- [ ] Clarify/validate Active Splat vs multi-visible-Splat AI render/contributor dependency scope.
- [ ] Cache invalidation works through semantic dependency identity and remains compatible with Suspended/exact-Undo recovery.
- [ ] Record measured before/after profile data and avoid speculative rewrites with no demonstrated bottleneck.

## Failure / recovery criteria

- [ ] Cache mismatch fails closed to recomputation rather than serving stale RGB/Contributor.
- [ ] Large-scene preparation failure does not mutate Native Selection or publish partial AI artifacts.

## Affected seams

- src/splat-scene-snapshot.ts
- Companion SceneSnapshot registration/cache
- Companion gsplat tensor/runtime cache
- Contributor render/cache
- Profiling harness

## Validation

- Full relevant tests
- Locked GPU representative large-scene profile
- Cache invalidation tests across CameraBinding/dependency mutations

## Non-goals

- No Evidence aggregation optimization
- No mask artifact GC
- No generic architecture rewrite
