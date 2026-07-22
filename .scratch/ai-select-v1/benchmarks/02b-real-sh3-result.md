# Ticket 02B real SH3 working-set validation

Run date: 2026-07-22

Fixture:

```text
/home/ubuntu/wormh01e/3dgrut/runs/q9000_sanity/MT20260702-190531-1M-0507_165452/export_last.ply
```

The file is a binary little-endian SH3 PLY (`f_rest_0` through `f_rest_44`)
with 954,603 Gaussians. The validation used no editor mutations, so the
benchmark harness maps its raw effective values directly into the v1 typed SoA
layout. It is a real-geometry/locked-renderer validation, but it is not a
measurement of a browser-produced snapshot with active editor edits.

Environment:

```text
RendererRuntimeStatus(status='ready', cuda_version='12.8', message=None)
GPU: NVIDIA GeForce RTX 4090 D (24,564 MiB), driver 580.173.02
```

Command:

```sh
cd selection-service-companion
uv run --locked --extra renderer python \
  ../.scratch/ai-select-v1/benchmarks/02b-real-sh3.py \
  --ply /home/ubuntu/wormh01e/3dgrut/runs/q9000_sanity/MT20260702-190531-1M-0507_165452/export_last.ply \
  --target-mode first-gaussian --chunk-bytes 1048576
```

The reproducible fixed Anchor is a 512 × 512 pinhole CameraBinding, `fx = fy =
1800`, near `0.01`, far `1000`, looking at the first Morton-ordered Gaussian.
It produced 99,611 non-zero-alpha pixels, so the equality result is not a
background-only comparison.

| Metric                                |     Selective result | Full/reference result / note                               |
| ------------------------------------- | -------------------: | ---------------------------------------------------------- |
| effective Gaussian count              |              954,603 | same                                                       |
| typed binary SceneSnapshot bytes      |          232,923,132 | 223 chunks total                                           |
| required chunks                       |                   37 | 223                                                        |
| required typed bytes                  | 38,793,316 (16.655%) | 232,923,132                                                |
| initial manifest registration         |              2.44 ms | direct in-process Companion store                          |
| spatial packing                       |            504.19 ms | benchmark-side typed SoA build                             |
| required chunk accept + atomic commit |            689.65 ms | in-process; not HTTP-network time                          |
| working-set tensor assembly           |             11.51 ms | mmap → typed tensor path                                   |
| gsplat render                         |              1.567 s | 1.300 s full reference                                     |
| Companion process peak RSS            |      7,492,345,856 B | includes fixture loader, payload build, and full reference |
| GPU peak allocation                   |        403,944,448 B | 620,689,920 B full                                         |
| browser editor peak memory            |         not measured | no browser instrumentation run                             |

The selected Anchor transferred 83.345% fewer typed payload bytes and used
216,745,472 B less peak GPU allocation than the full reference in this run.
The broader 4 MiB experiment for the same fixed Anchor required 18/56 chunks
(75,494,088 B, 32.412% of full), which is why v1's nominal spatial chunk target
is 1 MiB while its hard per-payload limit remains 4 MiB.

Exact locked-runtime parity:

```text
RGB bytes:                 equal
RGB digest:                equal
alpha:                     equal
contributor Stable IDs:    equal
contributor weights/mass:  equal
```

Conclusion: this representative non-empty Anchor materially reduces transferred
bytes and resident GPU working-set memory. The measured process RSS is not a
steady-state Companion-memory claim, and the missing browser peak-memory
measurement remains an explicit validation gap.
