# SuperSplat 中面向物体的 Gaussian 选择：技术调研与建议

> 调研日期：2026-07-11，补充核查：2026-07-12  
> 目标：给定一个已有 3D Gaussian PLY，用户点击画面中的物体，系统返回属于该物体的 Gaussian 索引集合，并复用现有编辑能力完成分离、克隆和删除。

## 结论

当前项目缺的不是编辑操作，而是一个可靠的“物体意图 → 每 Gaussian 二值掩码”生产器。项目已经具备：

- 单像素深度交点和 Gaussian ID picking；
- 2D mask、矩形、球和 AABB 到每 Gaussian 掩码的转换；
- `set/add/remove/intersect` 四种选择语义及 undo/redo；
- 对选中 Gaussian 的删除、克隆和分离。

这些能力分别可见于 [`camera.ts`](../../src/camera.ts#L705)、[`picker.ts`](../../src/picker.ts#L92)、[`editor.ts`](../../src/editor.ts#L343)、[`edit-ops.ts`](../../src/edit-ops.ts#L101) 和 [`splat-serialize.ts`](../../src/splat-serialize.ts#L35)。因此最小正确改动应让新的算法最终只输出 `Uint8Array` 或排序后的 `Uint32Array`，再交给现有 `SelectOp`，而不是另建编辑状态。

推荐主线是：

1. **先做单视图、仅可见表面的 PoC**：点击后用 SAM 产生当前帧 2D mask，用现有 ID buffer 只取 mask 下的最前层 Gaussian ID。它能直接验证并解决“把物体后方 Gaussian 一起框进来”的核心问题。
2. **再做围绕目标的短轨道视频 + 多视图融合**：以点击得到的 3D 交点或 `splat_analyzer` 的粗框为中心渲染轨道视图；用 SAM 2/3 或其他视频分割器传播 mask；按每个 Gaussian 在各视图中的可见贡献累计正、负证据，最后一次性提交选择。
3. **将原生 3D 模型作为可选补全器/对照组**：优先评估 Easy3D，其论文专门验证了 Gaussian 中心点分布；若有商用要求，评估 MIT 许可的 SNAP。它们不应阻塞第一阶段，因为 Gaussian 中心并不等同于干净的表面点云。
4. **不要先投入 SAGA/Click-Gaussian 一类逐场景特征训练**：它们适合一个场景被反复查询的离线语义化，但与“只给现有 PLY、立刻点击编辑”的产品约束不匹配。

这一路线并非仅是推测。近期三个独立工作都收敛到相同结构：ArtisanGS 使用密集合成视图、视频 mask tracking 和每 Gaussian 一维 mask 优化；SAGOnline 使用 SAM 2 视频传播与遮挡感知的 Gaussian 投票；B³-Seg 面向无原始相机、无训练的 PLY，用主动视角和 Beta–Bernoulli 更新融合多视图证据。[ArtisanGS](https://arxiv.org/html/2602.10173#S4)、[SAGOnline](https://arxiv.org/html/2508.08219#SIII)、[B³-Seg](https://arxiv.org/abs/2602.17134)。

## 问题的第一性原理

### 输出是什么

对含有 `N` 个 Gaussian 的场景，最终输出只是：

\[
y_i \in \{0,1\}, \quad i=1,\ldots,N
\]

可选地再保留置信度 `p_i`、被观察次数和来源视角，供 UI 显示“不确定区域”。现有 `SelectOp` 已把 mask 转成可撤销的 `IndexRanges`，并保护 locked/deleted 状态，因此新模块的边界应是“生成证据与索引”，不应直接修改 `state`。[本项目实现](../../src/edit-ops.ts#L101)

### 为什么一次点击不够

一个 2D 像素定义的是一条射线，而不是一个 3D 物体。即使点击处能得到最前层 Gaussian 或期望深度，背面、被遮挡部分和薄结构仍没有观测。要从点击扩展到完整物体，至少需要一种先验：

- 多视图外观一致性；
- 3D 邻接/实例先验；
- 预训练或逐场景学习的 per-Gaussian 特征；
- 用户的追加正/负点击。

因此“单帧分割后把 mask 视锥里的所有 Gaussian 全选”必然会选到后方；“只取最前层 ID”则精度高但召回不足。合理系统应先高精度初始化，再通过多视图和用户修正补召回。

### 两个不同的难题

应将问题拆成：

1. **2D mask 一致性**：同一物体在不同渲染视图里是否仍被追踪为同一实例；
2. **2D→3D 归因**：一个 mask 像素的语义应该分配给沿射线的哪些 Gaussian。

SAM 2/3 只主要解决第一项。若第二项仍用无深度的视锥投影，视频 mask 再稳定也会污染后景。SAGOnline 的核心正是同时检查前向透射率和 Gaussian 投影中心与像素的几何对齐，再给 Gaussian 投票。[SAGOnline 方法](https://arxiv.org/html/2508.08219#SIII-B)

## 当前仓库的可复用能力

### SuperSplat 编辑链路

以下为代码观察：

- `camera.intersect(x,y)` 对每个 splat 做深度 picking，返回最近 splat、世界坐标和距离；深度读回会用累计 alpha 对深度归一化。[`camera.ts`](../../src/camera.ts#L705)、[`picker.ts`](../../src/picker.ts#L177)
- ID picking 把 32 位 Gaussian 索引编码为 RGBA；`pickRect` 可读回任意屏幕矩形的逐像素 ID。[`picker.ts`](../../src/picker.ts#L92)
- `select.byMask` 已经存在。Centers 模式判断 Gaussian 中心是否投进 mask；Rings 模式读取 ID buffer 并只收集 mask 像素下的 ID。[`editor.ts`](../../src/editor.ts#L397)
- Centers 模式的 point selection 会遍历全部 Gaussian 并只比较投影位置，因此会命中同一屏幕位置的前后层；Rings 模式只读一个 ID。[`editor.ts`](../../src/editor.ts#L469)
- `SelectOp` 已支持 `set/add/remove/intersect`，输入可以是逐 Gaussian 字节 mask 或排序 ID 数组。[`edit-ops.ts`](../../src/edit-ops.ts#L101)
- 删除使用 `DeleteSelectionOp`；克隆和分离先仅序列化 selected Gaussian，再加载成新 splat；分离额外删除原选择。[`editor.ts`](../../src/editor.ts#L592)

**推断：** 单视图 PoC 几乎不需要新的 GPU picking 代码。SAM mask canvas 可直接接入 `select.byMask` 的 Rings/ID 路径。需要新增的是异步模型适配器、无效 ID `0xffffffff` 过滤、进度/取消 UI，以及多视图证据缓存。

### `thirdparty/splat_analyzer` 的真实能力和边界

用户称其输出为物体 AABB，但当前代码更准确地说是“由多视图 2D 检测估计出的轴对齐交互框”：

- 它渲染 RGB 和深度视图，以 OWLv2 对文本名词做 2D box detection；对 box 中心附近的深度中位数反投影，再把 box 像素宽高按深度换算为世界尺度。[`pipeline.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/pipeline.py#L137-L234)
- 同标签检测按 3D 锚点聚类，最终位置为分数加权中心，尺度为成员 box 尺度的中位数，旋转固定为单位四元数。[`pipeline.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/pipeline.py#L76-L130)、[`pipeline.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/pipeline.py#L285-L320)
- 输出还保留命中帧、2D box、相机位姿和深度图，这些比最终粗框更适合作为后续 mask 分割和多视图融合的输入。[`pipeline.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/pipeline.py#L270-L320)
- low/medium/high 分别渲染 24/90/192 帧，默认 512×512。[`config.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/config.py#L16-L34)

它**没有**计算“属于该物体的 Gaussian 集合”，也没有从该集合求真实 min/max；因此不能把这个 box 当最终 selection。适合用途是：ROI、目标中心、轨道半径、候选视角、文本提示和剔除明显远处 Gaussian。

另一个代码风险是 CUDA backend 把 camera-Z 当颜色做 alpha blending 后直接作为深度返回，没有像 SuperSplat picker 那样除以累计 alpha；这不是 first-hit depth，低 alpha 像素可能出现向零偏的深度。[`gsplat_backend.py`](https://github.com/Wormh0-le/splat_analyzer/blob/e199fef611296249cb15604474ae08aecc7db69f/renderers/gsplat_backend.py#L50-L76) 这是根据代码作出的数学推断，需用已知几何场景实测确认。

当前 analyzer 固定 `gsplat==1.5.3`。[`requirements.txt`](../../thirdparty/splat_analyzer/requirements.txt) 较新的 gsplat main 已公开 Gaussian-ID rasterization：包顶层 API 包括返回每像素全部 contributor ID 与 `alpha*T` radiance weight 的 `rasterize_contributing_gaussian_ids`，以及固定 top-K 的 `rasterize_top_contributing_gaussian_ids`；gsplat 为 Apache-2.0。[gsplat 官方仓库](https://github.com/nerfstudio-project/gsplat)、[官方 API 文档](https://docs.gsplat.studio/main/apis/utils.html) 这使“贡献权重融合”不再要求自写 CUDA；PoC 可固定一个已验证的 main commit，生产阶段再等正式版本或回移必要实现。

## 外部实现核查

### SplatEdit

2026-07-11 直接检查公开网页时，页面显示 v0.2.2、PlayCanvas、`SAM2 ONNX vietanhdev`，并公开以下选择控件：

- transparency、density、size、brightness、random、SH、colour；
- Segment Selection 的 `New/Add/Remove/Refine`；
- `2D/3D`、`Fast/Quality` 和 `Original/Orbit 2/Orbit 3` 选项；
- Duplicate、Separate、Delete Selection。

这些是对当前公开 DOM/UI 的观察，不是对其闭源算法的确认。[SplatEdit](https://www.splatedit.app/) 开发者公开声明该工具在浏览器本地运行 Segment Anything，并用 Refine 将选择“锁定到 3D”；这证明浏览器本地 ONNX 的产品形态可行，但不能证明其 3D 模式的正确性。[开发者公开说明](https://www.linkedin.com/posts/neal-menhinick-36014554_gaussiansplatting-3dgs-segmentanything-activity-7478736575686766593-bd1-)

对当时公开客户端 bundle 的只读核查还显示，其 experimental 3D 路径并不是软证据融合：它先在原始视图提交 SAM2 mask，再围绕点击得到的 3D 交点把相机旋转约 `+45°/-45°`；两个侧视图分别重新运行 SAM2，并用各自 mask 的补集执行 remove。最终效果近似三个视图的硬交集。[公开客户端 bundle](https://www.splatedit.app/index.js) **推断：** 任一侧视图因遮挡、投影偏差或 SAM 漂移漏掉目标，候选集合就可能被清空；这与用户观察到“3D 模式选中 0 个 Gaussian”一致，但没有运行日志，不能把它断言为该次失败的唯一根因。推荐方案应累计正/负贡献、跳过低置信视图，不能复刻硬交集。

### X 帖子：Carveout

通过公开 X 页面读取到，Hugues Bruyère 的 Carveout 正是以当前 `Splat Analyzer` 为触发点重新设计：从现有 3DGS 渲染合成视图，用 SAM 3 做实例分割，在 gsplat 上采用受 FlashSplat 启发的 mask lifting 跨视图累计证据，再把标注 Gaussian 聚成带 centroid、box 和 metadata 的 3D instance；约束是无需重训、无需预埋 language feature。作者明确称项目仍处早期，帖子未给可审计代码，因此只能把它视为独立设计验证，不能引用其性能。[原帖，2026-07-10](https://x.com/smallfly/status/2075570299387461741)

## 方案对比

| 路线                                      |     是否可仅用现有 PLY |           预处理 | 优点                                   | 主要问题                                   | 本项目建议                |
| ----------------------------------------- | ---------------------: | ---------------: | -------------------------------------- | ------------------------------------------ | ------------------------- |
| 单视图 SAM + ID buffer                    |                     是 |               无 | 最小、能立即排除后景                   | 只得到可见表面                             | 第一阶段 PoC              |
| 视频分割 + 多视图 ID/贡献融合             |                     是 |       数秒级按需 | 符合交互编辑；可持续修正               | 视角、遮挡和阈值仍需设计                   | **推荐主线**              |
| ArtisanGS 风格 mask 优化                  |                     是 |   每次选择约秒级 | 不依赖原始相机；可让用户修正           | 论文实现未公开；需可微 renderer            | 第二阶段质量上限参考      |
| B³-Seg 主动视角 + Bayes 更新              |                     是 |       数秒级按需 | camera-free、training-free；有不确定度 | 当前项目页未见可复用代码                   | 视角选择/融合升级方向     |
| Easy3D/SNAP 原生点云网络                  |       是，需转中心点云 |       每场景编码 | 真正 3D；可补不可见部分                | Gaussian 与扫描点云有域差；GPU/server 依赖 | 可选 refiner/A-B baseline |
| SAGA / Click-Gaussian / Gaussian Grouping | 通常否，需要图像与相机 | 约数十分钟至小时 | 训练后点击极快，适合反复查询           | 与 standalone PLY 即开即用冲突             | 后续“场景语义化”模式      |
| LangSplat/语言场                          |                 通常否 |       逐场景训练 | 文本开放词汇查询                       | 高维特征、训练和格式扩展                   | 非当前 MVP                |

### 与推荐路线最接近的方法

- **SAGD（仓库名 SAGS）**：点击首帧后对多视图生成 SAM masks，逐视图赋 Gaussian label，再投票；其 Gaussian Decomposition 用于边界处大 Gaussian。官方仓库称该交互 lifting 路径 training-free，但现有流程仍建立在其 Python/CUDA 3DGS 工程上，且 GUI 仍在 TODO。[官方仓库](https://github.com/XuHu0529/SAGS#overall-pipeline)
- **ArtisanGS**：不要求原始训练视图或场景预训练；约采样 50 个绕物体视图，用 Cutie 跟踪 mask，并通过可微 rasterizer 优化每 Gaussian 一维特征；还允许用户在错误视角补 mask。论文报告同硬件约 1–5 秒，并明确指出极端新视角的渲染质量会影响 2D 网络。[方法](https://arxiv.org/html/2602.10173#S4)、[评估](https://arxiv.org/html/2602.10173#S5)
- **SAGOnline**：SAM 2 在平滑渲染轨道上传播 mask；只对可见 surface crust 且 Gaussian 核心对齐像素的 primitive 投票，避免后方和 Gaussian tail 污染。论文报告 RTX 4090 上约 1.47 秒融合约 200 帧；另有约 4–5 分钟可选后台 refinement。该数字是作者报告，尚未在本项目复现。[方法与时间](https://arxiv.org/html/2508.08219#SIII-B)
- **FlashSplat**：把固定 3DGS 下的 mask rendering 看成 Gaussian label 的线性函数，以线性规划求 label，论文/仓库报告约 30 秒；官方 TODO 仍包括 SAM2 多视图 mask association。[官方仓库](https://github.com/florinshen/FlashSplat) 它适合借鉴目标函数，不宜直接复制代码：其 [`LICENSE.md`](https://github.com/florinshen/FlashSplat/blob/main/LICENSE.md) 继承了 Inria 3DGS 的非商用研究限制。建议在 Apache-2.0 gsplat 上重写必要部分。
- **GaussianCut**：用 2D/视频模型提供粗 mask，再在 Gaussian 邻接图上做 graph cut；无需 segmentation-aware retraining，适合做空间连续性后处理，但论文实现未提供可直接集成的网页路径。[论文/项目](https://umangi-jain.github.io/gaussiancut/)
- **SAGA**：从 SAM masks 蒸馏 scale-gated Gaussian affinity feature，官方实现需要先生成 masks/scales，再训练 10,000 iteration 的对比特征；之后点击可输出逐 Gaussian binary mask。[官方实现](https://github.com/Jumpat/SegAnyGAussians#train-3d-gaussian-affinity-features)
- **Click-Gaussian**：给预训练 3DGS 增加两层粒度特征并用多视图 SAM masks 对比训练；作者报告训练完成后约 10ms 点击选择，但也承认一个 Gaussian 跨两个物体和只有两级粒度会限制边界/层级。[论文](https://arxiv.org/abs/2407.11793)
- **Gaussian Grouping**：联合重建和分组，并展示 removal、inpainting、colorization、recomposition；每个 group 可解耦编辑，但它改变训练流程而不是消费任意现有 PLY。[官方仓库](https://github.com/lkeab/gaussian-grouping)

## 四项补充工作的统一核查

这四项常被放在一起讨论，但实际上分属四个不同层级：SA3D 是“单视图提示后把 2D mask 反渲染为 3D mask”的算法；SALT 是 2D 标注工具；arXiv:2411.03555 是把现有分割、重建、位姿跟踪组件串起来的机器人应用；Segment-then-Splat 则是在重建开始前就给 Gaussian 固定 object ID 的训练范式。只有 SA3D-GS 直接回答“已有 3DGS 上如何从一次提示得到逐 Gaussian mask”。

### 同一维度对比

| 工作                                                       | 场景表示与提示                                                                                                                                                                                                              | 2D/多视图到 3D/Gaussian 的映射                                                                                                                                                                                                                                                                                                                                                    | 优化与输出粒度                                                                                                                                                                                                                                                                                              |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SA3D / SA3D-GS**                                         | 输入已训练的 NeRF、TensoRF 或 3DGS；用户只需在一个渲染视图给点/涂画，文本模式则用 Grounding-DINO 先产 box。[论文方法](https://arxiv.org/html/2304.12308#S4)、[文本提示](https://arxiv.org/html/2304.12308#S5.SS4)           | 对 3DGS 给每个 Gaussian 增加一个零初始化 soft mask confidence，用原有 alpha/ray blending 权重做 mask inverse rendering；在新视角渲染当前不完整 mask，自动选 3D 距离约束的 self-prompts 再送入 SAM，并用预测/渲染 mask 的 IoU 拒绝坏视角。[mask 表示与反渲染](https://arxiv.org/html/2304.12308#S4.SS2)、[self-prompt 与 view rejection](https://arxiv.org/html/2304.12308#S4.SS4) | 不训练额外 feature field，只优化 3D mask；阈值化后得到逐 Gaussian 二值 mask，可做物体、部件和多物体分割。另有去除物体边界 ambiguous Gaussians 的可选第二遍，但论文只把它用于定性实验。[边界处理](https://arxiv.org/html/2304.12308#S4.SS5)                                                                  |
| **SALT**                                                   | 普通 2D 图片数据集；左键为正点，右键为物体外负点；用户 accept/reject、切图和调 overlay。[官方 README](https://github.com/anuragxel/salt#usage)                                                                              | **没有多视图或 3D lifting**。它先在 GPU 机器离线提取 SAM image embeddings、导出 ONNX 模型，标注机可以无 GPU 运行。[官方 README](https://github.com/anuragxel/salt#installation)                                                                                                                                                                                                   | 无训练；输出 COCO-style 2D annotations，而不是 Gaussian ID。可复用的是预计算 embedding、正负点击、accept/reject、透明叠加和保存进度的交互语义。                                                                                                                                                             |
| **Object and Contact Point Tracking…**（arXiv:2411.03555） | 输入两个 Spectacular Rec RGB-D 视频：一个多视角场景视频用于 3DGS，另一个固定相机的人类操作示范；它不是静态场景的鼠标点击算法。RAFT 找运动物体 box，SAM 2 生成示范 mask。[论文流程](https://arxiv.org/html/2411.03555#S3)    | 用 COLMAP 把示范相机注册到场景轨迹；在最近场景位姿从 **3DGS 重渲染** 图像而不是直接用原视频帧，再以示范 box 提示 SAM 2 生成场景多视图 masks；随后调用 Semantic Anything in 3D Gaussians（SAGS）投票得到 Gaussian segment。[表示对齐细节](https://arxiv.org/html/2411.03555#A1.F3)                                                                                                 | 先训练 3DGS，另做 GS2Mesh、FoundationPose 6DoF 跟踪和接触点估计；输出不仅是 Gaussian object segment，还包括轨迹和 contact points。论文没有提出新的可点击语义场训练目标。[论文总览](https://arxiv.org/html/2411.03555#S1.F1)                                                                                 |
| **Segment-then-Splat**                                     | 输入原始多视图图片/视频和 COLMAP sparse reconstruction；第一帧用 SAM 网格点自动发现大/中/小粒度 masks，SAM 2 跟踪；重建后用 CLIP **文本**查询，不提供编辑器式鼠标点击入口。[方法](https://arxiv.org/html/2503.22204#S3.SS2) | 在优化前按多视图 mask 给每个初始 Gaussian 分配三层 object ID；补新出现物体、消除重叠 track、以几何中心和颜色合并 lost tracks；每个 Gaussian 从一开始只属于一个 object set。[初始化](https://arxiv.org/html/2503.22204#S3.SS3)                                                                                                                                                     | 必须重建。object loss 保证每组只贡献给自身 mask，densification/cloning 也严格限制在组内，并在后期剔除低 IoU partial masks；输出是持久的三粒度逐 Gaussian object IDs，并为每组挂统一 CLIP embedding。[优化](https://arxiv.org/html/2503.22204#S3.SS4)、[CLIP 关联](https://arxiv.org/html/2503.22204#S3.SS5) |

### 性能、开放状态与许可

| 工作                   | 作者报告的速度/硬件                                                                                                                                                                                                                                                          | 代码与许可                                                                                                                                                                                                                                                                                                                                                                                | 对当前 SuperSplat fork 的直接限制                                                                                                                                                                                                                                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **SA3D**               | 单 RTX 3090；SAM feature cache 约 30 秒，SA3D-GS 在 NVOS 表中约 2 秒；五个视角低于 2 秒，11→103 视角只增加约 2.7 秒。3DGS 本身的 30k 预训练不计入交互时间。[实现与时间](https://arxiv.org/html/2304.12308#S5.SS2)、[视角消融](https://arxiv.org/html/2304.12308#S5.SS5.SSS1) | 官方仓库顶层为 Apache-2.0，公开 NeRF 与 nerfstudio 实现；但 README 中“3D-GS version”的 `here` 实际仍指向 `nerfstudio-version` 分支，未找到一个清楚独立、可直接运行的 SA3D-GS 分支。因此算法一手描述充分，直接复用代码仍有工程风险。[官方 README](https://github.com/Jumpat/SegmentAnythingin3D#update)、[公开分支](https://github.com/Jumpat/SegmentAnythingin3D/tree/nerfstudio-version) | 论文假设有已训练 radiance field 的多视图图片并缓存其 SAM features；对只有 PLY 的场景需改用 SuperSplat 合成轨道视图。好处是 3DGS 版的状态本来就是每 Gaussian 一个标量，与现有 selection mask 很接近。                                                                                                                                 |
| **SALT**               | 无作者 benchmark；重型 image encoder 可在另一台 GPU 机器预计算，交互标注机无需 GPU。[官方 README](https://github.com/anuragxel/salt#installation)                                                                                                                            | Python，MIT；README 明示仍在 active development，存在 rough edges/bugs。[仓库与许可](https://github.com/anuragxel/salt)                                                                                                                                                                                                                                                                   | 不能当分割算法 baseline，也不能直接嵌入 WebGL 编辑器；适合把“离线/服务端 image encoder + 交互 decoder”的边界和标注 UX 移植到 TypeScript/服务端接口。                                                                                                                                                                                 |
| **arXiv:2411.03555**   | RTX 3060 Ti 8GB；完整 pipeline 每视频数分钟；预计算 mesh 后标准 pose tracking 可接近实时，而逐帧 pose estimation 慢 11 倍。[硬件与速度](https://arxiv.org/html/2411.03555#S3)、[讨论](https://arxiv.org/html/2411.03555#S5)                                                  | 论文和 CoRL workshop PDF 公开，但截至本次核查，论文/arXiv 页面未链接整套实现，故无法给整条 pipeline 指定开源许可；其 RAFT、SAM 2、SAGS、GS2Mesh、FoundationPose 等组件必须分别审计。[论文](https://arxiv.org/abs/2411.03555)                                                                                                                                                              | 大量 RGB-D、mesh、相机注册和动态示范要求与“已有静态 PLY + 点击”不匹配；只应抽取它的 scene-render alignment 和 voting 经验，不应移植整条机器人 pipeline。                                                                                                                                                                             |
| **Segment-then-Splat** | 单 RTX A6000；小场景 20k iterations，大场景 40k；论文报告 3DOVS 平均约 9.4 分钟、LERF_OVS 约 50.75 分钟，动态数据约 161–218 分钟。[设置与主表](https://arxiv.org/html/2503.22204#S4.SS1)                                                                                     | 官方实现顶层 MIT，但 README 把 object tracking / object-specific initialization 标为“to be verified”，且依赖/包含 3DGS、Deformable-3DGS、SAM/SAM2 等第三方组件；不能把顶层 MIT 等同于完整部署栈已完成许可审计。[官方实现](https://github.com/luyr/Segment-then-Splat#run)                                                                                                                 | 不消费任意训练完成的 PLY，必须拿原图、poses 和 sparse points 重新构建；论文使用的 RTX A6000 为 48GB，而 4090D 为 24GB，论文没有证明原设置可直接塞入后者。[NVIDIA A6000 规格](https://www.nvidia.com/en-au/products/workstations/rtx-a6000/)、[NVIDIA 4090D 规格](https://www.nvidia.cn/geforce/graphics-cards/40-series/rtx-4090-d/) |

### arXiv:2411.03555 的身份与关系澄清

该编号的准确标题是 **Object and Contact Point Tracking in Demonstrations Using 3D Gaussian Splatting**，是 CoRL 2024 Lifelong Learning for Home Robots workshop 的机器人模仿/接触点 pipeline，不是一个新的通用 Gaussian 分割模型。[论文](https://arxiv.org/abs/2411.03555)

- 它调用的是 **Semantic Anything in 3D Gaussians（SAGS，arXiv:2401.17857）** 来把 scene-view masks 变成 Gaussian segment；这不是 SA3D，也不要与上文仓库名同样为 SAGS、方法名为 SAGD 的 boundary decomposition 工作混为一谈。[论文参考与流程](https://arxiv.org/html/2411.03555#S3)
- 它与 SALT 没有直接继承关系；两者只是都使用 Segment Anything 家族。它也不是 Segment-then-Splat 的前身：前者在已重建 3DGS 上投票分割并继续做 mesh/pose/contact，后者在重建前固定 object-specific Gaussian sets。
- 它最有价值的是负面证据：作者报告示范物体 masking 为 10/12、scene masking 为 9/12，但整链高精度成功只有 2/12；这说明把多个现成模型串起来会明显积累误差。[结果表](https://arxiv.org/html/2411.03555#S4)
- SAGS voting 要求对象每帧完整处于视野内，否则未入镜部分会被排除；把视锥外 Gaussian 改为 neutral 又会纳入远处无关点。[失败分析](https://arxiv.org/html/2411.03555#S4) 因此融合状态不能只有“正/负”：必须区分 `observed-positive`、`observed-negative` 和 `unobserved`，并保留 `observations`/uncertainty，不能用跨视图硬交集。
- SAM 2 在冰箱场景只取门板、漏掉把手，人工输入也未能稳定把两者合并。[失败分析](https://arxiv.org/html/2411.03555#S4) 产品上必须保留层级选择和 `add/remove` 修正，而不能假设一次 click 永远对应用户心中的完整物体。

### 对现有推荐路线的影响

四项工作带来的不是换主线，而是把主线细化为以下职责：

1. **即时选择内核仍用 contributor-weighted 多视图证据**。它天然支持 standalone PLY，并能显式维护“未观察”；这正好规避 2411.03555 暴露的 hard voting 缺陷。
2. **把 SA3D-GS 做成质量版 lifting backend**：以 per-Gaussian soft confidence 替代额外 voxel/feature field，复用 alpha/transmittance contributor 权重、cross-view self-prompt、IoU view rejection 和小负项一致性；它与当前 `positive/negative/observations` 结构兼容，而不是另一套编辑状态。
3. **从 SALT 借工作流，不借算法**：服务端预计算/缓存 image embedding，浏览器只发点击并运行轻量 decoder 或 RPC；UI 必须有正负点击、accept/reject、overlay、add/remove 和保存中间证据。
4. **把 Segment-then-Splat 留作未来的“语义化采集/重建模式”**：若上游可控制拍摄与训练，持久三粒度 object IDs、object-local densification/cloning、track recovery、partial-mask filtering 和 object sidecar 都很有价值；它不进入当前已有 PLY 的 PoC critical path。

### 4090D 服务器上的 PoC 排序与最小实验

这四项不能按同一“能否直接跑”的标准硬排。对当前目标的**算法验证优先级**是：

1. **SA3D-GS 的最小重实现**：最接近输入/输出契约，论文已在 RTX 3090 上验证秒级分割；4090D 有 24GB 显存，但实际速度和峰值显存仍需本项目测量，且不应等待一个未明确公开的 GS 分支。[NVIDIA 4090D 规格](https://www.nvidia.cn/geforce/graphics-cards/40-series/rtx-4090-d/)
2. **2411.03555 中的 SAGS-style voting 对照**：只复现“3DGS 渲染帧 → SAM2 scene masks → 三状态逐 Gaussian 投票”，不复现 RAFT、RGB-D、GS2Mesh、FoundationPose 和 contact tracking。它适合当廉价 baseline，也能专门验证 partial-FOV/neutral-vote 失败。
3. **Segment-then-Splat 单独离线试验**：仅当手头有原始 images/poses/COLMAP 且确实要评估“从重建起就对象化”时运行一个小 3DOVS 场景；它不属于 standalone PLY 的成功条件，24GB 适配也要单独验证。
4. **SALT 不列入算法排名**：只用其交互/标注模式制作修正 mask 和小规模真值。

建议只做一个能在一两天内证伪关键假设的实验：

1. 选一个保留 images/poses 的 3DGS 场景，挑 3 个目标：普通独立物体、带细部/把手的物体、被遮挡或部分出视野的物体；再加一个前后重叠的合成双层场景测后景污染。
2. 对同一个初始 click 和同一组 12 个 orbit views 跑三条 lifting：`ID/contributor + Beta evidence`（当前推荐）、`SA3D per-Gaussian soft mask + self-prompt + IoU rejection`、`SAGS hard voting` 及其修正后的 three-state variant。三者共用同一 SAM 2 masks，避免把 2D 模型差异误当 lifting 差异。
3. 用 SALT 风格的正/负点击与 accept/reject 修正 6 个 held-out views，作为 2D 真值；在 SuperSplat 中人工清理一次逐 Gaussian selection，作为小规模 3D 真值。记录逐 Gaussian precision/recall/F1、held-out render IoU、后层误选率、未见区域召回、端到端延迟、峰值显存和需要的人工修正次数。
4. 必须包含两个消融：把 `unobserved` 错当 negative，以及关闭 IoU view rejection。若前者重现“物体部分消失”、后者显著增加漂移，就证明三状态证据和坏视角拒绝是必要模块；若 SA3D soft optimization 没有优于直接 contributor/Beta 融合，则不引入可微优化复杂度。

这个实验的决策门槛很简单：先选择能稳定保住细部、后景误选低且延迟可交互的 lifting；只有在可重复收益明确时，才把 SA3D 式梯度优化升级为默认质量档。Segment-then-Splat 的离线重建结果不与这组三条 standalone-Ply lifting 的交互延迟混在一起比较。

## 原生 3D 模型与 Hugging Face 核查

查询 Hugging Face `benchmark:official` 数据集后，没有找到 3D/point-cloud interactive segmentation 官方 leaderboard；唯一命中 segmentation 的官方榜单是 2D referring-expression `tiiuae/PBench`。[HF 官方 API 查询](https://huggingface.co/api/datasets?filter=benchmark:official&limit=500) 因此目前无法按统一 HF 榜单诚实地给这些 3D 模型排“第一”，只能依据各自论文实验、可用 checkpoint、许可和与 Gaussian 数据的匹配度选择。

当前 PoC 设备按 RTX 4090D 24GB 规划，但下表中 SAM 3.1/2.1 是视频物体分割（VOS）分数，Point-SAM 是 3D point-prompt IoU；二者不可横向比较，只能分别回答“2D mask 传播用哪个”和“原生 3D baseline 用哪个”，具体峰值显存仍须在本项目输入尺寸上实测。

| #   | Hugging Face 模型                                                                 | 参数量 | SA-V test J&F |   MOSE val J&F | LVOS v2 J&F |                                3D IoU@1 | 许可                      | 设备                          |
| --- | --------------------------------------------------------------------------------- | -----: | ------------: | -------------: | ----------: | --------------------------------------: | ------------------------- | ----------------------------- |
| ⭐1 | [facebook/sam3](https://huggingface.co/facebook/sam3)（SAM 3.1 Tracker）          |  0.86B |          85.1 | 79.6（MOSEv1） |        89.2 |                                       — | Meta SAM，自定义且 gated  | 未指定；建议服务端 GPU        |
| 2   | [facebook/sam2.1-hiera-large](https://huggingface.co/facebook/sam2.1-hiera-large) | 224.4M |          79.5 |           74.6 |        80.6 |                                       — | Apache-2.0                | 未指定                        |
| 3   | [facebook/sam2.1-hiera-small](https://huggingface.co/facebook/sam2.1-hiera-small) |  46.1M |          76.6 |           73.5 |        78.3 |                                       — | Apache-2.0                | 未指定                        |
| 4   | [facebook/sam2.1-hiera-tiny](https://huggingface.co/facebook/sam2.1-hiera-tiny)   |  39.0M |          76.5 |           71.8 |        77.3 |                                       — | Apache-2.0                | 未指定；最适合浏览器/ONNX PoC |
| 5   | [yuchen0187/Point-SAM](https://huggingface.co/yuchen0187/Point-SAM)               | 311.0M |             — |              — |           — | KITTI360 52.8；S3DIS 63.6；Replica 58.3 | 模型 Apache-2.0；代码 MIT | 未指定；CUDA backend          |

参数量来自 HF 模型元数据；SAM 3.1 分数来自 [Meta 官方 3.1 release notes](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md#video-object-segmentation-vos)，SAM 2.1 分数来自 [Meta 官方 checkpoint 表](https://github.com/facebookresearch/sam2#sam-21-checkpoints)，Point-SAM 数字来自论文的 Voronoi tokenizer 单点击结果（Replica 为单独附录实验）。[Point-SAM 论文](https://arxiv.org/abs/2406.17741)

**模型选择结论：** 服务端质量档首选 SAM 3.1 Tracker；若希望许可简单、部署成熟，首选 SAM 2.1 Large；浏览器 PoC 先用 SAM 2.1 Tiny/Small。Point-SAM 只作为原生 3D 对照或背面补全器，不是主分割器。

| 模型          | 公开状态                                                                    | 一手证据                                                                                                                                                                                                                                                                               | 与本项目匹配度                                   |
| ------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| **Easy3D**    | 官方代码和预训练 checkpoint；模型 CC BY-NC                                  | 原生 voxel/sparse encoder + click decoder；论文构造 GS-ScanNet40，并报告 mesh-trained 模型在 Gaussian 数据上 IoU@1/2/3 为 44.9/55.4/61.5，GS-trained 为 63.9/71.3/74.8。[论文](https://arxiv.org/html/2504.11024#S4.SS7.SSS2)、[代码](https://github.com/facebookresearch/easy3d#demo) | **最值得做的原生 3D baseline**；商用受限         |
| **SNAP**      | 官方代码、多个 checkpoint，MIT                                              | 同一模型覆盖 indoor/outdoor/aerial，支持 point 和 text prompt；项目方报告空间提示 9 个 zero-shot benchmark 中 8 个 SOTA。[项目页](https://neu-vi.github.io/SNAP/)、[代码](https://github.com/neu-vi/SNAP)                                                                              | 商用许可更友好；缺少 Gaussian 专项证据           |
| **Point-SAM** | HF 上 0.3B safetensors，1.24GB，模型卡 Apache-2.0；无 HF Inference Provider | 输入 point cloud + point/mask prompt；官方 demo 支持 `scene.ply`，并建议 >100k points 调大 group 参数。[HF 模型卡](https://huggingface.co/yuchen0187/Point-SAM)、[官方代码](https://github.com/zyc00/Point-SAM#evaluation-and-inference)                                               | 最方便下载的 HF baseline，但不是证据上的当前最佳 |
| AGILE3D       | 官方代码与交互工具                                                          | 支持多物体与 click sharing，但训练于 ScanNet；官方称可迁移到 S3DIS、ARKitScenes、KITTI-360。[项目页](https://ywyue.github.io/AGILE3D/)                                                                                                                                                 | 适合作为 Easy3D 对照                             |

SAM2Point 虽称 3D segmentation，但把 3D 数据解释为多方向视频并复用 SAM 2，并非独立的原生 3D 几何先验。[论文页](https://huggingface.co/papers/2408.16768) Meta 的 `sam-3d-objects` 则是从图像重建单物体 3D，不是对现有场景 point/Gaussian 做实例分割，也不适合本任务。[官方模型卡](https://huggingface.co/facebook/sam-3d-objects)

### 原生 3D 支路的正确用法

推荐只在 analyzer AABB 或高置信多视图初选附近运行：

1. 取 Gaussian mean 作为 point；附带 DC color；按 opacity、尺度和异常值先过滤；
2. 用点击拾取到的最前层 Gaussian mean 作为 positive 3D prompt；用户点错区或多视图负 mask 产生 negative prompts；
3. 原生模型输出逐 point mask，映回原始 Gaussian index；
4. 与多视图证据做 union/intersection 或作为 graph unary prior，而不是盲目替换 2D 结果。

原因是 Gaussian mean 分布高度非均匀，含 floaters、透明层和非表面体积；而大部分 3D 网络训练于 voxelized mesh/LiDAR point cloud。Easy3D 的 Gaussian 实验降低了这个风险，但其数据仍是 ScanNet/SplatFacto，不覆盖所有户外摄影测量 PLY。

## 推荐实现

### 阶段 A：最小可证伪 PoC

**目标：** 证明在当前视图中，2D mask 不会选择物体后面的 Gaussian，同时能无改动复用 delete/duplicate/separate。

流程：

1. 用户启用 Object Select 并点击 `(x,y)`。
2. 用 `camera.intersect` 获得世界交点和 splat；用 ID picker 获得 seed Gaussian。
3. 捕获当前 RGB frame，把点击送给 SAM image predictor，获得一个 2D binary mask。
4. 强制走 `select.byMask(..., Rings/ID)` 路径：读取 mask bounding rect 的 ID buffer，过滤 `0xffffffff`，去重排序。
5. 只调用一次 `new SelectOp(splat, 'set', ids)`；随后直接测试现有 Separate、Duplicate、Delete 和 undo。

最小测试场景应故意包含两个沿相机方向重叠的物体/薄片。若选择中后层 ID 比例仍显著大于零，说明当前 ID pass 的前后排序或 alpha 规则不满足假设，PoC 失败，需改为深度/贡献阈值；若后景污染接近零但物体召回低，这正是预期，进入阶段 B，而不是扩大视锥。

建议验收指标：

- 后层误选率 `< 1%`（合成双层场景有精确 ID 真值）；
- 当前视图的 projected mask IoU `> 0.9`；
- delete/duplicate/separate/undo 四条现有链路全部通过；
- 一次选择只创建一个 history op，不在每个 orbit frame 上传 selection state。

### 阶段 B：轨道视频与证据融合

1. **确定 ROI**：优先用点击深度点；若 analyzer 有同一 object 的多帧 boxes，则用其 position/scale 扩张后的 AABB。AABB 只做候选过滤。
2. **生成轨道**：先做 12–24 个平滑环绕视图；保留用户当前 view 为第一帧。渲染异常时退回原始/临近视角。ArtisanGS 的经验值约 50 views，可作为后续质量档而非初始默认。[ArtisanGS](https://arxiv.org/html/2602.10173#S4.SS4.SSS1)
3. **传播 2D mask**：浏览器 PoC 可用小型 SAM 2 ONNX；服务端质量档可用 SAM 2/3 tracker。模型通过接口隔离，避免 UI 和特定 checkpoint 绑定。
4. **逐 Gaussian 累计证据**：
   - 快速版：每个 view 得到 ID map；对 Gaussian `i` 计算 `q_iv = mask 内属于 i 的像素数 / i 的全部可见像素数`，每视图至多贡献一次，避免大 Gaussian 仅因覆盖更多像素而占优；
   - 质量版：使用 gsplat 的全部或 top-K contributor ID 与 `alpha*T` 权重，把 mask 内权重加到正证据、mask 外可见权重加到负证据；
   - 置信版：维护 `Beta(alpha_i,beta_i)`，最终按 posterior mean、最小观测量和不确定度选择。B³-Seg 给出了同类闭式更新和主动视角依据。[B³-Seg](https://arxiv.org/abs/2602.17134)
5. **一次性提交**：融合完成后才生成一个最终 `Uint32Array` 并交给 `SelectOp`。当前 `SplatState.flush()` 会上传整张 state texture，因此逐帧修改会产生不必要的 O(N×V) 上传。[`splat-state.ts`](../../src/splat-state.ts#L104)
6. **可修正 UI**：展示低置信/冲突 views，允许用户在任意 view 补 positive/negative click 或画 mask，再只重算受影响证据。ArtisanGS 将“能诊断并纠错”视为自动方法落地的关键。[ArtisanGS](https://arxiv.org/html/2602.10173#S4.SS4.SSS4)

推荐的数据边界：

```ts
type ObjectSelectionEvidence = {
  positive: Float32Array;
  negative: Float32Array;
  observations: Uint16Array;
  sourceViews: CameraPose[];
};

type ObjectSelectionResult = {
  indices: Uint32Array;
  confidence?: Float32Array;
};
```

渲染、分割、融合不应知道 undo/history；编辑器只消费最终 `ObjectSelectionResult`。

### 阶段 C：质量和重复查询

- 用 B³-Seg 式 Expected Information Gain 替代均匀轨道，优先渲染最能降低不确定度的视角；
- 用 Easy3D/SNAP mask 对多视图未观察区域做补全，再要求用户确认；
- 对接触物体加入 kNN graph cut，但只能在 mask/语义证据之后使用，不能只靠空间距离；
- 若一个场景需要大量文本/点击查询，再提供离线“语义化场景”任务，训练 SAGA/Click-Gaussian 类 affinity feature，并把 feature 作为 sidecar 资产，而不是破坏普通 PLY 兼容性。

## 关键风险与可证伪检查

| 风险                                    | 最简单的反证/检查                                    | 缓解                                                                  |
| --------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------- |
| ID buffer 不是稳定最前层                | 两个完全重叠、ID 已知的平面；改变透明度和渲染顺序    | 改用 top-K contributor + depth/transmittance threshold                |
| 合成新视角图像失真，SAM 跟踪漂移        | 对每帧记录 mask score、面积突变和与前帧 warp IoU     | 使用原训练相机（若有）；限制轨道；允许用户补 mask                     |
| 背面未观测导致对象残缺                  | held-out 背面视角 projected IoU                      | 增加 elevation/active view；原生 3D refiner；明确“不确定”而非强选     |
| 接触物体通过 3D 邻接泄漏                | 椅子贴墙、桌上物体、枝叶交叠专项场景                 | 外观/多视图证据优先；负点击；graph cut 边权结合颜色、尺度和 mask      |
| 单个大 Gaussian 跨物体边界              | 放大边界，统计高 covariance Gaussian 的错误率        | 初期允许保守缺口；后续研究 SAGD/COB-GS 式 split，但这是几何变更       |
| 透明/反射物体                           | 玻璃、镜面专项数据；比较 ID 与贡献融合               | 多层 contributor；降低单帧权重；要求人工确认                          |
| analyzer 深度/粗框偏差                  | 已知尺寸合成场景比较输出 box 和真值                  | 修复 alpha-normalized/median depth；粗框只做 ROI，不做 selection      |
| 百万 Gaussian CPU/GPU 读回和 state 上传 | 1M/5M/10M splat 的峰值内存、读回、选择延迟           | ROI；GPU 累加；top-K；最终只 flush 一次；分块                         |
| 模型和代码许可                          | 在引入依赖前逐项检查 checkpoint 与代码许可           | Easy3D 仅研究；FlashSplat 只借鉴论文；生产优先 Apache gsplat/MIT SNAP |
| 评估数据过于简单                        | 不只用 LERF/NVOS；加入户外、薄结构、相邻同类、透明体 | 建内部小基准并保留逐 Gaussian 真值/人工审阅                           |

## 建议的决策顺序

1. 先用现有 ID picker + 任意 SAM image predictor 完成阶段 A；这一步能在最少代码下验证产品核心假设。
2. 同时把 `splat_analyzer` 的 frames/boxes/transforms 作为数据接口保留，但不要把其输出 box 当物体本身。
3. 阶段 B 先实现 ID footprint 的 view-normalized voting，再用新版 gsplat contributor API 做 A/B；只有数据证明 ID voting 不足时才上可微优化或线性规划。
4. 用 Easy3D checkpoint 做离线 baseline：同一批点击、同一批场景比较 3D precision/recall、held-out view IoU、延迟和显存。若它对本项目 PLY 的补全收益稳定，再封装成可选 server refiner。
5. 在 5–10 个代表场景、每场景 5 个对象上通过后，再决定是否投入 browser-local 全流程、场景级 affinity training 或开放词汇文本查询。

最值得尽快回答的未知数只有三个：

- 当前 PlayCanvas ID pass 在半透明和极大 Gaussian 下是否仍能提供足够可靠的前层归因；
- 12–24 个围绕点击点的合成视图是否对目标场景保持足够的 SAM 可分割质量；
- Easy3D/SNAP 对真实摄影测量 Gaussian means 的增益是否大于它们引入的域偏差和部署成本。

这三个问题都能用小 PoC 直接证伪，不需要先建设完整语义系统。
