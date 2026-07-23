# Camera-aware Spatial Chunk Working Set v1

## Scope

This specification defines the additive Ticket 02B extension to Binary
SceneSnapshot Registration v1 (02A). It lets the Companion render an
authoritative observation from a conservative, CameraBinding-specific subset
of the effective editor SceneSnapshot.

It does not change the 02A packed snapshot format, its canonical content
digest, or the meaning of any 02A field. The 02A full-scene registration path
remains the compatibility and reference-render path.

```text
effective Packed SceneSnapshot (02A)
    -> immutable global spatial manifest
    -> Companion resolves CameraBinding working set
    -> sceneChunkMiss for non-resident payloads
    -> raw bounded chunk upload + atomic commit
    -> deterministic typed/tensor working set
    -> gsplat RGB / alpha / contributor Stable IDs
```

## Capability and wire discipline

The Selection Service protocol version remains `"1"`. A compatible Companion
advertises both existing operations and the additive operation:

```json
{
    "supportedOperations": [
        "binarySceneSnapshotRegistrationV1",
        "cameraAwareSpatialWorkingSetV1"
    ]
}
```

The Editor uses selective residency only when the second operation is present.
Otherwise it continues using the 02A full-snapshot route; it never silently
falls back to a JSON, base64, source-PLY, or editor-framebuffer path.

The new manifest is a separate schema:

```text
format: "supersplat-spatial-scene-manifest"
formatVersion: 1
chunkFormat: "supersplat-spatial-scene-chunk"
chunkFormatVersion: 1
```

The existing `supersplat-packed-scene-snapshot` format remains version 1 with
its published semantics unchanged.

## Independent identities

Three identities are deliberately independent:

| Identity                  | Meaning                                                                                                 | Changes when                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `sceneVersion`            | Complete effective Target Splat content identity. It is exactly the cached 02A Snapshot Content Digest. | Effective editor render/geometry/identity/world state changes. |
| `chunkId` + `chunkDigest` | One immutable spatial payload inside that scene.                                                        | Its partitioned typed bytes change.                            |
| `workingSetToken`         | The ordered required chunk set for an exact CameraBinding.                                              | CameraBinding or required descriptor set changes.              |

Chunk arrival, retry count, transport batch size, cache residency, and another
camera asking for additional chunks do not change `sceneVersion`.
`TargetDependencyToken` remains an editor semantic revision identity and is
not derived from any of these values.

## Global manifest and spatial payloads

The Editor builds a spatial manifest from the same cached 02A effective SoA
planes. In particular, deletion filtering, world and transform-palette edits,
rotation and scale, color grade, DC/SH semantics, and global Stable Gaussian
IDs are already applied before spatial partitioning. Source PLY rows and
PlayCanvas visibility are not inputs to the protocol.

The manifest is a bounded JSON control-plane object and contains:

- schema/protocol version, `sceneId`, `sceneVersion`, and `contentDigest`;
- Target Splat identity and total effective Gaussian count;
- coordinate convention, Stable ID schema, attribute schema, appearance
  policy, SH count, and locked render configuration;
- every chunk's `chunkId`, `chunkDigest`, byte length, Gaussian count,
  global-ordinal metadata, and conservative support bounds.

It is logically complete before any payload is resident. Registration validates
and atomically publishes this small immutable manifest only; it does not imply
that a renderer may use a partial set of payloads.

Each spatial payload is a little-endian SoA sequence for `M` rows:

| Order | Field            | Type        | Elements |
| ----- | ---------------- | ----------- | -------- |
| 0     | `globalOrdinals` | `uint32le`  | `M`      |
| 1     | `stableIds`      | `uint32le`  | `M`      |
| 2     | `means`          | `float32le` | `M * 3`  |
| 3     | `rotationsXyzw`  | `float32le` | `M * 4`  |
| 4     | `logScales`      | `float32le` | `M * 3`  |
| 5     | `logitOpacities` | `float32le` | `M`      |
| 6     | `dc`             | `float32le` | `M * 3`  |
| 7     | `sh`             | `float32le` | `M * S`  |

`globalOrdinals` identify the source row in the complete 02A logical order.
They are not Stable IDs and never cross the contributor protocol as identity.
They let the Companion restore exact full-scene tensor order regardless of
spatial partitioning, HTTP completion order, or resident-cache order.

Spatial chunks use deterministic Morton-ordered groups with a fixed bounded
payload limit. The partitioning algorithm may change only behind a new spatial
manifest format version. A chunk digest is SHA-256 over exactly the typed bytes
above. It is independent of upload batching and network retry boundaries.

## Conservative support bounds

The locked classic gsplat contributor validity cut is
`tau = 1 / 255`. For a Gaussian with effective opacity
`p = sigmoid(logitOpacity)`, normalized effective rotation `R`, and effective
axis scales `s = exp(logScale)`, the finite alpha support used by the locked
renderer is bounded by:

```text
alpha = p * exp(-0.5 * q) >= tau
k = sqrt(max(0, 2 * ln(max(p, tau) / tau)))
axisExtent[i] = k * sqrt(sum_j((R[i,j] * s[j])^2)) + epsilonWorld
```

The resulting world-space AABB is `mean +/- axisExtent`. `epsilonWorld` is
`1e-5 + 2^-18 * max(1, max(s))`; the resolver additionally widens each image
plane by two output pixels and widens near/far comparisons by the same
world-space margin. These are deliberate float32 and projection-boundary
safety margins, not a visibility heuristic.

A Gaussian is marked empty only if its float32-safe opacity is below
`tau * (1 - 2^-12)`. Values in the boundary guard band are retained with at
least the safety AABB even when their mathematical radius is zero. Non-finite
values, non-normalizable rotations, unsafe scale/radius values, missing bounds,
or a camera/support relationship for which a finite reject cannot be proven
make the resolver include all chunks rather than cull.

Chunk bounds union every non-empty member AABB. The Companion may reject a
chunk only when that complete bound lies beyond one expanded camera-frustum or
clipping half-space. It must never reject based on a Gaussian center alone,
PlayCanvas visibility, occlusion, an apparent-size threshold, or top-k
visibility. Near-plane, far-plane, and uncertain perspective cases are
included.

## Manifest, residency, and render flow

The endpoint family is intentionally separate from 02A:

| Step                     | Request                                                           | Result                                                                                                         |
| ------------------------ | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Register manifest        | `POST /spatial-scene-manifests/v1`                                | immutable `registered` / `alreadyRegistered` binding with `registrationId`, scene/version, and `contentDigest` |
| Begin payload batch      | `POST /spatial-scene-chunk-uploads/v1`                            | bounded staged batch and missing chunk IDs                                                                     |
| Upload chunk             | `PUT /spatial-scene-chunk-uploads/v1/{uploadId}/chunks/{chunkId}` | raw `application/octet-stream`, digest-verified and idempotent                                                 |
| Commit batch             | `POST /spatial-scene-chunk-uploads/v1/{uploadId}/commit`          | every staged chunk atomically becomes resident                                                                 |
| Abort batch              | `DELETE /spatial-scene-chunk-uploads/v1/{uploadId}`               | idempotent staging cleanup                                                                                     |
| Release target residency | `DELETE /spatial-scene-manifests/v1/{registrationId}`             | target-local cache release                                                                                     |

The Editor's nominal spatial payload target is 1 MiB; every payload remains
bounded at 4 MiB, uses no base64, and includes
`X-Spatial-Scene-Chunk-Digest`. Begin/PUT/commit are retry-safe for equal
identities. A mismatched digest, scene/version, schema, descriptor, or
overwrite is an immutable conflict. Incomplete stages are cleaned by explicit
abort or bounded TTL and are never resident.

After the Editor registers the global manifest, it sends the normal
`POST /ai-select/anchor-renders` request with spatial mode. The Companion
parses and retains the exact `AIRequestBinding` and `CameraBinding`, resolves a
sorted required descriptor list, and computes:

```text
workingSetToken = sha256(
  canonical JSON {
    format: "supersplat-camera-working-set-v1",
    sceneId,
    sceneVersion,
    cameraBinding,
    chunks: sorted [{chunkId, chunkDigest}]
  }
)
```

If an otherwise valid required chunk is absent, it returns only:

```json
{
    "status": "sceneChunkMiss",
    "requestBinding": { "...": "unchanged AIRequestBinding" },
    "sceneId": "...",
    "sceneVersion": "...",
    "cameraBinding": { "...": "exact CameraBinding" },
    "workingSetToken": "sha256:...",
    "missingChunkIds": ["sorted", "chunk", "ids"]
}
```

The Editor validates every returned binding/token/chunk ID, uploads only those
IDs through the raw batch protocol, then retries the identical logical render
request. The editor controller rechecks the Current Target Context before it
publishes a result; a stale context, dependency token, or camera can never
publish after a delayed upload.

The Companion renders only when every descriptor named by that
`workingSetToken` is resident and digest-validated. It never publishes an
authoritative partial working set as `Ready`.

## Deterministic typed assembly and fallback

Resident chunks remain mmap-backed typed planes. The Companion concatenates
only the required chunk tensor views, sorts by `globalOrdinals`, and builds
gsplat tensors through vectorized/tensor operations. It does not construct
per-Gaussian Python dict/list records or a canonical JSON snapshot. Contributor
tensor rows map through the sorted global Stable-ID tensor, so responses always
refer to global Stable Gaussian IDs.

### Anchor contributor publication artifact

For the authoritative Anchor route, the Companion keeps RGB alpha, local
contributor rows, contributor weights, and Stable-ID remapping as typed tensors
until publication. `contributorDigest` remains the existing opaque digest field
on the wire; its published meaning remains “the complete same-rasterization
Contributor product,” so no Selection Service protocol bump is required.

The current internal artifact format embeds its own identity:

```text
magic: "SSPAICTR"
formatVersion: uint32le = 1
width, height, contributorSlots: uint32le
alpha: float32le[height * width]
validity: uint8[height * width * contributorSlots]
stableIds: uint32le[height * width * contributorSlots]
weights: float32le[height * width * contributorSlots]
```

It is row-major and deterministic. The validity plane is separate from Stable
IDs because `0xffffffff` is a valid uint32 Stable Gaussian ID and cannot serve
as a padding sentinel. The SHA-256 input is copied from GPU tensors in bounded
16 MiB-or-smaller slices; no base64, nested Python list, ContributorSample
graph, or giant JSON serialization is created for an Anchor. A future change to
this artifact must use a new embedded format version rather than reinterpret
version 1.

## Anchor Server-Timing diagnostics

`POST /ai-select/anchor-renders` may include an additive standard
`Server-Timing` HTTP response header. It does not change the response JSON,
Anchor/SceneSnapshot identity, `workingSetToken`, or Selection Service protocol
version. For browser-origin requests the Companion also exposes this header via
`Access-Control-Expose-Headers`.

The current header emits these wall-clock milliseconds in deterministic order:

| Metric               | Boundary                                                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `working-set`        | Registered packed-snapshot lookup or spatial manifest resolution, including a bound cache miss.                               |
| `gpu-queue`          | Waiting to acquire or join the Companion's single Anchor admission. A matching in-flight retry measures its replay wait here. |
| `gsplat`             | The locked renderer's typed rasterization call, including its required synchronous result preparation.                        |
| `contributor-digest` | Complete contributor validation, Stable-ID remapping, bounded tensor-to-CPU hashing, or the legacy reference equivalent.      |
| `png`                | RGB PNG encoding.                                                                                                             |
| `json-base64`        | Anchor PNG base64 encoding plus the Companion's replay and outgoing JSON serialization.                                       |

`gpu-queue` is intentionally an admission measurement, not a CUDA hardware
scheduler measurement: this Companion currently rejects a different active
Anchor key with `capacityFull` instead of placing it in a GPU work queue. A zero
or small value therefore does not prove that the CUDA device had no external
queueing. The metrics are diagnostic only and need not sum exactly to network
TTFB because they exclude request transfer, browser work, and unrelated server
overhead.

The resolver and renderer retain a full-scene mode. Invalid manifests,
unavailable/support bounds, ambiguous resolution, resident inconsistency, or a
failed selective/reference parity gate cause all chunks to be required or the
request to fail closed. The existing 02A complete packed snapshot remains a
compatibility/reference path. Selective mode is not considered authoritative
until the fixture parity suite proves RGB, alpha, contributor stream, mass, and
Stable-ID mapping against the full-scene reference under the locked runtime.

## Test seams

Ticket 02B test-first seams are:

1. TypeScript support-bound calculation and spatial manifest/chunk digest
   construction, including center-outside/support-inside and anisotropic cases.
2. TypeScript spatial manifest registration and missing-only raw chunk retry
   transport, including stale binding rejection.
3. Python immutable manifest/resident-chunk store: digest, wrong scene/version,
   duplicate retry, atomic commit, and TTL cleanup.
4. Python camera working-set resolver: deterministic sorted IDs/tokens,
   clipping boundaries, ambiguity/full fallback.
5. Python mmap/tensor assembly: different chunk arrival orders produce the
   same row order and global Stable-ID contributor mapping.
6. Locked renderer full/reference versus selective parity for SH0--SH3 and the
   required transformed/deleted/boundary fixtures.
