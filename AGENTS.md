# SuperSplat 3.x native AI Select spike

This branch is based on upstream SuperSplat v3.1.2 (`0911f786db652a7700068fe6ccdfe32e24269e1d`), not an in-place upgrade of ai-select-v1. The branch name retains the original 3.0 discussion name.

Current product decisions: [Issue #37, accepted native-first direction](https://github.com/Wormh0-le/supersimplat/issues/37#issuecomment-5643008607). Read [the bounded spike](experiments/native-ai-select/README.md) before editing. Existing AI Select algorithm goals and Q10/Q11 interaction contracts remain requirements, not implemented features on this fresh upstream branch.

Keep upstream rendering, data model, transforms, Undo and other 3.x improvements. Do not bulk-merge the old Companion/rendering stack. Do not rename Sphere Brush and claim AI Select is implemented. It remains available for baseline comparison until a real AI path can replace the toolbar entry safely.

Prefer native RGB, camera/depth/ID and selection integration. Exact P/N/V is not equivalent to one-ID picking. Preserve Stable ID/source row mapping through compaction and transforms; do not silently weaken old input identity or occlusion guarantees.

SAM inference is separate from Gaussian rendering. Imported masks can establish an initial native evidence test without adding a model service. Browser-only model inference and elimination of every backend are unproven, not promises.

No production cutover, automatic merge, large asset commit, or new speculative stage graph. Keep benchmark assets outside the repo. Reference benchmark branch: `bench/lerf-teatime-benchmark`; current code reference: `ai-select-v1@e01246163b7226bca440239e8623fc507fdee7f3`.

Validation: use this branch's package.json scripts. Upstream has build/lint/locales, not the old branch's npm test or Companion tests. Build success is not GPU rendering/selection qualification. Record exact tested SHA and missing evidence.
