# Native contribution attribution — bounded Teatime experiment

Diagnostic only, based on `c9688a4ff8178c4a494fbb75b23f67fcf1efc8cb`. This is not AI Select production integration, exact P/N/V, SAM inference, or a replacement for Sphere Brush. See [TEATIME.md](TEATIME.md) for the unchanged complete PLY, camera, Mask and identity contracts.

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

Zero-alpha vertices are skipped as in the native vertex shader. Zero-width cache primitives are reported by identity, including any nonfinite major axis. When present, the oracle replays them across the **whole viewport** and requires zero fragment writes before qualifying the frame. Other nonfinite axes and all exceeded limits fail explicitly. This handles observed native degenerate projection records without changing the renderer, altering the PLY, or silently dropping an unknown finite footprint.

`Q_selected` is the sum of selected contributions under the **original full scene's T**, never a rerender after removing other Gaussians. The grayscale figures are black outside the bounded ROI. Target and local-negative ratios divide selected contribution by full-scene contribution in the corresponding pixels; they are not geometric precision/recall or IoU. Cyan diagnostic overlays retain original Gaussian opacity and ordering; they do not write Native Selection.

## Bounds and cost reporting

Hard CPU-reference limits are 20,000 ROI pixels, 20 million processed footprint records, 16 trace pixels, 20,000 trace records, 128 MiB of newly allocated typed-array storage, 32 evaluation sets and 64 reported zero-width identities. Compact per-view support/position output is limited to 20,000 identities. Exceeding a limit throws an incomplete error; no partial success is returned. The snapshot separately caps output CPU arrays at 96 MiB. Scene-sized outputs are ID statistics and packed caches/order, not a dense pixel-by-Gaussian matrix.

Reports distinguish processed pixels/records, actual live order count, touched IDs, exact new typed-array bytes, padded GPU staging allocation, temporary readback CPU arrays, readback bytes and wall time. They do not measure JavaScript heap/GC high-water marks, driver residency or GPU elapsed time. **GPU total memory is unmeasured.** Retaining A/B/C snapshots adds memory beyond one reference call; raw RGBA16F reads, Q-image encoding and the probe also cost memory/time. Build success is not GPU qualification.

## Results and limitations

Development runs establish feasibility, not a production cutover. Final fixed-SHA results and controlled evidence links will be recorded here after the committed diff review and hardware rerun. Historical M0 counts are comparisons, not cross-run/cross-device byte assertions: native sort/raster ties can change individual winners. Every delivered report records its own exact tested SHA, dirty status, native image hashes and actual per-frame results.
