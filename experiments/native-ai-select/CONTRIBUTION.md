# Native contribution attribution — bounded Teatime experiment

Diagnostic only, based on `c9688a4ff8178c4a494fbb75b23f67fcf1efc8cb`. This is not AI Select production integration, exact P/N/V, SAM inference, or a replacement for Sphere Brush. See [TEATIME.md](TEATIME.md) for the unchanged complete PLY, camera, Mask and identity contracts.

The subsequent frozen-policy apple/plate increment is recorded separately in [M2-PLATE.md](M2-PLATE.md). Results below remain the unchanged #119 history.

## Reproduction

Use Node 24 (native TypeScript stripping for the focused numerical tests), the installed PlayCanvas version from the lockfile, and a real WebGPU browser. No new test platform or dependencies:

```sh
npm run lint
npm run lint:locales
node --test experiments/native-ai-select/contribution-reference.test.mjs
npm run build
node experiments/native-ai-select/serve.mjs EXTERNAL_BUNDLE EXTERNAL_FULL_PLY
# Set PLAYWRIGHT_MODULE to an installed playwright-core/index.mjs.
# CDP_URL defaults to http://127.0.0.1:9333.
node experiments/native-ai-select/run-browser.mjs contribution-a EXTERNAL_OUTPUT
# Inspect A.native.alignment.png before supplying an actual review note.
node experiments/native-ai-select/run-browser.mjs contribution-review-a EXTERNAL_OUTPUT 'A development alignment review'
# A rule is frozen before B is captured. Inspect B.native.alignment.png.
node experiments/native-ai-select/run-browser.mjs contribution-review-b EXTERNAL_OUTPUT 'B development alignment review'
node experiments/native-ai-select/make-figures.mjs EXTERNAL_OUTPUT EXTERNAL_BUNDLE
node experiments/native-ai-select/run-browser.mjs guards EXTERNAL_OUTPUT
node experiments/native-ai-select/run-browser.mjs identity EXTERNAL_OUTPUT
```

Keep the model, Masks, screenshots, JSON traces, hardware information and logs outside this repository. Use a controlled artifact/draft release, not a public/latest release. A/B reviews are explicitly development reviews, **not User Confirmed**. The existing default non-contribution runner phases remain available.

## Methods and fixed policy

All views are 988 × 730: A=`test_0`/183, B=`test_2`/182, C=`test_1`/181. Only A and A+B may create candidates. C cannot analyze support into the fusion store or create a candidate set; its draft Mask is not certified IoU ground truth.

- **M0** retains `native-alpha-gated-frontmost-id-hit/v1`, alpha threshold **0.1**, per-Mask-pixel frontmost ID then A/B union. The A capture also repeats thresholds 0 and 1/255. It remains an alpha-gated picker, not exact contribution attribution.
- **M1** takes the largest `w_i = alpha_i * T_i` at each original Mask pixel, then unions instance IDs. Equal weights retain the first contributor in the exact near-to-far payload traversal. No independently reconstructed depth sort.
- **M2** retains all ROI-local contributions. Positive pixels are a square radius-2 erosion of the original Mask. Explicit local negatives are outside the Mask, more than 4 pixels away in Chebyshev distance. The remaining boundary and ROI-border neighborhoods are ignored. ROI is the original Mask bounding box plus **16 pixels** on every side, clipped to the original viewport. This is local evidence, never full-image negative evidence.

M2 selects an ID when `P >= 1` pixel-equivalent of contribution and `P/(P+N) >= .8`. Zero denominator or total support below 1 is unknown. `P >= 1 && N >= 1` is a reported conflict, which can coexist with selection when positive support dominates. A+B sums immutable raw per-view statistics with fixed coefficients `[1,1]`; there is no per-view normalization, posterior feedback or treatment of an unobserved view as negative. These are simple diagnostic support statistics, not calibrated probabilities or Direct Evidence P/N/V.

The fixed A trace samples are `(434,516)`, `(446,528)`, `(414,520)`, `(434,540)`, `(434,550)`, `(459,536)`, `(409,547)` (interior, silhouette and nearby table). B/C use a fixed ROI-relative five-point numerical regression stencil, not selection/tuning evidence. The runner refuses comparisons after a failed trace gate.

## Same-frame reference and numerical qualification

`readDiagnosticSnapshot` queues the actual RGB frame's packed cache A/B, sorter payload and survivor count before picker reprojection. It copies the instance/source-row mapping and preserves placement bases. Only a locked, sorted, untinted, single-placement frame is allowed. Pending color grading or native selection tint is rejected. The native renderer, selection flags, EditHistory and Sphere Brush are not modified by analysis or overlays.

The CPU reference decodes native packed snorm/half/UNORM/shared-exponent fields, reconstructs f32 clip vertices and the qualified NVIDIA/D3D12 8-bit subpixel raster grid, and streams the exact draw order backwards. It includes ellipse footprints whose centers lie outside the ROI, fully occluded contributors, and original-scene transmittance. There is no 0.1 filter in M1/M2, .99 opacity cap, residual early exit, top-K truncation, or H×W×N matrix. Background transmittance remains background, not an ID.

The native target blends gamma-encoded colors into RGBA16F. A double-precision color sum and even a simple binary16-storage model are not identical to fixed-function half-target blending. The trace report preserves those errors. A separate bounded raw-WebGPU fragment/blend oracle mirrors the packed-cache quad math, checks CPU alpha/weights and compares its RGBA16F replay against the original native target. It is a verification instrument, not the ROI producer or a speedup claim. Gates: replay error ≤ .002, CPU alpha/weight error ≤ 1/1024, fixed-sample RGBA8 difference ≤ 1 code, conservation error ≤ 1e-12. Conservation alone is not qualification. Full-ROI RGBA8 errors are separately reported; a fixed-sample pass does not establish bit-exact full-ROI reconstruction or portability to another GPU.

The oracle independently draws **every entry in the captured live payload** for each fixed pixel; it does not use the CPU contributor list as its input. A per-draw-slot storage write records every invoked fragment, including zero-weight layers behind an opaque foreground. GPU/CPU ID lists and draw slots must match exactly before any numerical gate may pass. A 1×1 GPU self-check also requires observing a far layer hidden by an alpha=1 near layer. Its live payload is capped at one million entries and its emitted fragment reports at 20,000 records. One N-slot buffer is read per pixel sequentially, not H×W×N; this additional verification readback is reported separately.

Zero-alpha vertices are skipped as in the native vertex shader. Zero-width cache primitives are reported by identity, including any nonfinite major axis. When present, the oracle replays them across the **whole viewport** and requires zero fragment writes before qualifying the frame. Other nonfinite axes and all exceeded limits fail explicitly. This handles observed native degenerate projection records without changing the renderer, altering the PLY, or silently dropping an unknown finite footprint.

`Q_selected` is the sum of selected contributions under the **original full scene's T**, never a rerender after removing other Gaussians. The grayscale figures are black outside the bounded ROI. Target and local-negative ratios divide selected contribution by full-scene contribution in the corresponding pixels; they are not geometric precision/recall or IoU. Cyan diagnostic overlays retain original Gaussian opacity and ordering; they do not write Native Selection.

## Bounds and cost reporting

Hard CPU-reference limits are 20,000 ROI pixels, 20 million processed footprint records, 16 trace pixels, 20,000 trace records, 128 MiB of newly allocated typed-array storage, 32 evaluation sets and 64 reported zero-width identities. Compact per-view support/position output is limited to 20,000 identities. Exceeding a limit throws an incomplete error; no partial success is returned. The snapshot separately caps output CPU arrays at 96 MiB. Scene-sized outputs are ID statistics and packed caches/order, not a dense pixel-by-Gaussian matrix.

Reports distinguish processed pixels/records, actual live order count, touched IDs, exact new typed-array bytes, padded GPU staging allocation, temporary readback CPU arrays, readback bytes and wall time. They do not measure JavaScript heap/GC high-water marks, driver residency or GPU elapsed time. **GPU total memory is unmeasured.** Retaining A/B/C snapshots adds memory beyond one reference call; raw RGBA16F reads, Q-image encoding and the probe also cost memory/time. Build success is not GPU qualification.

## Results and limitations

### Qualification and provenance

Final hardware evidence is from clean code SHA `5c83bf01c98479919e5b032949dfca1198d75bcd`: Chrome **153.0.8010.36** on Windows, NVIDIA GeForce RTX 4070 Laptop GPU, driver **32.0.16.1062**; WebGPU reports vendor `nvidia`, architecture `lovelace`. A subsequent documentation-only commit is not a retest of renderer code. The external `final-5c83bf0/summary.json` summarizes the numerical report; adjacent guard, identity, default-load, warm-check and hardware JSON retain their separate checks.

Lint, locales, build and all **11 numerical tests** passed. All **17 browser guards** passed, including immutable support, recapture invalidation, rejected late results, unchanged flags and Sphere Brush availability. The identity fixture passed transformed centers, duplicate source rows, compaction, locked eligibility and Undo; main selection/history and UI counts were unchanged. This fixture qualifies world centers within a 0.025-unit GPU sphere, not exact position readback or production cloning; it does not exercise picking, sort/compact draw payload, overlay invalidation or camera capture. Ordinary native loading of the full **2,746,452-row PLY** also passed with the diagnostic absent, no diagnostic chunk requested, unchanged selection flags and Sphere Brush available.

Two independent review axes at `8d9fa77` found a P1 subset-only GPU replay completeness gap and a P2 stale B-recapture report. Both were fixed in `a3d07b4` and confirmed by focused deep review. `5c83bf0` only corrected expected guard-error logging in the runner; the final hardware run used that clean SHA.

At all **17 fixed pixels** (7 A, 5 B, 5 C), independent GPU replay of **every live native draw entry** matched CPU contributor IDs and draw slots exactly; native RGBA16F replay error was **0**. The opaque-near/hidden-far GPU self-check passed. B/C zero-width entries produced no fragments over the whole viewport. Maximum CPU alpha error was 0.0002811, weight error 0.0000673 and conservation error 2.34e-15. Full-ROI CPU color errors were at most **2 RGBA8 codes for A/B, 1 for C** (means 0.08694/0.07073/0.06774 codes). This is fixed-sample GPU qualification on this device, not a bit-exact full-ROI or cross-device guarantee.

### Selection results

Each cell below is **target contribution % / local-negative contribution %** under the original scene transmittance. These are contribution ratios, not IoU, geometric coverage or certified semantic accuracy. Candidate counts are M0/M1/M2 = **427/410/336** for A-only and **641/583/970** for A+B.

| Candidates | Evaluation view | M0 | M1 | M2 |
|---|---|---:|---:|---:|
| A-only | A | 53.60 / 0.690 | 55.90 / 3.731 | 56.62 / 0.024 |
| A-only | B | 43.65 / 1.578 | 47.21 / 3.207 | 45.94 / 0.110 |
| A-only | C draft | 36.17 / 0.422 | 40.98 / 0.532 | 34.20 / 0.330 |
| A+B | A | 65.36 / 4.400 | 64.87 / 5.049 | 80.87 / 0.110 |
| A+B | B | 63.06 / 9.513 | 64.26 / 5.516 | 83.17 / 0.226 |
| A+B | C draft | 55.08 / 1.198 | 56.93 / 3.475 | 69.15 / 1.008 |

Development visual review found that A+B M2 drastically reduces A's downward/table trails and B's left/right table streaks, while filling the apple better. C still misses the upper red cap. A-only M2 **worsens C draft target contribution** to 34.20%, versus 36.17% M0 and 40.98% M1; lower local-negative contribution does not remove that omission. C supplied no selection evidence or rule tuning. These observations are not User Confirmed.

A+B M2 changes M0 by **+445 / −116** instances. Rounded source-position bounds `(x,y,z)` are:

| Delta | Minimum | Maximum |
|---|---|---|
| Added 445 | (−0.623684, 2.036090, 0.579246) | (−0.351780, 2.374190, 1.014633) |
| Removed 116 | (−0.726867, 2.091540, 0.852220) | (−0.242476, 2.509639, 1.472395) |

These are coordinate bounds, not semantic labels; units are not assumed to be meters. External `changed-instances.csv` and `report.json` preserve delta source rows, full source/world positions and raw per-view P/N. The fused support report contains 15,387 IDs, 12 conflicts and 13,390 unknowns.

### Broad, faint foreground counterexample

At alpha threshold 0, source row **2502665** owns all **1,478 A Mask pixels** in the picker. Threshold 1/255 yields 63 IDs; threshold 0.1 yields 427 A IDs, 544 B IDs and 641 in their union. Row 2502665 has quantized peak alpha **9/255 = 0.035294**, decoded half axis 1 `(88.375, 2.083984375)` and axis-2 length `74.8125`. Its sampled alpha and weight range from about **0.000549 to 0.020875**, with incoming `T = 1`. A broad footprint and frontmost ownership do not imply dominant contribution.

Its A target contribution is **6.765 / 1,478 = 0.458%** per Mask pixel, with raw support **P = 5.113, N = 14.095**. It is not a dominant apple contributor. M2 rejects it by the fixed support rule, with no special-case ID blacklist.

### Observed costs and remaining limits

The shared CPU reference evaluates the methods together; these costs are **not isolated M0/M1/M2 latency benchmarks**. The reference wall times below include accumulation for the respective Q sets, but exclude PNG encoding and report construction. A-only/A+B denote candidate sets, not different native payloads.

| View | ROI pixels | Live draw entries | Footprint records | Touched IDs | Evaluation ms, A-only / A+B | New typed-array bytes, A-only / A+B |
|---|---:|---:|---:|---:|---:|---:|
| A | 5,852 | 583,451 | 1,504,024 | 15,153 | 920.6 / 676.0 | 91,181,847 / 91,185,931 |
| B | 11,342 | 263,647 | 2,864,616 | 9,729 | 935.9 / 880.9 | 91,692,417 / 91,696,501 |
| C | 13,216 | 298,348 | 3,416,280 | 7,300 | 994.6 / 966.8 | 91,866,699 / 91,870,783 |

`warm-check.json` repeats the same no-Q analyze call on one frozen snapshot per view. First call then three warm calls (ms): **A 616.3 → 647.8, 641.9, 670.3; B 742.5 → 694.5, 744.0, 690.3**. New typed-array bytes per call were 91,036,704 A and 91,415,514 B. These are not cold-start timings; the separate main-run initial analyses were 707.3/686.4 ms.

Snapshot readback was **65,932,620 bytes** per reported A/B snapshot, taking 214.2/114.0 ms in the main run (426.1/162.0 ms in the warm-check capture). Each snapshot retained **76,918,428 CPU bytes**; its known CPU readback buffer allocation bound was **132,063,388 bytes**, padded GPU staging allocation **66,131,460 bytes**. These are buffer-accounting values, not measured heap or driver residency. Independent GPU oracle costs are additional:

| View | Oracle wall ms | Readback bytes | CPU typed peak bytes | Allocated GPU peak bytes |
|---|---:|---:|---:|---:|
| A | 362.9 | 65,348,304 | 21,004,492 | 36,109,636 |
| B | 182.9 | 21,093,040 | 9,491,548 | 19,479,828 |
| C | 188.3 | 23,869,120 | 10,740,784 | 21,284,280 |

Retaining three snapshots, three half-float images and the largest ROI reference gives a **logical added live typed-array subtotal of 339,935,827 bytes**. It excludes JavaScript/GC, Q-image encoding and baseline buffers; it is **not a measured process or GPU peak**. GPU total memory and GPU elapsed time remain unmeasured.

Retain the bounded **M2 experimental path**, rather than replacing it with M1 alone: A+B shows useful target contribution and contamination improvements, but A-only omissions, the C upper-cap miss, CPU/readback costs and single-device qualification remain material limits. No production cutover, exact P/N/V equivalence or production readiness is established. Historical picker counts are comparisons, not cross-run byte assertions; sort/raster ties can change individual winners.

Controlled evidence: [draft release](https://github.com/Wormh0-le/supersimplat/releases/tag/untagged-8f79c00b1b0bd314389e) (`native-contribution-evidence-5c83bf0`, target `5c83bf01c98479919e5b032949dfca1198d75bcd`). It remains a draft, not a public/latest release; draft access requires repository permissions. Archive `native-contribution-5c83bf0.tgz` is 52,436,571 bytes; SHA-256 `77cc62e2dc2bb1192e4da6f71246473806533571257db1d1329fd95e3c9fcdc5`, also confirmed by the uploaded asset digest. It contains raw reports/traces, figures, changed-instance CSV, hardware/check logs, the unchanged input bundle and a per-file checksum manifest; the full PLY is referenced by its pinned hash rather than duplicated.
