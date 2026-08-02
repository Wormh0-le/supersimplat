# 08 — TargetGeometryHint + Bounded Local Key Views

Status: implemented — `target-geometry/v1` + `local-key-view-planner/v1` + plan lifecycle (Stop / Generate More / Regenerate)

Blocked by: 07A

Blocks: 08A

Runs in parallel with: 07B

## Implementation record

- Design contract pinned in `.scratch/ai-select-v1/issues/08-design-contract.md`
  (wire shapes, algorithms, error taxonomy, lifecycle, test plan).
- Companion `target_geometry.py` (pure CPU, no torch/gsplat): first-hit
  visible surface at Gaussian-mean granularity (per set Stable Mask pixel the
  nearest alpha ≥ 0.5 Gaussian, the spec's "equivalent visible-surface seam";
  a production depth-render integration stays deferred), ≤64 visible points
  by deterministic stride, robust center (median) and extent (scaled MAD,
  1e-3 floor, never raw extrema), separated/background support filtered
  before statistics, quality `usable|limited` with evidence-backed reasons
  (`sparseSupport`, `separatedSupportFiltered`, `frameBoundaryContact`).
  Empty support fails closed as `geometryUnavailable` (409); the Anchor and
  prior completed Views are preserved.
- Bounded local Key-View planner: fixed deterministic offset fan
  (±30° azimuth, +20° elevation, then ±60°, ±30°/+20°, +40°), batch of ≤3,
  distance `max(anchor distance, 4×extent radius, 4×near)`, per-candidate
  validation (clipping, projected useful size ≥ 5% of frame, visibility
  fraction with `reducedVisibility` Limited marking), bounded closer
  replacement (×0.7, ×0.45), drop on failure, zero-accepted →
  `plannerFailure`, batch overflow → `planExhausted`. viewId
  `key-view-{batch}-{slot}` is stable and array-position independent.
- Two new routes replace the retired `POST /ai-select/generated-view-plans`
  (`generated-view-planner/v1` superseded, both sides fail closed):
  `POST /ai-select/target-geometry-hints` (resolves scene planes like the
  support probe, packed + spatial cache-miss 200s, single-slot
  admission/replay) and `POST /ai-select/local-key-view-plans` (pure CPU on
  the editor-supplied hint; fail-closed hint validation incl. recomputed
  `artifactDigest`, context and anchor-digest binding). Artifact digests are
  Companion-canonical; the editor binds them opaquely and never recomputes.
- Capabilities: `aiSelectGeneratedViewPlanning` replaced by
  `aiSelectTargetGeometryHint` + `aiSelectLocalKeyViewPlanning`; the editor
  gate requires both and keeps the Anchor flow usable without them.
- Nonblank render gate: `AnchorRenderArtifact.alpha_coverage` (fraction of
  pixels with raster alpha > 1e-3 from the same rasterization) feeds a
  fail-closed `blankRender` (409) check on `/ai-select/view-renders` only;
  the Anchor route is untouched and RGB is never published from a blank
  render.
- Editor controller: `geometryHint` + `keyViewPlans` + `generationStopped`
  target-local state; Stop preserves completed Views and skips queued pending
  renders (explicit Retry still runs); Generate More appends a bounded batch
  without dirtying completed Views (identity collisions fail closed, batch
  failure keeps the planner active with an actionable diagnostic); Regenerate
  validates the new batch 0 first, then preserves exact-identity
  (viewId + CameraBinding) records with their completed RGB/Mask, disposes
  dropped planner-owned Views, and never touches user-owned Views; pure
  exported helpers `findKeyViewIdCollisions` / `planRegenerateMerge`.
- Dock planner line: Stop / Generate More / Regenerate buttons in the active
  state plus the stopped status, localized in all 9 locales
  (`ai-select.views.planner.stop/.more/.regenerate/.stopped`).
- Ticket 06 retained unchanged: `/ai-select/view-renders`,
  `/ai-select/generated-view-masks` (`generated-view-mask/v1`), progressive
  per-View RGB publication, Mask Review and Participation. Ticket 08 itself
  runs no SAM inference.

## Follow-ups (not in scope)

- Production depth-render (`RGB+ED`) integration as the visible-surface seam
  behind the same artifact contract; the Gaussian-mean first-hit seam is the
  current production derivation.
- `targetGeometryHintDigest` / `localKeyViewPlanDigest` consumption lands
  with 08A/08B Prompt artifacts; the hint may seed but never hard-bounds the
  Ticket 13 Evidence Working Set.

## Final Spec mapping

- Final Spec v1.3 §§9–10, 19, 21, 24–26
- ADR 0016
- ADR 0013 ownership boundary

## Purpose

Convert the exact confirmed Anchor Stable Mask into one compact visible-surface geometry hint and a small bounded local Key-View plan.

```text
Anchor Stable Mask
+ depth / first-hit visible surface
→ TargetGeometryHintArtifact
→ 2–4 local Key Views
```

This ticket uses geometry for localization, framing and later Prompt synthesis only. It never publishes Gaussian ownership, P/N/V, Candidate or Mask acquisition output.

## TargetGeometryHintArtifact

```ts
interface TargetGeometryHintArtifact {
    schemaVersion: number;
    targetContextId: string;
    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;
    geometryPolicyDigest: string;
    centerWorld: [number, number, number];
    extentWorld: [number, number, number];
    visiblePoints: readonly [number, number, number][];
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    artifactDigest: string;
}
```

Requirements:

- derives from the exact confirmed Anchor revision;
- visible Points are bounded, finite, deterministic and canonical-digestable;
- invalid depth, background-dominated and separated samples are filtered or lower quality;
- center/extent use robust statistics rather than raw extrema;
- no Stable Gaussian ID, sample weight or ownership class is required;
- geometry may seed later Evidence Working Set but never hard-bound it;
- Anchor absence cannot classify Rejected or Out of Scope.

## Bounded local Key-View policy

Generate normally 2–4 local Views:

- left and right local azimuth offsets around target center;
- optional modest elevation offset;
- framing derived from target extent;
- bounded camera displacement from Anchor rather than a full orbit.

Each candidate validates:

- finite CameraBinding and current convention;
- target projection intersects image with sufficient size;
- clipping and near/far planes are valid;
- authoritative render is nonblank;
- gross occlusion/invalid depth may mark Limited or trigger bounded replacement.

## Lifecycle

```ts
interface LocalKeyViewPlan {
    schemaVersion: number;
    targetContextId: string;
    anchorStableMaskDigest: string;
    targetGeometryHintDigest: string;
    localViewPolicyDigest: string;
    orderedViews: readonly PlannedKeyView[];
    planAttemptId: string;
    artifactDigest: string;
}
```

- stable `viewId` is independent from array position;
- Stop preserves completed Views;
- Generate More appends another bounded local batch;
- Regenerate replaces planner-owned Views but preserves user-owned Views;
- prior completed RGB/Mask artifacts remain valid when their exact View identities remain unchanged.

## Explicitly deferred

v1 does not require:

- adaptive marginal-gain optimization;
- directional-diversity optimizer before any data exists;
- room/free-space reconstruction;
- behind-wall/outside-room semantic planning;
- occupancy/navmesh integration;
- Bridge Views or dense trajectories;
- tracker-specific ordering;
- append-only multi-segment planning framework;
- general robot/navigation planning.

## Acceptance criteria

- [x] Geometry derives only from exact Anchor RGB/Mask/Camera identity.
- [x] Visible Points and digest replay deterministically.
- [x] robust center/extent handle outliers and separated background support.
- [x] geometry carries no ownership labels.
- [x] default plan contains 2–4 bounded local Views.
- [x] target projects with useful framing in every accepted View.
- [x] invalid/nonblank render checks fail conservatively.
- [x] Generate More appends a bounded batch without dirtying completed Views.
- [x] Stop/Regenerate preserve correct user-owned and completed state.
- [x] Ticket 08 runs no SAM inference.

## Validation

- geometry digest golden vectors;
- depth/first-hit projection replay;
- background/separated-support regressions;
- small/thin/large target framing fixtures;
- local left/right/elevation View fixtures;
- blank/clipped/invalid-camera rejection;
- Generate More and stale-result tests;
- repository test/lint/build.

## Non-goals

- No Prompt synthesis or Mask inference.
- No backend registry or sequence planning.
- No P/N/V or Candidate.
- No general free-space planner.
