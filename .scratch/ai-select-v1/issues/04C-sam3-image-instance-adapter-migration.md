# 04C — SAM 3 Image Instance Adapter + Prompt Contract Migration

Status: ready-for-agent — critical model migration gate

Blocked by: 04B

Blocks: 02C, 07A, 08A, 08B

Runs in parallel with: 07

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

## Multimask policy

```text
exactly one Positive Point
+ no Box
+ no previous logits
→ multimask_output=true
→ retain at most 3 candidates

Positive Box
or multiple Points
or previous-logits refinement
→ multimask_output=false
→ retain at most 1 candidate
```

Rules:

- model score may define default preview ordering only;
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

- [ ] Anchor and single-image tests use the official SAM 3 Image path.
- [ ] no current static request instantiates the Multiplex video predictor.
- [ ] no current static adapter calls private tracker-head feature methods.
- [ ] a new SAM 3 Image Model Manifest/runtime digest is required for readiness.
- [ ] every provider request includes resolvable authoritative RGB plus matching digest/dimensions.
- [ ] digest-only requests with no RGB artifact/reference fail before inference.

### Prompt behavior

- [ ] Positive and Negative Points work end to end.
- [ ] one Positive Instance Box works in authoritative pixel XYXY.
- [ ] Negative Box, Prompt Brush, Mask Constraints and Text are absent from current Prompt UI/schema.
- [ ] Paint/Erase never appear in a model request.
- [ ] old Prompt artifacts fail by version/capability identity.

### Candidate and refinement behavior

- [ ] one positive point returns at most three candidates.
- [ ] Box, multiple Points and refinement return at most one candidate.
- [ ] candidate Masks, scores and references have matching cardinality.
- [ ] raw logits tensors remain Companion-local; only opaque refs cross the protocol.
- [ ] valid refs refine the same image under exact Companion/candidate lineage.
- [ ] Companion replacement or stale ref causes fresh no-logits inference.
- [ ] binary Brush data cannot validate as a logits ref.
- [ ] model score only orders preview and never confirms a Mask.

### Migration and recovery

- [ ] existing User Confirmed Stable Masks survive migration.
- [ ] old in-flight/cached Multiplex results cannot attach to the new adapter revision.
- [ ] cancellation/OOM/model failure publishes no partial Mask or refinement ref.
- [ ] explicit Retry mints a new attempt.

## Validation

- repository tests, Companion tests, lint, locales and build;
- locked SAM 3 Image GPU fixture;
- authoritative RGB payload/reference resolution fixture;
- single-point multimask fixture;
- Box/multi-point single-mask fixtures;
- previous-logits-ref refinement and Companion-restart invalidation fixtures;
- old Prompt/manifest/cache rejection fixtures;
- static import/call audit proving Multiplex absence.

## Non-goals

- No video or dense sequence tracking.
- No multi-object Multiplex workload.
- No Negative Box or Prompt Brush adapter.
- No Text grounding.
