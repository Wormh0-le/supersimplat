# Ticket 22 legacy contraction closeout

Date: 2026-08-17

## Result

The Final Spec v1.3 product path no longer imports, constructs, transports, or
presents `ObjectSelectionSession`. The browser legacy session/factory/editor/UI
modules and their workflow tests were removed. The Companion no longer exposes
Object Selection Session or Frame Set HTTP routes; route-level regression tests
require 404 for both surfaces.

Current SAM 3 Image Prompt capability records contain only Positive Point,
Negative Point, Positive Instance Box, opaque previous-logits refinement, and
the single-result policy. Retired Prompt families are not represented by false
placeholders, and extra legacy fields fail exact-key validation.

The current Runtime Profile publishes production Direct Evidence and production
Candidate identities only. Reference Candidate construction and complete
Contributor remain available to explicit diagnostics and frozen fixtures, but
they are not Availability dependencies and the product composition root cannot
apply a reference Candidate. The historical Multiplex/generated-mask helpers
remain non-current fixture code with no product route or Ready capability.

The browser regression also exposed an eager readiness-subscription ordering
bug: the Dock rendered before its suspension elements existed. Subscription is
now registered only after render-owned DOM initialization, with a source-order
regression test and the locked browser replay as executable coverage.

## Preserved foundations

- Stable Gaussian IDs and native `SelectOp` / `EditHistory` application;
- Binary and spatial SceneSnapshot registration and working-set recovery;
- authoritative gsplat RGB and production same-decision P/N/V Evidence;
- current SAM 3 Image instance inference and opaque logits references;
- versioned Mask, Participation, Lift Readiness and Candidate lifecycle;
- complete Contributor, Multiplex and historical benchmark artifacts behind
  explicit reference/fixture boundaries.

## Validation

- `rtk npm test`: 628 browser/editor tests and 441 Companion tests passed; two
  expected environment-gated Companion tests skipped.
- `rtk npm run test:companion`: 441 passed; two expected skips.
- `rtk npm run lint`, `rtk npm run lint:locales`, and `rtk npm run build` passed.
- Locked SAM 3 Image GPU regression: four tests passed on the RTX 4090 D with
  the operator-owned Ticket 21 checkpoint.
- Locked Direct Evidence GPU regression: seven tests passed.
- Locked spatial SceneSnapshot/render parity regression: three tests passed.
- Locked browser E2E loaded the 16,384-splat controlled-overlap fixture through
  the current production bundle and Runtime Profile. It completed authoritative
  Anchor RGB, real SAM 3 Image Mask inference, Anchor confirmation,
  TargetGeometryHint/local planning, production Direct Evidence and Candidate
  Re-Lift. The calibrated result was `not-ready`, so no invalid Candidate was
  published; the production identity was
  `sha256:c05c0b36b5e0a19fa848e0048598c5114af7384bed976732ea124347bdd56bf7`.
  No Object Selection Session, Frame Set or legacy Generated Mask request was
  observed. The executable harness is
  `.scratch/experiments/ai-select-v1/browser-validation/22-final-spec-browser-e2e.mjs`.

    With the locked Companion, current `dist` server and CDP browser already
    running, the replay command is:

    ```sh
    rtk env AI_SELECT_SCENE=$PWD/docs/benchmarks/fixtures/controlled-overlap/controlled_front_back_overlap.ply \
      node .scratch/experiments/ai-select-v1/browser-validation/22-final-spec-browser-e2e.mjs
    ```

- Static browser/session and Companion route audits returned no production
  matches; the only remaining `generated-view-mask/v1` source is the explicitly
  legacy fixture helper plus rejection tests/comments.
- Manifest JSON, local Markdown links, and `git diff --check` passed.
- Final two-axis review passed both Standards and Spec with no findings.

## Retained non-normative seams

The legacy JSON `/scene-snapshots/...` registration endpoint remains for
low-level fixtures; the browser product uses Binary SceneSnapshot Registration
v1. In-process PromptLog/MaskTrack/FrameSet/MaskSet helpers remain only for
frozen benchmark replay. Neither seam is advertised by the current Runtime
Profile or reachable through the retired Object Selection HTTP lifecycle.
