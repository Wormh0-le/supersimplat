# SuperSimPlat AI Select

## 产品、交互与工程规格 — Final Spec v2.0

**文档状态：** Current Final Spec / Normative  
**日期：** 2026-08-22（用户验收接受）  
**适用分支：** `ai-select-v1`  
**决策依据：** ADR 0021、ADR 0020、ADR 0019（延续并扩展）、ADR 0018（残余效力：
单结果 authoring 延续，`4–8` 范围被双预算取代）、ADR 0016/0017、未冲突的
ADR 0013/0015

本文件经用户验收接受为唯一权威产品与工程规格（2026-08-22），由 2026-08 架构
grilling 会话产出（研究输入：
`docs/research/coverage-driven-iterative-gaussian-selection.md`）。

本规范为目标规范：生产行为按 `docs/ai-select/TICKET-GRAPH-V2.md` 的 V2x
ticket 实现逐步切换；对应行为落地前，运行时行为仍为 v1.3。

---

# 0. 规范地位与 carry-over

## 0.1 取代关系

本文件取代 Final Spec v1.3 的当前规范效力；v1.3 及更早
历史继续作为历史依据。

被取代的关键差异（相对 v1.3）：

1. 固定初始四 View 计划退位为**冻结回归/消融基线**——不再是产品路径，
   不是请求内 best-effort 回退，不是用户可选模式；
2. `4–8` 初始自动 View 范围（ADR 0018）由双预算结构取代；
3. Candidate 在终止态 `ready-and-low-marginal-gain` 下**自动原子发布**
   （同意结构变更，见 ADR 0020）；v1.3 中 Candidate 仅由显式用户动作产生；
4. **User-added View 能力移除**：Anchor 确认后采集完全自动；
5. Negative Mass（N）语义修订为深度分类（见 ADR 0021）；
6. Evidence 派生出内核内部期望深度通道与共识 soft-mask 读出（同 ADR 0021）。

## 0.2 Carry-over 清单（延续 v1.3，不改语义）

以下 v1.3 语义原样延续，本文仅在被引用处给出差异：

- SAM 3 Image 静态实例单结果工作流与单结果政策（v1.3 §6）；
- Anchor 获取、Prompt/Edit palette、TargetGeometryHintArtifact 语义
  （v1.3 §7–§9；hint 保持纯几何、非 ownership）；
- Image instance Mask 契约、per-View Mask 获取、Mask Review、Participation、
  Stable Mask 原子发布（v1.3 §11、§13–§15）；
- 权威 RGB 与 same-decision 渲染不变量（v1.3 §5、§20）；
- exact-key 校验 + checksum 绑定的生产身份体系与 fail-closed 不变量（v1.3 §4）；
- Working Set 与 Candidate/Uncertain 原子替换、Native 操作边界（v1.3 §21–§22）；
- Dirty/refresh 生命周期、失败隔离惯例（v1.3 §19、§24）。

权威顺序：本文件 → 当前 Ticket mapping → ADR 0021 → ADR 0020 →
ADR 0019 → ADR 0018（残余效力）→ ADR 0016/0017 → 未冲突的 ADR 0013/0015 →
`CONTEXT.md` → Ticket acceptance criteria → 实现与测试。

---

# 1. 产品范围

一次选择一个 3D Gaussian Splat 场景中的对象实例。用户从当前视角建立并确认
Anchor Stable Mask 之后，系统运行**有界的自适应观测采集循环**，以
precision-first 的 Conservative Seed Support 为起点，逐 View 获取
Stable Mask + Direct P/N/V Evidence，经共识、可靠性与加权聚合推进
Lift Readiness，并在低边际增益终止时原子发布 Candidate。

仍然成立：对象级选择；不重训输入 3DGS；不要求补全不可见表面；不做全图
inventory；2D 信号（Prompt、logits、SAM 分数）永远不是 Gaussian ownership。

不再成立（相对 v1.3）：固定四 View 产品路径；用户添加 View。

---

# 2. 主链

```text
Anchor Stable Mask（用户确认）
    ↓
TargetGeometryHint                      （现有语义：定位/Prompt 支持，非 ownership）
    ↓
Anchor production Direct P/N/V          （提前运行，同决策源）
    ↓
Conservative Seed Support               （precision-first 3D support，Companion 内部）
    ↓
Core Target Denominator = seed 单调扩张
    ↓
首个 View：确定性 hint 规则选择
其后每个 View：View Utility 从分层候选池选择
    ↓
Authoritative RGB → SAM 3 单结果 Mask → Mask Review → Stable 发布 → Participation
    ↓
不可变 per-View Direct P/N/V（含 Evidence-Internal Depth）
    ↓
Provisional 3D Consensus revision（Companion-local 可弃态）
    ↓
Observation Reliability revision（lagged，view-level）
    ↓
加权聚合（reliability 只调 P/N）
    ↓
Observation Coverage + View Diversity + Lift Readiness revision
    ├─ ready 且边际增益低于收紧阈值 → 自动原子发布 Candidate，循环终止
    ├─ 预算耗尽且 Limited           → 发布 readiness+原因，不发布 Candidate
    ├─ 无可行 View / 阶段熔断       → 结构化停止原因
    └─ 用户 Cancel                  → 立即生效，保留全部已完成产物
```

---

# 3. Runtime ownership

延续 v1.3 §3 的所有权边界，新增：

Browser 拥有：

- **采集循环状态机**：候选选择请求、逐 View 步进驱动、重评分触发、
  终止判定呈现；消费 readiness reasons 但永不接管 Candidate 发布权；
- 最小进度状态面与 Cancel 控件（§10）。

Companion 拥有：

- 种子计算、Evidence-Internal Depth、共识 soft-mask 读出、
  Provisional Consensus、Observation Reliability、加权聚合修订、
  View Utility 评分、readiness 计算；
- loop-scoped 派生态缓存（键 = 目标 + 依赖身份；按策略可弃）。

不存在 Companion 自治会话：所有跨边界交互走既有经验证的请求/响应传输，
每个请求独立校验、绑定身份、可重放。

---

# 4. Conservative Seed Support

Confirm Anchor 后立即对 Anchor 运行生产级同决策 Direct P/N/V（提前的 GPU
Evidence 阶段），并从中派生种子：

1. precision 筛选：high positive ratio / sufficient visible mass /
   low conflicting mass（具体阈值为校准项）；
2. **Evidence-Internal Depth 一致性过滤**：候选的贡献深度须与所在像素的
   表面期望深度一致，排除 floater 与穿透归属；
3. 连接性过滤：scale-aware 邻接（成对距离 < k × 较大者尺度）+ 深度一致性
   门控；主分量构成核心，达标的非主分量以 `satellite` 标记随行，
   未达标者记 `filtered` 并带原因；无任何分量无痕消失。

契约：

- 产物携带 Stable Gaussian IDs + 逐 seed 诊断（support ratio、visible mass、
  过滤原因）；**Companion 内部产物，不跨 Browser/Companion 边界**；
- 质量 `usable / limited / unavailable` 三态仅为诊断，任何一态不阻断流程；
  unavailable 时回退宽分母，循环靠逐 View Evidence 自然推进；
- 种子 ≠ TargetGeometryHint、≠ ownership、≠ AI Candidate、≠ Native Selection；
  永远不是 Evidence 扩展的硬边界；
- 策略身份 `seed-policy/experimental-v*` 先行，校准后显式换 key 晋升生产。

Core Target 分母：从种子起步，单调扩张（共识/证据驱动增长，target 生命周期内
永不收缩）。影子评估期并行报告种子基与全 Target Splat 基两个 coverage 数。

---

# 5. Evidence-Internal Depth 与 N 的深度分类

在 Direct Evidence 内核家族内增加两个内部读出（同一接受序列、同一
`alpha × T`，遵守 Same Decision Source 不变量；禁止独立近似重光栅化）：

1. **期望深度通道**：`Σ wᵢ·zᵢ / Σ wᵢ`，供种子一致性过滤与邻接门控消费；
2. **共识 soft mask 读出**：按 Gaussian 当前共识状态加权的着色 pass，
   仅供 Companion 内 residual 计算（§7）。

两者均为内核内部量，**不发布独立协议产物**。权威整帧渲染深度
（几何可见性协议产物）不在本版本范围内；若覆盖度/效用分支未来证明需要，
作为独立 seam 另行立项。

**Negative Mass 深度分类**：N 区分两类反证据——贡献落在局部表面**前方**
（泄漏/floater）与落在表面**后方**（物体边缘露出的真实背景）。此为对 v1.3
单一 N 通道的原位语义修订；Reliability Weighting 消费分类后的 N。
深度分类不得把 Mask 不信任变成"未观察"。

---

# 6. 采集循环

## 6.1 职责分离

```text
Observation Coverage / View Diversity   描述已获得的观测（realized）
View Utility                            评估候选相机的预期边际价值（prospective）
Lift Readiness                          裁决当前证据是否足以发布 Candidate
```

三者各自独立版本化；planner 消费 readiness reasons 但不得接管发布权。

## 6.2 观测起点与候选池

- Confirm 后首个 View 由确定性规则选出（hint 投影尺寸最大的 feasible 候选；
  此时共识不存在，utility 无从打分——这是技术边界而非特例通道）；
- 其后所有 View 由 View Utility 从**分层候选池**中选择：现有 hint-offset
  机制 + hint 中心局部球面采样，统一过既有 feasibility 门（裁剪、投影尺寸、
  hint 可见性、非空 RGB 门）；层组合可消融；
- 一个 Included 发布即触发候选重评分（逐 View 增量）。

View Utility 校准范围：Core Target 分母上的预测边际 Visible Mass 增益、方向
多样性增量、重复惩罚、feasibility/cost；语义消歧类条款等 Reliability 建立
Uncertain 态后再评估。策略必须版本化、确定可重放、tie-break 确定。

## 6.3 预算与停止

双预算：View 数硬上限 + 时延/成本上限，任一耗尽即停；数值全部校准期决定。

失败语义：失败 View 不消耗 View 预算；同阶段连续失败达到小上限触发有界
替换（次优 utility 候补）；替换亦连续失败则触发阶段熔断。

停止原因工作集（canonical 命名随 domain modeling 收口）：
`ready-and-low-marginal-gain`、`marginal-gain-exhausted`、
`view-budget-exhausted`、`cost-budget-exhausted`、`no-feasible-view`、
`stage-failure`、`stale/cancelled/suspended`。

## 6.4 终止与发布

- 达到 Ready 不立即停机：增益门槛收紧，继续采到边际增益跌破收紧阈值；
- 正常终止 `ready-and-low-marginal-gain`：**自动原子发布 Candidate**
  （同意结构变更，ADR 0020）；Candidate 永不自执行 Native 操作；
- `Limited` + 预算耗尽：发布 readiness + 结构化原因，**不发布 Candidate**；
  用户显式 Re-Lift 后 Limited 可发布（沿用现状，显式同意）；
- 显式 Re-Lift 保持 v1.3 语义：对 exact current Evidence 重评估并尝试原子
  发布；不重启采集；stale 身份发布 stale 而非 Candidate。

---

# 7. Provisional 3D Consensus 与 Observation Reliability

## 7.1 Provisional 3D Consensus

Companion-local 可弃派生态，每次 Included 发布修订一轮。只喂 planner、
reliability、加权聚合；永不可执行 Native Set/Add/Remove/Intersect；不留跨
target 历史；不是 Candidate。不作为正式产物跨边界；replay 依赖 Companion 侧
digest/journal。新 View、Stable Mask revision 或 Participation 变更使依赖它的
consensus/reliability/readiness stale。

## 7.2 Reliability

- 定义：比较共识 soft mask（该 View CameraBinding 下）与其 Stable Mask 的
  residual，得到 view-level 版本化权重；
- residual：可见性门控逐像素 BCE（只在透射率可信像素上计算）+ 独立边界带
  残差；IoU 仅诊断；
- **作用域：只调节 P/N 语义 mass；raw `V` 不加权，保真用于 realized
  Observation Coverage**——Mask 不信任永远不得变成"未观察"；
- reliability 不静默修改 Stable Mask、不等价于 Participation、不能单独触发
  Excluded；低权 View 保持可检查并携带具体 residual/原因；
- User Confirmed / 手动编辑的 Stable Mask 豁免自动降权（用户意图高于内部
  共识）；Review 态 View 走标准流程；
- 防自我确认护栏（参数校准后定）：lagged consensus（第 k 轮权重来自 k−1 轮
  共识）、warm-up uniform 权重、非零 `r_min` 下限、frontier 新增前景降罚保护、
  高置信区矛盾正常惩罚、最大修订轮数上限；
- region/per-pixel 权重粒度需基准证据后才升级。

## 7.3 加权聚合

聚合消费：不可变 per-View Direct P/N/V（含深度分类 N）、view-level
reliability 权重、既有聚合政策修订版。Missing/unusable 观测保持 unobserved
而非负证据。

---

# 8. 编排、attempt 与生命周期

- 整个采集循环是一个 attempt；exact same-attempt replay 要求保留；
- Cancel 立即生效；已完成 Views/Stable Masks/raw Evidence/旧 Candidate 全部
  保留可检视；
- suspend/resume 只允许 View 边界；依赖变更使挂起态 stale，不得静默续跑；
- progressive publication 只发独立完整、身份正确的 AI View；
- iteration 失败保留一切独立有效产物；late result 不覆盖更新后的依赖身份；
- Native Selection 不随内部 consensus revision 自动变化。

---

# 9. 身份体系

纳入 exact-key 校验 + checksum 绑定的新身份（统一 experimental-v\* 先行、
校准后显式换 key 晋升）：

- conservative seed policy；
- soft-mask renderer 实现；
- consensus identity；
- reliability weight policy；
- View Utility policy；
- 加权聚合修订版。

Evidence-Internal Depth 属 Direct Evidence 实现身份的一部分，随其绑定。

---

# 10. UI

- 循环运行中呈现最小状态面：当前阶段（第 k 个 View / 评估中）、既有 View
  inspector 入口、终止停止原因、readiness 状态；实时 coverage/utility 数字
  不进默认呈现（诊断模式可在校准期暴露）；
- 专属 Cancel 控件终止当前循环（立即生效、保留产物）；它不是已退役 planning
  控件的复活——无常驻 Stop/Generate More 的约束保持；循环结束后是否提供
  "继续采集"是未设的产品决定；
- **User-added View 移除**：Anchor 是唯一用户放置相机；Generated View 上的
  手动 Mask 编辑保留并适用 User Confirmed 豁免。

---

# 11. 验证门

本轮只定指标族与门槛结构，数值留校准：

1. 质量：对冻结 fixed-four 基线的 Selected 对比、手动纠错操作数；
2. 系统：每目标 View 数分布、端到端时延、GPU 成本；
3. 校准：predicted vs realized gain 偏差（喂 utility/reliability 校准）；
4. 消融：seed on/off、reliability on/off、迭代深度、候选池分层。

全部挂锁定的 GPU 门，沿用既有 benchmark 记录格式。

---

# 12. 未决项清单（不阻塞接受，阻塞晋升生产）

- 种子 precision 阈值、邻接 k、residual 混合比、warm-up 轮数、`r_min`、
  收紧后的增益阈值、双预算数值、最大修订轮数；
- 停止原因 canonical 命名收口；
- 影子期双 coverage 报告的偏差容忍度；
- "继续采集"控件的产品决定。
