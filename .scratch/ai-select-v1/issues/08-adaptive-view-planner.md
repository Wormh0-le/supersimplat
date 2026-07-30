# 08 — Visible target support + 2.5D bootstrap + adaptive sparse Key-View planner

Status: blocked — waits for Ticket 07A

Blocked by: 07A

Blocks: 08A

## Final Spec mapping

- Final Spec v1.2 §§8–10, 27–29
- DG-26 Decisions 1, 6, and 7
- ADR 0013 ownership boundary

## Purpose

Convert a confirmed object-level Anchor Stable Mask into:

1. a bounded replayable set of Anchor-visible 3D support samples;
2. a lightweight target summary;
3. immutable adaptive sparse Key-View plan segments.

This ticket uses geometry early for localization, planning, and later Prompt synthesis, but never publishes Gaussian ownership, Mask acquisition output, P/N/V, or Candidate.

## Inputs / preconditions

- confirmed object-level Anchor Stable Mask;
- exact Target Context and Anchor Camera/RGB/Mask identity;
- authoritative depth, first-hit support, or equivalent visible-surface seam;
- compatible CameraBinding and render preflight primitives;
- scene validity/free-space information where available;
- Ticket 07A conservative Anchor decision complete.

Ticket 07B is not a blocker. Palette interaction hardening and geometric planning may proceed in parallel after 07A.

## Outputs / handoff artifacts

- versioned `VisibleTargetSupportArtifact`;
- versioned `TargetBootstrapArtifact` referencing visible support by digest;
- versioned adaptive sparse planner policy;
- bounded progressive planner jobs;
- candidate-pose validity/preflight records;
- immutable `SparseKeyViewPlanSegment` artifacts;
- deterministic Key-View review order;
- Stop / Generate More / Regenerate Auto Views lifecycle.

# Phase 1 — VisibleTargetSupportArtifact

Define and produce a contract equivalent to:

```ts
interface VisibleTargetSupportArtifact {
    schemaVersion: number;
    targetContextId: string;

    anchorViewId: string;
    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;

    supportPolicyDigest: string;
    samples: readonly VisibleTargetSupportSample[];
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    artifactDigest: string;
}

interface VisibleTargetSupportSample {
    worldPosition: [number, number, number];
    sourcePixel?: [number, number];
    depth?: number;
    weight?: number;
    stableGaussianId?: number;
}
```

Requirements:

- samples are bounded, deterministic, finite, and replayable;
- source pixel/depth are retained when available for diagnostics;
- optional `stableGaussianId` is provenance only, never ownership;
- support extraction rejects or degrades separated/background-dominated samples;
- quality and reasons are structured/versioned;
- policy defines sampling, deduplication, ordering, weighting, and resource cap;
- the artifact is immutable and digest-bound.

Permitted uses:

- robust target center/extent derivation;
- camera framing and candidate generation;
- Key-View projected Point/Box/ROI/Mask Prompt synthesis in Ticket 08B;
- conservative initial Evidence Working Set seed;
- render/scene-support diagnostics.

Prohibited uses:

- Owned Gaussian IDs;
- P/N/V or Candidate publication;
- Native Selection mutation;
- unseen-surface completion claims;
- hard Evidence Working Set upper bound;
- Rejected/Out-of-Scope classification from Anchor absence alone.

# Phase 2 — TargetBootstrapArtifact

The bootstrap is a lightweight summary and MUST reference the support artifact:

```ts
interface TargetBootstrapArtifact {
    schemaVersion: number;
    targetContextId: string;

    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;
    visibleTargetSupportArtifactDigest: string;

    bootstrapPolicyDigest: string;
    centerWorld: [number, number, number];
    extentWorld: [number, number, number];
    visibleSupportCount: number;
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    artifactDigest: string;
}
```

The bootstrap does not duplicate the full support sample payload.

If support quality is limited/unavailable, fail conservatively to smaller local moves, user-added Views, or a declared Limited state.

# Phase 3 — Adaptive sparse Key Views

Replace the Ticket 06 fixed `±45°` pair with a bounded adaptive sparse planner that:

1. consumes the exact support and bootstrap artifacts;
2. generates plausible candidate CameraBindings;
3. rejects invalid indoor/outside-room observation poses before gain ranking;
4. evaluates target observation, directional diversity, render/scene support, and resource cost separately;
5. selects a small number of useful Key Views;
6. publishes an immutable plan segment;
7. lets `Generate More` append a later segment without invalidating completed segments.

The mandatory planner does not require:

- Bridge Views;
- tracker transition envelopes;
- dense continuous camera trajectories;
- tracker-specific ordering.

Key-View role is separate from Participation.

# SparseKeyViewPlanSegment

```ts
interface SparseKeyViewPlanSegment {
    schemaVersion: number;
    segmentId: string;
    targetContextId: string;
    anchorStableMaskDigest: string;
    visibleTargetSupportArtifactDigest: string;
    targetBootstrapArtifactDigest: string;
    plannerPolicyDigest: string;
    orderedKeyViews: readonly PlannedKeyView[];
    attemptId: string;
    artifactDigest: string;
}
```

Each `PlannedKeyView` has a stable `viewId`, exact CameraBinding, validity-policy identity, and optional gain diagnostics.

`Generate More` appends a segment. It does not rewrite prior segments, rotate prior View identities, or invalidate current RGB/Mask artifacts.

`Regenerate Auto Views` is the explicit operation that may supersede planner-owned segments while preserving user-owned Views.

# Acceptance criteria

## Visible support

- [ ] Support derives only from the exact confirmed Anchor revision.
- [ ] Samples are bounded, deterministic, finite, and canonical-digestable.
- [ ] World position is required; optional source pixel/depth/weight/Gaussian provenance validate coherently.
- [ ] Background-dominated, separated, invalid-depth, and non-finite support fail closed or lower quality.
- [ ] Stable Gaussian provenance never becomes ownership.
- [ ] Support artifact has structural validator and golden identity vectors.
- [ ] Replaying exact inputs produces the same ordered support artifact.

## Bootstrap

- [ ] Bootstrap references the exact support artifact digest.
- [ ] Center/extent use robust support rather than raw unfiltered extrema.
- [ ] Bootstrap is non-ownership and never creates Candidate/P/N/V.
- [ ] Bootstrap is a Working Set seed, not a hard upper bound.
- [ ] Limited/unavailable bootstrap has actionable fallback.

## Adaptive sparse planner

- [ ] Main flow exposes no fixed user View count or quality preset.
- [ ] Planner uses bounded min/max, target observation, diversity, marginal gain, low-gain patience, and resource cap.
- [ ] Candidate validity is evaluated before gain.
- [ ] Target projection, clipping, occupancy, scene support, depth/alpha/free-space diagnostics are considered.
- [ ] Behind-wall, outside-room, blank-content, or implausible poses are rejected/replaced.
- [ ] Absence of reliable free space fails to local moves/user-added Views, not unconstrained orbit jumps.
- [ ] Planner does not require tracker-specific transition limits.

## Segment lifecycle

- [ ] Output is an immutable sparse Key-View segment bound to support and bootstrap digests.
- [ ] Stable `viewId` is independent from array position.
- [ ] Generate More appends a segment and preserves completed segments/artifacts.
- [ ] Stop cancels pending/future work without deleting completed artifacts.
- [ ] Regenerate replaces planner-owned segments and preserves user-owned Views.
- [ ] Manual View confirmation never implicitly resumes planning.
- [ ] Anchor/support/bootstrap/segment changes rotate explicit identities and reject stale results.
- [ ] Ticket 08 does not run Mask acquisition or publish Generated View Masks.

# Failure / recovery criteria

- Support extraction failure preserves Anchor and exposes local/user-added alternatives.
- Bootstrap failure preserves Anchor/support diagnostics.
- Invalid camera rejection preserves completed Views and uses bounded replacement.
- No useful Key View yields actionable Limited state.
- Stop/cancel/restart cannot publish obsolete support/bootstrap/segments.
- Generate More failure preserves every completed segment and View.
- Missing future Evidence never classifies RGB as Render Failed.

# Validation

- `npm run test:companion`
- `npm test`
- `npm run lint`
- locked GPU support/planner smoke
- support sample canonical digest golden vectors
- depth/first-hit projection replay
- separated/background support regressions
- indoor behind-wall/outside-content regressions
- conservative no-free-space fallback
- sparse Key-View marginal-gain regression
- append-only Generate More regression
- support/bootstrap/segment stale-result regression
- existing large-orbit regression

# Non-goals

- No Prompt synthesis; Ticket 08B owns it.
- No Mask acquisition backend; Ticket 08B owns it.
- No acquisition protocol foundation; Ticket 08A owns it.
- No mandatory tracker, Bridge View, or transition envelope.
- No final Lift Readiness calibration.
- No user-added View UI.
- No formal Direct Evidence kernel.
- No Gaussian ownership or provisional Candidate.
- No fixed full orbit.
- No general robot/navigation planner.
- No watertight room reconstruction.
