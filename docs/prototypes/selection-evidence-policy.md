# Selection Evidence Policy v1

Status: confirmed design decision for [Define Selection Evidence and uncertainty semantics](https://github.com/Wormh0-le/supersimplat/issues/8).

This record defines how the Selection Service turns a completed, promptable-mask update into the transient `Candidate Object Selection`. It is a policy for the PoC, not a claim that the thresholds are production-calibrated.

## Bound inputs and output

Every successful preview creates one complete, immutable **Evidence Snapshot**. It is bound to:

- the immutable Scene Snapshot and its `sceneVersion`;
- the ordered Frame Set and the frozen, complete Mask Set used for the preview;
- the ordered Prompt Log that produced the composite masks;
- the Model Manifest;
- the same-renderer `renderConfigVersion`, including contributor semantics; and
- the Evidence Policy identifier and revision (`selection-evidence-policy/v1`).

For every Stable Gaussian ID, the snapshot serializes at least:

```text
positiveEvidence (P)
negativeEvidence (N)
effectiveObservation = P + N
posterior = (1 + P) / (2 + P + N)
uncertaintyReason
classification = selected | rejected | uncertain
```

`posterior` is the mean of a `Beta(1, 1)` prior updated by fractional positive and negative evidence. Benchmark Ground Truth is not an input to this process and must not be read while producing a prediction.

## What counts as evidence

For a quality-accepted rendered view, only Stable Gaussian IDs in that renderer's contributor support can receive an observation. The same-renderer alpha-times-transmittance contribution mass is split by the final per-view composite mask:

- contribution inside the composite mask adds to `P`;
- contribution within the bounded contributor support but outside that mask adds to `N`.

The following are neutral, not negative evidence: a Gaussian absent from contributor support, a pixel outside that support, a `not_found` view, a quality-rejected view, and a technical failure. A view can therefore be useful without forcing all non-contributors to background.

`P` and `N` are accumulated across accepted views. Opposing observations are preserved rather than overwritten: either side may still determine the classification only when it clearly dominates under the policy below. Accepted-view counts and the per-view evidence breakdown are diagnostic fields, not hard classification gates.

## Classification rule

Apply this policy only after the full Evidence Snapshot has been computed:

| Condition                                              | Classification |
| ------------------------------------------------------ | -------------- |
| `effectiveObservation >= 0.10` and `posterior >= 0.80` | `selected`     |
| `effectiveObservation >= 0.10` and `posterior <= 0.20` | `rejected`     |
| Otherwise                                              | `uncertain`    |

There is no universal minimum number of accepted views. One sufficiently strong, consistent quality-accepted observation may resolve a Gaussian. Conversely, many weak or conflicting observations can remain uncertain.

`uncertaintyReason` explains the last case without inventing negative evidence:

- `unobserved` when `P + N = 0`;
- `insufficient_observation` when `0 < P + N < 0.10`; or
- `undecided_or_conflicting` when the effective observation is sufficient but the posterior is strictly between the two decision thresholds.

The numeric thresholds and the meaning/scale of contributor mass are inseparable from `renderConfigVersion` and the policy revision. Changing renderer configuration or contributor semantics requires a new policy revision and benchmark calibration; it must not silently retune an existing session.

## Prompt operations and recomputation

`New`, `Add`, `Remove`, and `Refine` are commands in the chronological Prompt Log, not incremental edits to old evidence scores.

- `New` starts a new Object Selection Session. Its successful complete snapshot replaces the prior candidate.
- `Add` contributes an include Mask Track at its chronological position. A later Add can deliberately restore a region that an earlier Remove excluded.
- `Remove` contributes an exclude Mask Track at its chronological position. A later Remove can exclude a region again.
- `Refine` changes the primary include track; any separate Add and Remove tracks remain present and are replayed.

For every successful preview update, the service replays the complete Prompt Log, derives the full current composite masks from the frozen Mask Set, recomputes evidence for every relevant Gaussian, and atomically replaces the entire Candidate Object Selection with the new Evidence Snapshot. Command chronology controls mask composition; it does **not** make raw positive/negative evidence last-write-wins.

If mask propagation, rendering, attribution, or lifting fails or is cancelled, the prior Candidate Object Selection remains unchanged. No partial evidence and no editor history entry are published.

## Preview and commit boundary

Before Selection Commit, `selected`, `rejected`, and `uncertain` are reversible preview states. A later successful Correction Round may move any Gaussian between all three states.

Selection Commit hands only the then-`selected` Stable Gaussian IDs to SuperSplat as one editor history operation. Rejected and uncertain IDs are excluded. Existing editor-owned delete, duplicate, separate, undo, and redo semantics begin only after that handoff.

## Deliberately deferred

This decision does not set PoC pass/fail metrics, Selection Service packaging, or the exact transport schema. Those remain for the acceptance-criteria, service-lifecycle, and technical-specification decisions. The shared-mask lifting comparison remains the supporting method decision: contributor-weighted three-state evidence is the required baseline, while soft-mask fitting is only a project-owned quality A/B.

## Related local evidence

- [`CONTEXT.md`](../../CONTEXT.md) defines the shared terms used here.
- [`shared-lifting-method-comparison-v1`](shared-lifting-method-comparison-v1/README.md) records why contributor-weighted three-state lifting is the required main line.
- [`benchmark fixtures`](../benchmarks/fixtures/) provide versioned Frame Sets, Mask Sets, contributor data, and frozen Ground Truth used for later calibration and acceptance work.
