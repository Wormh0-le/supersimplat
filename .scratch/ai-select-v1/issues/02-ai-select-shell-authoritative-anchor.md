# 02 — AI Select shell + authoritative gsplat Anchor tracer bullet

Status: implementation complete; manual-validation gaps remain

Blocked by: 01

## Final Spec mapping

- DG-01
- DG-02
- §7 Current View First
- §73–74 UI shell
- MVP Phase 0–1
- §87 Renderer acceptance

## Inputs / preconditions

- Current Scene View camera
- CurrentTargetContext
- Existing Companion readiness/transport
- SceneSnapshot / Stable Gaussian IDs

## Outputs / handoff artifacts

- CameraBinding
- Anchor AIView shell
- Authoritative gsplat Anchor RGB
- Anchor frustum
- Minimal AI View Dock + contextual toolbar

## What to build

Build the first real Final Spec end-to-end slice:
`Current Scene View → CameraBinding → Companion → authoritative gsplat RGB → AI View Dock`.
Introduce only the minimum tool shell required to exercise this path.

## Acceptance criteria

- [ ] AI Select is exposed as a native Selection Tool in the same conceptual class as existing Box/Sphere selection, not as a separate workspace.
- [ ] Activating AI Select for one selected visible Target Splat creates/uses the CurrentTargetContext and keeps native SuperSplat tools otherwise unaffected.
- [ ] Anchor CameraBinding is copied from the Current Scene View; activation does not move the Editor Camera.
- [ ] CameraBinding versionably binds pose, projection/intrinsics, dimensions, clipping, and coordinate-convention identity needed by both editor and Companion.
- [ ] All Anchor AI RGB comes from the authoritative Companion gsplat renderer; the new path does not use PlayCanvas framebuffer/canvas capture as AI observation truth.
- [ ] The AI View Dock displays authoritative Anchor RGB and at least Rendering / Ready state.
- [ ] The viewport Anchor frustum is derived from the exact same CameraBinding used for gsplat rasterization.
- [ ] Anchor render request/result is bound to the current AIRequestBinding; late results cannot overwrite a newer context/revision.
- [ ] Initial contextual toolbar state exposes AI Select, `Anchor: Current View`, `Adjust Anchor`, `Restart Current Target`, and `Exit AI Select` at the appropriate priority/overflow level.
- [ ] Existing Stable Gaussian ID and SceneSnapshot ownership remain editor-owned and are reused rather than duplicated.

## Failure / recovery criteria

- [ ] Companion offline/incompatible state does not break Native SuperSplat; AI Select presents the existing readiness recovery path with reconnect/settings actions.
- [ ] Anchor render failure remains an AI View/render failure; it does not mutate Native Selection.

## Affected seams

- src/ai-select/
- src/main.ts tool registration/wiring
- src/ui/ minimal AI View Dock
- src/ui/ contextual AI Select toolbar
- src/splat-scene-snapshot.ts
- selection-service readiness/transport
- Companion gsplat render boundary

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion if protocol changes
- Locked GPU: CameraBinding → gsplat Anchor RGB + frustum parity

## Non-goals

- No mask editing
- No Camera Inspection manipulation
- No Generated Views
- No Candidate

## Manual validation follow-up — 2026-07-22

Observed on `/home/ubuntu/wormh01e/gaussian/restroom/ply-result/point_cloud/iteration_100/point_cloud_3.ply`
(331,150 displayed Gaussians):

- [x] **02-G1 — persistent bottom AI Select panel.** The Final Spec's AI View
      Dock is now represented by a default-collapsed `AI Select` tab beside
      Timeline/Splat Data. It exists while inactive, shows an idle instruction,
      and auto-expands only on a new AI Select target context or restart; it
      remains an editor bottom panel rather than a separate workspace.
- [x] **02-G2 — scalable Anchor publication.** The browser closure reached a
      terminal Ready state, but the legacy Anchor route spent minutes expanding
      complete contributor tensors into Python objects and JSON. The 02B
      supplement now validates and hashes the complete contributor stream as
      bounded typed tensors. Fresh browser timing after restarting the local
      Companion is still required to validate the deployed process.

Not a Ticket 02 gap:

- Frustum translation/rotation is explicitly deferred to Ticket 03 Camera
  Inspection; Ticket 02's non-goals prohibit that implementation.
