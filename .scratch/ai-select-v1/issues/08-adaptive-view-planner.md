# 08 — TargetGeometryHint + Bounded Local Key Views

Status: proposed — unblocked (07A implemented)

Blocked by: 07A

Blocks: 08A

Runs in parallel with: 07B

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

- [ ] Geometry derives only from exact Anchor RGB/Mask/Camera identity.
- [ ] Visible Points and digest replay deterministically.
- [ ] robust center/extent handle outliers and separated background support.
- [ ] geometry carries no ownership labels.
- [ ] default plan contains 2–4 bounded local Views.
- [ ] target projects with useful framing in every accepted View.
- [ ] invalid/nonblank render checks fail conservatively.
- [ ] Generate More appends a bounded batch without dirtying completed Views.
- [ ] Stop/Regenerate preserve correct user-owned and completed state.
- [ ] Ticket 08 runs no SAM inference.

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
