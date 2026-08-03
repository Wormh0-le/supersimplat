# 08A — Compact Per-View Image Instance Mask Contracts

Status: implemented — contract foundation (no production per-View SAM execution)

Blocked by: 08, 04C

Blocks: 08B

## Final Spec mapping

- Final Spec v1.3 §§4, 6, 9–13, 16, 19, 24–26
- ADR 0016

## Purpose

Define the small immutable contracts required to reuse the Ticket 04C SAM 3 Image instance adapter on Generated and User-added Views.

This ticket does not implement Prompt synthesis, camera planning, SAM inference, Mask Review, Stable publication, Gallery, tracker behavior or Gaussian Evidence.

## Implementation record

Implemented on `ai-select-v1` as a bounded cross-runtime contract slice:

- `src/ai-select/image-instance-mask.ts` provides immutable, canonical-digested Prompt, RGB-reference, request, result, opaque-ref matching, and publication-command contracts. `inferImageInstanceMask()` validates requests before provider invocation and validates the complete echoed result before it can enter browser state.
- `selection-service-companion/src/selection_service_companion/image_instance_mask_contract.py` mirrors Companion-facing request/result and RGB-resolution validation without adding a route, model execution path, backend registry, tracker, or publication side effect.
- Shared golden vectors verify canonical Prompt, request identity, opaque logits reference, stale RGB, Companion replacement, and result score identity on both runtimes.

This is contract foundation only. Ticket 08B remains responsible for 3D-guided Prompt synthesis, provider route/orchestration, SAM execution, Mask Review, and automatic Stable publication.

## ImageInstancePromptArtifact

```ts
interface ImageInstancePromptArtifact {
    schemaVersion: number;
    targetContextId: string;
    contextRevision: number;
    viewId: string;
    rgbDigest: string;
    cameraBindingDigest: string;
    targetGeometryHintDigest?: string;
    localKeyViewPlanDigest?: string;
    adapterCapabilityDigest: string;
    promptSynthesisPolicyDigest?: string;
    positivePoints: readonly PixelPoint[];
    negativePoints: readonly PixelPoint[];
    positiveBox?: PixelBoxXYXY;
    previousLogitsRefDigest?: string;
    multimaskOutput: boolean;
    artifactDigest: string;
}
```

Rules:

- authoritative pixel coordinates only;
- at most one Positive Instance Box;
- no Negative Box, Mask Constraint, Prompt Brush or Text fields;
- previous logits are referenced only through the 04C opaque ref, never embedded as binary or tensor data;
- Generated Key Views normally bind geometry/plan/policy digests;
- Anchor/User-added manual Prompts may omit geometry/plan fields;
- exact same inputs produce the same canonical artifact.

## Authoritative RGB input

A provider request must include resolvable authoritative RGB, not only `rgbDigest`:

```ts
interface ImageInstanceRgbInput {
    rgbDigest: string;
    width: number;
    height: number;
    artifact?: AuthoritativeRgbArtifact;
    companionRgbRef?: CompanionRgbArtifactRef;
}
```

Exactly one payload/reference form is present. A Companion RGB reference must resolve to immutable bytes in the current Companion Instance and reproduce the declared digest/dimensions. Digest-only input is invalid.

## PreviousPredictionLogitsRef

Reuse the Ticket 04C opaque-reference contract.

- actual logits tensor remains Companion-local;
- ref binds Companion Instance, state ID, View/RGB, adapter/runtime, source attempt and candidate;
- no raw logits bytes enter browser persistence or PromptState;
- Companion replacement, state eviction, RGB change or adapter/runtime change invalidates the ref;
- an unavailable ref may be omitted and the request rerun from current Points/Box without `mask_input`.

## ImageInstanceMaskRequestIdentity

```ts
interface ImageInstanceMaskRequestIdentity {
    targetContextId: string;
    contextRevision: number;
    viewId: string;
    rgbDigest: string;
    promptArtifactDigest: string;
    adapterId: string;
    modelManifestDigest: string;
    runtimeDigest: string;
    companionInstanceId: string;
    inferenceAttemptId: string;
}
```

## ImageInstanceMaskRequest

```ts
interface ImageInstanceMaskRequest {
    schemaVersion: number;
    identity: ImageInstanceMaskRequestIdentity;
    rgb: ImageInstanceRgbInput;
    prompt: ImageInstancePromptArtifact;
}
```

The Prompt and RGB inputs must match the request identity exactly.

## ImageInstanceMaskResult

```ts
interface ImageInstanceMaskResult {
    schemaVersion: number;
    requestIdentity: ImageInstanceMaskRequestIdentity;
    masks: readonly MaskArtifact[];
    modelScores: readonly number[];
    previousLogitsRefs?: readonly PreviousPredictionLogitsRef[];
    diagnostics: ImageInstanceMaskDiagnostics;
    resultDigest: string;
}
```

Invariants:

- result exactly echoes accepted request identity;
- resolved RGB bytes match request digest and dimensions;
- Mask, score and optional ref cardinality match;
- `multimaskOutput=false` produces at most one usable Mask;
- `multimaskOutput=true` produces at most three;
- empty result is representable as semantic unavailable;
- transport/runtime/OOM/cancellation failure produces no partial result;
- model score is adapter-local preview ordering only;
- raw logits tensor never crosses the browser boundary;
- diagnostics cannot publish Stable Mask, Participation, Evidence or Candidate.

## Provider seam

```ts
interface ImageInstanceMaskProvider {
    infer(request: ImageInstanceMaskRequest): Promise<ImageInstanceMaskResult>;
}
```

The current provider is the single Active SAM 3 Image adapter from 04C.

There is no current requirement for:

- `MaskAcquisitionBackendRegistry`;
- backend bundle/kind matrix;
- Route B/C/D identifiers;
- sequence extension;
- reference update/repropagation methods;
- automatic Route-A fallback;
- generic KeyViewMaskProposalSet/KeyViewMaskDecision for ordinary Generated Views.

Future video tracking requires a new ADR and separate contract.

## Stable publication input

08A defines a minimal publication command binding:

- exact View/RGB;
- exact Prompt artifact and inference result;
- chosen Mask when Anchor multimask is used;
- exact MaskReviewResult;
- current Stable authority;
- publication policy and attempt identity.

The provider itself cannot publish.

## Acceptance criteria

- [x] every public artifact is schema-versioned and canonical-digestable.
- [x] removed Prompt fields fail structural validation.
- [x] one Box maximum and pixel XYXY semantics validate.
- [x] provider request carries resolvable authoritative RGB plus matching digest/dimensions.
- [x] digest-only or mismatched RGB request fails before inference.
- [x] previous-logits ref binds exact Companion/View/RGB/adapter/source candidate.
- [x] raw logits tensor cannot validate as a browser request payload.
- [x] result cardinality matches multimask policy.
- [x] empty semantic result is distinct from technical failure.
- [x] technical failure exposes no partial Mask/ref result.
- [x] provider output contains no Review, Stable publication, Participation, Evidence or Candidate.
- [x] no backend registry/sequence/fallback schema is required by readiness.
- [x] golden vectors cover valid, stale and Companion-replacement identities.

## Validation

- schema/digest golden vectors;
- RGB artifact/reference resolution and mismatch fixtures;
- single-mask and three-mask cardinality fixtures;
- previous-logits cross-View/stale/Companion-replacement rejection;
- old Negative Box/Mask Constraint schema rejection;
- technical-failure no-partial-result fixture;
- provider/publication separation tests;
- repository test/lint/build.

## Non-goals

- No production SAM execution.
- No Mask Review or publication implementation.
- No candidate ranker or cluster policy.
- No tracker/backend registry.
- No P/N/V.
