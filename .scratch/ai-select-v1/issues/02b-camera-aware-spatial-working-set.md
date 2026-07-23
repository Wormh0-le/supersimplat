# 02B — Camera-aware Spatial Chunk Working Set

Status: implementation complete; browser-memory/manual lifecycle validation remains

Blocked by: Binary SceneSnapshot Registration v1 (02A)

## Objective

Keep one complete, immutable effective SceneSnapshot identity while allowing
the first authoritative Anchor render to upload and materialize only the
conservative spatial chunks that can affect its fixed CameraBinding.

```text
Current Anchor CameraBinding
    → Companion resolves conservative required chunks
    → sceneChunkMiss for absent payloads
    → editor uploads only those immutable chunks
    → retry same logical Anchor request
    → deterministic gsplat RGB + Contributor
```

## Authority and compatibility

- Preserve 02A's editor-owned effective SoA representation, cached strong
  content digest, bounded raw binary transfer, atomic commit, and typed/mmap
  Companion path.
- Do not introduce per-Gaussian JS/Python record graphs, giant JSON, base64,
  source-PLY shortcuts, or PlayCanvas visibility as AI truth.
- Keep 02A's complete packed-snapshot registration as a full-scene reference
  and fail-safe path. The extension is additive; published v1 field meanings
  are not reinterpreted.
- `sceneVersion` identifies complete effective Target Splat state, `chunkId +
chunkDigest` identify immutable spatial payloads, and `workingSetToken`
  identifies the ordered camera-required subset. Camera/residency changes never
  change `sceneVersion`.

## Design seam

Protocol/format design is committed before implementation in
`docs/protocols/camera-aware-spatial-working-set-v1.md`; ADR 0014 records the
decision. This is additive to 02A and keeps Selection Service protocol `"1"`.

### Global spatial manifest

Register a lightweight, logically complete manifest before payload residency.
It contains protocol/schema identity, `sceneId`, `sceneVersion`, target
identity, complete effective Gaussian count, coordinate/render semantics,
Stable-ID schema, and every spatial chunk's `chunkId`, digest, byte length,
Gaussian count, global-order range, and conservative world-space support
bounds. A manifest is valid while zero chunks are resident.

Chunks are built from 02A effective values after delete filtering, world and
palette transforms, effective rotation/scale, color grading, DC/SH handling,
and Stable-ID preservation.

### Conservative selection

Each chunk bound encloses all finite raster support of its Gaussian payloads,
including rotated anisotropic scale and locked-rasterizer alpha/validity
semantics plus a documented float/projection margin. The Companion alone uses
the exact CameraBinding frustum/clipping range to resolve a sorted required
chunk list. Ambiguity, missing bounds, invalid manifest, inconsistency, or
failed parity must fall back to all chunks or fail closed—never an incomplete
Ready render.

### Residency and deterministic assembly

`sceneChunkMiss` returns the unchanged request/camera binding, `sceneId`,
`sceneVersion`, deterministic `workingSetToken`, and sorted missing `chunkId`s.
The editor uploads only those chunks using idempotent raw binary requests and
retries the identical logical Anchor request. The Companion validates digest and
identity before residency, then assembles tensor rows in stored global ordinal
order—not arrival/cache order—and maps contributors back to global Stable IDs.

## TDD seams

1. Support-bound computation and conservative frustum intersection.
2. Global manifest/chunk identity separate from physical residency.
3. Deterministic working-set resolution and token formation.
4. `sceneChunkMiss` → selective raw upload → retry with preserved
   `AIRequestBinding`.
5. Deterministic tensor assembly and global Stable-ID contributor remapping.
6. Full-scene/reference versus selective parity and fallback.
7. Typed Anchor contributor publication: full Stable-ID stream, mass
   conservation, bounded binary hashing, and no legacy list/object dispatch.

## Acceptance criteria

- [x] Anchor registers one complete global manifest but does not require all
      chunk payloads when a conservative subset suffices.
- [x] Required IDs are deterministic/sorted; only returned missing chunks are
      uploaded and retries are idempotent.
- [x] Camera or residency changes do not rebuild packed data or change
      `sceneVersion`.
- [x] Every selected chunk has conservative support bounds; center-only,
      occlusion, visible-only, and top-k culling are forbidden.
- [x] Missing/corrupt/wrong-version/wrong-scene chunks cannot make a render
      Ready; partial working sets never publish authoritative artifacts.
- [x] Tensor order and Stable-ID contributor mapping are identical across chunk
      upload/cache arrival orders.
- [x] Full-scene reference/fallback remains available and parity gates
      selective rendering.
- [x] Authoritative Anchor publication keeps complete contributor tensors typed
      through Stable-ID remapping and bounded binary digesting; it does not
      expand them into `ContributorSample` objects or canonical JSON.
- [ ] Fixtures cover SH0–SH3, delete/world/palette/color transforms,
      anisotropic center-outside/support-inside and clipping boundaries, and
      different chunk arrival orders.
- [ ] Real representative SH3 metrics record total/selective bytes, timings,
      editor/CPU/GPU memory, and full/selective parity before claiming benefit.

The locked GPU suite now covers SH0–SH3, typed effective transformed values,
deleted-ID absence, deterministic reverse arrival, contributor Stable-ID
remapping, RGB/alpha/weight parity, and the full reference path. Existing
resolver/store tests cover rotated anisotropic center-outside support,
near/far boundaries, ambiguity/all-chunk fallback, corrupt bytes, wrong scene,
duplicate retry, incomplete commit, and release. A browser-driven editor
fixture for active delete/world/palette/color edits and browser peak-memory
instrumentation remain open; they are not represented as complete here.

## Validation record — 2026-07-23

- [x] Locked CUDA GPU SH0–SH3 full/selective parity:
      `selection-service-companion/tests/test_spatial_scene_gpu_parity.py`.
- [x] Real 954,603-Gaussian SH3 PLY selective/full parity and metrics:
      [02b-real-sh3-result.md](../benchmarks/02b-real-sh3-result.md).
- [x] The measured fixed non-empty Anchor needed 37/223 chunks (38,793,316 /
      232,923,132 bytes; 16.655%) and had exact RGB, alpha, Stable-ID, and weight
      parity. It therefore materially reduced transferred bytes and locked GPU
      allocation for that view.
- [x] Locked CUDA typed Anchor publication test rejects the legacy list path;
      fixed binary digest tests retain complete mass, tensor-row order, and the
      valid uint32 Stable ID `0xffffffff`.
- [x] On the 331,150-Gaussian restroom SH0 fixture, a cold 1024² selective
      Anchor completed gsplat plus typed publication in 0.445 s in the locked
      harness (6/21 chunks; 25.786% of payload bytes), with exact selective/full
      RGB, alpha, Stable-ID, and weight parity.
- [x] On the 954,603-Gaussian SH3 fixture, a cold 512² selective Anchor
      completed gsplat plus typed publication in 0.585 s (37/223 chunks;
      16.655% of payload bytes), with exact selective/full parity.
- [ ] Browser editor peak memory and a browser-generated effective SceneSnapshot
      with active edit mutations have not yet been measured. Do not treat the
      direct typed-Ply harness RSS as editor memory.

## Manual validation links

- `02-G1` (persistent collapsed AI Views dock) remains a Ticket 02 shell gap;
  it is not changed by this transport/runtime ticket.
- `02-G2` (Anchor must reach Ready or a terminal actionable failure state)
  remains a Ticket 02 lifecycle gap. This ticket removes full-scene residency
  as one likely cause but does not reassign the shell lifecycle requirement.
- `03-G1` (interactive Frustum translation/rotation) is Ticket 03, not 02B.

## Non-goals

- Per-edit delta or Merkle synchronization.
- Mask/ROI-driven culling, occlusion culling, Generated/User View workflows,
  Camera Inspection UI, Candidate/Lifting changes, provenance UI, or a
  cross-scene LRU/memory-pressure manager.
