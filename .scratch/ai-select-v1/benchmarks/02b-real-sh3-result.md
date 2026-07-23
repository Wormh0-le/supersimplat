# Ticket 02B real-scene working-set and typed-Anchor validation

Run date: 2026-07-23

These are read-only locked-runtime harness runs. A browser-produced effective
SceneSnapshot remains production authority; both fixtures had no editor edits,
so their raw typed PLY planes equal the effective values for this validation.
They are not browser peak-memory measurements.

Environment:

```text
RendererRuntimeStatus(status='ready', cuda_version='12.8', message=None)
GPU: NVIDIA GeForce RTX 4090 D (24,564 MiB), driver 580.173.02
```

The harness now measures the first authoritative Anchor operation before its
legacy full/reference parity render. The Anchor metric includes gsplat RGB,
complete contributor generation, Stable-ID remapping, PNG encoding, and the
bounded typed contributor digest; it does not construct a Python
`ContributorSample` graph or giant JSON.

## User-reported restroom fixture (SH0)

Fixture:

```text
/home/ubuntu/wormh01e/gaussian/restroom/ply-result/point_cloud/iteration_100/point_cloud_3.ply
```

Command:

```sh
uv run --project selection-service-companion --locked --extra renderer --python 3.12 python \
  .scratch/ai-select-v1/benchmarks/02b-real-sh3.py \
  --ply /home/ubuntu/wormh01e/gaussian/restroom/ply-result/point_cloud/iteration_100/point_cloud_3.ply \
  --target-mode first-gaussian --chunk-bytes 1048576 --resolution 1024
```

| Metric                                               |                                               Result |
| ---------------------------------------------------- | ---------------------------------------------------: |
| effective Gaussian count                             |                                              331,150 |
| SH coefficients / Gaussian                           |                                              0 (SH0) |
| complete typed snapshot                              |                             21,193,600 B / 21 chunks |
| Anchor required chunks                               |                    6 / 5,464,960 B (25.786% of full) |
| manifest registration                                |                                             0.334 ms |
| required-chunk accept + atomic commit                |                    621.652 ms (in-process, not HTTP) |
| independent working-set mmap → tensor assembly       |                                             3.194 ms |
| first 1024² authoritative Anchor + typed publication |                                       **444.920 ms** |
| selective / full reference gsplat render             |                              405.300 ms / 420.702 ms |
| GPU peak: Anchor / full reference                    |                        150,640,640 B / 174,434,304 B |
| process peak RSS                                     | 2,919,329,792 B (includes loader and full reference) |

Exact parity: RGB bytes/digest, alpha, contributor global Stable IDs, and
contributor weights all equal the full-chunk reference. The fixed camera had
230,226 non-zero-alpha pixels.

## Representative large SH3 fixture

Fixture:

```text
/home/ubuntu/wormh01e/3dgrut/runs/q9000_sanity/MT20260702-190531-1M-0507_165452/export_last.ply
```

Command:

```sh
uv run --project selection-service-companion --locked --extra renderer --python 3.12 python \
  .scratch/ai-select-v1/benchmarks/02b-real-sh3.py \
  --ply /home/ubuntu/wormh01e/3dgrut/runs/q9000_sanity/MT20260702-190531-1M-0507_165452/export_last.ply \
  --target-mode first-gaussian --chunk-bytes 1048576 --resolution 512
```

| Metric                                              |                                               Result |
| --------------------------------------------------- | ---------------------------------------------------: |
| effective Gaussian count                            |                                              954,603 |
| SH coefficients / Gaussian                          |                                             45 (SH3) |
| complete typed snapshot                             |                           232,923,132 B / 223 chunks |
| Anchor required chunks                              |                  37 / 38,793,316 B (16.655% of full) |
| manifest registration                               |                                             2.380 ms |
| spatial packing                                     |                                           498.830 ms |
| required-chunk accept + atomic commit               |                    670.432 ms (in-process, not HTTP) |
| independent working-set mmap → tensor assembly      |                                            10.985 ms |
| first 512² authoritative Anchor + typed publication |                                       **585.070 ms** |
| selective / full reference gsplat render            |                                    1.336 s / 1.215 s |
| GPU peak: Anchor / full reference                   |                        403,944,448 B / 619,641,344 B |
| process peak RSS                                    | 7,517,839,360 B (includes loader and full reference) |

Exact parity: RGB bytes/digest, alpha, contributor global Stable IDs, and
contributor weights all equal the full-chunk reference. The fixed camera had
99,611 non-zero-alpha pixels.

## Interpretation and remaining validation

The representative Anchor transfers 83.345% fewer typed bytes and uses
215,696,896 B less peak GPU allocation than its full-chunk reference. The SH0
fixture likewise transfers 74.214% fewer bytes and uses 23,793,664 B less
Anchor GPU allocation. These results establish selective residency and typed
Anchor publication under the locked GPU runtime; they do not claim that every
camera benefits by the same amount.

The user-observed browser request took 3.7 minutes on the old deployed
Companion. That exact browser CameraBinding/resolution was not captured, so it
is not an apples-to-apples speedup claim. The next required operator check is
to restart the local Companion from this revision and repeat that browser
request; DevTools should then show a sub-second-scale render phase for a
similarly sized working set, with upload time visible separately before the
final `anchor-renders` retry.
