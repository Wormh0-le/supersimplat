# 08 — Implementation Design Contract (pinned 2026-08-01)

Post-16B supersession notice: this file remains the historical Ticket 08
implementation contract. ADR 0018 supersedes its current-facing
`local-key-view-planner/v1` identity with `local-key-view-planner/v2`, sets the
initial fixed-offset automatic-view range to `4–8`, and retires persistent
Stop / Generate More / Regenerate product controls through stages 16D and 16G;
the historical body below is preserved unchanged.

This file pins the editor↔Companion wire contract and algorithm policy for
ticket 08 (TargetGeometryHint + Bounded Local Key Views). Both implementation
tracks (Companion Python, editor TypeScript) must match this file exactly.

Authority: Final Spec v1.3 §§9–10, 19, 21, 24–26; ADR 0016 items 8–10.

## Ownership

- Companion owns: TargetGeometryHint extraction, bounded local Key-View camera
  planning, per-candidate validation, authoritative nonblank render gate.
- Editor owns: both artifacts as target-local product state, lifecycle commands
  (Stop / Generate More / Regenerate / Retry), stale-result rejection,
  Gallery/Frustum presentation.
- The hint carries NO Stable Gaussian IDs, no weights, no ownership labels.
- Ticket 08 runs no SAM inference. The ticket-06 cross-view mask route
  (`/ai-select/generated-view-masks`, `generated-view-mask/v1`) and the
  `/ai-select/view-renders` route are unchanged and stay.

## Superseded and removed

- `generated-view-planner/v1` (fixed 2-view ±45° orbit pair) is superseded.
- Route `POST /ai-select/generated-view-plans` is removed (both sides).
- TS contract `GeneratedViewPlanRequest/Response`, `PlannedGeneratedView`,
  `AISelectGeneratedViewPlanner`, `aiSelectGeneratedViewPlannerVersion` and
  their validators are removed from `src/ai-select/generated-view-service.ts`.
- Python `plan_first_generated_views`, `PlannedGeneratedView`,
  `GENERATED_VIEW_PLAN_COUNT`, `AISelectGeneratedViewPlanRequest`,
  `GeneratedViewPlanAdmission`, the admission trio, and the
  `_active_generated_view_plan` slot are removed. `MaskSupportSeed` /
  `derive_mask_support_seed` are removed if no other caller remains.
  `synthesize_view_prompts` / `_collect_support_means` STAY (mask route).
- Capability string `aiSelectGeneratedViewPlanning` is replaced by the two new
  strings below.

## Constants

- Geometry policy version: `target-geometry/v2`; hint `schemaVersion: 2`.
- Key-View planner policy version: `local-key-view-planner/v1`; plan
  `schemaVersion: 1`.
- Routes: `POST /ai-select/target-geometry-hints`,
  `POST /ai-select/local-key-view-plans`.
- Capabilities (Companion `supportedOperations`):
  `aiSelectTargetGeometryHint`, `aiSelectLocalKeyViewPlanning`.
- Error envelopes (409): hint route `status: "geometryHintError"`; plan route
  `status: "keyViewPlanError"`. 400 stays `invalidRequest`, 503 `unavailable`.
  Codes: `geometryUnavailable` (no usable first-hit support),
  `geometryFailure`, `plannerFailure`, `planExhausted` (no further bounded
  batch), `capacityFull`, plus `sceneCacheMiss` / `sceneChunkMiss` as 200
  statuses on the hint route only.

## TargetGeometryHint request (wire)

```jsonc
{
  "requestBinding": { "targetContextId", "contextRevision", "dependencyToken" },
  "targetSplatId": string,
  "sceneId": string,            // === targetSplatId
  "sceneVersion": string,
  "renderConfigVersion": string,
  "geometryAttemptId": string,  // "target-geometry-hint-attempt-N"
  "anchorCameraBinding": CameraBinding,
  "anchorCameraBindingDigest": "sha256:...",  // editor-computed, opaque to Companion
  "anchorRgbDigest": "sha256:...",            // identity binding only
  "anchorStableMask": MaskArtifact,           // bytes, digest-verified
  "geometryPolicyVersion": "target-geometry/v2",
  "sceneTransport": "packed-v1" | "spatial-v1"  // optional
}
```

The hint route resolves scene planes exactly like the ticket-06 plan route did
(`_resolve_ai_select_scene_planes`, packed or spatial working set) and gets the
same single-slot admission/replay treatment.

## TargetGeometryHint response (wire)

```jsonc
{
  "status": "complete",
  // ... identity echo of every request field above except the mask bytes:
  "requestBinding", "targetSplatId", "sceneId", "sceneVersion",
  "renderConfigVersion", "geometryAttemptId",
  "geometryPolicyVersion": "target-geometry/v2",
  "hint": {
    "schemaVersion": 2,
    "targetContextId": string,               // === requestBinding.targetContextId
    "anchorCameraBindingDigest": "sha256:...",  // echo of request value
    "anchorRgbDigest": "sha256:...",            // echo of request value
    "anchorStableMaskDigest": "sha256:...",     // digest of verified mask bytes
    "geometryPolicyDigest": "sha256:...",       // Companion policy descriptor digest
    "centerWorld": [x, y, z],
    "extentWorld": [x, y, z],
    "visiblePoints": [[x, y, z], ...],       // 1..64 retained distinct support
    "quality": "usable" | "limited",         // "unavailable" is contract-only;
                                             // production fails closed with 409
    "reasons": [string, ...],                // evidence-backed, may be empty
    "promptSupport": "usable" | "limited", // independent Prompt eligibility
    "artifactDigest": "sha256:..."           // Companion canonical digest
  }
}
```

## Geometry derivation algorithm (`target_geometry.py`, pure CPU, no torch)

First-hit visible surface at Gaussian-mean granularity (the spec's "equivalent
visible-surface seam"; a production depth-render integration is deferred):

1. For every Gaussian in the resolved planes (means + logitOpacities), gate:
   `logitOpacity >= 0.0` (alpha ≥ 0.5, support-probe parity), camera-space
   depth in `[near, far]`, rounded pinhole pixel in bounds, anchor Stable Mask
   bit set at that pixel.
2. Per set mask pixel keep the NEAREST (min depth) Gaussian: its world mean is
   the first-hit visible-surface sample at that pixel.
3. Deduplicate equal world means (one retained support sample must not be
   counted once per repeated pixel), then bound the distinct points: if count
    > 64, keep `points[::ceil(n/64)]` (deterministic stride, first point always
    > kept). Formal `visiblePoints` never contains the pre-filter raw support.
4. Empty support → route raises `MaskSessionError('geometryUnavailable', ...)`
   (409). The editor keeps the Anchor and may still add user Views.
5. Robust center: per-axis median of the bounded distinct points (provisional), drop samples
   farther than `max(0.05, 3 × median distance)` (separated/background
   filter); if all are dropped, fail closed with `geometryUnavailable` rather
   than publishing rejected points.
6. `centerWorld` = per-axis median of retained points.
   `extentWorld[axis]` = `max(1e-3, 1.4826 × median(|retained[axis] −
center[axis]|))` (scaled MAD; never a raw extremum; epsilon floor keeps
   thin/degenerate targets finite).
7. Quality and evidence-backed reasons:
    - `sparseSupport` when retained count < 8;
    - `separatedSupportFiltered` when dropped fraction > 0.25;
    - `frameBoundaryContact` when the Stable Mask touches the frame border;
    - quality = `limited` when reasons non-empty, else `usable`.
8. Prompt Support is independent from Geometry Quality. It is `usable` only
   when at least four distinct retained samples remain and the only possible
   quality reason is `separatedSupportFiltered`; it is otherwise `limited`.
   Each Generated View must additionally project at least two distinct
   in-frame samples. `sparseSupport` and `frameBoundaryContact` therefore stay
   Prompt-limited even when RGB and geometry localization remain available.

`geometryPolicyDigest` = `_canonical_json_digest` of the policy descriptor
(dict with `version` + every numeric constant above). Route B
`artifactDigest` uses the Companion `route_b_artifact_digest` encoding over the
full payload minus `artifactDigest`: sorted object keys, finite numbers as
IEEE-754 binary64 tokens, and tight separators. This keeps identity stable
when the browser parses and re-stringifies the artifact. The editor NEVER
recomputes artifact digests — it binds them opaquely. Cross-runtime identity
fields (`anchorCameraBindingDigest` etc.) are always editor-computed and only
string-compared by the Companion.

## LocalKeyViewPlan request (wire)

```jsonc
{
  "requestBinding": {...},
  "targetSplatId": string,
  "planAttemptId": string,        // "local-key-view-plan-attempt-N"
  "batchOrdinal": 0,              // 0 = default batch; Generate More increments
  "anchorCameraBinding": CameraBinding,
  "anchorCameraBindingDigest": "sha256:...",  // editor-computed
  "anchorRgbDigest": "sha256:...",
  "anchorStableMaskDigest": "sha256:...",
  "targetGeometryHint": { ...full hint artifact as produced above... },
  "localViewPolicyVersion": "local-key-view-planner/v1"
}
```

No scene resolution (pure CPU on the hint) → no snapshot, no cache-miss path.
The route validates the untrusted hint fail-closed: structure, `schemaVersion
== 2`, `quality != "unavailable"`, `promptSupport` enum, recomputed `artifactDigest` equality,
`hint.targetContextId === requestBinding.targetContextId`, and string equality
of the three anchor digests against the request fields. Any mismatch → 400.
Single-slot admission/replay like the other routes.

## LocalKeyViewPlan response (wire)

```jsonc
{
  "status": "complete",
  "requestBinding", "targetSplatId", "planAttemptId", "batchOrdinal",
  "localViewPolicyVersion": "local-key-view-planner/v1",
  "plan": {
    "schemaVersion": 1,
    "targetContextId": string,
    "anchorStableMaskDigest": "sha256:...",
    "targetGeometryHintDigest": "sha256:...",  // === hint.artifactDigest
    "localViewPolicyDigest": "sha256:...",
    "orderedViews": [
      {
        "viewId": "key-view-{batchOrdinal}-{index}",
        "cameraBinding": CameraBinding,
        "quality": "usable" | "limited",
        "reasons": [string, ...]
      }
    ],                             // 1..3 per batch
    "planAttemptId": string,       // === request planAttemptId
    "artifactDigest": "sha256:..."
  }
}
```

## Key-View planning algorithm (same module, pure CPU)

- `extentRadius = max(extentWorld)` floored at `0.05`.
- Ring distance `d = max(dist(anchorPos, center), 4 × extentRadius,
4 × near)` — bounded local displacement, never a full orbit.
- `baseDir = normalize(anchorPos − center)`; azimuth axis = ticket-06 orbit
  axis (world +z component orthogonal to baseDir, deterministic fallback
  order +z, +y, +x); elevation axis = `normalize(cross(baseDir, azimuthAxis))`
  with the rotation sign chosen so the camera rises along the azimuth axis.
- Fixed deterministic offset sequence `(azimuthDeg, elevationDeg)`:
  `[(+30, 0), (−30, 0), (0, +20), (+60, 0), (−60, 0), (+30, +20),
(−30, +20), (0, +40)]`. Batch `k` takes offsets `[3k : 3k+3]` (batch 0 = 3
  views: left, right, elevated; 8 candidates total). Out of range → 409
  `planExhausted`.
- Camera: ticket-06 look-at builder (camera-to-world, OpenCV convention)
  aimed at `centerWorld`, inheriting the exact anchor projection/resolution/
  clipping.
- Per-candidate validation (fail → bounded replacement):
    1. finite binding (by construction, asserted);
    2. center depth ∈ `[near, far]`;
    3. projected target size `max(fx, fy) × extentRadius / depth ≥ 5%` of
       `min(width, height)` in pixels ("intersects image with sufficient size");
    4. visibility fraction: fraction of hint `visiblePoints` projecting in-bounds
       with depth ∈ `[near, far]`; `< 0.25` fails the candidate, `[0.25, 0.5)`
       accepts with `quality: "limited"`, reason `reducedVisibility`.
- Bounded replacement on validation failure: same offset with `d × 0.7`, then
  `d × 0.45`; first passing wins. All fail → candidate dropped.
- Zero accepted views in a batch → 409 `plannerFailure`.
- `localViewPolicyDigest` = canonical digest of the planner policy descriptor.
- `plan.artifactDigest` = `route_b_artifact_digest` of the plan minus
  `artifactDigest`.

## Nonblank render gate (Companion, view-renders only)

- `AnchorRenderArtifact` gains `alpha_coverage: float | None = None` (fraction
  of pixels with raster alpha > 1e-3, computed from the already-rendered
  `raster_alpha` in the same launch — zero extra GPU work).
- `GsplatContributorRenderer.render_anchor` sets it; fixture renderers leave
  it `None`.
- `_render_ai_select_view` (the `/ai-select/view-renders` state method only —
  the Anchor route is untouched) fails closed with
  `MaskSessionError('blankRender', ...)` when `alpha_coverage is not None and
alpha_coverage < 0.001`. The view's RGB is not published; the editor marks
  that View Render Failed (Retry creates a true new attempt).

## Editor lifecycle (AISelectGeneratedViewController)

- Controller options: `planner: AISelectLocalKeyViewPlanner`,
  `geometryHints: AISelectTargetGeometryProvider` (new), renderer/maskProvider
  unchanged. `supportsGeneratedViews()` now gates on the two new capability
  strings.
- `beginRun` → enqueue `planViews`: hint request (carries snapshot for
  transport, cache-miss bounded retry in the adapter) → validate → store
  frozen hint → plan request batch 0 → validate (viewIds unique, no collision
  with existing) → replace views → `active` → enqueue per-view render+mask
  (existing pipeline unchanged).
- State gains: `geometryHint: TargetGeometryHintArtifact | null`,
  `keyViewPlans: readonly LocalKeyViewPlan[]` (accepted batches),
  `generationStopped: boolean`. `plannerStatus` enum unchanged
  (`idle|planning|active|failed`).
- `stopGeneration()`: only from `active`; sets `generationStopped = true`.
  Queued per-view render steps skip while stopped (views stay `pending`);
  in-flight identity-bound results may still publish (cancellation is only a
  resource optimization). Completed Views are preserved.
- `generateMoreViews()`: requires `active`; clears stopped; plans
  `batchOrdinal = nextBatchOrdinal` (new planAttemptId); on success appends
  views (collision → fail closed), increments ordinal, enqueues renders of new
  and any pending views. On `planExhausted`/transport error: keep `active`,
  set `plannerErrorMessage` (cleared by the next success); completed Views are
  never dirtied.
- `regenerateViews()`: requires `active` + current run; disposes views whose
  `source === 'auto-generated'` (mask/evidence registry disposal exactly like
  `disposeRun` per view), preserves `user-added` records (partition logic in
  an exported pure helper for tests), clears selection if disposed, resets
  batch ordinal, re-plans batch 0 with the SAME stored hint (new attempt).
- `retryPlanning()`: unchanged semantics (full hint+plan re-run, `failed`
  only).
- `GeneratedViewRecord` gains `readonly source: AIViewSource` (planner views
  `'auto-generated'`) and optional `planQuality` / `planReasons`; `compose()`
  emits `source: view.source` instead of hardcoded `'auto-generated'`.
- Hint/plan failure preserves the Anchor (§24) and never touches prior
  completed Views.

## Editor validation rules (fail closed)

- Hint response: full structural validation + identity echo match
  (`requestBinding`, target, scene ids, attempt, policy version) +
  `hint.targetContextId === request.requestBinding.targetContextId` +
  `hint.anchorCameraBindingDigest === request.anchorCameraBindingDigest` +
  `hint.anchorRgbDigest === request.anchorRgbDigest` +
  `hint.anchorStableMaskDigest === request.anchorStableMask.digest` +
  `hint.schemaVersion === 2` + `quality ∈ {usable, limited, unavailable}`
  (unavailable from transport is treated as failure) + visiblePoints: 1..64
  finite retained triples + reasons: strings + promptSupport semantic gate
  (four distinct points for `usable`, only `separatedSupportFiltered`
  promotable) + all digests `sha256:<64hex>`.
- Plan response: structural + identity echo + `batchOrdinal` echo +
  `plan.schemaVersion === 1` + `plan.targetGeometryHintDigest ===
hint.artifactDigest` + `plan.anchorStableMaskDigest ===
request.anchorStableMaskDigest` + `plan.planAttemptId ===
request.planAttemptId` + views 1..3, each valid CameraBinding,
  `viewId !== 'anchor-view'`, unique within response and against existing
  controller views, quality ∈ {usable, limited}, reasons strings.

## Editor UI

- Anchor Dock planner line gains three buttons: Stop (`active` only),
  Generate More (`active`), Regenerate (`active`). Failed keeps Retry.
  Planner line shows `plannerErrorMessage` whenever set.
- New locale keys in all 9 locales: `ai-select.views.planner.stop`,
  `ai-select.views.planner.more`, `ai-select.views.planner.regenerate`,
  `ai-select.views.planner.stopped`.

## Test plan

Companion (stdlib unittest, fixture renderers, no GPU):

- `tests/test_target_geometry.py`: first-hit projection replay golden vectors
  (hand-computed), stride bound at 64, median/MAD robustness with outliers,
  separated/background filtering, sparse support, frame-boundary contact,
  empty support → None, digest determinism golden vectors.
- `tests/test_local_key_view_plans.py`: batch 0 = left/right/elevated, azimuth
  symmetry, framing for small/thin/large targets, projection-size and clipping
  rejection, bounded replacement (closer distance), reducedVisibility limited
  marking, batch 1 append ids, exhausted batch → error, digest replay.
- `tests/test_ai_select_target_geometry.py`: hint route parse/400s, mask
  digest verification, packed + spatial cache-miss 200s, admission replay
  (same attempt idempotent, new attempt re-executes), capacityFull,
  geometryUnavailable 409, plan route hint-digest/binding rejection (400),
  planExhausted 409, stale admission eviction, capabilities contain the two
  new strings.
- Update `tests/test_ai_select_generated_views.py`: remove plan-route tests,
  keep mask-route tests; add blankRender gate test (fixture with
  alpha_coverage below threshold → 409; anchor route unaffected).

Editor (node:test against .test-dist):

- `test/ai-select-target-geometry-hint.test.js`,
  `test/ai-select-local-key-view-plan.test.js`: validator matrices,
  matchesRequest, digest formats, schema-version fail-closed.
- `test/ai-select-generated-view-service.test.js`: drop plan-contract tests.
- `test/ai-select-generated-view-controller.test.js`: re-stub (hint provider +
  key-view planner); hint failure → planning failed, Anchor preserved; plan
  failure; full hint→plan→render→mask progression; Stop preserves completed
  and skips pending; Generate More appends without dirtying completed
  (identities unchanged), collision fail-closed; Regenerate disposes
  planner-owned, keeps user-owned (pure-helper partition test), replans batch
  0; stale-result discard across Stop/More/Regenerate.
- `test/selection-service-fetch-adapter-generated-views.test.js`: new hint
  route incl. packed/spatial cache-miss bounded retry; new plan route
  (no snapshot); old plan-route tests removed.

Docs: CONTEXT.md gains `TargetGeometryHint` + `Local Key View` entries and the
stale `Adaptive View Planner` entry is corrected (marginal-gain planning is
the deferred concept); issue 08 gets an implementation record; browser
walkthrough notes under `.scratch/ai-select-v1/browser-validation/`.
