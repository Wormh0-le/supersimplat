# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.3

**文档状态：** Current Final Spec / Normative  
**规划版本：** Ticket Graph v2.14 / Ticket 09 frontier
**日期：** 2026-08-07
**适用分支：** `ai-select-v1`  
**决策依据：** ADR 0013、ADR 0015、ADR 0016、ADR 0017

---

# 0. 规范地位

本文件是 AI Select 当前唯一权威产品与工程规格。

它取代 Final Spec v1.2 的当前规范效力。Final Spec v1.1、Amendment 001–005、Final Spec v1.2、ADR 0014 及 DG-20～DG-26 继续作为历史依据，但不得覆盖本文件。

当前 Ticket 映射由 `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md` 维护。发生冲突时，权威顺序为：

1. Final Spec v1.3；
2. 当前 Ticket mapping；
3. ADR 0016；
4. ADR 0017（TargetGeometryHint / Prompt Support 语义）；
5. ADR 0013、ADR 0015；
6. 未冲突的 Ticket acceptance criteria；
7. 当前实现与测试。

历史 Ticket 中的 Negative Box、Prompt Brush、Mask Constraint、Multiplex static path、Route fallback、backend registry 和 adaptive planner 文字均不具有当前规范效力，除非本文件明确保留。

---

# 1. 产品范围

AI Select 一次选择一个 3D Gaussian Splat 场景中的对象实例。

v1 要求：

- 对象级选择，不要求任意部件发现；
- 用户从当前视角建立并确认 Anchor Stable Mask；
- 系统生成少量局部 Key Views，并为每个 View 独立获取对象 Mask；
- 只有 Included Stable Masks 参与 P/N/V Gaussian Evidence 和 Lift；
- 不重新训练输入 3DGS；
- 不要求补全不可见背面、底面或内部；
- 不运行全图对象 inventory；
- 不把模型分数、2.5D geometry、Prompt 或 previous logits 当成 Gaussian ownership。

---

# 2. 当前产品链

```text
Current Scene Camera
→ authoritative gsplat Anchor RGB
→ InstancePromptState
    ├── Positive Point
    ├── Negative Point
    └── optional Positive Instance Box
→ SAM 3 Image instance prediction
    ├── one Positive Point only: up to 3 candidates
    └── Box / multiple Points / refinement: one candidate
→ user candidate choice where needed
→ optional Point refinement before Accept
→ basic Prompt/Mask validity and Review
→ Accept
→ Editing Mask
→ Confirm
→ Anchor Stable Mask
→ TargetGeometryHintArtifact
→ bounded local Key-View plan
→ authoritative per-View RGB
→ projected Positive Instance Box + Points
→ SAM 3 Image instance prediction, single-mask mode
→ per-View Mask Review
→ Stable Mask publication / manual correction
→ Included Stable View Annotations
→ P/N/V Gaussian Evidence
→ Gaussian Candidate + Uncertain
→ Native Set / Add / Remove / Intersect
```

核心状态不得折叠：

```text
RGB Ready
≠ Mask Inference Ready
≠ Stable Mask Ready
≠ Evidence Ready
≠ Candidate Ready
```

---

# 3. Runtime ownership

## 3.1 Browser Editor owns

- CurrentTargetContext、CameraBinding 和 stale-result rejection；
- PromptState、Prompt history 和 Mask editing history；
- candidate choice、Accept、Paint、Erase、Confirm；
- opaque previous-logits reference metadata；
- Stable Mask registry 和 Participation；
- Gallery、Frustum、Camera Inspection；
- explicit Retry、Refresh、Re-Lift 和 Restart；
- Native Selection operations。

## 3.2 Selection Service Companion owns

- authoritative gsplat RGB rendering；
- SAM 3 Image model loading and instance prediction；
- authoritative RGB artifact/reference resolution；
- actual previous-prediction logits tensors and their disposable cache；
- TargetGeometryHint extraction；
- bounded local Key-View generation；
- 3D-guided per-View Prompt synthesis；
- Mask validity diagnostics and Review policy；
- P/N/V Evidence、aggregation and Lift；
- bounded scheduling、replay、cleanup and versioned readiness。

Companion cache is disposable runtime state, not user-visible product authority。

---

# 4. Identity and fail-closed invariants

Every asynchronous artifact binds exact current identities where applicable：

```text
targetContextId + contextRevision
scene / splat dependency identity
CameraBinding digest
RGB digest + dimensions
PromptState digest
SAM image adapter / checkpoint / runtime digest
Companion Instance ID
inferenceAttemptId
previous-logits state ID / source attempt / source candidate
Stable Mask digest
TargetGeometryHintArtifact digest
LocalKeyViewPlan digest
per-View Prompt artifact digest
Mask review policy digest
Evidence / Lift policy digest
```

Rules：

- explicit Retry creates a new attempt；
- same-attempt replay may be idempotent；
- stale or incompatible artifacts fail closed；
- no partial Mask、refinement state、Evidence or Candidate becomes current；
- cancellation is a resource optimization, not a correctness mechanism；
- User Confirmed Stable Mask cannot be silently replaced；
- Companion Instance replacement invalidates every Companion-local RGB/logits reference from the prior Instance；
- independently persisted Stable Masks remain governed by their own exact RGB/Mask identity。

---

# 5. Authoritative RGB

Anchor、Generated Key View 和 User-added View 的 AI observation RGB MUST come from the locked gsplat renderer and exact CameraBinding。

RGB Ready never waits for Mask inference、2.5D geometry、Evidence or Candidate。

Every SAM inference request MUST contain either：

- the exact authoritative RGB artifact bytes；or
- an immutable Companion-resolvable RGB reference tied to the current Companion Instance。

The resolved bytes MUST match the declared RGB digest、width and height。A digest without resolvable image data is not a valid inference input。

---

# 6. SAM model and instance Prompt contract

## 6.1 Current production model

Static Anchor and per-Key-View instance segmentation MUST use the official SAM 3 Image path：

```text
build_sam3_image_model(enable_inst_interactivity=True)
→ Sam3Processor.set_image(authoritativeRgb)
→ model.predict_inst(inferenceState, ...)
```

SAM 3.1 Multiplex video predictor is not a current static-image production dependency。It may remain only as historical benchmark or future video-tracking experiment behind a later ADR。

Production code MUST NOT depend on Multiplex tracker private heads、private feature extraction or fabricated multiplex state for ordinary static segmentation。

## 6.2 Supported v1 Prompt families

The v1 instance Prompt surface contains only：

- Positive Point；
- Negative Point；
- at most one Positive Instance Box in authoritative-image pixel XYXY coordinates。

The following are removed from PromptState、toolbar、capability contract and Prompt artifacts：

- Negative Box；
- Positive Mask Constraint；
- Negative Mask Constraint；
- Prompt Brush；
- Text Prompt。

Paint and Erase remain Mask Editing operations and never enter SAM inference requests。

## 6.3 Previous prediction logits

The actual previous-prediction logits tensor is Companion-local, low-resolution, continuous model state。

The browser may receive only an opaque `PreviousPredictionLogitsRef` bound to：

```text
Companion Instance ID
stateId
targetContextId + viewId
RGB digest
source inference attempt
source candidate
adapter/runtime digest
shape + dtype + data digest
```

It is not：

- a user Prompt；
- a binary Brush bitmap；
- an Editing Mask；
- a Stable Mask；
- a cross-View artifact；
- browser-persisted tensor data。

A valid ref may refine the currently chosen candidate while still in Prompt mode。The refinement creates a new inference attempt with `multimask_output=false`。

After `Accept`, Paint/Erase operate on Editing Mask。Returning to Prompt mode is explicit and never converts Editing pixels into `mask_input`。

Companion restart/Instance replacement、state eviction、target disposal、RGB change or adapter/runtime change invalidates the ref。An expired ref falls back to fresh inference from current Points/Box without `mask_input`。

## 6.4 Multimask policy

```text
exactly one Positive Point
+ no Box
+ no previous logits
→ multimask_output=true
→ retain at most 3 candidates

Positive Instance Box
or multiple Points
or previous-logits refinement
→ multimask_output=false
→ retain at most 1 candidate
```

Raw model score may choose default preview ordering。It is not a correctness probability and never auto-confirms a Stable Mask。

---

# 7. Anchor acquisition

Anchor acquisition is intentionally 2D-first：

```text
Prompt
→ SAM 3 Image prediction
→ candidate choice when single-click ambiguity exists
→ optional Point refinement before Accept
→ basic validity / Review
→ Accept
→ Editing Mask
→ Confirm
```

Required validity checks：

- resolvable authoritative RGB and exact dimensions/digest；
- non-empty and not full-frame；
- all Positive Points inside；
- all Negative Points outside；
- when Box exists, meaningful overlap and no gross spill；
- severe fragmentation or material boundary clipping enters Review；
- no result becomes Stable before Confirm。

Generic near-duplicate clustering、material-distinct clustering、automatic Top-1 calibration、Gaussian-support-based Anchor selection and repeated-run stability ranking are not v1 requirements。

For a one-point multimask result, exact duplicate removal is allowed and the user resolves material ambiguity directly。

---

# 8. Prompt/Edit palette

The v1 palette exposes：

```text
Positive Point
Negative Point
Positive Instance Box
Paint
Erase
```

Negative Box and Prompt Brush are absent, not disabled placeholders。

Prompt tools modify PromptState。Paint/Erase modify Editing Mask only。Palette layout state never enters model requests or formal artifacts。

---

# 9. TargetGeometryHintArtifact

After Anchor confirmation, Ticket 08 publishes one compact non-ownership artifact：

```ts
interface TargetGeometryHintArtifact {
    schemaVersion: 2;
    targetContextId: string;
    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;
    geometryPolicyDigest: string;
    centerWorld: [number, number, number];
    extentWorld: [number, number, number];
    visiblePoints: readonly [number, number, number][];
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    promptSupport: 'usable' | 'limited';
    artifactDigest: string;
}
```

Requirements：

- visible Points derive from exact Anchor Mask plus depth、first hit or equivalent visible-surface seam；
- per set Mask pixel only the nearest valid Gaussian mean contributes; equal
  world means are deduplicated before deterministic bounding；
- formal `visiblePoints` contains only retained support after separated-support
  filtering, never the pre-filter raw samples；
- Points are bounded、finite、deterministically ordered and filtered for invalid/background-separated support；
- center and extent use robust statistics；
- `quality` is `limited` when evidence-backed reasons are present, otherwise
  `usable`; if robust filtering rejects every distinct sample, the route fails
  closed as `geometryUnavailable`；
- `promptSupport` is an independent eligibility state. It is `usable` only
  with at least four distinct retained first-hit samples and no disqualifying
  reason; when `quality` is `limited`, the only promotable reason is
  `separatedSupportFiltered`；
- no Stable Gaussian IDs、weights or ownership labels are required；
- geometry is localization and Prompt context only；
- Anchor absence cannot classify a Gaussian as Rejected or Out of Scope。

---

# 10. Bounded local Key Views

v1 generates a small fixed-policy set of local Views, normally 2–4：

- left/right local azimuth offsets around the target；
- optional modest elevation offset；
- framing around `centerWorld` and `extentWorld`；
- bounded local movement rather than room-scale orbit planning。

Each candidate performs minimal validity checks：

- finite CameraBinding；
- target projection intersects image with sufficient size；
- clipping is valid；
- authoritative RGB is nonblank；
- gross occlusion or invalid depth may mark the View Limited or trigger bounded replacement。

Adaptive marginal-gain optimization、general free-space reconstruction、room/outside-room inference、Bridge Views、dense trajectories and append-only multi-segment planner frameworks are deferred。

`Generate More` may append another bounded local batch without invalidating completed Views。

---

# 11. Image instance Mask contracts

Ticket 08A defines a small versioned seam, not a generic backend ecosystem。

## 11.1 Prompt artifact

```ts
interface ImageInstancePromptArtifact {
    schemaVersion: number;
    targetContextId: string;
    contextRevision: number;
    viewId: string;
    rgbDigest: string;
    cameraBindingDigest: string;
    positivePoints: readonly PixelPoint[];
    negativePoints: readonly PixelPoint[];
    positiveBox?: PixelBoxXYXY;
    previousLogitsRefDigest?: string;
    multimaskOutput: boolean;
    artifactDigest: string;
}
```

## 11.2 Provider request

```ts
interface ImageInstanceMaskRequest {
    schemaVersion: number;
    identity: ImageInstanceMaskRequestIdentity;
    rgb: ImageInstanceRgbInput;
    prompt: ImageInstancePromptArtifact;
}
```

`ImageInstanceRgbInput` contains exactly one of：authoritative RGB artifact bytes or current Companion RGB reference。The provider resolves and verifies bytes before inference。

## 11.3 Result

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

Invariants：

- result echoes exact request identity；
- resolved RGB matches digest/dimensions；
- Mask/score/ref cardinality matches；
- single-mask mode returns at most one usable Mask；
- multimask mode returns at most three；
- raw logits tensors remain Companion-local；
- technical failure returns no partial result；
- provider does not publish Stable Mask、Participation、Evidence or Candidate；
- no current backend registry、Route B/C/D bundle、sequence extension or automatic Route-A fallback exists。

Future tracker work requires a new experiment-backed ADR and separate `SequenceInstanceTracker` contract。

---

# 12. 3D-guided per-View Prompt synthesis

For each Generated Key View, Prompt synthesis projects `TargetGeometryHintArtifact` through the exact CameraBinding and produces：

- one Positive Instance Box；
- 1–3 visible Positive Points inside projected support；
- optionally 0–2 Negative Points in clearly local background or neighbour regions。

Generated per-View inference uses `multimask_output=false`。

Prompt synthesis MUST NOT create：

- Negative Box；
- Mask Constraint / Prompt Brush；
- Text Prompt；
- concept-level normalized CXCYWH Box；
- guessed oversized target regions when support is insufficient。

Prompt regeneration and Mask Retry are distinct operations。

Prompt Support is also a per-View gate: at least two distinct retained points
must project inside the authoritative View image. A failed global or per-View
gate returns structured `status: "limited"` and issues no Mask inference.
When global and per-View Prompt Support are usable, synthesis may return
`status: "ready"` even when Geometry Quality is `limited` for the sole
recoverable `separatedSupportFiltered` reason. Geometry diagnostics remain
visible and do not automatically change Mask Review Participation。

---

# 13. Per-View Mask acquisition

Each Key View is inferred independently through the same SAM 3 Image adapter used by Anchor acquisition。

Required behavior：

- no adjacent-frame or tracker-memory dependency；
- no Multiplex session；
- exact RGB/Prompt/Companion/attempt identity；
- one output Mask in normal 3D-guided mode；
- Prompt consistency and basic geometry validation；
- technical failure preserves RGB and prior Stable Mask；
- no automatic fallback to legacy projected-support/Multiplex route。

A valid empty result is semantic `unavailable`, distinct from transport/runtime/OOM failure。

---

# 14. Mask Review, Participation and optional cross-view diagnostics

## 14.1 Per-View Mask Review

Per-View Mask Review may use：

- Prompt consistency；
- empty/full-frame detection；
- meaningful boundary clipping ratio；
- severe fragmentation；
- Box spill or obvious neighbour contamination；
- exact identity and dimensions。

It produces Good / Review / Failed。

`propagation-uncertain` is removed because no tracker propagation exists。

`weak-gaussian-support` and `low-visible-support` are not Mask-quality reasons。They belong to Ticket 13 Lift Readiness。

## 14.2 Participation defaults

```text
Good automatic Stable Mask → Included
Review automatic Stable Mask → Excluded
Failed / unavailable / no Stable Mask → Excluded
User Confirmed Stable Mask → Included unless explicitly excluded
```

Participation remains independent from View role and source。

## 14.3 Ticket 10 optional diagnostics

Ticket 10 may add cross-view Evidence-conflict diagnostics after per-View P/N/V exists。It does not own Mask Review、visibility readiness or ownership classification。Its absence does not block base Lift Readiness or core release closure。

---

# 15. Stable Mask publication

Only the Stable Mask publication layer may replace an automatic Stable Mask revision。

It validates exact RGB、Prompt/result、review policy and current Stable authority。It never silently replaces User Confirmed Stable state and never creates P/N/V or Candidate。

---

# 16. Orchestration and migration

The controller coordinates：

```text
plan local Views
→ render RGB immediately
→ synthesize per-View instance Prompt
→ run SAM 3 Image inference
→ review Mask
→ publish automatic Stable Mask or retain Review/Unavailable
```

It does not implement model internals or geometry algorithms。

Migration MUST retire or isolate：

- SAM 3.1 Multiplex static-image shim；
- private tracker-head static prediction；
- `maskSource: 'propagated'` as generic provenance；
- `GeneratedViewMaskResponse.assessment` provider coupling；
- Negative Box and Mask Constraint Prompt artifacts；
- binary Brush-to-`mask_input` mapping；
- raw logits tensor in browser Prompt/request state；
- generic backend registry and automatic route fallback contracts；
- former Ticket 06 production-fallback claims；
- legacy `generated-view-mask/v1` cache rebinding。

Old artifacts fail version validation。User Confirmed Stable Masks remain authoritative。

---

# 17. Gallery and inspection

Cards present separate：

```text
Render
Prompt synthesis
Mask inference
Mask Review / Stable Mask
Participation
Evidence
Candidate stale/current
```

The Gallery does not expose backend-route matrices、fallback provenance、sequence state or generic ProposalDecision for ordinary Generated Views。

Anchor candidate choice remains in the Anchor editing surface。

---

# 18. User-added Views

User-added Views reuse the same RGB、instance Prompt、SAM 3 Image inference、Mask Review、Stable publication and Participation contracts。

They may also use Manual Draw and are never trusted solely because they are user-created。

---

# 19. Dirty and refresh lifecycle

Formal dirty states include：

- TargetGeometryHint dirty；
- local Key-View plan dirty；
- per-View Prompt dirty；
- per-View Mask inference dirty；
- per-View Evidence dirty；
- Lift dirty；
- Candidate stale。

Rules：

- unconfirmed Editing changes do not dirty Evidence；
- Anchor Stable change invalidates geometry、plan and dependent per-View Prompts/Masks；
- Camera/RGB change dirties that View Prompt、Mask and Evidence；
- Point refinement may reuse exact previous-logits ref only on the same RGB/Companion/candidate lineage；
- Companion Instance change invalidates all previous-logits and Companion RGB refs；
- missing refinement state causes fresh no-logits inference；
- Refresh creates a new inference attempt；
- no Mask refresh automatically Re-Lifts；
- manual correction affects only that View by default。

---

# 20. Formal P/N/V Evidence

Only current Views with：

```text
Render Ready
+ Stable Mask
+ Participation Included
+ exact current identities
```

contribute to P/N/V。

Target geometry、Prompt、SAM score、previous logits、Mask Review、cross-view diagnostic and View role are not ownership Evidence。

---

# 21. Working Sets and Lift Readiness

Render Working Set preserves correct compositing and occlusion。Evidence Working Set controls Stable Gaussian IDs receiving P/N/V writes。

`TargetGeometryHintArtifact` may seed but never hard-bound Evidence Working Set。Later Included Views may expand it。

Ticket 13 is the sole current authority for：

- visibility/support sufficiency；
- Observation Coverage；
- useful View Diversity；
- Not Ready / Limited / Ready。

Ticket 10 optional conflict diagnostics may enrich inspection but cannot emit weak/low-support readiness claims and do not block release。

---

# 22. Candidate and native operations

Aggregation preserves per-View Evidence and produces Selected、Rejected、Uncertain、Out of Scope classes。Candidate contains Selected only。

Native Set/Add/Remove/Intersect remains explicit and undoable。No AI artifact mutates Native Selection before user application。

---

# 23. Future video tracking

SAM 3.1 Multiplex may be reconsidered only for a real ordered video/dense multi-object tracking workload。

Adoption requires a new ADR with measured benefit、sequence semantics、reference updates、drift handling、resource envelope、failure isolation and migration。No current Ticket implements speculative sequence interfaces。

---

# 24. Failure and recovery

Minimum rules：

- Companion unavailable leaves Native SuperSplat usable；
- RGB failure preserves inspectable prior state；
- unresolved/digest-only RGB request fails before inference；
- SAM technical failure preserves RGB、prior Stable Mask and manual editing；
- one-point candidate ambiguity asks the user to choose/refine；
- expired previous-logits ref reruns current Points/Box without `mask_input`；
- no usable Mask offers Point/Box adjustment、Retry、Manual Draw or Exclude；
- geometry failure preserves Anchor and allows local/user-added alternatives；
- stale or old-schema artifacts are rejected, never rebound；
- OOM/cancellation publishes no partial artifact；
- Evidence/Lift failure preserves Views and Stable Masks；
- optional Ticket 10 failure leaves core release, readiness, Participation and Candidate unchanged。

---

# 25. Validation gates

Required validation：

- repository tests、lint、locales and build；
- official SAM 3 Image adapter GPU fixture；
- no static path imports or invokes Multiplex predictor/private tracker heads；
- authoritative RGB artifact/reference resolution and mismatch fixtures；
- Point、Negative Point、Positive Box and opaque previous-logits-ref refinement fixtures；
- Companion restart/state eviction invalidation；
- single-point multimask and Box/multi-point single-mask fixtures；
- PromptState migration rejecting Negative Box/Mask Constraint artifacts；
- Paint/Erase never entering model request；
- TargetGeometryHint deterministic projection fixtures；
- bounded local View framing and nonblank render fixtures；
- 3D-guided Box/Point per-View quality fixtures；
- Mask Review versus Lift Readiness reason separation；
- core release without Ticket 10 output；
- stale identity、Retry、OOM and User Confirmed preservation tests。

---

# 26. Ticket ownership and current frontier

```text
04C  SAM 3 Image adapter + Prompt/RGB/refinement contract migration        implemented
07   MaskReviewPolicy correction                                           implemented
02C  automatic readiness for the new Active Model Manifest                 implemented
07A  simplified Anchor candidate choice and confirmation                   implemented
07B  Point/Box + Paint/Erase palette hardening                             implemented
08   TargetGeometryHint + bounded local Key Views                           implemented
08A  compact Image Instance Mask contracts                                 implemented
08B  3D-guided per-View SAM 3 Image acquisition                            implemented
08C  reliable retained TargetGeometryHint support and Route B Prompt eligibility implemented
09   simplified Gallery states                                              ready / current frontier
12   simplified dirty/refresh lifecycle                                     after 09
13   sole Lift Readiness / visibility authority                             after 14 + 11 + 12
10   optional cross-view Evidence-conflict diagnostics                      nonblocking
```

Current ready frontier：

```text
09  Scalable Gallery + Frustum Sync + Mask Inspection
```

After 09：

- 11 and 12 proceed in parallel；
- 14 proceeds after both 11 and 12；
- Ticket 10 remains optional and off the core release path。

Locked-GPU browser E2E for Tickets 08B and 08C completed on 2026-08-07 with no blocking issue reported。