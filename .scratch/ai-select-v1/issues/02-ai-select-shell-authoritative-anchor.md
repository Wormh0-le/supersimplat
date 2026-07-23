# 02 — AI Select shell + authoritative gsplat Anchor tracer bullet

Status: closed — 2026-07-23

Blocked by: 01

## Final Spec mapping

- Final Spec v1.1 §§1–7 where inherited from the completed v1.0 tracer bullet
- DG-01, DG-02
- MVP Phase 0–1

## Inputs / preconditions

- Current Scene View camera
- CurrentTargetContext
- Companion readiness/transport
- SceneSnapshot / Stable Gaussian IDs

## Outputs / handoff artifacts

- CameraBinding
- Anchor AIView shell
- Authoritative gsplat Anchor RGB
- Anchor frustum
- Minimal AI View Dock + contextual toolbar

## What was built

The first real end-to-end slice:

```text
Current Scene View
→ CameraBinding
→ Companion authoritative gsplat RGB
→ AI View Dock
```

## Acceptance criteria — closed scope

- [x] AI Select is a native Selection Tool, not a separate workspace.
- [x] Activation creates/uses CurrentTargetContext and keeps native SuperSplat behavior outside the AI seam.
- [x] Anchor CameraBinding is copied from Current Scene View without moving Editor Camera.
- [x] CameraBinding binds pose, projection/intrinsics, dimensions, clipping, and convention identity.
- [x] Anchor AI RGB comes from Companion gsplat, not PlayCanvas capture.
- [x] AI View Dock displays authoritative Anchor RGB and Rendering/Ready state.
- [x] Anchor frustum derives from the same CameraBinding.
- [x] Render request/result binds current AIRequestBinding and rejects late context/revision results.
- [x] Initial contextual toolbar exposes AI Select, Anchor: Current View, Adjust Anchor, Restart, and Exit.
- [x] Stable Gaussian ID and SceneSnapshot ownership remain editor-owned.

## Failure / recovery criteria

- [x] Companion offline/incompatible state does not break native SuperSplat and exposes readiness recovery.
- [x] Anchor render failure does not mutate Native Selection.

## Validation recorded at closure

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU CameraBinding → Anchor RGB + frustum parity

## Historical manual validation — 2026-07-22/23

- The default-collapsed AI Select bottom panel was present before activation and expanded for a new/restarted target.
- The original per-contributor Python-object/JSON publication bottleneck was replaced by bounded typed-tensor validation/hashing.
- A fresh browser request reached terminal Ready with DevTools `anchor-renders` waiting-for-server time of 1.26 s on the recorded test scene.
- Large-scene profiling, effective-snapshot parity, browser memory, and phase timing were transferred to Ticket 19.
- Frustum translate/rotate remained explicitly deferred to Ticket 03.

## Final Spec v1.1 architecture amendment — 2026-07-23

Ticket 02 remains closed for the native shell, authoritative RGB tracer bullet, CameraBinding/frustum identity, and browser Ready path.

ADR 0013 / Final Spec v1.1 supersede only the former assumption that complete Contributor publication is part of normal View readiness or production lifting:

- authoritative RGB remains a validated Ticket 02 foundation;
- complete Contributor code produced by the old tracer path is retained only as reference/debug infrastructure;
- Ticket 03 removes Contributor/Evidence from Camera Inspection preview readiness and implements true Retry attempts;
- Tickets 14 and 20 own reference P/N/V and production same-decision Evidence respectively.

This amendment does not reopen Ticket 02 or retroactively claim that Direct Evidence was implemented here.

## Non-goals

- No Camera Inspection manipulation
- No Mask editing
- No Generated Views
- No formal P/N/V Evidence
- No Candidate