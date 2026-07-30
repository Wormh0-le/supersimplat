# 08 — 2.5D object bootstrap + adaptive sparse Key-View planner

Status: blocked — waits for reopened 07A and Ticket 07B

Blocked by: 07B

Blocks: 08A

## Final Spec mapping

- Final Spec v1.1 §§23, 27, 30–32
- Final Spec v1.1 Amendments 002–004
- DG-13, DG-20, DG-21, DG-22, DG-24
- MVP Phase 3

## Inputs / preconditions

- confirmed object-level Anchor Stable Mask;
- resolved Prompt/proposal state;
- no permanent fitted-image blind region after Ticket 07B;
- exact Anchor CameraBinding/RGB/Mask identity;
- authoritative depth, first-hit support, or equivalent visible-surface seam;
- compatible camera/preflight primitives;
- scene validity/free-space information where available.

## Outputs / handoff artifacts

- versioned `TargetBootstrapArtifact`;
- versioned adaptive sparse planner policy;
- bounded progressive planner jobs;
- candidate-pose validity/preflight records;
- immutable `SparseKeyViewPlanSegment` artifacts;
- deterministic Key-View review order;
- Stop / Generate More / Regenerate Auto Views.

## What to build

Replace the Ticket 06 fixed `±45°` pair with a bounded adaptive sparse planner that:

1. derives a conservative visible-target center/extent from the confirmed Anchor;
2. rejects invalid indoor/outside-room observation poses before gain ranking;
3. selects a small number of useful Key Views by target observation/diversity gain;
4. publishes an immutable plan segment;
5. allows `Generate More` to append another segment without invalidating completed segments.

The planner may use low-cost support/visibility diagnostics before formal Lift. It must not fabricate Gaussian ownership, P/N/V Evidence, tracked Masks, or a video-like tracking sequence.

# TargetBootstrapArtifact

The bootstrap binds exact Anchor Camera/RGB/Stable Mask and policy identity and records visible support, robust center, extent, quality, reasons, and an artifact digest.

It may guide framing, pose generation, projected ROI/Prompt construction, and an initial conservative Working Set seed.

It cannot publish Owned Gaussian IDs, Candidate, Native Selection, or unseen-surface completion. It cannot become a hard upper bound on later Evidence Working Set expansion.

If bootstrap quality is limited/unavailable, fail conservatively to smaller local moves or user-added Views.

# Sparse Key-View semantics

```text
Key View
= expected to add useful object observation
  and may later become Included
```

The mandatory v1 planner does not require:

- Bridge Views;
- tracker transition envelopes;
- dense continuous camera trajectories;
- tracker-specific ordering.

A later optional tracker/hybrid ADR may request auxiliary frames through a separate capability contract. Those frames are not part of the default sparse Key-View plan.

Key-View role is separate from Participation. Planner role never overrides Ticket 07 assessment or user inclusion/exclusion.

# Planning decisions

Evaluate separately:

```text
camera validity
expected target observation gain
directional diversity gain
expected render / scene-support quality
resource cost
```

A high gain cannot override invalid camera geometry. View count is not a proxy for coverage.

# Immutable plan segments

Each planner result is an immutable `SparseKeyViewPlanSegment` with:

```text
segmentId
targetContextId
Anchor Stable Mask digest
TargetBootstrapArtifact digest
planner policy digest
ordered Key Views
attempt identity
artifact digest
```

`Generate More` appends a new segment. It does not rewrite prior segments, rotate prior Key-View identities, or invalidate current RGB/Mask artifacts.

`Regenerate Auto Views` is the explicit operation that may supersede planner-owned segments while preserving user-owned Views.

# Acceptance criteria

## Bootstrap

- [ ] Bootstrap derives only from the confirmed Anchor revision.
- [ ] Center/extent use robust visible support and reject separated/background-dominated support.
- [ ] Bootstrap identity includes target/Anchor/RGB/Mask/policy/support/artifact digests.
- [ ] Bootstrap is explicitly non-ownership and never creates Candidate/P/N/V.
- [ ] Bootstrap is a Working Set seed, not a hard search-space upper bound.
- [ ] Limited/unavailable bootstrap has actionable fallback.

## Adaptive sparse Key Views

- [ ] Main flow exposes no fixed user View count or quality preset.
- [ ] Planner uses bounded min/max, target observation, diversity, marginal gain, low-gain patience, and resource cap.
- [ ] Candidate validity is evaluated before gain.
- [ ] Target projection, clipping, occupancy, scene support, depth/alpha/free-space diagnostics are considered.
- [ ] Behind-wall, outside-room, blank-content, or implausible poses are rejected/replaced.
- [ ] Training-camera manifold/free-space envelope may constrain candidates under versioned policy.
- [ ] Absence of reliable free space fails to local moves/user-added Views, not unconstrained orbit jumps.
- [ ] Target-only visibility is insufficient when the camera lies outside a plausible observation region.
- [ ] Planner does not require tracker-specific transition limits.

## Plan segment lifecycle

- [ ] Output is an immutable sparse Key-View segment.
- [ ] Stable `viewId` is independent from array position.
- [ ] Generate More appends a new segment and preserves completed segments/artifacts.
- [ ] Stop cancels pending/future work without deleting completed artifacts.
- [ ] `maxAutoViews` remains a hard bounded batch limit.
- [ ] Regenerate replaces planner-owned segments and preserves user-owned Views.
- [ ] Manual View confirmation never implicitly resumes planning.
- [ ] Segment/Anchor/bootstrap changes create explicit new identities and reject stale results.
- [ ] Ticket 08 does not run Mask acquisition or publish Generated View Masks.

## Anchor dependency

- [ ] Planner starts only from a confirmed Anchor with no unresolved ProposalDecision.
- [ ] Ticket 07B removes edge/corner authoring blind spots.
- [ ] Anchor revision changes follow explicit Restart/Recompute lifecycle.
- [ ] 07A diagnostics are not reused as formal planner Evidence.

# Failure / recovery criteria

- Bootstrap failure preserves Anchor and requests local/user-added alternatives.
- Invalid camera rejection preserves completed Views and uses bounded replacement.
- No useful Key View yields actionable Limited state.
- Stop/cancel/restart cannot publish obsolete segments.
- Generate More failure preserves every completed segment and View.
- Missing Evidence never classifies RGB as Render Failed.

# Validation

- `npm run test:companion`
- `npm test`
- `npm run lint`
- locked GPU planner smoke
- frozen-scene bootstrap/pose/gain benchmark
- indoor-room behind-wall/outside-content regressions
- conservative no-free-space fallback
- sparse Key-View marginal-gain regression
- append-only Generate More segment regression
- segment identity/stale-result regression
- existing large-orbit regression

# Non-goals

- No Mask acquisition backend; Ticket 08A owns it.
- No mandatory tracker, Bridge View, or transition envelope.
- No final Lift Readiness calibration.
- No User-added View UI.
- No formal Direct Evidence kernel.
- No Gaussian ownership or provisional Candidate.
- No fixed full orbit.
- No general robot/navigation planner.
- No watertight room reconstruction.
