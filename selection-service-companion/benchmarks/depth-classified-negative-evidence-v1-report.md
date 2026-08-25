# V2AX depth-classified Negative Evidence report

**Recommendation: `retain-experimental`.**
**Trial validity: `invalid-incomplete-for-promotion`.**

This report does not promote a classified channel. The production baseline result remains independent of every variant.

## Trial seals and runtime

- `controlled-overlap-seed-1`: prediction manifest `sha256:66224db481bfef74f89d634ebb92641232a7412546c370714358debfed23a8d7`, Ground Truth `sha256:740e2a6a3080a6828aa14ff5fc7e0c9741af50e89b53b2480c26ba1021027dc0`, input identity `sha256:9c1556a9f5c40d287d2ae84fb89b6363e580b9b0e0382f66ef6016b7829ccf38`.
- GPU: `NVIDIA GeForce RTX 4090 D` (compute capability `8.9`).
- Runtime: torch `2.11.0+cu128`, CUDA `12.8`, gsplat source `77ab983ffe43420b2131669cb35776b883ca4c3c`.

## Trial results

| Scene digest                                                            | Seed                      | Method                                                        | Precision |   Recall | Distractor leaks | Thin/edge retention | Latency ms | Peak VRAM bytes | Buffer writes | Gate |
| ----------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------- | --------: | -------: | ---------------: | ------------------: | ---------: | --------------: | ------------: | ---- |
| sha256:cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8f2177964ad36aa6e | controlled-overlap-seed-1 | production-single-negative-mass/baseline-v1                   |  0.981287 | 0.995192 |              150 |         unavailable |    727.244 |        43320832 |         49152 | fail |
| sha256:cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8f2177964ad36aa6e | controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 |  0.972150 | 0.998102 |              226 |         unavailable |   3481.700 |      4527751168 |        245760 | fail |
| sha256:cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8f2177964ad36aa6e | controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  |  0.980975 | 0.998102 |              153 |         unavailable |   3472.638 |      4527751168 |        245760 | fail |
| sha256:cb238cb771f8a662e79a7dfe3de79c623810457fc0486aa8f2177964ad36aa6e | controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        |  0.981341 | 0.998102 |              150 |         unavailable |   3478.191 |      4527751168 |        245760 | fail |

## Isolation verdict

- The unchanged single-`negativeMass` baseline was persisted and sealed first.
- Every classified sidecar and Candidate replay used the same input identity digest as the baseline.
- Ground Truth was opened only by the independent scorer after prediction hash verification.
- Variant quality cannot rescue or alter baseline pass/fail.
- Production Evidence, readiness, Runtime Profile, Candidate binding, and orchestration remain unchanged.

## Recommendation rationale

- the available immutable fixture has no thin/edge Ground Truth class.
- no immutable real-scene trial is present in this repository.

A later promotion requires a new reviewed Issue. Until then, keep this experiment sealed and nonblocking.
