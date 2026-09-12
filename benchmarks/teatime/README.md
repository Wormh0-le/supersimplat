# Teatime：三个难度、三个真实视角

当前决定在 [#37](https://github.com/Wormh0-le/supersimplat/issues/37#issuecomment-5643008607)，算法验证仍属于 #115。本目录是可运行的数据准备工具，不是新 Spec/ADR 体系。

## 已实际核对，而不是示例文件名

来源为 Gaussian Grouping 作者发布的 LERF-Mask `teatime`。它是茶桌/咖啡馆室内场景，不是完整餐厅/茶水间扫描。

| 角色 | source image | COLMAP image ID | Mask 来源 |
|---|---|---:|---|
| A 输入 | test_0.jpg | 183 | 发布者 test_mask/0，完整原字节复制 |
| B 补充输入 | test_2.jpg | 182 | 发布者 test_mask/2，完整原字节复制 |
| C 检查 | test_1.jpg | 181 | 本次补绘的 polygon draft；不冒充官方GT或User Confirmed |

全部 988×730。官方 archive 实际只有 15 张 Mask，位于 0/2 两组；不存在第三组官方 Mask，也没有先前示例中的茶壶标签。A/B/C 明确映射，不能把排序第二张当 B。

| 任务 | 梯度理由 | 排除边界 |
|---|---|---|
| easy-apple | 不透明、紧凑、与邻物分离 | 不含桌面与投影 |
| medium-plate | 薄盘沿、饼干遮挡、桌面接触；B 有画面裁切 | 只标可见盘子，饼干作为孔洞排除 |
| hard-glass | 透明杯沿和杯体，外观/几何归属困难 | 按来源的茶杯与内容物轮廓，不含包装/茶签/桌面 |

难度是本次任务设计，不是经过用户实验校准的量表。先跑苹果，再盘子，玻璃杯作困难案例；不要把透明杯 silhouette 当精确物理玻璃表面真值。

## 一次准备，得到9张Mask和9张叠图

Python 3.12，数据必须在仓库外。不会执行 checkpoint pickle、训练脚本或模型推理。

```sh
python -m pip install Pillow==11.3.0
python scripts/prepare-teatime.py --out /path/outside/repo/teatime --with-model
python scripts/bundle-teatime.py --prepared /path/outside/repo/teatime/prepared --out /path/outside/repo/teatime-abc
python -m unittest discover -s scripts/tests -v
```

`--with-model` 会下载约751MB的checkpoint ZIP；数据ZIP约257MB。已有ZIP只有SHA匹配才复用，已生成目录不静默覆盖。省略该开关可只准备RGB/Mask/标定。

输出：A/B/C.rgb.jpg；每个角色的 easy-apple、medium-plate、hard-glass 二值 PNG 与同尺寸 overlay；benchmark.json；bundle-report.json。C 的可编辑坐标在本目录 `C.annotations.json`。外部产物保留 provenance，没有任何 userConfirmed=true。

GitHub Actions 的 `Teatime asset preparation` 在本分支自动实际下载、校验并生成整包 artifact（保留30天）；过期后可用固定来源重建。仓库只存来源锁、精确相机、A/B Mask 哈希与 C polygon、脚本/测试，不塞巨型模型和图像。

## 模型和相机的准确边界

模型实际为2,746,452个Gaussian、856,894,946 bytes。使用完整场景保留遮挡，不先抠目标；但不要对整场景执行无界O(N²) connectivity。

模型来自 **Gaussian Grouping语义训练checkpoint**，不是vanilla RGB-only训练基线。只能把xyz/scale/rot/opacity/SH作为固定资产；`obj_dc_*`、classifier和object_mask不得用于AI预测。对比结果需披露这个训练来源，不能拿它冒充独立重建上的无泄漏算法排行榜。

内参来自未畸变 `sparse/0/cameras.bin`，fx=775.3188460434766，fy=778.7358059194906，cx=494，cy=365。manifest中的COLMAP qvec是WXYZ，定义world-to-camera：p_c=R(q)p_w+t。不要当c2w使用；原世界尺度不承诺米。只改显示大小不意味着改实验分辨率；改分辨率必须同步K/RGB/Mask身份。

**source RGB/GT 不等于当前renderer RGB/Stable Mask。** 先用同一相机和指定的native或Companion渲染模式输出实际RGB，再检查轮廓并必要时改Mask。图像同尺寸也不能证明边界对齐。不得将这次下载记录自动升级为人工确认或GPU验收。

当前 A/B 使用原官方test标注作oracle输入，因此这是 **custom development protocol**，不是原LERF-Mask held-out成绩。C只用于独立检查，不参与Seed/Scope、选择或调参；C标注仍为draft，未经核准不报正式定量分数。展示C叠图核对标注本身，不等于用算法结果调参。

## 已执行与未执行

已执行：固定数据与模型ZIP SHA校验；真实目录/标签/三视图核对；PLY头及内容SHA；COLMAP标定提取；A/B二值Mask和source RGB同尺寸检查；C多边形补绘、孔洞和叠图检查；本地数据边界测试。

初次来源运行：[34668993112](https://github.com/Wormh0-le/supersimplat/actions/runs/34668993112)，精确SHA `ac6da8e7efb4b945b8bec5308d202a4d0ad63a27`。最终整包执行以PR中的新运行记录为准。

未执行：native/Companion真实渲染、Mask与新渲染核准、SAM、P/N/V比较、人工基线计时、GPU速度/显存验证。#115不因此关闭或自动ready。

## 来源与使用条款

- https://huggingface.co/mqye/Gaussian-Grouping （作者发布元数据标注 Apache-2.0）
- https://github.com/lkeab/gaussian-grouping/blob/main/docs/dataset.md
- https://github.com/lkeab/gaussian-grouping/blob/main/render_lerf_mask.py

模型/相片/数据按各自上游条款使用，代码仓库MIT不替代数据条款。A/B保留发布者字节和归属；C为本次补充草稿。下载不执行 .pth、cfg_args；不提交私有本地资产。Bonsai历史材料保留，不继续作为强制案例。
