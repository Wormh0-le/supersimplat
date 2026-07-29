# 08 — 2.5D object bootstrap + adaptive Key/Bridge View sequence planner

Status: blocked — waits for reopened 07A and Ticket 07B

Blocked by: 07B

Blocks: 08A

## Final Spec mapping

- Final Spec v1.1 §§23, 27, 30–32
- Final Spec v1.1 Amendments 002 and 003
- DG-13, DG-20, DG-21, DG-22, DG-23
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
- versioned adaptive planner policy;
- bounded progressive planner jobs;
- candidate-pose validity/preflight records;
- ordered `TrackingSequencePlan`;
- explicit Key View / Bridge View roles;
- transition-cost diagnostics;
- Stop / Generate More / Regenerate Auto Views.

## What to build

Replace the Ticket 06 fixed `±45°` pair with a bounded adaptive planner that:

1. derives a conservative visible-target center/extent from the confirmed Anchor;
2. rejects invalid indoor/outside-room observation poses before gain ranking;
3. selects useful Key Views by target observation/diversity gain;
4. orders Key Views into a trackable sequence;
5. inserts Bridge Views only when needed to keep adjacent transitions within a declared tracking envelope.

The planner may use low-cost support/visibility diagnostics before formal Lift. It must not fabricate Gaussian ownership, P/N/V Evidence, or tracked Masks.

# TargetBootstrapArtifact

The bootstrap binds exact Anchor Camera/RGB/Stable Mask and policy identity and records visible support, robust center, extent, quality, and reasons.

It may guide framing, pose generation, ROI, and transition ordering. It cannot publish Owned Gaussian IDs, Candidate, Native Selection, or unseen-surface completion.

If bootstrap quality is limited/unavailable, fail conservatively to smaller local moves or user-added Views.

# Key / Bridge semantics

```text
Key View
= expected to add useful object observation
  and may later become Included

Bridge View
= inserted primarily for tracking continuity
  and defaults Excluded from Lift
```

`trackingMembership` is separate from Participation. Planner role never overrides Ticket 07 assessment or user inclusion/exclusion.

# Planning decisions

Evaluate separately:

```text
camera validity
expected target observation gain
directional diversity gain
adjacent transition cost
resource cost
```

A high gain cannot override invalid camera geometry. A low transition cost cannot make a redundant Bridge View a Key View.

# Acceptance criteria

## Bootstrap

- [ ] Bootstrap is derived only from the confirmed Anchor revision.
- [ ] Center/extent use robust visible support and reject separated/background-dominated support.
- [ ] Bootstrap identity includes target/Anchor/RGB/Mask/policy/support digests.
- [ ] Bootstrap is explicitly non-ownership and never creates Candidate/P/N/V.
- [ ] Limited/unavailable bootstrap has actionable fallback.

## Adaptive Key Views

- [ ] Main flow exposes no fixed user View count or quality preset.
- [ ] Planner uses bounded min/max, target observation, diversity, marginal gain, low-gain patience, and resource cap.
- [ ] Candidate validity is evaluated before gain.
- [ ] Target projection, clipping, occupancy, scene support, depth/alpha/free-space diagnostics are considered.
- [ ] Behind-wall, outside-room, blank-content, or implausible poses are rejected/replaced.
- [ ] Training-camera manifold/free-space envelope may constrain candidates under versioned policy.
- [ ] Absence of reliable free space fails to local moves/user-added Views, not unconstrained orbit jumps.
- [ ] Target-only visibility is insufficient when the camera lies outside a plausible observation region.

## Sequence ordering and Bridge Views

- [ ] Output is an ordered sequence, not only an unordered camera set.
- [ ] Adjacent transition cost is recorded separately from information gain.
- [ ] Key Views remain selected for observation value.
- [ ] Bridge Views are inserted only when a Key-to-Key transition exceeds the declared tracking envelope.
- [ ] Bridge Views default `participation=excluded`.
- [ ] Planner records role, sequence index, policy, and expected transition cost.
- [ ] Sequence changes create a new plan identity and invalidate dependent tracking work.
- [ ] Ticket 08 does not run the tracker or publish Generated View Masks.

## Progressive controls

- [ ] View candidates/RGB/Mask/later Evidence publish independently.
- [ ] Stop cancels pending/future work without deleting completed artifacts.
- [ ] Generate More continues from current observation/directional/sequence gaps.
- [ ] `maxAutoViews` remains a hard bounded batch limit.
- [ ] Regenerate replaces planner-owned Views and preserves user-owned Views.
- [ ] Manual View confirmation never implicitly resumes planning.

## Anchor dependency

- [ ] Planner starts only from a confirmed Anchor with no unresolved ProposalDecision.
- [ ] Ticket 07B removes edge/corner authoring blind spots.
- [ ] Anchor revision changes follow explicit Restart/Recompute lifecycle.
- [ ] 07A diagnostics are not reused as formal planner Evidence.

# Failure / recovery criteria

- Bootstrap failure preserves Anchor and requests local/user-added alternatives.
- Invalid camera rejection preserves completed Views and uses bounded replacement.
- No useful Key View yields actionable Limited state.
- No trackable ordering may insert bounded Bridges, request replanning, or stop Limited.
- Stop/cancel/restart cannot publish obsolete plans.
- Missing Evidence never classifies RGB as Render Failed.

# Validation

- `npm run test:companion`
- `npm test`
- `npm run lint`
- locked GPU planner smoke
- frozen-scene bootstrap/pose/gain/sequence benchmark
- indoor-room behind-wall/outside-content regressions
- conservative no-free-space fallback
- Key-to-Key transition and Bridge insertion regression
- plan identity/stale-result regression
- existing large-orbit regression

# Non-goals

- No tracker backend or Mask propagation; Ticket 08A owns it.
- No final Lift Readiness calibration.
- No User-added View UI.
- No formal Direct Evidence kernel.
- No Gaussian ownership or provisional Candidate.
- No fixed full orbit.
- No general robot/navigation planner.
- No watertight room reconstruction.