# AI View Dock 布局设计

状态：**当前可复用合同 — Tickets 16D、16E、16G 已实现**

本文记录 Ticket 16G 闭合后的 AI View Dock。它取代 Ticket 16A 历史基线中关于永久标题、Action Bar、Proposal、显式 recovery 和 persistent planner controls 的描述。

## 目标

Dock 是连续的 2D 观察与修正工作台：

`Navigator → selected-View Work Area → current-View Inspector`

权威 RGB/Mask canvas 始终是视觉焦点。导航、状态和解释保持紧凑；Native Candidate Operations 留在主 3D Toolbar。

## 三栏结构

| 区域      | 拥有                                                                        | 不拥有                                                                |
| --------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Navigator | View 选择、filter/sort、缩略图、优先状态 badge、初始 planning failure retry | Prompt/Mask 编辑、Participation mutation、persistent planner commands |
| Work Area | 权威 RGB、Mask overlay、浮动 palette、Re-Lift、必要的 Next Review 导航      | View 集合管理、Native Candidate Operations、bottom Action Bar         |
| Inspector | Assessment、Participation、Prompt/Mask 状态、technical details              | 主操作、重复 recovery controls、第二个 Participation toggle           |

Dock 不渲染 Dock-wide status header、selected-work header 或 bottom Action Bar。

## 尺寸与响应式

- Navigator 默认约 `220px`，范围 `180–280px`。
- Inspector 默认约 `280px`，范围 `240–360px`。
- 多余宽度和高度属于 Work Area；侧栏保持单列。
- 图像使用完整、居中、等比 contain，保留小安全边距；不得 crop 或 stretch。
- Wide 和约 `1280×720` 显示三栏。
- 约 `1024×720` 保留 Navigator + Work Area，并先折叠 Inspector。
- 更窄时 Work Area 常驻；侧栏展开时推挤画布而不是覆盖。
- Dock 默认高度 `420px`，最小 `300px`，最大为编辑区域高度减 `160px`。
- 手动 zoom 在 resize 后保留，直到显式 Reset Fit。
- 宽度、展开状态和 Dock 高度只存本机 editor preference，不进入项目或领域 identity。

## Navigator

标题行只有 Navigator 和相邻 collapse control。下方一个紧凑 trigger 打开两个 radio groups：

- Filter：All、Needs Review；
- Sort：global creation order、newest first、Needs Review first。

默认顺序是 Anchor、Generated 和 User-added Views 的严格全局创建顺序。选择 View 不改变顺序；filter/sort 只改变 presentation projection。当前 View 不匹配时选中第一个匹配项；没有匹配项显示 filter-empty state。

每个 item 是全宽 `16:9` 缩略图：

- Anchor 使用 overlay pin；
- badge 优先级为 failure、Needs Review、processing、ready；
- Excluded 降低强调但保持可检查；
- selection 使用 inset outline；
- 卡片不显示多行 Quality、Mask、role 或 Participation 元数据。

### 初始规划

初始 planner 一次调度 `4–8` 个固定 local-offset automatic Generated Views，不含 Anchor 和 User-added Views；有效性失败可能留下更少 usable Views。

Navigator 不提供 Stop、Continue、Generate More 或 Regenerate Plan。仅初始 planning 失败时显示一个 failure-only retry icon；该动作创建新的 bounded planning attempt。Anchor 和已完成 Views 不被 planning/loading/failure empty state 覆盖。Companion batch/ordinal protocol 保留为内部扩展基础。

## Work Area

Work Area 不保留永久 selected-View 标题或底部 Action Bar。它包含：

1. aspect-preserving RGB/Mask surface；
2. 图像内可拖动、吸附、折叠的 Prompt/Edit palette；
3. 图像外上方少量 target-level chrome，包括 Re-Lift 和 Reset Fit；
4. 仅在有其他待审 View 且当前无 authoring primary 时出现的 Next Review 导航。

浮动 palette 提供：

- Positive Point、Negative Point、Positive Instance Box；
- Paint、Erase 和 brush size；
- Prompt 或 Mask-local Undo/Redo/Clear；
- Confirm Mask / Confirm Review / Confirm Anchor 的稳定 confirmation slot；
- Correction 与 Back to Candidate 的稳定 context slot；
- Restore Auto Mask。

每个 operator Prompt inference 最多产生一个 usable result，并自动成为 Editing Mask；没有 Proposal carousel/count/Accept。已审阅 automatic Generated-View result 可直接成为 Stable Mask，后续 correction 才建立独立 Editing draft。

Re-Lift 是唯一强调的 target-level action。它映射 Ticket 13 Lift Readiness 和 Ticket 15 Candidate lifecycle，不在 3D Toolbar 重复。

## Inspector

Inspector 纵向显示：

- Assessment 和 actionable Review reasons；
- Participation 只读结果和 blocker；
- Prompt、Editing Mask、Stable Mask 与 Evidence 状态；
- 默认折叠的 technical details。

Inspector 不提供 Retry Render、Regenerate Prompt、Retry Mask、Retry Auto Segmentation 或其他 identical-input recovery。Restore Auto Mask 属于 palette，不在 Inspector 重复。

## Failure 与恢复

- failed Generated/User-added render 保持可检查、failed、Excluded；添加 replacement View 是支持的产品恢复。
- Prompt/Mask failure 保留 RGB 和 prior Stable Mask；改变 PromptState 会创建 normal new intent，或使用 Paint/Erase 手动修正。
- Anchor render failure 通过改变或 Reset pose 后启动 normal render intent。
- semantic unavailable 与 technical failure 分开显示。
- failed Candidate replacement 保留 prior stale Candidate；Re-Lift 仍通过原子 publication gate。
- service unavailable/incompatible 保留 local inspectable work，并把原因投影到真实 action；不增加 duplicate Dock availability header。
- target disposal 释放 target-local transient state，late result 由 identity mismatch 拒绝。

## Accessibility

- 所有交互命中区域至少 `40×40px`；icon button 有 tooltip、accessible name 和 visible focus。
- Thumbnail、collapse/restore、filter/sort、planning retry、Reset Fit 和 palette 支持键盘。
- Popover 支持 Escape/outside click，关闭后恢复焦点。
- disabled reason 不只依赖 hover 或颜色。
- sidebar transition 只使用 transform/opacity 并遵守 reduced motion。
- 普通 navigation、filter、collapse、resize 不丢失 drafts、history、selection 或 scroll。

## 状态走查矩阵

必须在 wide、`1280×720`、`1024×720` 走查：

- service unavailable/incompatible；
- no Target；
- planning、planning failure、RGB Ready；
- confirmed/unconfirmed Mask、Review、Excluded；
- Candidate current/stale/updating/failed；
- Anchor adjustment；
- filter-empty；
- collapsed Navigator/Inspector。

走查同时确认 canvas priority、无重叠、图像 fidelity、禁止控件不存在，以及 planning retry 仅出现在 failure state。

## 禁止面

- 无 Proposal choice/accept；
- 无 persistent planning controls；
- 无 explicit Render/Prompt/Mask recovery commands；
- 无 permanent Dock header、selected-work header 或 bottom Action Bar；
- 无 Native Set/Add/Remove/Intersect；
- 无新 UI framework、icon library、font 或 theme。
