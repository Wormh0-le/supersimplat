# Standalone Object Selection PoC Benchmark

## Purpose

This benchmark is the smallest comparison intended to falsify unsuitable Standalone Gaussian object-selection methods. It tests both realistic operation and the specific failure mode where a plausible front view hides an incomplete or contaminated Gaussian Selection.

It is a planning artifact, not an implementation plan. Candidate methods receive only a Standalone Gaussian Scene plus the recorded editor prompts; original images, camera poses, and reconstruction metadata are unavailable.

## Scene and target roster

### Real office scene

Use `filtered_lixel_office65.ply`, a roughly 250 MB binary little-endian PLY containing 3,680,541 Gaussians and DC color only. Bind the benchmark to the asset by a file hash; do not copy the PLY into the repository.

Before candidate outputs are viewed, choose and freeze three targets by role:

1. **Simple target** — a clear silhouette with spatial separation from nearby geometry.
2. **Contact target** — an object touching a desk, wall, floor, or another object, exposing boundary leakage.
3. **Difficult target** — an object with occlusion, thin structure, or colors similar to its surroundings, exposing incomplete selection.

Record the concrete object name and why it satisfies its role in the benchmark manifest.

### Controlled front/back-overlap scene

Construct two simple, closed, programmatic Gaussian objects with disjoint, known index ranges. Align the front target and rear distractor so their initial-view projections overlap heavily, while side and rear views separate them. The target must itself contain front-, rear-, and side-facing Gaussians.

Construction membership is exact Ground Truth. This case isolates multi-view evidence and index assignment; semantic realism remains the responsibility of the office scene.

## Benchmark Ground Truth

For each real target, classify every relevant Gaussian as:

- `selected`: clearly belongs to the target;
- `rejected`: clearly does not belong to the target;
- `ambiguous`: reliable ownership cannot be established at a mixed or poorly observed boundary.

Inspect at least front, rear, left, right, top, and bottom views around the target. Add oblique views for occlusions and concavities. Perform an initial selection pass and an opposite-view contamination and omission pass.

Freeze Ground Truth before viewing any candidate method's result. Later corrections require a new Ground Truth revision and must not silently replace results from the earlier revision.

## Reproducible interaction

Each target has a versioned, replayable prompt script:

1. `New` from a fixed initial camera with one positive prompt on the target body.
2. `Add` on a clearly omitted independent region or part when the scenario calls for it.
3. `Remove` on a known adjacent or rear contaminant when the scenario calls for it.
4. `Refine` with recorded positive or negative prompts at the remaining error boundary.

Save the camera, prompt coordinates, interaction mode, candidate selection, and uncertain set after every inference-and-preview refresh. No target may use more than five Correction Rounds after `New`.

The operator judges whether the result is a Ready Object Selection using only the selected/rejected/uncertain preview, without seeing Ground Truth scores. Scores are computed afterward.

## Metrics

Compute accuracy only over non-ambiguous Benchmark Ground Truth:

- Gaussian-index IoU (primary);
- Precision and Recall;
- rear-surface Recall for the controlled overlap target;
- target uncertainty rate and overall uncertainty rate;
- whether and at which Correction Round the operator first judged the result Ready.

For commit metrics, a candidate `Uncertain Gaussian` counts as not selected. Thus uncertainty on a truth-selected Gaussian lowers Recall; a method cannot improve its primary score by abstaining on everything. Ground Truth marked `ambiguous` is excluded from accuracy calculations.

Multi-view rendered pixel overlap may be recorded as a diagnostic, but it is not a primary metric because large Gaussians can hide index-level errors.

Record these operational measurements without a pass/fail threshold:

- one-time preprocessing time;
- `New` inference-and-preview time;
- each Correction Round inference-and-preview time;
- peak GPU VRAM;
- out-of-memory events, fallbacks, and failed runs;
- Ground Truth annotation labor, reported separately from algorithm time.

Run stochastic methods three times with fixed recorded seeds. Report the median and slowest run. A deterministic method needs only one run after determinism is confirmed.

## Eligibility gates

A candidate is ineligible for the PoC main line if any of these conditions holds:

- on the controlled overlap scene, IoU, Precision, Recall, or rear-surface Recall is below 0.90;
- after correction, IoU is below 0.80 on any of the three real targets;
- any real target fails to become a Ready Object Selection within five Correction Rounds after `New`.

Passing is necessary but does not select a winner. Eligible candidates are compared using accuracy, correction burden, failure patterns, timing, VRAM, implementation risk, and licensing in later Wayfinder decisions.

## Frozen benchmark manifest

The benchmark manifest must reference:

- input PLY hash and Gaussian count;
- concrete target names, roles, and selection rationale;
- selected, rejected, and ambiguous Ground Truth index sets;
- required inspection cameras and any added oblique cameras;
- initial prompt camera and complete correction script;
- Ground Truth version and freeze time;
- candidate configuration, random seeds, and result artifacts.

Large scene assets remain outside the repository. The manifest and hashes identify them without treating local data as source-controlled project content.
