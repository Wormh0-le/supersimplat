# V2AX depth-classified Negative Evidence report

**Recommendation: `retain-experimental`.**
**Trial validity: `invalid-incomplete-for-promotion`.**

This report does not promote a classified channel. The production baseline result remains independent of every variant.

## Trial seals and runtime

- `controlled-overlap-seed-1`: prediction manifest `sha256:f7e7a52c78d6c1246097df9362fdb2644183c6a39914ff10ae546ac03fdd60a3`, Ground Truth `sha256:740e2a6a3080a6828aa14ff5fc7e0c9741af50e89b53b2480c26ba1021027dc0`, input identity `sha256:791cddbf44eb8b1bf01d7aefb1d8d15f21949e069076690b70f62e68eecdd539`.
- GPU: `NVIDIA GeForce RTX 4090 D` (compute capability `8.9`).
- Runtime: torch `2.11.0+cu128`, CUDA `12.8`, gsplat source `77ab983ffe43420b2131669cb35776b883ca4c3c`.

## Trial results

| Scene digest                                                            | Seed                      | Method                                                        | Precision |   Recall | Distractor leaks | Thin/edge retention | Derived total latency ms | Max component peak VRAM bytes | Logical output elements | Gate |
| ----------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------- | --------: | -------: | ---------------: | ------------------: | -----------------------: | ----------------------------: | ----------------------: | ---- |
| sha256:0f31c4f659bf02f5927f132b38703005f1ffd82a019ee58cff277696b18e51bf | controlled-overlap-seed-1 | production-single-negative-mass/baseline-v1                   |  0.981287 | 0.995192 |              150 |         unavailable |                 1254.881 |                      21169664 |                 3407872 | fail |
| sha256:0f31c4f659bf02f5927f132b38703005f1ffd82a019ee58cff277696b18e51bf | controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 |  0.972150 | 0.998102 |              226 |         unavailable |                 5053.529 |                    4553768960 |               210796544 | fail |
| sha256:0f31c4f659bf02f5927f132b38703005f1ffd82a019ee58cff277696b18e51bf | controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  |  0.980975 | 0.998102 |              153 |         unavailable |                 5044.743 |                    4553768960 |               210796544 | fail |
| sha256:0f31c4f659bf02f5927f132b38703005f1ffd82a019ee58cff277696b18e51bf | controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        |  0.981341 | 0.998102 |              150 |         unavailable |                 5040.269 |                    4553768960 |               210796544 | fail |

## Audited cost components

GPU-stage latencies are sums of per-View medians and GPU allocations are maxima across the identically reset per-View calls; Candidate replay latencies are whole-stage medians. Method totals are derived sums of component values and maximum component peaks, not paired end-to-end samples. The production total is moments-off Direct Evidence plus baseline Candidate aggregation; each shadow total adds CWED/readout acquisition, reference Contributor/classification, and its own replay.

| Seed                      | Method                                                        | Stage                                        | Kind           | Composition                                         | Latency ms | Start / peak / end VRAM bytes     | Logical output elements | Retained outputs                                                    |
| ------------------------- | ------------------------------------------------------------- | -------------------------------------------- | -------------- | --------------------------------------------------- | ---------: | --------------------------------- | ----------------------: | ------------------------------------------------------------------- |
| controlled-overlap-seed-1 | production-single-negative-mass/baseline-v1                   | productionBaseline                           | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |    833.851 | 8650752 / 21169664 / 13172736     |                 3391488 | productionGaussianEvidenceArtifacts, exactProjectedDepthRowsRecords |
| controlled-overlap-seed-1 | production-single-negative-mass/baseline-v1                   | baselineCandidateReplay                      | measured-stage | median-of-whole-stage-runs                          |    421.030 | None / None / None                |                   16384 | baselineCandidateReplay                                             |
| controlled-overlap-seed-1 | production-single-negative-mass/baseline-v1                   | productionBaselineTotal                      | derived-total  | sum-of-components/max-of-components                 |   1254.881 | None / 21169664 / None            |                 3407872 | none                                                                |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | productionBaseline                           | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |    833.851 | 8650752 / 21169664 / 13172736     |                 3391488 | productionGaussianEvidenceArtifacts, exactProjectedDepthRowsRecords |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | baselineCandidateReplay                      | measured-stage | median-of-whole-stage-runs                          |    421.030 | None / None / None                |                   16384 | baselineCandidateReplay                                             |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | sharedCwedReadoutAcquisition                 | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1034.577 | 37289984 / 60489728 / 51576832    |                10469376 | depthMomentReadouts, cwedMassEquivalentDirectResults                |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | referenceContributorAndClassificationSidecar | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1992.434 | 51642368 / 4553768960 / 367460352 |               196853760 | classifiedDiagnosticSidecars                                        |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | variantCandidateReplay                       | measured-stage | median-of-whole-stage-runs                          |    771.636 | None / None / None                |                   65536 | variantCandidateReplay                                              |
| controlled-overlap-seed-1 | front-near-preserve-behind-suppress/experimental-reference-v1 | shadowExperimentTotal                        | derived-total  | sum-of-components/max-of-components                 |   5053.529 | None / 4553768960 / None          |               210796544 | none                                                                |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | productionBaseline                           | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |    833.851 | 8650752 / 21169664 / 13172736     |                 3391488 | productionGaussianEvidenceArtifacts, exactProjectedDepthRowsRecords |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | baselineCandidateReplay                      | measured-stage | median-of-whole-stage-runs                          |    421.030 | None / None / None                |                   16384 | baselineCandidateReplay                                             |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | sharedCwedReadoutAcquisition                 | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1034.577 | 37289984 / 60489728 / 51576832    |                10469376 | depthMomentReadouts, cwedMassEquivalentDirectResults                |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | referenceContributorAndClassificationSidecar | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1992.434 | 51642368 / 4553768960 / 367460352 |               196853760 | classifiedDiagnosticSidecars                                        |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | variantCandidateReplay                       | measured-stage | median-of-whole-stage-runs                          |    762.851 | None / None / None                |                   65536 | variantCandidateReplay                                              |
| controlled-overlap-seed-1 | front-near-preserve-behind-quarter/experimental-reference-v1  | shadowExperimentTotal                        | derived-total  | sum-of-components/max-of-components                 |   5044.743 | None / 4553768960 / None          |               210796544 | none                                                                |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | productionBaseline                           | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |    833.851 | 8650752 / 21169664 / 13172736     |                 3391488 | productionGaussianEvidenceArtifacts, exactProjectedDepthRowsRecords |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | baselineCandidateReplay                      | measured-stage | median-of-whole-stage-runs                          |    421.030 | None / None / None                |                   16384 | baselineCandidateReplay                                             |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | sharedCwedReadoutAcquisition                 | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1034.577 | 37289984 / 60489728 / 51576832    |                10469376 | depthMomentReadouts, cwedMassEquivalentDirectResults                |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | referenceContributorAndClassificationSidecar | measured-stage | sum-of-per-view-medians/max-of-per-view-allocations |   1992.434 | 51642368 / 4553768960 / 367460352 |               196853760 | classifiedDiagnosticSidecars                                        |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | variantCandidateReplay                       | measured-stage | median-of-whole-stage-runs                          |    758.376 | None / None / None                |                   65536 | variantCandidateReplay                                              |
| controlled-overlap-seed-1 | near-emphasis-symmetric-half/experimental-reference-v1        | shadowExperimentTotal                        | derived-total  | sum-of-components/max-of-components                 |   5040.269 | None / 4553768960 / None          |               210796544 | none                                                                |

## Isolation verdict

- The unchanged single-`negativeMass` baseline was persisted and sealed first.
- Prediction opened one allowlisted input manifest, a label-free Scene Snapshot, and a masks-only NPZ; no Ground Truth-bearing fixture manifest was reachable.
- Every classified sidecar and Candidate replay used the same input identity digest as the baseline.
- Baseline Direct Evidence ran with moments off; the CWED call proved exact RGB, Stable-ID row, and projected-depth parity plus production-tolerance P/N/V/boundary parity before sidecar use.
- Ground Truth was opened only by the independent scorer after prediction input/output graph hash and canonical-digest verification.
- Variant quality cannot rescue or alter baseline pass/fail.
- Production Evidence, readiness, Runtime Profile, Candidate binding, and orchestration remain unchanged.

## Recommendation rationale

- the available immutable fixture has no thin/edge Ground Truth class.
- no immutable real-scene trial is present in this repository.

A later promotion requires a new reviewed Issue. Until then, keep this experiment sealed and nonblocking.
