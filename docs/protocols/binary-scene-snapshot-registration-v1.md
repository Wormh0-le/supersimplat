# Binary SceneSnapshot Registration v1

## Scope

This specification defines the versioned Editor-to-Companion registration path
for an effective, editor-owned SceneSnapshot. It is the Ticket 02A format and
transport contract.

It preserves the Final Spec authority model:

```text
Editor effective Target Splat + Stable IDs
    -> packed binary SceneSnapshot
    -> Companion gsplat RGB / contributor
    -> mask lifting
```

It does not define per-edit delta synchronization, project persistence, a PLY
path protocol, or a public/multi-user upload service.

## Capability and versioning

The existing Selection Service protocol version remains `"1"`. A Companion
that implements this contract advertises:

```json
{
    "supportedOperations": ["binarySceneSnapshotRegistrationV1"]
}
```

The Editor requires this operation before it uses the binary registration path.
A Companion without it is incompatible for this Editor version; it is not a
candidate for a silent JSON fallback.

The manifest contains:

```text
format: "supersplat-packed-scene-snapshot"
formatVersion: 1
```

## Logical packed snapshot

All data is little-endian. The Editor builds effective values after applying
the current Target Splat world/palette transforms and color-grade policy. It
does not preserve source PLY row meaning as protocol identity.

For `N = gaussianCount` and `S = shFloatCountPerGaussian`, the logical payload
is the following contiguous sequence of SoA planes:

| Order | Field            | Type        | Element count |
| ----- | ---------------- | ----------- | ------------- |
| 0     | `stableIds`      | `uint32le`  | `N`           |
| 1     | `means`          | `float32le` | `N * 3`       |
| 2     | `rotationsXyzw`  | `float32le` | `N * 4`       |
| 3     | `logScales`      | `float32le` | `N * 3`       |
| 4     | `logitOpacities` | `float32le` | `N`           |
| 5     | `dc`             | `float32le` | `N * 3`       |
| 6     | `sh`             | `float32le` | `N * S`       |

`S` is one of `0`, `9`, `24`, or `45`. The fields are views over typed buffers;
the Editor must not create `N` object records. A chunk may cross a field
boundary. Payload offsets and byte lengths are derived solely from the table.

The logical manifest binds:

- coordinate convention and Stable ID schema;
- Gaussian count, `S`, and the field layout;
- effective appearance policy and attribute schema;
- render configuration version, rasterizer, alpha mode, SH bands, and RGBA
  background;
- the content digest and payload byte length.

`sceneId` binds an Editor target namespace but is not a substitute for content
identity. `sceneVersion` in existing Anchor request/result bindings is the
registered Snapshot Content Digest. It is never a `TargetDependencyToken`.

## Snapshot Content Digest

The Snapshot Content Digest is `sha256:<lowercase-hex>` over canonical logical
bytes, not over JSON and not over upload chunks.

The canonical byte sequence is:

1. UTF-8 bytes of `supersplat-packed-scene-snapshot-v1\0`;
2. the following UTF-8 strings, each encoded as
   `uint32le(byteLength) + UTF-8 bytes`, in exactly this order:
   `coordinateConvention`, `stableIdSchema`, `attributeSchema`,
   `appearancePolicy`, `renderConfiguration.version`,
   `renderConfiguration.alphaMode`, `renderConfiguration.rasterizer`;
3. `uint32le(N)`, `uint32le(S)`, and
   `uint32le(renderConfiguration.shBands)`;
4. the four `float32le` values of `renderConfiguration.backgroundRgba`, in
   RGBA order;
5. `uint32le` component counts in plane order:
   `1, 3, 4, 3, 1, 3, S`;
6. all seven planes in the order above, as their raw little-endian bytes.

`sceneId` is a registration namespace, not a content byte, and is deliberately
excluded from the digest. `sceneVersion` is required to equal the resulting
content digest.

The content digest deliberately excludes the transfer chunk size, upload ID,
chunk boundaries, chunk hashes, retry count, and timestamps. The Editor updates
the digest incrementally while building/reading the typed planes and caches the
result on the packed snapshot. `isCurrent()` and `TargetDependencyToken`
comparison must not rebuild or rehash all Gaussian values.

## TargetDependencyToken separation

The Editor's semantic `TargetDependencyToken` controls Current Target Context
suspension and stale-result rejection. It is built from editor semantic
revisions for render state, geometry, Gaussian identity/membership, and world
transform. It is neither derived from nor replaced by the Snapshot Content
Digest.

The content digest instead identifies one immutable effective byte payload for
Companion cache/registration. An unchanged dependency revision may reuse its
cached packed snapshot and digest; a changed dependency revision causes a new
packed snapshot build before a new registration.

## Transport manifest and endpoints

The transport manifest is a small JSON object. Its `content` section is the
logical manifest described above. Its `transfer` section is explicitly excluded
from Snapshot Content Digest calculation:

```json
{
    "format": "supersplat-packed-scene-snapshot",
    "formatVersion": 1,
    "sceneId": "editor-splat:42",
    "sceneVersion": "sha256:...",
    "contentDigest": "sha256:...",
    "content": { "...": "logical manifest fields" },
    "transfer": {
        "chunkByteLength": 4194304,
        "chunks": [
            {
                "index": 0,
                "offset": 0,
                "byteLength": 4194304,
                "digest": "sha256:..."
            }
        ]
    }
}
```

`chunkByteLength` is at most 4 MiB. Each final chunk may be smaller. There are
at most 4096 chunks and the request manifest is at most 2 MiB. The Companion
rejects malformed, overlapping, gapped, or out-of-range chunk plans. A raw
chunk body uses `application/octet-stream`; no payload field is base64 encoded.

The browser protocol is:

| Step         | Request                                                                                                      | Success result                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| Begin/resume | `POST /scene-snapshot-uploads/v1` with transport manifest                                                    | staged upload ID + missing chunk indices, or already committed |
| Chunk        | `PUT /scene-snapshot-uploads/v1/{uploadId}/chunks/{index}` with raw bytes and `X-SceneSnapshot-Chunk-Digest` | stored or idempotently already stored                          |
| Commit       | `POST /scene-snapshot-uploads/v1/{uploadId}/commit`                                                          | committed or already committed SceneSnapshot binding           |
| Abort        | `DELETE /scene-snapshot-uploads/v1/{uploadId}`                                                               | idempotent staging cleanup                                     |

The begin request has a deterministic idempotency identity over the full
transport manifest. A lost begin response may therefore be retried safely. A
changed transfer chunk size has a different staging identity but the same
Snapshot Content Digest and final registered SceneSnapshot identity.

## Staging, commit, and cleanup

The Companion maintains a disposable runtime staging area separate from its
committed SceneSnapshot cache.

- Begin validates the small manifest only and creates or resumes an isolated
  staging record. It does not publish to the cache.
- Chunk upload verifies route/upload/index bindings, exact byte length, and the
  declared per-chunk SHA-256. A repeated identical chunk succeeds; a different
  byte sequence for an occupied chunk is an immutable conflict.
- Commit requires every declared chunk, recomputes the canonical Snapshot
  Content Digest over the logical bytes, validates typed layout/finite values,
  and atomically installs a typed/mmap-backed `PackedSceneSnapshot` in the
  runtime cache. A failure preserves any prior committed snapshot and publishes
  no partial replacement.
- A conflicting logical manifest for an existing `(sceneId, sceneVersion)` is
  rejected. A completed identical registration is idempotent. For the bounded
  staging TTL, a repeated commit for the same upload ID returns
  `alreadyCommitted`; after that TTL, Begin/resume returns the committed
  identity instead.
- Explicit abort, failed commit, and a bounded TTL clean incomplete staging
  uploads. Cleanup never removes a committed cache entry.

The committed representation exposes typed field views. The gsplat backend uses
vectorized/tensor conversion from these views; it does not rebuild a giant JSON
string or a list/dict per Gaussian.

## Test seams

The public seams for Ticket 02A are:

1. TypeScript `buildPackedSceneSnapshot()` and
   `createBinarySceneSnapshotManifest()` — SoA layout, digest, bounded chunk
   plan, and digest independence from transfer chunking.
2. TypeScript `BinarySceneSnapshotRegistrar.register()` — begin/resume, missing
   chunks, raw binary upload, retry, abort, and atomic commit behavior through a
   narrow transport adapter.
3. Python `BinarySceneSnapshotUploadStore` — staged upload lifecycle, chunk
   validation, conflict/idempotence, incomplete-upload cleanup, and atomic
   typed snapshot publication.
