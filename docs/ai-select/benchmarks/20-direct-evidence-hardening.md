# Ticket 20 Direct Evidence validation

Date: 2026-08-17

## Locked environment and identity

- GPU: NVIDIA GeForce RTX 4090 D, compute capability 8.9
- Runtime: Python 3.12, PyTorch 2.11.0+cu128, CUDA 12.8, gsplat 1.5.3
- Source revision:
  `sha256:d5568856951be511573c6c766d225f8b95c3ac5850eb965805c2aa632c01976a`
- ABI: `supersimplat-direct-evidence-abi/v1`
- Raster implementation: `supersimplat-gsplat-direct-evidence/v1`
- Evidence backend: `global-atomic/direct-v1`
- Runtime build:
  `sha256:42765fdd26ef420b822357e70fa39b95eaf11e31e6b0426215cd6c4a6f1fc3a4`
- Build flags: `-O3`, `--use_fast_math`, `--generate-line-info`,
  `--ptxas-options=-v`

The checked-in CUDA extension consumes gsplat's pinned projection and
intersection order once. Its front-to-back loop makes the alpha validity and
termination decisions used by both RGB and `alpha * incoming T` Evidence.
Normal RGB and Direct Evidence do not invoke or allocate the complete
Contributor path.

## Reproduction

```sh
rtk uv run --project selection-service-companion --extra renderer python selection-service-companion/scripts/benchmark_ticket20_direct_evidence.py
rtk uv run --project selection-service-companion --extra renderer python -m unittest selection-service-companion/tests/test_direct_gaussian_evidence.py selection-service-companion/tests/test_gsplat_contributor_renderer.py selection-service-companion/tests/test_spatial_scene_gpu_parity.py
```

The benchmark uses the tracked 16,384-Gaussian controlled-overlap fixture at
1008 x 1008. Seven warm runs are used for RGB-only and Direct Evidence timing.
The Stable Mask selects the known contributor/raster-alpha mismatch pixel.

## Measured latency and memory

| Path                           |     Median |              p95 |           Peak VRAM |
| ------------------------------ | ---------: | ---------------: | ------------------: |
| Direct-capable RGB only        | 196.491 ms |       222.423 ms | renderer state only |
| Production Direct Evidence     | 196.690 ms |       203.138 ms |       154,882,560 B |
| Complete Contributor reference | 488.902 ms | one measured run |     1,316,375,040 B |

Direct Evidence's compact output is 262,144 bytes: exactly
`16,384 Gaussians * 4 channels * sizeof(float)`. The four full-frame Mask
weight channels use 16,257,024 bytes and the bounded boundary queue uses
524,296 bytes. With a 256-Gaussian Evidence Working Set, the compact output is
4,096 bytes while the unchanged full render traversal takes 189.390 ms and
reports 47 target-boundary contacts. This demonstrates O(|Evidence Working
Set| x channels) output storage without incorrectly rasterizing only that
working set.

RGB digest is identical between RGB-only, full-Evidence and the 256-Gaussian
Evidence Working Set runs. Complete Contributor memory is reported separately;
Mask storage is the 127,008-byte bitset and Gallery thumbnail/texture bounds
remain owned and exercised by the existing Ticket 09 lifecycle tests.

## Numeric policy and reference result

The production gate requires byte-identical authoritative PNG RGB for the same
inputs. P/N/V/boundary uses float32 atomics and is compared with the complete
Contributor reference accumulated in float64. The declared per-channel mass
gate is maximum absolute error <= `2e-5` on the controlled fixture and <=
`1e-4` on full-versus-spatial SH0-SH3 parity fixtures; support and final class
must be identical. Relative error uses `max(abs(reference), 1e-8)` as the
denominator and is diagnostic after the absolute gate protects low mass.

| Metric over 4 x 16,384 channel values      |      Result |
| ------------------------------------------ | ----------: |
| Maximum absolute error                     | 4.563481e-7 |
| p95 absolute error                         |           0 |
| p99 absolute error                         |           0 |
| Maximum relative error                     | 6.232698e-7 |
| p95 relative error                         |           0 |
| p99 relative error                         |           0 |
| Support differences                        |           0 |
| Repeat-run maximum absolute mass variation | 7.152557e-7 |
| Final class differences                    |           0 |

The reference aggregation/classification fixtures cover strong positive,
background, mixed large-footprint, unobserved and threshold-near cases. Direct
and reference classification agree; the repeat variation remains below the
`2e-5` margin. TargetGeometryHint-seeded working sets expand from later
Included Stable Views, and a boundary contact either produces explicit
expansion input or fails closed before artifact publication.

## Contention and compiler measurements

The simple global-atomic baseline executed 3,347 non-zero channel writes in
the selected ROI. Maximum observed fan-in was 49 writes to one Gaussian and
p95 fan-in among touched Gaussians was 49. The conservative payload-only
atomic bandwidth was 68,066.6 bytes/s; it intentionally excludes atomic
protocol and cache traffic, so it is a lower-bound payload measure rather than
a hardware-throughput claim.

`ptxas` reports 36 registers, 0 spill loads, 0 spill stores, 0 bytes stack and
0 barriers for `direct_evidence_kernel`. NVIDIA performance counters are not
available to this container (`ERR_NVGPUCTRPERM`), so contention is recorded
from the complete support stream rather than claimed as a hardware counter.
The measured baseline meets the current semantic and memory gates; no tile,
block, sparse or special-case optimization is introduced in Ticket 20.

## Failure and lifecycle result

- duplicate, missing, colliding and out-of-range Stable-ID mappings fail before
  launch;
- out-of-Evidence-set target contact returns a bounded diagnostic and no
  artifact, while non-target occluders stay in traversal with no writes;
- RGB digest mismatch, kernel failure, overflow and incompatible
  raster/backend/runtime identity publish no partial artifact and preserve the
  prior RGB, Stable Mask and Candidate;
- per-view cache reuse validates the complete artifact identity, so reference
  and production artifacts cannot collide; the formal per-View cache retains
  production Direct Evidence while the reference Candidate path owns a
  separate private reference cache;
- ordinary target restart, changed-Anchor cutover, View disposal and Stable
  Mask replacement continue through the target-local Evidence registry and
  existing exact shared-cache ownership rules;
- explicit reference capability can fail independently from authoritative RGB
  and Direct Evidence.

Ticket 21 still owns release calibration and production Candidate readiness.
Ticket 20 deliberately leaves the existing reference Candidate Re-Lift path
separate rather than relabeling it as production-ready.
