# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.1

**文档状态：** Final Spec / Baseline v1.1  
**目标：** 作为 AI Select 当前版本的产品、交互、状态机、数据边界、Lifting 语义与工程实现基线。  
**适用对象：** Product / UX / Visual / Frontend / Companion / Algorithm / QA  
**版本：** v1.1  
**日期：** 2026-07-23  
**基线来源：** Final Spec v1.0 + ADR 0013 + DG-20 Mask-Conditioned Direct Gaussian Evidence  
**适用分支：** `ai-select-v1`

---

# 0. 文档定位与规范继承

本规格取代 `docs/specs/ai-select-final-spec-v1.0.md`，作为新实现、验收与 ticket traceability 的最高产品/工程规格。

Final Spec v1.0 中未被本规格显式修改的产品、交互、生命周期和 Native Selection 规则继续有效，并视为已合并到 v1.1。

当文档发生冲突时，权威顺序为：

1. `docs/specs/ai-select-final-spec-v1.1.md`；
2. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`；
3. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` 中未被 ADR 0013 替代的部分；
4. `CONTEXT.md`；
5. 非 superseded ADR；
6. 对应 implementation issue；
7. 实现与测试。

本规格中的 MUST / SHALL / 必须 / 不得为强制约束。

## 0.1 v1.1 的修订范围

v1.1 保留 v1.0 的产品主模型：

- AI Select 是原生 Gaussian Selection Tool；
- Current View First；
- explicit Camera Inspection；
- 独立、版本化 Mask；
- Adaptive Generated Views；
- View Assessment 与 Participation 分离；
- Explicit Repropagate / Re-Lift；
- Candidate / Uncertain；
- Native Set / Add / Remove / Intersect；
- Restart Current Target；
- Suspended Context 与 exact Undo recovery。

v1.1 主要修订：

1. 正式 Lifting 不再依赖完整逐像素 Contributor artifact；
2. 正式数据表示改为 per-view、per-Gaussian 的 Mask-Conditioned Evidence；
3. RGB Ready 与 Evidence Ready 分离；
4. Camera Inspection 和 AI View Render Ready 不再被 Contributor 对齐失败阻塞；
5. 区分 Render Working Set 与 Evidence Working Set；
6. 引入 per-view Evidence Artifact 及增量失效语义；
7. 完整 Contributor 降为 debug/reference backend；
8. 生产 Direct Evidence 必须与权威 RGB 共享 raster decision source。

## 0.2 Decision Gate 状态

v1.0 已关闭的 DG-01～DG-19 继续有效，其中 DG-14 仍为 Deferred。

新增：

```text
DG-20  CLOSED
Mask-Conditioned Direct Gaussian Evidence
```

DG-20 决定：

- AI View 的权威观察结果是 gsplat RGB；
- Evidence 是 Stable Mask 存在后产生的独立派生 artifact；
- 正式 Lift 直接使用 P/N/V Evidence；
- 完整 Contributor 不再处于产品关键路径；
- 生产 Evidence 与 RGB 必须共享权威 acceptance / transmittance / termination 决策。

---

# 1. 一句话产品定义

> **AI Select 是 SuperSplat 的一种 3D Gaussian Selection Tool：用户以当前场景视角作为默认 AI Anchor，在需要时通过 3D Camera Frustum 调整或补充观察视角，在 AI View Dock 中查看权威 gsplat RGB 并独立生成、修正或手工绘制 2D Mask；系统针对 Included Stable View Annotations 累计 per-Gaussian Mask-Conditioned Evidence，将多视图 Evidence Lift 为 Gaussian Candidate，最后通过原生设置、添加、移除、相交应用到当前 Gaussian Selection。**

---

# 2. 核心模型

```text
Camera View
    ↓
Authoritative gsplat RGB
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Mask-Conditioned Gaussian Evidence (P / N / V)
    ↓
Multi-view Evidence Aggregation
    ↓
Gaussian Lifting
    ↓
AI Candidate + Uncertain
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

其中：

```text
RGB           = Mask-independent authoritative observation
Stable Mask   = user/algorithm-confirmed 2D annotation
Evidence      = Mask-conditioned per-view Gaussian measurements
Candidate     = current policy-derived Selected Gaussian set
Uncertain     = mixed / unobserved / insufficient Gaussian diagnostics
```

---

# 3. 产品原则

## 3.1 AI Select 是 Selection Tool，不是 Workspace

AI Select 与 Picker、Lasso、Polygon、Brush、Flood、Sphere、Box 处于同一级。

它复用：

- SuperSplat Scene Manager；
- 3D Viewport；
- Bottom Toolbar；
- Native Selection；
- Native EditHistory；
- Native Undo / Redo；
- Delete / Lock / Separate / Duplicate / Transform / Export。

不创建独立语义对象数据库、长期 Session Stack 或第二套 3D 编辑系统。

## 3.2 Candidate 是派生结果

AI Candidate 只能来自当前 Included Stable View Annotations 的正式 Lift。

结构性错误通过：

```text
View / Mask / Participation 修正
→ Explicit Re-Lift
```

小型最终修正通过 Native Selection tools 完成。

Candidate 不支持独立 3D Brush/Lasso patch 后再与后续 Re-Lift 隐式合并。

## 3.3 RGB、Mask、Evidence 生命周期分离

```text
RGB Ready
≠
Mask Ready
≠
Evidence Ready
≠
Candidate Ready
```

任何一层失败不得错误地改写另一层状态。

---

# 4. Runtime Ownership

## 4.1 Browser Editor owns

- scene / splat state；
- Stable Gaussian IDs 及当前 splat index 映射；
- Current Editor Camera；
- CameraBinding 构造；
- 3D Frustum 展示与操纵；
- CurrentTargetContext；
- AIView registry；
- Mask version lifecycle；
- View Participation；
- Candidate / Uncertain visualization；
- Native Selection / EditHistory；
- Set / Add / Remove / Intersect。

## 4.2 Selection Service Companion owns

- locked authoritative gsplat AI observation rendering；
- same-decision Mask-Conditioned Evidence production；
- SAM inference 与自动 Mask 生成/传播；
- Generated View planning/rendering；
- ViewAssessmentPolicy；
- per-view Evidence Artifact；
- multi-view Evidence aggregation；
- Gaussian Lifting policy；
- renderer/model/runtime readiness；
- disposable runtime caches；
- debug/reference complete Contributor backend。

Companion 可以缓存 scene tensors、RGB、Evidence、reference Contributor 与 model state，但缓存不是用户可见产品状态。

---

# 5. Authoritative AI Rendering

## 5.1 SuperSplat / PlayCanvas

负责：

```text
Interactive Editor Rendering
Scene Visualization
Viewport Camera
Frustum Visualization / Picking / Manipulation
Candidate / Uncertain Visualization
Native Selection Visualization
```

## 5.2 gsplat

负责全部 AI Observation RGB：

```text
Anchor Preview RGB
Anchor Final RGB
Generated View RGB
User-added View RGB
```

以及需要时的：

```text
Depth / Auxiliary Buffers
Mask-Conditioned Direct Gaussian Evidence
```

## 5.3 RGB Ready 条件

AIView `renderStatus = ready` 必须表示：

- exact CameraBinding 的权威 gsplat RGB 已成功产生；
- RGB artifact/digest 合法；
- request/result binding 与当前 context 匹配；
- 当前 CameraBinding revision 未被更新结果 supersede。

不得要求：

- 完整 Contributor artifact 已生成；
- Stable Mask 已存在；
- Evidence 已生成；
- Candidate 已计算。

## 5.4 Correctness Invariant

权威 RGB、Mask、Evidence、Depth 和 Frustum 必须绑定一致且可重放的 identity：

```text
Target / Scene / Splat dependency
CameraBinding
RGB digest
Stable Mask digest（Evidence 使用时）
Evidence Policy digest（Evidence 使用时）
Render Working Set token
Evidence Working Set token
Stable Gaussian ID mapping
```

生产 Direct Evidence 必须与对应权威 RGB 共享：

- projected Gaussian data；
- front-to-back order；
- sigma evaluation；
- alpha value；
- alpha validity threshold；
- incoming transmittance `T`；
- `alpha × T` weight；
- early termination decision。

正式要求是同一 **decision source**，不强制单次 CUDA launch。

## 5.5 禁止的 Attribution 替代

正式 Evidence 不得替换为：

```text
nearest Gaussian
center projection
visible-only set
top-k contributors
distance threshold
screen-space overlap without alpha × transmittance
```

---

# 6. CameraBinding、Editor Camera 与 Frustum

v1.0 的 CameraBinding、Editor Camera、Anchor Camera、Anchor Frustum、Camera Inspection 与 stale-response 规则继续有效。

CameraBinding 必须唯一决定：

```text
pose
intrinsics
resolution
near / far clipping
camera convention
```

3D Frustum 必须由与权威 gsplat RGB 相同的 CameraBinding 派生。

Camera Inspection Observer Camera 不得静默成为 Anchor Camera。

---

# 7. AIView Domain Model

```ts
interface AIView {
  viewId: string;

  source:
    | 'anchor'
    | 'auto-generated'
    | 'user-added'
    | 'replacement';

  camera: CameraBinding;

  renderStatus:
    | 'pending'
    | 'rendering'
    | 'ready'
    | 'failed';

  rgbArtifact?: string;
  rgbDigest?: string;

  participation:
    | 'included'
    | 'excluded';

  stableMaskId?: string;
  editingMaskId?: string;

  evidenceStatus?:
    | 'not-requested'
    | 'pending'
    | 'ready'
    | 'stale'
    | 'failed';

  evidenceArtifactId?: string;
}
```

`evidenceStatus` 可以由依赖版本推导，不要求成为额外、可能冲突的持久 source of truth。

## 7.1 合法状态

```text
View Ready + Mask None + Evidence Not Requested
View Ready + Stable Mask + Evidence Stale
View Ready + Stable Mask + Evidence Failed
View Ready + Stable Mask + Evidence Ready
```

Evidence Failed 不等于 View Render Failed。

## 7.2 四类失败

### View Render Failure

```text
Camera invalid
authoritative RGB render failed
RGB unavailable
RGB / CameraBinding binding invalid
```

### Mask Failure

```text
SAM failed
propagation failed
mask artifact invalid
```

### Evidence Failure

```text
P/N/V accumulation failed
Evidence identity invalid
Render Working Set incomplete
Evidence Working Set invalid
Stable ID mapping invalid
```

### Lift Failure

```text
multi-view aggregation failed
classification failed
Candidate atomic publication failed
```

---

# 8. Render Retry 语义

同一 render attempt identity 可以幂等回放，以支持请求响应丢失后的恢复。

用户显式点击：

```text
[重试]
```

必须为同一 CameraBinding 创建新的 render attempt，并真正重新执行权威 RGB render。

不得把已缓存 failure 直接回放并伪装成新 Retry。

CameraBinding 不得通过静默 jitter 或无语义字段修改来绕过缓存。

---

# 9. Final Anchor Preview

Frustum Manipulation End 后请求一次固定 CameraBinding revision 的 final-resolution authoritative gsplat RGB。

Dragging 期间：

- 更新 Anchor CameraBinding；
- 更新 3D Frustum；
- 不请求正式 RGB。

Manipulation End：

- 发起新的 RGB render attempt；
- 旧 CameraBinding revision 的响应丢弃；
- 当前请求失败时保留 last valid preview，但明确标记为 stale/not-current；
- 完整 Contributor 或 Evidence 失败不得将已成功 RGB 变为 Preview Failure。

---

# 10. Mask 是独立、版本化 Annotation

v1.0 的 `MaskAnnotation`、Stable Mask、Editing Mask、Confirm Mask、Prompt、Brush、Clear、Restore Auto、manual mask 与 mask-local Undo/Redo 规则继续有效。

```ts
interface MaskAnnotation {
  maskId: string;
  viewId: string;

  source:
    | 'single-frame-sam'
    | 'propagated'
    | 'manual'
    | 'hybrid';

  status:
    | 'draft'
    | 'auto-good'
    | 'auto-review'
    | 'user-confirmed';

  maskArtifact: string;
  prompts?: MaskPrompt[];
  parentMaskId?: string;
  createdFromRgbDigest: string;
}
```

Stable Mask 必须绑定创建它的 RGB digest。

Editing Mask 在 Confirm 前不得进入正式 Evidence、Coverage 或 Lift。

---

# 11. Stable Mask 与 Evidence 依赖

Stable Mask 从 v3 发布为 v4 时：

```text
对应 View 的旧 Evidence Artifact
→ stale
```

若该 View 为 Included：

```text
Candidate
→ stale
```

旧 Evidence 和旧 Candidate 可以保留用于原子替换、对比与失败恢复，但不得作为当前结果应用。

Editing Mask 的变化不会使当前 Candidate stale，直到 Confirm Mask 发布新的 Stable Mask。

---

# 12. Anchor Validation 与 Confirm Anchor

## 12.1 Confirm 条件

Anchor 必须具有：

```text
Confirmed Stable Mask
+
Included Participation
+
Valid Camera / RGB / Mask Binding
+
Valid mask-conditioned Gaussian support probe
```

Confirm Anchor 不要求：

- 完整逐像素 Contributor artifact；
- 正式 multi-view Evidence Artifact；
- Candidate。

## 12.2 Hard Validation

以下情况必须阻塞 Confirm Anchor：

- final authoritative RGB 不可用；
- Mask 为空或低于最小有效面积；
- Mask 没有可计算的 Gaussian support；
- Mask / RGB / CameraBinding 版本不匹配；
- 最新 Mask/SAM revision 尚在计算；
- CameraBinding 已失效；
- Stable Gaussian ID 映射无法建立；
- Render Working Set 无法安全建立。

Mask Gaussian support 可以通过低成本、版本化 support probe 或 reference Evidence operation 验证；它不是完整 Contributor publication。

## 12.3 Soft Warning

以下不默认阻塞：

- target touches image boundary；
- target very small；
- fragmented mask；
- weak visible support；
- evidence-backed observation risk。

## 12.4 Atomic Publish

Confirm Anchor 后原子发布并绑定：

```text
Anchor CameraBinding
Anchor RGB Digest
Anchor Stable Mask + Digest
Mask Evidence Policy Version
Target Dependency Token
Scene / Splat Version
```

完整 Contributor 不属于正式 Anchor binding。

---

# 13. Participation 与 Included Stable View Annotation

是否参与 Lift 只由：

```text
renderStatus = ready
stableMaskId exists
participation = included
```

决定。

Auto Good 默认 Included；Auto Review 默认 Excluded；User Confirmed 默认 Included；Failed / no Stable Mask 默认 Excluded。

Review 不得以隐藏低权重偷偷参与 Lift。

---

# 14. Gaussian Evidence 定义

对于 View `v`、Pixel `p`、Gaussian `g`：

\[
w_{v,p,g}=\alpha_{v,p,g}T_{v,p,g}
\]

其中：

- `alpha` 是 Gaussian 对 Pixel 的局部 alpha；
- `T` 是该 Gaussian 之前的 incoming transmittance；
- `w` 是实际写入权威 RGB 的可见贡献质量。

定义：

\[
P_{v,g}=\sum_p m^+_{v,p}w_{v,p,g}
\]

\[
N_{v,g}=\sum_p m^-_{v,p}w_{v,p,g}
\]

\[
V_{v,g}=\sum_p m^V_{v,p}w_{v,p,g}
\]

语义：

```text
P = target-positive mass
N = local-background counter-evidence
V = valid visible observation mass
```

Evidence 必须绑定 Stable Gaussian ID，而不是 tensor row、file row、draw order 或临时 renderer index。

---

# 15. Mask Evidence Policy

## 15.1 Strong Positive Interior

高置信 Mask 内部：

```text
positiveWeight = 1
negativeWeight = 0
visibleWeight  = 1
```

可通过 erosion 或 soft probability 定义。

## 15.2 Boundary / Ignore Band

边界附近：

```text
positiveWeight = 0 或较小值
negativeWeight = 0 或较小值
visibleWeight  = 1
```

可选累计：

```text
boundaryMass
```

## 15.3 Local Negative Context Ring

Mask 外扩后的局部环带：

```text
positiveWeight = 0
negativeWeight = 1
visibleWeight  = 1
```

用于区分目标与：

- 墙面；
- 桌面；
- 柜体；
- 相邻对象；
- 接触边界。

## 15.4 Far Region

远离目标：

```text
positiveWeight = 0
negativeWeight = 0
visibleWeight  = 0
```

不得把整张图所有 Mask 外像素无差别作为强负证据。

## 15.5 Soft Mask

正、负、可见权重可以是连续值，彼此独立，不要求：

\[
m^+ + m^- = 1
\]

必须允许显式 ignore 区域。

---

# 16. Direct Evidence Production Contract

正式生产路径应在权威 raster decision chain 中直接累计 Evidence。

对于每个被权威 rasterizer 接受的贡献：

```text
w = alpha × incoming T
```

同一个 `w` 同时用于：

```text
RGB accumulation
Evidence accumulation
```

概念实现：

```cpp
for each accepted Gaussian g at pixel p:
    w = alpha * T

    rgb[p] += color[g] * w

    localId = globalToEvidenceLocal[g]
    if (localId >= 0) {
        atomicAdd(&positiveMass[localId], positiveWeight[p] * w)
        atomicAdd(&negativeMass[localId], negativeWeight[p] * w)
        atomicAdd(&visibleMass[localId],  visibleWeight[p]  * w)
    }
```

正式路径不需要输出完整逐像素 Contributor IDs/weights。

## 16.1 多 pass 条件

允许：

```text
projection / sorting
→ memory preparation
→ authoritative RGB + Evidence accumulation
```

不要求单次 CUDA launch。

但后续 pass 不得独立重新做出可能与最终 RGB 分叉的 acceptance / termination 决定。

## 16.2 Atomic nondeterminism

`atomicAdd` 累加顺序可能导致末位 float32 差异。

Evidence Policy 必须：

- 使用 benchmark 校准的 margin；
- 不把最后几个 ULP 作为分类边界；
- 进行相同输入重复运行测试；
- 以分类稳定性为生产验收目标；
- 保留 raw mass 供诊断，而不是在 CUDA 内硬编码分类。

---

# 17. Render Working Set 与 Evidence Working Set

## 17.1 Render Working Set

记为：

```text
R_v
```

表示对 CameraBinding `v` 可能影响以下结果的完整保守 Gaussian 集合：

```text
projection
sorting
RGB
occlusion
transmittance
termination
```

空间分块允许仅加载 Camera 相关 chunks，但必须满足：

```text
render(R_v, CameraBinding)
≈
render(complete scene, CameraBinding)
```

并通过定义的 numeric / visual parity gate。

无法安全证明 chunk 无贡献时必须保守包含，或 fallback 到 full working set。

## 17.2 Evidence Working Set

记为：

```text
W = K ∪ Ctx
```

其中：

```text
K   = Core Target Set
Ctx = Context Set
```

Evidence Working Set 只决定哪些 Stable Gaussian IDs 接收 P/N/V 写入。

不在 W 中但位于 R_v 的 Gaussian：

```text
仍参与遮挡与 transmittance
但不写入当前目标 Evidence buffer
```

禁止只 rasterize W，若这样会移除遮挡 Gaussian 或改变 `T`。

---

# 18. Per-view Gaussian Evidence Artifact

```ts
interface GaussianEvidenceArtifact {
  schemaVersion: number;

  targetContextId: string;
  targetDependencyToken: string;
  sceneVersion: string;
  splatVersion: string;

  viewId: string;
  cameraBindingDigest: string;
  rgbDigest: string;
  stableMaskDigest: string;
  evidencePolicyDigest: string;

  renderWorkingSetToken: string;
  evidenceWorkingSetToken: string;

  stableGaussianIds: Uint32Array;

  positiveMass: Float32Array;
  negativeMass: Float32Array;
  visibleMass: Float32Array;

  boundaryMass?: Float32Array;
}
```

以下变化必须使对应 artifact stale：

- Target / Scene / Splat dependency；
- CameraBinding；
- authoritative RGB；
- Stable Mask；
- Evidence Policy；
- Render Working Set；
- Evidence Working Set；
- Stable Gaussian ID mapping；
- raster/evidence kernel policy。

per-view artifact 必须支持：

- 单 View Exclude；
- Stable Mask 替换；
- incremental Re-Lift；
- cross-view consistency；
- 原子 Candidate replacement；
- 失败时保留旧 Candidate。

---

# 19. Reference / Debug Contributor Backend

完整逐像素 Contributor 可以保留为：

```text
debug / reference backend
```

用途：

- Direct Evidence 数学对照；
- regression fixture；
- failing pixel / Stable ID attribution 诊断；
- rasterizer 升级验证；
- 局部 provenance 检查。

它不是：

- View Render Ready 条件；
- Anchor Confirm binding；
- 正式 Lift 必需 artifact；
- Camera Inspection 正常关键路径；
- nearest/top-k 降级入口。

Reference Contributor 失败不得让已成功 RGB 变为 View Render Failed。

---

# 20. Multi-view Evidence Aggregation

必须先保存 per-view raw P/N/V，再跨 View 聚合。

基础聚合：

\[
P_g=\sum_vP_{v,g},\quad
N_g=\sum_vN_{v,g},\quad
V_g=\sum_vV_{v,g}
\]

可以按 View 计算 ownership：

\[
q_{v,g}=\frac{P_{v,g}}{P_{v,g}+N_{v,g}+\epsilon}
\]

并结合：

- effective evidence；
- visible mass；
- supporting view count；
- conflicting view count；
- cross-view variance；
- boundary mass ratio；
- screen-space footprint；
- direction diversity。

聚合和分类必须由 versioned Evidence Policy 完成，不得固化在 CUDA kernel 中。

---

# 21. Lifting 内部四态

```text
Selected
Uncertain
Rejected
Out of Scope
```

建议映射：

```text
strong consistent target evidence     → Selected
strong consistent local-negative      → Rejected
mixed target/background               → Uncertain(mixed-or-boundary)
insufficient visible evidence          → Uncertain(unobserved-or-insufficient)
outside Evidence Working Set / policy  → Out of Scope
```

默认：

```text
Candidate C = Selected
Diagnostic U = Uncertain
```

Uncertain 不进入 Native Candidate operation。

未观察到的 Gaussian 不得自动归类为 Rejected。

---

# 22. Observation Coverage

禁止使用：

```text
observed Gaussian count
/
whole scene Gaussian count
```

作为产品 Coverage。

Observation Coverage 必须基于 Core Target Set 的有效 Visible Evidence，例如：

- 具有足够 `V` 的 Core Gaussian 比例；
- 被多个 Included Views 有效观察的 target mass；
- 方向覆盖与可见证据的组合。

不是：

```text
inside camera frustum
```

Context Gaussian 不直接拉低 Target Observation Coverage。

若：

```text
V_g < minimumVisibleEvidence
```

则保持：

```text
Uncertain(reason=unobserved-or-insufficient)
```

AI Select v1.1 不承诺恢复从未有效观察到的底面、背面、贴墙面、内部结构或严重遮挡区域的物理对象所有权。

---

# 23. Lift Readiness

Lift Readiness 继续使用：

```text
Not Ready
Limited
Ready
```

Readiness 可以使用低成本 support/visibility diagnostics，不要求在用户点击 Lift 前预先生成全部正式 per-view Evidence Artifact。

## Not Ready

Hard gate 不满足，例如：

- Anchor 未 Confirm；
- usable Included Views 不足；
- Stable Mask / RGB binding 不完整；
- Stable Gaussian ID / Render Working Set 无法建立；
- 视角严重重复。

## Limited

Hard gate 满足，但 observation/diversity 较弱。Lift enabled + warning。

## Ready

满足当前 policy，正常 Lift。

阈值属于 versioned policy，必须 benchmark 校准，不是产品常量。

---

# 24. Explicit Recompute Policy

总原则继续保持：

> **局部、即时、低成本反馈自动执行；跨 View 或影响 3D Candidate 的派生计算显式触发。**

## 24.1 Dirty State

```ts
interface AIComputeDirtyState {
  propagationDirty: boolean;
  evidenceDirtyViewIds: string[];
  liftDirty: boolean;
  candidateStale: boolean;
  contextSuspended: boolean;
}
```

可从版本依赖推导。

## 24.2 操作依赖

| 操作 | Propagation | Per-view Evidence | Lift |
|---|---|---|---|
| 编辑 Editing Mask，未 Confirm | 不变 | 不变 | 不变 |
| Confirm 普通 View Stable Mask | 不变 | 对应 View Dirty | Dirty |
| Confirm Anchor / Reference Mask | Dirty | Anchor Dirty | Dirty |
| Exclude Included View | 不变 | artifact 可保留 | Dirty |
| Include 有 Stable Mask 的 View | 不变 | 缺失/旧 artifact Dirty | Dirty |
| Add View，无 Stable Mask | 不变 | 不变 | 不变 |
| 新 View Stable Mask + Included | 不变 | 对应 View Dirty | Dirty |
| CameraBinding / RGB 新 revision | 依赖策略 | 对应 View Dirty | Dirty |
| Gallery / Frustum 浏览 | 不变 | 不变 | 不变 |

## 24.3 Update 3D Candidate

一次显式 Lift attempt：

```text
1. Resolve exact Included Stable View Annotation set
2. Reuse matching per-view Evidence Artifacts
3. Recompute missing/stale per-view P/N/V
4. Aggregate multi-view Evidence
5. Classify four states
6. Publish Candidate + Uncertain atomically
```

任何阶段失败：

- 不发布 partial Candidate；
- 保留 Views / Stable Masks / Gallery；
- 保留上一个可检查 Candidate；
- 上一个 Candidate 继续 stale 且不可应用。

---

# 25. Candidate 与 Native Selection

v1.0 的 Candidate lifecycle、Candidate Stale、Candidate Applied、Set/Add/Remove/Intersect、Native Undo/Redo、Undo-and-Fix、Restart Current Target 与 continuous multi-object rules 继续有效。

设：

```text
S = current Native Selection
C = current valid AI Candidate
```

```text
Set        S' = C
Add        S' = S ∪ C
Remove     S' = S - C
Intersect  S' = S ∩ C
```

Operation 是立即执行的 Native action，不是 preview mode。

---

# 26. ViewAssessmentPolicy

Review Reason 继续必须 evidence-backed。

允许的数据来源更新为：

```text
Mask geometry
Propagation metadata
Mask-Conditioned Gaussian Evidence / Visibility
Cross-view Gaussian Evidence
```

不得要求完整 Contributor 才能产生普通 Review Reason。

P0：

```text
target-at-boundary
fragmented-mask
weak-gaussian-support
propagation-uncertain
```

P1：

```text
cross-view-inconsistency
low-visible-support
```

普通 UI 不显示未校准的统一 `Confidence XX%`。

---

# 27. Adaptive View Planner

Planner 继续基于：

```text
Observation Coverage
View Diversity
Marginal Observation Gain
Directional Gain
```

而不是固定 View Count 或 whole-scene Gaussian denominator。

Generated View RGB 可以渐进发布，Mask 与 Evidence 均允许稍后产生。

```text
View RGB Ready
Mask Pending / None
Evidence Not Requested
```

是合法状态。

---

# 28. Failure 与 Recovery

## 28.1 Preview / RGB Render Failure

- 当前 View 为 Render Failed；
- last valid preview 可保留但标记 stale/not-current；
- 提供真实新 attempt Retry；
- 不允许旧 RGB 冒充当前 CameraBinding。

## 28.2 Evidence Failure

```text
View Render Status = Ready
Evidence Status = Failed
```

保留：

- RGB；
- View；
- Stable Mask；
- Gallery；
- 上一个 Candidate。

提供：

```text
[重试更新 3D Candidate]
[检查 Mask]
[排除此 View]
[调整/添加视角]
```

## 28.3 Mask Failure

保留 View，允许 Retry Auto Mask / Manual Draw / Exclude。

## 28.4 Lift Failure

保留所有稳定输入和上一个 Candidate；不发布替代 Candidate。

## 28.5 Reference Contributor Failure

只影响 debug/reference 诊断，不阻塞正常 RGB Preview，也不自动否定成功的 Direct Evidence Lift。

## 28.6 OOM / Cancellation

不得发布 partial Evidence 或 partial Candidate。

旧有效 artifact 继续保留。晚到结果必须按 AIRequestBinding 和 artifact identity 丢弃。

---

# 29. Scene Mutation、Suspended 与 Undo

v1.0 规则继续有效：

- Native Selection-only 与 UI-only 变化不 invalid Candidate；
- 实际 render/geometry/identity dependency mutation → Suspended；
- Suspended 保留 Anchor / Views / Masks / Evidence / Candidate，但只读；
- exact Undo 恢复相同 semantic dependency token 后可自动恢复；
- v1.1 不做跨 dependency partial artifact repair。

Target dependency mutation 必须使相关 Evidence Artifact 与 Candidate 不可应用。

---

# 30. Implementation Staging

## Stage 1 — Reference Evidence PoC

使用 stock gsplat autograd、feature rendering 或其他独立 reference 方法验证：

- P/N/V 是否足够完成对象选择；
- Mask 三带/四带策略；
- multi-view aggregation；
- mixed/boundary 分类；
- unobserved 语义；
- per-view artifact 生命周期；
- exclude/reinclude 与 incremental Re-Lift。

该阶段允许较慢，不是最终生产 trust boundary。

## Stage 2 — Policy Calibration

验证：

- Gaussian-level precision / recall；
- novel-view rendered-mask IoU；
- background contamination；
- Mixed 比例；
- 用户 Add/Remove 数量；
- 单视图 vs 多视图收益；
- threshold 附近稳定性。

## Stage 3 — Same-decision Direct Evidence

实现 locked production path，使 RGB 与 Evidence 共享权威 decision source。

首选：

- project-owned pinned CUDA extension；或
- controlled pinned gsplat fork。

## Stage 4 — Performance / Reliability

验证：

- reference-vs-production Evidence；
- VRAM；
- latency；
- atomic contention；
- repeated-run classification stability；
- spatial Render Working Set parity；
- OOM / cancellation；
- atomic publication。

## Stage 5 — Debug Contributor Retention

完整 Contributor 保留为 reference/debug backend，不进入普通产品关键路径。

---

# 31. 工程与 Benchmark 项目

必须验证：

1. CameraBinding 坐标与 revision；
2. true render-attempt Retry；
3. Render Working Set 与 full-scene parity；
4. Evidence Working Set 与 Stable ID mapping；
5. positive / boundary / local-negative mask policy；
6. P/N/V reference PoC；
7. Direct Evidence vs complete Contributor reference；
8. multi-view ownership / consistency；
9. mixed / unobserved classification margin；
10. atomicAdd contention 与 repeatability；
11. Evidence artifact cache / GC；
12. Candidate atomic publication；
13. OOM / cancellation；
14. ViewAssessment threshold；
15. Observation Coverage / Lift Readiness；
16. Suspended Context late-result rejection。

---

# 32. 核心验收标准

## Renderer

- 所有 AI RGB 来自 gsplat；
- Frustum 与 gsplat 使用同一 CameraBinding；
- stale preview response 不覆盖新 revision；
- Retry 真正重跑；
- RGB Ready 不依赖 Contributor / Evidence Ready。

## Evidence

- 正式 Lift 使用 per-view P/N/V；
- P/N/V 使用实际 `alpha × transmittance`；
- Direct Evidence 与 RGB 共享 decision source；
- 完整 Contributor 仅 debug/reference；
- 不允许 nearest/top-k/distance fallback；
- Render Working Set 保持完整遮挡；
- Evidence Working Set 只限制 Evidence 写入；
- Stable Mask / Camera / Policy / Working Set变化正确 invalidate；
- Evidence failure 不改变 View Render Ready；
- atomic 末位差异不得改变最终分类。

## Anchor

- Confirm Anchor 不要求完整 Contributor；
- Hard Validation 检查 binding、Mask、support 与 computability；
- Soft Warning 不默认阻塞；
- Restart 始终可用。

## Lifting

- Included Stable View Annotations 是正式输入；
- Excluded / no Stable Mask 不贡献；
- unobserved 不自动 Rejected；
- mixed/boundary 进入 Uncertain；
- Candidate / Uncertain 分离；
- failed Lift 不破坏上一 Candidate；
- Re-Lift 显式触发。

## Native Selection

- Candidate 不直接修改 Native Selection；
- Set/Add/Remove/Intersect 进入 Native EditHistory；
- stale Candidate 不可应用；
- AI Select 操作后保持 Active。

---

# 33. 最终状态机

```text
AI Select Active
      ↓
Current Target Context created
      ↓
Current Scene View → Anchor
      │
      ├── Adjust Anchor
      │      ↓
      │ Camera Inspection
      │
      ↓
authoritative gsplat Anchor RGB
      ↓
Editing Anchor Mask
      ↓
Anchor Validation
      │
      ├── Invalid → Fix Mask / Adjust Anchor / Restart Target
      └── Valid / Warning
              ↓
        Confirm Anchor
              ↓
        Stable Anchor
              ↓
      Adaptive View Planner
              │
              ├── Stop Generation
              ├── Generate More
              └── Add User View
              ↓
            Gallery
              │
              ├── Auto Good → Included
              ├── Review → Excluded by default
              ├── Correct / Manual Mask
              └── Exclude
              ↓
     Included Stable View Annotations
              ↓
        Lift Readiness
              ↓
       Lift / Update Candidate
              ↓
 resolve/reuse per-view P/N/V Evidence
              ↓
 recompute stale/missing Evidence
              ↓
 aggregate + classify atomically
              ↓
       Candidate + Uncertain
              │
              ├── Correct AI Result
              │      ↓
              │ View / Mask / Participation change
              │      ↓
              │ Candidate Stale
              │      ↓
              │ Update 3D Candidate
              │
              ├── Set
              ├── Add
              ├── Remove
              └── Intersect
                     ↓
             Native Selection
                     ↓
             Candidate Applied

Any target dependency mutation
      ↓
Current Target Context Suspended
      │
      ├── exact Undo restores dependency token
      │      ↓
      │ previous AI state restored
      │
      └── Restart Current Target
```

---

# 34. v1.0 → v1.1 兼容性摘要

```text
v1.0 production representation:
RGB + complete per-pixel Contributor
→ aggregate Evidence

v1.1 production representation:
RGB
→ Stable Mask
→ direct per-Gaussian P/N/V Evidence
```

迁移期间：

- v1.0 已实现的完整 Contributor 路径保留为 debug/reference；
- 已关闭 ticket 的历史验收不因表示迁移而重写；
- 新 implementation、issue、traceability 与 audit 以 v1.1 和 ADR 0013 为准；
- reference PoC 和 production gate 通过前不得删除 Contributor fixtures/backend；
- 正式 Candidate publication 始终 fail-closed 且 atomic。
