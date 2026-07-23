# ADR 0014: Add Camera-aware Spatial Chunk Working Set v1

- **Status:** Accepted
- **Date:** 2026-07-22
- **Applies to:** `ai-select-v1`, Ticket 02B
- **Extends:** ADR 0013, Binary SceneSnapshot Registration v1
- **Protocol specification:** `docs/protocols/camera-aware-spatial-working-set-v1.md`

## Context

ADR 0013 removes the JSON/string-size failure mode by atomically registering a
complete typed SceneSnapshot. It still transfers and materializes every binary
chunk before the first Anchor render. On a large effective Target Splat this
can make an Anchor wait for data that cannot affect its fixed CameraBinding.

The SceneSnapshot must remain editor-owned and complete. A camera-specific
cache miss must not alter the semantic target state, and the Companion must
not render a convenient but incomplete visibility subset as authoritative RGB
or contributor evidence.

## Decision

Add Camera-aware Spatial Chunk Working Set v1 as an additive protocol and
runtime path.

1. Keep the 02A packed SoA snapshot and cached content digest as the complete
   `sceneVersion`. Camera/residency changes never construct a new scene
   identity.
2. Register a lightweight immutable global spatial manifest before any payload
   residency. The manifest describes every chunk and conservative support
   bounds derived from the effective editor data.
3. Have the Companion, not PlayCanvas or the browser, resolve a deterministic
   conservative working set from the exact versioned CameraBinding. Absent
   chunks return a bound `sceneChunkMiss`; the Editor uploads only that sorted
   set and retries the same logical Anchor request.
4. Store committed payloads as typed mmap chunks and assemble them with
   vectorized/tensor operations in global ordinal order. Tensor row IDs map to
   global Stable Gaussian IDs regardless of upload arrival order.
5. Retain a full-scene full-chunk/reference mode and fail closed or request all
   chunks whenever the spatial proof or resident state is not trustworthy.
6. Publish Anchor contributor identity from a versioned typed binary stream,
   with bounded tensor-to-CPU hashing, rather than first expanding the complete
   per-pixel stream into Python records or canonical JSON. The existing opaque
   `contributorDigest` wire field retains its meaning; the artifact version is
   embedded in the hashed bytes.

## Consequences

- A representative CameraBinding may transfer and materialize materially less
  than the complete Snapshot, while the logical SceneSnapshot remains exact.
- The new operation can be capability-gated without changing Selection Service
  protocol version `"1"` or changing the published 02A schema.
- The Editor pays a one-time deterministic spatial manifest/chunk-index build
  per cached effective Snapshot. This ticket does not implement per-edit deltas
  or general cache eviction.
- Correctness requires parity validation before claiming a benefit. A working
  selective flow without full/reference parity is not production renderer
  validation.
