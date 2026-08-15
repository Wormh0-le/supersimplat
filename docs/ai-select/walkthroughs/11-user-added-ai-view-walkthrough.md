# 11 — User-added AIView (Current / Adjusted Camera): browser E2E walkthrough

Audience: an operator validating Ticket 11 end to end against the locked
Companion, a real SAM 3 Image checkpoint, and a scene with one well-isolated
object. Repository tests/lint/build cover the code path; this document is the
manual browser pass. CPU fixtures do not establish the production CUDA path.

## Prerequisites

Same locked environment as `08B-route-b-production-acquisition-walkthrough.md`
(install, model manifest `sam3-image-instance/v1`, Companion on
`http://127.0.0.1:8787`, editor on `http://localhost:3000` with browser and
service-worker caches disabled).

Capabilities must include at least:

```text
aiSelectImageInstanceMasks
aiSelectImageInstanceMaskReview
```

plus `aiSelectTargetGeometryHint` / `aiSelectLocalKeyViewPlanning` /
`aiSelectGeneratedViewPromptSynthesis` when the Regenerate-preservation check
below runs against planned Key Views.

Starting state for every flow below: AI Select active with a **confirmed
Anchor Stable Mask** (Ticket 07A/07B flow). The `Use Current View` /
`Adjust New View…` buttons appear in the Dock's Views row only from that
point on.

## Flow A — Use Current View

1. Orbit the Editor Camera to a fresh angle on the target object.
2. Click **Use Current View**.
3. Expected: a new Gallery card `user-view-1` titled `User View 1` with the
   user-added role and a 3D frustum in the viewport at exactly the Editor
   Camera pose. The Editor Camera itself never moves or re-poses.
4. The card renders progressively to **RGB Ready** (thumbnail + gsplat
   renderer badge). Mask stays `None` and Evidence stays `Not Requested` —
   RGB Ready alone must not trigger any inference. Companion log shows
   exactly one `/ai-select/view-renders` call and no
   `/ai-select/mask-proposals` call.
5. Adding the View never resumes local generation: the planner line stays
   idle/stopped throughout.

## Flow B — Adjust New View… + Confirm View

1. Click **Adjust New View…**. Expected: Camera Inspection opens with the
   provisional draft frustum and gizmos attached; Move/Rotate are enabled and
   the toolbar shows the `Adjust New View` tool label with a **Confirm View**
   button. The Editor Camera never adopts the draft pose.
2. Drag and rotate the draft frustum. Expected: the draft pose updates live;
   **no** render request fires during or at the end of the drag (the draft is
   not a View yet).
3. Click **Confirm View**. Expected: inspection returns to the Scene View and
   a new `user-view-N` card appears, rendering authoritative RGB from exactly
   the confirmed draft CameraBinding.
4. Repeat of step 1 while a draft is already open, or clicking
   **Use Current View** mid-draft: the unconfirmed draft is discarded and the
   capture uses the pre-inspection Scene camera — no half-confirmed View is
   left behind.

## Flow C — No-Mask choices and Mask authoring

1. Select an RGB Ready user View with no Mask. The card offers **Auto Mask**,
   **Manual Draw**, and **Exclude**.
2. **Auto Mask**: the Dock switches to the View's own RGB as the authoring
   surface (status line `User View — Mask authoring`) with the 07B palette
   (Positive/Negative Point, Positive Box, Paint/Erase). Every Prompt returns
   at most one result, which becomes Editing Mask automatically. Refinement
   uses only the opaque same-View logits ref. **Confirm Mask** then publishes
   the Stable Mask atomically, the
   card flips to Mask Ready, and Participation becomes Included — matching
   generated-View semantics. No automatic Re-Lift follows.
3. **Manual Draw**: the authoring surface opens with Paint active. Paint and
   Erase strokes never enter inference (no network calls).
4. **Exclude**: Participation records the explicit Excluded decision; the
   card keeps its RGB and stays inspectable.

## Flow D — Regenerate preservation

1. With at least one user View present (Masked or not), run **Regenerate**
   from the planner line.
2. Expected: generated Key Views re-plan and re-render as needed; every
   user-owned card keeps its exact viewId, RGB, Stable Mask, and
   Participation with no re-render flash.

## Failure and recovery checks

- **Render failure** (e.g. stop the Companion between adding the View and
  its render, or the blank-render gate): the card shows Render Failed and
  offers **Retry Render** next to **Exclude**; the View record and its
  CameraBinding/frustum stay inspectable. Retry is a true new attempt — same
  CameraBinding, a fresh `/ai-select/view-renders` call, never a mutated
  camera to bypass the cached failure.
- **Mask technical failure**: RGB and View survive; Retry / Manual Draw /
  Exclude are offered; no automatic fallback runs.
- **Companion Instance replacement mid-refinement** (restart the Companion
  between a proposal and a refinement): the logits ref is invalidated and the
  session reruns the current Points/Box without `mask_input` (EF-07).
- **Stale-response discard**: Restart Current Target while a user-View render
  or mask request is in flight; the late response is discarded by identity
  and never publishes into the new target context.

## What to look at in devtools

- Network: one `/ai-select/view-renders` per user-View render attempt;
  `/ai-select/mask-proposals` requests carry the exact authoritative RGB
  bytes (first ship) or the current Companion RGB ref, the view-scoped
  attempt id (`user-view-N:proposal-attempt-M`), and — on refinement — only
  the opaque `previousLogitsRef`; reviews land on
  `/ai-select/image-instance-mask-reviews`.
- Console: no unhandled errors; stale responses are discarded silently by
  target/revision/dependency identity.
