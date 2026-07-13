# Standalone PLY 3DGS 选择路线补充

> 调研补充：2026-07-13；输入：`/home/ubuntu/Downloads/3DGS场景分割技术路线.md`；范围：只讨论 Standalone PLY 的 Complete Object Selection，不讨论持久对象、资产导出、USD 或重建期语义化。

## 结论

新调研支持现有 PoC 的主链，而不是替换它：**当前视图 ID 提议是可见部分的快速 baseline；完整选择应由质量门控的多视图 2D mask，结合与该渲染同源的 Gaussian contribution evidence 得出；未观察区域必须保持不确定。**

FlashSplat 提供了有价值的 alpha-aware 求解思路，但它的官方实现和许可不能作为 Standalone-PLY PoC 的直接依赖。因此当前 Wayfinder 不应因为这份调研新增方法 ticket 或预先选定算法；图切、dense feature 和 boundary primitive 分裂都应等基准显示出明确缺口后再进入路线。

这与现有的 [场景边界决议](./editor-selection-service-boundary.md)、[SAM 掩码契约](./sam-promptable-mask-contract-facts.md) 和 [冻结基准](./standalone-object-selection-benchmark.md) 一致。

## 经一手资料核实的技术事实

### FlashSplat 是 alpha-aware 求解的参考，不是可直接接入的依赖

[FlashSplat 官方论文](https://arxiv.org/abs/2409.08270)及其[官方实现](https://github.com/florinshen/FlashSplat)把 2D mask 的渲染表述为 Gaussian 标签的线性函数，并利用 alpha blending 的贡献项来求 2D→3D 标签分配；作者将其描述为带背景偏置的闭式/线性规划求解。这个事实支持研究 alpha-aware lifting，而非“按可见 ID 计数”。

这不证明官方代码可直接用于本项目：其 README 仍把 multi-view SAM2 mask association 列为 TODO，仓库继承的[研究/非商业 Gaussian-Splatting License](https://github.com/florinshen/FlashSplat/blob/master/LICENSE.md)也不满足当前核心依赖的要求。若实验 alpha-aware 闭式或优化式求解，必须由项目自己的 renderer、Scene Snapshot、Frame Set 和 Stable Gaussian ID 契约实现；应称作“FlashSplat-inspired variant”，不能称为 FlashSplat 本体。

[gsplat 的 main 文档](https://docs.gsplat.studio/main/apis/utils.html)已公开每像素 all/top contributor IDs 与 radiance weights（top-K 权重为 `alpha * T`）的工具接口，这为项目自有的 contributor evidence 提供了可实现的低层能力。它是主线候选而非已验证结论：当前 analyzer 依赖仍固定 `gsplat==1.5.3`（[`requirements.txt`](../../thirdparty/splat_analyzer/requirements.txt)），使用该接口前必须固定验证过的上游 commit、版本写入 Model/Renderer Manifest，并重跑共享基准。

### 图优化是候选 refinement，不是基础事实

[GaussianCut 论文](https://arxiv.org/abs/2411.07555)明确采用“粗 2D 图像/视频分割 → Gaussian graph → graph cut”的交互多视图分割结构。它支持把图优化视为接触物体、相似颜色或局部漏选时的 ROI-bound refinement 候选；它没有证明图邻接本身能决定本项目中每个 Gaussian 的对象归属，也没有证明其官方实现可直接接受本项目的“只有最终 PLY”输入。

因此 graph edge 只能在多视图证据之后补充，不可用纯空间洪泛替代可见性和负证据。它必须在 contact/difficult GT 上证明降低 leakage 或 correction burden，才值得增加复杂度。

### Dense feature 可辅助关联或边界，但不会产生 Gaussian ownership

[DINOv3 官方仓库](https://github.com/facebookresearch/dinov3)提供 dense/sparse patch matching 与视频分割跟踪示例；其代码和权重采用[自定义 DINOv3 License](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md)，不是当前 PoC 可默认绑定的许可证。[LingBot-Vision 论文](https://arxiv.org/abs/2607.05247)提出 boundary-centric 的自监督 dense representation；其[官方仓库](https://github.com/Robbyant/lingbot-vision)当前标示 Apache-2.0，但项目在 2026-07 初才公开，且论文没有针对 Standalone 3DGS 的 Gaussian ownership 评测。

两者最多可给跨视图 mask association、appearance affinity 或 boundary prior 提供额外证据；它们都不替代 SAM 的 promptable 2D mask、同源 contributor attribution，或 Stable Gaussian ID 返回。因此不应成为当前 PoC 的必需依赖或新的主线 ticket。

## 对现有 PoC 的技术落点

| 层次                                         | 在 PoC 中的角色                                                                                                                       | 约束与判据                                                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 当前视图 `mask ∩ ID-buffer-visible Gaussian` | 快速、可见表面 baseline                                                                                                               | 不宣称 Complete Object Selection；在受控前后重叠场景测后层污染。                                                   |
| 多视图 contributor evidence                  | 主 lifting 候选，待[“Compare 2D-to-Gaussian lifting methods on shared masks”](https://github.com/Wormh0-le/supersimplat/issues/7)验证 | RGB、mask 和 contributor 必须来自同一次服务端 rasterization；按正、负、未观察累积。                                |
| FlashSplat-inspired variant                  | 仅在项目自有 renderer 内的可选 A/B                                                                                                    | 与上项共用 Frame Set、Mask Set、GT、阈值和 Stable IDs；不复用官方代码或把其假设带入 PoC。                          |
| mask association                             | 先由同一 prompt log/Mask Track 和 Gaussian evidence overlap 维持                                                                      | 仅在同类实例混淆可量化时，再 A/B dense feature。                                                                   |
| graph / boundary refinement                  | 条件性局部实验                                                                                                                        | 只处理已量化的 contact/difficult 失败；先输出 uncertain/boundary diagnostic，不改变 Gaussian primitive 或冻结 GT。 |

“边界 primitive 拆分/trim”尤其不应混入本 PoC 的选择比较：它会改变 Gaussian 集合和 Stable ID 空间，令现有冻结 Ground Truth 与 candidate 方法不再可比。当前可测的是边界处的 selected/rejected/uncertain 分类，不是重建质量。

## 证据与不确定性的补强

新调研反复强调的关键不是“多投票”，而是 observation semantics：

- mask 内、可靠可见的 contributor 产生正证据；
- mask 外、可靠可见的 contributor 才能产生负证据；
- 被遮挡、出视野、渲染失真或 mask 被质量门拒绝的 Gaussian 是 **unobserved**，不是 negative；
- 当正负证据冲突或总观察量不足时，返回 `Uncertain Gaussian`，不进入 Selection Commit。

这正是当前地图中“Coverage Report 只报告观察，不决定选择”和[“Define Selection Evidence and uncertainty semantics”](https://github.com/Wormh0-le/supersimplat/issues/8)的问题边界。不要用跨视图硬交集、或把未入镜部分计为负票来换取表面上更干净的结果。

另一个实现修正是：本仓库的普通 PLY 加载会 Morton reorder 并原地置换行（[`loader.ts`](../../src/io/read/loader.ts#L119-L132)），所以任何比较输出都必须使用编辑器的 Stable Gaussian ID，而不能把输入 PLY row 当跨前后端的永久身份。现有 `state` byte 也只承载 `selected`、`locked`、`deleted` 三个编辑位（[`splat-state.ts`](../../src/splat-state.ts#L5-L18)），不应被算法证据复用。

## 建议的 Wayfinder 影响

**建议暂不修改地图或[“Compare 2D-to-Gaussian lifting methods on shared masks”](https://github.com/Wormh0-le/supersimplat/issues/7)的问题文本，也不新开 ticket。** 该任务已经把 current ID visibility、contributor-weighted evidence、hard voting 和 SA3D-style soft optimization 放在正确的决策缝上；本补充应作为它的研究证据。

若共享基准结果显示 alpha-aware closed-form 或背景偏置确有独立、可重复的增益，可在[“Compare 2D-to-Gaussian lifting methods on shared masks”](https://github.com/Wormh0-le/supersimplat/issues/7)的实验配置中加入一个明确标为 `flashsplat-inspired/project-owned` 的子变体，而不是引入 FlashSplat 依赖。[“Define Selection Evidence and uncertainty semantics”](https://github.com/Wormh0-le/supersimplat/issues/8)已覆盖 evidence/uncertainty，无需改动。GaussianCut、DINOv3、LingBot-Vision、SAGD/GaussianTrimmer 类方法只在前述 lifting 对比的失败报告能隔离出“关联错误”“接触泄漏”或“边界混合”中的某一种，且简单 baseline 无法通过时，再作为后续有验收标准的实验 ticket。

## 来源

- 输入调研文档：`/home/ubuntu/Downloads/3DGS场景分割技术路线.md`
- [FlashSplat 论文](https://arxiv.org/abs/2409.08270)；[官方实现](https://github.com/florinshen/FlashSplat)
- [gsplat contributor utilities（main）](https://docs.gsplat.studio/main/apis/utils.html)
- [GaussianCut 论文](https://arxiv.org/abs/2411.07555)
- [DINOv3 官方仓库与许可证](https://github.com/facebookresearch/dinov3)
- [LingBot-Vision 论文](https://arxiv.org/abs/2607.05247)；[官方实现](https://github.com/Robbyant/lingbot-vision)
