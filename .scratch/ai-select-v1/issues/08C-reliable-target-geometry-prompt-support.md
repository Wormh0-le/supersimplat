# 08C — Reliable Target Geometry Prompt Support

Status: implemented — Companion/browser contract, CPU regression coverage, HAR replay, and locked-GPU browser E2E complete 2026-08-07

Blocked by: 08B

Runs in parallel with: 09

Blocks: none

## Implementation record

- TargetGeometryHint now publishes distinct retained first-hit support only,
  with `target-geometry/v2`, schema version 2, rotated policy/artifact
  identity, and independent `promptSupport` eligibility.
- Route B permits Prompt synthesis for a Limited hint only when retained
  support is globally usable (`separatedSupportFiltered` is the sole
  promotable reason); each View still requires two distinct in-frame projected
  samples. Geometry diagnostics remain in ready/limited responses and do not
  change Mask Review Participation.
- Old Hint schema/policy/digest payloads fail closed and must be regenerated.
- `npm test` (419 browser tests, 383 Companion tests with one skip), lint,
  locale checks, and build pass. HAR replay and operator locked-GPU browser E2E
  completed on 2026-08-07 for the Route B / retained-support flow with no
  blocking issue reported.

## Final Spec mapping

- Final Spec v1.3 §§9–10, 17–19, 24–26
- ADR 0017
- ADR 0016

## Purpose

Make the recoverable part of Route B Target Geometry usable without allowing
separated or boundary-contaminated support to become false SAM constraints.

Before this ticket, robust center/extent were computed from retained support
while Prompt synthesis could still consume the original pre-filter first-hit
points. When the separated-support filter dropped more than the policy
threshold, those discarded points could become false Prompt constraints. The
implemented contract now exposes only retained support; a View uses that
support when eligible or remains Limited. This ticket does not introduce
tracker memory, ordered video, or ArtisanGS-style multi-view mask aggregation.

## Decision contract

### TargetGeometryHint

- `visiblePoints` becomes the bounded, finite, deterministic set of distinct
  retained first-hit world-space samples after the separated-support filter.
- Raw pre-filter points are not a formal browser-consumable Prompt input.
- `centerWorld` and `extentWorld` continue to derive from the retained points.
- `quality` and `reasons` remain diagnostic. A hint can be `quality: "limited"`
  with `reasons: ["separatedSupportFiltered"]` while still exposing usable
  Prompt Support.
- Add `promptSupport: "usable" | "limited"` to the versioned artifact.
- Bump the TargetGeometryHint schema, geometry policy identity, and artifact
  digest identity. Old Hint/plan/Prompt artifacts fail closed and are
  regenerated.

### Prompt Support policy

Global Prompt Support is `usable` when:

- at least four distinct retained first-hit 3D samples remain; and
- there is no disqualifying Geometry reason. If Geometry is Limited, the only
  promotable reason is `separatedSupportFiltered`.

For each Generated View, Prompt synthesis additionally requires at least two
distinct retained points projected inside the authoritative image. Existing
projection/clipping limits remain active. A View that fails the per-View check
returns structured `status: "limited"` and issues no Mask inference.

When global and per-View Prompt Support are usable, Prompt synthesis may return
`status: "ready"` even when the Hint's Geometry Quality is Limited. The
response and View diagnostics retain `separatedSupportFiltered`; the browser
does not automatically Exclude the View. Participation remains governed by
Mask Review.

## Acceptance criteria

### Geometry artifact

- [x] retained `visiblePoints` contain no pre-filter separated-support samples;
- [x] repeated first-hit samples do not inflate the distinct-support count;
- [x] schema/policy/artifact identities are versioned and browser-stable;
- [x] old schema or digest-bound artifacts are rejected and re-requested;
- [x] `quality` and `promptSupport` are validated independently.

### Prompt synthesis

- [x] a separated-support Hint with at least four distinct retained samples
      can synthesize a Prompt from retained points only;
- [x] raw/discarded points cannot appear in the Box or Positive Points;
- [x] a Hint with sparse or frame-boundary reasons remains Limited;
- [x] a View with fewer than two distinct in-frame projected points remains
      Limited and does not call Mask inference;
- [x] Geometry Limited diagnostics remain visible when Prompt Support is usable;
- [x] Generated Prompt shape remains one Positive Box, 1–3 Positive Points,
      optional local Negative Points, and `multimaskOutput: false`.

### Validation

- [x] Companion geometry and Prompt route regression tests;
- [x] browser protocol, controller, stale-identity, and old-schema tests;
- [x] HAR replay proving the former `prompt-inconsistent` inputs use only
      retained points;
- [x] locked-runtime browser E2E on a recoverable separated-support scene and
      on sparse/boundary Limited scenes;
- [x] `npm test`, `npm run lint`, `npm run lint:locales`, `npm run build`, and
      Companion tests pass.

## Non-goals

- No Cutie/video tracker or ordered sequence contract.
- No cross-View mask aggregation or P/N/V/Lift changes.
- No production depth-render (`RGB+ED`) replacement; that remains a separate
  geometry follow-up.
- No change to Mask Review ownership or Participation authority.