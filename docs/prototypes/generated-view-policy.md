# Generated View Policy Prototype

## Decision answered

This policy defines how the Selection Service proposes, validates, orders, replaces, and stops Generated Views for a Complete Object Selection. Generated Views remain hidden and never move the visible editor camera. The policy reports observation coverage; later lifting and Selection Evidence decisions classify Gaussians.

## Seed Region

View generation starts in two stages:

1. Intersect the `New` prompt ray with the Target Splat to obtain a provisional 3D seed.
2. After the current-view mask succeeds, collect its high-contribution visible Gaussians, reject spatial outliers, and estimate a robust center and bounding sphere.

The resulting Seed Region is a framing aid, not a selection or object box. If a reliable contribution region cannot be formed, fall back to the click intersection plus a conservative minimum radius. `splat_analyzer` is not required for this path and its coarse boxes do not enter the current critical path.

## Camera framing

Keep the Anchor View's projection family and approximate field of view. Solve camera distance so the Seed Region occupies about 60% of the shorter image dimension with roughly 20% margin around it.

The camera must remain outside the Seed Region sphere and its near plane must not cut the region. If the target is clipped, move outward rather than widening the field of view. Small targets use a conservative minimum radius; framing does not collapse onto a single Gaussian.

## Initial candidate layout

The standard orbit aims for 16 views:

- the current Anchor View;
- 11 same-elevation views that complete an approximately 30-degree full azimuth orbit together with the Anchor View;
- 4 upper oblique views at approximately +30 degrees near cardinal azimuths.

Do not generate below-floor or through-ground views by default. Lower views are candidates only when camera preflight proves usable free space. Sixteen is an ideal candidate layout, not a requirement that all 16 masks be accepted. The incremental attempt envelope separately permits up to 16 planned hidden cameras and eight replacements (24 camera attempts total); the required Anchor is a replay input and does not consume a hidden-camera attempt.

## Resolution

The quality baseline is `1008×1008`, matching the verified SAM 3.1 tracking model's internal image size. Store RGB frames on CPU and compute contributor summaries per view without retaining all full-resolution contributor detail on GPU.

On measured OOM, create a different `renderConfigVersion` at `768×768`, then `512×512`. Never mix resolutions in one Frame Set, Mask Set, or benchmark run.

## Camera preflight

Before expensive RGB and mask inference, reject or adjust a candidate when:

- the camera position has high local Gaussian density or opacity;
- its near plane intersects the Seed Region;
- the line to the Seed Region loses most transmittance before reaching the region;
- the region is substantially clipped or outside the view;
- camera or projection values are non-finite.

First move outward on the same bearing, then try small elevation or azimuth offsets. If the view remains inside geometry or blocked by a wall, cabinet, or other reconstruction, mark it rejected. Never hide scene geometry, pass through walls, or modify the Target Splat to manufacture visibility.

## Ordering for tracking

Order views by camera proximity rather than by category:

- start propagation at the Anchor View;
- walk around the Seed Region with neighboring azimuth changes no greater than approximately 30 degrees;
- insert upper views beside their closest horizontal bearing;
- insert adaptive replacements next to their closest accepted camera;
- propagate from the Anchor View in both directions so the two paths meet near the back.

If a proposed neighboring jump is too large in camera angle or target projection, insert a smaller intermediate step within the exploration budget.

## Anchor View

Every preview update's visible prompting camera is a required Anchor View. The system captures its camera, display-frame digest, dimensions, and prompts without moving it.

If the view already exists in the Frame Set, reuse it. Otherwise create a new `frameSetVersion`, insert it at the nearest camera position, and preferentially replace a redundant hidden view so the normal budget remains near 16. Replay all Mask Tracks from the authoritative Prompt Log.

The Anchor View mask uses the editor RGB that the user actually clicked. Contributor attribution uses the Selection Service's render of the same camera. A renderer-parity check compares geometry, alpha/support, silhouette, and major appearance:

- within tolerance: use normal positive and negative evidence;
- moderate appearance/parity difference: use the view to seed the mask but do not treat mask-outside pixels as negative evidence;
- severe geometry/projection mismatch: fail the update rather than map a displaced mask to Gaussians.

All hidden Generated Views use service-rendered RGB and contributors from the same rasterization path.

## Two-stage view quality gate

### Hard rejection

Reject a view when any structural check fails:

- non-finite camera, render, contributor, or mask data;
- substantial clipping, near-plane cut, or no contributor support for the Seed Region;
- an empty or near-full-frame mask under the agreed framing;
- no contributor support beneath the mask;
- a positive prompt outside the mask or an explicit negative prompt inside it;
- mismatched frame, camera, model, render, or Mask Set version.

### Neighbor anomaly rejection

For otherwise valid views, compare robustly with adjacent accepted views:

- mask area and bounding extent;
- mask center displacement;
- contributor support;
- overlap with the projected Seed Region;
- adapter-declared tracking confidence.

Use versioned, benchmark-calibrated robust thresholds rather than one universal model confidence cutoff. Record every metric and rejection reason.

The first executable revision is `generated-view-neighbor-anomaly/v1`. It compares a candidate with its immediately preceding accepted neighbor, beginning with the Anchor. Projected Seed Region overlap must clear both an absolute floor and a relative minimum/maximum versus that neighbor; the Anchor baseline is `1.0` because the Seed Region comes from its accepted mask. A missing projected Seed Region or adapter-declared tracking-confidence metric rejects the hidden candidate neutrally. Threshold values, measured inputs, and rejection reasons remain internal/benchmark artifacts in [`generated-view-neighbor-anomaly-v1.json`](../benchmarks/fixtures/generated-view-neighbor-anomaly-v1.json) and require a new policy revision with fixture evidence when calibration changes.

An accepted view may contribute observed positive and negative evidence. A `not_found`, `rejected`, blocked, or technically invalid view remains neutral; it is never converted into an all-zero negative mask.

## Poorly reconstructed or inaccessible directions

A full nominal orbit is not evidence of full coverage. If a refrigerator back, cabinet interior, or other direction was never reconstructed reliably, the policy rejects bad renders and tries nearby, farther, or slightly elevated views. It stops before crossing geometry or fabricating a back surface.

Existing Gaussians without reliable observation remain candidates for later uncertainty classification. Physical surfaces absent from the Target Splat cannot and need not be invented by Complete Object Selection.

## Adaptive replacement and stopping

For one Correction Round:

- begin with up to 16 planned candidates;
- attempt at most 8 nearby replacements for failed candidates;
- attempt at most 24 camera views in total;
- after the initial Frame Set, allow at most one quality-driven Frame Set rebuild and Prompt Log replay;
- stop early after 3 consecutive accepted new views each add less than 2% previously unseen contributor coverage.

The required Anchor View must be accepted. Too few hidden accepted views do not create a technical failure: publish a Coverage Report with `insufficient_coverage` and leave unsupported regions available for uncertain classification.

## Reuse across Correction Rounds

Reuse the `New` Frame Set for `Refine`, `Remove`, and initially for `Add`. Re-rendering is not a default consequence of every prompt change.

Expand the Seed Region and create a new Frame Set only when an added region is outside the current extent, repeatedly touches image borders, or lacks observable support. A newly prompted Anchor View also creates a new version when absent. Necessary pre-propagation Anchor registration does not consume the one later quality-driven rebuild.

Changing a Frame Set does not add a Correction Round by itself, but all work remains inside that round's view-attempt and rebuild budgets. Prompt Logs replay against the new immutable Frame Set.

## Coverage Report

Coverage is measured by reliable contributor visibility, not by camera count or completed azimuth:

```text
CoverageReport {
  frameSetVersion
  renderConfigVersion
  attemptedViews
  acceptedViews
  rejectedViews[] { viewId, stage, reason, replacementOf? }
  coveredContributorIdsOrSummary
  unseenCandidateIdsOrSummary
  incrementalCoverageByView
  effectiveAzimuthElevationCoverage
  status: sufficient | insufficient_coverage
}
```

The report does not itself label selected, rejected, or uncertain Gaussians. It supplies observation facts to lifting and Selection Evidence.

## Beginner-facing behavior

Generated View thumbnails, orbit paths, mask quality scores, and rejection internals remain hidden. When coverage is insufficient, show only an actionable summary:

```text
Coverage is limited.
Some Gaussians could not be observed reliably and remain uncertain.

Try rotating to another visible side and use Refine.
```

Continue to display selected and uncertain counts. Preserve detailed coverage and rejection diagnostics in benchmark/run artifacts.

## Policy acceptance scenarios

1. A well-reconstructed isolated object produces the planned 16-view Frame Set at 1008 resolution.
2. A wall-backed object rejects blocked rear cameras without adding all-negative evidence.
3. A cabinet-contained object stops within 24 attempts and reports insufficient coverage rather than looping.
4. A bad SAM mask is rejected independently of a structurally valid render.
5. A newly prompted editor camera becomes the Anchor View without moving the editor camera.
6. A moderate editor/service render difference disables Anchor negative evidence; a geometric mismatch fails safely.
7. Repeated low incremental contributor coverage triggers early stopping.
8. `Add` expands and rebuilds only when the current Seed Region cannot frame or observe the new part.
9. All Frame Set changes invalidate model continuation state and replay the Prompt Log.
10. View count alone can never mark coverage sufficient.
