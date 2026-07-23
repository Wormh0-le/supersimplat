# 03 — Camera Inspection + authoritative RGB final preview + true Retry

Status: ready-for-agent — v2.2 FlashSplat-alignment review

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

- [ ] Entering Camera Inspection saves the exact Scene View active before inspection.
- [ ] The Editor Camera moves to an observer pose while Anchor CameraBinding remains separate.
- [ ] Observer pose is never silently copied into the Anchor.
- [ ] Anchor frustum supports explicit translate/rotate manipulation.
- [ ] Dragging updates CameraBinding/frustum without requesting formal RGB.
- [ ] Manipulation end creates a new render attempt for final-resolution authoritative gsplat RGB.
- [ ] AIView becomes RGB Ready from valid RGB/CameraBinding identity alone; complete Contributor, Stable Mask, and Evidence are not prerequisites.
- [ ] The normal production RGB request does not invoke, allocate, hash, serialize, cache, or wait for complete per-pixel Contributor IDs/weights.
- [ ] The production RGB response contract does not require a Contributor identity or Contributor mass-validation result.
- [ ] Complete Contributor is accessible only through an explicit debug/reference path or capability that cannot be selected implicitly by production preview code.
- [ ] Complete Contributor or Evidence failure cannot convert an already successful RGB render into Preview Failure.
- [ ] Same attempt identity may replay idempotently, but explicit user Retry creates a new attempt for the same CameraBinding and actually reruns rendering.
- [ ] Retry never mutates or jitters CameraBinding merely to bypass cached failure.
- [ ] A stale response cannot overwrite a newer CameraBinding revision or newer attempt.
- [ ] `Return to Scene View` restores the exact saved Scene View without modifying Anchor.
- [ ] `Reset Anchor` restores the workflow-defined current-view baseline.
- [ ] Contextual toolbar exposes Move / Rotate / Return / Reset and actionable current-preview status.
- [ ] Formal downstream artifacts bind the fixed CameraBinding/RGB revision produced at manipulation end.
- [ ] Ticket 03 does not attempt to implement Direct Evidence; it leaves an explicit renderer-version seam for Ticket 20 to replace the RGB implementation with the FlashSplat-style same-decision kernel later.

## Failure / recovery criteria

- [ ] Current-attempt RGB failure preserves the last valid preview only as explicitly stale/not-current and exposes true Retry.
- [ ] Reference Contributor failure is diagnostic only and does not block current RGB publication.
- [ ] Inspection exit/restart cannot leak observer pose into a new Anchor.

## Affected seams

- src/ai-select/camera-binding*
- src/ai-select/camera-inspection*
- src/ai-select render-attempt/admission state
- Editor camera events
- Frustum/manipulator seam
- AI View Dock preview state
- Companion Anchor RGB route/cache
- Explicit reference Contributor route/capability boundary

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU final RGB validation
- Same-CameraBinding new-attempt Retry test
- Cached-failure replay versus explicit Retry test
- Test that production preview never calls the complete Contributor backend
- Test that enabling/failing the explicit reference Contributor path does not affect RGB readiness
- Manual Scene View save/restore walkthrough

## Non-goals

- No Anchor mask authoring
- No formal P/N/V Evidence production
- No Contributor tolerance adjustment or reconciliation work
- No Generated View pose editing

## Manual validation evidence — 2026-07-22

- [ ] **03-G1 — Anchor Frustum manipulation unavailable.** The current Anchor frustum cannot translate or rotate after AI Select activation. This remains the expected missing behavior owned by this ticket.