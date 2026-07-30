# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.2

**文档状态：** Current Final Spec / Normative  
**版本：** v1.2  
**日期：** 2026-07-30  
**适用分支：** `ai-select-v1`  
**适用对象：** Product / UX / Frontend / Companion / Algorithm / QA  
**决策依据：** ADR 0013、DG-20～DG-26  

---

# 0. 规范地位

本文件是 AI Select 当前唯一权威产品与工程规格。

它合并并取代以下文件的当前规范效力：

- Final Spec v1.1；
- Amendment 001–005。

这些旧文件继续保留为历史记录，但实现 agent、验收、traceability 和新 Ticket 不得要求读者自行合并其 supersession 链。

发生冲突时，权威顺序为：

1. 本文件；
2. ADR 0013；
3. 未被本文件覆盖的非 superseded ADR；
4. `CONTEXT.md`；
5. implementation tickets；
6. 实现与测试。

本文件中的 MUST / SHALL / 必须 / 不得均为强制要求。

---

# 1. 产品定义与范围

AI Select 是 SuperSplat 的原生 3D Gaussian Selection Tool。

用户以当前场景视角建立一个对象级 Anchor，获得并修正 2D Stable Mask；系统生成少量高价值 Key Views，为每个 View 独立获得对象 Mask；最终只从 Included Stable View Annotations 计算 per-Gaussian P/N/V Evidence，并将其 Lift 为 Gaussian Candidate。

v1 范围：

- 一次选择一个对象实例；
- 对象级 Mask 足够；
- 不要求任意部件选择；
- 不要求完整恢复不可见底面、背面或内部；
- 不要求全图对象 inventory；
- 不重新训练输入 3DGS；
- 不建立长期语义对象数据库；
- 不创建第二套 3D 编辑系统。

---

# 2. 当前产品链

```text
Current Scene Camera
→ authoritative gsplat Anchor RGB
→ PromptState
→ AutoMaskProposalSet
→ conservative ProposalDecision
    ├── selected
    ├── ambiguous
    └── unavailable
→ Editing Mask
→ Confirm Mask
→ object-level Anchor Stable Mask
→ VisibleTargetSupportArtifact
→ TargetBootstrapArtifact
→ adaptive sparse Key Views
→ authoritative per-View RGB
→ KeyViewPromptSynthesizer
→ KeyViewPromptArtifact
→ MaskAcquisitionBackend.perView.acquireView
→ KeyViewMaskProposalSet
→ KeyViewMaskDecisionPolicy
    ├── selected
    ├── ambiguous
    └── unavailable
→ ViewAssessmentPolicy
    ├── Good
    ├── Review
    └── Failed
→ MaskPublicationCoordinator
→ Included Stable View Annotations
→ Mask-conditioned Gaussian Evidence (P / N / V)
→ multi-view aggregation
→ Gaussian Candidate + Uncertain
→ Set / Add / Remove / Intersect
→ Native SuperSplat Selection
```

核心不变量：

```text
RGB Ready
≠ Mask Ready
≠ Evidence Ready
≠ Candidate Ready
```

任何上游诊断、模型分数、Visible Support 或 acquisition backend 身份都不能直接授权 Gaussian ownership。

---

# 3. Runtime ownership

## 3.1 Browser Editor owns

- scene / splat state；
- Stable Gaussian ID 与当前 index 映射；
- Current Editor Camera；
- CameraBinding 构造；
- CurrentTargetContext；
- AIView registry；
- 3D Frustum 展示、选择与 Camera Inspection；
- PromptState 与 Prompt/Edit 工具状态；
- Prompt history 与 Mask pixel history；
- Stable Mask registry；
- View Participation；
- Candidate / Uncertain presentation；
- Native Set/Add/Remove/Intersect 与 EditHistory；
- backend readiness presentation；
- explicit Retry / Refresh / Re-Lift / Restart actions。

## 3.2 Selection Service Companion owns

- locked authoritative gsplat RGB rendering；
- Anchor and Key-View model inference；
- Visible Target Support extraction；
- adaptive sparse Key-View planning；
- KeyViewPromptSynthesizer implementation；
- acquisition backend registry and execution；
- proposal diagnostics；
- KeyViewMaskDecisionPolicy；
- ViewAssessmentPolicy；
- Mask-conditioned per-view P/N/V Evidence；
- multi-view aggregation and Lift policy；
- bounded scheduling, replay, cancellation, cleanup；
- versioned model/runtime/policy readiness；
- disposable scene/model/runtime caches；
- reference/debug Contributor or autograd paths。

Companion caches are not user-visible product state.

---

# 4. Identity and fail-closed invariants

Every asynchronous artifact MUST bind enough immutable identity to reject stale results.

Common identity envelope includes, where applicable:

```text
targetContextId + contextRevision
sceneId + sceneVersion + splat dependency token
Stable Gaussian ID mapping identity
CameraBinding digest
RGB digest
Stable Mask digest
VisibleTargetSupportArtifact digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
KeyViewPromptArtifact digest
backend descriptor/capability digest
model / adapter / runtime build identity
policy digest
attempt / fallback / sequence-run identity
result artifact digest
```

Rules:

- explicit Retry creates a new attempt identity；
- same-attempt replay may be idempotent；
- cancellation is only a resource optimization；
- correctness relies on identity rejection, not timely cancellation；
- incompatible renderer/model/backend/runtime changes invalidate dependent artifacts；
- no partial result may become Ready or Stable；
- atomic publication replaces a whole bound artifact or publishes nothing。

---

# 5. Authoritative RGB and CameraBinding

All AI observation RGBs MUST come from the locked authoritative gsplat rendering path:

- Anchor Preview / Final；
- Generated Key View；
- User-added View。

RGB Ready means:

- exact CameraBinding render succeeded；
- RGB payload and digest validate；
- request/result identity is current；
- CameraBinding revision is current。

RGB Ready MUST NOT require:

- Stable Mask；
- Evidence；
- complete Contributor；
- Candidate。

Frustum, depth, support projection and RGB MUST use the same CameraBinding convention and image dimensions.

---

# 6. Anchor Prompt, proposal and confirmation

Anchor acquisition uses three stages:

```text
Prompt Authoring
→ model proposal generation
→ conservative ProposalDecision
→ candidate acceptance / Editing Mask
→ Confirm Mask
```

Prompt Authoring and direct Mask pixel editing are distinct modes and histories.

Prompt capabilities are versioned and truthful. Unsupported Point/Box/Mask/Text combinations fail before inference; they are never silently dropped or converted.

Anchor model output is a bounded proposal set. The decision layer MUST:

- deduplicate exact Masks；
- cluster near-duplicate Masks；
- reject hard Prompt contradictions；
- treat raw model score as diagnostic/tie-break only；
- preserve materially distinct plausible candidates as `ambiguous`；
- preserve `unavailable` when no eligible candidate exists。

Only Confirm publishes a new Anchor Stable Mask revision.

A confirmed Anchor Stable Mask is an identity seed for later geometry and views. It is not Gaussian Candidate or ownership Evidence.

---

# 7. Floating Prompt/Edit palette

The fitted authoritative image surface owns Prompt and Mask pointer mapping.

The palette MUST support:

- drag within the fitted image；
- deterministic clamp and optional edge snap；
- expanded/collapsed mode；
- Space temporary hide while image authoring focus is active；
- no stale or invisible hit region；
- focus-aware shortcuts and accessibility；
- reset on target/context disposal。

Palette state MUST NOT enter PromptState, Mask history, Evidence, Candidate or Companion requests.

Ticket 07B may execute in parallel with Ticket 08 after Ticket 07A, but it remains mandatory before complete Generated/User-added View correction UX and final release hardening.

---

# 8. Visible Target Support

Ticket 08 MUST publish a versioned `VisibleTargetSupportArtifact`.

Minimum contract:

```ts
interface VisibleTargetSupportArtifact {
    schemaVersion: number;
    targetContextId: string;

    anchorViewId: string;
    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;

    supportPolicyDigest: string;
    samples: readonly VisibleTargetSupportSample[];
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    artifactDigest: string;
}

interface VisibleTargetSupportSample {
    worldPosition: [number, number, number];
    sourcePixel?: [number, number];
    depth?: number;
    weight?: number;
    stableGaussianId?: number;
}
```

Requirements:

- samples are bounded and deterministically ordered/encoded；
- `stableGaussianId` is optional provenance only；
- support may originate from depth, first-hit support or equivalent visible-surface extraction；
- invalid/background-dominated/separated support lowers quality or fails closed；
- support can guide geometry and Prompt synthesis；
- support cannot publish P/N/V, Candidate or Native Selection；
- absence from support cannot classify a Gaussian as Rejected or Out of Scope。

---

# 9. Target Bootstrap

`TargetBootstrapArtifact` is a lightweight object summary referencing the visible-support artifact.

Minimum contract:

```ts
interface TargetBootstrapArtifact {
    schemaVersion: number;
    targetContextId: string;

    anchorCameraBindingDigest: string;
    anchorRgbDigest: string;
    anchorStableMaskDigest: string;
    visibleTargetSupportArtifactDigest: string;

    bootstrapPolicyDigest: string;
    centerWorld: [number, number, number];
    extentWorld: [number, number, number];
    visibleSupportCount: number;
    quality: 'usable' | 'limited' | 'unavailable';
    reasons: readonly string[];
    artifactDigest: string;
}
```

It may guide framing, camera generation, ROI construction, Prompt synthesis and an initial conservative Evidence Working Set seed.

It MUST NOT become a hard upper bound on later Working Set expansion.

---

# 10. Adaptive sparse Key-View planning

Ticket 08 MUST replace a fixed orbit with bounded adaptive sparse planning.

Planner evaluates independently:

```text
camera validity
target observation gain
directional diversity gain
expected render / scene-support quality
resource cost
```

Invalid camera geometry cannot win through theoretical information gain.

The default route does not require:

- Bridge Views；
- tracker transition envelopes；
- dense continuous trajectories；
- adjacent-frame ordering。

Output is an immutable `SparseKeyViewPlanSegment`:

```ts
interface SparseKeyViewPlanSegment {
    schemaVersion: number;
    segmentId: string;
    targetContextId: string;
    anchorStableMaskDigest: string;
    visibleTargetSupportArtifactDigest: string;
    targetBootstrapArtifactDigest: string;
    plannerPolicyDigest: string;
    orderedKeyViews: readonly PlannedKeyView[];
    attemptId: string;
    artifactDigest: string;
}
```

`Generate More` appends a new segment and preserves prior completed View/RGB/Mask artifacts.

`Regenerate Auto Views` is the explicit operation that may supersede planner-owned segments while preserving user-owned Views.

---

# 11. Acquisition contract foundation

Ticket 08A owns contracts and validators, not production model execution.

Required contracts include:

- `KeyViewPromptArtifact`；
- `KeyViewMaskProposalSet`；
- `KeyViewMaskDecision`；
- acquisition request/result identity；
- attempt/fallback identity；
- publication command/result；
- backend descriptor/bundle/registry；
- optional sequence extension schemas；
- structural validators, canonical digest rules and golden vectors。

## 11.1 Backend bundle

```ts
interface MaskAcquisitionBackend {
    readonly descriptor: MaskAcquisitionBackendDescriptor;
    readonly perView?: MultiViewMaskAcquisitionProvider;
    readonly sequence?: SequenceMaskAcquisitionExtension;
}

interface MaskAcquisitionBackendRegistry {
    resolveBackend(backendId: string): MaskAcquisitionBackend;
}
```

Capabilities are derived from the actual bundle and validated against `backendKind`.

```text
Route B = perView required, sequence absent
Route C = sequence required, perView optional
Route D = perView required, sequence required
```

A contradictory descriptor/bundle is Not Ready.

## 11.2 Per-view provider

```ts
interface MultiViewMaskAcquisitionProvider {
    acquireView(
        request: PerViewMaskAcquisitionRequest
    ): Promise<PerViewMaskAcquisitionResult>;
}
```

The provider returns a proposal set plus backend diagnostics. It MUST NOT return `ViewAssessmentResult`, choose a hidden final Mask, publish Stable state or set Participation.

## 11.3 Optional sequence extension

```ts
interface SequenceMaskAcquisitionExtension {
    openSequence(request: OpenMaskSequenceRequest): Promise<OpenMaskSequenceResult>;
    acquireSequenceRange(request: AcquireMaskSequenceRangeRequest): Promise<AcquireMaskSequenceRangeResult>;
    updateReferences(request: UpdateMaskSequenceReferencesRequest): Promise<UpdateMaskSequenceReferencesResult>;
    closeSequence(request: CloseMaskSequenceRequest): Promise<void>;
}
```

Route B has no sequence extension. Unsupported operations fail before inference or state mutation.

---

# 12. Key-View Prompt synthesis

Ticket 08B MUST implement `KeyViewPromptSynthesizer` independently from controller and provider.

```text
VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
+ SparseKeyViewPlanSegment / Key-View CameraBinding
+ adapter capabilities
+ Prompt synthesis policy
→ KeyViewPromptArtifact
```

A `KeyViewPromptArtifact` binds:

- target/scene/View identities；
- visible-support digest；
- bootstrap digest；
- plan-segment digest；
- Key-View CameraBinding and RGB digest；
- adapter capability digest；
- synthesis policy digest；
- ordered Prompt payload；
- clipping/support/contamination diagnostics；
- artifact digest。

Supported Prompt families may include:

- projected positive support points；
- projected target center；
- projected Box/ROI；
- local negative points/region；
- compatible projected Mask input；
- scale, clipping and boundary diagnostics。

Unsupported Prompt types fail closed and are not silently dropped.

Prompt regeneration and SAM Retry are distinct operations. A same-Prompt Retry may reuse the immutable Prompt artifact while creating a new inference attempt.

---

# 13. Route-B proposal generation

Route B performs independent prompt-conditioned SAM inference per authoritative Key View.

It does not require adjacent frames, tracker memory, Bridge Views or dense sequences.

The provider returns:

```ts
interface KeyViewMaskProposalSet {
    schemaVersion: number;
    targetContextId: string;
    viewId: string;
    promptArtifactDigest: string;
    backendId: string;
    modelId: string;
    runtimeBuildId: string;
    attemptId: string;
    proposals: readonly KeyViewMaskProposal[];
    artifactDigest: string;
}
```

Each proposal binds its Mask artifact and may include raw model score plus geometry/Prompt consistency diagnostics.

No provider-internal Top-1 decision is authoritative.

---

# 14. Key-View proposal decision

`KeyViewMaskDecisionPolicy` is separate from inference and assessment.

Output:

```ts
type KeyViewMaskDecision =
    | { status: 'selected'; selectedProposalId: string; reasons: readonly string[] }
    | { status: 'ambiguous'; candidateProposalIds: readonly string[]; reasons: readonly string[] }
    | { status: 'unavailable'; reasons: readonly string[] };
```

Decision rules:

- exact duplicate and near-duplicate clustering precedes selection；
- hard Prompt contradiction makes a proposal ineligible；
- raw model score is not sole selector；
- one credible cluster may become `selected`；
- multiple materially distinct plausible clusters become `ambiguous`；
- zero eligible proposals becomes `unavailable`；
- ambiguous decisions preserve proposal artifacts for Review and publish no arbitrary Stable Mask。

---

# 15. View Assessment and Participation

Only a `selected` proposal enters `ViewAssessmentPolicy`.

Assessment answers whether the selected Mask is good enough to use, not which proposal is the target.

Assessment may use:

- Mask geometry；
- projected support consistency；
- boundary clipping；
- fragmentation；
- neighbour contamination；
- declared versioned Gaussian support/visibility diagnostics；
- later formal P/N/V diagnostics where available。

Assessment produces Good / Review / Failed and structured reason codes.

Participation is independent from View role, planner role and acquisition backend.

Default transitions:

```text
selected + Good
→ Auto Good Stable Mask
→ Included

selected + Review
→ Auto Review Stable Mask
→ Excluded

ambiguous
→ Review ProposalSet
→ no new Stable Mask
→ Excluded

unavailable
→ Mask Failed
→ no new Stable Mask
→ Excluded
```

User Confirmed Stable authority cannot be silently replaced or revoked.

---

# 16. Mask publication

`MaskPublicationCoordinator` is the only route-B layer allowed to publish an automatic Stable Mask revision.

It validates:

- current request/result identity；
- selected proposal membership；
- exact RGB dimensions and digest；
- decision and assessment policy identity；
- current Stable authority；
- no partial/cancelled/stale state。

Automatic results MUST NOT silently replace a User Confirmed Stable Mask. They may be retained as Review proposals or require explicit Refresh/acceptance.

Mask failure preserves View/RGB/frustum and prior Stable Mask.

---

# 17. Route-A fallback

Route A remains the existing projected-support + independent single-frame SAM baseline.

Automatic fallback is permitted only after route-B technical/capability failure:

- backend unavailable；
- required route-B Prompt capability unavailable；
- explicit technical compatibility rejection；
- recoverable inference error；
- route-B OOM with declared lower-resource route-A availability。

Automatic fallback is prohibited for:

- ambiguous proposals；
- neighbour contamination；
- Prompt inconsistency；
- clipping/fragmentation quality risk；
- Assessment Review；
- an existing User Confirmed Stable Mask。

Fallback creates a new attempt with:

```text
fallbackOfAttemptId
fallbackReason
route-A backend/model/runtime/policy identity
```

Route A uses the same ProposalSet → Decision → Assessment → Publication pipeline.

It may produce Auto Good only under the same or stricter threshold and contamination policy. Fallback provenance remains inspectable and does not hide the route-B failure.

---

# 18. Orchestration and scheduling

The Generated View controller MUST separate:

```text
planning
RGB rendering
Prompt synthesis
per-view acquisition dispatch
proposal decision
assessment
publication
optional future sequence dispatch
```

The controller coordinates artifacts; it does not implement geometric Prompt synthesis, SAM inference, proposal decision or assessment algorithms.

Companion scheduling MUST support:

- bounded concurrency；
- explicit attempt identity；
- idempotent same-attempt replay；
- true Retry；
- cancellation；
- stale-result rejection；
- OOM-safe cleanup；
- backend dispatch through registry；
- no assumption that every future backend is stateless。

RGB publication never waits for Mask acquisition.

---

# 19. Gallery and Camera inspection

Gallery presents separate states for:

- Render；
- acquisition attempt/backend/fallback；
- ProposalDecision；
- Mask quality；
- Participation；
- Evidence；
- Candidate staleness。

Navigation, filters and card/frustum selection MUST NOT mutate Mask, Participation, Evidence, references or Candidate.

View role is visible but does not imply trust:

- Anchor；
- Key；
- User-added；
- optional future Auxiliary/Bridge only when an adopted backend creates them。

Backend/fallback identity is inspectable but not a confidence percentage.

---

# 20. User-added Views

`Use Current View` and `Adjust New View…` create user-owned Views through the same RGB/Mask/assessment/Participation contracts.

User-added Views:

- use authoritative gsplat RGB；
- may remain RGB Ready with no Mask and Evidence Not Requested；
- may request route-B automatic Mask generation where required artifacts can be synthesized；
- may use Manual Draw；
- are not removed by Regenerate Auto Views；
- do not implicitly resume the planner；
- are never trusted or rejected solely by source role。

Complete Prompt/Edit correction UX depends on Ticket 07B.

---

# 21. Dirty, refresh and correction lifecycle

Formal dirty state includes:

- per-view acquisition dirty；
- per-view Evidence dirty；
- Lift dirty；
- Candidate stale；
- optional future propagation dirty only when a sequence backend advertises it。

Rules:

- unconfirmed Editing Mask changes no formal Evidence/Candidate state；
- Confirmed Stable Mask revision dirties that View Evidence and Lift；
- Anchor Stable Mask change invalidates support, bootstrap, planner segments and dependent acquisition；
- CameraBinding/RGB change dirties that View acquisition and Evidence；
- Generate More does not dirty prior completed Views；
- Refresh Auto Mask creates a new attempt；
- automatic refresh does not overwrite User Confirmed Stable state；
- no Mask refresh automatically Re-Lifts；
- Confirming a correction affects only that View by default；
- ordinary Confirm does not create tracker reference memory。

`Use as Tracking Reference`, propagation dirty and `Update Multi-view Masks` remain absent unless a future ADR adopts C/D capabilities.

---

# 22. Formal P/N/V Evidence

Only current Views satisfying all conditions contribute:

```text
Render Ready
+ Stable Mask
+ Participation Included
+ current exact identities
```

For View `v`, pixel `p`, Gaussian `g`:

```text
w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)
P(v,g) = Σ positiveWeight(v,p) × w(v,p,g)
N(v,g) = Σ negativeWeight(v,p) × w(v,p,g)
V(v,g) = Σ visibleOrRoiWeight(v,p) × w(v,p,g)
```

Positive, negative and visible weights are independently versioned. `P + N = V` is not assumed.

Mask policy defines:

- Strong Positive Interior；
- Boundary / Ignore Band；
- Local Negative Context Ring；
- Far Neutral Region；
- optional soft weights。

The following are not formal ownership Evidence:

- visible-support sample/provenance；
- bootstrap support；
- Prompt score；
- model score；
- backend confidence；
- ProposalDecision reason；
- tracker confidence/reference memory；
- View role。

---

# 23. Render and Evidence Working Sets

Render Working Set preserves all Gaussians required for correct compositing, occlusion and transmittance.

Evidence Working Set controls which Stable Gaussian IDs receive P/N/V writes.

Required semantics:

- Core Target Set + Context Set form an initial conservative Evidence Working Set；
- bootstrap support may seed but never hard-bound it；
- later Included View observations may expand it；
- Gaussians outside Evidence Working Set still participate in rendering；
- boundary-touch diagnostics trigger declared expansion or fail closed；
- absence from Anchor support cannot alone classify Rejected/Out of Scope。

Production RGB and Direct Evidence MUST share the same raster decision source: projection, ordering, sigma/alpha validity, incoming transmittance, weight and termination decisions.

Complete per-pixel Contributor remains a reference/debug backend, not a product dependency.

---

# 24. Multi-view classification and Candidate

Per-view raw P/N/V is preserved before aggregation.

Aggregation is versioned and considers:

- positive/negative effective Evidence；
- visible mass；
- supporting/conflicting Views；
- optional boundary, footprint and directional-diversity diagnostics；
- safeguards against one close/high-resolution View silently dominating。

Internal classes remain distinct:

```text
Selected
Rejected
Uncertain
Out of Scope
```

Rules:

- Candidate contains Selected only；
- unobserved/insufficient V is Uncertain, not default Rejected；
- material positive+negative conflict is Uncertain；
- Candidate publication is atomic；
- Candidate never mutates Native Selection until explicit Set/Add/Remove/Intersect；
- changed Stable input/policy/runtime makes Candidate stale；
- Re-Lift is explicit。

---

# 25. Native application and recovery

Native operations are explicit:

- Set；
- Add；
- Remove；
- Intersect。

Application uses Native Selection/EditHistory.

After application, `Undo and Fix` restores the exact pre-apply Native Selection and returns to the current AI Candidate correction path.

Restart Current Target disposes target-local AI state while preserving normal scene state and user-owned semantics specified by the operation.

Scene dependency mutation moves the context to Suspended/read-only. Exact Native Undo may restore the dependency identity; otherwise Restart is required.

---

# 26. Future route C/D

Current implementation provides extension schemas only.

```text
C = ordered/dense object-level VOS tracker
D = route-B Key-View references + tracker propagation
```

A later experiment-backed ADR is mandatory before production adoption.

That ADR MUST define:

- supported scenes and measurable downstream benefit；
- sequence ordering and auxiliary/Bridge frames；
- transition/resource envelope；
- session and range identity；
- reference-memory semantics；
- correction-reference action；
- drift detection；
- propagation atomicity；
- fallback to per-view acquisition；
- retry/cancellation/teardown/migration；
- Gallery and dirty-state capability presentation。

Future backends reuse common RGB, proposal, decision, assessment, publication and P/N/V evaluation paths where applicable.

---

# 27. Failure and recovery requirements

All failures state retained artifacts and actionable recovery.

Minimum rules:

- Companion offline/incompatible leaves Native SuperSplat usable；
- RGB failure keeps prior preview only as stale/not-current and offers true Retry；
- support/bootstrap failure preserves Anchor and offers local/user-added alternatives；
- invalid camera is rejected before gain ranking；
- Mask backend failure preserves View/RGB/prior Stable Mask；
- ambiguous decision preserves ProposalSet and requests Review；
- route-B technical failure may use B2 fallback；
- semantic/quality Review never silently falls back；
- OOM/cancellation publishes no partial artifact；
- unsupported extension call produces structured failure with no mutation；
- Evidence/Lift failure preserves Views, Stable Masks and prior Candidate；
- stale results are discarded rather than rebound；
- no failure downgrades to approximate Gaussian attribution。

---

# 28. Validation and quality gates

Required validation includes:

## 28.1 General

- `npm test`；
- `npm run test:companion`；
- `npm run lint`；
- `npm run lint:locales`；
- `npm run build`；
- protocol structural validators；
- canonical digest golden vectors；
- stale-result and identity-mismatch fixtures；
- atomic publication and failure retention tests。

## 28.2 Support and planner

- support projection replay；
- background/separated support rejection；
- indoor behind-wall/outside-room rejection；
- no-free-space conservative fallback；
- sparse marginal-gain and diversity tests；
- append-only Generate More；
- stable View/segment identity。

## 28.3 Route B

- deterministic Prompt synthesis；
- Prompt artifact replay；
- candidate dedup/clustering；
- selected/ambiguous/unavailable fixtures；
- neighbour-instance contamination；
- boundary/fragmentation regression；
- per-view acceptable-mask rate；
- manual correction burden；
- latency and peak VRAM；
- true Retry and cancellation；
- route-A technical fallback provenance；
- no fallback for semantic Review；
- User Confirmed authority preservation。

## 28.4 Downstream quality

- final Gaussian precision/recall；
- background contamination；
- Mixed/Uncertain ratio；
- novel-view rendered-mask quality；
- Add/Remove burden proxy；
- single-view versus multi-view effect；
- View exclusion/reinclusion correctness；
- Working Set expansion；
- reference versus production P/N/V parity；
- repeatability under atomic accumulation。

---

# 29. Ticket ownership and order

```text
04A = Prompt/proposal foundation
04B = real visual-Prompt adapter enablement
07A = conservative object-level Anchor acquisition
07B = floating Prompt/Edit palette UX
08  = visible support + bootstrap + sparse planner
08A = acquisition contracts + backend registry
08B = route-B production acquisition
09  = Gallery / frustum / acquisition inspection
11  = user-added Views
12  = refresh / dirty / stale lifecycle
14  = reference P/N/V and Candidate
20  = production same-decision Evidence
21  = end-to-end failure/calibration/release hardening
```

After 07A:

```text
07A → 07B
07A → 08 → 08A → 08B → 09
07B + 09 → complete correction UX / 11
07B + 08B + downstream production path → 21
```

Ticket 04B remains the next implementation ticket at the time this specification is issued.

---

# 30. Non-goals

Final Spec v1.2 does not require:

- A/B/C/D route tournament before route B；
- tracker, Bridge View or dense sequence implementation；
- automatic correction propagation；
- Prompt/model/backend confidence as P/N/V；
- target-only rasterization；
- complete Contributor in the product path；
- arbitrary part segmentation；
- whole-scene semantic inventory；
- invisible-surface completion；
- automatic Re-Lift；
- implicit mutation of Native Selection。
