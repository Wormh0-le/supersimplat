# 04C — SAM 3 Image Instance Adapter + Prompt Contract Migration

Status: ready-for-agent — next implementation gate

Blocked by: 04B

Blocks: 02C, 07A, 08A, 08B

## Final Spec mapping

- Final Spec v1.3 §§4, 6–8, 11, 16, 24–26
- ADR 0016

## Purpose

Replace the current static SAM 3.1 Multiplex/private-tracker-head path with the official SAM 3 Image instance-interaction path and shrink the v1 Prompt contract to the capabilities actually required and supported.

```text
SAM 3 Image model
+ instance interactivity
+ Positive/Negative Points
+ optional Positive Instance Box
+ internal previous-prediction logits
→ bounded instance Mask result
```

This ticket is a production migration, not an experimental comparison gate.

## Required model path

The current static path MUST use the pinned upstream public surface equivalent to:

```text
build_sam3_image_model(enable_inst_interactivity=True)
→ Sam3Processor.set_image(...)
→ model.predict_inst(...)
```

Requirements:

- use a SAM 3 image checkpoint and a new Model Manifest identity;
- bind exact upstream source commit, checkpoint digest, runtime configuration and adapter version;
- do not instantiate `build_sam3_multiplex_video_predictor` for Anchor or independent Key-View Mask generation;
- do not call private Multiplex tracker-head feature methods or fabricate multiplex state;
- model output crosses the Companion boundary only as generic Mask, score, logits and diagnostics artifacts;
- release model/session memory deterministically on cancellation, failure and target disposal.

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
- old artifacts containing excluded Box polarity or `maskConstraints` fail closed;
- no best-effort conversion from Negative Box or Prompt Brush into Points;
- remove misleading normalized left-top XYWH fields from the instance Box program;
- instance Box uses authoritative-image pixel XYXY only;
- unsupported old tools are removed from ordinary UI rather than left as permanent disabled placeholders.

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
- exact duplicate masks may be removed without introducing a general clustering framework;
- every candidate binds RGB, PromptState, adapter/model/runtime, attempt and output index.

## PreviousPredictionLogitsArtifact

Define an internal artifact equivalent to:

```ts
interface PreviousPredictionLogitsArtifact {
    schemaVersion: number;
    targetContextId: string;
    viewId: string;
    rgbDigest: string;
    sourceInferenceAttemptId: string;
    sourceCandidateId: string;
    adapterRuntimeDigest: string;
    width: number;
    height: number;
    dtype: string;
    dataDigest: string;
    artifactDigest: string;
}
```

Requirements:

- stores continuous low-resolution logits returned by the model;
- never accepts a binary Prompt Brush bitmap;
- reusable only for the same RGB and compatible adapter/runtime lineage;
- adding Points with previous logits forces single-mask mode;
- Retry without explicit refinement does not silently reuse logits from another attempt;
- logits are disposable model interaction state, not Stable Mask or Evidence.

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

The removed fields may be absent in the new schema; compatibility validation must reject clients requiring them.

## Legacy isolation

Retire or isolate:

- `sam3.1-interactive-image/v1` built from Multiplex internals;
- static `Sam3PointMaskAdapter.produce_tracks()` propagation behavior;
- private `_forward_sam_heads()` static session shim;
- Multiplex-specific runtime configuration in the Active Model Manifest;
- binary Brush-to-`mask_input` fixtures as anything other than a negative regression;
- generic `maskSource: 'propagated'` assumptions.

The old Multiplex implementation may remain as a non-current benchmark fixture only. It must not be advertised Ready for AI Select v1 static instance segmentation.

## Acceptance criteria

### Model and runtime

- [ ] Anchor and single-image tests use the official SAM 3 Image model path.
- [ ] No current static request instantiates the Multiplex video predictor.
- [ ] No current static adapter calls private tracker-head feature methods.
- [ ] A new SAM 3 Image Model Manifest/runtime digest is required for readiness.
- [ ] Old Multiplex manifest identity is incompatible with the current static profile.

### Prompt behavior

- [ ] Positive and Negative Points work end to end.
- [ ] One Positive Instance Box works in authoritative pixel XYXY coordinates.
- [ ] Negative Box, Prompt Brush, Mask Constraints and Text are absent from current Prompt UI/schema.
- [ ] Paint/Erase never appear in a model request.
- [ ] Old Prompt artifacts fail by version/capability identity.

### Candidate and refinement behavior

- [ ] One positive point returns at most three candidates.
- [ ] Box, multiple Points and previous-logits refinement return at most one candidate.
- [ ] Candidate masks, scores and logits have matching cardinality and identity.
- [ ] Previous logits refine the same image under exact lineage.
- [ ] Binary brush data cannot validate as previous logits.
- [ ] Model score only orders default preview and never confirms a Mask.

### Migration and recovery

- [ ] Existing User Confirmed Stable Masks survive migration.
- [ ] Old in-flight/cached Multiplex results cannot attach to the new adapter revision.
- [ ] cancellation/OOM/model failure publishes no partial Mask or logits artifact.
- [ ] explicit Retry mints a new attempt.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- locked SAM 3 Image GPU fixture
- single-point multimask fixture
- Box/multi-point single-mask fixtures
- previous-logits refinement fixture
- old Prompt/manifest/cache rejection fixtures
- static-path import/call audit proving Multiplex absence

## Non-goals

- No video or dense sequence tracking.
- No multi-object multiplex workload.
- No Negative Box adapter composition.
- No Prompt Brush adapter.
- No Text grounding.
- No Gaussian ownership, P/N/V or camera planning.
- No generic backend registry.
