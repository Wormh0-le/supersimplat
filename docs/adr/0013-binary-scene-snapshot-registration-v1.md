# ADR 0013: Use Binary SceneSnapshot Registration v1

- **Status:** Accepted
- **Date:** 2026-07-22
- **Applies to:** `ai-select-v1`, Ticket 02A
- **Protocol specification:** `docs/protocols/binary-scene-snapshot-registration-v1.md`

## Context

The first authoritative Anchor tracer bullet represents an editor-owned effective
SceneSnapshot as a JSON array of per-Gaussian objects. It then serializes that
array once to derive `sceneVersion` and again to register the snapshot with the
Companion. Large SH3 scenes can exceed the JavaScript maximum string length
before the Companion receives any request.

The problem is the representation and registration transport, not the authority
boundary. The Companion still needs the effective Target Splat geometry,
appearance, transforms, and editor-owned Stable Gaussian IDs in order to render
authoritative gsplat RGB/contributor observations and lift masks to Native
Selection.

## Decision

Adopt **Binary SceneSnapshot Registration v1** for the editor-to-Companion
registration path.

1. The Editor continues to own the effective SceneSnapshot and Stable Gaussian
   IDs. The protocol does not substitute an editor screenshot, source PLY path,
   source PLY contents, or a Companion-side reconstruction.
2. The Editor materializes the effective snapshot as a structure-of-arrays
   (SoA) collection of typed binary planes. It never creates a per-Gaussian JS
   record array, base64-encodes the planes, or JSON-serializes the full payload.
3. A SHA-256 **Snapshot Content Digest** is incrementally computed over the
   format's canonical logical bytes and cached with the packed snapshot. It is
   independent of upload chunk size and distinct from the editor semantic
   `TargetDependencyToken`.
4. A small, versioned JSON manifest describes the logical packed data and a
   bounded chunk transfer plan. Raw binary chunks are verified independently;
   the Companion publishes the snapshot to its runtime cache only after an
   explicit, successful atomic commit.
5. The Companion retains committed binary data as a typed/mmap-backed
   `PackedSceneSnapshot`. It must not expand a binary upload into a
   per-Gaussian `dict`/`list` collection or a canonical giant JSON string.
   gsplat consumes typed tensor views directly.
6. Begin, chunk upload, and commit are idempotent where their identities match.
   Immutable conflicts, incomplete uploads, malformed chunks, and expired
   staging uploads fail closed and never expose a partial cache entry.

The existing JSON SceneSnapshot endpoint remains a legacy compatibility path for
frozen fixtures during migration. New Editor AI Select registration uses only
Binary SceneSnapshot Registration v1.

## Consequences

- Large SH3 snapshots no longer depend on a single JavaScript string or JSON
  object graph.
- Snapshot identity stays strong and reproducible across retry and differing
  transport chunk sizes.
- The wire change is an editor/Companion vertical slice: capability gating,
  TypeScript transport, Python HTTP routes, staging state, typed renderer
  ingestion, and contract tests evolve together.
- This decision deliberately does **not** add per-edit delta synchronization,
  persistent semantic storage, a source-Ply shortcut, or Ticket 19's broader
  cache/performance work.
