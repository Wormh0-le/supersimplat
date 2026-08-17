# Ticket 21 failure and calibration hardening record

Date: 2026-08-17

## Production identity

The current Runtime Profile publishes one digest-bound production identity only
when the renderer, Direct Evidence backend and SAM 3 Image adapter are all
Ready. The record binds authoritative RGB/raster/runtime identity, the active
operator Model Manifest and checkpoint, Prompt compiler and synthesis policy,
TargetGeometryHint and local-View policies, Mask Review, P/N/V aggregation and
Lift Readiness. On the locked validation host the complete record validated as
Ready with identity digest
`sha256:9daeeac4f57ba0ee7362629abec5bb5ebae2cf310fd4820ec923f6bf6d831ffc`.
The digest is intentionally operator-manifest-specific and is not a portable
constant.

The production Candidate route now consumes only exact current
`production-direct` per-View Evidence and publishes a `production-ready`
Candidate. Before constructing it, the Companion evaluates and returns the
exact `lift-readiness/production-v1` artifact from the same aggregation; Not
Ready returns no Candidate, while the browser publishes the readiness result
and keeps the previous Candidate stale. The retained complete-Contributor Candidate path stays explicitly
reference-only for Ticket 22 migration work.

## Calibrated policy identities

| Policy              | Identity                                                                  |
| ------------------- | ------------------------------------------------------------------------- |
| TargetGeometryHint  | `sha256:7272aa7cda6d8da9a0916488d91f46e70bdabdb42417351e78bfd485fe10174f` |
| Bounded local Views | `sha256:c1e4a20cb20ac08dba8c9fed2d94e0dd7ad0b50d45b4dff2d11aed874df2749e` |
| Mask Review         | `sha256:411ab66e44fb491fe966c77e46aa0ff161b24c759118508796e328f6f1a96ccb` |
| Lift Readiness      | `sha256:5c8fe60c75ff889b6fd71c09901970c0229d681e1eb193d54b63a9d4bff7b904` |

The Lift Readiness identity is now `lift-readiness/production-v1`. Its formal
matrix preserves the Ticket 13 separation: weak/low Visible Mass is a readiness
reason, while Prompt inconsistency, material clipping, severe fragmentation,
gross Box spill and empty/degenerate Masks remain Mask Review reasons. No
Ticket 10 output is required by the evaluator or production Candidate path.

## Local-View envelope

The deterministic `local-key-view-planner/v3` policy schedules four initial automatic Views inside the
accepted `4–8` range and retains at most 64 distinct TargetGeometryHint points.
A 10,000-iteration pure-CPU planner run on the locked host measured 0.468 ms
mean latency, 139,782 bytes peak traced Python allocation and constant four-slot
output. A calibrated asymmetric-support fixture produces three usable/limited
slots plus one explicit Failed slot; the browser keeps the Failed slot
inspectable and Excluded and never sends it to rendering. An all-failed batch
still fails the initial planning attempt and exposes only the accepted
failure-only fresh-attempt recovery.

## Failure and atomicity gates

- Render, geometry, plan, Prompt, Mask, Direct Evidence and Lift retain distinct
  attempt identities; same-attempt replay returns the same complete result or
  the same failure, while a normal new intent uses a new attempt.
- Direct Evidence and Candidate Re-Lift admissions record only a complete JSON
  publication or one terminal failure. Injected OOM leaves the publication
  field empty and replays the same `modelOutOfMemory`, `evidenceOutOfMemory` or
  terminal Lift failure.
- The locked SAM 3 Image fixture ran Point, Box, previous-logits refinement and
  an injected real-runtime CUDA OOM boundary: 4 tests passed on an RTX 4090 D.
- The locked Direct Evidence fixture ran RGB/P/N/V parity, mapping, Working Set
  expansion, occluder and atomic accumulation checks: 7 tests passed.
- Browser stale-result tests cover cancellation races, target restart,
  suspension, Stable-input replacement and User Confirmed authority. Failed
  Evidence/Lift retains Views, Stable Masks and the prior inspectable Candidate.

## Release surface

The repository interaction matrix verifies the exact five-tool floating
palette, stale-hit-region removal, Render/Prompt/Mask Review/Participation/
Evidence Gallery separation, semantic-unavailable versus technical failure,
and absence of identical-input Render/Prompt/Mask/Evidence recovery actions.
The initial-planning failure icon remains the only product Retry. Native
SuperSplat state stays usable while readiness is Connecting or Unavailable.

## Commands

```sh
rtk npm test
rtk npm run lint
rtk npm run lint:locales
rtk npm run build
rtk env SUPERSPLAT_SAM3_IMAGE_GPU_CHECKPOINT=<operator-checkpoint> uv run --project selection-service-companion --locked --extra sam3 python -m unittest discover -s selection-service-companion/tests -p test_sam3_image_instance_gpu.py
rtk uv run --project selection-service-companion --locked --extra renderer python -m unittest discover -s selection-service-companion/tests -p test_direct_gaussian_evidence.py
```
