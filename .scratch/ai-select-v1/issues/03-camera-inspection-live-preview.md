# 03 — Camera Inspection + final Anchor preview

Status: ready-for-agent

Blocked by: 02

## Final Spec mapping

- DG-05
- §8–12 Camera Inspection / Final Anchor Preview
- §74 Camera Inspection toolbar
- MVP Phase 0–1

## Inputs / preconditions

- Anchor CameraBinding
- Current Scene View
- CurrentTargetContext
- Authoritative gsplat preview path

## Outputs / handoff artifacts

- Saved Scene View
- Inspection observer pose
- Manipulable Anchor frustum
- Final-resolution Anchor preview

## What to build

Implement explicit Camera Inspection without conflating the observer camera with the Anchor.
During frustum manipulation update only the Anchor CameraBinding and Frustum; on manipulation end
publish one final-resolution preview for the fixed resulting CameraBinding.

## Acceptance criteria

- [ ] Entering Camera Inspection saves the exact Scene View that was active before inspection.
- [ ] Camera Inspection moves the Editor Camera to an observer pose while keeping the Anchor CameraBinding as a separate object.
- [ ] The observer camera pose is never silently copied into the Anchor.
- [ ] Anchor frustum supports explicit translate/rotate manipulation in Camera Inspection.
- [ ] While dragging, update the Anchor CameraBinding and Frustum without requesting RGB.
- [ ] On manipulation end, request final-resolution authoritative gsplat RGB for the final fixed CameraBinding.
- [ ] A stale final preview response cannot overwrite a newer CameraBinding revision.
- [ ] `Return to Scene View` restores the exact saved Scene View without modifying the Anchor.
- [ ] `Reset Anchor` restores the Anchor to its workflow-defined initial/current-view baseline.
- [ ] Contextual toolbar presents Camera Inspection state with Move / Rotate / Return to Scene View / Reset Anchor actions.
- [ ] Formal inference artifacts use the fixed CameraBinding revision rendered at manipulation end.

## Failure / recovery criteria

- [ ] Final preview failure preserves the last valid RGB and provides a retry path.
- [ ] Inspection exit/restart cannot leak the observer camera as a new Anchor.

## Affected seams

- src/ai-select/camera-binding*
- src/ai-select/camera-inspection*
- Editor camera events
- Frustum/manipulator seam
- AI View Dock final preview
- Contextual toolbar
- Companion final render

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU final render validation
- Manual Scene View save/restore test

## Non-goals

- No Anchor mask authoring
- No Generated View pose editing

## Manual validation evidence — 2026-07-22

- [ ] **03-G1 — Anchor Frustum manipulation unavailable.** The current Anchor
      frustum cannot translate or rotate after AI Select activation. This is the
      expected missing behavior until this ticket implements explicit Camera
      Inspection; it is not a Ticket 02 regression.
