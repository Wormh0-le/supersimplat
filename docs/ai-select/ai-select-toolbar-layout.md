# AI Select Toolbar 布局与交互设计

Status: Ticket 16A 已实现的历史合同 — 16F/16G 正在修正人工视觉走查发现项

> Ticket 16A 完成后的人工视觉走查不接受本文的最终 Toolbar 呈现。
> Candidate Overlay 和 Native Candidate Operations 的职责仍然有效；与
> `docs/ai-select/tickets/16F-*`、`16G-*` 冲突的文字标签、More、Restart、
> Exit 和布局要求已由后续 Ticket 取代。当前 3D 子工具栏不含 More、
> Restart 或 Exit；Ticket 17 将 `选择另一个对象` 放在全局 AI Select
> 生命周期菜单中。

本文记录 Ticket 16A 的 AI Select Toolbar Candidate 展示、Native Candidate Operations 和 Correction 跳转设计。AI View Dock 的对应历史基线见 [AI View Dock 布局设计](ai-view-dock-layout.md)。

已接受 Q34–Q65。Toolbar 交互设计、相邻 Ticket 所有权、交付方式和验收边界已闭合。Ticket 16A 承载 Ticket 16 完成后新增的完整 AI View Dock 布局、视口展示与表面迁移范围。

## 解决的问题

现有 `AISelectToolbar` 负责 Anchor 和 Camera Inspection。Set、Add、Remove、Intersect 与 `Show AI Result` 位于 Dock，导致主视口操作和 2D View/Mask 编辑混在同一表面。

新设计需要满足以下目标：

- Native Candidate Operations 在主 3D 视口附近执行；
- Dock 保持 View Review、Prompt/Mask 编辑和 Candidate 生产职责；
- Candidate 与 Native Selection 在视口中可区分；
- Correction 跳转明确区分 Native Undo 与 2D 编辑职责；
- Toolbar 保持单行和单一焦点，不永久堆叠所有操作。

## 交互方向

Toolbar 使用上下文式单行布局。它是主 3D 视口上方的固定子工具栏，与 Box Select 和 Sphere Select 的子工具栏属于同一类型，不可拖动。它不是按业务流程分页，而是投影当前主视口交互对象所需的控制。

优先级从高到低为：

1. Camera Inspection 或 User View Draft；
2. 可检查的 Candidate；
3. Anchor 和 View 建立操作。

高优先级上下文出现时，低频操作进入 `More`，不增加第二行 Toolbar。

## Candidate 操作组

Candidate 操作组是固定 AI Select Toolbar 内的一组控件，不是独立控件、第二条工具栏或可拖动面板。它连接 Candidate 与 Native Selection，至少包含：

- Candidate Overlay 控制；
- Set、Add、Remove、Intersect；
- 满足条件时的 `Undo and Fix`。

Candidate 操作组只投影共享 Candidate controllers 的状态，不复制 Candidate、Correction 或 Application 状态。

Candidate 操作组的显示遵循以下规则：

- 尚未请求 Candidate 时不显示；
- 首次 Candidate 更新开始后，只在 Status Bar 显示状态，尚不显示无可操作内容的 Candidate 操作组；
- 一旦存在可检查 Candidate，操作组在 current、stale、updating、update failed、correcting 和 applied 之间保持位置稳定；
- 状态变化只更新 Overlay 样式、控件 enablement 和禁用原因，不重新排列整个 Toolbar。

Candidate 上下文不在操作组前重复显示 `AI Select` 标签。固定顺序为：

`Overlay 👁 ▾ | Set | Add | Remove | Intersect | Undo and Fix* | More`

`Undo and Fix*` 仅在存在相关 Application 记录时出现，并在窄屏时进入 `More`。

## Native Candidate Operations

Set、Add、Remove、Intersect 沿用 Box Select 和 Sphere Select 的四按钮语法。按钮点击后立即执行对应集合运算，并通过 Native EditHistory 记录可撤销命令。

Toolbar 不增加「先选运算，再 Apply」步骤，也不为可撤销操作增加确认对话框。四种操作共享 Candidate applicability gate。

禁用原因按用户可执行的恢复动作归类，而不是在主界面展开底层 blocker 枚举：

- 等待当前更新完成；
- 回到 AI View Dock 完成或退出 Correction；
- 在 Dock 中更新 3D Candidate；
- 重新开始当前 Target。

四个按钮显示同一条精简禁用原因；精确技术原因仅放在 tooltip 或详情信息中。

Candidate 应用成功后，四个按钮继续可用。每次点击生成独立的 Native EditHistory command；Toolbar 显示最近一次操作，`Undo and Fix` 只关联最近一次 Candidate application。

四种操作是本地、可撤销且通常即时完成的 Native Selection command。主视口中的 Native Selection 高亮变化是成功的主要反馈；Toolbar 不为正常路径增加 spinner、逐动词进行时或持久进度 UI。执行期间仍需阻止重复提交，异常失败必须保持 Native Selection 和 Native EditHistory 不变。

异常失败只显示一条简短的非模态提示，说明 Native Selection 未改变，然后立即恢复四个按钮。失败不会在 Dock 建立重复操作或持久 application failure 状态。

## Candidate Overlay

`Show AI Result` 不再表示 Dock 文本 emphasis。该能力改为真正、非破坏性的主 3D 视口 Candidate Overlay。

Candidate Overlay 与 Native Selection 相互独立：

- 显示或隐藏 Overlay 不修改 Native Selection；
- 显示或隐藏 Overlay 不写入 Native EditHistory；
- 只有 Set、Add、Remove、Intersect 可以把 Candidate 应用到 Native Selection。

现有 `SplatOverlay` 直接读取 Native `splatState`，因此 Candidate Overlay 必须使用独立的瞬态 Candidate membership GPU 状态。实现可复用现有 splat 排序、变换和 Overlay 绘制基础设施，但不得借用 selected、locked 或 deleted 位，也不得通过临时修改 Native Selection 实现预览。

Overlay 包含以下图层：

- Candidate Selected：默认显示；
- Uncertain：可选诊断图层，位于 Overlay 展开菜单，默认关闭。

Overlay 使用拆分控件：主按钮的眼睛图标直接显示或隐藏 Candidate Selected，相邻箭头展开菜单。菜单提供 Uncertain 复选项、图例和对应数量，不把 Uncertain 移入 `More`。

Overlay 遵循以下生命周期：

- Candidate current 时默认显示；
- Native Candidate Operation 执行期间保持当前显示状态；
- 操作成功后自动隐藏，使 Native Selection 成为视口焦点；
- 操作失败时保持原显示状态；
- 用户可以通过 Toolbar 的 Overlay 控制重新显示 Candidate；
- Candidate stale 时保留旧 Overlay，但使用降饱和或纹理化样式；
- Candidate updating 时继续显示旧 stale Overlay，直到新 Candidate 原子发布；
- stale 或 updating Candidate 不可应用。

显示或隐藏 Overlay 是 presentation state，不进入项目数据、Candidate identity 或 Native EditHistory。

Candidate 可见性按 Candidate revision 管理：

- 新 Candidate 发布时自动显示；
- Candidate 应用成功后自动隐藏；
- 用户对可见性的修改只覆盖当前 Candidate revision。

Uncertain 图层偏好在当前 Target 内延续，`Restart Current Target` 后恢复默认关闭。

## Correction 所有权

| 操作                  | 所属表面 | 语义                                                      |
| --------------------- | -------- | --------------------------------------------------------- |
| `Fix AI Result`       | Dock     | 在应用前进入 View、Prompt 和 Mask Correction              |
| `Back to Candidate`   | Dock     | 保留未发布草稿，无损退出 Correction                       |
| `Update 3D Candidate` | Dock     | 使用当前 Stable 输入显式更新 Candidate                    |
| `Undo and Fix`        | Toolbar  | 安全撤销关联的 Native command，再展开或聚焦 Dock 进入修正 |

`Undo and Fix` 在 Candidate Applied 状态直接显示。关联 Native command 位于 Native EditHistory 顶部时启用；发生后续 Native edit 后保留但禁用，并说明「应用后 Selection 已更改，请使用普通 Undo 或重新应用」。它不遍历或跳过后续 Native EditHistory。

普通 Native Undo/Redo 需要更新 Application 状态：

- Undo 撤销关联 command 后，状态为 `Application Undone`，重新显示 Candidate Overlay，并恢复四种操作；
- Redo 恢复关联 command 后，状态回到 `Applied`，并再次隐藏 Candidate Overlay；
- 后续 Native edit 不会使 Candidate stale，但会把 Application 标记为 `Diverged`，并禁用 `Undo and Fix`。

## Dock 与 Toolbar 的共享状态

Dock 和 Toolbar 使用同一个 presentation mapper，组合 Candidate Publication、Correction 和 Application 状态。两个表面不得各自维护 Candidate 状态副本。

统一状态词包括：

- `No Candidate`；
- `Updating`；
- `Current`；
- `Stale`；
- `Update Failed`；
- `Correcting`；
- `Applying`；
- `Applied`；
- `Application Undone`；
- `Diverged`。

Dock 负责 Candidate 生产动作，Toolbar 负责 Candidate Overlay 和 Native Candidate Operations。两个表面可以只读回显对方状态，但不得复制对方的操作。

Dock 顶栏只读回显持久的 Native application 结果，例如 `Applied · Add`、`Application Undone` 和 `Diverged`。Dock 不显示瞬时 applying，也不提供 Native Candidate Operations。Status Bar 回显 Candidate current、stale、updating、update failed 和 correcting 等生产状态；Toolbar 只通过 Overlay 样式、操作 enablement 和禁用原因反映它们。

Candidate 生命周期状态位于右下角 Status Bar，不在 Toolbar 重复常驻。该状态保持只读，只用于解释 Candidate Overlay 的 currency 和 Native Candidate Operations 的 enablement，不承担打开 Dock 的导航职责。stale、updating、update failed 和 correcting 的恢复动作位于 AI View Dock；Dock 继续使用既有 Status Bar 按钮打开。

Correction 期间，四种 Native Candidate Operations 禁用，即使保留的 Candidate 尚未 stale。Status Bar 显示 `CORRECTING`，Candidate Overlay 继续作为修正参考，Toolbar 通过共享禁用原因说明正在 Dock 编辑。`Back to Candidate` 恢复未变化 Candidate 的应用能力；Stable 输入发生变化后，Candidate 保持 stale，直到 `Update 3D Candidate` 成功。

存在可检查 Candidate 后，固定 Toolbar 使用以下状态矩阵：

| 状态                                              | Candidate Overlay           | Set / Add / Remove / Intersect | `Undo and Fix`              |
| ------------------------------------------------- | --------------------------- | ------------------------------ | --------------------------- |
| 尚无 Candidate                                    | 不显示 Candidate 操作组     | —                              | —                           |
| 首次 Updating，尚无旧结果                         | 不显示；Status Bar 回显状态 | —                              | —                           |
| `Current`                                         | 正常，可切换                | 启用                           | 不显示                      |
| `Stale` / 有旧结果的 `Updating` / `Update Failed` | 保留旧结果，使用 stale 样式 | 禁用                           | 不显示                      |
| `Correcting`                                      | 保留作为编辑参考            | 禁用                           | 不显示                      |
| `Applied`                                         | 默认隐藏，可重新显示        | 启用，可重复应用               | 关联 command 安全时启用     |
| `Application Undone`                              | 自动重新显示                | 启用                           | 不显示                      |
| `Diverged`                                        | 可检查                      | 启用                           | 保留但禁用，并说明后续 edit |
| Target suspended 或其他全局 blocker               | 已有结果仍可检查            | 禁用                           | 按安全条件禁用或不显示      |

本地 Native Candidate Operation 执行期间只在内部防止重复提交，不把瞬时 `Applying` 投影为 spinner、工具栏布局变化或 Status Bar 持久状态。

## Status Bar 数量与状态

右下角保留现有 `SPLATS`、`SELECTED`、`LOCKED` 和 `DELETED` 统计的原有语义。`SELECTED` 只表示 Native Selection，不在 Candidate 应用前借用为 AI Candidate 数量。

开始请求 Candidate 后，Status Bar 增加一个仅在当前 AI Select Target 上下文内显示的独立项：

`AI CANDIDATE 222 · CURRENT`

- 首次更新且尚无可检查 Candidate 时显示 `AI CANDIDATE — · UPDATING`；
- 存在可检查 Candidate 时显示 Candidate Selected 数量与 `CURRENT`、`STALE`、`UPDATING`、`UPDATE FAILED`、`CORRECTING` 或持久 Application 结果；
- Candidate 应用后，现有 `SELECTED` 统计根据 Native Selection 的真实结果自然更新；
- Uncertain 数量仅在 Candidate Overlay 展开菜单中显示，不增加第二个常驻 Status Bar 统计项；
- Restart 清空当前 Target Candidate 后隐藏该项，直到新的 Candidate 请求开始。

## 视觉通道

- Native Selection 保持原生橙色填充；
- Candidate 使用青色外缘或光晕，不覆盖 Native Selection 的原生颜色；
- Uncertain 使用低透明度琥珀色点状表达；
- stale Candidate 降饱和并使用静态稀疏纹理，不使用持续动画。

Candidate Overlay 与 Native Selection 同时显示时，外缘和填充仍需保持可区分。

## 响应式退化

Toolbar 始终保持单行，不换行：

1. 优先把 `Undo and Fix` 及 Anchor/View 低频操作移入 `More`；
2. 空间仍不足时，把 Set、Add、Remove、Intersect 改为带 tooltip 的原生集合运算图标。

Status Bar 空间不足时可以缩短 `AI CANDIDATE` 标签和状态文本，但不得把 Candidate 数量冒充为 Native `SELECTED`。

Candidate Overlay 控制和四种 Native Candidate Operations 不进入 overflow。响应式退化不得改变操作语义。

`More` 只收纳低频的环境和 Target 操作：

- View：`Adjust Anchor`、`Use Current View`、`Adjust New View`；
- Target：`Restart Current Target`、`Exit AI Select`；
- 窄屏时的 `Undo and Fix`。

Set、Add、Remove、Intersect、Candidate Overlay 和 Uncertain 不进入 `More`。

## 键盘和焦点

- 首版不增加 Set、Add、Remove、Intersect 全局快捷键；
- 所有按钮支持 `Tab`、`Enter` 和 `Space`；
- Candidate Overlay 控制使用 `aria-pressed`；
- 菜单支持 `Esc` 和外部点击关闭；
- 菜单关闭后焦点返回触发按钮；
- 禁用原因可通过 tooltip 和辅助文本读取。

## 当前实现差异

- `AISelectToolbar` 尚未订阅 Candidate publication、Correction 或 Application controllers。
- Status Bar 尚未提供独立的 AI Candidate 数量和状态项。
- Set、Add、Remove、Intersect 仍由 Dock 渲染。
- `Show AI Result` 只改变 Dock Candidate 状态文字的 emphasis，没有连接 3D renderer。
- Candidate Correction 没有保留草稿的 `Back to Candidate` 状态转换。
- Candidate Application 尚未跟踪后续 Native Undo/Redo，因此不能判断 `Undo and Fix` 是否安全。
- Ticket 16 仍把四种操作和 `Show AI Result` 的实现位置记录为 Dock。

## Ticket 映射方向

Ticket 16 保留 `implemented` 状态，继续作为以下已实现行为的所有者：

- Candidate applicability gate 和 fail-closed 检查；
- Set、Add、Remove、Intersect 精确集合语义；
- Native `SelectOp` / `EditHistory` 集成；
- `CandidateApplicationRecord` 及已实现的 Application 基础状态。

新增 Ticket 16A 作为 Ticket 16 完成后的 UI 集成阶段，并在 Ticket 17 之前实施。16A 的已确定范围包括：

- 已接受的完整 AI View Dock 布局与响应式行为；
- 真实、非破坏性的主 3D 视口 Candidate Overlay；
- 固定 AI Select Toolbar 中的 Candidate 操作组；
- 右下角 Status Bar 的 AI Candidate 数量和状态；
- 从 Dock 移除 Set、Add、Remove、Intersect 和旧 `Show AI Result`；
- Dock、Toolbar 和 Status Bar 共用的 presentation mapper。

Ticket 16A 同时实现新设计所需的 `Back to Candidate` 转换；Ticket 15 保留已实现的 Correction 和 Re-Lift 语义所有权，不重新打开。Ticket 17 保留 `Undo and Fix`、Native Undo/Redo/Diverged 跟踪、Restart 和多 Target/工具切换生命周期所有权。

Ticket 16A 保持一个纵向闭环 Ticket，内部可分 renderer、presentation mapper、Toolbar/Status Bar 和 Dock cutover 工作包，但不建立不可交付的中间子 Ticket。关闭 16A 时必须同时满足新 Toolbar 可用、Status Bar 可用和 Dock 旧操作已移除，不保留双入口过渡状态。

16A 需通过 presentation/controller 不变式、UI 状态矩阵、完整仓库验证和真实浏览器视口检查。浏览器检查可使用确定性 development Candidate fixture，不把生产 same-decision GPU Evidence 作为本 Ticket 前置条件。
