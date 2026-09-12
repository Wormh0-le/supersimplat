# Frozen M2: apple regression and plate transfer

This increment starts at PR #119's actual unmerged head `9ada1fa31e27990d57919e489453b8e932a3b87d`; its PR base is `feat/native-contribution-attribution`. The initial checkout was clean at `7da53f3c`, on `feat/native-contribution-diagnostic`; that branch and unrelated documentation worktrees were preserved. Fetch confirmed spike at `c9688a4ff8178c4a494fbb75b23f67fcf1efc8cb` and the read-only upstream ref at `0911f786db652a7700068fe6ccdfe32e24269e1d`.

## Frozen input and decision

Reuse the full PLY and external preparation bundle from [TEATIME.md](TEATIME.md). Only `easy-apple` and `medium-plate` are accepted. Actual Mask filenames and all six byte hashes (including C) come from `bundle-report.json`; the benchmark's A/B source hashes must also match. Original bytes are not edited. Reviews bind target, Mask hash and actual native RGB, and are development reviews, not User Confirmed.

M0 and M2 retain [CONTRIBUTION.md](CONTRIBUTION.md)'s exact policy. M1's implementation and historical reports remain, but the runner emits M0/M2 comparisons only. C is an already-observed cross-view regression, never fusion/tuning evidence or formal held-out IoU. Plate means visible plate/rim, excluding cookie holes, table and shadows. Off-frame B pixels do not produce negatives.

Preflight of the existing 988×730 Masks (x/y/width/height):

| Target | A ROI / pixels | B ROI / pixels | C ROI / pixels |
|---|---|---|---|
| Apple | 397/480/76/77 · 5,852 | 615/557/107/106 · 11,342 | 189/536/118/112 · 13,216 |
| Plate | 388/330/155/124 · 19,220 | 811/510/177/220 · 38,940 | 335/213/268/231 · 61,908 |

Plate B touches the right and bottom viewport edges. B/C exceed the existing 20,000-pixel single-call limit; tiling is therefore necessary, not an optimization based on selection quality.

## Bounded execution

The monolithic path stays available at ≤20,000 pixels. Larger ROIs use full-width horizontal bands of ≤20,000 pixels. Policy regions are computed from the **global ROI/full Mask**; tile boundaries add no ignores. Each pixel starts with T=1 and traverses the full native live order, including off-ROI centers whose footprints overlap, and hidden contributors. Shared raw ID arrays accumulate in the same per-ID row-major order as the monolithic path. Classification happens after complete accumulation, without threshold epsilon, normalization or per-tile union.

Before running, the total ceiling is fixed at 65,536 pixels, 80M footprint records, 60 seconds; each tile has 20M records and a 10-second ceiling. Newly allocated evaluator typed arrays remain capped at 128 MiB. Overrides only lower ceilings. Checks are cooperative, not preemptive deadlines. Event-loop yields between bands allow cancellation/target invalidation; an incomplete run cannot replace complete support. Compact support and position export still have the existing 20,000-ID limit until a measured capacity failure justifies a bounded increase.

One snapshot is read once and shared by every band. The runner releases A/B snapshots after frozen A/B evaluation, before acquiring C, avoiding the historical three-snapshot retention. Logical evaluator bytes are `33*N + 69*ROI_pixels + 8*ROI_pixels*Q_sets + 4*selected_IDs + Q_sets`; snapshot buffers, PNGs, report objects and verification comparisons are separate costs. GPU elapsed time, GPU residency and process/JS-heap peaks are not measured.

Plate A trace coordinates use seven fixed rounded Mask-bbox fractions, chosen from A RGB/Mask before support: interior, lower thin rim, two cookie exclusions, lower contact/table, left table and the boundary beside the cookie seam. All samples, including failures, are retained. The full-live-payload independent GPU oracle and opaque-near/hidden-far self-check are unchanged, as are all numerical gates.

## Reproduction

Use Node 24 and an external Playwright 1.63.0 installation, with the existing hardware Chrome CDP endpoint and loopback server:

```sh
npm run lint
npm run lint:locales
npx tsc --noEmit
node --test experiments/native-ai-select/*.test.mjs
npm run build
node experiments/native-ai-select/serve.mjs EXTERNAL_BUNDLE EXTERNAL_FULL_PLY
export PLAYWRIGHT_MODULE=EXTERNAL_PLAYWRIGHT_CORE/index.mjs
export TASK_ID=easy-apple # then medium-plate, after apple regression
node experiments/native-ai-select/run-browser.mjs contribution-a EXTERNAL_OUTPUT
# Inspect the actual A.native.alignment.png before recording the review.
node experiments/native-ai-select/run-browser.mjs contribution-review-a EXTERNAL_OUTPUT 'Actual A review'
# Inspect the actual B.native.alignment.png before recording the review.
node experiments/native-ai-select/run-browser.mjs contribution-review-b EXTERNAL_OUTPUT 'Actual B review'
node experiments/native-ai-select/run-browser.mjs identity EXTERNAL_OUTPUT
node experiments/native-ai-select/run-browser.mjs guards EXTERNAL_OUTPUT
node experiments/native-ai-select/run-browser.mjs target-guards EXTERNAL_OUTPUT
```

The runner separately records same-snapshot first/three warm analyses, apple monolithic/tiled exact comparisons (and plate A while small enough), and failed-phase evidence. Verification-only comparisons retain two evaluator outputs and must not be counted as product latency/memory. Source-row/raw P/N, target and local-negative numerators/denominators, unknown/conflict, M0-relative changes, native overlays and original-full-scene-T Q images remain external. Zero denominators are null, not zero scores.

## Execution outcome

Pending fixed-SHA hardware run and committed-diff review. No algorithm effectiveness or production capacity claim is made by this implementation alone. No SAM, Companion, native Apply, fourth view, semantic checkpoint features, production reduction, new benchmark queue or production cutover is added.
