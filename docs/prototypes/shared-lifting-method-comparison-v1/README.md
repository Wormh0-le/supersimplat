# Shared 2D-to-Gaussian lifting comparison v1

该原型比较同一份冻结的 Scene Snapshot、Frame Set 与 Mask Set 上的四种 lifting 方法。预测阶段不读取 Benchmark Ground Truth：每个方法先写出 Stable Gaussian ID 结果及其 hash，随后评分阶段才打开真值。

运行器：[compare_shared_lifting_methods.py](../../../scripts/benchmarks/compare_shared_lifting_methods.py)。输入 manifest 为 [`shared-lifting-benchmark-v1.json`](../../benchmarks/fixtures/shared-lifting-benchmark-v1.json)，其 SHA-256 是 `3b52c0abf55097d0dfd48624b9187b2085a261411e9efac085ae4933c175514c`。

## 保守两视图结果

固定比较策略：top-K=8、mask bounding box 外扩 24 px、至少两个 accepted view、累计 alpha×transmittance 观测量至少 0.10；比值 ≥0.80 为 selected、≤0.20 为 rejected，其余为 uncertain。该策略只用于本次比较；产品级 Evidence/uncertainty 阈值仍由后续决策定义。

| 场景                          | Current top-1 | Hard top-1 vote | Contributor three-state | Soft mask fit |
| ----------------------------- | ------------: | --------------: | ----------------------: | ------------: |
| controlled front/back overlap |         0.405 |           0.211 |                   0.374 |         0.374 |
| gift_box（simple）            |         0.254 |           0.425 |                   0.897 |     **0.945** |
| microwave（contact）          |         0.230 |           0.385 |                   0.849 |     **0.889** |
| clothes_rack（difficult）     |         0.226 |           0.242 |                   0.634 |     **0.714** |

表中为 Gaussian-index IoU；全部 candidate 在真实 office 目标上的 selected precision 都至少为 0.994。三种 office 目标中，soft fit 相对 contributor three-state 分别提高 0.048、0.040、0.080 IoU；额外求解耗时为 17–31 ms，四方法并行原型峰值 VRAM 约为 0.98–1.00 GB。

受控场景的 Coverage Report 本身为 `insufficient_coverage`。它说明不能把“保守两视图”当作完整选择的通过证明：四种方法都保留大量 target 为 uncertain，而不是把未观察区域当成 negative。

完整的可重放输出在：

- [conservative-two-view/report.md](conservative-two-view/report.md)
- [conservative-two-view/result.json](conservative-two-view/result.json)
- [conservative-two-view/prediction-manifest.json](conservative-two-view/prediction-manifest.json)

每个场景目录中还保存了每种方法的 selected/rejected Stable Gaussian ID `.npz`；未列出的 ID 即 uncertain。

## 敏感性检查

将最低观测数从两个 accepted view 改为一个，office 的排序不变：soft fit 的 IoU 为 gift_box 0.952、microwave 0.918、clothes_rack 0.767，仍高于 contributor three-state 的 0.904、0.882、0.685。受控场景中 contributor three-state 为 0.896，soft fit 为 0.895，差异不构成 soft 变体在该场景的独立收益。

将 support margin 从 24 px 扩到 48 px 后，保守两视图的 office IoU 变化小于 0.001。这个检查排除了 ROI 边缘恰好有利于 soft fit 的简单解释。

详细敏感性资产在 [one-view-sensitivity/report.md](one-view-sensitivity/report.md) 和 [one-view-sensitivity/result.json](one-view-sensitivity/result.json)。

## 观察与建议（等待人类决策）

1. `current_top1_visibility` 只应保留为可见表面 baseline；其真实目标 IoU 为 0.226–0.254，不能代表 Complete Object Selection。
2. `hard_top1_vote` 虽没有明显 contact leakage，却在真实目标上只达到 0.242–0.425 IoU，丢弃 contributor 权重的代价可量化。
3. `contributor_three_state` 应成为 PoC 必需主线：它在同一 service-side rasterization 中保存 positive、negative、unobserved，且三组真实目标均显著优于两个 top-1 baseline。
4. `soft_mask_fit` 有可重复的真实目标增益，但在受控 overlap 上未胜出，并增加数值求解、配置和测试负担。因此推荐将它指定为**项目自有的质量档 A/B 变体**，而不是取代三态 evidence 的基础契约；它不是 SA3D 或 FlashSplat 的实现或依赖。

所有 office Coverage Report 都是 `insufficient_coverage`，且 clothes_rack 的三个 `not_found` views 在本次比较中保持 neutral。因此这些结果不证明 Ready Object Selection，也不允许把 uncertain 直接提交；它们只回答本票的 lifting 比较问题。

## 许可和实现边界

本原型只使用现有 `gsplat 1.5.3` contributor API 和项目代码；没有下载或调用 SA3D、FlashSplat、GaussianCut、DINOv3 或任何新模型/权重。soft fit 是项目自有的线性 alpha×transmittance 拟合，因此没有新增外部许可依赖，但其数值稳定性、阈值和回归测试仍是额外实现风险。
