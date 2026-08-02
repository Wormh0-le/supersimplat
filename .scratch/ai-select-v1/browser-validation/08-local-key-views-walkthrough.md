# 08 — TargetGeometryHint + Bounded Local Key Views: browser E2E walkthrough

Audience: operator validating ticket 08 end to end against the locked
Companion and a real scene. Companion unit/integration coverage lives in
`selection-service-companion/tests/`; this document is the manual browser
path. Ticket 08 runs no SAM inference itself, but the retained ticket-06
pipeline still auto-produces per-View Masks after RGB Ready when a model is
configured.

## Prerequisites

1. Locked Companion environment (see `selection-service-companion/README.md`):

    ```sh
    cd selection-service-companion
    uv sync --python 3.12.12 --locked --extra renderer --extra sam3
    ```

2. Start the Companion (loopback profile):

    ```sh
    uv run --locked --extra renderer --extra sam3 selection-service start \
      --endpoint http://127.0.0.1:8787 \
      --allow-origin http://localhost:3000
    ```

3. Start the editor dev server from the repo root (disable browser
   network/service-worker caching when validating rebuilt code):

    ```sh
    npm run develop
    # open http://localhost:3000
    ```

4. Confirm the capability gate: in the browser console,

    ```js
    await fetch('http://127.0.0.1:8787/capabilities').then((r) => r.json());
    ```

    `supportedOperations` must include `aiSelectTargetGeometryHint` and
    `aiSelectLocalKeyViewPlanning` (the retired `aiSelectGeneratedViewPlanning`
    is gone). Without them the editor keeps the Anchor flow usable and fails
    planning closed with an actionable planner-line diagnostic.

## Happy path: hint + default local batch

1. Load a scene with one clear object, frame it, and activate AI Select.
2. Produce an Anchor Mask (one Positive Point, choose a candidate, Accept,
   optionally Paint/Erase, Confirm).
3. On Confirm the planner line appears (`Planning…`), then the Gallery shows
   the Anchor card plus **three** Key-View cards (`key-view-0-0`,
   `key-view-0-1`, `key-view-0-2` — left / right / elevated of the bounded
   local policy), each rendering progressively with 3D frustums in the
   viewport. The Editor Camera never moves.
4. Expected states per View: RGB Ready (thumbnail + gsplat renderer badge),
   then automatic Mask production follows independently. A render failure is
   contained to its card (Retry Render is a true new attempt).
5. Companion log shows one `/ai-select/target-geometry-hints` call followed by
   one `/ai-select/local-key-view-plans` call with `batchOrdinal: 0`, then
   `/ai-select/view-renders` per View. No SAM inference happens for planning
   itself.

## Lifecycle controls

- **Stop** (active only): queued pending renders stop starting; already
  completed cards stay. Status shows `Generation stopped — completed views
are kept`. In-flight renders may still finish and publish.
- **Generate More**: appends batch 1 (`key-view-1-*`, wider azimuth fan)
  without dirtying any completed card; another click appends batch 2. After
  the bounded sequence is exhausted the planner line shows an actionable
  error and stays active; completed cards are untouched.
- **Regenerate**: re-plans batch 0 from the same bound TargetGeometryHint.
  Views whose exact identity (viewId + CameraBinding) survives keep their
  completed RGB/Mask (no re-render flash); replaced cards re-render.
- Planner failure (e.g. Companion offline mid-flight) keeps the failed state
  with **Retry**; every previously completed View stays inspectable.

## Conservative failure checks

- **Blank render gate**: point the Anchor at a scene region where a planned
  Key View would see nothing (or temporarily hack a near/far clamp). A blank
  authoritative render fails closed as `blankRender` (409) on
  `/ai-select/view-renders`; the card shows Render Failed with Retry — the
  RGB is never published.
- **No support**: an Anchor Stable Mask over empty space yields
  `geometryUnavailable` (409) from `/ai-select/target-geometry-hints`; the
  planner line shows the failure, the Anchor stays intact, and no plan is
  published.
- **Old Companion**: a Companion without the two new capability strings
  leaves the Anchor flow working and fails planning closed with the
  install/refresh diagnostic.

## Automated GPU smoke (production renderer path)

`.scratch/ai-select-v1/browser-validation/08-gpu-smoke.py` boots a real
Companion server on loopback with the production `GsplatContributorRenderer`
(locked runtime verified), registers a 5-Gaussian packed fixture scene, and
checks: anchor/view renders, the real typed-raster `alpha_coverage`, the
`blankRender` 409 gate on an empty-space camera, and both new routes with
hand-computed hint expectations.

```sh
uv run --project selection-service-companion --locked --extra renderer \
  python .scratch/ai-select-v1/browser-validation/08-gpu-smoke.py
```

## What to look at in devtools

- Network: `target-geometry-hints` response carries the hint artifact
  (`centerWorld`, `extentWorld`, ≤64 `visiblePoints`, `quality`, `reasons`,
  `artifactDigest`); `local-key-view-plans` echoes `batchOrdinal` and carries
  the plan artifact with per-View `quality`/`reasons`.
- Console: no unhandled errors; stale responses (Restart during planning)
  are discarded silently by identity.
