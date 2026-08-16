# AI Select Toolbar 布局与交互设计

状态：**当前可复用合同 — Tickets 16F、16G 已实现**

本文记录主 3D 视口内 AI Select 子工具栏的最终 Ticket 16G 接口。领域状态以 Final Spec v1.3、`CONTEXT.md` 和 Ticket 合同为准。

## 设计目标

- 保持单行、固定、不可拖动的技术工作台控件。
- 只承载主 3D 视口的空间交互和 Native Candidate Operations。
- 图标约 `18–20px`，命中区域至少 `40×40px`。
- 使用 PCUI、现有语义 token、项目 tooltip 和统一自定义 SVG；不引入新框架、图标库或主题。

## 所有权

| 表面                | 拥有                                                               | 不拥有                                        |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------- |
| AI Select Toolbar   | Anchor 调整、Add View、Candidate Overlay、Set/Add/Remove/Intersect | Prompt/Mask 编辑、Re-Lift、目标重启、工具退出 |
| AI View Dock        | View 导航、2D Prompt/Mask、Review、Participation、Re-Lift          | Native Candidate Operations                   |
| 全局 AI Select 工具 | Ticket 17 的目标生命周期菜单和工具退出                             | 当前 Ticket 的上下文操作                      |

## 普通模式

普通模式只有两个稳定入口：

1. Anchor 状态与 `Adjust Anchor` 合并控件；
2. Add View split control：主操作 `Use Current View`，备选操作 `Adjust New View`。

不显示前导 `AI Select` 文字、独立 Anchor 状态文字、`More`、`Restart Current Target`、`Exit AI Select` 或 `Re-Lift`。工具退出继续由既有全局 AI Select 工具控制承担；Ticket 17 只能在全局生命周期菜单中加入目标处置，不得把这些动作放回 3D 子工具栏。

## Candidate 模式

存在可检查 Candidate 时，固定顺序为：

`Overlay | Set | Add | Remove | Intersect`

- Overlay split control 的主按钮切换 Candidate Selected，菜单管理 Uncertain、图例和数量。
- 四个 Native 操作复用 Ticket 16 的真实 applicability gate、`SelectOp` 和 `EditHistory`。
- Candidate `Current` 时可用；`Stale`、`Updating`、`Update Failed`、`Correcting` 或全局 blocker 时保留稳定位置并给出可访问禁用原因。
- `Applied` 后 Candidate Overlay 默认隐藏但可重新显示；Native Selection 颜色和语义不被 Candidate 覆盖。
- Ticket 17 的 `Undo and Fix` 只在真实历史行为实现后追加到 Intersect 后方；Ticket 16G 不提供占位控件。

## Anchor 调整模式

进入调整时，工具栏切换为紧凑的 Move、Rotate、Reset、Confirm 和 Cancel 控件，并保持图标、tooltip、pressed 状态和键盘行为一致。

- 进入、取消或确认未变化姿态不销毁当前 run。
- 变化姿态先建立独立 Camera/RGB/Prompt/Editing Mask 草稿。
- 只有新的 Mask 确认、验证和原子 Anchor cutover 才旋转身份并释放旧 Views。
- 渲染失败通过改变或 Reset 姿态后执行正常的新 render intent 恢复；没有 `Retry Preview`。
- Add View 渲染失败保留可检查、失败且 Excluded 的 View；操作者可从其他姿态添加 replacement View。

## 响应式与视觉

- 工具栏保持单行且不换行。
- Normal、Candidate 和 Adjustment 模式各自只显示当前必要操作；不建立 overflow `More`。
- Visible glyph、hit area 和 tooltip 锚点相互独立，命中区域不得重叠。
- Candidate、Native Selection、Prompt 和错误状态继续使用现有语义色；不增加装饰渐变或高对比容器。
- 快速操作不使用持久 spinner 或布局跳变。

## 可访问性

- 每个 icon button 必须有项目 tooltip、`aria-label` 和可见 focus。
- Toggle/工具模式使用 `aria-pressed`，禁用原因对键盘和辅助技术可读。
- Split control/popover 支持 Escape、外部点击关闭，并把焦点还给触发器。
- 所有按钮支持 Tab、Enter 和 Space；reduced-motion 设置得到遵守。

## Ticket 16G 禁止面

当前产品和 editor public surface 均不得提供：

- persistent Stop、Continue、Generate More、Regenerate Plan；
- Retry Render、Regenerate Prompt、Retry Mask、Retry Auto Segmentation；
- 3D Toolbar More、Restart、Exit 或 Re-Lift；
- Proposal chooser/acceptance。

仅初始规划失败可在 Navigator 显示一个 failure-only planning retry icon。Attempt identity、same-attempt replay、cache-miss resubmission、stale rejection 和 cancellation 属于内部正确性基础，不构成产品控件。

## 验证合同

- Normal、Candidate、Adjustment 状态矩阵；
- Native operation applicability 回归；
- changed-Anchor stage/cancel/no-op/cutover 与 late-response 回归；
- Add View split control；
- tooltip、focus、pressed、disabled reason 和 keyboard；
- wide、`1280×720`、`1024×720` 视觉检查；
- source/locale/style contract 证明禁止面不存在。
