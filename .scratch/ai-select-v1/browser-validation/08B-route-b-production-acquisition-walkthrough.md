# 08B — Route B Generated View acquisition: browser E2E walkthrough

Audience: an operator validating the simplified v1.3 production path with a
locked Companion, a real SAM 3 Image checkpoint, and a scene containing one
well-isolated object. This is a browser/manual validation guide; CPU fixtures
do not establish the production CUDA path.

## Prerequisites

1. Install and register the locked Companion release and the current SAM 3
   Image Model Manifest. The manifest must use
   `adapterId: "sam3-image-instance/v1"` and the runtime digest documented in
   `selection-service-companion/README.md`.

    ```sh
    cd selection-service-companion
    uv sync --python 3.12.12 --locked --extra renderer --extra sam3
    uv run --locked --extra renderer --extra sam3 selection-service install \
      --release 0.1.0 \
      --lock-file ./uv.lock
    uv run --locked --extra renderer --extra sam3 selection-service models install \
      --manifest /secure/manifests/sam3-image.json \
      --weights /secure/models/sam3.pt
    uv run --locked --extra renderer --extra sam3 selection-service start \
      --endpoint http://127.0.0.1:8787 \
      --allow-origin http://localhost:3000
    ```

2. In a separate shell at the repository root, start the editor and open it
   with browser cache and service-worker cache disabled:

    ```sh
    npm run develop
    # http://localhost:3000
    ```

3. Before activating AI Select, inspect the locked runtime in DevTools:

    ```js
    await fetch('http://127.0.0.1:8787/capabilities').then((response) =>
        response.json()
    );
    ```

    Require a ready renderer and image-instance provider, the selected SAM 3
    Image manifest, and all of:

    ```text
    aiSelectTargetGeometryHint
    aiSelectLocalKeyViewPlanning
    aiSelectGeneratedViewPromptSynthesis
    aiSelectImageInstanceMasks
    aiSelectImageInstanceMaskReview
    ```

    Do not validate this path with a `sam3.1`/Multiplex manifest. The absence
    of any listed capability should leave the Anchor usable and fail the
    generated-view flow closed.

## Happy path

1. Load a scene, frame a clear object, activate AI Select, create and confirm
   the Anchor Stable Mask.
2. Wait for Target Geometry and the first bounded local Key View batch. The
   Editor Camera must not move; generated card thumbnails/frustums publish as
   RGB becomes ready.
3. For each generated card, observe this order in the gallery and Network
   panel:

    ```text
    /ai-select/target-geometry-hints
    /ai-select/local-key-view-plans
    /ai-select/view-renders
    /ai-select/generated-view-prompts
    /ai-select/image-instance-masks
    /ai-select/image-instance-mask-reviews
    ```

4. Inspect one prompt request/response. It must bind the exact View RGB
   digest, recomputable camera digest, Target Geometry Hint digest, Local Key
   View Plan digest, model manifest, runtime digest, and Companion Instance.
   The returned prompt has exactly one `positiveBox`, 1–3 positive pixel
   points, at most two negative points, and `multimaskOutput: false`.
   It must not contain a Negative Box, text, brush/mask constraint, or
   `previousLogitsRefDigest`.
5. Inspect the inference request. Its `rgb` contains the exact authoritative
   PNG artifact (not a digest alone), `identity.inferenceAttemptId` is present,
   and `prompt.multimaskOutput` is false. The result contains zero or one
   bitset Mask, never a candidate list or raw logits.
6. Inspect Review. It references the exact inference result and chosen Mask;
   it contains an evidence-backed `good`, `review`, or `failed` assessment.
   It does not contain a Stable publication command, Participation mutation,
   P/N/V, or Lift result.
7. Expected browser state:

    - Good: Auto Good Stable Mask appears and defaults Included.
    - Review: Auto Review Stable Mask appears and defaults Excluded; use
      **Confirm as-is** to create User Confirmed authority.
    - Failed: no new automatic Stable Mask; the card is Excluded.

## Recovery and negative checks

- **Semantic unavailable:** make a planned View lack projectable support or
  use a test scene/model behavior that returns no usable mask. RGB remains
  inspectable, the card shows **No usable Mask**, no Stable Mask is published,
  and it is Excluded. Retry must issue a new `inferenceAttemptId` while keeping
  the View camera/RGB/Prompt identities unchanged.
- **Limited Prompt:** a `limited` prompt response publishes no inference
  request. The card remains RGB Ready and Excluded. Its retry action regenerates
  the Prompt with a new prompt-synthesis attempt; it is distinct from an
  inference retry.
- **Technical inference/review failure:** stop the Companion or induce an OOM
  after RGB Ready. RGB and any previous Stable Mask remain inspectable; no
  partial mask/ref/Stable state is published.
- **User Confirmed protection:** confirm a Review mask, then retry/regenerate
  automatic work. The User Confirmed Stable revision must not be replaced.
- **Migration guard:** Network must contain no
  `/ai-select/generated-view-masks` request. There is no Route-A fallback,
  scene-snapshot registration, Multiplex/video session, tracker reference, or
  propagation payload on the Route B acquisition calls.

## Production GPU evidence

Record the Companion release/lock identity, CUDA/PyTorch/gsplat capability
output, model manifest digest, scene, and captured Network requests with the
test result. A successful browser run establishes the operator's actual GPU
environment; the repository's Route B unit fixtures use an injected image
runtime and do not make that claim.
