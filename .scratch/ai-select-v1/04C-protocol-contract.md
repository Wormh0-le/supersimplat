# 04C Protocol Contract — SAM 3 Image Instance Adapter Migration

Working design note pinning the exact editor↔Companion contract for ticket
`.scratch/ai-select-v1/issues/04C-sam3-image-instance-adapter-migration.md`.
Both implementation slices (Companion Python, Editor TypeScript) implement
against this document. It is a scratch coordination artifact, not a spec; Final
Spec v1.3 / ADR 0016 remain authoritative for semantics.

## 1. Identities (exact strings)

| Concept                    | Value                                                                                                                                                                         |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Adapter ID                 | `sam3-image-instance/v1` (already `SAM3_IMAGE_INSTANCE_ADAPTER_ID` in `state.py`)                                                                                             |
| Compiler policy            | `sam3-image-instance-compiler/v1`                                                                                                                                             |
| PromptState schemaVersion  | `2`                                                                                                                                                                           |
| Proposal policy            | `auto-mask-proposals/bounded-source-order-v2`                                                                                                                                 |
| Ranking policy             | `anchor-mask-ranking/v2`                                                                                                                                                      |
| Proposal set schemaVersion | `3` (TS `AutoMaskProposalSet.schemaVersion`, Python proposal-set builder, readiness `supportedOperations` entry renamed `autoMaskProposalSetSchemaV3` everywhere it is gated) |
| Runtime profile            | unchanged: `ai-select-static-image-instance/v1`, readiness protocol `"2"`                                                                                                     |

Legacy identities stay reserved and non-current: `sam3.1` adapter,
`sam3.1-interactive-image/v1`, `sam3.1-visual-prompt-compiler/v1`,
`point-mask-compiler/v1`, `auto-mask-proposals/bounded-source-order-v1`,
`anchor-mask-ranking/v1`, proposal set schema v1/v2. Old artifacts carrying them
fail closed on the current route (version/capability-digest mismatch).

## 2. Companion runtime config (new, pinned)

`masking.py` gains:

```python
SAM3_IMAGE_RUNTIME_CONFIG = {
    "anchor_prompt_adapter": "sam3-image-instance/v1",
    "anchor_prompt_compiler_policy": "sam3-image-instance-compiler/v1",
    "image_model_builder": "sam3.build_sam3_image_model",
    "enable_inst_interactivity": True,
    "processor_resolution": 1008,
    "confidence_threshold": 0.5,
    "multimask_policy": "single-positive-point-multimask/v1",
    "max_multimask_candidates": 3,
    "low_res_logits_size": 288,
    "reject_full_frame_masks": True,
    "autocast_dtype": "bfloat16",
    "compile": False,
    "load_from_hf": False,
}
SAM3_IMAGE_RUNTIME_CONFIG_DIGEST = "sha256:" + sha256(canonical json)
```

`install_model` rule: `adapterId == "sam3-image-instance/v1"` requires
`runtimeConfigDigest == SAM3_IMAGE_RUNTIME_CONFIG_DIGEST` (same hard-gate
pattern as the existing `sam3.1` rule at `state.py:999-1005`). New sample
manifest `selection-service-companion/sam3-image.json` (adapterId
`sam3-image-instance/v1`, sourceCommit `5dd401d1c5c1d5c3eedff06d41b77af824517619`,
operator checkpoint digest placeholder); `sam31.json` stays for the legacy
benchmark fixture only.

`adapterRuntimeDigest` (embedded in logits refs, Companion-computed, opaque to
editor):

```text
sha256 over canonical JSON of:
{ adapterId, compilerPolicyVersion, runtimeConfigDigest, checkpointDigest, sourceCommit }
```

## 3. Adapter capability record (identical both sides)

```json
{
    "positivePoints": true,
    "negativePoints": true,
    "positiveInstanceBox": true,
    "previousLogitsRefinement": true,
    "singlePointMultimask": true,
    "negativeBox": false,
    "promptBrush": false,
    "maskConstraints": false,
    "text": false,
    "compilerPolicyVersion": "sam3-image-instance-compiler/v1",
    "capabilityDigest": "sha256:<over the 10 fields above, canonical sorted JSON>"
}
```

- Python: `sam3_image_instance_capabilities()` in `masking.py` (mirrors
  `sam31_visual_prompt_capabilities` digest mechanics). No
  `unsupportedPromptReasons` — removed families are not tools anymore.
- TS: new `PromptAdapterCapabilities` shape in `src/ai-select/prompt-state.ts`
  = the 9 booleans + `compilerPolicyVersion` + `capabilityDigest`;
  `createPromptAdapterCapabilities` computes the digest;
  `isPromptAdapterCapabilities` validates exact keys + recomputes digest.
- Readiness handoff: Companion `imageInstanceProvider` payload gains
  `compilerPolicyVersion` and `adapterCapabilityDigest` at provider level
  (pass-through in `_image_instance_provider_capability` when the adapter
  reports ready; absent when unavailable). TS
  `SelectionServiceImageInstanceProviderCapability` gains the same two optional
  fields; the profile gate requires them when `status === 'ready'`.
  `main.ts getPromptAdapterCapabilities` builds `PromptAdapterCapabilities`
  from readiness state (9 flags + compilerPolicyVersion) and returns null
  unless the recomputed digest equals the advertised `adapterCapabilityDigest`
  and the readiness profile is fully ready.

## 4. PromptState v2 (identical both sides)

```ts
interface PromptState {
    schemaVersion: 2;
    viewId: string;
    rgbDigest: string; // sha256 of authoritative RGB PNG bytes
    revision: number;
    points: PointPrompt[]; // polarity 'include' | 'exclude', pixel x/y
    boxes: BoxPrompt[]; // length 0 or 1, polarity MUST be 'include', pixel XYXY (x0<x1, y0<y1)
    digest: string; // sha256 over canonical payload (all fields except digest)
}
```

- REMOVED fields: `maskConstraints`, `textPrompts`, negative box polarity,
  any normalized XYWH. Old artifacts fail closed via exact-key + schemaVersion
    - digest-recompute validation on both sides.
- `PromptTool` = `'positive-point' | 'negative-point' | 'positive-box'`.
  Paint/Erase are NOT PromptTools and never enter PromptState or requests.
- Adding a box when one exists replaces it (keeps the ≤1 invariant).
- ≥1 prompt required for a model request (Companion rejects empty programs).

## 5. Mask proposal request (route `POST /ai-select/mask-proposals`)

```ts
interface AIViewMaskRequest {
    requestBinding: AIRequestBinding; // unchanged
    target: AITarget; // unchanged
    sceneId: string;
    sceneVersion: string;
    viewId: string;
    cameraBindingDigest: string;
    rgbDigest: string; // ALWAYS present
    rgbWidth: number;
    rgbHeight: number; // ALWAYS present, positive ints
    rgb?: AnchorRgbArtifact; // optional; if present digest+dims must match
    promptState: PromptState; // v2; rgbDigest/viewId must match request
    previousLogitsRef?: PreviousPredictionLogitsRef;
    modelManifestDigest: string;
    adapterCapabilityDigest: string; // must equal current capability record digest
    proposalPolicyVersion: 'auto-mask-proposals/bounded-source-order-v2';
    rankingPolicyVersion: 'anchor-mask-ranking/v2';
    proposalAttemptId: string;
}
```

Rules:

- `rgb` absent ⇒ Companion resolves `rgbDigest` against its immutable RGB
  cache; miss ⇒ `MaskSessionError('rgbUnresolvable')` BEFORE inference.
  Digest-only with no resolvable bytes is invalid.
- Companion RGB cache: digest → (png bytes, width, height), populated by the
  anchor-render route output and by every request carrying `rgb`; bounded (≤16
  entries, FIFO); cleared with `_release_all_transient_caches_locked`.
- Editor rule: first request for an `rgbDigest` in a target context carries the
  artifact; later requests for the same digest may omit it. Responses match on
  `rgbDigest` (not on artifact presence).
- `previousLogitsRef` present ⇒ refinement attempt: Companion resolves the ref
  (§7); unresolvable ⇒ fresh no-`mask_input` inference (never an error, never
  brush conversion). Refinement forces single-mask mode.

## 6. Multimask policy

```text
multimask_output = true  IFF  exactly 1 point AND that point is 'include'
                              AND no box AND no resolved previousLogitsRef
                   → retain at most 3 candidates
else               → multimask_output = false → retain at most 1 candidate
```

- Python: pure helper `resolve_multimask_output(program, has_refinement)` in
  `masking.py`; adapter enforces cap after filtering empty/full-frame masks and
  removing exact duplicate masks (byte-identical `bitset-lsb-v1` payloads).
- TS: `maximumAutoMaskProposalCount(promptState, hasRefinement)` replaces the
  flat `maximumAutoMaskProposalCount = 4`.
- Model score orders preview only; never auto-confirms. Candidate cardinality
  of masks/scores/refs must match (ref per retained candidate).

## 7. PreviousPredictionLogitsRef (wire shape, per ticket)

```ts
interface PreviousPredictionLogitsRef {
    schemaVersion: 1;
    companionInstanceId: string;
    stateId: string;
    targetContextId: string;
    viewId: string;
    rgbDigest: string;
    sourceInferenceAttemptId: string;
    sourceCandidateId: string; // == proposalId of the source candidate
    adapterRuntimeDigest: string;
    shape: readonly number[]; // e.g. [1, 288, 288]
    dtype: string; // 'float32'
    dataDigest: string; // sha256 of raw logits bytes
    refDigest: string; // sha256 over canonical JSON of all fields above
}
```

- Raw logits/inference state NEVER cross the wire; editor validates structure +
  recomputes `refDigest`; everything else opaque.
- Companion logits store (on `CompanionState`, cleared by
  `_release_all_transient_caches_locked`): `stateId → { logits, inferenceState,
targetContextId, viewId, rgbDigest, sourceAttemptId, sourceCandidateId,
adapterRuntimeDigest, dataDigest }`, ≤8 entries FIFO. Entries are minted only
  on the success path of a proposal request (atomic with publication; failure /
  cancellation / OOM ⇒ no ref published, no partial store mutation).
- Resolution checks (any failure ⇒ silent fallback to fresh inference with a
  `refinementFallback` diagnostic in the response diagnostics):
    1. `refDigest` recomputes; 2. `companionInstanceId` == this process;
    2. `stateId` in store; 4. entry's targetContextId/viewId/rgbDigest match the
       request; 5. entry's `adapterRuntimeDigest` == current; 6. stored dataDigest
       still matches logits bytes.
- Refinement reuses the stored inference state + logits as `mask_input`,
  forces `multimask_output=false`, mints a NEW ref whose
  `sourceInferenceAttemptId` is the OLD attempt id (attempt linkage).
- Retry (explicit, no prompt change) ⇒ editor omits `previousLogitsRef`.
- After Accept, editor clears its held ref; returning to Prompt mode mints a
  fresh attempt.

## 8. Response / proposal set v3

Proposal (per candidate): `proposalId` (`proposal-{sourceIndex}`), `mask`
(bitset-lsb-v1), `sourceIndex`, `modelScore?`, `modelScoreSemantics?`,
`promptConsistency`, `promptDiagnostics`, optional `logitsRef` (§7).
Every candidate binds RGB digest, PromptState digest, adapter/model/runtime,
attempt, output index via the proposal-set identity digest.

`PromptConsistencyFacts` shrinks to:
`{ positivePointsSatisfied, negativePointsSatisfied, positiveBoxesSatisfied }`
(text/mask-constraint/negative-box facts removed). `PromptDiagnosticFamily` =
`'point' | 'box'`. `proposal_ranking.py` features updated accordingly;
`RANKING_POLICY_VERSION = 'anchor-mask-ranking/v2'`.

Diagnostics for refinement fallback: proposal set `diagnostics` (or per-set
field) carries `refinementFallback: true` when a supplied ref was not resolved.

## 9. Companion adapter (new code)

New `Sam3ImageInstanceAdapter` in `masking.py` (or a new
`sam3_image_adapter.py` imported by `masking.py` — implementer choice, keep
`masking.py` importable without torch):

- `runtime_profile_capability()` → ready/unavailable + `authoritativeRgb
{artifact: true, companionReference: true}` + the 9 prompt flags +
  `compilerPolicyVersion` + `adapterCapabilityDigest`. Unavailable (with
  message) when the checkpoint cannot be initialized.
- Model builder (injectable for tests): default
  `build_sam3_image_model(enable_inst_interactivity=True,
checkpoint_path=<manifest weightsPath>, load_from_HF=False)` →
  `Sam3Processor(model)` → `set_image(PIL RGB)` → `model.predict_inst(
inference_state, point_coords=..., point_labels=..., box=...(XYXY pixels),
mask_input=..., multimask_output=..., return_logits=False,
normalize_coords=True)`; request low-res logits (third return value,
  Cx288x288) for ref minting. bf16 autocast on CUDA per upstream example.
- Built model cached per manifest digest (Companion-local disposable cache);
  inference/refinement state released on cancellation, failure, target
  disposal, and cache eviction.
- Must NOT import/instantiate `build_sam3_multiplex_video_predictor` or call
  private tracker-head methods.

Legacy isolation in `masking.py`:

- Delete `Sam3PointMaskAdapter.produce_ai_select_visual_proposals`,
  `_build_sam3_interactive_image_predictor`, `_Sam31InteractiveImageSession`,
  and the `_forward_sam_heads` shim (the retired static private-tracker path).
- `Sam3PointMaskAdapter.produce_tracks` + `_build_sam3_predictor` stay ONLY for
  the legacy object-selection PoC flow (benchmark fixture); mark non-current in
  comments. A `sam3.1` manifest on the current mask-proposals route now fails
  closed (adapter has no visual-proposal capability).
- `compile_sam31_visual_prompt_program` is removed;
  `compile_point_mask_prompt_program` is reimplemented standalone (points-only)
  so the deterministic `point-mask-v1` reference adapter keeps working.
- New compiler `compile_sam3_image_prompt_program()` enforcing §4 (exact keys,
  schemaVersion 2, digest recompute, ≤1 include-only box, in-bounds points,
  unique promptIds, capability digest match).

`state.py` wiring:

- `_prompt_capabilities_for_adapter('sam3-image-instance/v1')` →
  `sam3_image_instance_capabilities()`.
- `produce_ai_select_mask` parses §5 request shape (rgbDigest/width/height
  always; optional rgb artifact; optional previousLogitsRef), resolves RGB +
  refinement, dispatches to the new adapter, mints refs on success, v3 proposal
  set, `bounded-source-order-v2` policy gate.
- `_image_instance_provider_capability` passes through
  `compilerPolicyVersion` + `adapterCapabilityDigest` when ready.
- RGB cache + logits store lifecycle as §5/§7.
- `install_model` hard gate for the new adapterId.

## 10. Editor changes

- `prompt-state.ts`: schema v2 per §4; `PromptTool` shrunk; capability record
  per §3; `promptStateHasConstraints` = points+boxes; old-shape artifacts fail
  `isPromptState`.
- `mask-service.ts`: request/response per §5/§8 (rgbDigest/width/height always,
  optional artifact, optional `previousLogitsRef`; `isPreviousPredictionLogitsRef`
  with refDigest recompute; response match updated).
- `mask-proposal.ts`: schema v3, policy-driven candidate bound, shrunk
  consistency facts, `logitsRef` on proposals, policy/ranking version rotation.
- `mask-controller.ts` / `anchor-controller.ts`: positive-box only, box
  replace semantics, refinement lineage (hold chosen candidate's `logitsRef`;
  send on prompt revision; omit on Retry; clear on Accept/RGB/view/target
  change), rgb artifact first-then-reference rule, anchor auto masks register
  `maskSource: 'single-frame-sam'` (generated-view 'propagated' path is owned
  by later tickets — leave it).
- `ai-select-anchor-dock.ts`: remove negative-box/mask-constraint/text tools,
  text input, prompt-brush slider gating; keep Paint/Erase untouched; removed
  tools are deleted, not disabled placeholders.
- `static/locales/*.json`: remove keys for deleted tools
  (`npm run lint:locales` must pass).
- `selection-service-readiness.ts`: provider capability gains
  `compilerPolicyVersion` + `adapterCapabilityDigest` (required when ready);
  rename the proposal-set schema operation gate to v3 if gated.
- `main.ts`: real `getPromptAdapterCapabilities` per §3.

## 11. Tests

Python (`selection-service-companion/tests/`):

- compiler v2: schema/digest/box rules, removed-field rejection.
- adapter multimask policy via fake builder (3 vs 1 candidates, dedupe,
  empty/full-frame filtering).
- logits ref lifecycle: mint, refine-with-ref (single mask, attempt linkage),
  fallback on companion restart / adapter change / RGB change / unknown
  stateId, binary-brush bytes rejected as ref, no ref on cancellation/failure.
- RGB reference: artifact-then-reference flow, `rgbUnresolvable` on miss.
- route: old PromptState v1 / old capability digest / sam3.1 manifest rejected;
  capability digest mismatch rejected.
- update `test_runtime_profile_readiness.py` expectations for pass-through
  digest fields; keep the sam3.1-unavailable test.
- rewrite `test_sam31_visual_prompt_gpu.py` → `test_sam3_image_instance_gpu.py`
  (env-gated `SUPERSPLAT_SAM3_IMAGE_GPU_CHECKPOINT`): official image path,
  multimask 3, box single, refinement single; static audit asserting no
  multiplex/private-tracker use in the current static path.
- migrate `test_ai_select_masks.py` route tests to the new adapter/capability
  identity; keep `test_mask_sessions.py` legacy flow green.

TS (`test/`): prompt-state v2 validation/migration failure, capability digest,
mask-service request/response (rgbRef, logitsRef, stale discard), controller
(refinement lineage, Retry, Paint/Erase never in requests, box replace),
proposal v3 bounds, readiness provider gate, dock tool set. Update every test
constructing PromptState v1.

## 12. Explicit non-goals for these slices

- No generated-view acquisition changes (08A/08B own per-view SAM 3 Image).
- No video/tracking, no Negative Box/Brush/Text adapters.
- Legacy object-selection session PoC routes stay as-is (ticket 22 owns
  closure); only their static visual-proposal path is retired.
- GPU fixtures are env-gated; CI here runs CPU-only (record as unverified GPU).
