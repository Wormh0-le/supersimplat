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

Before running, the total ceiling is fixed at 65,536 pixels, 80M footprint records, 60 seconds; each tile has 20M records and a 10-second ceiling. Newly allocated evaluator typed arrays remain capped at 128 MiB. Overrides only lower ceilings. Checks are cooperative, not preemptive deadlines. Event-loop yields between bands allow cancellation/target invalidation; an incomplete run cannot replace complete support.

Plate A at clean `92c0f0f` passed its frozen trace gate but explicitly failed the historical 20,000-ID compact-output cap before publishing support. Failure evidence is retained separately. The compact/position envelope was then raised **once to 65,536 identities**, matching the declared experiment's pixel envelope as a storage budget, not asserting one ID per pixel. It applies to each view and the A+B union before support replacement. No plate selection/support was inspected to choose that ceiling; a further overflow is incomplete, not permission to discard IDs or keep raising the budget.

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

**Capacity requirements are not met: cross-object M2 validation is incomplete.** Apple regression succeeds; plate M2 is neither qualified as effective nor demonstrated ineffective. Do not advance to the interactive prototype, increase the fixed ceiling again, introduce a remedy, or add more benchmark objects in this task.

### Exact execution and checks

Final runtime evidence uses clean `49c3221c32d28d63996f6a4f610c7decb214cec5`, Windows Chrome 153.0.8010.36 / RTX 4070 Laptop, NVIDIA Lovelace. Main apple, plate failure and plate M0 reports have empty dirty state. Later default-load and B M0 A-only overlay replay used identical built browser source; their sidecars explicitly record the offline `make-figures.mjs` working change. Later figure/document commits do not change runtime selection code.

Node 24 numerical/target tests: **20 passed**. Lint, locales, build and `tsc --noEmit` passed. Apple **17 existing + 10 target/capacity guards** passed, as did identity/transform/compaction/SelectOp Undo with unchanged main UI counts. Diagnostic-disabled full 2,746,452-row loading, zero native flags, absent diagnostic chunk and Sphere Brush passed. No SwiftShader replay or new cross-GPU qualification is claimed.

Post-commit review at fixed base `9ada1fa3` found no Standards findings and one Spec P1: a request invalidated while waiting in the command queue could execute under the next target. Actual browser red evidence reproduced this. `92c0f0f` binds generation before enqueue; untinted/tinted queued switch/cancel and in-flight invalidation checks pass. Independent focused follow-up confirmed the fix. Final independent Standards and Spec reviews of `9ada1fa3...740e376` found no further actionable issues; all software checks passed again at clean `740e376`.

### Apple regression

Each cell is **target contribution % / local-negative contribution %**, with original-full-scene T. The external report retains every numerator and denominator; these are not IoU or geometric precision.

| Frozen selection | Evaluation | M0 | M2 |
|---|---|---:|---:|
| A-only | A | 53.631 / 0.690 | 56.610 / 0.024 |
| A-only | B | 43.679 / 1.578 | 45.935 / 0.110 |
| A-only | C draft | 36.192 / 0.422 | 34.202 / 0.330 |
| A+B | A | 65.355 / 4.400 | 80.867 / 0.110 |
| A+B | B | 63.056 / 9.513 | 83.168 / 0.226 |
| A+B | C draft | 55.077 / 1.198 | 69.149 / 1.008 |

M0/M2 counts are 428/336 (A-only) and 641/970 (A+B). M2 A+B changes M0 by +445/−116; raw fused support reports 13,390 unknown and 12 conflict IDs. Visual inspection confirms much less downward/table contamination and fuller apple tint, but C's upper red cap remains missed. A-only M2 still underperforms M0 on C draft target contribution.

The final A+B M0 and M2 **ID sets exactly match #119**, not merely their counts. M0 A alone adds ID 2495896 (428 versus 427); that ID was already present in B, so the union is unchanged. The intermediate `b483001` run gave M2 968: IDs 7483 and 2713313 had fused P=0.954695 and 0.967942, respectively, below the unchanged minimum 1. At `49c3221`, their B raw contributions increase and fused P becomes 1.229031 and 1.016861; both have N=0. `apple-cross-run-delta.json` retains exact A/B rows and changing capture hashes. The native cross-capture cause was not isolated; no claim that a specific sort tie caused it is made.

All reports are retained rather than forcing historical counts. On each identical final A/B snapshot, monolithic versus four horizontal bands gives **exact zero difference** in regions, total/T/RGBA/Q, raw P/N and classification. No selection epsilon was added. All 17 apple fixed-pixel full-live GPU identity/order and numerical gates pass; RGBA16F replay error is zero.

### Plate: explicit storage failure, not algorithm failure

A/B native alignment was inspected before their respective mapping. Original Mask bytes were retained, including cookie holes and A's thin annotation exclusion slit. B clips the plate at the right and bottom viewport edges. No out-of-frame negatives were invented and no development review is called User Confirmed.

Plate A's seven fixed samples `(428,378), (465,430), (474,375), (445,407), (465,444), (395,392), (510,399)` all pass the unchanged full-live GPU gate and hidden-far check. Replay error is zero; maximum alpha error is 0.000374727, weight error 0.000014077, RGBA8 difference 1 code. No failing sample was removed.

The 19,220-pixel A ROI records **68,497 distinct instance IDs** across 6,132,733 footprint records, exceeding the frozen compact limit 65,536. These are ROI-recorded identities, not a claim that all are visibly contributing or selected. A read-only debugger inspection of the retained snapshot at the existing throw recovered the exact count/summary; it did not alter limits, inspect labels, drop IDs or modify candidates. Both the initial 20,000-cap failure and final 65,536-cap failure remain external. No complete plate M2 support or selection was published.

Independent M0 continuation retains A-only 1,126, B 1,201 and A+B 1,936 IDs, with A/B native overlays and frozen C draft inspection. Detail crops show rim/contact, cookie holes, the retained slit and B clipping. Some B cookie tint and table/rim contamination remain visible in M0; this is a baseline observation, not a measured M2 counterexample.

**Missing:** plate M2 A-only/A+B selections and overlays, plate M0/M2 Q metrics, B/C M2 numerical/evaluator runs, plate warm/per-tile timings, plate monolithic/tiled hardware comparison and semantic failure attribution. Without complete support these must not be replaced by zero scores or an inference that frozen M2 fails on plates.

### Cost and remaining limits

| Measured item | Apple A | Apple B |
|---|---:|---:|
| First same-snapshot no-Q evaluator ms | 261.9 | 255.3 |
| Three subsequent no-Q evaluator ms | 282.1 / 237.9 / 237.6 | 239.8 / 242.2 / 241.0 |
| Footprint records | 1,504,024 | 2,864,616 |
| New evaluator typed-array bytes (no Q) | 91,036,704 | 91,415,514 |
| Snapshot readback bytes | 65,932,620 | 65,932,620 |
| Snapshot readback wall ms | 211.2 | 104.0 |

These are shared reference timings, not isolated M2 speedups or cold-start/product latency. Independent GPU oracle readback costs are additional: A 65,348,304 bytes / 199.6 ms, B 21,093,040 / 94.6 ms, C 23,869,120 / 100.5 ms. Full trace workflows additionally include CPU/sample verification; do not substitute them for product runtime.

Plate A snapshot readback is 65,932,620 bytes / 259.6 ms; retained snapshot CPU arrays are 76,918,428 bytes. Its complete numeric evaluator before compact failure allocates 91,959,096 typed-array bytes. The debugger-audited evaluator reports 710.4 ms, explicitly **instrumented verification**, not an ordinary first/warm timing. A was one block; real B/C tiles were not reached. Plate A's GPU oracle is an additional 65,348,304-byte readback / 197.8 ms, with 2,633 emitted verification records.

Snapshot(s) + half images + current evaluator give a logical non-verification subtotal of about **257.0 MB** at apple A/B evaluation and **174.6 MB** for plate A. The apple parity instrument separately retains two ~91 MB evaluator outputs; it is not product memory. These subtotals exclude JS compact rows/GC, PNG encoding, baseline buffers and driver residency. GPU total memory, GPU elapsed time, actual process/heap peak and human correction time remain unmeasured. The bounded tiling implementation has CPU/fixture and apple same-snapshot evidence, not production capacity approval.

Complete images, original bytes, raw/failed reports, numerical traces, summaries, source-row data, timing/check logs and checksums are in the [controlled draft release](https://github.com/Wormh0-le/supersimplat/releases/tag/untagged-a36e356652e53997b0b0), tag `native-m2-plate-evidence-49c3221`. Authenticated retrieval: `gh release download native-m2-plate-evidence-49c3221 --repo Wormh0-le/supersimplat`. Keep the release draft; no full PLY is duplicated. #119 history remains unchanged.
