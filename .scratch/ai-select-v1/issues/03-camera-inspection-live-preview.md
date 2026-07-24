# 03 — Camera Inspection + authoritative RGB final preview + true Retry

Status: implemented — 2026-07-24; observer pose roll fix 2026-07-24 after manual Scene View walkthrough

Blocked by: 02

## Final Spec mapping

- Final Spec v1.1 §§5.3, 6, 8, 9, 19, 28.1
- ADR 0013 observation/Evidence separation
- DG-05, DG-20
- MVP Phase 1

## Inputs / preconditions

- Anchor CameraBinding
- Current Scene View
- CurrentTargetContext / AIRequestBinding
- Authoritative gsplat RGB path
- Anchor render admission/cache seam

## Outputs / handoff artifacts

- Saved Scene View
- Inspection observer pose
- Manipulable Anchor frustum
- Final-resolution authoritative RGB preview
- Render attempt identity and retry semantics
- RGB-only production request/response path

## What to build

Implement explicit Camera Inspection without conflating the observer camera with the Anchor. Frustum manipulation changes only the Anchor CameraBinding. Manipulation end requests one final authoritative RGB for the fixed CameraBinding. Preview success is determined by RGB rendering, not complete Contributor or Evidence production.

The normal Camera Inspection/Anchor preview path must stop invoking the complete Contributor backend. That backend is reachable only through an explicit debug/reference capability and is not a hidden synchronous side effect of RGB publication.

## Acceptance criteria

- [x] Entering Camera Inspection saves the exact Scene View active before inspection.
- [x] The Editor Camera moves to an observer pose while Anchor CameraBinding remains separate.
- [x] Observer pose is never silently copied into the Anchor.
- [x] Anchor frustum supports explicit translate/rotate manipulation.
- [x] Dragging updates CameraBinding/frustum without requesting formal RGB.
- [x] Manipulation end creates a new render attempt for final-resolution authoritative gsplat RGB.
- [x] AIView becomes RGB Ready from valid RGB/CameraBinding identity alone; complete Contributor, Stable Mask, and Evidence are not prerequisites.
- [x] The normal production RGB request does not invoke, allocate, hash, serialize, cache, or wait for complete per-pixel Contributor IDs/weights.
- [x] The production RGB response contract does not require a Contributor identity or Contributor mass-validation result.
- [x] Complete Contributor is accessible only through an explicit debug/reference path or capability that cannot be selected implicitly by production preview code.
- [x] Complete Contributor or Evidence failure cannot convert an already successful RGB render into Preview Failure.
- [x] Same attempt identity may replay idempotently, but explicit user Retry creates a new attempt for the same CameraBinding and actually reruns rendering.
- [x] Retry never mutates or jitters CameraBinding merely to bypass cached failure.
- [x] A stale response cannot overwrite a newer CameraBinding revision or newer attempt.
- [x] `Return to Scene View` restores the exact saved Scene View without modifying Anchor.
- [x] `Reset Anchor` restores the workflow-defined current-view baseline.
- [x] Contextual toolbar exposes Move / Rotate / Return / Reset and actionable current-preview status.
- [x] Formal downstream artifacts bind the fixed CameraBinding/RGB revision produced at manipulation end.
- [x] Ticket 03 does not attempt to implement Direct Evidence; it leaves an explicit renderer-version seam for Ticket 20 to replace the RGB implementation with the FlashSplat-style same-decision kernel later.

## Failure / recovery criteria

- [x] Current-attempt RGB failure preserves the last valid preview only as explicitly stale/not-current and exposes true Retry.
- [x] Reference Contributor failure is diagnostic only and does not block current RGB publication.
- [x] Inspection exit/restart cannot leak observer pose into a new Anchor.

## Affected seams

- src/ai-select/camera-binding*
- src/ai-select/camera-inspection*
- src/ai-select render-attempt/admission state
- Editor camera events
- Frustum/manipulator seam
- AI View Dock preview state
- Companion Anchor RGB route/cache
- Explicit reference Contributor route/capability boundary

## What was built — 2026-07-24

Camera Inspection shell, observer pose, frustum translate/rotate, drag-only
CameraBinding revision, manipulation-end final RGB, stale-result protection,
and last-valid-preview retention landed with the earlier tracer commits
(`c9117f5`, `6469059`, `0fbcf71`). This pass completed the remaining v2.2
contract work:

- **RGB-only production contract.** The Anchor response no longer carries
  `contributorDigest`; it adds `rgbRendererVersion: 'gsplat-rgb/v1'` (the
  explicit Ticket 20 seam) and echoes `renderAttemptId`. Editor validation
  fails closed on an unknown RGB renderer version.
- **Companion production path never touches Contributor.**
  `render_anchor` defaults to `include_reference_contributor=False`; the
  locked backend then never calls `rasterize_num_contributing_gaussians` /
  `rasterize_contributing_gaussian_ids`, never reconciles, and never hashes
  (proven by a locked-GPU test that forbids those kernels). The typed
  `SSPAICTR` digest path survives only as the reference backend.
- **Explicit reference Contributor capability.** `referenceContributor: true`
  (boolean-only, advertised as `aiSelectAnchorReferenceContributor`) adds
  `referenceContributorDigest`; a reference failure degrades to the
  diagnostic-only `referenceContributorError` beside the still-published RGB.
  Production editor code never sends the switch.
- **Render attempt identity.** Every submitted render mints a fresh
  `renderAttemptId`; the Companion admission/replay key includes it. The
  transport's snapshot cache-miss recovery resends the identical request, so
  same-attempt replay stays idempotent, while an explicit user Retry reruns
  rendering for the same CameraBinding without any camera jitter.
- **Toolbar status.** The contextual toolbar now shows the current preview
  status during Camera Inspection and exposes a true-Retry action on failure.

## Validation recorded — 2026-07-24

- `npm test` (tsc + 101 JS tests + 181 Companion tests) — pass
- `npm run lint` — pass
- `npm run lint:locales` — pass
- `npm run build` — pass
- Locked GPU (RTX 4090 D, torch 2.11.0+cu128, locked gsplat source) renderer
  tests — pass, including the new production test that forbids the reference
  Contributor CUDA kernels on the RGB-only path
- Same-CameraBinding new-attempt Retry test — JS
  (`retryAnchorPreview` mints a fresh attempt, identical CameraBinding) and
  Python (`test_explicit_retry_creates_a_new_attempt_that_actually_rerenders`)
- Cached-failure replay versus explicit Retry —
  `test_a_new_attempt_reruns_instead_of_replaying_a_cached_failure`
- Production preview never calls the complete Contributor backend —
  `test_production_render_anchor_never_touches_the_reference_contributor`
  (renderer seam) and
  `test_production_anchor_render_never_invokes_the_contributor_kernels`
  (locked GPU)
- Enabling/failing the explicit reference path does not affect RGB readiness —
  `test_reference_contributor_requires_an_explicit_opt_in`,
  `test_reference_contributor_failure_never_blocks_rgb_publication`,
  `test_reference_contributor_failure_stays_diagnostic_beside_valid_rgb`
- [ ] Manual Scene View save/restore walkthrough — not yet performed in a
      browser session

## Non-goals

- No Anchor mask authoring
- No formal P/N/V Evidence production
- No Contributor tolerance adjustment or reconciliation work
- No Generated View pose editing

## Manual validation evidence — 2026-07-22

- [x] **03-G1 — Anchor Frustum manipulation unavailable.** Resolved: the
      Anchor frustum translates and rotates during Camera Inspection
      (`AnchorFrustumManipulator` + `AnchorFrustumManipulation`), with drags
      revising only the CameraBinding and manipulation end requesting the final
      authoritative RGB.

## Manual Scene View walkthrough — 2026-07-24

- [x] **03-G2 — Entering Camera Inspection rolled the viewport.** Found in the
      browser walkthrough: for a Z-up scene viewed near the orbit pole (view
      direction along ±Y, screen-up +Z), clicking Adjust Anchor rotated the whole
      viewport ~90° around the view axis. Root cause: the observer pose added
      25% up/right offsets to the pull-back, and the editor camera's roll-free
      azimuth/elevation model (screen-up forced to world +Y) swung azimuth wildly
      for the tilted direction near the pole. Fixed in
      `cameraInspectionObserverView`: the observer now pulls straight back along
      the Anchor view axis, so `setPose` recovers the Anchor's own
      azimuth/elevation and the scene orientation stays continuous; regression
      test in `test/camera-inspection.test.js`. Re-test initially appeared unfixed
      because the app service worker (`src/sw.ts`, cache-first on
      `superSplat-v<version>`) kept serving the previous `index.js`; after
      bypassing the service-worker cache the browser walkthrough confirmed the
      viewport orientation stays continuous on entering Camera Inspection.
