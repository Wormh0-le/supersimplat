# SuperSimPlat Interface System

Status: current reusable interface guidance

本文沉淀 SuperSimPlat 编辑器中可跨功能复用的界面规则。领域语义、生命周期和 Ticket 验收仍以 `CONTEXT.md`、Final Spec 和功能设计文档为准；本文件不复制产品状态机。

## 方向与感受

- **使用者**：正在主 3D 视口中检查、编辑和应用高斯选择结果的专业创作者。
- **核心任务**：在不中断空间判断的前提下，在 2D 观察/编辑与 3D 原生操作之间快速往返。
- **感受**：紧凑、克制、精确，像持续工作的技术工作台，而不是独立的向导、仪表盘或展示页。
- **焦点**：当前图像/Mask 或主 3D 视口始终是唯一视觉焦点；导航、状态和恢复操作主动降级。
- **产品特征**：一个连续工作区同时保留“观察和修正”与“空间结果和原生操作”，但每个表面只有一个明确所有者。

拒绝以下默认方案：

- 将复杂任务拆成互斥向导页；改用保留上下文的连续审阅/编辑循环。
- 用等宽卡片填满空间；改用由内容宽高比、操作职责和侧栏价值决定的非均匀比例。
- 用多个高对比色和边框制造层级；改用空间、字重、文本明度和轻微表面差。

## 深度与表面

- 基础策略是**低对比边界 + 轻微表面明度差**，延续现有 PCUI 深灰表面。
- 基础画布、侧栏和工作区属于同一暗色世界，不为每栏创建不同色相。
- 输入和编辑区域可以比所在表面略深，表达“可接收内容”。
- Popover、菜单和临时抽屉高于父表面，可沿用项目已有的克制阴影；不要新增第二套阴影体系。
- 边框在不寻找时应消失，在需要识别边界时仍可见。优先使用现有 SCSS/PCUI 变量，不写随机灰色或黑色常量。
- 不使用装饰性渐变、厚边框、剧烈表面跳变或大面积强调色。

## 间距与密度

- 基础间距单位：`4px`。
- 紧凑控制区的常用间距：`8–12px`。
- 相关控件紧密分组；职责不同的组使用明显更大的分隔，不把所有间距设为相同值。
- 交互命中区域不小于 `40×40px`。可见图标可以更小，但扩展后的命中区域不得重叠。
- 面板密度保持“工作台紧凑”，不使用营销页式 `24px+` 大留白。
- 未经真实界面校准，不新增全局圆角或间距档位；优先复用现有 `2/4/6/8px` 局部圆角语言。

## 字体与层级

- 继承现有 PCUI/编辑器字体栈；不为功能区引入新字体。
- 当前没有建立新的全局字号比例。实现时先复用现有字号，通过字重、明度和空间建立层级。
- 层级顺序：当前内容/主操作 > 状态和值 > 标签和说明 > 技术细节/禁用信息。
- 动态计数使用 tabular numerals，避免 Status Bar 和进度文本产生横向跳动。
- 主操作每个状态最多一个；次级、恢复和破坏性操作不得与主操作争夺同等视觉权重。

## 色彩语义

- 深灰/黑色：画布、Dock、Toolbar 和 Inspector 的结构背景。
- 现有橙色：主操作和 Native Selection 的既有语义，不能被 Candidate 覆盖。
- 青色：Candidate Selected 的外缘/光晕，以及既有 Erase 语义；具体使用场景必须靠形状和位置区分。
- 琥珀色：Uncertain 诊断层和需要注意但非错误的状态。
- 绿色/红色：Positive/Negative Prompt 等既有编辑语义。
- stale：从 Candidate 颜色派生的降饱和静态表达，不创建新的高亮色。
- success、warning、error、disabled 继续使用项目 semantic colors。
- 实现 Candidate 颜色时应增加或复用具名语义 token；不得在组件内散落硬编码色值。

## 布局模式

### 连续编辑 Dock

- 宽屏采用 `Navigator | Work Area | Inspector` 三栏结构。
- Navigator 初始宽度范围：`190–238px`。
- Inspector 初始宽度范围：`280–350px`。
- Work Area 的理想宽度由可用高度、权威图像宽高比和侧栏约束共同决定，不无条件吞掉剩余空间。
- 图像使用完整、居中、等比的 contain 语义；不为消除空白而 crop 或 stretch。
- Dock 使用完整容器宽度，不在最大化窗口中保留固定舞台外边距。
- 多余横向空间优先提升 Navigator 和 Inspector 的有效信息承载；约 `1600px` 以上使用 `20% Navigator / 55% Work Area / 25% Inspector` 的职责比例，并将卡片和信息分组排成多列，不扩大无信息字母箱。
- 约 `1280×720` 提供完整三栏；约 `1024×720` 保留 Navigator 和 Work Area，Inspector 可折叠；更窄时 Work Area 常驻，两侧栏均可折叠。
- 展开的侧栏推挤 Work Area，不覆盖图像。
- Dock 默认高度 `420px`，最小 `300px`，最大为主编辑区域高度减 `160px`。
- 顶栏、图像和主 Action Bar 固定；Navigator 与 Inspector 独立滚动，图像不进入滚动容器。

### 固定主视口子工具栏

- 主视口上下文操作使用固定、不可拖动、单行子工具栏。
- 工具栏不按业务流程分页；它只投影当前视口交互对象需要的控制。
- 高优先级操作始终可见；低频 View/Target 操作进入 `More`。
- 响应式顺序：先移动低频操作，再缩短文案，再把高频集合操作改为带 tooltip 的图标；不得换行。
- 不为快速、可撤销的本地操作增加确认框、Apply 中间步骤或持久 spinner。

### 状态栏

- Status Bar 只承载紧凑、只读、持续有解释价值的统计或生命周期状态。
- 领域不同的数量保持独立标签；派生结果不得冒充原生统计。
- Status Bar 状态不是隐藏导航入口。打开编辑表面必须使用明确、既有的面板触发器。

## 可复用组件模式

### Compact Context Bar

- 一行合并 availability、当前生产状态和必要摘要。
- 同一时刻最多一个上下文动作。
- 状态文字和动作不得复制到相邻表面。

### Navigator Card

- 只显示支持导航和判断的缩略图、名称/来源、Assessment、Participation、草稿和阻塞错误。
- 卡片选择与卡片内开关是两个独立焦点和操作。
- 当前条目固定可见，不在过滤结果中重复。

### Selected Work Area

- 结构：约 `28px` 的轻量标题行、主图像、图像内可拖动并自动吸附的浮动工具栏，以及仅承载上下文恢复动作的 Action Bar。
- 一次只显示一个主操作；无关操作隐藏，暂时不可用的操作保留并紧邻解释原因。
- 没有主操作时，Action Bar 整体隐藏并把高度还给图像。
- 每次 Prompt 推理只暴露一个结果，并直接进入 Editing Mask；不提供 Proposal 轮播、计数或接受步骤。
- 浮动工具栏把 `确认 Mask` 放在清除操作之前，并提供 `重置为自动 Mask`。确认 Anchor 的 Editing Mask 同时继续 Anchor 确认和 Generated View 规划。

### Inspector

- 只负责解释、只读状态、次级操作和恢复操作。
- 技术细节默认折叠。
- 高频 Mask 恢复（重置为自动 Mask）属于图像内浮动工具栏，不在 Inspector 重复。
- 不复制主 Action Bar 或 Navigator 的可变控件。

### Overlay Split Control

- 主按钮直接切换主要 Overlay，并暴露 pressed 状态。
- 相邻箭头打开图层、图例和数量菜单。
- 诊断图层留在 Overlay 菜单，不进入通用 `More`。

### Candidate Operation Group

- 固定顺序：`Overlay 👁 ▾ | Set | Add | Remove | Intersect | Undo and Fix* | More`。
- Overlay 和四个集合操作不进入 overflow。
- 生命周期状态改变样式、enablement 和禁用原因，不重排整条工具栏。
- 四个集合操作共享一个按恢复动作归类的禁用原因。

## 状态、反馈与动效

- 状态切换优先保持布局稳定；保留控件并正确禁用，避免隐藏导致的跳动。
- 快速本地操作的成功反馈来自内容本身的变化和正常 Undo；只在异常失败时显示简短非模态提示。
- 旧结果在更新时可继续作为 stale 参考，直到新结果原子替换。
- stale 使用静态、降饱和或稀疏纹理表达，不使用持续动画。
- 侧栏和低频 popover 只动画 `transform` 和 `opacity`，并遵循 `prefers-reduced-motion`。
- 高频工具操作不添加动画；菜单关闭后焦点返回触发按钮。

## 可访问性与状态保留

- 所有控件支持键盘；按钮使用 Enter/Space，菜单支持 Escape 和外部点击关闭。
- 禁用原因不能只依赖 hover 或颜色，必须能被键盘和辅助技术读取。
- 折叠表面收起后焦点返回触发器。
- 普通导航、过滤、折叠和 resize 不丢失当前对象、草稿、历史或各区域滚动位置。
- 只有明确的破坏性操作可以清理状态，并在必要时解释影响或请求确认。

## 边界

- 布局、过滤、折叠、Overlay 可见性和面板尺寸属于 presentation state，不进入项目数据或领域 identity。
- Candidate/预览等派生可视化不得通过临时修改 Native Selection 实现。
- Dock、Toolbar 和 Status Bar 可以投影同一状态，但不能各自维护状态副本。
- 组件语义优先复用 PCUI、原生控件和已有编辑器事件；不创建只有视觉而没有完整键盘/焦点行为的仿制控件。

## 当前参考

- [AI View Dock 布局设计](../docs/ai-select/ai-view-dock-layout.md)
- [AI Select Toolbar 布局与交互设计](../docs/ai-select/ai-select-toolbar-layout.md)
- [Ticket 16A 实现合同](../docs/ai-select/tickets/16A-candidate-viewport-presentation.md)

当功能设计与本文存在表达差异时，以当前 Final Spec、`CONTEXT.md` 和对应功能设计/验收合同为准，再回写本文中可复用的新规则。
