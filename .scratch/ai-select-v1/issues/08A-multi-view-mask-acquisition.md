# 08A — Compact Per-View Image Instance Mask Contracts

Status: planned — contract foundation

Blocked by: 08, 04C

Blocks: 08B

## Final Spec mapping

- Final Spec v1.3 §§4, 6, 9–13, 16, 19, 24–26
- ADR 0016

## Purpose

Define the small immutable contracts required to reuse the Ticket 04C SAM 3 Image instance adapter on Generated and User-added Views.

This ticket does not implement Prompt synthesis, camera planning, SAM inference, Mask Review, Stable publication, Gallery, tracker behavior or Gaussian Evidence.

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
    previousLogitsArtifactDigest?: string;
    multimaskOutput: boolean;
    artifactDigest: string;
}
```

Rules:

- authoritative pixel coordinates only;
- at most one Positive Instance Box;
- no Negative Box, Mask Constraint, Prompt Brush or Text fields;
- previous logits are optional internal refinement identity, never embedded binary Brush data;
- Generated Key Views normally bind geometry/plan/policy digests;
- Anchor/User-added manual Prompts may omit geometry/plan fields;
- exact same inputs produce the same canonical artifact.

## PreviousPredictionLogitsArtifact

Reuse the 04C contract. Per-View contracts validate that logits match the exact View/RGB/adapter lineage and are not cross-View reusable.

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
    inferenceAttemptId: string;
}
```

## ImageInstanceMaskResult

```ts
interface ImageInstanceMaskResult {
    schemaVersion: number;
    requestIdentity: ImageInstanceMaskRequestIdentity;
    masks: readonly MaskArtifact[];
    modelScores: readonly number[];
    lowResolutionLogits?: readonly PreviousPredictionLogitsArtifact[];
    diagnostics: ImageInstanceMaskDiagnostics;
    resultDigest: string;
}
```

Invariants:

- result exactly echoes accepted request identity;
- masks, scores and logits cardinality match when logits are present;
- `multimaskOutput=false` produces at most one usable Mask;
- `multimaskOutput=true` produces at most three;
- empty result is representable as semantic unavailable;
- transport/runtime/OOM/cancellation failure produces no partial result;
- model score is adapter-local preview ordering only;
- diagnostics cannot publish Stable Mask, Participation, Evidence or Candidate.

## Provider seam

```ts
interface ImageInstanceMaskProvider {
    infer(
        prompt: ImageInstancePromptArtifact,
        requestIdentity: ImageInstanceMaskRequestIdentity
    ): Promise<ImageInstanceMaskResult>;
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

- [ ] Every public artifact is schema-versioned and canonical-digestable.
- [ ] Removed Prompt fields fail structural validation.
- [ ] one Box maximum and pixel XYXY semantics validate.
- [ ] previous logits bind exact View/RGB/adapter/source candidate.
- [ ] result cardinality matches multimask policy.
- [ ] empty semantic result is distinct from technical failure.
- [ ] technical failure exposes no partial Mask/logits result.
- [ ] provider output contains no Review, Stable publication, Participation, Evidence or Candidate.
- [ ] no backend registry/sequence/fallback schema is required by readiness.
- [ ] golden vectors cover valid and stale cross-artifact identity.

## Validation

- schema/digest golden vectors;
- single-mask and three-mask cardinality fixtures;
- previous-logits cross-View/stale rejection;
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
