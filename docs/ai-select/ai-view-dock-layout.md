# AI View Dock 布局设计

状态：**已确认设计，尚未实现**

本文定义 AI View Dock 的目标布局、信息归属、响应式行为和验收条件。它不改变 AI Select Final Spec v1.3 的 Prompt、Mask、View、Evidence、Candidate 或 Native Selection 语义。

视觉线框见 [AI View Dock accepted layout](show-me-ai-view-dock-layout.html)。

配套的主视口操作设计见 [AI Select Toolbar 布局与交互设计](ai-select-toolbar-layout.md)。

## 解决的问题

当前 Dock 使用固定左右布局。右栏名义宽度为 `340px`，最多占主区域的 `45%`；图像在剩余区域内等比居中。面板较宽但高度有限时，图像两侧会出现较大空白，右栏同时混合 View 状态、Gallery、Mask 操作、Candidate 操作和失败恢复入口。

新设计需要满足以下结果：

- View Review、Prompt 编辑和 Mask 编辑在同一个工作区内连续完成。
- 图像保持完整、等比、无裁切和无拉伸，并成为唯一视觉焦点。
- 操作按作用对象分区，不把 View、View 集合、Candidate 生产和 Native Selection 操作混在同一栏。
- `1280×720` 提供完整三栏体验；约 `1024px` 宽时仍保留 Navigator 和图像编辑能力。
- View 切换、过滤、侧栏折叠和面板 resize 不丢失 Editing Mask、Prompt、Proposal 或历史状态。

## 范围

本文覆盖：

- Dock 顶栏；
- AI View Navigator；
- Selected AI View Work Area；
- 当前 View Inspector；
- Candidate 生产状态；
- View 生成命令的渐进披露；
- 宽度、高度、滚动、键盘和焦点行为；
- UI 实现的验证矩阵。

本文不重复定义：

- AI Select 子工具栏的最终布局；
- `Set`、`Add`、`Remove`、`Intersect` 的最终控件形态；
- 主 3D 视口中的 Candidate/Uncertain 可视化；
- Selection Service、协议、SAM 3、Evidence 或 lifting 算法变更。

## 交互模型

Dock 不按「View Review」「Prompt/Mask 编辑」「Candidate 应用」切换页面。View Review 和编辑是同一个循环：

```text
在 Navigator 选择 AI View
→ 查看权威 RGB、Mask 和 Assessment
→ 满意：确认或调整 Participation
→ 不满意：修改 Prompt 或 Editing Mask
→ Confirm Mask
→ 显式前往下一张 Needs Review View
```

Gallery 是 Navigator，不是独立工作阶段。Anchor View、Generated View 和 User-added View 使用同一个 Selected AI View Work Area；Anchor 保留自身的确认语义。

## 信息和操作归属

| 区域                       | 负责                                                                           | 不负责                                      |
| -------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------- |
| 紧凑顶栏                   | AI Select Availability、Candidate 生产状态、Included View 摘要、一个上下文动作 | Native Candidate Operations                 |
| AI View Navigator          | View 选择、过滤、Assessment 摘要、Participation、View 集合状态                 | 当前 View 的 Prompt/Mask 编辑和低频恢复操作 |
| Selected AI View Work Area | 权威 RGB、Prompt、Editing Mask、浮动工具栏和 View 主操作                       | View 集合管理和 Native Selection            |
| 当前 View Inspector        | 当前 View 的 Review 原因、状态解释、只读 Participation、次级和恢复操作         | 主操作、重复的 Participation 开关           |
| AI Select Toolbar          | 主 3D 视口交互和 Native Candidate Operations                                   | View Review 和 2D Prompt/Mask 编辑          |

## 布局

### 宽屏布局

```text
┌──────────────────────── 紧凑顶栏 ────────────────────────┐
├──────────────┬──────────────────────────┬─────────────────┤
│ View         │ Selected AI View         │ Current View    │
│ Navigator    │ Work Area                │ Inspector       │
│              │ RGB/Mask + 浮动工具栏    │                 │
└──────────────┴──────────────────────────┴─────────────────┘
```

- Navigator 的实现起始范围为 `190–238px`。
- Inspector 的实现起始范围为 `280–350px`。
- Work Area 不无条件占用全部剩余宽度。图像高度、权威 RGB 宽高比和侧栏约束共同决定理想宽度。
- 图像继续使用 contain 语义：完整显示、等比缩放、居中，不使用 crop 或 stretch 消除空白。
- Dock 使用完整容器宽度，不在最大化窗口中居中保留固定舞台外边距。
- 多余横向空间优先分配给 Navigator 和 Inspector 的有效内容；宽于约 `1600px` 时，Navigator 卡片和 Inspector 分组可使用多列，而不扩大无信息的图像字母箱区域。
- 宽于约 `1600px` 时采用 `20% Navigator / 55% Work Area / 25% Inspector` 的职责比例；Work Area 保持最大份额，Navigator 小于 Inspector。
- 精确阈值由容器尺寸和浏览器走查校准，不以浏览器窗口宽度代替 Dock 实际宽度。

### 响应式退化

布局按 Dock 容器宽度退化：

1. 宽：Navigator、Work Area、Inspector 三栏同时显示。
2. 中：Navigator 和 Work Area 常驻；Inspector 折叠。
3. 窄：Work Area 常驻；Navigator 和 Inspector 均可折叠。

折叠侧栏展开时推挤 Work Area，不覆盖图像。`Esc`、关闭按钮或再次点击触发按钮均可收起侧栏。收起后焦点返回触发按钮；当前 View、草稿和各区域滚动位置保持不变。

约 `1024px` 宽时 Navigator 必须常驻。Navigator 仅在低于目标支持范围的窄宽条件下折叠。

### 高度和滚动

- 默认高度：`420px`。
- 最小高度：`300px`。
- 最大高度：主编辑区域高度减 `160px`。
- 首次打开和窗口尺寸变化时立即限制高度。
- 用户调整后的高度保存在当前设备的编辑器偏好中，不进入项目数据。
- 顶栏、图像和 View Action Bar 固定；Navigator 与 Inspector 分别纵向滚动。
- 图像不进入滚动容器。

## 紧凑顶栏

Dock 标题、Availability 和 Candidate 生产摘要合并为一条顶栏：

```text
AI Select · Available    Candidate stale · 4 Included    Update 3D Candidate
```

顶栏最多显示一个上下文动作：

| 状态                              | 动作                    |
| --------------------------------- | ----------------------- |
| 尚无 Candidate 或 Candidate stale | `Update 3D Candidate`   |
| 正在更新                          | `Updating…`，不显示按钮 |
| Candidate current                 | `Fix AI Result`         |
| 更新失败                          | `Retry Update`          |
| Correction 且 Stable 输入未变化   | `Back to Candidate`     |

`Back to Candidate` 保留每张 View 的 Editing Mask 草稿，不执行 Confirm 或 discard。Stable 输入已经变化时，Candidate 保持 stale，并显示 `Update 3D Candidate`。

`Show AI Result`、`Set`、`Add`、`Remove` 和 `Intersect` 不属于 Dock。

## AI View Navigator

### 当前 View 和过滤

- 当前 View 固定显示在过滤结果上方，并标记 `Current`。
- 当前 View 不在过滤结果中重复出现。
- 默认过滤控件为 `All Views ▾`。
- `Review N` 是唯一常驻快捷过滤入口。
- All、Included、Excluded 和 Needs Review 过滤只改变列表显示，不修改 View、Mask、Participation、Evidence 或 Candidate。

### View 卡片

卡片只显示影响导航和判断的信息：

- 缩略图；
- View 名称和来源；
- Assessment；
- Participation；
- `Editing` 草稿标记；
- 阻止继续工作的错误。

Participation 开关只存在于 Navigator 卡片。Inspector 只显示 Participation 结果和不可 Include 的原因。

Retry、Inspect、Regenerate Prompt、Refresh Mask 等操作不在每张卡片内重复出现；这些操作属于当前 View Inspector。

### View 切换和草稿

普通 View 切换保持现有 per-View 行为：

- Editing Mask 保留且不自动 Confirm；
- 未接受的 Proposal 和当前 Proposal 预览保留；
- Prompt 及 Prompt/Mask Undo/Redo 历史保留；
- 进行中的 SAM 请求继续，并把结果写回对应 View session；
- 尚未原子提交的当前 Pointer gesture 取消。

普通切换不弹出确认框。Restart、Regenerate 或移除 View 等会销毁状态的操作必须明确说明影响，并在需要时确认。

### View 集合状态

集合级状态显示在 Navigator 标题下方：

```text
Planning       Generating views 2 / 3… · Stop
Failed         <简短原因> · Retry
Plan exhausted No more planned views
```

`Generate More`、`Stop` 和 `Regenerate` 不常驻：

- Lift Readiness 因 Coverage 或 View Diversity 不足且 planner 仍有容量时，显示 `Generate More` 建议；更多菜单保留同一能力。
- `Stop` 仅在生成过程中显示。
- `Regenerate Auto Views…` 位于更多菜单，并在执行前说明 planner-owned Views 会被替换、User-added Views 会被保留。

Anchor 和已完成 View 不因 Planning、Failed 或 plan exhausted 状态被空态覆盖。

## Selected AI View Work Area

### 结构

Work Area 包含：

1. 约 `28px` 高的轻量 View 标题行，显示名称、来源和 Assessment；
2. 权威 RGB、Prompt、Mask overlay 和 Box preview；
3. 图像内可拖动、自动吸附、可折叠的浮动工具栏；
4. 图像下方只在存在上下文恢复动作时显示的 View Action Bar。

浮动工具栏暴露 Positive Point、Negative Point、Positive Instance Box、Paint、Erase、Mask 历史、确认 Mask 和重置为自动 Mask。拖动和吸附只改变呈现状态，不进入 Prompt、Mask 或项目数据。

### 单结果 Mask

每次 Prompt 推理最多返回一个可用 Mask 结果：

```text
Prompt → 单个自动结果 → Editing Mask → Confirm Mask → Stable Mask
```

- Companion 固定 `multimask_output=false`，浏览器拒绝超过一个结果的响应。
- 唯一可用结果自动成为 Editing Mask，不显示 Proposal 轮播、计数、下拉框、模型分数或接受按钮。
- 继续添加 Prompt 时，唯一结果的 opaque logits ref 可作为 refinement lineage；Retry 仍显式丢弃该 lineage。
- `Confirm Mask` 在浮动工具栏内发布 Stable Mask；若当前 View 是未确认 Anchor，同一动作继续 Anchor 确认并启动 Generated View 规划。

### 主操作

每个状态只显示一个主操作：

| 当前状态         | 主操作或恢复动作          |
| ---------------- | ------------------------- |
| Editing Mask     | 浮动工具栏 `Confirm Mask` |
| Auto Review      | `Confirm As Is`           |
| Mask 失败        | `Retry Mask`              |
| 当前 View 已完成 | `Next Review`             |

无关操作隐藏。只有操作存在但暂时被阻止时才禁用，并紧邻显示原因。
没有任何主操作时，View Action Bar 整体隐藏并把高度还给图像。

`Next Review` 不自动执行。按钮和键盘快捷键显式前往下一张 Needs Review View；具体按键需要在实现时完成现有快捷键冲突审计，并显示在 tooltip 中。

## 当前 View Inspector

Inspector 只承载当前 View 的解释和次级操作：

- Assessment 和 Review reason；
- 只读 Participation 和不可 Include 的原因；
- Prompt、Stable Mask 和 Editing Mask 状态；
- Retry、Refresh、Inspect Camera 等低频或恢复操作；重置为自动 Mask 留在浮动工具栏；
- 默认折叠的 technical details。

Inspector 不重复 View Action Bar 的主操作，也不提供第二个 Participation 开关。

## 视觉系统

- 延续 SuperSplat/PCUI 的深灰表面和现有字体，不引入新的字体或独立主题。
- 以 4px 为基础间距单位；控制区使用 `8–12px` 的紧凑间距。
- 图像和 Mask 是唯一焦点。层级主要通过字重、文本明度和空间建立，不依赖高对比边框。
- 橙色保留给主操作和既有 SuperSplat 高亮语义。
- Positive Point、Negative Point、Paint 和 Erase 保留现有绿色、红色、橙色和青色语义。
- Assessment、错误和不可用状态使用项目现有 semantic colors，不增加装饰性色彩。
- 深色界面使用低对比边界和轻微表面明度差分层，不混用新的阴影体系。
- 交互控件的有效 hit area 不小于 `40×40px`；焦点环、hover、active、disabled 和 loading 状态必须完整。
- 动画只用于折叠侧栏和低频 popover，使用 transform/opacity，并遵循 `prefers-reduced-motion`。

## 键盘和焦点

- Navigator 使用 roving focus；方向键移动焦点，`Enter` 选择 View。
- Participation 是独立按钮，不借用卡片的选择操作。
- View 切换后焦点保持在 Navigator，不自动跳进图像区。
- 浮动工具栏、View Action Bar、Inspector 和侧栏触发按钮均可键盘操作。
- `Esc` 收起 Inspector，并把焦点还给触发按钮。
- Dock resize handle 保留方向键调整能力。
- 快捷键在文本或数值输入获得焦点时不触发。

## 验证

### 尺寸矩阵

- `1280×720`：完整三栏布局；
- `1024×720`：Navigator 与 Work Area 常驻，Inspector 可折叠；
- 窄宽条件：Navigator 和 Inspector 均可折叠，Work Area 保持可用。

### 状态矩阵

- Anchor Proposal；
- Generated View Auto Review；
- Editing Mask 草稿；
- Planner Planning、Failed 和 plan exhausted；
- Candidate current、stale 和 updating；
- Companion unavailable；
- Inspector 和 Navigator 折叠、恢复及焦点返回。

### 实现验证

UI 实现至少需要：

- 为列模式、图像理想宽度和 Dock 高度 clamp 增加纯逻辑测试；
- 更新样式契约测试，移除固定 `340px / 45%` 两栏假设；
- 增加 View A 草稿 → View B → View A 的显式保留测试；
- 验证当前 View 在过滤后仍固定可见；
- 验证 Proposal stepper、单一主操作和 Candidate 顶栏状态投影；
- 验证 0/1/多个 Proposal 分别隐藏、仅显示接受动作、显示相册式切换；
- 在尺寸矩阵和状态矩阵下保存浏览器截图或走查记录；
- 运行 `rtk npm test`、`rtk npm run lint`、`rtk npm run lint:locales` 和 `rtk npm run build`。

纯布局改动不建立生产 GPU 正确性；若实现同时改变 Generated View、Evidence 或 lifting 行为，必须另行执行对应的锁定 GPU 验证。

## 实现路由和已知差异

主要实现入口预计包括：

- `src/ui/ai-select-anchor-dock.ts`；
- `src/ui/ai-select-floating-palette.ts`；
- `src/ui/ai-select-toolbar.ts`；
- `src/ui/editor.ts`；
- `src/ui/scss/ai-select.scss`；
- `src/ai-select/image-viewport.ts`；
- 对应 presentation、locale 和 test 文件。

布局状态不得进入模型请求、PromptState、Mask artifact、Evidence 或 Candidate identity。

已实现的 Ticket 16 保留其关于 Dock 操作和最小 Candidate 状态强调的历史闭环证据。Ticket 16A 使用本文和配套 Toolbar 设计作为当前 UI 验收合同，一次实现完整 Dock 布局、真实 Candidate Overlay、固定 Toolbar、Status Bar 状态和 Dock 旧操作移除。

当前 `Show AI Result` 只调整 Dock Candidate 状态文字的 emphasis，没有连接主 3D 视口 Overlay。Ticket 16A 不迁移该旧按钮，而是以非破坏性 3D Candidate Overlay 取代它。

本次布局决策可逆，不满足 ADR 的「难以逆转」条件，因此不创建 ADR。
