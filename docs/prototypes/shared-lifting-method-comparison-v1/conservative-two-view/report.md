# Shared 2D-to-Gaussian lifting comparison

This is a Wayfinder prototype result. Every method consumed the same frozen Scene Snapshot, Frame Set, and Mask Set. Prediction artifacts were written before the scoring phase opened Ground Truth.

## Fixed comparison policy

- Top contributors per pixel: 8
- Prompt-derived support margin: 24 px
- Evidence decisions: at least 2 accepted views and 0.1 accumulated alpha×transmittance support; selected at ≥0.8, rejected at ≤0.2, otherwise uncertain.
- The thresholds are comparison-only. Product semantics remain owned by the later Selection Evidence decision.

## Results

| Scenario           | Method                  |   IoU | Precision | Recall | Truth-selected → uncertain | Truth-rejected → selected |
| ------------------ | ----------------------- | ----: | --------: | -----: | -------------------------: | ------------------------: |
| controlled_overlap | current_top1_visibility | 0.405 |     1.000 |  0.405 |                       4878 |                         0 |
| controlled_overlap | hard_top1_vote          | 0.211 |     1.000 |  0.211 |                       6461 |                         0 |
| controlled_overlap | contributor_three_state | 0.374 |     1.000 |  0.374 |                       5131 |                         0 |
| controlled_overlap | soft_mask_fit           | 0.374 |     1.000 |  0.374 |                       5131 |                         0 |
| gift_box           | current_top1_visibility | 0.254 |     0.966 |  0.256 |                       1243 |                        15 |
| gift_box           | hard_top1_vote          | 0.425 |     1.000 |  0.425 |                        890 |                         0 |
| gift_box           | contributor_three_state | 0.897 |     1.000 |  0.897 |                        120 |                         0 |
| gift_box           | soft_mask_fit           | 0.945 |     0.996 |  0.949 |                         32 |                         6 |
| microwave          | current_top1_visibility | 0.230 |     0.974 |  0.231 |                       2117 |                        17 |
| microwave          | hard_top1_vote          | 0.385 |     1.000 |  0.385 |                       1565 |                         0 |
| microwave          | contributor_three_state | 0.849 |     1.000 |  0.849 |                        257 |                         1 |
| microwave          | soft_mask_fit           | 0.889 |     0.994 |  0.893 |                        126 |                        14 |
| clothes_rack       | current_top1_visibility | 0.226 |     1.000 |  0.226 |                       2263 |                         0 |
| clothes_rack       | hard_top1_vote          | 0.242 |     1.000 |  0.242 |                       1941 |                         0 |
| clothes_rack       | contributor_three_state | 0.634 |     1.000 |  0.634 |                        668 |                         0 |
| clothes_rack       | soft_mask_fit           | 0.714 |     1.000 |  0.714 |                        417 |                         0 |

## Implementation and license boundary

- The top-1 and hard-vote baselines introduce no dependency but cannot represent alpha×transmittance evidence.
- Contributor evidence adds service-side accumulation over the already-installed gsplat contributor API; this prototype adds no model, checkpoint, or external source dependency.
- Soft fitting adds a numerical-solver/configuration/test burden, but is project-owned code over the same inputs. It does not use SA3D or FlashSplat code, weights, or licenses.

## Interpretation boundary

- `current_top1_visibility` is a same-renderer top-1-contributor proxy for the current ID-visibility baseline; it is not a claim that the browser ID pass is identical.
- `hard_top1_vote` uses unweighted top-1 footprint votes. `contributor_three_state` uses alpha×transmittance weight; both leave non-observation uncertain.
- `soft_mask_fit` is a project-owned SA3D-style linear fit with a contributor-evidence prior. It is not the official SA3D implementation and introduces no external dependency.
- Frozen office Coverage Reports are insufficient by design, so none of these outputs proves a Ready Object Selection or full-object coverage.

Full configuration, raw Stable Gaussian ID outputs, per-view diagnostics, timings, VRAM, and hashes are in `result.json` and `prediction-manifest.json` beside this report.
