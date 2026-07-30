# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.3

**文档状态：** Current Final Spec / Normative  
**规划版本：** Ticket Graph v2.11  
**日期：** 2026-07-30  
**适用分支：** `ai-select-v1`  
**决策依据：** ADR 0013、ADR 0015、ADR 0016

---

# 0. 规范地位

本文件是 AI Select 当前唯一权威产品与工程规格。

它取代 Final Spec v1.2 的当前规范效力。Final Spec v1.1、Amendment 001–005、Final Spec v1.2、ADR 0014 及 DG-20～DG-26 继续作为历史设计依据，但不得覆盖本文件。

当前 Ticket 映射由 `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md` 维护。发生冲突时，权威顺序为：

1. Final Spec v1.3；
2. 当前 Ticket mapping；
3. ADR 0016；
4. ADR 0013、ADR 0015；
5. 未冲突的 Ticket acceptance criteria；
6. 当前实现和测试。

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
- 不把模型分数、2.5D geometry 或 Prompt 当成 Gaussian ownership。

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
    ├── one positive point only: up to 3 candidates
    └── Box / multiple points / refinement: one candidate
→ user candidate choice where needed
→ basic Prompt/Mask validity and Review
→ Accept
→ Editing Mask
→ Confirm
→ Anchor Stable Mask
→ TargetGeometryHintArtifact
→ bounded local Key-View plan
→ authoritative per-View RGB
→ projected Instance Box + positive/negative Points
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
- Stable Mask registry 和 Participation；
- Gallery、Frustum、Camera Inspection；
- explicit Retry、Refresh、Re-Lift 和 Restart；
- Native Selection operations。

## 3.2 Selection Service Companion owns

- authoritative gsplat RGB rendering；
- SAM 3 Image model loading and instance prediction；
- Prompt compilation and internal previous-logits refinement state；
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
RGB digest
PromptState digest
SAM image adapter / checkpoint / runtime digest
inferenceAttemptId
previousLogits source-attempt and candidate identity
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
- no partial Mask、Evidence or Candidate becomes current；
- cancellation is a resource optimization, not a correctness mechanism；
- User Confirmed Stable Mask cannot be silently replaced。

---

# 5. Authoritative RGB

Anchor、Generated Key View 和 User-added View 的 AI observation RGB MUST come from the locked gsplat renderer and exact CameraBinding。

RGB Ready never waits for Mask inference、2.5D geometry、Evidence or Candidate。

---

# 6. SAM model and instance Prompt contract

## 6.1 Current production model

Static Anchor and per-Key-View instance segmentation MUST use the official SAM 3 Image path：

```text
build_sam3_image_model(enable_inst_interactivity=True)
→ Sam3Processor.set_image(...)
→ model.predict_inst(...)
```

The SAM 3.1 Multiplex video predictor is not a current static-image production dependency. It may be retained only as a historical benchmark or future video-tracking experiment behind a later ADR。

Production code MUST NOT depend on Multiplex tracker private heads、private feature extraction or fabricated multiplex state for ordinary static segmentation。

## 6.2 Supported v1 Prompt families

The v1 instance Prompt surface contains only：

- Positive Point；
- Negative Point；
- at most one Positive Instance Box in authoritative-image pixel XYXY coordinates。

The following are removed from v1 PromptState、toolbar、capability contract and Prompt artifacts：

- Negative Box；
- Positive Mask Constraint；
- Negative Mask Constraint；
- Prompt Brush；
- Text Prompt。

Paint and Erase remain Mask Editing operations and never enter SAM inference requests。

## 6.3 Previous prediction logits

`previousPredictionLogits` is an internal, low-resolution continuous model artifact returned by a prior prediction and bound to the same RGB、adapter、attempt lineage and selected candidate。

It is not：

- a user-authored Prompt；
- a binary Brush bitmap；
- a Stable Mask；
- an Editing Mask；
- a cross-View artifact。

Adding Points to refine an accepted candidate may reuse the exact prior logits with `multimask_output=false`。

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
→ one candidate
```

Raw model score may choose the default preview among same-request candidates. It is not a correctness probability and never auto-confirms a Stable Mask。

---

# 7. Anchor acquisition

Anchor acquisition is intentionally 2D-first：

```text
Prompt
→ SAM 3 Image prediction
→ candidate choice when single-click ambiguity exists
→ basic validity / Review
→ Accept
→ Editing Mask
→ Confirm
```

Required validity checks：

- non-empty and not full-frame；
- exact RGB dimensions and digest；
- all Positive Points inside；
- all Negative Points outside；
- when Box exists, meaningful overlap and no gross spill；
- severe fragmentation or material boundary clipping enters Review；
- no result becomes Stable before Confirm。

Generic near-duplicate clustering、material-distinct clustering、automatic Top-1 calibration、Gaussian-support-based Anchor selection and repeated-run stability ranking are not v1 requirements。

For a one-point multimask result, exact duplicate removal is allowed, candidates remain bounded, and the user resolves material ambiguity directly。

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

Negative Box and Prompt Brush are absent, not merely disabled placeholders。

Prompt tools modify PromptState. Paint/Erase modify Editing Mask only. Palette layout state never enters model requests or formal artifacts。

---

# 9. TargetGeometryHintArtifact

After Anchor confirmation, Ticket 08 publishes one compact non-ownership artifact：

```ts
interface TargetGeometryHintArtifact {
    schemaVersion: number;
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
    artifactDigest: string;
}
```

Requirements：

- visible points derive from exact Anchor Mask plus depth、first hit or equivalent visible-surface seam；
- points are bounded、finite、deterministically ordered and filtered for invalid/background-separated support；
- center and extent use robust statistics；
- no Stable Gaussian IDs、weights or ownership labels are required；
- geometry is localization and Prompt context only；
- Anchor absence cannot classify a Gaussian as Rejected or Out of Scope。

---

# 10. Bounded local Key Views

v1 generates a small fixed-policy set of local views, normally 2–4：

- left/right local azimuth offsets around the target；
- optional modest elevation offset；
- look-at or equivalent framing around `centerWorld` and `extentWorld`；
- bounded local movement rather than room-scale orbit planning。

Each candidate performs minimal validity checks：

- finite CameraBinding；
- target projection intersects the image with sufficient size；
- clipping is valid；
- rendered RGB is nonblank；
- gross occlusion or invalid depth may mark the View Limited/Review。

Adaptive marginal-gain optimization、general free-space reconstruction、room/outside-room inference、Bridge Views、dense trajectory planning and append-only multi-segment planner frameworks are deferred。

`Generate More` may append another bounded local batch without invalidating completed Views。

---

# 11. Image instance Mask contracts

Ticket 08A defines a small model-specific-but-versioned seam, not a generic backend ecosystem：

```ts
interface ImageInstancePromptArtifact {
    schemaVersion: number;
    targetContextId: string;
    viewId: string;
    rgbDigest: string;
    adapterCapabilityDigest: string;
    positivePoints: readonly PixelPoint[];
    negativePoints: readonly PixelPoint[];
    positiveBox?: PixelBoxXYXY;
    previousLogitsArtifactDigest?: string;
    multimaskOutput: boolean;
    artifactDigest: string;
}

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

Invariants：

- result echoes exact request identity；
- Mask/score/logits cardinality matches；
- single-mask mode returns at most one usable Mask；
- multimask mode returns at most three；
- technical failure returns no partial result；
- provider does not publish Stable Mask、Participation、Evidence or Candidate；
- there is no current backend registry、Route B/C/D bundle、sequence extension or automatic Route-A fallback contract。

Future tracker work requires a new experiment-backed ADR and a separate `SequenceInstanceTracker` contract。

---

# 12. 3D-guided per-View Prompt synthesis

For each Generated Key View, Prompt synthesis projects `TargetGeometryHintArtifact` through the exact Key-View CameraBinding and produces：

- one Positive Instance Box；
- 1–3 visible Positive Points inside projected target support；
- optionally 0–2 Negative Points in clearly local background or neighbour regions。

Generated per-View inference uses `multimask_output=false`。

Prompt synthesis MUST NOT create：

- Negative Box；
- Mask Constraint / Prompt Brush；
- Text Prompt；
- concept-level normalized CXCYWH Box；
- guessed oversized target regions when support is insufficient。

Prompt regeneration and Mask Retry are distinct operations。

---

# 13. Per-View Mask acquisition

Each Key View is inferred independently through the same SAM 3 Image adapter used by Anchor acquisition。

Required behavior：

- no adjacent-frame or tracker-memory dependency；
- no Multiplex session；
- exact RGB/Prompt/attempt identity；
- one output Mask in normal 3D-guided mode；
- Prompt consistency and basic geometry validation；
- technical failure preserves RGB and prior Stable Mask；
- no automatic fallback to the legacy projected-support/Multiplex route。

A missing or invalid Mask becomes `unavailable` or Review according to structured cause. It is distinct from transport/runtime/OOM failure。

---

# 14. Mask Review, Participation and Lift Readiness

## 14.1 Mask validity / Review

Per-View Mask Review may use：

- Prompt consistency；
- empty/full-frame detection；
- meaningful boundary clipping ratio；
- severe fragmentation；
- Box spill or obvious neighbour contamination；
- exact identity and dimensions。

It produces Good / Review / Failed。

## 14.2 Removed reasons

`propagation-uncertain` is removed from the ordinary v1 path because no tracker propagation exists。

`weak-gaussian-support` is not a Mask-quality reason. It belongs to Lift Readiness in Ticket 13。

## 14.3 Defaults

```text
Good automatic Stable Mask → Included
Review automatic Stable Mask → Excluded
Failed / unavailable / no Stable Mask → Excluded
User Confirmed Stable Mask → Included unless the user explicitly excludes it
```

Participation remains independent from View role and source。

---

# 15. Stable Mask publication

Only the Stable Mask publication layer may replace an automatic Stable Mask revision。

It validates exact RGB、Prompt/result、review policy and current Stable authority. It never silently replaces User Confirmed Stable state and never creates P/N/V or Candidate。

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
- generic backend registry and automatic route fallback contracts；
- legacy `generated-view-mask/v1` cache rebinding。

Old artifacts fail version validation. User Confirmed Stable Masks remain authoritative。

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

Anchor candidate choice remains in the Anchor editing surface, not in every Gallery card。

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
- Point refinement may reuse exact prior logits only on the same RGB and lineage；
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

Target geometry、Prompt、SAM score、previous logits、Mask Review and View role are not ownership Evidence。

---

# 21. Working Sets and Lift

Render Working Set preserves correct compositing and occlusion. Evidence Working Set controls Stable Gaussian IDs receiving P/N/V writes。

`TargetGeometryHintArtifact` may seed but never hard-bound Evidence Working Set。Later Included Views may expand it。

Ticket 13 owns Lift Readiness：coverage、view diversity、visibility/support sufficiency and Not Ready / Limited / Ready classification。

---

# 22. Candidate and native operations

Aggregation preserves per-View Evidence and produces Selected、Rejected、Uncertain、Out of Scope classes. Candidate contains Selected only。

Native Set/Add/Remove/Intersect remains explicit and undoable. No AI artifact mutates Native Selection before the user applies an operation。

---

# 23. Future video tracking

SAM 3.1 Multiplex may be reconsidered only for a real ordered video/dense multi-object tracking workload。

Adoption requires a new ADR with measured benefit、sequence semantics、reference updates、drift handling、resource envelope、failure isolation and migration。No current Ticket must implement speculative sequence interfaces。

---

# 24. Failure and recovery

Minimum rules：

- Companion unavailable leaves Native SuperSplat usable；
- RGB failure preserves inspectable prior state；
- SAM technical failure preserves RGB、prior Stable Mask and manual editing；
- one-point candidate ambiguity asks the user to choose/refine；
- no usable Mask offers Point/Box adjustment、Retry、Manual Draw or Exclude；
- geometry failure preserves Anchor and allows local/user-added alternatives；
- stale or old-schema artifacts are rejected, never rebound；
- OOM/cancellation publishes no partial artifact；
- Evidence/Lift failure preserves Views and Stable Masks。

---

# 25. Validation gates

Required validation：

- repository tests、lint、locales and build；
- official SAM 3 Image adapter GPU fixture；
- no static path imports or invokes Multiplex predictor/private tracker heads；
- Point、Negative Point、Positive Box and previous-logits refinement fixtures；
- single-point multimask and Box/multi-point single-mask fixtures；
- PromptState migration rejecting Negative Box/Mask Constraint artifacts；
- Paint/Erase never entering model request；
- TargetGeometryHint deterministic projection fixtures；
- bounded local View framing and nonblank render fixtures；
- 3D-guided Box/Point per-View quality fixtures；
- Mask Review versus Lift Readiness reason separation；
- stale identity、Retry、OOM and User Confirmed preservation tests。

---

# 26. Ticket ownership summary

```text
04C  SAM 3 Image adapter + Prompt contract migration
02C  automatic readiness for the new Active Model Manifest
07   Mask Review / Participation correction
07A  simplified Anchor candidate choice and confirmation
07B  Point/Box + Paint/Erase palette hardening
08   TargetGeometryHint + bounded local Key Views
08A  compact Image Instance Mask contracts
08B  3D-guided per-View SAM 3 Image acquisition
09   simplified Gallery states
12   simplified dirty/refresh lifecycle
13   Lift Readiness including weak Gaussian support
```

Current implementation begins at Ticket 04C。
