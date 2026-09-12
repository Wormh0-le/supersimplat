# Teatime 苹果：原生 Mask→Gaussian 诊断

这是可证伪的 development/oracle-mask 实验。不是生产 AI Select、SAM 接入、原 LERF-Mask held-out 成绩，也不宣称优于 Sphere Brush 或旧 P/N/V。

## 输入和运行边界

只复用已合入 `ai-select-v1@4265d862a81dd6f1895746d106425b19b8316ca6` 的 `benchmarks/teatime` 和两个输入准备脚本。模型、RGB、Mask 和运行证据均在仓库外。完整模型包含 2,746,452 行、856,894,946 bytes；浏览器对实际导入 Blob 验证 SHA-256 `09c2fe384fcd667645bec188ac7e0dee332496d7ea5580d77cb6222ef6ca49e0`，随后从同一个 Blob 导入。

Gaussian Grouping checkpoint 有语义训练来源。原生上传只请求 position/geometric/color，不读取 `obj_dc_*`、classifier、object_mask 或 pickle 来选择目标。没有裁切全场景遮挡体。

A=`test_0`/183，B=`test_2`/182，C=`test_1`/181；全部 988×730，完整 K 和 COLMAP w2c 保存在报告。相机采用 `model × inverse(COLMAP w2c) × diag(1,-1,-1)`，包括 PLY 默认导入旋转。fx/fy 分别进入投影矩阵，不用单个 FOV 近似。原生 compute projector 在计算前应用自定义投影，并读取实际离屏尺寸。RGB 使用 sorted alpha blend、SH3、linear tone mapping、exposure=1、minPixelSize=0、黑背景、无网格/工具 gizmo，near=.01/far=1000。

A/B 来源 Mask 字节与尺寸必须匹配。先导出当前 native RGB 和洋红边界叠图，检查位置、轮廓及桌面投影排除，再记录发展实验可视核准。此记录明确不是 `User Confirmed Stable Mask`；CI 只重放已检查输入，新的 CI 图仍可供审阅。C 为 assistant polygon draft，只在 A+B 后加载检查，不能进入 `map()`，不报告正式 C IoU。

## 明确命名的近似

`native-alpha-gated-frontmost-id-hit/v1`：对整个固定场景进行原生 sorted ID pass，仅保留 `normExp(radius) × Gaussian alpha >= 0.1` 的片元；在 Mask 像素中收集最近赢家的 layer-local instance IDs。A+B 只做集合并集。没有负证据、置信权重、incoming transmittance 或隐藏 Gaussian 恢复。

0.1 只根据 A 的具体反例固定，在 B/C 前冻结。原生工具的默认门限仍为 0，Sphere Brush 与原生选区行为保留。异常时诊断拾取参数复位。独立 uint 纹理按 instance ID 给 Gaussian 染青绿色，沿用其原透明度和遮挡；不写 instance flags、调色板或 edit history。关闭 Overlay 即恢复正常显示。

身份是 `(实际 PLY SHA, layer uid, instance ID, original source row)`，不是 GPU draw slot。专用导入 `skipReorder=true`，并核验完整 identity source-row 列表。普通导入默认 Morton 重排后的 `sourceRow` 不应冒充原始 PLY 行。渲染 compaction/sort 携带 entry identity，Overlay 用 `entry - placement.entryBase` 索引实例。此有界输入要求一个完整、可见、未锁定的原始 layer；模型/instance palette 编辑后拒绝继续使用旧 Mask。

选择、几何变更、删除和 transform drag 开始使证据失效。读回及 Mask 解码完成时都检查 generation；晚到结果不能重新出现。重新 capture A/B 必须重新核准，A 会失效下游 B/C。失败保留先前有效 Overlay，显式失效则清空。C capture 不改变 A/B ID 集合。

## 本地复现

先按已合入的准备脚本获得外部 bundle 和 `point_cloud.ply`；现成准备结果可直接复用。无需切换或合入旧算法分支。

```sh
npm ci
npm run lint
npm run lint:locales
npm run build
node experiments/native-ai-select/serve.mjs /outside/teatime-abc /outside/teatime/point_cloud.ply
```

服务只绑定 loopback 3187，避免与旧应用的 3000 端口混淆。启动一个独立 Chrome profile，启用 `--remote-debugging-port=9333`。`PLAYWRIGHT_MODULE` 指向仓库外安装的 `playwright-core@1.63.0/index.mjs`；不添加应用依赖。

```sh
export PLAYWRIGHT_MODULE=/outside/browser/node_modules/playwright-core/index.mjs
node experiments/native-ai-select/run-browser.mjs a /outside/evidence
# 先查看 A.native.alignment.png，再填写实际检查结论
node experiments/native-ai-select/run-browser.mjs review-a /outside/evidence '实际 A 边界核准说明'
# A-only 已运行，此时查看 B.native.alignment.png
node experiments/native-ai-select/run-browser.mjs review-b /outside/evidence '实际 B 边界核准说明'
node experiments/native-ai-select/run-browser.mjs identity /outside/evidence
node experiments/native-ai-select/run-browser.mjs screenshot /outside/evidence
node experiments/native-ai-select/make-figures.mjs /outside/evidence /outside/teatime-abc
node experiments/native-ai-select/run-browser.mjs guards /outside/evidence
```

`guards` 最后运行：它会故意使诊断会话失效，单独输出 `guards.json`，保留先前冻结的报告与检查图。浏览器 console 也可使用：

```js
const d = window.scene.events.invoke('nativeMaskDiagnostic');
await d.load('/bundle/', '/point_cloud.ply');
const a = await d.capture('A'); // a.png / a.alignment 是实际离屏 PNG
// 看图后 d.review('A', '具体核准结论'); d.map('A');
d.overlay('A'); // 'AB' 或 'off'
await d.focus(); // 只调浏览相机；可继续自由旋转，Sphere Brush 仍在原工具栏
```

## 证据与已知失败

实际本地硬件运行使用 Windows Chrome 153、NVIDIA Lovelace / RTX 4070 Laptop，完整场景原生 WebGPU。`report.json` 记录精确 tested SHA、dirty 状态、浏览器和 adapter、相机、原始 RGB/ID 哈希、每个候选的 instance/source rows、实际 PLY hash 和分阶段耗时。PR 正文给出最终测试 SHA；构建记录不代替浏览器证据。各次运行可能因排序深度量化/并列顺序出现少量逐像素或候选差别，不要求跨设备 byte-identical。

| 检查图 | 内容 |
|---|---|
| `01-alignment.png` | A/B 原生 RGB、原始 Mask 边界、局部放大；原始图仍为 988×730 |
| `02-a-only.png` | A-only 非破坏性原生 Gaussian 染色与遗漏 |
| `03-ab.png` | 固定 A∪B 在 A/B 中的表现 |
| `04-c-inspection.png` | 独立 C 的 draft 边界、A-only 和 A+B；不参与融合或调参 |

另有真实编辑器 `browser.png`，可看 Native Selection 计数与保留的工具栏。`identity-ui.json` 核验 fixture 前后状态栏仍为完整模型、零原生选区/锁定/删除。推送此 spike 或手工触发 `Native AI Select baseline` workflow 并令 `browser=true`，会尝试生成同一 SHA 的 `native-teatime-browser-*` artifact（30 天保留）。远端使用 SwiftShader 软件 WebGPU，不代表硬件性能；必须检查 job 结果，失败 artifact 可能只有错误日志。`8fad7d1` 的远端及本地软件运行发生 device-lost；测试启动器禁用 GPU watchdog 后的结果见 PR，不把构建通过当成软件回放成功。

具体失败和限制：

- 原生门限 0 在 A 的全部 1,478 个苹果 Mask 像素上只命中 source row **2502665**，重复运行仍相同。该行 logit opacity=-3.265126（中心 alpha≈.03679），位置 `[-.8270288, 2.0386415, .1504044]`，log-scales `[-1.1319680,-1.7521006,-16.1265965]`。低透明度前景椭圆可以占满 ID，却几乎不贡献苹果的 RGB；picking 与 P/N/V 不等价。固定配置 `8fad7d1` 实测较低门限 1/255 得到 63 个实例，仍包含该污染行；每次报告都实际重测两个对照门限，不将中间运行的数量当常数。
- 0.1 门限能形成可见苹果 Overlay，但它会漏掉低 alpha、有用的后方贡献和未被 A/B 看到的表面。A+B 的 C 图仍有红色未染区域及斑驳，不能将“Mask 像素都有 ID”解释为完整对象被选中。边缘染色可能略伸到桌面，当前没有三维 GT 定量污染率。
- 不跨 layer 推断完整遮挡：上游 picker 会过滤到单个 layer。此 harness 明确拒绝多 layer/锁定/编辑后的输入，而非静默减弱旧遮挡与输入身份保证。
- 当前排序的深度量化和单 ID 舍弃其它贡献；alpha≥.1 不包含 incoming T。透明物体、精确 P/N/V、CWED 和旧 Direct Evidence 数值对照均未资格验证。
- GPU 身份 fixture 用独立字面 world centers 核验 source-row、重复实例、实体非均匀变换与 palette 组合；核验 native SelectOp 锁定/Undo、删除压缩及恢复，主选择不变。该 fixture 不单独资格认证 sorter 的全体并列 ID 稳定性或生产 cloning。
- Sphere Brush 可用，但尚未做人类完整操作/修正/Undo 的配对计时；旧 P/N/V 没有本次同输入运行成绩。人工 Mask 核准耗时与人工纠错收益也未量化。不得据此宣称质量或总时间优于它们。

最小后续缺口是**保留每像素多 Gaussian 的 alpha×incoming-T 贡献及输入行/实例身份**，以同一 A 反例对照当前 winner 近似。是否值得增加原生贡献 pass 取决于这些遗漏和人工修正成本；本 PR 没有重建完整后端或 stage graph，没有 Companion/SAM 服务、生产 cutover 或自动 Native Selection 应用。
