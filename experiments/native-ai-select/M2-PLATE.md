# Frozen M2: apple regression and plate transfer

**Current continuation:** the support-row blocker is removed, but plate B fails the unchanged numerical gate. See [continuation evidence and remaining blocker](#continuation-evidence-and-remaining-blocker). Earlier execution outcomes below are preserved historical records, not the current storage status.

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

## Support storage correction — authorized continuation of #120

[Review instruction](https://github.com/Wormh0-le/supersimplat/pull/120#issuecomment-5651817636) explicitly authorizes this representation correction. The historical runs, two capacity failures, tested SHA and incomplete conclusion above remain unchanged. No selection rule, input byte, oracle gate or evaluator pixel/record/time ceiling is relaxed.

Before new hardware selection results, the additional support working envelope is fixed at **256 MiB**, including a **4 MiB export reserve**. This is two existing 128 MiB evaluator envelopes as a separate logical storage allowance, not measured spare GPU memory. A table owns two Uint32 identity columns and four Float64 raw-sum columns: **40 bytes per touched instance**, including weak, N-only and zero-weight entries. The finite scene has 2,746,452 instances; one hypothetical full-scene table would cost 109,858,080 bytes. The budget does not promise that all simultaneously retained worst-case tables fit.

The preallocation check includes retained A, B and A+B columns, retained M1 winner-number payloads, the incoming view and its prospective complete merge **while the previous complete result remains live**. Tables merge in ascending instance ID with no per-ID index (index bytes: zero); equal source rows do not collapse distinct instances. Selection-list numeric payloads are separately checked against the same envelope. Exceeded budgets, malformed sizes, stale input and cancellation reject before publication. Only the owned previous tables count as retained; a caller keeping exported copies has separate costs.

No writable column reference escapes the table. Reports retain summaries, not expanded rows. `support(role, offset, count)` exports at most 4,096 immutable copied rows; `contributionPositions(offset, count, token)` uses a separate 4,096-row position pool instead of borrowing the source pool's million-row allocation. At the frozen 12-byte position stride, its capacity is 49,152 bytes plus at most 16,384 bytes of source indices. The 4 MiB reserve covers a numeric page and finite-number JSON staging; exports are bound to a support-version token, drained page-by-page and completed externally only after the full count matches. The runner writes `A/B/AB.support.jsonl`, `AB.positions.jsonl` and selection files outside the repo. JavaScript objects/GC, caller-retained copies, baseline source caches, process peaks and GPU residency remain unmeasured.

Q/metrics-only analysis runs the same full-occlusion kernel but does not materialize support or M1 output. C cannot publish into the A/B store. Snapshot and evaluator arrays retain their separate original bounds/accounting; oracle parity checks retain additional outputs and are explicitly verification costs, not product latency. Apple checks compare the old object representation against columns on a single snapshot, and full-output against metrics-only Q/metrics. Large B/C ROIs compare two bounded band partitions (not an over-limit monolithic run); each band's wall time and records are retained.

### Continuation evidence and remaining blocker

**The old support-row blocker is removed; the plate experiment is still incomplete, now at B's frozen numerical gate.** This is neither GPU OOM nor evidence that M2 is ineffective on plates. No interactive prototype or numerical-policy change is authorized by these results.

Implementation commit `b0b38fdb9186c4d33771ba69a66cd632dfc948fb` passed 29 Node 24 tests, lint, locales, TypeScript and build. Independent Standards and Spec reviews of `eab90a3...b0b38fd` found the same P2: plate C's purported comparison used identical bands. `9d5e46564d8fc2f9c0a51a605e5b7e3ad778c00b` fixes comparison partition selection and requires `partitionsDiffer`; 30 tests and all software checks pass. Independent follow-up confirmed the fix. CPU fixtures verify B `[112,108]` versus `[56,56,56,52]`, C `[74,74,74,9]` versus `[37,37,37,37,37,37,9]`, complete coverage and unchanged per-band bounds. These fixtures are not B/C GPU qualification.

Hardware evidence is separately bound to **clean `b0b38fd` for apple** and **clean `9d5e465` for plate/default loading**, on Chrome 153.0.8010.36 / RTX 4070 Laptop, driver 32.0.16.1062. The latter commit changes verification partitioning only, not selection or contribution arithmetic; apple evidence is not relabelled as a later tested SHA. Full PLY, bundle and Mask hashes remain pinned.

#### Apple: representation parity and cross-capture difference

On each retained A/B snapshot, old object rows versus new columns have **zero identity, raw-statistic, unknown/conflict and classification differences**. Full-output versus metrics-only Q/metrics are identical; metrics-only support bytes are zero. A has 15,153 rows / 606,120 bytes, B 9,729 / 389,160; A+B has 15,387 / 615,480. External reconstruction verifies every A+B raw sum and selected ID, and all 15,387 position rows restore the same identities/source rows. Numerical A/B/C and same-snapshot tiling gates pass.

M0/M2 A-only counts remain 428/336. A+B is 641/969, not historical 641/970: ID 7483 has unchanged A P=0.21475289740309023, but B P=0.739941888160625 versus historical 1.0142779382189813, so fused P=0.9546947855637152 is below 1, with N=0. It is retained as unknown, not dropped from support. All other historical M2 A+B IDs match. Capture hashes and exact rows are in `apple-cross-capture-delta.json`; the underlying cross-capture cause remains unisolated. No epsilon or historical-count assertion masks the difference.

Current **target contribution % / local-negative contribution %**, always using original-full-scene T:

| Apple selection | Evaluation | M0 | M2 |
|---|---|---:|---:|
| A-only | A | 53.634 / 0.690 | 56.615 / 0.024 |
| A-only | B | 43.686 / 1.578 | 45.943 / 0.110 |
| A-only | C draft | 36.192 / 0.422 | 34.204 / 0.330 |
| A+B | A | 65.358 / 4.400 | 80.852 / 0.110 |
| A+B | B | 63.063 / 9.513 | 83.152 / 0.226 |
| A+B | C draft | 55.078 / 1.198 | 69.129 / 1.008 |

A+B changes M0 by +444/−116, with 13,391 unknown and 12 conflict IDs. Inspected overlays/Q retain the fuller apple and reduced table contamination, but miss C's upper red cap; A-only M2 remains worse on C's target contribution. These are observed regressions, not held-out scores.

#### Plate A succeeds; B fails before support publication

Actual A/B native alignment was inspected before the respective analysis. Original cookie holes, A's thin exclusion slit and B's right/bottom viewport clipping remain unchanged; reviews are development-only. A's seven numerical samples, hidden-far check and exact same-snapshot tiling comparison pass. Its full **19,220 pixels / 6,132,733 records / 68,497 touched IDs** now produce **2,739,880 column bytes**. All 68,497 raw rows and paged positions export and restore matching identities. No significant-contribution filter or row cap is used.

A-only M0 selects 1,126 IDs; M2 selects 986 (+383/−523 relative to M0). Complete raw support retains 66,016 unknown and 16 conflict IDs. With target denominator 5,638 and local-negative denominator 8,401:

| Plate A-only, evaluated at A | M0 | M2 |
|---|---:|---:|
| Target numerator / ratio | 3018.332818 / 53.5355% | 3250.572579 / 57.6547% |
| Local-negative numerator / ratio | 154.614685 / 1.84043% | 2.057224 / 0.0244878% |

Inspected A overlays/Q show support concentrated on the plate around the preserved holes and less local spill; the outer rim still has incomplete support. This limited A-only improvement does not establish A+B transfer or plate-wide usefulness.

B's unchanged five-point full-live oracle fails at **pixel (971,620), ID/source row 25346, draw slot 167601**: CPU alpha `0.37306782945514244`, GPU alpha `0.3745875954627991`, error **0.001519766007656631 > 1/1024 (0.0009765625)**. All five identity/order comparisons match and replay errors are zero; small weight error does not waive the alpha bound. One recheck on the **same retained snapshot, without recapture**, reproduces the failure.

An external, alpha-only replay of this saved packed record through both previous `eab90a3` and current CPU kernels gives exactly the same failing CPU alpha. This local diagnosis is not subset GPU qualification; it locates the discrepancy before support materialization, without establishing the underlying raster/interpolation cause or changing the contribution calculation.

B analysis is correctly rejected; no B support or A+B fusion is published. C capture is correctly rejected because B support is absent. A remains unchanged after these calls and an explicit zero-byte-budget rejection. **Still missing:** qualified plate B support, B/C real tiling/evaluation and warm/per-band costs, A+B M0/M2 Q/overlays, C inspection and a cross-object M2 conclusion. Missing results are not zeros. Proceeding requires addressing the numerical discrepancy without silently relaxing the frozen contract; this support-only continuation does not rewrite that kernel.

#### Costs, guards and evidence

“First” below means the first of four recorded same-snapshot no-Q analyses after verification, not cold startup or M2-only/product latency.

| Same-snapshot no-Q analysis | Apple A | Apple B | Plate A |
|---|---:|---:|---:|
| First kernel ms | 276.8 | 258.2 | 635.3 |
| Three subsequent kernel ms | 317.7 / 328.7 / 241.5 | 248.2 / 251.5 / 268.0 | 595.0 / 583.5 / 587.7 |
| Support copy ms, first / three subsequent | 46.8 / 44.4 / 48.4 / 52.3 | 61.8 / 38.3 / 48.9 / 62.3 | 41.9 / 44.0 / 45.5 / 58.7 |
| Merge ms, first / three subsequent | 0 / 0 / 0 / 0 | 8.1 / 6.3 / 3.3 / 4.8 | 0 / 0 / 0 / 0 |
| First end-to-end analysis ms | 328.2 | 334.3 | 684.2 |
| Maximum support replacement + reserve logical bytes | 5,413,104 | 6,820,776 | 9,689,904 |
| New no-Q evaluator typed-array bytes | 91,036,704 | 91,415,514 | 91,959,096 |
| Snapshot readback bytes / wall ms | 65,932,620 / 186.8 | 65,932,620 / 66.3 | 65,932,620 / 170.1 |

Support retention after apple A+B is 1,617,936 bytes including winner payloads; plate A is 2,747,800. Plate A positions use at most 65,536 scratch typed bytes and an estimated 1,538,756-byte serialized page, within the 4 MiB export reserve; no claim of measured JS serialization/GC peak is made. Each snapshot retains 76,918,428 CPU bytes, with reported readback CPU peak 132,063,388 and staging 66,131,460 bytes. Per-band records/times, all Q numerator/denominator values and support budgets remain in the reports. Plate B/C costs are unavailable, not extrapolated.

Independent plate A/B GPU oracle costs are additional: 65,348,304 / 21,093,040 readback bytes and 220.5 / 109.6 ms on the initial trace; B's separate recheck is 136.7 ms. Oracle and dual-output parity costs are verification, not product latency. Existing snapshot/evaluator ceilings remain separate from support; actual process/JS heap/GC and GPU residency/elapsed time remain **unmeasured**.

Apple identity/compaction/transform/SelectOp Undo checks, 17 existing guards, 12 target/capacity guards and four support export/merge guards pass. They cover immutable exports, atomic low-budget failure, queued/in-flight invalidation, C non-fusion and unchanged native flags/UI counts. At clean `9d5e465`, diagnostic-disabled full 2,746,452-row loading, absent diagnostic chunk, zero flags, no browser errors and Sphere Brush pass. No production selection path is enabled.

New evidence is kept separately in the [controlled draft release](https://github.com/Wormh0-le/supersimplat/releases/tag/untagged-994565a4a7b1c051913c), tag `native-m2-support-evidence-9d5e465`, not latest; the historical draft release above is untouched. Retrieve with `gh release download native-m2-support-evidence-9d5e465 --repo Wormh0-le/supersimplat` and verify its accompanying archive checksum. It contains original input bundle, raw/support/position exports, actual overlays/Q, the preserved B failure/recheck, old-kernel alpha diagnostic, software/review logs and internal checksums; no full PLY is duplicated.
