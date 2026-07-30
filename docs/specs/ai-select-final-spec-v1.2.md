# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.2

**文档状态：** Current Final Spec / Normative  
**版本：** v1.2（v2.9 protocol-closure revision）  
**日期：** 2026-07-30  
**适用分支：** `ai-select-v1`  
**适用对象：** Product / UX / Frontend / Companion / Algorithm / QA  
**决策依据：** ADR 0013、ADR 0014、DG-20～DG-26

---

# 0. 规范地位

本文件是 AI Select 当前唯一权威产品与工程规格。

它合并并取代以下文件的当前规范效力：

- Final Spec v1.1；
- Amendment 001–005。

这些旧文件继续保留为历史记录，但实现 agent、验收、traceability 和新 Ticket 不得要求读者自行合并其 supersession 链。

当前 Ticket 到本规范的映射由 `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md` 维护。Ticket 内遗留的 v1.1/Amendment 引用仅是历史实现 provenance，不具有当前规范效力。

发生冲突时，权威顺序为：

1. 本文件；
2. 当前 Ticket mapping；
3. ADR 0013；
4. ADR 0014 与未被本文件覆盖的非 superseded ADR；
5. `CONTEXT.md`；
6. implementation tickets；
7. 实现与测试。

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
→ PerViewMaskAcquisitionResult
    ├── KeyViewMaskProposalSet
    └── one attempt-level backendDiagnostics authority
→ KeyViewMaskDecisionPolicy
    ├── selected
    ├── ambiguous
    └── unavailable
→ selected only: ViewAssessmentPolicy
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
≠ Acquisition Ready
≠ Stable Mask Ready
≠ Evidence Ready
≠ Candidate Ready
```

任何上游诊断、模型分数、Visible Support、Decision reason、unavailable 状态或 acquisition backend 身份都不能直接授权 Gaussian ownership。

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

Common identity envelope includes, where applicable：

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
ProposalSet artifact digest
result artifact digest
```

Rules：

- explicit Retry creates a new attempt identity；
- same-attempt replay may be idempotent；
- cancellation is only a resource optimization；
- correctness relies on identity rejection, not timely cancellation；
- incompatible renderer/model/backend/runtime changes invalidate dependent artifacts；
- no partial result may become Ready or Stable；
- atomic publication replaces a whole bound artifact or publishes nothing。

---

# 5. Authoritative RGB and CameraBinding

All AI observation RGBs MUST come from the locked authoritative gsplat rendering path：

- Anchor Preview / Final；
- Generated Key View；
- User-added View。

RGB Ready means：

- exact CameraBinding render succeeded；
- RGB payload and digest validate；
- request/result identity is current；
- CameraBinding revision is current。

RGB Ready MUST NOT require Stable Mask、Evidence、complete Contributor 或 Candidate。

Frustum、depth、support projection 和 RGB MUST use the same CameraBinding convention and image dimensions。

---

# 6. Anchor Prompt, proposal and confirmation

Anchor acquisition uses three stages：

```text
Prompt Authoring
→ model proposal generation
→ conservative ProposalDecision
→ candidate acceptance / Editing Mask
→ Confirm Mask
```

Prompt Authoring and direct Mask pixel editing are distinct modes and histories。

Prompt capabilities are versioned and truthful. Unsupported Point/Box/Mask/Text combinations fail before inference；they are never silently dropped or converted。

Anchor model output is a bounded proposal set. The decision layer MUST：

- deduplicate exact Masks；
- cluster near-duplicate Masks；
- reject hard Prompt contradictions；
- treat raw model score as diagnostic/tie-break only；
- preserve materially distinct plausible candidates as `ambiguous`；
- preserve `unavailable` when no eligible candidate exists。

Only Confirm publishes a new Anchor Stable Mask revision。

A confirmed Anchor Stable Mask is an identity seed for later geometry and views. It is not Gaussian Candidate or ownership Evidence。

---

# 7. Floating Prompt/Edit palette

The fitted authoritative image surface owns Prompt and Mask pointer mapping。

The palette MUST support drag、deterministic clamp/optional edge snap、expanded/collapsed、Space temporary hide、no stale hit region、focus-aware shortcuts/accessibility、target/context disposal reset。

Palette state MUST NOT enter PromptState、Mask history、Evidence、Candidate or Companion requests。

Ticket 07B may execute in parallel with Ticket 08 after Ticket 07A, but remains mandatory before complete Generated/User-added View correction UX and final release hardening。

---

# 8. Visible Target Support

Ticket 08 MUST publish a versioned `VisibleTargetSupportArtifact`：

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

Requirements：

- samples are bounded and deterministically ordered/encoded；
- `stableGaussianId` is optional provenance only；
- support may originate from depth、first-hit support or equivalent visible-surface extraction；
- invalid/background-dominated/separated support lowers quality or fails closed；
- support can guide geometry and Prompt synthesis；
- support cannot publish P/N/V、Candidate or Native Selection；
- absence from support cannot classify a Gaussian as Rejected or Out of Scope。

---

# 9. Target Bootstrap

`TargetBootstrapArtifact` is a lightweight object summary referencing the visible-support artifact：

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

It may guide framing、camera generation、ROI construction、Prompt synthesis and an initial conservative Evidence Working Set seed。

It MUST NOT become a hard upper bound on later Working Set expansion。

---

# 10. Adaptive sparse Key-View planning

Ticket 08 MUST replace a fixed orbit with bounded adaptive sparse planning。

Planner evaluates independently：camera validity、target observation gain、directional diversity gain、expected render/scene-support quality、resource cost。

Invalid camera geometry cannot win through theoretical information gain。

The default route does not require Bridge Views、tracker transition envelopes、dense continuous trajectories 或 adjacent-frame ordering。

Output is an immutable `SparseKeyViewPlanSegment` bound to Anchor、support、bootstrap、planner policy、attempt and stable View identities。

`Generate More` appends a new segment and preserves prior completed View/RGB/Mask artifacts。

`Regenerate Auto Views` may supersede planner-owned segments while preserving user-owned Views。

---

# 11. Acquisition contract foundation

Ticket 08A owns contracts and validators, not production model execution。

Required contracts include：

- `KeyViewPromptArtifact`；
- `KeyViewMaskProposalSet`；
- `PerViewMaskAcquisitionResult`；
- `KeyViewMaskDecision`；
- acquisition request/result identity；
- attempt/fallback identity；
- publication command/result；
- backend descriptor/bundle/registry；
- optional sequence extension schemas；
- structural validators、canonical digest rules and golden vectors。

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

Capabilities derive from the actual bundle and MUST match `backendKind`：

```text
Route B = perView required, sequence absent
Route C = sequence required, perView optional
Route D = perView required, sequence required
```

A contradictory descriptor/bundle is Not Ready。

## 11.2 Per-view provider and result envelope

```ts
interface MultiViewMaskAcquisitionProvider {
    acquireView(request: PerViewMaskAcquisitionRequest): Promise<PerViewMaskAcquisitionResult>;
}

interface PerViewMaskAcquisitionResult {
    schemaVersion: number;
    requestIdentity: PerViewMaskAcquisitionRequestIdentity;
    proposalSet: KeyViewMaskProposalSet;
    backendDiagnostics: AcquisitionBackendDiagnostics;
    resultDigest: string;
}
```

The provider returns a ProposalSet plus one attempt-level backend-diagnostics authority. It MUST NOT return `KeyViewMaskDecision`、`ViewAssessmentResult`、Stable status、Participation、Candidate/P/N/V or publication side effects。

`KeyViewMaskProposalSet` contains candidate artifacts and candidate-local metrics only；it MUST NOT duplicate attempt-level `backendDiagnostics`。

A successful result may contain an empty ProposalSet. Technical dispatch/inference failure produces no partial result or ProposalSet。

## 11.3 Decision identity

Every Decision variant MUST bind：

```text
targetContextId + contextRevision
viewId
acquisitionAttemptId
proposalSetArtifactDigest
decisionPolicyDigest
artifactDigest
```

Selected/ambiguous proposal IDs MUST belong to that exact ProposalSet. Cross-attempt proposal-ID collision cannot satisfy membership。

## 11.4 Optional sequence extension

Route B has no sequence extension. Unsupported operations fail before inference or state mutation。

---

# 12. Key-View Prompt synthesis

Ticket 08B MUST implement `KeyViewPromptSynthesizer` independently from controller and provider：

```text
VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
+ SparseKeyViewPlanSegment / Key-View CameraBinding
+ adapter capabilities
+ Prompt synthesis policy
→ KeyViewPromptArtifact
```

A Prompt artifact binds target/scene/View、support/bootstrap/segment、Camera/RGB、capability、policy、ordered Prompt payload、diagnostics and artifact digest。

Supported Prompt families may include projected positive support、target center、Box/ROI、local negatives、compatible Mask input、scale/clipping/boundary diagnostics。

Unsupported Prompt types fail closed and are not silently dropped。

Prompt regeneration and SAM Retry are distinct operations。

---

# 13. Route-B proposal generation

Route B performs independent prompt-conditioned SAM inference per authoritative Key View and requires no adjacent frames、tracker memory、Bridge Views or dense sequences。

Provider returns a bounded `KeyViewMaskProposalSet` through `PerViewMaskAcquisitionResult`。Each proposal binds its Mask artifact and may include raw model score plus geometry/Prompt consistency diagnostics。

No provider-internal Top-1 decision is authoritative。

---

# 14. Key-View proposal decision

`KeyViewMaskDecisionPolicy` is separate from inference and assessment。

Decision rules：

- validate exact ProposalSet digest/attempt first；
- exact duplicate and near-duplicate clustering precedes selection；
- hard Prompt contradiction makes a proposal ineligible；
- raw model score is not sole selector；
- one credible cluster may become `selected`；
- multiple materially distinct plausible clusters become `ambiguous`；
- zero eligible proposals becomes `unavailable`；
- ambiguous preserves proposals and publishes no arbitrary Stable Mask。

---

# 15. View Assessment and Participation

Only a `selected` proposal enters `ViewAssessmentPolicy`。

Assessment answers whether the selected Mask is usable, not which proposal is the target；it may use Mask geometry、projected support consistency、clipping、fragmentation、contamination、versioned Gaussian support/visibility diagnostics and later formal P/N/V diagnostics。

Assessment produces Good / Review / Failed and structured reason codes。

Participation is independent from View role、planner role and backend。

Default transitions：

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
→ Acquisition Ready / completed
→ Decision Unavailable
→ no ViewAssessmentResult
→ no new Stable Mask
→ Excluded
```

`unavailable` is not backend/protocol/OOM/cancellation failure and does not trigger automatic Route-A fallback。

User Confirmed Stable authority cannot be silently replaced or revoked。

---

# 16. Mask publication

`MaskPublicationCoordinator` is the only route-B layer allowed to publish an automatic Stable Mask revision。

It validates current identity、exact ProposalSet/Decision membership、selected proposal、RGB dimensions/digest、decision/assessment/publication policy、Stable authority and no partial/cancelled/stale state。

Automatic results MUST NOT silently replace a User Confirmed Stable Mask。

Mask technical failure preserves View/RGB/frustum and prior Stable Mask。

Ambiguous/unavailable publish no new Stable Mask；unavailable remains distinguishable from technical failure。

---

# 17. Route-A fallback

Route A remains the existing projected-support + independent single-frame SAM baseline。

Automatic fallback is permitted only after route-B technical/capability failure：backend unavailable、required capability unavailable、technical compatibility rejection、recoverable inference error、declared lower-resource route-A path after OOM。

Automatic fallback is prohibited for：

- ambiguous；
- unavailable after successful acquisition；
- neighbour contamination；
- Prompt inconsistency；
- clipping/fragmentation risk；
- Assessment Review；
- existing User Confirmed Stable Mask。

Fallback creates a new attempt with parent/reason and route-A backend/model/runtime/policy identity。

Route A uses the same ProposalSet → Decision → Assessment → Publication pipeline and may Auto Good only under the same or stricter gates。

---

# 18. Orchestration, scheduling and legacy migration

Generated View controller MUST separate planning、RGB rendering、Prompt synthesis、acquisition dispatch、proposal decision、assessment、publication and optional future sequence dispatch。

Controller coordinates artifacts；it does not implement geometric Prompt synthesis、SAM selection、Decision or Assessment algorithms。

Scheduling MUST support bounded concurrency、attempt identity、idempotent replay、true Retry、cancellation、stale rejection、OOM-safe cleanup、registry dispatch and stateful future backend compatibility。

RGB publication never waits for Mask acquisition。

The current implementation MUST explicitly migrate from legacy generated-view contracts：

```text
GeneratedViewMaskResponse.assessment
maskSource: 'propagated'
GeneratedViewMaskPropagation as generic diagnostics
controller direct Stable/Participation publication
legacy generated-view-mask/v1 payload/cache
```

Requirements：

- provider-returned Assessment is not current；
- fixed `maskSource: 'propagated'` is not generic route-B provenance；
- attempt diagnostics use `PerViewMaskAcquisitionResult.backendDiagnostics`；
- controller publishes only through Decision/Assessment/Publication layers；
- legacy payload/cache fails current contract/version validation and is never structurally rebound；
- User Confirmed Stable authority survives migration；
- route-A compatibility adapter emits the current result/ProposalSet/Decision contract and remains visibly route A。

---

# 19. Gallery and Camera inspection

Gallery presents separate states for Render、acquisition attempt/backend/fallback、ProposalDecision、Mask/Stable quality、Participation、Evidence、Candidate staleness。

It MUST distinguish：

```text
acquisition ready + Decision unavailable
```

from：

```text
acquisition technical failure + no Decision
```

Navigation、filters and card/frustum selection MUST NOT mutate formal state。

View role is visible but does not imply trust。Backend/fallback identity is inspectable but not a confidence percentage。

---

# 20. User-added Views

`Use Current View` and `Adjust New View…` create user-owned Views through the same RGB/Prompt/acquisition/Decision/Assessment/publication/Participation contracts。

User-added Views may remain RGB Ready with no Mask/Evidence requested；may request route-B automatic Mask where support context exists；may use Manual Draw；are not removed by Regenerate Auto Views；do not resume planner implicitly；are never trusted by source role alone。

Complete Prompt/Edit correction UX depends on Ticket 07B。

---

# 21. Dirty, refresh and correction lifecycle

Formal dirty state includes Prompt synthesis dirty、per-view acquisition dirty、per-view Evidence dirty、Lift dirty、Candidate stale and optional future propagation dirty。

Rules：

- unconfirmed Editing Mask changes no formal Evidence/Candidate state；
- Confirmed Stable revision dirties that View Evidence and Lift；
- Anchor Stable change invalidates support/bootstrap/plans/dependent Prompt/acquisition；
- Camera/RGB change dirties that View Prompt/acquisition/Evidence；
- Generate More does not dirty prior completed Views；
- Refresh creates a new attempt；
- automatic refresh does not overwrite User Confirmed Stable；
- no Mask refresh automatically Re-Lifts；
- confirming correction affects only that View by default；
- ordinary Confirm does not create tracker memory；
- ambiguous/unavailable without Stable replacement do not dirty exact prior Evidence solely because a new review artifact exists；
- legacy acquisition artifacts invalidate by contract/version identity and cannot attach to a current attempt。

---

# 22. Formal P/N/V Evidence

Only current Views satisfying：

```text
Render Ready
+ Stable Mask
+ Participation Included
+ current exact identities
```

contribute。

```text
w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)
P(v,g) = Σ positiveWeight(v,p) × w(v,p,g)
N(v,g) = Σ negativeWeight(v,p) × w(v,p,g)
V(v,g) = Σ visibleOrRoiWeight(v,p) × w(v,p,g)
```

Positive、negative、visible weights are independently versioned；`P + N = V` is not assumed。

Visible support、bootstrap、Prompt/model score、backend diagnostics/confidence、Decision reason/status、fallback、tracker state and View role are not formal ownership Evidence。

---

# 23. Render and Evidence Working Sets

Render Working Set preserves all Gaussians required for correct compositing、occlusion and transmittance。

Evidence Working Set controls which Stable Gaussian IDs receive P/N/V writes。

Bootstrap/support may seed but never hard-bound it；later Included Views may expand it；outside Gaussians still render；boundary-touch triggers expansion or fail closed；Anchor absence cannot classify Rejected/Out of Scope。

Production RGB and Direct Evidence MUST share the same raster decision source。

Complete per-pixel Contributor remains reference/debug only。

---

# 24. Multi-view classification and Candidate

Per-view raw P/N/V is preserved before aggregation。

Aggregation is versioned and considers effective positive/negative Evidence、visible mass、supporting/conflicting Views、optional boundary/footprint/diversity diagnostics and dominance safeguards。

Internal classes remain Selected、Rejected、Uncertain、Out of Scope。

Candidate contains Selected only；unobserved/insufficient V and material conflict become Uncertain；publication is atomic；Candidate never mutates Native Selection until explicit operation；changed inputs make Candidate stale；Re-Lift is explicit。

---

# 25. Native application and recovery

Native operations are explicit Set、Add、Remove、Intersect and use Native Selection/EditHistory。

Undo and Fix restores exact pre-apply Native Selection and returns to current AI Candidate correction path。

Restart Current Target disposes target-local AI state while preserving native scene/user-owned semantics。

Scene dependency mutation moves context to Suspended/read-only；exact Native Undo may restore identity, otherwise Restart is required。

---

# 26. Future route C/D

Current implementation provides extension schemas only：

```text
C = ordered/dense object-level VOS tracker
D = route-B Key-View references + tracker propagation
```

A later experiment-backed ADR is mandatory before production adoption and MUST define supported scenes/benefit、sequence ordering/auxiliary frames、resource envelope、identity、reference semantics、drift、atomicity、fallback、retry/teardown/migration and Gallery/dirty presentation。

Future backends reuse common RGB、ProposalSet、Decision、Assessment、publication and P/N/V paths where applicable。

---

# 27. Failure and recovery requirements

All failures state retained artifacts and actionable recovery。

Minimum rules：

- Companion offline/incompatible leaves Native SuperSplat usable；
- RGB failure keeps prior preview only as stale/not-current and offers true Retry；
- support/bootstrap failure preserves Anchor and offers local/user-added alternatives；
- invalid camera is rejected before gain ranking；
- technical Mask backend failure preserves View/RGB/prior Stable Mask；
- ambiguous preserves ProposalSet and requests Review；
- unavailable preserves successful acquisition result/diagnostics, publishes no Stable Mask, and offers Prompt/View/manual/Retry/Exclude recovery；
- route-B technical failure may use B2 fallback；
- semantic/quality Review、ambiguous、unavailable never silently fall back；
- OOM/cancellation publishes no partial artifact；
- unsupported extension call produces structured failure with no mutation；
- legacy contract/cache mismatch is rejected, never rebound；
- Evidence/Lift failure preserves Views、Stable Masks and prior Candidate；
- stale results are discarded rather than rebound；
- no failure downgrades to approximate Gaussian attribution。

---

# 28. Validation and quality gates

Required general validation：repository tests/lint/build、protocol validators、canonical digest vectors、stale identity fixtures、atomic publication/failure retention。

Support/planner validation：projection replay、background/separated rejection、behind-wall/outside-room rejection、conservative no-free-space fallback、sparse gain/diversity、append-only Generate More、stable identity。

Route-B validation：

- deterministic Prompt synthesis/replay；
- single backend-diagnostics authority；
- ProposalSet candidate validation；
- exact Decision-to-ProposalSet digest/attempt binding；
- proposal-ID collision across attempts；
- selected/ambiguous/unavailable fixtures；
- unavailable-versus-technical-failure matrix；
- contamination/boundary/fragmentation regression；
- acceptable-mask/manual burden/latency/VRAM；
- Retry/cancellation；
- route-A technical fallback provenance and no semantic fallback；
- User Confirmed preservation；
- legacy generated-view contract/cache rejection and route-A adapter migration。

Downstream validation：Gaussian precision/recall、background contamination、Mixed/Uncertain、novel-view mask quality、Add/Remove burden、single-vs-multi-view、exclude/reinclude、Working Set expansion、reference/production parity、atomic repeatability。

---

# 29. Ticket ownership and order

Current mapping is maintained in `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`。

Core ownership：

```text
04A = Prompt/proposal foundation
04B = real visual-Prompt adapter enablement
07A = conservative object-level Anchor acquisition
07B = floating Prompt/Edit palette UX
08  = visible support + bootstrap + sparse planner
08A = acquisition contracts + result/Decision identity + backend registry
08B = route-B production acquisition + fallback + legacy migration
09  = Gallery / frustum / acquisition inspection
11  = user-added Views
12  = refresh / dirty / stale / legacy invalidation lifecycle
14  = reference P/N/V and Candidate
20  = production same-decision Evidence
21  = end-to-end failure/calibration/release hardening
```

After 07A：

```text
07A → 07B
07A → 08 → 08A → 08B → 09
07B + 09 → complete correction UX / 11
07B + 08B + downstream production path → 21
```

Ticket 04B remains the next implementation ticket at the time of this revision。

---

# 30. Non-goals

Final Spec v1.2 does not require：

- A/B/C/D route tournament before route B；
- tracker、Bridge View or dense sequence implementation；
- automatic correction propagation；
- Prompt/model/backend confidence or unavailable status as P/N/V；
- target-only rasterization；
- complete Contributor in the product path；
- arbitrary part segmentation；
- whole-scene semantic inventory；
- invisible-surface completion；
- automatic Re-Lift；
- implicit mutation of Native Selection。
