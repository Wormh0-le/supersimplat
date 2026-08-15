# 04C — SAM 3 Image Instance Adapter + Prompt Contract Migration

Status: implemented — locked GPU fixture passed on operator CUDA hardware (see implementation record)

Blocked by: 04B

Blocks: 02C, 07A, 08A, 08B

Runs in parallel with: 07

## Implementation record

Implemented on `ai-select-v1` across both runtimes against the pinned contract
in `.scratch/ai-select-v1/04C-protocol-contract.md`:

- Companion: `sam3-image-instance/v1` adapter on the official
  `build_sam3_image_model(enable_inst_interactivity=True)` →
  `Sam3Processor.set_image` → `predict_inst` path with pinned
  `SAM3_IMAGE_RUNTIME_CONFIG` (`sha256:736e6c4e…`), new
  `sam3-image-instance-compiler/v1` Prompt v2 compiler, multimask policy
  (≤3 single-positive-point / ≤1 otherwise), immutable RGB artifact/reference
  resolution (`rgbUnresolvable` fails before inference), Companion-local
  logits store behind opaque `PreviousPredictionLogitsRef` with fallback
  semantics, and install/readiness hard gates. The static Multiplex
  interactive-image path (`produce_ai_select_visual_proposals`,
  `_build_sam3_interactive_image_predictor`, `_Sam31InteractiveImageSession`,
  `_forward_sam_heads`) is deleted; legacy `produce_tracks` remains only as a
  non-current benchmark fixture and a `sam3.1` manifest fails closed on the
  current route.
- Editor: PromptState schema v2 (Positive/Negative Point + ≤1 Positive
  Instance Box pixel XYXY), rotated capability record/digest, removed
  Negative Box / Mask Constraint / Prompt Brush / Text from schema, toolbar,
  palette, and locales, request-level `rgbDigest` + optional artifact +
  optional `previousLogitsRef`, proposal set v3 with policy-driven candidate
  bounds, refinement lineage with Retry-mints-new-attempt semantics, and
  readiness-gated capability derivation in `main.ts`.
- Cross-runtime wire audit: editor-produced PromptState/capability/ref
  payloads validated by the Python compiler and digest code, and
  Companion-produced fresh/refinement/fallback exchanges validated by the
  editor's fail-closed response gates
  (`.scratch/ai-select-v1/04c-cross-check-*.py/.cjs`).
- Validation run: `npm test` (330 TS + 299 Companion tests, 1 env-gated GPU
  skip), `npm run lint`, `npm run lint:locales`, `npm run build`. The locked
  SAM 3 Image GPU fixture (`test_sam3_image_instance_gpu.py`) subsequently
  ran on an RTX 4090 D with the operator `sam3.pt` checkpoint and passed
  (multimask point, single box, single refinement, static audits). Its first
  production run exposed that the pinned upstream returns low-resolution
  logits at 288×288 (backbone feature size), not SAM 2's 256×256; the pinned
  `low_res_logits_size` and runtime config digest were corrected to 288
  (`sha256:736e6c4e…`), which is why the first production requests failed
  closed with `modelFailure` before this fix. The first live HTTP run then
  exposed a second real-model defect: the model builder leaks an enabled
  autocast state into its calling thread and autocast state is thread-local,
  so HTTP handler threads executed `set_image` outside bf16 autocast and
  failed with a BFloat16/Float mismatch. Both `set_image` and `predict_inst`
  now establish the pinned inference_mode + bf16 autocast scope explicitly
  on every entry point, the GPU fixture covers a handler-thread inference,
  and the live route was verified returning three bound candidates with
  opaque logits refs. Operator-facing logs now preserve the underlying
  model failure cause while the wire keeps the generic `modelFailure` code.

## Final Spec mapping

- Final Spec v1.3 §§4, 6–8, 11, 16, 19, 24–26
- ADR 0016

## Purpose

Replace the current static SAM 3.1 Multiplex/private-tracker-head path with the official SAM 3 Image instance-interaction path and shrink the v1 Prompt contract to supported instance semantics.

```text
SAM 3 Image model
+ Positive/Negative Points
+ optional Positive Instance Box
+ Companion-local previous-prediction logits
→ bounded instance Mask result
```

This is a production migration, not a model-comparison gate.

## Required model path

The current static path MUST use the pinned public upstream surface equivalent to:

```text
build_sam3_image_model(enable_inst_interactivity=True)
→ Sam3Processor.set_image(authoritativeRgb)
→ model.predict_inst(inferenceState, ...)
```

Requirements:

- use a SAM 3 Image checkpoint and new Model Manifest identity;
- bind exact upstream source commit, checkpoint digest, runtime configuration and adapter version;
- do not instantiate `build_sam3_multiplex_video_predictor` for Anchor or independent Key-View Mask generation;
- do not call private Multiplex tracker-head feature methods or fabricate multiplex state;
- every inference request carries either the exact authoritative RGB artifact or a Companion-resolvable immutable RGB reference whose digest matches the request identity;
- digest-only input without resolvable RGB bytes is invalid;
- output crosses the browser boundary only as generic Mask, score, opaque previous-logits reference and diagnostics metadata;
- release image/model/refinement state deterministically on cancellation, failure and target disposal.

## Prompt schema migration

The current v1 PromptState contains only:

```text
Positive Point
Negative Point
at most one Positive Instance Box
```

Remove from current schema, toolbar, capability record, compiler and request protocol:

```text
Negative Box
Positive Mask Constraint
Negative Mask Constraint
Prompt Brush
Text Prompt
```

Paint and Erase remain Editing Mask operations and MUST NOT enter model requests.

Migration rules:

- rotate PromptState schema/version and capability digest;
- old artifacts containing excluded Box polarity, `maskConstraints` or Text fields fail closed;
- no best-effort conversion from Negative Box or Prompt Brush into Points;
- remove misleading normalized left-top XYWH fields from the instance Box program;
- Instance Box uses authoritative-image pixel XYXY only;
- unsupported old tools are removed from ordinary UI rather than retained as permanent disabled placeholders.

## Single-result policy

```text
Positive/Negative Points
or Positive Box
or previous-logits refinement
→ multimask_output=false
→ retain at most 1 candidate
```

Rules:

- model score is not a correctness probability;
- no result becomes Stable automatically;
- exact duplicate Masks may be removed without introducing a general clustering framework;
- every candidate binds RGB, PromptState, adapter/model/runtime, attempt and output index.

## PreviousPredictionLogitsRef

The actual low-resolution continuous logits tensor remains Companion-local disposable state. The browser may receive only an opaque, digest-bound reference equivalent to:

```ts
interface PreviousPredictionLogitsRef {
    schemaVersion: number;
    companionInstanceId: string;
    stateId: string;
    targetContextId: string;
    viewId: string;
    rgbDigest: string;
    sourceInferenceAttemptId: string;
    sourceCandidateId: string;
    adapterRuntimeDigest: string;
    shape: readonly number[];
    dtype: string;
    dataDigest: string;
    refDigest: string;
}
```

Requirements:

- raw logits bytes/tensors do not enter PromptState, browser persistence or user-visible artifacts;
- the reference resolves only inside the exact Companion Instance that owns `stateId`;
- it is reusable only for the same View/RGB/adapter lineage and currently chosen candidate;
- adding Points with a valid reference forces single-mask mode and creates a new inference attempt linked to the source attempt;
- candidate choice and Prompt refinement occur before `Accept` while still in Prompt mode;
- after `Accept`, Paint/Erase operate on Editing Mask; returning to Prompt mode is explicit and mints a new inference attempt;
- Retry without explicit refinement does not silently reuse logits;
- Companion restart/Instance replacement, target disposal, RGB change or adapter/runtime change invalidates the reference;
- an expired/missing reference falls back to a fresh Point/Box prediction without `mask_input`, never to binary Brush conversion;
- logits are not Stable Mask, Editing Mask, Evidence or cross-View state.

## Capability contract

Advertise exact current capabilities equivalent to:

```ts
{
    positivePoints: true,
    negativePoints: true,
    positiveInstanceBox: true,
    previousLogitsRefinement: true,
    singlePointMultimask: true,
    negativeBox: false,
    promptBrush: false,
    maskConstraints: false,
    text: false
}
```

Removed fields may be absent in the new schema. Compatibility validation rejects clients requiring them.

## Legacy isolation

Retire or isolate:

- `sam3.1-interactive-image/v1` built from Multiplex internals;
- static `Sam3PointMaskAdapter.produce_tracks()` behavior;
- private `_forward_sam_heads()` static shim;
- Multiplex-specific runtime configuration in the Active Model Manifest;
- binary Brush-to-`mask_input` fixtures except as negative regression;
- generic `maskSource: 'propagated'` assumptions.

The old Multiplex implementation may remain as a non-current benchmark fixture only. It must not advertise Ready for current static instance segmentation.

## Acceptance criteria

### Model and RGB

- [x] Anchor and single-image tests use the official SAM 3 Image path.
- [x] no current static request instantiates the Multiplex video predictor.
- [x] no current static adapter calls private tracker-head feature methods.
- [x] a new SAM 3 Image Model Manifest/runtime digest is required for readiness.
- [x] every provider request includes resolvable authoritative RGB plus matching digest/dimensions.
- [x] digest-only requests with no RGB artifact/reference fail before inference.

### Prompt behavior

- [x] Positive and Negative Points work end to end.
- [x] one Positive Instance Box works in authoritative pixel XYXY.
- [x] Negative Box, Prompt Brush, Mask Constraints and Text are absent from current Prompt UI/schema.
- [x] Paint/Erase never appear in a model request.
- [x] old Prompt artifacts fail by version/capability identity.

### Candidate and refinement behavior

- [x] Point, Box and refinement requests return at most one candidate.
- [x] candidate Masks, scores and references have matching cardinality.
- [x] raw logits tensors remain Companion-local; only opaque refs cross the protocol.
- [x] valid refs refine the same image under exact Companion/candidate lineage.
- [x] Companion replacement or stale ref causes fresh no-logits inference.
- [x] binary Brush data cannot validate as a logits ref.
- [x] model score only orders preview and never confirms a Mask.

### Migration and recovery

- [x] existing User Confirmed Stable Masks survive migration.
- [x] old in-flight/cached Multiplex results cannot attach to the new adapter revision.
- [x] cancellation/OOM/model failure publishes no partial Mask or refinement ref.
- [x] explicit Retry mints a new attempt.

## Validation

- repository tests, Companion tests, lint, locales and build;
- locked SAM 3 Image GPU fixture;
- authoritative RGB payload/reference resolution fixture;
- single-result Point fixture;
- Box/multi-point single-mask fixtures;
- previous-logits-ref refinement and Companion-restart invalidation fixtures;
- old Prompt/manifest/cache rejection fixtures;
- static import/call audit proving Multiplex absence.

## Non-goals

- No video or dense sequence tracking.
- No multi-object Multiplex workload.
- No Negative Box or Prompt Brush adapter.
- No Text grounding.
