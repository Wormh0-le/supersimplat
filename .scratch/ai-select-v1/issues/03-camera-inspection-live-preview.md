# 03 — Camera Inspection + interactive/final Anchor preview

Status: ready-for-agent

Blocked by: 02

## Final Spec mapping

- DG-05
- §8–12 Camera Inspection / Live Preview
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
- Interactive preview
- Final-resolution Anchor preview

## What to build

Implement explicit Camera Inspection without conflating the observer camera with the Anchor.
During frustum manipulation use the Final Spec's two-level preview policy; on manipulation end
publish a final-resolution preview for the fixed resulting CameraBinding.

## Acceptance criteria

- [ ] Entering Camera Inspection saves the exact Scene View that was active before inspection.
- [ ] Camera Inspection moves the Editor Camera to an observer pose while keeping the Anchor CameraBinding as a separate object.
- [ ] The observer camera pose is never silently copied into the Anchor.
- [ ] Anchor frustum supports explicit translate/rotate manipulation in Camera Inspection.
- [ ] While dragging, preview requests are latest-only and may use lower resolution, RGB-only output, and throttle/debounce.
- [ ] On manipulation end, request final-resolution authoritative gsplat RGB for the final fixed CameraBinding.
- [ ] A stale interactive or final preview response cannot overwrite a newer CameraBinding revision.
- [ ] `Return to Scene View` restores the exact saved Scene View without modifying the Anchor.
- [ ] `Reset Anchor` restores the Anchor to its workflow-defined initial/current-view baseline.
- [ ] Contextual toolbar presents Camera Inspection state with Move / Rotate / Return to Scene View / Reset Anchor actions.
- [ ] Formal inference artifacts use a fixed CameraBinding revision; transient drag previews are never mistaken for a confirmed inference view.

## Failure / recovery criteria

- [ ] Preview failure preserves the last valid preview and provides a retry path.
- [ ] Inspection exit/restart cannot leak the observer camera as a new Anchor.

## Affected seams

- src/ai-select/camera-binding*
- src/ai-select/camera-inspection*
- Editor camera events
- Frustum/manipulator seam
- AI View Dock preview
- Contextual toolbar
- Companion preview/final render

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU preview/final parity
- Manual Scene View save/restore test

## Non-goals

- No Anchor mask authoring
- No Generated View pose editing
