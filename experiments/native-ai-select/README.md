# Native-first AI Select · 有界验证分支

**状态：上游基线与迁移边界已建立；AI Select 尚未移植。** 不是新的生产版本，不能因为本分支构建成功就宣称已经移除算法后端。

当前决定：[Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37#issuecomment-5643008607)。本文件只记录这个分支怎么验证，不建立第二套 Spec 或 Ticket 图。

## 精确基线

- 上游：`playcanvas/supersplat@v3.1.2`，commit `0911f786db652a7700068fe6ccdfe32e24269e1d`。
- 查询日期：2026-09-12。最新 3.x 稳定版已是 3.1.2；不使用不断变化的 main。branch 名中的 3.0 指最初讨论的重写代际。
- 只读比较基线：`upstream/supersplat-v3.1.2`。
- 旧算法参考：`ai-select-v1@e01246163b7226bca440239e8623fc507fdee7f3`，保留其 gsplat/Direct Evidence，不把旧分支删掉或强行 rebase。
- 基准准备：`bench/lerf-teatime-benchmark`。三个 source views、Mask 来源和角色由该分支 manifest 固定。

## 三项 gsplat 判断

1. RGB、新视角、depth/ID picking 和局部空间操作不是 gsplat 独有能力。产品路径先尝试 native renderer。
2. 当前 gsplat + 项目 CUDA 的实际价值是精细的逐 Gaussian 贡献与 P/N/V。单个像素 ID 或代表深度不提供等价信息；保留为 reference，比较后再决定是否需要原生贡献 pass。
3. 双渲染器/场景上传/独立运行环境的代价必须换来实际质量或人工时间收益。不要先移植整个 Companion 再验证价值。

**Gaussian rendering 与 SAM inference 是两个决策。** 首个原生实验可以导入准确 Mask，不新增模型后端；后续模型可用已有服务或研究浏览器推理。没有模型体积、算子、延迟和设备验证，就不能承诺完全无后端。

## 已有上游接口与需要验证的缺口

| 任务 | 当前源码入口 | 边界 |
|---|---|---|
| 排序的投影与深度/ID拾取 | `src/picker.ts` 的 prepareId/prepareDepth/readId/readIds 与 projectedSplatRenderer | 源码可用不是 offscreen benchmark API 已实现；picker 对图层/selection filtering 有自己的语义 |
| 空间笔刷与原生选择命令 | `src/tools/sphere-brush-selection.ts`、`src/editor.ts` | 保留为比较；不可给它改名冒充多视图 AI Select |
| Gaussian相交与变换 | `src/data-processor/intersect.ts` | instance→source row、compact/sort 和 transform palette 必须接清楚，不可假设 GPU row 就是 Stable ID |
| 投影片元 | `src/shaders/projected-splat-shader.ts` | 深度权重不等于旧 Direct Evidence alpha×incoming-T；新近似必须命名并比较 |
| 指定相机RGB、Mask→Gaussian | 需最小专用适配 | 必须记录相机、尺寸、坐标、色彩/渲染模式、输入版本，不把UI截图当任意相机渲染 |
| 精确P/N/V、CWED | 无已验证原生等价实现 | 先以旧路径作reference，不把重写完整CUDA为WGSL当首步 |
| SAM | 本分支没有模型接入 | 浏览器SAM/WebGPU可行性未验证 |

## 不重做的用户设计

保留 [当前 Interface System](https://github.com/Wormh0-le/supersimplat/blob/e01246163b7226bca440239e8623fc507fdee7f3/.interface-design/system.md) 与 #37 的 Q10/Q11：

- Dock/Session Strip 管二维观察、Mask 编辑和自动流程；主3D工具栏管 Anchor/Observation 空间编辑及 Candidate Native 操作。
- 一次点击 authoritative edit 先安全 auto-Pause；被动浏览不暂停；Resume/Continue 明确，不偷偷恢复。
- 视锥体/Navigator/Dock 共用 View identity；draft 高频本地更新，Dock 只在稳定结果边界更新。
- 草稿不是Stable Mask；Candidate发布不是Native应用；取消后迟到无权写入；旧结果失败保留。
- 目标是AI Select最终占用原Sphere Brush位置，其他上游工具与新功能保留。移植完成前不删除比较工具。

## 第一个可证伪实验，而不是整套移植

在同一个固定 Teatime 目标上：固定 native camera/render → 导入与该渲染真正对齐的Mask → 最简单明确命名的native映射 → 仅显示诊断选择，不自动改 Native Selection。记录 source-row/transform 映射、污染/遗漏及人工修正成本，与原生Sphere Brush及旧P/N/V参考相比。

若轻量映射已经够好，先保留轻量实现；若明确在常见重叠场景失败，再验证贡献pass，不能因原计划写过P/N/V就预先重建全部后端。

该实验仍未实现。本次只创建干净上游开发基线、范围约束和真实benchmark准备，不把文档当算法交付。

## 本地启动与验证

```sh
git fetch origin
git switch spike/supersplat-3.0-native-ai-select
npm ci
npm run lint
npm run lint:locales
npm run build
npm run develop
```

此处使用上游 package-lock 和 Node 22。没有新增运行依赖或 Companion。CI 只验证 build/lint/locales；浏览器实际渲染、工具状态、SAM、原生证据、准确Mask以及GPU性能分别需要真实执行记录。

本分支 PR 只与 `upstream/supersplat-v3.1.2` 比较，方便审查新增差异；**不要把它合入旧 ai-select-v1，或反向合入全部旧实现。**
