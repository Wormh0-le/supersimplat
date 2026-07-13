# PoC Acceptance Criteria v1

Status: confirmed design decision for [Set evidence-based PoC acceptance criteria](https://github.com/Wormh0-le/supersimplat/issues/9).

The PoC passes only when its **required default path** satisfies every hard gate below. The required path is same-renderer contributor-weighted three-state evidence under one declared Evidence Policy and rendering configuration. `soft_mask_fit` remains a project-owned quality A/B: it may be measured on the same frozen inputs, but it cannot rescue or replace a failing default-path result.

## Trial integrity

Each PoC Trial replays a frozen, point-only Benchmark Prompt Log and binds the following identities in its PoC Run Record:

- Scene Snapshot, Frame Set, Mask Set, and Prompt Log versions or hashes;
- Model Manifest, `renderConfigVersion`, Evidence Policy revision, and fixed seed; and
- prediction artifact hash, Coverage Report, Evidence Snapshot summary, correction outcomes, timing, peak VRAM, and later scoring result.

Prediction is blind to Benchmark Ground Truth. The candidate artifact and its prediction-phase manifest must be persisted and hashed before an independent scoring phase opens Ground Truth; that score is then linked into the final PoC Run Record. A leakage breach or a missing required record invalidates the trial regardless of its score.

When the default path has a stochastic component, all three prescribed fixed-seed trials independently pass every hard gate. An average, best run, or two-of-three result does not pass.

## Hard gates

| Axis                               | Required outcome                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Default-path correctness           | After the initial `New` result and at most five successful Correction Rounds, the default contributor-weighted three-state path reaches Gaussian-index IoU `>= 0.80` on **each** frozen office target: `gift_box`, `microwave`, and `clothes_rack`. Score only frozen `scope_ids`, exclude ambiguous truth, and count an uncertain target ID as not selected.               |
| Controlled completeness and safety | On the exact front/back-overlap fixture, Gaussian-index IoU, Precision, Recall, and rear-surface Recall are each `>= 0.90`. In addition, no more than 81 of the 8,192 known distractor Stable Gaussian IDs may be in the final selected set (`<= 1%` rear-layer false-selection rate).                                                                                      |
| Manual effort                      | Before prediction, every target has a frozen point-only `New`/`Add`/`Remove`/`Refine` Benchmark Prompt Log that records point count and order. A trial may not add interactions outside that log. An operator, without seeing Ground Truth scores, must judge the result Ready within the five-round correction budget. Failed or cancelled updates do not consume a round. |
| Honest limited coverage            | No numeric cap is imposed on Uncertain IDs when the Coverage Report is insufficient. Instead, unsupported regions remain Uncertain; the preview shows selected/uncertain counts and a limited-coverage explanation; and confirmation requires acknowledgement that only selected IDs will commit.                                                                           |
| Editor compatibility               | Preview updates create no editor history entries. Confirm creates exactly one selected-ID history operation. Cancel restores the entry selection without a history entry. The resulting committed selection succeeds through the existing delete, duplicate, separate, undo, and redo paths.                                                                                |
| Observability                      | Each trial has a complete PoC Run Record, including coverage and uncertainty state, correction/terminal status, error or cancellation reason, per-stage timing, peak VRAM, version bindings, artifact hashes, and the independent score/pass result.                                                                                                                        |

## Evaluation order

1. Freeze the input identities and point-only Benchmark Prompt Log before running the candidate.
2. Run the default path with the declared configuration and seed; preserve any unobserved evidence as Uncertain.
3. Persist and hash the output and prediction-phase manifest before opening Ground Truth.
4. Have the operator make the blind Ready judgment within the correction budget.
5. Independently score the frozen truth and apply all hard gates to every required trial.
6. Exercise Confirm/Cancel and the editor compatibility matrix.
7. Optionally run `soft_mask_fit` on the identical frozen input as a separately labelled quality A/B result.

## Explicit non-gates

- Current conservative one- or two-view lifting comparison values are diagnostics, not final Ready results.
- Timing and VRAM must be recorded but have no numerical pass/fail threshold in this PoC.
- An insufficient Coverage Report is not itself a failure and must not be converted into negative evidence or hidden by a low-uncertainty target.
- Optional `soft_mask_fit` quality results are not part of default-path pass/fail.

## Related local evidence

- [`selection-evidence-policy.md`](selection-evidence-policy.md) defines the required three-state evidence behavior.
- [`shared-lifting-method-comparison-v1`](shared-lifting-method-comparison-v1/README.md) records the shared-mask lifting baseline and its limits.
- [`benchmark fixtures`](../benchmarks/fixtures/) contain the frozen scenes, Frame Sets, Mask Sets, Coverage Reports, and Ground Truth used by this decision.
- [`CONTEXT.md`](../../CONTEXT.md) defines the terms used here.
