# AI Select：从固定多视图到 Coverage-driven Iterative Gaussian Selection

> 文档类型：技术调研结果 / 后续设计输入，**非规范、非实现规格**  
> 调研日期：2026-08-19  
> 当前基线：`ai-select-v1`，AI Select Final Spec v1.3  
> 主要外部来源：[Seed2GS（arXiv:2608.11928）](https://arxiv.org/pdf/2608.11928)  
> 建议仓库路径：`docs/research/coverage-driven-iterative-gaussian-selection.md`

## 1. 结论

AI Select 下一阶段值得吸收 Seed2GS 的四个核心思想：

1. **Conservative Seed Lift**：从 Anchor Stable Mask 构造高精度、允许不完整的 3D seed，不把一次 2D 投影当成最终 Gaussian ownership。
2. **Coverage-driven View Acquisition**：根据当前已经观察到什么、仍缺什么以及下一视角的预期增益决定是否继续和去哪里看，而不是固定生成若干 View。
3. **3D-consistency Reliability Weighting**：把每个 2D Stable Mask 当作 noisy observation，用当前跨视图 3D hypothesis 反向评估其可靠度，再参与 Evidence aggregation。
4. **Iterative 3D Consensus**：将一次性 `plan → observe → lift` 改为有界循环：获取 observation、更新临时 3D consensus、评估 reliability 与 coverage、选择下一步，直到满足发布条件或触发有解释的停止原因。

这四点应当作为**一个闭环系统**设计，不能拆成四个互不相干的 feature：

```text
Anchor Stable Mask
        ↓
visibility-aware conservative 3D seed
        ↓
当前 observation / coverage / uncertainty 评估
        ↓
选择预期价值最高且可行的下一 View
        ↓
authoritative RGB + Stable Mask + raw P/N/V Evidence
        ↓
临时 multi-view 3D consensus
        ↓
3D-consistency observation reliability
        ↓
weighted aggregation + readiness
        ↓
继续获取 View / 有界停止 / 原子发布 AI Candidate
```

对当前项目最重要的适配原则是：

- **保留 v1.3 已验证的信任边界和产品状态模型**，不要为复刻论文另建第二套 selection system。
- **复用 same-decision Direct Evidence、Stable Gaussian ID、Observation Coverage、View Diversity、Lift Readiness 和 atomic Candidate publication**。
- **将固定 `4–8` View 降级为当前 baseline 或有界预算候选，而不是继续作为“信息充分”的代理指标**。
- **不默认引入 SAM2/video tracker、dense orbit、open-vocabulary re-grounding 或新的 per-Gaussian logit ownership 主链**。
- **先完成领域模型、ADR、benchmark 和分阶段规格，再进入实现**。

---

## 2. 当前项目基线

当前权威链路由 [Final Spec v1.3](../specs/ai-select-final-spec-v1.3.md)、[ADR 0018](../adr/0018-adopt-single-result-authoring-and-retire-explicit-recovery-planning-controls.md) 和 [ADR 0019](../adr/0019-promote-direct-evidence-candidate-and-bind-production-identity.md) 约束：

```text
Anchor authoritative RGB
→ operator-authored Single Mask Result
→ Confirm
→ Anchor Stable Mask
→ TargetGeometryHint
→ fixed-offset bounded Local Key-View plan
→ authoritative per-View RGB
→ independent SAM 3 Image instance Mask
→ Stable Mask + Participation
→ per-View production Direct P/N/V Evidence
→ multi-view aggregation
→ Lift Readiness
→ atomic production-ready AI Candidate + Uncertain
→ Native Set / Add / Remove / Intersect
```

当前设计已经具备后续升级所需的大部分基础：

- `TargetGeometryHint` 已使用 Anchor 的 visible-surface support 做定位和 framing，但明确不携带 Gaussian ownership。
- Generated View、authoritative RGB、Stable Mask、Participation、per-View Evidence 和 Candidate 生命周期彼此分离。
- production Direct Evidence 使用与 RGB 相同的权威 raster decision source，输出每 View、每 Gaussian 的 `P / N / V`。
- `Observation Coverage` 使用 Included Stable Views 对 Core Target Gaussian 的有效 Visible Mass，而不是 View 数量或 frustum inclusion。
- `View Diversity` 与 coverage 分离。
- `Lift Readiness` 已经是 `Not Ready / Limited / Ready`，并非固定 N-view gate。
- Candidate replacement、Stable Mask publication 和 per-View Evidence publication均为原子操作；失败保留旧的可检查 Candidate。
- production identity 已绑定 renderer、SAM、Prompt、TargetGeometryHint/local-View、Mask Review、Direct Evidence/aggregation 和 Lift Readiness policy。

当前主要缺口不在基础 lifting，而在 orchestration：

```text
当前：先固定规划，再一次性聚合
目标：根据当前 3D 状态逐步规划，并在每轮更新可靠度与 consensus
```

### 2.1 固定 View 数量的问题

ADR 0018 当前规定初始自动 Generated Views 为 `4–8`，默认配置实际生成 4 个；它也明确说明这**不是 adaptive-quality claim**。固定数量有两个对称问题：

- 简单目标可能被过度采样，增加 render、SAM、Evidence 和错误 observation 的成本。
- 困难目标即使达到 8 个 View，也可能没有观察到真正 unresolved 的方向。

因此下一阶段不应只把 `4–8` 改成另一个固定范围，而应让 View acquisition 受当前 evidence state 驱动。

### 2.2 规范影响

本调研方向会触及并可能部分 supersede：

- Final Spec v1.3 的 bounded local Key-View planning 语义；
- ADR 0018 的固定 `4–8` 初始规划和无常驻 planning controls 语义；
- ADR 0019 绑定的 aggregation、Lift Readiness 和 production identity；
- `CONTEXT.md` 中 `TargetGeometryHint`、`Local Key View`、`Observation Coverage`、`Lift Readiness` 与 deferred `Adaptive View Planner` 的定义。

因此它不能作为“内部重构”静默落地。后续至少需要一个新的、明确 supersede 关系的 ADR，并很可能需要新的规范版本；具体版本号与迁移策略应由 grilling session 决定。

---

## 3. Seed2GS 的可迁移证据

Seed2GS 的价值不在于某组固定轨迹参数，而在于它证明了以下组合有效：

```text
precision-first seed
+ visibility-adaptive observation acquisition
+ cross-view 3D reliability
```

根据论文及本次调研提炼：

- Seed Lift 使用 2D mask、rendered depth consistency 和 3D connected-component filtering，得到 conservative `G₀`，而不是直接把 mask 视锥中的全部 Gaussian 当作目标。
- VAAS 根据已有 seed 的可见覆盖调整是否增加 elevation；论文报告 adaptive 方案平均使用约 27.1 个 trajectory views，而 fixed ascending 使用 48 个，同时 adaptive 的精度增益更高。
- 单纯把 orbit 从 24 views 增加到 48 views 反而可能降低 LERF-MASK 的 mIoU/mBIoU，说明“更多 observation”不等于“更多有效信息”。
- 论文用当前 3D membership 渲染 soft mask，与每个 2D observation 比较 residual，再用 median/MAD 形成 robust view weight；其 ablation 在两个 benchmark 上分别带来约 `+1.25` 和 `+1.40` mIoU。

这些结果支持的是设计原则，不应被解释为当前项目必须复制：

- 24/48-view dense orbit；
- SAM2 tracking；
- 论文的具体 pitch 公式；
- 论文的 per-Gaussian logit optimizer；
- 论文的数据集阈值。

---

## 4. Conservative Seed Lift

### 4.1 目标

从 exact Anchor Stable Mask 构造一个**高 precision、允许低 recall**的 3D support，作为后续 observation acquisition 和 consensus bootstrapping 的起点。

它不是最终 segmentation，也不是 AI Candidate：

```text
Conservative Seed Support
≠ TargetGeometryHint
≠ Evidence Working Set 的永久边界
≠ Selected Gaussian ownership
≠ AI Candidate
```

### 4.2 对当前项目的首选适配假设

Seed2GS 使用独立的 mask + rendered depth projection。当前项目已经有 same-decision per-View `P/N/V` Direct Evidence，因此应优先验证：

> 能否从 **Anchor 的 production-direct Evidence** 构造 conservative seed，而不是新增一个独立 depth/back-projection seam？

一个待验证的候选方法是：

```text
exact Anchor Stable Mask
→ Anchor production Direct P/N/V
→ high positive ratio / sufficient visible mass / low conflicting mass
→ scale-aware 3D connectivity or support filtering
→ conservative Stable Gaussian ID support
```

潜在优势：

- 复用 Stable Gaussian IDs；
- 与 authoritative RGB 共享 raster decisions；
- 避免第二套 visibility/depth tolerance 产生边界分歧；
- 可以直接进入现有 Evidence Policy、working-set 和 production identity 体系；
- 更容易通过现有 reference Contributor backend 做对照验证。

这只是研究假设。Codex 必须检查当前 Evidence 的生命周期：Anchor per-View Evidence 是否能在初始 View planning 前安全产生、缓存和绑定，是否需要解耦现有 Re-Lift orchestration。

### 4.3 可能需要的新领域概念

工作名：`Conservative Seed Support`。最终名称必须在 grill 中与 `CONTEXT.md` 对齐。

可能的概念契约：

```text
exact target/context/dependency identity
Anchor CameraBinding + RGB + Stable Mask identity
seed policy identity
Stable Gaussian IDs or bounded support representation
per-seed support diagnostics
connectivity/filtering reasons
quality: usable / limited / unavailable
artifact digest
```

是否允许该 artifact 跨 Browser/Companion 边界、是否必须包含 Stable IDs、它是否属于 Evidence 派生物，均未决定。

### 4.4 必须保持的约束

- seed 必须 precision-first；允许漏掉背面、薄结构和遮挡区域。
- seed 不能直接发布 Native Selection 或 AI Candidate。
- seed 不能把缺失或未连接 support 自动标为 Rejected。
- seed 可帮助初始化 Evidence Working Set，但不能 hard-bound 后续 Evidence expansion。
- seed 的 filtering 必须可重放、版本化、可诊断。
- 不应无条件“只保留最大 connected component”；细腿、把手、线缆、低密度区域和真实多组件对象可能被错误删除。
- 被过滤的 satellite support 应至少有可诊断的 uncertain/filtered reason，而不是无痕消失。

### 4.5 Grill 中需要决定

- seed 的 authoritative source：Anchor Direct Evidence、first-hit support，还是同一 renderer seam 中的新 artifact？
- Stable Gaussian IDs 是否进入 seed artifact；这是否会与“geometry is not ownership”冲突？
- Gaussian adjacency 的定义：中心距离、scale-aware overlap、KNN、render co-visibility，还是组合？
- 主 component 与 plausible satellite components 的保留规则。
- seed unavailable/limited 时：fail closed、退回当前 fixed planner，还是只用 TargetGeometryHint？
- seed policy 是否进入 production Runtime Profile，还是先作为 experimental/shadow policy。

---

## 5. Coverage-driven View Acquisition

### 5.1 目标

让系统回答两个不同问题：

```text
已经观察得是否足够？
下一台可行相机能增加多少有价值的信息？
```

当前 `Observation Coverage` 是**已实现 observation 的 realized metric**。Adaptive planner 还需要一个前瞻性的量，工作名可为：

```text
Expected Observation Gain / View Utility
```

它不能与 `Observation Coverage` 混用。

### 5.2 不应只使用 seed visibility

只测 conservative seed 的可见比例可能形成错误提前停止：seed 可能只有正面，所有 seed Gaussian 都已被看到，但真实物体的背面和薄结构从未进入 seed。

下一 View 的价值至少可能综合：

- 对当前 seed/consensus 中低覆盖 Gaussian 的预计新增 Visible Mass；
- 对 `Uncertain` 或 P/N conflict support 的消歧价值；
- 与已有 Included Views 的方向新颖度；
- 对 consensus frontier / boundary 的预计观察；
- 对遮挡后 support 的可见性；
- CameraBinding feasibility、projection size、clipping、nonblank、gross occlusion；
- render、SAM 和 Evidence 的预计成本；
- 与已有 View 的重复度；
- 当前 Lift Readiness 的具体缺口。

### 5.3 建议的职责分离

```text
Observation Coverage / View Diversity
    描述已经获得的 observation

View Utility / Next-View Decision
    评估候选 CameraBinding 的预期边际价值

Lift Readiness
    决定当前 Evidence 是否足以发布 Candidate
```

Planner 可以消费 readiness reasons，但不能接管 Candidate publication authority。Lift Readiness 也不应成为包含 camera search、cost model 和 observation weighting 的总控对象。

### 5.4 可能的 acquisition loop

```text
生成小规模初始候选池或第一批 View
→ preflight
→ 选择最高 utility 的可行 View
→ render / mask / evidence
→ 更新 consensus、coverage、diversity、readiness
→ 重新评分候选或生成新候选
→ repeat
```

有界停止原因至少应可区分：

- `ready-and-low-marginal-gain`；
- `marginal-gain-exhausted`；
- `view-budget-exhausted`；
- `latency/cost-budget-exhausted`；
- `no-feasible-view`；
- `planning/render/mask/evidence-failure`；
- `stale/cancelled/suspended`。

最终 canonical names 待 domain modeling 决定。

### 5.5 与当前 `4–8` 的关系

需要通过 benchmark 决定以下方案之一，而不是提前写死：

- 保留 `4–8` 作为 hard maximum，但允许 1–N early stop；
- 将 `4–8` 改为初始候选池大小，而非实际 render 数；
- 使用双预算：View 数上限 + latency/cost 上限；
- 完全替换当前范围，但保留 fixed-four 作为 regression baseline。

### 5.6 Grill 中需要决定

- 初始 observation 是否只含 Anchor，还是自动追加最小的 horizontal pair？
- 候选相机族：当前 fixed offsets、flat orbit、ascending offsets、局部球面采样、分层候选池，或其他。
- utility 的定义、归一化、tie-break 和 deterministic replay。
- realization 后多久重规划：每个 View、每个小 batch，还是只在 readiness 不足时。
- invalid/failed View 是否消费预算，是否触发 bounded replacement。
- 用户是否看到自动 acquisition 进度、停止原因或手动终止；当前无常驻 Stop/Generate More 控件不能被无意复活。
- User-added View 如何进入下一轮 planning 和 consensus。

---

## 6. 3D-consistency Reliability Weighting

### 6.1 目标

不再把所有 Included Stable Views 视为同等可信。对每个 observation，比较：

```text
当前临时 3D consensus 在该 CameraBinding 下渲染的 soft mask
vs.
该 View 的 Stable Mask
```

由 residual 得到版本化的 reliability weight，再参与 Evidence aggregation。

### 6.2 与当前状态模型的关系

必须保留以下分层：

```text
Mask Review
    判断单 View observation 是否 Good / Review / Failed

Participation
    决定该 Stable View 是否 Included / Excluded

Observation Reliability
    决定一个 Included observation 在 aggregation 中的相对语义影响
```

Reliability 不能静默修改 Stable Mask，也不能自动等价为 Participation。

### 6.3 首选适配原则

- raw per-View Direct `P/N/V` artifact 保持不可变。
- reliability 作为 aggregation policy 的输入或派生 artifact。
- residual、robust center/scale、floor、最终 weight 和 policy digest 可审计、可 replay。
- 使用非零 `r_min`，避免早期 consensus 把困难但正确的 View 完全压制。
- 在最小 observation 数之前采用 uniform weight 或弱 weighting。
- weight policy、soft-mask renderer 和 consensus identity 必须进入 production identity。

### 6.4 一个关键未决问题：权重作用于什么

当前 `V` 表示几何可见贡献，`P/N` 表示 mask-conditioned 语义 evidence。直接将同一个 `ω_c` 乘到 `P/N/V` 可能把“Mask 不可靠”和“该区域未被观察”混为一谈。

优先需要评估的方案是：

```text
raw V 保留用于 realized Observation Coverage
reliability 主要调节 P/N 语义 mass
```

但这不是最终决定。也可能需要额外的：

- raw geometric visibility；
- trusted semantic evidence mass；
- reliability-adjusted coverage/readiness 分量。

该边界必须在 grill 和 benchmark 中明确。

### 6.5 防止 3D consensus 自我确认

最危险的失败模式是：初始 seed 漏掉真实区域，新 View 正确发现它，但因为与旧 consensus 冲突而被降权。

需要考虑：

- lagged consensus：第 `k` 轮 weight 只由第 `k-1` 轮 consensus 计算；
- warm-up：前若干 observation 使用 uniform weight；
- non-zero floor；
- 对当前未覆盖 frontier 的新增 foreground 降低惩罚；
- 对已充分观察、高置信区域的矛盾给予更强惩罚；
- reliability 不能单独触发 Excluded；
- 低权 View 保持可检查，并带具体 residual/reason；
- User Confirmed / manually edited Stable Mask 是否允许自动降权，必须显式决定，不能默默处理。

### 6.6 Grill 中需要决定

- consensus soft mask 的权威渲染 seam；是否必须复用 same-decision raster decisions。
- residual：BCE、IoU、boundary residual、visibility-aware residual，还是组合。
- view-level weight、region-level weight或 per-pixel weight 的范围。
- median/MAD 等 robust estimator 的具体策略和退化处理。
- `r_min`、warm-up、最大重算轮数和收敛条件如何校准。
- reliability 对 P、N、V、coverage、readiness 的具体作用。
- automatic、Review、User Confirmed、manual masks 是否采用不同 policy。
- diagnostics 是否只在 Companion/benchmark，还是需要最小 Browser inspection。

---

## 7. Iterative 3D Consensus

### 7.1 目标

把当前一次性 Re-Lift 扩展成一个有界、可重放的内部闭环：

```text
raw observations
→ provisional consensus revision
→ reliability revision
→ weighted aggregation revision
→ coverage/readiness revision
→ next-view or stop decision
```

### 7.2 临时 consensus 不等于 AI Candidate

当前 `AI Candidate` 是可检查、可应用、绑定 production identity 的原子发布结果。新的 provisional consensus 应保持明确边界：

```text
Provisional 3D Consensus
    用于 planner、reliability 和迭代计算
    不可执行 Native Set/Add/Remove/Intersect
    不形成跨 target persistent history

AI Candidate
    仅在 exact current Evidence + readiness + identity 满足时原子发布
```

这可以避免把 AI Select 变成第二个可编辑 3D model，也避免违反当前 deferred 的 persistent Candidate history / provenance UI。

### 7.3 建议的有界迭代结构

```text
revision 0:
    conservative seed + available observations
    uniform or warm-up weights

revision k:
    aggregate exact current raw Evidence using reliability(k-1)
    derive provisional consensus(k)
    render/compare observations
    derive reliability(k)
    derive coverage/diversity/readiness(k)
    choose next View or stop
```

需要明确限制：

- 最大 View 数；
- 最大 consensus revisions；
- 最大 wall-clock / GPU cost；
- convergence threshold；
- stale/cancel/suspend semantics；
- failure isolation；
- exact same-attempt replay。

### 7.4 与现有生命周期的兼容要求

- 新 View、Stable Mask revision 或 Participation change 必须使依赖它的 consensus/reliability/readiness stale。
- Editing Mask 仍不影响当前 Stable Evidence，直到 Confirm Mask。
- iteration failure 保留所有独立有效 Views、Stable Masks、raw Evidence 和旧的可检查 Candidate。
- late result 不得覆盖更新后的 target/context/dependency/policy identity。
- progressive View publication 只允许发布独立完整、身份正确的 AI View。
- Candidate 仍只在完整 replacement 成功时原子替换。
- Native Selection 不随内部 consensus revision 自动变化。

### 7.5 Grill 中需要决定

- consensus 是 Companion-local disposable state，还是 Browser 持有最小 revision/status authority。
- acquisition 与 aggregation 是每 View 串行闭环，还是小 batch 闭环。
- explicit Re-Lift 在新架构中是触发完整闭环、只重算 consensus，还是仍保留现有职责。
- 自动 Generated View 的 Stable Mask publication 与 iteration 的先后关系。
- iteration 中途达到 `Ready` 是否立即停止，还是还需一个 marginal-gain gate。
- `Limited` 在 budget exhausted 时是否允许 Candidate publication。
- 当前无常驻 planning controls 的产品约束是否保持。

---

## 8. 推荐的项目化主链

以下是研究阶段的目标形态，不是最终 contract：

```text
Anchor Stable Mask
        ↓
TargetGeometryHint                         (现有，定位/Prompt，不是 ownership)
        ↓
Conservative Seed Support                  (待决，新 precision-first 3D support)
        ↓
Initial / candidate CameraBindings
        ↓
Next-View utility + renderer preflight
        ↓
Authoritative RGB
        ↓
SAM 3 Image Single Mask Result             (首轮默认继续复用当前 production path)
        ↓
Stable Mask + Participation
        ↓
Raw same-decision Direct P/N/V Evidence    (不可变)
        ↓
Provisional 3D Consensus revision
        ↓
Observation Reliability revision
        ↓
Weighted Evidence aggregation
        ↓
Observation Coverage + View Diversity + Lift Readiness
        │
        ├── valuable feasible View exists → acquire next observation
        ├── sufficient and low gain       → atomic Candidate publication
        ├── Limited + budget exhausted    → policy-defined outcome
        └── Not Ready / no feasible View  → fail closed with reasons
```

### 8.1 Runtime ownership的研究建议

遵循当前边界：

- Browser 继续拥有 Current Target Context、AI View registry、Stable Mask、Participation、Candidate/Uncertain presentation 和 Native Selection authority。
- Companion 继续拥有 renderer、seed computation、candidate-view scoring、SAM inference、Direct Evidence、consensus、reliability、aggregation 和 readiness computation。
- Browser 是否需要持有 seed/consensus/reliability 的正式 artifact，必须以产品可检查性、replay、stale rejection 和协议成本为依据，而不是因为“计算发生过”就全部跨协议发布。

### 8.2 Production identity

若进入 production，至少以下 policy/implementation identity 需要被纳入或明确关联：

- conservative seed policy；
- candidate-view generation / utility policy；
- soft-consensus rendering policy；
- observation reliability policy；
- iterative consensus / convergence / stop policy；
- 更新后的 aggregation 与 Lift Readiness policy。

不能只更新算法代码而保留旧的 `productionIdentityDigest`。

---

## 9. 主要风险和需要主动攻击的场景

### 9.1 Seed false-negative lock-in

保守 seed 漏掉的真实结构可能永远不进入 candidate pool、Evidence Working Set 或 view utility。必须验证 working set expansion 和 frontier discovery 不被 seed hard-bound。

### 9.2 Consensus confirmation bias

错误初始 consensus 可能系统性压低正确但新颖的 View。必须使用 warm-up、floor、frontier-aware disagreement、lagged updates 和 adversarial fixtures。

### 9.3 Coverage circularity

当前 Observation Coverage 依赖 Core Target set；如果 Core Target 又由 seed/consensus 定义，系统可能通过缩小分母制造“高 coverage”。Core Target authority、扩张规则和 denominator stability 是核心设计问题。

### 9.4 View utility 与真实信息增益错位

仅凭几何 visibility 可能选择语义无用或 SAM 易漂移的 View；仅凭 mask uncertainty 又可能忽略真实未观察表面。需要同时测 realized gain 与 predicted gain 的 calibration。

### 9.5 成本失控

adaptive 不等于无限循环。每个 View 涉及 render、Prompt synthesis、SAM、Evidence 和 consensus update，必须有明确预算和停止原因。

### 9.6 现有产品控制被意外复活

自动迭代可能诱导重新加入 Stop / Generate More / Retry 等控件。是否需要这些交互是独立产品决策，不应由 orchestrator 实现细节暗中决定。

### 9.7 Artifact 与 identity 爆炸

每轮都可能新增 seed、utility、consensus、reliability、aggregation revision。需要决定哪些是正式 immutable artifact，哪些只是可重建的 Companion-local execution state。

### 9.8 用户权威被软化

User Confirmed Stable Mask、explicit Participation 和 Native application authority 不能被自动 weighting 或 planner 静默覆盖。

### 9.9 必测目标类别

- 简单凸物体；
- 背面不可见或强 self-occlusion；
- 薄结构、把手、腿、线缆；
- 多个相邻同类实例；
- 与背景紧贴或颜色相似；
- 低 opacity / splat density 不均；
- 多个真实 disconnected components；
- 大型目标、局部裁切目标；
- 相机候选进入墙体、桌面或空洞；
- 新 View 正确扩张旧 consensus 的反 confirmation-bias 场景；
- 一个严重 drift 的 automatic Stable Mask；
- User Confirmed Mask 与当前 consensus 冲突。

---

## 10. Benchmark 与验收方向

### 10.1 必须保留的 baseline

当前 fixed-four production path 应冻结为 regression baseline。建议至少比较：

```text
A. current fixed-four, current aggregation
B. conservative seed + fixed-four
C. conservative seed + adaptive acquisition + uniform weights
D. C + reliability weighting
E. D + iterative consensus / convergence
```

SAM2/sequence tracking 和新的 per-Gaussian logit optimizer 不进入第一轮主 ablation；若后续单独调研，应作为额外变量，避免无法归因。

### 10.2 质量指标

- seed Gaussian precision / recall；
- final Gaussian precision / recall / F1；
- novel-view mask mIoU / boundary IoU；
- background contamination；
- `Uncertain` ratio 与 mixed-evidence rate；
- disconnected true-part retention；
- identity switching；
- failure / Limited / Not Ready rate；
- Candidate stability across deterministic replay；
- predicted View utility 与 realized Evidence gain 的相关性；
- drift View 被降权的比例与正确 novel View 被误降权的比例。

### 10.3 用户成本指标

- Candidate application 后需要 Native Remove 的 Gaussian 数量；
- 需要 Native Add 的 Gaussian 数量；
- 用户修正的 Stable Views 数量；
- User-added Views 数量；
- Re-Lift / restart 次数；
- 完成一次可靠 selection 的操作数。

### 10.4 系统成本指标

- actual Generated View count：median / P90 / P95；
- render、SAM、Evidence 和 consensus update 次数；
- end-to-end latency：median / P95；
- peak VRAM、Companion RSS；
- OOM、timeout、cancel、stale discard；
- 每种 stop reason 的分布；
- shadow planner 的 predicted gain calibration；
- locked-GPU throughput 与 deterministic policy stability。

### 10.5 成功标准的方向

Adaptive 方案的成功不应定义为“轨迹更复杂”，而应是：

```text
简单目标显著提前停止
+ 困难目标能有界地获取更多真正有价值的 observation
+ 相同或更高的 Gaussian selection 质量
+ 更少的用户修正
+ 可解释、可重放的停止与降权原因
+ 不破坏现有 identity、atomicity 和 Native Selection authority
```

具体阈值必须通过 benchmark/calibration 决定，不能从 Seed2GS 数据集直接移植。

---

## 11. 推荐开发推进顺序

这不是 ticket 拆分，只是研究建议。正式顺序应在 grill → ADR/spec 后确定。

### Phase 0：设计与 instrumentation

- 冻结 fixed-four baseline；
- 记录 per-view P/N/V、Observation Coverage、View Diversity、readiness reasons、latency 和人工修正成本；
- 确认 Anchor Direct Evidence 能否在 planning 前安全产生；
- 建立 adversarial fixtures。

### Phase 1：Conservative seed shadow artifact

- 不改变 planner 和 Candidate；
- 对比 Anchor first-hit、Anchor Direct Evidence 和 reference Contributor seed；
- 校准 seed precision-first policy 与 connectivity。

### Phase 2：View utility shadow planner

- 对当前 fixed Views 和更大候选池离线打分；
- 比较 predicted gain 与 realized gain；
- 不改变用户可见行为。

### Phase 3：Adaptive sparse acquisition behind explicit experiment identity

- 继续使用现有 SAM 3 Image single-frame path；
- 有界 acquisition；
- raw Direct Evidence 不变；
- 与 fixed-four A/B。

### Phase 4：Reliability-weighted aggregation

- 先 uniform warm-up + 单次 robust reweight；
- 保护 raw V、User Confirmed authority 和 frontier disagreement；
- version/calibrate Evidence policy。

### Phase 5：Bounded iterative consensus productionization

- 明确 consensus revision、convergence、stale/replay、failure isolation；
- 更新 Runtime Profile、production identity、Final Spec、ticket graph、traceability 和 locked-GPU gates。

---

## 12. 已确定方向与未决设计树

### 12.1 本次调研已经确定的方向

- 下一阶段吸收 Conservative Seed Lift。
- 下一阶段吸收 Coverage-driven View Acquisition。
- 下一阶段吸收 3D-consistency Reliability Weighting。
- 下一阶段吸收 Iterative 3D Consensus。
- 四者作为统一闭环设计，而不是四个孤立功能。
- 以当前 v1.3 production path 作为 baseline，不静默修改已接受规范。
- 优先复用现有 SAM 3 Image、same-decision Direct Evidence、P/N/V、Coverage/Readiness 和 atomic Candidate 边界。
- 不因 Seed2GS 而默认引入 dense orbit、video tracker、open-vocabulary re-grounding 或替代 ownership optimizer。

### 12.2 Grill 必须展开的根分支

1. **产品与版本边界**：这是 experiment、vNext 还是新的 normative spec？如何 supersede v1.3/ADR 0018/0019？
2. **Seed authority**：来源、artifact、Stable IDs、connectivity、fallback、working-set expansion。
3. **Coverage 与 prospective gain**：Core Target denominator、View utility、候选相机族、预算和停止。
4. **Reliability semantics**：residual、weight 作用通道、User Confirmed policy、bias protection。
5. **Consensus lifecycle**：revision、warm-up、convergence、incremental/batch、Re-Lift 语义。
6. **Runtime ownership与协议**：Browser product authority、Companion state、正式 artifact 与 disposable state。
7. **Identity、atomicity、failure**：stale rejection、attempt replay、OOM/cancel、旧 Candidate preservation。
8. **交互**：自动运行、状态可见性、失败恢复、是否保持无常驻 planning controls。
9. **Benchmark 与迁移**：ablation、locked-GPU gates、shadow rollout、ticket graph 和 traceability。

---

## 13. 明确不做的事情

本轮设计不应自动扩展到：

- SAM2/Cutie/Multiplex sequence tracking production migration；
- text/open-vocabulary object grounding；
- dense 24/48-view orbit；
- 完整补全不可见内部或所有背面作为产品目标；
- persistent Candidate history 或 Gaussian-level provenance UI；
- 直接用 provisional consensus 修改 Native Selection；
- 取消 Stable Mask、Participation、P/N/V 或 Lift Readiness 边界；
- 在未完成 calibration 前把论文公式或阈值写成 production policy；
- 在 grill 结束前创建实现 tickets 或开始代码修改。

---

## 14. 参考资料

- [Seed2GS, arXiv:2608.11928](https://arxiv.org/pdf/2608.11928)
- [AI Select Final Spec v1.3](../specs/ai-select-final-spec-v1.3.md)
- [AI Select Current Ticket / Spec Mapping](../ai-select/CURRENT-TICKET-SPEC-MAPPING.md)
- [ADR 0013 — Mask-conditioned Direct Gaussian Evidence](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md)
- [ADR 0015 — Automated Readiness](../adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md)
- [ADR 0016 — SAM 3 Image and Minimal Multi-view](../adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md)
- [ADR 0017 — Geometry Quality and Prompt Support](../adr/0017-separate-geometry-quality-from-route-b-prompt-support.md)
- [ADR 0018 — Fixed 4–8 Views and Product Controls](../adr/0018-adopt-single-result-authoring-and-retire-explicit-recovery-planning-controls.md)
- [ADR 0019 — Production Direct Evidence Candidate and Identity](../adr/0019-promote-direct-evidence-candidate-and-bind-production-identity.md)
- [`CONTEXT.md`](../../CONTEXT.md)
- [Earlier object-aware Gaussian selection research](./object-aware-gaussian-selection.md)
