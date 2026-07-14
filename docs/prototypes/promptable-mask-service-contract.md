# Promptable-Mask Service Contract Prototype

## Decision answered

This logical contract defines how the Selection Service turns batched point prompts over an immutable Frame Set into a replayable Mask Set for later 2D-to-Gaussian lifting. It keeps the editor independent of SAM-specific Python state and does not prescribe HTTP, WebSocket, process packaging, or production implementation.

## Boundary

The external contract is model-independent. `SAM 3.1` is the initial experimental adapter, not a required dependency of the open-source-ready core. The editor never receives or sends SAM tensor names, Python dictionaries, filesystem resource paths, object-state tensors, or checkpoint paths.

The Selection Service renderer registers the Frame Set internally. The editor sends point prompts and stable view references; it does not resend Generated View images on each Correction Round.

## Capabilities and Model Manifest

Before opening a mask session, the service reports:

```text
Capabilities {
  protocolVersion
  supportedPromptKinds: [point]
  supportsPositivePoints
  supportsNegativePoints
  supportsOrderedFramePropagation
  supportsMultipleTracks
  supportsCancellation
  maxTracks
  modelManifest
}

ModelManifest {
  adapterId
  modelName
  checkpointDigest
  sourceCommit
  licenseName
  licenseUrl
  weightsBundled
  runtimeConfigDigest
  device
  precision
}
```

One Object Selection Session pins one manifest digest. A changed model, checkpoint, source revision, threshold, or material runtime setting requires a new mask session. Every completed Mask Set echoes the digest. For the initial SAM 3.1 adapter, `runtimeConfigDigest` is the SHA-256 of the canonical fixed runtime settings below, rather than an operator-defined label.

## SAM 3.1 experimental baseline

The verified initial adapter uses the official `SAM 3.1` visual-prompt/video path. “SAM 3.1 Tracker” is shorthand for that capability, not a separate official model name.

```text
version             = sam3.1
checkpoint          = operator-supplied local sam3.1_multiplex.pt
max_num_objects     = 8
multiplex_count     = 16
use_fa3             = false
use_rope_real       = true
compile             = false
warm_up             = false
output_prob_thresh  = 0.5
full-frame masks    = rejected as too coarse
session_expiration  = 1200 seconds
video frames        = CPU-backed
tracker state       = GPU-backed; CPU fallback only after measured OOM
```

Keep `multiplex_count=16` aligned with the released multiplex checkpoint. Establish correctness and memory measurements in eager mode before separately testing compilation, FA3, or greater CPU offload.

The canonical settings digest for this baseline is `sha256:39a47a6b641b55bf967b7b73fb7e76efa900ff69ecfed764bcce1a89683c3cba`. The Companion rejects a SAM 3.1 Model Manifest with another runtime digest instead of silently adopting an upstream default.

The adapter and weights are governed by Meta's custom SAM License and gated access, not MIT or Apache. Operators obtain access and download weights separately; the application repository and distribution do not bundle them. The 4090D 24GB fit is an empirical test, not an assumed capability.

## Frame Set registration

```text
FrameSet {
  frameSetId
  frameSetVersion
  orderedViews[] {
    viewId
    frameDigest
    width
    height
    rgbFrameHandle
    cameraMetadataRef
  }
}
```

A Frame Set is immutable. Changing view content, dimensions, ordering, or camera/render identity produces a new version. Model adapters receive internal frame handles; the external editor contract never exposes SAM's `resource_path`. The SAM 3.1 adapter may use its official in-memory image-list loader.

A changed Frame Set invalidates the continuation token. The service rebuilds adapter state by replaying the Prompt Log against the new version.

## Tracks and operations

One mask session contains:

- one primary include Mask Track created by `New`;
- zero or more include tracks created by `Add`;
- zero or more exclude tracks created by `Remove`.

`Refine` adds positive or negative prompts to the primary track and recomputes its propagation. It does not create another union/subtraction region. Include union and exclude subtraction occur outside the model adapter, preserving each original track mask for lifting and diagnosis.

SAM object IDs are adapter internals. Stable application `trackId` values survive adapter reconstruction and map to fresh model object IDs during replay.

## Prompt contract

The first version supports point prompts only:

```text
PointPrompt {
  promptId
  trackId
  viewId
  frameDigest
  xPx
  yPx
  frameWidth
  frameHeight
  polarity: include | exclude
}
```

Coordinates address pixel centers in the registered frame, with origin at top-left, x rightward, and y downward. The service rejects non-finite, out-of-bounds, dimension-mismatched, unknown-view, or digest-mismatched prompts. The SAM adapter converts accepted points to its normalized coordinate and `1`/`0` point-label convention.

Multiple positive and negative points for one track/view may be submitted together. Text, boxes, scribbles, input masks, and automatic object discovery are outside the first contract even if an adapter supports them internally.

## Prompt Log and continuation state

The Prompt Log is the recoverable authority:

```text
PromptLogRevision {
  sessionId
  revision
  frameSetVersion
  acceptedOperations[]
  acceptedPrompts[]
}
```

The service may return an opaque continuation token for incremental execution, but the token is a disposable cache. On cache loss, service restart, adapter eviction, or Frame Set change, it reconstructs state by replaying the Prompt Log. No Meta-specific state crosses into the editor protocol.

## Transactional preview update

```text
UpdateMaskSession {
  requestId
  sessionId
  baseRevision
  frameSetVersion
  modelManifestDigest
  operation: New | Add | Remove | Refine
  trackId
  prompts[]
  deterministicSeed
}
```

Every update is transactional:

1. Validate all versions and prompts against the last accepted revision.
2. Apply new prompts to temporary adapter state.
3. Validate the prompted current-view mask.
4. Propagate over the ordered Frame Set.
5. Validate and freeze the complete Mask Set.
6. Atomically advance Prompt Log revision and continuation token.

Cancel or failure discards temporary state and preserves the previous accepted revision. If the adapter cannot clone state, reconstruct from the previous Prompt Log. Repeating the same `requestId` is idempotent and never applies prompts twice.

The official SAM cancellation primitive stops propagation but is not treated as rollback; transactional behavior belongs to this adapter layer.

## Initial mask choice

For `New`, the current prompting view is mandatory. If the model produces multiple candidates, the adapter chooses one using positive-point inclusion, negative-point exclusion, model quality score, and basic area validation. Candidate alternatives and scores are recorded as diagnostics but not exposed in the beginner UI.

For SAM 3.1, `diagnostics.candidateSelection` records the selected candidate
index, all candidate indexes, foreground-pixel counts, point-consistency,
selection decision, and any `out_probs` score. Its `scoreSemantics` explicitly
limits that score to ordering candidates within this adapter; it is not a
cross-adapter confidence value and includes no raw tensors or logits.

Failure to obtain an accepted current-view mask fails the complete update. The user edits prompts and retries; the adapter never propagates an invalid seed mask.

## Per-view outcome

Each track/view produces one explicit state:

- `accepted`: mask may be consumed by lifting;
- `not_found`: no reliable target was found; neutral evidence;
- `rejected`: association, confidence, or mask-shape validation failed; neutral evidence with a reason;
- `error`: technical failure.

`not_found` and `rejected` are never encoded as all-zero negative masks. Only accepted masks may contribute observed positive or negative evidence. The prompted current view is required; the later Generated View policy decides how many hidden-view rejections a complete update may tolerate.

## Mask Set

The adapter preserves each track separately:

```text
MaskSet {
  requestId
  sessionId
  promptLogRevision
  frameSetVersion
  modelManifestDigest
  threshold
  tracks[] {
    trackId
    role: include | exclude
    frames[] {
      viewId
      status
      binaryMaskRef?
      confidence?
      rejectionReason?
    }
  }
  diagnostics
}
```

The canonical required output is a finite `threshold` in `[0, 1]` plus a binary
mask for every accepted track/view. Raw logits or model-specific scores are
optional diagnostics with explicitly declared meaning; scores from different
adapters are not presumed comparable.

The combination layer unions include tracks and subtracts exclude tracks only after preserving the original masks. All candidate lifting methods receive the same immutable Mask Set.

## Streaming and atomic publication

Propagation may stream progress and temporary frame results:

```text
UpdateProgress {
  requestId
  processedViews
  totalViews
  currentViewId?
}
```

Partial masks never enter lifting or Candidate Object Selection. A Correction Round advances only after a complete, version-validated Mask Set is atomically published. Cancellation, required-frame failure, stale version, or service error discards the round and leaves the preceding candidate usable.

## Lifecycle commands

The logical contract contains:

```text
getCapabilities()
registerFrameSet(frameSet)
openMaskSession(frameSetVersion, modelManifestDigest)
updateMaskSession(update)
cancelUpdate(sessionId, requestId)
closeMaskSession(sessionId)
releaseFrameSet(frameSetVersion)
```

`closeMaskSession` releases model state and continuation caches but never modifies the editor's Candidate Object Selection or Gaussian Selection. Transport, health, discovery, installation, process ownership, and upgrade behavior are defined by the [Selection Service Lifecycle Decision](selection-service-lifecycle.md); they do not alter this logical contract.

## Contract acceptance scenarios

1. A positive and negative point batch replays to the same track and pixel after service restart.
2. A stale Frame Set, Prompt Log revision, or Model Manifest result is rejected.
3. `Add` and `Remove` preserve separate raw Mask Tracks and deterministic composition roles.
4. Cancelled and failed updates do not advance Prompt Log revision or Correction Round count.
5. Retrying a request ID does not duplicate prompts.
6. A `not_found` or `rejected` view contributes neutral rather than all-negative evidence.
7. Lifting backends receive one identical immutable Mask Set.
8. No SAM-specific state or filesystem path is required by the editor protocol.
9. Model/checkpoint/license identity is recorded for every accepted Mask Set.
10. The locally supplied SAM 3.1 adapter is rejected cleanly when its checkpoint, source commit, license declaration, or runtime capability is missing.
