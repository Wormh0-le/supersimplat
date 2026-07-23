# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v1.0

**文档状态：** Final Spec / Baseline v1.0  
**目标：** 作为当前版本 AI Select 的产品、交互、状态机、数据边界与工程实现基线。  
**适用对象：** Product / UX / Visual / Frontend / Companion / Algorithm / QA
**版本：** v1.0  
**日期：** 2026-07-21  
**基线来源：** Final Preview v5 + DG-11~DG-19 walkthrough decisions（DG-14 deferred）

**核心模型：**

```text
Camera View
    ↓
gsplat RGB / Contributor
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Gaussian Lifting
    ↓
AI Candidate
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

---

# 0. 文档定位

这是一份 **Final Spec v1.0**，作为当前版本的规范基线。除非后续形成新的已批准 Decision Gate 或版本修订，本规格中的 MUST / SHALL / 不得 / 必须均视为当前版本的约束。

当前已关闭并纳入：

```text
DG-01  AI Select Tool Model
DG-02  Authoritative AI Renderer
DG-04  Observation Coverage & Lift Readiness
DG-05  Anchor Initial Pose & Camera Inspection
DG-06  Review View Participation
DG-07  Post-Selection Lifecycle
DG-08  View / Mask Decoupling & User-added Views
DG-09  Independent Mask Authoring & Versioning
DG-10  Explicit Recompute Policy
DG-11  Current Target Restart & Anchor Failure Recovery
DG-12  Anchor Validation & Confirm Gate
DG-13  Adaptive View Budget & User Control
DG-15  Candidate Correction Loop
DG-16  Multi-target Context Lifecycle
DG-17  Scene Mutation Invalidation & Undo Recovery
DG-18  Scalable View Gallery
DG-19  Review Reason & Quality Explanation
```

状态：

```text
DG-03  RETIRED
DG-14  DEFERRED → Next Version
```

`DG-03` 的原始问题由 `Candidate Construction + Uncertain Overlay` 模型取代。

`DG-14 Candidate Provenance & Source Inspection` 不进入 v1.0；当前版本仅保留 stale 判断、异步一致性和原子发布所需的最小版本绑定，不提供 Candidate Source Inspection、Gaussian Evidence Inspector 或 Candidate History Browser。

本规格面向 Product / UX / Visual / Frontend / Companion / Algorithm / QA，并作为实现、验收和测试用例设计的共同依据。

---

# 1. 一句话产品定义

> **AI Select 是 SuperSplat 的一种 3D Gaussian Selection Tool：用户以当前场景视角作为默认 AI Anchor，在需要时通过 3D Camera Frustum 调整或补充观察视角，在底部 AI View Dock 中查看 gsplat 渲染并独立生成、修正或手工绘制 2D Mask，系统基于 Included Stable Views 将多视图 Mask Lift 为 Gaussian Candidate，最后通过原生的设置、添加、移除、相交应用到当前 Gaussian Selection。**

---

# 2. 产品原则

## 2.1 AI Select 是 Selection Tool，不是 Workspace

AI Select 与 Picker、Lasso、Polygon、Brush、Flood、Sphere、Box 处于同一级。

AI Select 不创建独立 Workspace。

它复用：

- SuperSplat Scene Manager；
- 3D Viewport；
- Bottom Toolbar；
- Native Selection；
- Native EditHistory；
- Native Undo / Redo；
- Delete / Lock / Separate / Duplicate / Transform / Export。

## 2.2 AI Select 的 Selection Primitive

```text
Sphere Select
    ↓
Sphere Volume
    ↓
Gaussian Candidate

Box Select
    ↓
Box Volume
    ↓
Gaussian Candidate

AI Select
    ↓
Camera Views
+
2D Masks
+
Gaussian Lifting
    ↓
Gaussian Candidate
```

Candidate 产生后统一使用：

```text
Set / Add / Remove / Intersect
```

中文：

```text
设置 / 添加 / 移除 / 相交
```

## 2.3 3D 与 2D 操作区域严格分开

### Main Viewport

只负责：

- 3D 场景观察；
- Camera Frustum；
- Camera Inspection；
- Frustum 操作；
- Candidate Overlay；
- Uncertain Overlay；
- Native Selection。

### AI View Dock

只负责：

- gsplat RGB；
- View Gallery；
- 2D Mask；
- SAM Prompt；
- Brush；
- Mask Version；
- View / Mask 状态；
- Lift Readiness；
- 更新多视图 Mask；
- 更新 3D Candidate。

主 Viewport 不进入固定二维 Mask 编辑模式。

---

# 3. 权威渲染职责

## 3.1 SuperSplat / PlayCanvas

负责：

```text
Interactive Editor Rendering
Scene Visualization
Viewport Camera
Frustum Visualization
Frustum Picking
Frustum Manipulation
Candidate Visualization
Native Selection Visualization
```

## 3.2 gsplat

负责全部 AI Observation Rendering：

```text
Anchor Preview RGB
Anchor Final RGB
Generated View RGB
User-added View RGB
Contributor
Depth / Auxiliary Buffers（需要时）
```

即：

```text
PlayCanvas = Editor Renderer
gsplat     = AI Observation Renderer
```

## 3.3 Correctness Invariant

AI pipeline 的：

```text
RGB
Mask
Contributor
Depth
```

必须绑定相同版本的：

```text
CameraBinding
```

3D Frustum 必须由同一个 CameraBinding 派生。

---

# 4. 核心领域模型

## 4.1 AITarget

AI Select 默认只操作当前 Active Splat。

```ts
interface AITarget {
  splatId: string;
  sceneVersion: string;
  splatVersion: string;
}
```

Active Splat 或目标数据版本改变后，当前 AI 结果标记 stale / invalid。

## 4.2 CameraBinding

CameraBinding 是 3D Frustum 与 gsplat Rasterization 的共享真值。

```ts
interface CameraBinding {
  cameraToWorld: Matrix4;

  projection: {
    model: 'pinhole';
    fx: number;
    fy: number;
    cx: number;
    cy: number;
    width: number;
    height: number;
    near: number;
    far: number;
  };

  conventionVersion: string;
}
```

实际工程可使用等价参数化，但必须唯一确定 pose、intrinsics、resolution、clipping 和 camera convention。


## 4.3 CurrentTargetContext

当前版本同一时刻只允许一个用户可见的 Current Target Context。

```ts
interface CurrentTargetContext {
  targetContextId: string;
  revision: number;

  target: AITarget;
  anchorViewId?: string;
  viewIds: string[];
  candidateId?: string;
}
```

Current Target Context 包含：

```text
Anchor
Generated Views
User-added Views
Mask Versions
Participation
Coverage / Readiness
Candidate
Uncertain
```

这些状态全部 target-local；`重新选择对象` 后旧 Context 被 dispose。

跨目标允许复用的只是 Runtime Context：

```text
loaded models
scene tensors
gsplat renderer cache
Contributor cache
Stable Gaussian ID mapping
Companion connection
Planner / Policy settings
```

Runtime cache reuse 不等于 AI View Context inheritance。

## 4.4 TargetDependencyToken

AI Context MUST 绑定能够表示当前目标实际 AI render / lifting dependency 的语义 Token。

```ts
interface TargetDependencyToken {
  splatId: string;
  renderStateToken: string;
  geometryToken: string;
  gaussianIdentityToken: string;
  worldTransformToken: string;
}
```

实现不要求对全部 Gaussian 实时做内容 Hash；可以使用编辑器维护的 immutable semantic revision token。关键要求是：

```text
State A → Edit → Undo → State A
```

恢复后必须能够重新得到与 State A 等价的 dependency token，使 Suspended AI Context 可以安全恢复。

## 4.5 AIRequestBinding

所有异步 AI 请求和结果至少绑定：

```ts
interface AIRequestBinding {
  targetContextId: string;
  contextRevision: number;
  dependencyToken: string;
}
```

任一绑定与当前 Context 不一致，结果 MUST discard，不得依赖 cancellation 一定成功。

---

# 5. AI View 与 Mask 解耦

一个 View 不是 `Camera + RGB + Mask` 的不可拆对象。

正式模型：

```text
AI View
├── CameraBinding
├── gsplat RGB
├── Contributor
├── View Source
├── Render Status
├── Participation
└── Mask Versions
```

因此允许：

```text
View Ready
Mask = None
```

## 5.1 AIView

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

  contributorArtifact?: string;
  contributorVersion?: string;

  participation:
    | 'included'
    | 'excluded';

  stableMaskId?: string;
  editingMaskId?: string;
}
```

## 5.2 View Failure 与 Mask Failure 分离

View Failure：

```text
Camera invalid
gsplat render failed
RGB unavailable
Contributor unavailable when required
```

以下不是 View Failure：

```text
SAM failed
Mask tracking failed
Mask quality = Review
Mask = None
```

---

# 6. Mask 是独立、版本化 Annotation

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

## 6.1 Stable Mask

`stableMaskId` 表示当前允许用于：

- Lifting；
- Observation Coverage；
- Participation；

的稳定版本。

## 6.2 Editing Mask

`editingMaskId` 表示用户或算法正在编辑/生成的新版本。

它不会在未发布前破坏 stableMask。

## 6.3 Atomic Publish

```text
Stable Mask v3
      ↓
Edit
      ↓
Editing Mask v4
      ↓
Confirm Mask
      ↓
stableMaskId = v4
```

Confirm 前 Lift 仍使用 v3；Confirm 后 v4 原子替换 v3。

---

# 7. AI Select 激活：Current View First

AI Select 激活时：

```text
Anchor CameraBinding
←
Current Editor CameraBinding
```

系统不得自动移动 Editor Camera。

同时自动打开：

```text
AI 视图 Dock
```

并请求当前 Anchor 的 gsplat Preview。

---

# 8. Editor Camera、Anchor Camera、Anchor Frustum

必须区分：

```text
Editor Camera
= 用户浏览主 3D Viewport 的相机

Anchor Camera
= AI pipeline 使用的 CameraBinding

Anchor Frustum
= Anchor Camera 在 3D Viewport 中的可视化和操纵实体
```

因此：

```text
Anchor Camera exists
≠
Anchor Frustum must currently be visible
```

---

# 9. AI Select 激活后的默认 UI

## Main Viewport

保持原来的 Scene View。

```text
AI Select
Anchor: Current View

[调整 Anchor]
```

Anchor 与当前 Editor Camera 初始重合，因此不强迫用户立即看到/操作 Frustum。

## AI View Dock

立即显示：

```text
Anchor · Current View

gsplat Preview

Mask: None
```

用户通常可以直接开始 Prompt。

---

# 10. 最短 Anchor 路径

```text
用户先在场景中找到对象
      ↓
点击 AI Select
      ↓
Current View 成为 Anchor
      ↓
Dock 显示 gsplat Preview
      ↓
Include / Box Prompt
      ↓
SAM Mask
      ↓
修正
      ↓
Confirm Anchor
```

这个路径不要求用户先摆放 Frustum。

---

# 11. Camera Inspection

当当前 Anchor 视角不理想时，用户显式：

```text
[调整 Anchor]
```

进入：

```text
Camera Inspection
```

## 11.1 进入 Inspection

系统：

```text
1. 保存当前 Editor Camera Pose
2. Anchor Camera 保持不动
3. Editor Camera 移到外部观察位置
4. 显示 Anchor Frustum
5. 显示 Frustum Manipulator
```

## 11.2 Inspection 中

用户可以：

```text
Translate Anchor Frustum
Rotate Anchor Frustum
```

拖动期间只更新 Anchor CameraBinding；操作结束后，Dock 左侧显示该固定 CameraBinding 的 gsplat Final RGB。

## 11.3 返回场景视图

```text
[返回场景视图]
```

只恢复 Editor Camera。

Anchor Camera 保持用户修改后的 CameraBinding。

## 11.4 重置 Anchor

```text
[重置 Anchor 到初始视角]
```

作用于 Anchor Camera，与返回场景视图不同。

---

# 12. Final Anchor Preview

Frustum Manipulation：

```text
CameraBinding revision N
      ↓
Manipulation End
      ↓
gsplat Final RGB Request
```

Dragging 期间不发起 gsplat RGB 请求。

Final 请求必须绑定固定的 CameraBinding revision；旧响应晚到时丢弃。

## 12.1 Dragging

只更新 Anchor CameraBinding 和 3D Frustum，不更新 Dock RGB。

## 12.2 Manipulation End

请求一次 final-resolution RGB。

正式 Inference View 必须使用固定 CameraBinding。

---

# 13. Anchor Mask 编辑

第一个 Prompt 前：

```text
Anchor Camera editable
```

产生第一个 Mask Prompt 后：

```text
Anchor Camera temporarily locked
```

因为 Prompt pixel coordinates 和 Editing Mask 已绑定当前 RGB。

已有 Mask Draft 时点击：

```text
[更改 Anchor 视角]
```

提示：

```text
更改 Anchor 视角将丢弃当前 Prompt 和 Editing Mask。

[取消]
[丢弃并调整]
```

---

# 14. 2D Mask Editor

全部位于 AI View Dock。

支持：

```text
Pan / Zoom

Include Point
Exclude Point
Box Prompt

Brush Add
Brush Erase

Undo
Redo

Clear Mask
Restore Auto Mask

Confirm Mask
```

---

# 15. Clear Mask 与 Restore Auto Mask

两者语义严格分开。

## Clear Mask

```text
editingMask
→ Empty
```

用于从零开始手画。

## Restore Auto Mask

恢复最近可用：

```text
SAM / propagated auto mask
```

如果从未存在 Auto Mask：

```text
Restore Auto
→ disabled
```

---

# 16. 完全手工 Mask

合法流程：

```text
Clear Mask
      ↓
Brush Add
      ↓
Brush Erase
      ↓
Confirm Mask
      ↓
User Confirmed Stable Mask
```

完全手工 Mask 与自动 Mask 在 Lifting 中具有同等合法性。

---

# 17. Mask Prompt 与 Brush 的反馈

以下局部反馈自动执行：

```text
Include / Exclude Prompt
→ single-frame SAM update

Brush Stroke
→ editing mask update
```

不需要额外 `Apply Mask Edit`。

只有：

```text
Confirm Mask
```

才发布 stableMask。

---

# 18. Confirm Anchor

Anchor 必须具有：

```text
Confirmed Stable Mask
+
Included Participation
+
Valid Camera/RGB/Contributor Binding
```

## 18.1 Anchor Validation

当前版本不提供 `Anchor Readiness 87%`、Poor/Good/Excellent 等综合质量评分。

系统自动维护：

```text
Anchor Validation
├── Invalid
├── Valid with Warning
└── Valid
```

### Hard Validation

以下情况 MUST 阻塞 `确认 Anchor`：

- final gsplat RGB 不可用；
- Mask 为空或低于最小有效面积；
- Mask 没有有效 Gaussian contributor support；
- Mask / RGB digest / CameraBinding 版本不匹配；
- 最新 Mask/SAM revision 尚在计算；
- CameraBinding 已失效。

Hard Validation 失败时必须显示可行动原因，例如：

```text
× No valid Gaussian support

[修正 Mask]
[调整 Anchor]
[重新选择对象]
```

### Soft Warning

以下风险不得自动宣称目标错误，也不得默认阻塞 Confirm：

```text
Target touches image boundary
Very small target
Highly fragmented mask
Weak visible support
Other evidence-backed warning
```

UI 示例：

```text
⚠ Target may be partially outside the view

[调整 Anchor]
[确认 Anchor]
```

### Validation Authority

Anchor Validation 只验证：

```text
computability
binding correctness
obvious observation risk
```

它不验证“用户想选的是整把椅子还是椅子坐垫”这类最终语义。

用户点击：

```text
[确认 Anchor]
```

即完成目标语义确认。

## 18.2 Publish

Confirm Anchor 后原子发布并绑定：

```text
Anchor CameraBinding
Anchor RGB Digest
Anchor Stable Mask
Anchor Contributor Binding
Target Dependency Token
Scene/Splat Version
```

Anchor 随后锁定。

---

# 19. 初始 Auto Complete

`确认 Anchor` 是一次显式触发。

确认后允许自动启动：

```text
Adaptive View Planning
      ↓
Generated Cameras
      ↓
gsplat Rendering
      ↓
Initial Mask Propagation
      ↓
View Assessment
```

当前版本不要求用户在 Confirm 前指定固定 View 数量，也不在主流程强制选择 Fast / Balanced / High Quality。

默认 Planner 使用策略预算：

```text
minAutoViews
maxAutoViews
targetObservation
targetDiversity
marginalGainThreshold
lowGainPatience
```

`maxAutoViews` 是安全上限，不是目标生成数量。

---

# 20. Generated View 渐进发布

View 与 Mask 渐进发布：

```text
View 03
Pending

↓

View 03
RGB Ready
Generating Mask...

↓

View 03
RGB Ready
Mask Auto Good
```

或：

```text
View 05
RGB Ready
Mask Failed
```

Gallery 不必等待 Mask 完成才显示 View。

## 20.1 Adaptive Generation Control

自动 Planner 正在运行时 MUST 提供：

```text
[停止生成]
```

停止只取消 pending / future jobs；已完成 View、RGB、Stable Mask、Review 状态全部保留，并立即重新计算 Lift Readiness。

Planner 停止后根据当前状态允许：

```text
[生成更多视图]
```

其语义是 incremental planning：基于当前 Observation Gap 和 Directional Gap 增量补充 Camera，不推翻已有 View。

与之严格区分：

```text
生成更多视图 = AI chooses camera
添加视图     = user chooses camera
```

`Regenerate Auto Views` 是低频 destructive action：替换 planner-owned auto-generated views，但保留 user-added views；默认置于 Overflow / Advanced。

---

# 21. Generated Frustums

每个 Generated View 对应一个 3D Frustum。

MVP：

```text
selectable
not pose-editable
```

---

# 22. Gallery ↔ Frustum 双向同步

点击 Gallery Card：

```text
selectedViewId = card.viewId
```

Dock 左侧显示对应 RGB + Mask，3D 对应 Frustum 高亮。

点击 3D Frustum同理反向同步。

---

# 23. 不自动改变 Editor Camera

点击 Generated View：

```text
DO NOT
→ move Editor Camera automatically
```

用户需要空间检查时：

```text
[在 3D 中查看相机]
```

进入 Camera Inspection。

---

# 24. Inspect Cameras

Generated Views 存在后提供：

```text
[查看 AI 相机]
```

进入 Camera Inspection，可查看：

- Anchor Frustum；
- Generated Frustums；
- User-added Frustums；
- Review / Failed / Excluded 的空间位置。

Generated Frustum 在 MVP 中只读。

---

# 25. 用户补充 View

AI View Gallery 支持：

```text
+ 添加视图 ▾
├── 使用当前视角
└── 调整新视角...
```

## 25.1 使用当前视角

```text
New AI View Camera
←
Current Editor CameraBinding
```

随后：

```text
gsplat Render
→ View appears in Gallery
```

## 25.2 调整新视角

进入 Camera Inspection：

```text
create User-added Frustum
→ Translate / Rotate
→ Live gsplat Preview
→ Confirm View
```

---

# 26. User-added View 默认不强制生成 Mask

View Ready 后允许：

```text
No Mask
```

Dock：

```text
[自动生成 Mask]
[手工绘制]
[排除此 View]
```

---

# 27. 自动生成 Mask

产品入口统一：

```text
[自动生成 Mask]
```

内部允许：

- propagation；
- single-frame SAM；
- fallback strategy。

技术策略不必强制暴露给普通用户。

---

# 28. 手工绘制 Mask

```text
[手工绘制]
```

内部：

```text
create empty Editing Mask
activate Brush Add
```

完成后：

```text
Confirm Mask
```

成为 User Confirmed Stable Mask。

---

# 29. View Source 不决定可信度

以下后续行为一致：

```text
auto-generated view
user-added view
replacement view
```

是否参与 Lift 只由：

```text
Render Ready
Stable Mask
Participation
```

决定。

---

# 30. Mask Quality 与 Lift Participation 分离

## Mask Quality

```text
User Confirmed
Auto Good
Auto Review
Failed / None
```

## Lift Participation

```text
Included
Excluded
```

Mask Quality / Assessment 与 Participation 是两个独立维度。

---

# 31. 默认 Participation

| View / Stable Mask | Default |
|---|---|
| Anchor / User Confirmed | Included |
| Auto Good | Included |
| Auto Review only | Excluded |
| No Stable Mask | Excluded |
| Mask Failed | Excluded |
| Render Failed | Excluded |

用户可以手动排除 Auto Good 或 User Confirmed View。

---

# 32. Review 策略与 ViewAssessmentPolicy

Review 默认：

```text
Excluded
```

不会以低权重偷偷进入 Lift。

但：

```text
存在 Review
≠
必须阻塞 Lift
```

如果剩余 Included Views 满足 Lift Readiness，Lift allowed。

## 32.1 Review Reason 的产生位置

Review Reason 不由前端推断，也不要求 SAM 直接给出。

Companion 后端 MUST 提供独立的：

```text
ViewAssessmentPolicy
```

概念链路：

```text
SAM
→ Mask

gsplat
→ RGB / Contributor / Visibility

Mask + Contributor + Propagation Metadata + Cross-view Evidence
→ ViewAssessmentPolicy
→ Auto Good / Auto Review / Failed + ReviewReason[]
```

第一版不要求新的深度模型 inference。

## 32.2 Evidence-backed Requirement

Review Reason MUST be evidence-backed。

当前版本只允许输出能够由以下数据明确支撑的 Reason：

```text
Mask geometry
Propagation metadata
gsplat Contributor / Visibility
Cross-view Gaussian Evidence
```

无法可靠区分的原因不得猜测。

## 32.3 MVP Reason Scope

P0 / Local Assessment：

```text
target-at-boundary
fragmented-mask
weak-gaussian-support
propagation-uncertain
```

P1 / Cross-view Assessment：

```text
cross-view-inconsistency
low-visible-support
```

`identity-drift` 可以保留在未来 taxonomy 中，但在没有可靠检测能力前 v1.0 不得实际 emit。

`mask-area-outlier` 可以作为内部 diagnostics；在未做 perspective / visibility normalization 前，不建议作为独立用户可见 Reason。

## 32.4 Assessment Output

```ts
interface ViewAssessmentResult {
  status: 'good' | 'review' | 'failed';
  primaryReason?: ReviewReason;
  reasons: ReviewReason[];
  diagnostics?: {
    boundaryContactRatio?: number;
    largestComponentRatio?: number;
    gaussianSupportRatio?: number;
    crossViewPrecision?: number;
    crossViewRecall?: number;
    visibleTargetRatio?: number;
  };
  policyVersion: string;
}
```

普通 UI 不显示统一 `AI Confidence XX%`。

原始 diagnostics 可以进入 Advanced Diagnostics，但不得伪装成概率意义的单一 Confidence。

## 32.5 Reason → Recommended Action

后端返回结构化 Reason Code；前端负责本地化文案和静态 Action Mapping。

示例：

| Reason | 推荐动作 |
|---|---|
| target-at-boundary | 检查 Mask / 添加更完整视角 |
| fragmented-mask | Brush 修正 |
| weak-gaussian-support | 检查视角 / 添加新视角 |
| propagation-uncertain | 检查 Mask |
| cross-view-inconsistency | 检查/重画 Mask |
| low-visible-support | 排除 View / 添加新视角 |

用户可见解释必须可行动，不显示 entropy、feature cosine、logit margin 等算法日志。

## 32.6 User Authority

`Auto Review` 可以被用户：

```text
Confirm as-is
Prompt Refine
Brush Refine
Clear + Manual
Exclude
```

一旦用户 Confirm：

```text
User Confirmed Stable Mask
Participation = Included
```

后续自动 assessor 不得把 User Confirmed 自动降回 Auto Review 或偷偷降低 Lift 权重。

原始 assessment 可以作为内部诊断数据保留。

---

# 33. Review View 修正

用户可：

```text
Confirm as-is
Prompt Refine
Brush Refine
Clear + Manual
Exclude
```

Confirm 后：

```text
User Confirmed Stable Mask
Participation = Included
```

Review / Failed / No Mask 必须继续与 View Render Failure 分离。

---

# 34. Stable Mask 与重新编辑

已有：

```text
stableMask = v3
```

用户 Edit Mask：

```text
editingMask = v4
```

在 Confirm v4 前：

```text
v3 remains stable
```

所以现有 Candidate 不因“正在编辑”而立即 stale。

---

# 35. 新 Mask 不原地覆盖 Stable Mask

无论：

```text
manual editing
SAM regenerate
repropagate
```

都采用：

```text
Stable v3
+
Proposed/Editing v4
      ↓
success + publish
      ↓
Stable = v4
```

失败则 Stable 继续保持 v3。

---

# 36. Explicit Recompute Policy

总原则：

> **局部、即时、低成本反馈自动执行；跨 View 或影响 3D Candidate 的派生计算显式触发。**

---

# 37. 自动执行

```text
Frustum manipulation end
→ Final Anchor Preview

Prompt
→ Single-frame SAM

Brush
→ Editing Mask

Gallery / Frustum selection
→ UI synchronization

Included count
Review count
View Diversity
Observed Target
Lift Readiness
→ cheap derived state refresh
```

---

# 38. 显式执行

```text
Confirm Mask
Update Multi-view Masks
Update 3D Candidate
Set / Add / Remove / Intersect
```

以及：

```text
Regenerate Views
Reposition Anchor
Add View
```

---

# 39. Dirty / Stale / Suspended Model

```ts
interface AIComputeDirtyState {
  propagationDirty: boolean;
  liftDirty: boolean;
  candidateStale: boolean;
  contextSuspended: boolean;
}
```

允许从版本依赖推导。

语义：

```text
Dirty
= 某个派生计算需要显式更新

Candidate Stale
= Stable AI Input 已变，但底层 Target Dependency 仍兼容

Context Suspended
= 底层 AI render / geometry / identity dependency 已改变
```

`Candidate Stale` 可以通过 Re-Lift 恢复；`Context Suspended` 在 v1.0 不做局部 artifact repair，只允许 Undo 精确恢复或 Restart Target。

---

# 40. 操作依赖表

| 操作 | Propagation | Lift |
|---|---|---|
| 编辑 Editing Mask，未 Confirm | 不变 | 不变 |
| Confirm 普通 Generated/User View Mask | 不变 | Dirty |
| Confirm Anchor / Reference Mask 修改 | Dirty | Dirty |
| Exclude Included View | 不变 | Dirty |
| Include 有 Stable Mask 的 View | 不变 | Dirty |
| Add View，没有 Stable Mask | 不变 | 不变 |
| 新 View Stable Mask + Included | 不变 | Dirty |
| Gallery / Frustum 浏览 | 不变 | 不变 |

---

# 41. UI 只显示当前必要的下一步

```text
Editing Mask
→ [确认 Mask]

Propagation Stale
→ [更新多视图 Mask]

Candidate Stale
→ [更新 3D Candidate]

Candidate Ready
→ [设置] [添加] [移除] [相交]
```

不要求用户自己判断“该 Repropagate 还是 Re-Lift”。

---

# 42. 更新多视图 Mask

Reference / Anchor Stable Mask 改变：

```text
propagationDirty = true
```

显示：

```text
多视图 Mask 需要更新

[更新多视图 Mask]
```

不会自动 Repropagate。

---

# 43. Repropagate 后不自动 Lift

Repropagate 可能产生新的：

```text
Good
Review
Failed
```

完成后：

```text
重新计算 Participation / Readiness
→ 用户 Review
→ 显式更新 3D Candidate
```

不会：

```text
Repropagate
→ automatic Re-Lift
```

---

# 44. 更新 3D Candidate

Included Stable View/Mask Set 改变后：

```text
candidate = stale
```

显示：

```text
3D Candidate 已过期

[更新 3D Candidate]
```

点击才重新 Lift。

---

# 45. Stale Candidate 与 Suspended Context

## Candidate Stale

旧 Candidate 数据可以保留用于对比，但必须标记：

```text
Outdated
```

且：

```text
设置
添加
移除
相交
```

全部禁用。

不提供 `Apply stale candidate anyway`。

## Context Suspended

当当前目标实际 AI dependency 发生 Scene Mutation：

```text
Current Target Context
→ Suspended
```

Suspended 时：

```text
inspectable
but not editable
not liftable
not applicable
```

禁止：

```text
Mask Edit
Add View
Repropagate
Re-Lift
Set/Add/Remove/Intersect
```

主要恢复路径：

```text
Undo Scene Change
→ dependency token exact match
→ restore previous AI state
```

或：

```text
重新选择对象
→ dispose old context
→ Current View First
```

Suspend 不得立即销毁 Anchor / Views / Masks / Candidate / Gallery。

---

# 46. Gaussian Lifting Input

真正送入 Lifting：

```text
Views
WHERE
  renderStatus = ready
  AND participation = included
  AND stableMaskId exists
```

即：

```text
Included Stable View Annotations
```

---

# 47. Lifting 内部四态

内部允许：

```text
Selected
Uncertain
Rejected
Out of Scope
```

---

# 48. Candidate Construction

Native Selection Operation 不直接处理四态。

默认：

```text
C = Selected
U = Uncertain
```

其中：

```text
C = Gaussian Candidate
U = diagnostic overlay
```

---

# 49. Uncertain

Uncertain 默认：

```text
not in Candidate
```

所以：

```text
Set / Add / Remove / Intersect
```

只作用于 C。

---

# 50. Local Working Set

内部建议：

```text
W = K ∪ Ctx
```

其中：

```text
K   = Core Target Set
Ctx = Context Set
```

Core Target Set 代表有可能属于目标的 Gaussian。

Context 用于：

```text
negative evidence
boundary disambiguation
leakage detection
```

不直接拉低 Target Observation Coverage。

---

# 51. Coverage 不使用 Whole Scene

禁止：

```text
observed contributors
/
whole scene gaussian count
```

作为产品 Coverage。

---

# 52. Observation Coverage

Observation 基于：

```text
gsplat actual contributor / visibility evidence
```

而不是：

```text
inside camera frustum
```

对于 Core Gaussian，聚合 Included Views 的有效 contributor evidence。

---

# 53. View Diversity

Included View Count 不代表视角多样性。

系统单独维护：

```text
View Diversity
```

MVP：

```text
direction bins
```

后续可升级 spherical directional coverage。

---

# 54. Lift Readiness

产品层不使用孤立的：

```text
Coverage 87%
```

而显示：

```text
Included Views
View Diversity
Observed Target
Lift Readiness
```

---

# 55. Lift Readiness 状态

```text
Not Ready
Limited
Ready
```

## Not Ready

Hard Gates 不满足，例如：

- Anchor 未 Confirm；
- usable Included Views 太少；
- 视角严重重复；
- 必需 artifact 不完整。

Lift disabled。

## Limited

Hard Gates 满足，但 Observation / Diversity 较弱。

Lift enabled + warning。

## Ready

满足当前 policy，正常 Lift。

---

# 56. 阈值不是产品常量

```text
minimumIncludedViews
minimumDirectionDiversity
minimumObservationCoverage
```

作为可调策略。

初始工程值可从：

```text
minimum included views ≈ 3
minimum direction bins ≈ 3
observation target ≈ 70%
```

起步，但必须 benchmark 校准。

---

# 57. Adaptive View Planner & Early Stop

View Count 不是目标，只是计算成本。

Planner 默认基于：

```text
Observation Coverage
+
View Diversity
+
Marginal Target Observation Gain
+
Directional Gain
```

而不是：

```text
new contributors / whole scene
```

## 57.1 Policy Budget

```text
minAutoViews
maxAutoViews
targetObservation
targetDiversity
marginalGainThreshold
lowGainPatience
```

`maxAutoViews` 是硬安全预算。

## 57.2 Stop Policy

Planner SHOULD 在满足基本 usable view 数量后，依据 Coverage / Diversity 或连续低收益 early-stop。

停止依据主要看：

```text
usable / included observation
```

不能把 Review / Failed 简单算成有效 View。

达到 Auto Budget 上限必须停止，即使 Readiness 仍不足。

## 57.3 User Control

自动生成期间：

```text
[停止生成]
```

停止后可以：

```text
[生成更多视图]  → incremental AI planning
[添加视图]      → user chooses camera
```

达到预算上限后，用户显式 `生成更多视图` 相当于授权额外 batch budget。

Future 可以在 AI Select Settings 中提供 Faster / Balanced / More Coverage Policy Preset，但不属于 v1.0 主流程必需交互。

---

# 58. Lift to 3D

初次：

```text
[Lift to 3D]
```

后续 stale：

```text
[更新 3D Candidate]
```

得到：

```text
Candidate C
Uncertain U
```

---

# 59. Candidate Preview 与 Correction Loop

Candidate Ready：

```text
Native Selection
    native visualization

AI Candidate
    green overlay

Uncertain
    yellow overlay
```

Candidate 此时尚未修改 Native Selection。

## 59.1 Candidate 不直接编辑

v1.0 不支持：

```text
AI Candidate
→ 3D Brush/Lasso patch Candidate
→ merge with future Re-Lift
```

Candidate 始终是 Included Stable View Annotations 经 Lifting 得到的派生结果。

## 59.2 修正 AI 结果

Candidate Ready 提供次级动作：

```text
[修正 AI 结果]
```

它只回到现有 AI View / Mask workflow，不创建新 Workspace。

允许：

```text
Edit existing Mask
Exclude View
Fix Review View
Generate More Views
Add User View
```

只是浏览 Gallery 或创建 Editing Mask 不会立即使 Candidate stale。

只有 Stable Input 真正改变：

```text
Candidate → Stale
→ [更新 3D Candidate]
```

## 59.3 Candidate Applied 后修正

Candidate 已 Applied 后，修改 AI Source 的优先路径：

```text
[撤销并修正]
```

仅当关联 AI SelectOp 可以安全作为当前 Native Undo 顶部操作撤销时，系统可以执行复合动作：

```text
Undo Native SelectOp
→ Candidate Ready
→ Correction
```

若之后已经存在其他 Native Edit，系统不得穿越 History 自动撤销；用户必须先处理 Native History。

## 59.4 Native Selection Refinement

另一条合法路径是：

```text
Apply AI Candidate
→ switch to Brush/Lasso/Sphere/Box...
→ manually refine Native Selection
```

这些原生修正不回写 AI Candidate。

---

# 60. Selection Operation

设：

```text
S = current native selection
C = current AI candidate
```

```text
Set        S' = C
Add        S' = S ∪ C
Remove     S' = S - C
Intersect  S' = S ∩ C
```

---

# 61. Selection Operation 是 Action，不是 Mode

点击：

```text
设置 / 添加 / 移除 / 相交
```

立即执行：

```text
Native SelectOp
```

修改 Native Selection 并进入 Native EditHistory。

不存在额外：

```text
Apply
Commit Draft
```

---

# 62. Candidate Applied 后 AI Select 不退出

```text
Native Selection updated
AI Select remains active
```

保留：

```text
Anchor
Views
Frustums
Masks
Lift Result
Candidate
Uncertain
Gallery
```

---

# 63. Candidate Applied

```text
Candidate Ready
      ↓
Set/Add/Remove/Intersect
      ↓
Candidate Applied
```

记录：

```text
lastOperation
nativeHistoryCommand
```

但 Candidate 不销毁。

---

# 64. Applied 后视觉降级

Candidate Applied 后：

```text
Native Selection
→ primary visualization
```

Candidate Overlay 默认 hidden / de-emphasized。

用户可以：

```text
[显示 AI 结果]
```

重新查看 Candidate + Uncertain。

---

# 65. 再次执行 Operation

第二次 Operation 始终基于：

```text
current Native Selection
```

四个按钮不是四种 Alternative Preview。

---

# 66. 换一种 Operation

正确路径：

```text
Undo
→ choose another operation
```

---

# 67. Undo / Redo

3D Selection Operation 完全复用 Native EditHistory。

```text
Ctrl/Cmd + Z
→ Undo SelectOp
```

Candidate / Gallery / Masks 不需要重新计算。

Undo 后：

```text
Candidate Applied
→ Candidate Ready
```

Redo 反向恢复。

---

# 68. 2D Mask Undo / Redo

Mask Editor 维护独立轻量历史。

```text
Mask Editor focused
→ Undo Mask Edit

3D Viewport / normal editor focused
→ Native Undo
```

必须有明确焦点反馈。

---

# 69. 重新选择对象 / Restart Current Target

`重新选择对象` 是整个 AI Select 生命周期中的通用恢复动作，而不仅属于 Candidate Applied 阶段。

可在以下阶段使用：

```text
Anchor Draft
Generated Views
Mask Review
Propagation Stale
Candidate Stale
Candidate Ready
Candidate Applied
```

内部语义：

```text
Restart Current Target
```

清除：

```text
Anchor
AI Views
User-added Views
Mask Versions
Review State
Coverage / Readiness
Lift Result
Candidate
Uncertain
Gallery target-local state
```

保留：

```text
Native Selection
Native EditHistory
AI Select Active
Scene View
Tool/Planner Policy
Shared Runtime Cache
```

然后：

```text
New Anchor ← Current Scene View CameraBinding
```

继续 Current View First。

## 69.1 与其他动作的边界

必须严格区分：

```text
调整 Anchor
≠
重新选择对象
≠
退出 AI Select
```

## 69.2 Confirmation Policy

```text
No meaningful draft
→ no confirmation

Unconfirmed Prompt / Editing Mask
→ confirm discard

Confirmed Anchor / Views / Masks
→ confirm AI context deletion

Candidate already Applied
→ no confirmation required
```

所有确认必须明确说明：

```text
当前 Native Selection 不会改变
```

## 69.3 Camera Inspection

如果 Restart 时处于 Camera Inspection：

```text
restore saved Scene View
→ create New Anchor from Scene View
```

Inspection Observer Camera 绝不能成为新 Anchor。

## 69.4 Async Safety

Restart 会 rotate `targetContextId`。旧 Context 的异步任务即使无法取消，晚到结果也必须因 Context ID 不匹配而 discard。

---

# 70. 连续多对象与 Context Lifecycle

连续多对象：

```text
Candidate A
→ Add
→ 重新选择对象

Candidate B
→ Add
→ 重新选择对象

Candidate C
→ Add
```

Current Native Selection 由原生 Set/Add/Remove/Intersect 决定。

v1.0 不引入用户可见的 Persistent AI Session / Object Context Stack。

同一时刻只有：

```text
one Current Target Context
```

跨目标不继承：

```text
Previous Views
Masks
Candidate
Gallery position
Mask Tool editing state
Camera Inspection state
```

跨目标保留：

```text
Native Selection
Native EditHistory
AI Select Active
Scene View
Planner Policy
Shared renderer/model/scene cache
```

新的 Candidate 仍然可以执行任一原生 Operation，不因为连续选对象而偷偷进入 Add Mode。

底层 RGB / Contributor 可以按 Scene Dependency + CameraBinding 命中缓存，但属于 runtime cache reuse，不是 View Context inheritance。

Current Target Context v1.0 不要求 project persistence，也不要求重新打开前一个 AI Target。

---

# 71. 切换工具

切换到 Box / Sphere / Picker 等时结束当前 AI Candidate Context。

MVP 不要求恢复上一轮用户可见 AI Session。

允许保留底层：

```text
Scene tensor cache
Model cache
Renderer cache
```

用于性能。

---

# 72. Scene Mutation Invalidation & Undo Recovery

Selection-only 操作：

```text
Set / Add / Remove / Intersect / Native Undo / Redo
```

不会使 Candidate stale，因为 Candidate 不依赖 Current Native Selection。

Editor-only / UI-only 状态，例如普通 Camera Orbit、Gallery selection、Panel resize，同样不影响 AI Context。

只有改变当前 AI pipeline 实际 dependency 的 Scene Mutation 才触发：

```text
Current Target Context
→ Suspended
```

典型 dependency mutation：

```text
Gaussian position / rotation / scale
opacity / SH / render state when used by AI renderer
Target Splat world transform
Delete / Separate / add-remove Gaussian
Target Splat replacement
Stable Gaussian identity / membership change
```

Invalidation MUST target dependency scope，而不是“任何全局 Scene edit”。如果其他 Splat 的修改不进入当前 AI Observation Render Input，则不得粗暴 invalid 当前 Context。

## 72.1 Suspend, Do Not Destroy

Scene Mutation 后保留：

```text
Anchor
Views
Masks
Candidate
Gallery
```

进入只读 Suspended。

UI 示例：

```text
⚠ 场景已发生变化

当前 AI 结果基于修改前的 Gaussian 数据，暂时无法继续应用。

[撤销场景修改以恢复]
[重新选择对象]
```

## 72.2 Exact Undo Restore

Undo 后只有当当前 semantic dependency token 与 AI Context 原绑定 token 精确等价时，自动：

```text
Suspended
→ previous AI state
```

不能仅依据 monotonic scene revision counter。

## 72.3 No Partial Repair in v1.0

当前版本不实现：

```text
color changed → only rerender
transform changed → only contributor refresh
```

统一采用：

```text
Suspend
→ Undo to Restore
或
Restart Target
```

## 72.4 Async Result Binding

所有异步结果必须同时检查：

```text
targetContextId
+
dependencyToken
```

任一不匹配即 discard。

---

# 73. 主 UI 结构

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Menu                                                                         │
│                                                                              │
│ Scene Manager                       3D VIEWPORT             Right Toolbar     │
│                                                                              │
│                     Scene View / Camera Inspection                           │
│                                                                              │
│             Frustums / Candidate / Uncertain / Selection                     │
│                                                                              │
│                   Contextual AI Select Toolbar                               │
│                       Bottom Main Toolbar                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Timeline] [Splat Data] [AI Views]                                           │
│                                                                              │
│  Selected View + Mask Editor        Horizontal View Gallery                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# 74. Contextual AI Select Toolbar

工具栏状态驱动。

## Anchor 初始

```text
AI Select
Anchor: Current View

[调整 Anchor]

⋯
  重新选择对象
  退出 AI Select
```

## Anchor Valid / Warning

```text
✓ Ready for multi-view
[确认 Anchor]
```

或：

```text
⚠ Target may be partially outside the view
[调整 Anchor] [确认 Anchor]
```

Hard Validation 失败时 `确认 Anchor` disabled。

## Camera Inspection

```text
Camera Inspection

[移动] [旋转]
[返回场景视图]
[重置 Anchor]
```

## Generated Views

```text
Generating AI Views...
4 views ready

[停止生成]
[查看 AI 相机]
```

不得使用固定 `4 / 8` 总数表达 Adaptive Planner。

## Propagation Stale

```text
多视图 Mask 需要更新

[更新多视图 Mask]
```

## Candidate Stale

```text
3D Candidate 已过期

[更新 3D Candidate]
```

## Candidate Ready

```text
[设置] [添加] [移除] [相交]

Candidate: 126,841
[修正 AI 结果]
```

## Candidate Applied

```text
✓ 已应用：添加

[显示 AI 结果]
[重新选择对象]
[撤销并修正]   // only when safely undoable
```

## Scene Suspended

```text
⚠ 当前 AI 结果暂停

[撤销场景修改以恢复]
[重新选择对象]
```

---

# 75. AI View Dock

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ AI 视图   View 03 · Review                                      [Collapse]  │
├──────────────────────────────────┬───────────────────────────────────────────┤
│                                  │                                           │
│          CURRENT VIEW            │   Anchor | 01 | 02 | 03 | 04 | 05 →      │
│                                  │                                           │
│          RGB + MASK              │              GALLERY                      │
│                                  │                                           │
├──────────────────────────────────┼───────────────────────────────────────────┤
│ Include  Exclude  Box            │ View Status                               │
│ Brush+   Brush-   Undo  Redo     │ Mask Status                               │
│ Clear    Restore Auto            │ Participation                             │
│                       Confirm    │ Readiness / Diagnostics                   │
└──────────────────────────────────┴───────────────────────────────────────────┘
```

---

# 76. Scalable View Gallery

Gallery 保持单层横向、稳定顺序，不做独立 Workspace。

## 76.1 Card Responsibilities

Gallery Card 只承担：

```text
thumbnail
view id
primary status badge
selection / participation visual state
```

复杂信息全部进入 Selected View Detail。

三个视觉维度严格分开：

```text
Status Badge
= View / Mask quality

Opacity / desaturation
= Included / Excluded

Outline
= Current selected View
```

## 76.2 Stable Base Order

```text
Anchor first
→ auto-generated creation order
→ user-added creation order
```

状态变化不得自动重排。

v1.0 不提供 sort / manual reorder / search。

## 76.3 Summary & Filters

Gallery Header SHOULD 提供：

```text
Total Views
Included
Needs Attention
Failed
```

至少支持：

```text
All
Needs Attention
Included
Excluded
User-added
```

`Needs Attention` 包含 Review / No Mask / Mask Failed / Render Failed。

Filter 只影响显示，不改变 Participation。

非匹配 3D Frustums 默认 de-emphasized，而不是必须完全隐藏。

## 76.4 Review Queue

Needs Attention Filter 下，一个 View 修正后如果不再匹配 Filter，可以自动离开列表，并选中下一条需要处理的 View。

## 76.5 Gallery ↔ Frustum at Scale

点击 3D Frustum 后：

```text
selectedViewId = frustum.viewId
→ Gallery auto-scroll card into view
```

点击 Gallery Card 继续高亮对应 Frustum，但不得自动移动 Editor Camera。

## 76.6 Performance

Gallery 始终单行横向滚动。

大量 Views 下 SHOULD 使用：

```text
thumbnail artifacts
horizontal virtualization / lazy loading
```

Gallery Card 不保存 full-resolution interactive Mask Editor texture；真正交互式 Mask 仅存在于 Selected View。

## 76.7 Sticky Add Action

Gallery 右侧提供 Sticky：

```text
[+]
```

统一入口：

```text
生成更多视图
────────────
使用当前视角
调整新视角...
```

Planner 正在运行时 `[停止生成]` 放在 Header / Summary，不藏进 `+`。

## 76.8 No Ordinary Delete View

v1.0 不提供普通 `Delete View`。

优先使用：

```text
Exclude
```

真正移除 View Record 主要发生在 Restart Target 或 Regenerate Auto Views。

---

# 77. Frustum Visual State

| 状态 | 建议 |
|---|---|
| Anchor Confirmed | 蓝色 |
| Auto Good Included | 绿色 |
| Review Excluded | 黄色 |
| Failed | 红/灰虚线 |
| User Excluded | 灰色 |
| Current Frustum | 高亮描边 |
| Rendering | 半透明/动态 |
| User Confirmed Generated | 蓝/青 + check |

具体颜色需与 SuperSplat 原生 Selection 色做最终视觉冲突检查。

---

# 78. Candidate Visual State

```text
Candidate Ready
→ green strong overlay

Uncertain
→ yellow overlay

Candidate Stale
→ de-emphasized + outdated

Candidate Applied
→ hidden / weak by default
```

Native Selection 始终沿用原生视觉。

---

# 79. 典型流程 A：最快单对象选择

```text
1. 用户在 Scene View 找到对象
2. 点击 AI Select
3. Current View → Anchor
4. Dock 显示 gsplat Preview
5. Include 点击目标
6. SAM Mask
7. Brush/Prompt 修正
8. Confirm Anchor
9. 自动生成 Views + 初始 Masks
10. Review 默认排除
11. Readiness = Ready / Limited
12. Lift to 3D
13. Candidate Preview
14. 点击 Set
15. Native Selection 更新
16. AI Select 保持 Active
```

---

# 80. 典型流程 B：调整 Anchor

```text
1. AI Select
2. Current View Preview 不理想
3. 调整 Anchor
4. Camera Inspection
5. 拖动 / 旋转 Frustum
6. Dock Final Anchor Preview
7. 返回 Scene View（可选）
8. Prompt
9. Confirm Anchor
```

---

# 81. 典型流程 C：补一个系统没生成好的视角

```text
1. 用户发现观察不足
2. Scene View 转到更好的角度
3. + 添加视图
4. 使用当前视角
5. gsplat Render
6. 新 View 出现在 Gallery
7. 自动生成 Mask 或手工绘制
8. Confirm Mask
9. Candidate Stale
10. 更新 3D Candidate
```

---

# 82. 典型流程 D：完全重画错误 Mask

```text
1. View 04 Mask 很差
2. 选择 View 04
3. Clear Mask
4. Brush Add 从零绘制
5. Brush Erase 修边
6. Confirm Mask
7. Stable Mask 更新
8. Candidate Stale
9. 更新 3D Candidate
```

---

# 83. 典型流程 E：修改 Reference 后 Repropagate

```text
1. Edit Anchor / Reference Stable Mask
2. Confirm
3. Propagation = Stale
4. 更新多视图 Mask
5. 新 Good / Review / Failed 出现
6. 用户处理 Review
7. Lift Readiness 自动刷新
8. 更新 3D Candidate
```

---

# 84. 典型流程 F：连续选多个对象

```text
1. Candidate A
2. Add
3. 重新选择对象
4. Current View → new Anchor
5. Candidate B
6. Add
7. 重新选择对象
8. Candidate C
9. Add
```

---


# 84A. 典型流程 G：Candidate 结构性错误

```text
1. Candidate Ready
2. 用户发现明显漏选 / 多选
3. 修正 AI 结果
4. 检查 Gallery / Review / Uncertain
5. 修 Mask、Exclude View、Generate More 或 Add View
6. Confirm Stable Input Change
7. Candidate → Stale
8. 更新 3D Candidate
9. Candidate Ready
```

---

# 84B. 典型流程 H：Candidate 已应用后修正

```text
1. Candidate → Add / Set
2. 用户发现 AI Source 需要结构性修正
3. 如果关联 AI SelectOp 可安全撤销：撤销并修正
4. Native Undo
5. Candidate Ready
6. 修正 View / Mask
7. 更新 3D Candidate
```

只有很小的最终 Selection 局部错误时，可以直接切换原生 Brush/Lasso 等工具精修 Native Selection。

---

# 84C. 典型流程 I：Scene Mutation + Undo

```text
1. Candidate Ready / Applied
2. 用户 Delete / Separate / Transform 当前 AI dependency
3. AI Context → Suspended
4. Gallery / Candidate 保留但只读
5. Undo Scene Mutation
6. Dependency Token 精确恢复
7. AI Context 自动恢复到 Mutation 前状态
```

---

# 85. 错误与降级

## Companion Offline

```text
AI 服务不可用

[重连]
[设置]
```

Native SuperSplat 不受影响。

## Preview Failure

保留 last valid preview，提供重试。

## Mask Generation Failure

View 保留：

```text
[重试自动 Mask]
[手工绘制]
[排除此 View]
```

## View Render Failure

提供：

```text
[重试]
[生成替代 View]
[排除]
```

## Lifting Failure

保留 Views / Stable Masks / Gallery，Candidate 不更新。

## Repropagate Failure

保留旧 Stable Masks，不发布未完成 Proposed Mask。

---

# 86. MVP 分期

## Phase 0 — Tool Shell

- AI Select Toolbar Entry；
- Contextual Toolbar；
- AI View Dock；
- Current View Anchor；
- Camera Inspection shell；
- Frustum hit-test / manipulator；
- CurrentTargetContext / targetContextId。

## Phase 1 — gsplat Preview

- CameraBinding；
- Final Anchor Preview after manipulation；
- revision / stale-response discard；
- AIRequestBinding；
- dependency token plumbing；
- Dock Preview。

## Phase 2 — Anchor Mask & Validation

- Prompt / single-frame SAM；
- Brush；
- Clear / Restore Auto；
- Mask History；
- Stable / Editing Mask；
- Anchor Hard Validation / Soft Warning；
- Confirm Anchor；
- Restart Current Target。

## Phase 3 — Adaptive Generated Views

- Adaptive View Planner；
- Planner budget / early stop；
- Stop Generation；
- Generate More Views；
- Progressive View publication；
- Generated Frustums；
- Scalable Gallery；
- Frustum ↔ Card sync；
- Render / Mask status separation。

## Phase 4 — Review & User-added Views

- ViewAssessmentPolicy；
- evidence-backed Review Reason；
- P0 local assessment；
- P1 cross-view assessment；
- Auto Good / Review；
- Participation；
- User Confirm；
- Exclude；
- Add View using current camera；
- Add View with Camera Inspection；
- Auto Mask / Manual Mask；
- Repropagate。

## Phase 5 — Coverage & Lift

- Core Target Set / Context Set；
- Observation Coverage；
- View Diversity；
- Lift Readiness；
- Gaussian Lifting；
- Candidate / Uncertain；
- Candidate Correction Loop；
- Candidate atomic publication。

## Phase 6 — Native Selection Integration

- Set/Add/Remove/Intersect；
- Native SelectOp / Native Undo/Redo；
- Candidate Applied；
- 撤销并修正；
- Restart Current Target；
- Multi-target Context Lifecycle。

## Phase 7 — Scene Mutation Safety & Performance

- semantic TargetDependencyToken；
- Suspended / exact Undo restore；
- async stale result rejection；
- GPU evidence aggregation；
- View tensor / contributor cache；
- Working-set optimization；
- profiling / benchmark calibration；
- assessment threshold calibration。

---

# 87. 核心验收标准

## 产品模型

- AI Select 与 Sphere / Box 同级；
- 不存在独立 Workspace；
- 不存在 Draft Selection / Apply / Commit Draft；
- 同一时刻只有一个 Current Target Context；
- DG-14 Provenance UI 不进入 v1.0。

## Renderer

- 所有 AI RGB 来自 gsplat；
- Frustum 与 gsplat 使用同一 CameraBinding；
- Preview 旧请求不会覆盖最新状态；
- AI request/result 绑定 targetContextId + dependencyToken。

## Anchor

- 默认 Current View；
- 默认不自动移动 Editor Camera；
- Adjust Anchor 显式进入 Camera Inspection；
- Prompt 后 Anchor Camera 被保护；
- Anchor Hard Validation 失败时不能 Confirm；
- Soft Warning 不默认阻塞 Confirm；
- 任何阶段均可 Restart Current Target。

## View / Mask

- View 可以无 Mask；
- Mask Failure 不等于 View Failure；
- User-added View 与 Auto View 使用同一后续流程；
- Stable / Editing 版本隔离；
- 自动 Mask 和完全手工 Mask 均合法。

## View Planning

- 默认 Adaptive Planner；
- 不要求固定 View Count；
- 支持 Stop Generation；
- 支持 incremental Generate More；
- Add View 由用户决定 Camera；
- Auto Budget 有硬上限。

## Review

- Auto Review 默认 Excluded；
- Review 不会偷偷参与 Lift；
- Review 不一定阻塞 Lift；
- Review Reason 由 Companion ViewAssessmentPolicy 输出；
- Reason 必须 evidence-backed；
- 普通 UI 不显示统一 Confidence %；
- User Confirmed 后自动 assessor 不得夺回用户权威。

## Gallery

- 单行横向、稳定顺序；
- Card 极简；
- Status / Participation / Selection 使用独立视觉编码；
- Needs Attention 可作为 Review Queue；
- Frustum 选中可自动滚动 Gallery；
- Filter 不改变 Participation。

## Recompute

- local feedback / assessment 自动；
- Repropagate 显式；
- Re-Lift 显式；
- Repropagate 后不自动 Re-Lift；
- Stable Input 改变才让 Candidate stale。

## Coverage

- 不使用 Whole Scene denominator；
- Observation 基于 contributor；
- View Count 与 View Diversity 分开；
- Lift Readiness 支持 Not Ready / Limited / Ready。

## Candidate

- Lift 不直接修改 Native Selection；
- Candidate 与 Uncertain 分开；
- Candidate 不允许直接 3D patch；
- stale Candidate 不能执行原生 Operation；
- 结构性错误通过 View/Mask 修正后 Re-Lift；
- 小型最终修正通过 Native Selection tools 完成。

## Native Selection

- Set/Add/Remove/Intersect 直接写 Native Selection；
- Operation 进入 Native EditHistory；
- AI Select 操作后保持 Active；
- Undo 不需要重新 AI 推理；
- 连续多对象不引入隐式 Add Mode。

## Scene Mutation

- Selection/UI-only change 不 invalid；
- AI dependency mutation → Suspended；
- Suspended Context 保留但只读；
- 精确 Undo 恢复 dependency token 后自动恢复；
- v1.0 不实现 partial artifact repair。

---

# 88. 决策记录

| ID | 状态 | 决策 |
|---|---|---|
| DG-01 | CLOSED | AI Select 是与 Sphere/Box 同级的 Selection Tool |
| DG-02 | CLOSED | gsplat 是 authoritative AI observation renderer |
| DG-03 | RETIRED | Uncertain operation-specific semantics 被 Candidate Construction 取代 |
| DG-04 | CLOSED | Core Target Observation + View Diversity + Lift Readiness |
| DG-05 | CLOSED | Current View First + Explicit Camera Inspection |
| DG-06 | CLOSED | Review 默认 Excluded，但不必阻塞 Lift |
| DG-07 | CLOSED | Selection Operation 后 AI Select 与上下文继续保留 |
| DG-08 | CLOSED | View / Mask 解耦，支持 User-added View |
| DG-09 | CLOSED | Mask 独立、版本化、可清空/重画/恢复/重新生成 |
| DG-10 | CLOSED | Repropagate / Re-Lift 显式触发 |
| DG-11 | CLOSED | 所有阶段支持 Restart Current Target；保留 Native Selection/EditHistory |
| DG-12 | CLOSED | Anchor Validation = Hard Gate + Soft Warning，不提供虚假综合 Readiness 分数 |
| DG-13 | CLOSED | 默认 Adaptive View Planner；Stop / Generate More / Add View 分层控制 |
| DG-14 | DEFERRED | Candidate Provenance & Source Inspection 延后到下一版本 |
| DG-15 | CLOSED | Candidate 不直接编辑；结构性错误修 Observation 后 Re-Lift，小修交给 Native Selection |
| DG-16 | CLOSED | 同时只有一个 Current Target Context，不引入 Persistent AI Session Stack |
| DG-17 | CLOSED | Scene dependency mutation → Suspended；exact Undo 可自动恢复 |
| DG-18 | CLOSED | 单行可扩展 Gallery + Summary/Filter/Review Queue |
| DG-19 | CLOSED | Review Reason 由 evidence-backed ViewAssessmentPolicy 给出；无统一 Confidence % |

---

# 89. 工程验证、PoC 与 Benchmark 项目

以下不是重新打开产品架构，而是实现阶段必须验证/校准的工程项目：

1. Camera Inspection 自动外部观察位置算法；
2. CameraBinding 与 SuperSplat / gsplat 坐标约定的精确实现；
3. Anchor / Generated View inference resolution；
4. Frustum manipulation-end Final Preview response sequencing；
5. Adaptive View Planner 具体候选 Camera 策略；
6. Planner min/max budget 与 early-stop benchmark；
7. Core Set / Context Set 构造；
8. contributor observation strength 数学定义；
9. View Diversity direction bins；
10. Lift Readiness benchmark 阈值；
11. Stable Gaussian ID 生命周期；
12. semantic TargetDependencyToken 与 Undo 恢复机制；
13. 大规模 SceneSnapshot 数据布局；
14. gsplat tensor / contributor cache；
15. GPU evidence aggregation；
16. Repropagate reference selection；
17. Mask version artifact storage / GC；
18. Native EditHistory command 与 Candidate Applied / 撤销并修正 UI 同步；
19. Active Splat 与多可见 Splat的 AI render / contributor dependency scope；
20. Companion cancellation、OOM、atomic publication 端到端 PoC；
21. ViewAssessmentPolicy P0 reason threshold calibration；
22. Cross-view consistency / visible-support PoC；
23. Review Reason false-positive / false-negative benchmark；
24. Gallery virtualization、thumbnail texture lifecycle；
25. Suspended Context 下异步旧结果 rejection 压测。

`identity-drift`、Candidate Provenance UI、Gaussian Evidence Inspector 不属于 v1.0 实施阻塞项。

---

# 90. 最终状态机

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
gsplat Anchor RGB
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
              ├── Review + Reason → Excluded by default
              ├── Correct / Manual Mask
              └── Exclude
              ↓
     Included Stable View Set
              ↓
        Lift Readiness
              ↓
      Lift / Update Candidate
              ↓
        Gaussian Candidate
              │
              ├── 修正 AI 结果
              │      ↓
              │ View / Mask Correction
              │      ↓
              │ Candidate Stale
              │      ↓
              │ Update Candidate
              │
              └── Set / Add / Remove / Intersect
                     ↓
                 Native Selection
                     ↓
                Candidate Applied
                     │
                     ├── Undo / Redo
                     ├── 撤销并修正
                     ├── Native Tool 精修 Selection
                     ├── 重新选择对象
                     └── Switch Tool
```

全局任意 Current Target 阶段：

```text
重新选择对象
→ dispose Current Target Context
→ rotate targetContextId
→ Current Scene View First
```

若发生 AI dependency Scene Mutation：

```text
Current Target Context
→ Suspended
    │
    ├── exact Undo dependency restore → previous state
    └── Restart Target → new context
```

---

# 91. 最终数据依赖图

```text
AITarget
  │
  ├── Active Splat
  └── TargetDependencyToken
          │
          ↓
CurrentTargetContext / targetContextId
          │
          ↓
Anchor CameraBinding
  │
  ├── gsplat RGB
  ├── Contributor
  └── Anchor Mask Versions
          │
          ↓
    Stable Anchor Mask
          │
          ↓
    Adaptive View Planning
          │
          ↓
        AI Views
 ┌────────┼──────────┐
 │        │          │
Camera   RGB     Contributor
 │
Mask Versions
 │
Stable Mask
 │
ViewAssessmentPolicy
 │
├── Good
├── Review + Reason[]
└── Failed
 │
Participation
 │
 └─────────────┐
               ↓
     Included Stable Views
               │
               ├── Observation Coverage
               ├── View Diversity
               └── Lift Readiness
                       │
                       ↓
                 Gaussian Lifting
                       │
              ┌────────┼────────┐
              │        │        │
          Selected  Uncertain  Rejected
              │
              ↓
          Candidate C
              │
              ↓
   Set / Add / Remove / Intersect
              │
              ↓
        Native SelectOp
              │
              ↓
       Native EditHistory
```

所有异步产物额外绑定：

```text
targetContextId
+
contextRevision
+
dependencyToken
```

---

# 92. v1.0 版本边界

## 92.1 已明确不进入 v1.0

```text
Candidate Provenance & Source Inspection (DG-14)
Candidate History Browser
Reopen Previous AI Target
Persistent AI Session Stack
View → Candidate Gaussian contribution percentage
Gaussian-level Evidence Inspector
Gaussian-level uncertainty explanation
Reliable semantic Identity Drift detection
Direct 3D editing / patching of AI Candidate
Scene Mutation partial artifact repair
```

这些能力不得因为实现便利而隐式混入 v1.0 主流程。

## 92.2 v1.0 必须保留的未来扩展点

即使 DG-14 延后，当前版本仍需保留：

```text
candidateId / candidateRevision
stable input revision/fingerprint
target dependency binding
pipeline/policy version where needed
atomic publish boundary
```

用途仅限：

```text
stale correctness
async correctness
atomic publication
debug logging
```

不要求暴露 Candidate provenance UI。

## 92.3 变更原则

后续如果真实用户流程出现无法由本状态机解释的状态，再新增针对性 Decision Gate。

不得因为实现阶段局部问题重新打开已经关闭的基础产品模型，例如：

```text
AI Select 是否是 Workspace
是否需要 Draft Selection
Anchor 是否先摆 Frustum
Review 是否默认参与 Lift
View 与 Mask 是否绑定
Mask 是否能完全手画
Repropagate 是否自动
Selection Operation 是否结束 AI Select
Candidate 是否应变成第二套 3D Editor
```

---

# 93. Final Conclusion

当前 v1.0 产品模型最终收敛为：

```text
SuperSplat
= 3D Editor / Scene Authority / Native Selection Authority

gsplat
= AI Observation Rendering / Contributor Attribution

SAM
= 2D Mask Proposal / Propagation

ViewAssessmentPolicy
= Evidence-backed View / Mask Quality Assessment

AI View + Stable Mask
= Versioned Observation Annotation

Gaussian Lifting
= Observation → Candidate

Set / Add / Remove / Intersect
= Candidate → Native Selection
```

AI Select 不建立另一套编辑器，也不建立另一套 Selection 体系。

它的核心价值是：

> **把一个原本很难由用户直接精确描述的 3D Gaussian Candidate，通过可检查、可修正、可补充、可解释风险的多视图 2D Observation 构造出来，然后交回 SuperSplat 原生 Selection 工作流。**

当前版本的边界同时保持清晰：

```text
结构性 AI 错误
→ 修 View / Mask / Observation
→ Re-Lift

最终 Selection 的局部小修
→ SuperSplat Native Selection Tools
```

这条边界是 v1.0 的核心设计约束。
