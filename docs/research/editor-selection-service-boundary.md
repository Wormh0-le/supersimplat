# Editor ↔ Selection Service scene boundary

> 调研日期：2026-07-12  
> 问题：对单个 Target Splat，渲染和 2D→Gaussian attribution 应在哪一侧运行，哪些数据跨边界，如何保证结果仍指向编辑器里的同一批 Gaussian。

## 决议

采用 **Editor-owned identity, Service-owned inference render**：

- 编辑器是 Target Splat 身份、当前内容版本、Gaussian 稳定 ID 和最终 Selection Commit 的唯一权威。
- Selection Service 在 GPU 上同时执行 Generated View 的 RGB 渲染、2D mask 推理和 contributor-weighted 2D→Gaussian attribution。RGB 与 attribution 必须来自同一次、同一参数的 rasterization；不要由编辑器渲染 RGB、服务端另行重建可见贡献。
- 一个 Target Splat 的不可变 **Scene Snapshot** 只在该内容版本首次使用时上传。服务端按内容摘要缓存 GPU-ready scene；后续 `New/Add/Remove/Refine` 只传 `sceneVersion`、相机和提示。
- 服务返回按编辑器稳定 ID 排序的稀疏证据/结果，不返回服务端 tensor row、tile ID 或 renderer 内部排序。编辑器先验证版本，再预览；`Confirm` 才交给现有 `SelectOp`。

这是 scene boundary，而不是编辑状态边界。Candidate Object Selection、普通 Gaussian Selection、undo/redo 和删除/复制/分离仍只存在于编辑器。

## 为什么渲染与 lifting 必须同侧

gsplat 的官方 rasterization API 同时消费 Gaussian means/quaternions/scales/opacities/colors、world-to-camera `viewmats`、相机内参 `Ks`、图像尺寸、near/far plane、camera model 和 rasterization mode；这些参数共同决定每个像素的颜色与贡献者。[gsplat rasterization API](https://docs.gsplat.studio/main/apis/rasterization.html)

2D mask 的语义只能可靠地分配给**产生该像素的同一组贡献者**。若浏览器用 PlayCanvas 生成 RGB，而服务端用 gsplat 计算 attribution，即使相机表面上相同，以下差异仍可能改变边界、遮挡顺序或小 Gaussian 是否出现：

- 相机坐标系、矩阵布局、FOV→intrinsics 换算和像素中心约定；
- near/far、分辨率、背景和投影模型；
- scale/opacity 是否已激活、SH degree、antialias/classic 模式、2D epsilon 和 radius clipping；
- deleted Gaussian、per-Gaussian edit transform、Target Splat world transform 和 renderer 的内部排序。

因此服务端对所有 Generated Views 生成 RGB 与 contributor data，并把它们视作一个原子产物。官方 gsplat API 已提供 CUDA rasterization；其公开项目为 Apache-2.0，并说明 PyPI 安装会构建 CUDA 代码。[gsplat 官方仓库](https://github.com/nerfstudio-project/gsplat) 当前仓库的 analyzer 已使用 `gsplat==1.5.3`，但该版本现有 backend 只渲染 RGB/深度；contributor attribution 应作为同一 CUDA renderer 的新能力实现，而不是复用编辑器的 front-most ID buffer。[现有 backend](../../thirdparty/splat_analyzer/renderers/gsplat_backend.py)

初始用户视图是一个例外但不是第二套 lifting：编辑器可以上传精确的 display RGB 作为首帧分割输入，以保留用户看到的色调/背景；服务仍必须用同一相机重渲 attribution，并在协议里标记 `rgbSource=editor`. 若重渲 RGB 与上传帧的校验差异超过阈值，该视图只能用于提示初始化，不能成为无提示的负证据。Generated Views 不走这个例外。

## 跨边界契约

### 1. Scene Snapshot：每个内容版本上传一次

逻辑头（JSON/MessagePack 均可）：

```text
protocolVersion
sceneId                 // 本次编辑文档内 Target Splat 的不透明 ID
sceneVersion            // immutable content digest + schema/render semantics version
gaussianCount
coordinateConvention    // handedness, camera forward/up, matrix order, units
attributeSchema         // name, dtype, shape, encoding
stableIdSchema          // uint32; unique within sceneVersion
appearance              // SH degree, background/alpha policy needed by inference render
```

二进制列：

- `stableId: uint32[N]`；
- `mean: float32[N,3]`、`rotation: float32[N,4]`、`logScale: float32[N,3]`、`logitOpacity: float32[N]`；
- DC/SH appearance，保留 snapshot 声明的 band 数；
- 可选的 `sourceRow: uint32[N]` 仅供诊断，不能作为结果身份。

Snapshot 必须表示**编辑器此刻实际渲染的 Target Splat**：排除 deleted Gaussian，并烘焙 Target Splat world transform、per-Gaussian transform palette、当前几何/颜色编辑。仓库加载器会为普通输入执行 Morton reorder，故原始 PLY row number 不是编辑会话中的可靠身份；`stableId` 应在加载/重排完成后分配，并在该 `sceneVersion` 内保持不变。[loader](../../src/io/read/loader.ts) 现有 PLY serialization 已具备排除 deleted splats、解析 per-Gaussian palette transform 与 world transform 的代码路径，可抽取为 snapshot builder，而不要另写一套变换规则。[serializer](../../src/splat-serialize.ts)

`sceneVersion` 应覆盖规范化后的 schema、稳定 ID 与所有会影响 RGB/attribution 的列和语义参数。显示名称、选择状态和相机不进入摘要。任何增删、几何/颜色变更、动画帧替换或 stable-ID remap 都产生新版本；纯相机移动、普通 selection、locked bit 不产生新版本。

### 2. View/Prompt request：每次 Update Preview

```text
requestId, sessionId, sceneId, sceneVersion
operation               // New | Add | Remove | Refine
round, deterministicSeed
views[] {
  viewId,
  width, height,
  worldToCamera[16], K[9],
  near, far, projectionModel,
  prompts[] { kind, xPx, yPx },
  optionalEditorRgbRef
}
renderConfigVersion
previousEvidenceToken   // opaque, optional incremental-cache handle
```

传 `worldToCamera + K + width/height`，不要只传 position/target/FOV：后者不足以唯一恢复非方形 viewport、principal point 和投影细节。矩阵仍需附明确 convention 和一个协议级 golden-camera test，不能假设 TypeScript 与 PyTorch 对同一 16 个 float 的解释一致。请求中的 prompt 使用像素坐标并绑定 `viewId`，因此相机锁定规则可被服务端验证。

### 3. Result：版本化、稀疏、可诊断

```text
requestId, sessionId, sceneId, sceneVersion, renderConfigVersion
status, modelVersion, timings, peakVram
views[] { viewId, maskRef, maskConfidence, accepted, rejectionReason }
gaussians[] {
  stableId,
  positiveEvidence,
  negativeEvidence,
  observationWeight,
  posterior,
  uncertainty
}
selectedIds: uint32[]
uncertainIds: uint32[]
evidenceToken
warnings[]
```

服务应返回足以重算阈值和解释 uncertain 的聚合证据，而不只返回 binary mask。数组必须按 `stableId` 升序、去重；所有浮点字段定义范围、NaN/Inf 处理与精度。`maskRef`/Generated View 可按需获取用于 UI 诊断，不嵌入主结果。

编辑器只接受 `sceneVersion` 与当前 Target Splat 完全相等、ID 均存在且互斥的结果。旧请求完成、取消后迟到、服务重启或用户在计算中编辑场景，都不得把 stale result 套到新版本。服务端 cache miss 返回明确状态，让客户端重传 snapshot；不能悄悄按同名文件复用。

`locked` 是编辑器可选择性而不是渲染内容：切换它不重建 Scene Snapshot，服务也不需要把它当成 inference 属性。编辑器在生成 Candidate Object Selection 与 Selection Commit 前，必须用当前状态过滤 locked Gaussian，并报告被过滤数量；不得假设服务返回的目标归属自动等于“当前可提交”。deleted Gaussian 已从 snapshot 排除，删除会产生新 `sceneVersion`。

## 缓存与传输

缓存分三层，key 都含版本：

1. `sceneVersion → canonical CPU columns / GPU tensors`；
2. `(sceneVersion, renderConfigVersion, view digest) → RGB + contributor summary`；
3. `(modelVersion, frame digest) → image embedding/mask state`。

第 1 层是必要优化：大场景每轮重传会让交互时间主要消耗在网络和反序列化，而 GPU scene 本身没有改变。第 2 层允许相同相机的提示修订只重跑 mask decoder/融合；第 3 层复用分割 encoder。缓存是性能机制，不是身份机制；每项必须由完整 key 验证，并可被 LRU/TTL 淘汰。

Scene Snapshot 和结果使用二进制 frame/stream，不把百万级 float 或 ID 编成 JSON。浏览器 WebSocket 可直接把二进制消息接收为 `ArrayBuffer`；Web Worker 的 `ArrayBuffer` transfer 会移动所有权而非复制底层资源，适合在编码/哈希 worker 与主线程间交接大列。[WebSocket `binaryType`](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/binaryType)、[Transferable objects](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Transferable_objects) 网络传输仍会复制并受 backpressure 约束，因此协议要有 byte length、digest、分块/断点、最大尺寸、超时和取消；不得把浏览器零拷贝误写成端到端零拷贝。

## 备选方案比较

| 方案                                   | 传输/性能                                                                  | 正确性                                                                          | 许可与部署                                                       | 结论                                                |
| -------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------- |
| **服务端 render + lifting（推荐）**    | snapshot 每版本一次；后续小请求；GPU tensors 可缓存                        | RGB 与 contributors 同源；最容易复现和审计                                      | gsplat Apache-2.0；需要 CUDA/PyTorch 服务                        | 默认边界                                            |
| 编辑器 render RGB/ID，服务只跑 2D 模型 | 可只上传 images/masks，但多视图像素数据随轮次增长；浏览器要做大量 readback | front-most ID 不等于 alpha-weighted contributors；无法可靠区分 tail/遮挡/未观察 | 保持 MIT/PlayCanvas 客户端简单，服务 GPU 压力较小                | 仅作单视图 baseline，不作 Complete Object Selection |
| 编辑器 RGB，服务重建 attribution       | 少上传 RGB 生成工作，但仍需上传 scene                                      | 两端 renderer 差异使 mask 和 contributor 不共像素真相，是最隐蔽的失败模式       | 同时维护 PlayCanvas 与 gsplat 语义                               | 拒绝                                                |
| 浏览器完成 render、SAM 和 lifting      | 无 scene RPC，隐私/离线最好                                                | 单一实现可一致，但现有 Web renderer 没有完整 weighted-contributor path          | 避免 CUDA 服务；模型、显存、浏览器兼容和大场景 readback 风险最高 | 未来离线档，不阻塞 PoC                              |
| 每轮上传 PLY，由服务返回 row indices   | 无 cache 协议                                                              | 编辑期间 reorder/filter/transform 后 row identity 易漂移；stale result 难检测   | 实现表面最小，带宽/解析成本最大                                  | 拒绝                                                |

许可证结论限于已核查组件：SuperSplat 顶层声明 MIT，[项目 package](../../package.json)；gsplat 官方仓库为 Apache-2.0。[gsplat LICENSE](https://github.com/nerfstudio-project/gsplat/blob/main/LICENSE) 当前 analyzer 的 CUDA 服务依赖 gsplat；其 Apple Metal backend 源码已明确标记 gsplat-mps 为 AGPLv3，因此不能把 Metal backend 与推荐 CUDA 部署视作同一许可结论。[Metal backend](../../thirdparty/splat_analyzer/renderers/gsplat_metal_backend.py) 模型权重、Torch/CUDA 容器和未来 codec 仍需各自做部署清单审计。

## 最小可证伪验证

在实现完整服务前，用一个前后重叠的程序化场景锁定协议：

1. 编辑器对重排后 Gaussian 分配稳定 ID，执行一个 world transform、一个 palette transform 和一个 deletion，再构造 snapshot。
2. 对同一 golden camera，让服务输出 RGB、top/all contributors 和 selected IDs；用编辑器截帧做像素差诊断。
3. 校验服务返回 ID 能逐一映回正确 Gaussian，deleted ID 从不出现，变换后的投影位置一致。
4. 改一项内容产生新 `sceneVersion`，让旧请求延迟返回，验证编辑器拒收；仅移动相机则复用 scene cache。
5. 对相同 snapshot/view/config 重放三次，验证排序、集合和证据在约定容差内确定；记录上传、GPU materialization、render、mask、lifting 与下载的独立耗时。

只有 stable-ID round trip、stale-result rejection 和同源 RGB/contributor 三项都通过，才继续模型质量比较。否则准确率变化无法被可靠归因于分割或 lifting 算法。

## 与现有研究的分工

[`object-aware-gaussian-selection.md`](./object-aware-gaussian-selection.md) 已决定多视图 mask propagation、contributor-weighted evidence、Beta/uncertainty 和候选算法顺序；本文不重做模型排名。本文新增的约束是：这些算法必须消费一个版本化的 Target Splat snapshot，Generated View 的 RGB 与 contributor attribution 由同一个服务端 renderer 原子产生，最终证据只通过编辑器稳定 ID 回到 Candidate Object Selection。
