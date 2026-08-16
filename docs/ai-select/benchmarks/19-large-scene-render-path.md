# Ticket 19 large-scene render-path validation

Date: 2026-08-17

## Scope and environment

- Browser: Headless Chrome 151.0.0.0 with precise heap reporting
- Companion: locked `uv.lock` Python 3.12 environment
- GPU: NVIDIA GeForce RTX 4090 D, 24,564 MiB
- Large-scene fixture: 200,000 Gaussians, four immutable spatial chunks,
  12,800,000 payload bytes, 128 × 128 authoritative RGB
- Browser fixture: 250,000 source Gaussians, delete stride 16, world transform,
  palette transform, color grade and bounded 4 MiB transfer chunk

The profile commands are reproducible:

```sh
rtk google-chrome --headless=new --no-sandbox --disable-gpu --enable-precise-memory-info --dump-dom file:///home/ubuntu/orca/workspaces/supersimplat/houndshark/scripts/benchmarks/ticket19-browser-effective-snapshot-profile.html
rtk uv run --project selection-service-companion --locked --python 3.12 python scripts/benchmarks/profile_ticket19_large_scene.py
rtk uv run --project selection-service-companion --locked --python 3.12 --extra renderer python -m unittest discover -s selection-service-companion/tests -p 'test_spatial_scene_gpu_parity.py'
```

## Browser effective-snapshot profile

| Phase                                |    Time | Used JS heap before | Used JS heap after |
| ------------------------------------ | ------: | ------------------: | -----------------: |
| Source allocation                    |  4.5 ms |           737,211 B |       16,491,587 B |
| Delete/world/palette/color mutations |  5.0 ms |        16,491,759 B |       16,742,055 B |
| Effective typed snapshot             | 21.3 ms |        16,742,151 B |       31,258,543 B |
| Bounded transfer chunk               |  1.0 ms |        31,258,639 B |       35,453,535 B |

The resulting effective snapshot contains 234,375 Gaussians. Browser memory is
reported separately from Companion RSS and GPU allocation. The executable
browser-code fixture in `splat-scene-snapshot-effective.test.js` additionally
proves delete filtering, world/palette transforms, color grading, exact target
Stable ID mapping and changed-world digest invalidation against the production
snapshot binding.

The locked-GPU parity suite additionally exports a production
`SplatSceneSnapshotBinding` fixture through the real packed manifest/payload
seam, commits it in the Companion, and verifies its authoritative RGB digest
and alpha coverage against the independently declared effective fixture.

## Companion and GPU profile

| Phase                               |      Time |      RSS before |       RSS after |
| ----------------------------------- | --------: | --------------: | --------------: |
| Scene typed-payload creation        |  16.53 ms |   543,809,536 B |   570,875,904 B |
| Manifest registration               |   0.11 ms |   570,875,904 B |   570,875,904 B |
| Chunk transfer and validation       |  40.32 ms |   570,875,904 B |   572,190,720 B |
| Conservative working-set resolution |   0.09 ms |   572,190,720 B |   572,190,720 B |
| Cold gsplat RGB and PNG             | 292.40 ms |   572,190,720 B | 1,068,617,728 B |
| Warm gsplat RGB and PNG             |   9.65 ms | 1,068,617,728 B | 1,069,080,576 B |

Cold `Server-Timing` measured `gsplat=272.259 ms` and `png=9.128 ms`.
The exact repeat measured `gsplat=9.299 ms` and `png=0.242 ms`; scene-tensor
cache counters moved from `{hits: 0, misses: 1}` to `{hits: 1, misses: 1}`.
Both renders produced RGB digest
`sha256:7d6f3c84bc3d4d152d5a3f208ccfbc48bbe215d417b8d79319c6aa41b2b2c643`.
The locked backend reported 38,745,088 bytes peak VRAM for this raster; retained
scene tensors remain part of the warm baseline, so this number is not added to
the browser or Companion RSS measurements.

The measured cold-to-warm wall-time reduction is 96.7%. This is reuse of exact
immutable Scene/WorkingSet identity, not a changed raster policy or reduced
render scope.

## Parity and failure gates

- Selective versus full working-set RGB, alpha, Contributor IDs and weights
  match for SH degrees 0–3 on the locked GPU.
- A target plus visible non-target occluder fixture matches its full declared
  render scope and produces different RGB from invalid target-only rendering.
- Same WorkingSetToken returns the same working-set object and deterministic
  membership digest; repeated CameraBindings reuse immutable CUDA scene
  tensors, while the camera-keyed CPU working-set LRU stays bounded.
- Camera, dependency, raster implementation and runtime changes miss the RGB
  cache. Exact Undo back to the prior semantic dependency reuses the prior RGB.
- Reference Contributor results use a separate backend-bound cache. Missing or
  failed Contributor data never invalidates authoritative RGB.
- Scene/Chunk Miss and invalid or incomplete render-scope metadata fail before
  Ready RGB publication.
- Support probes and Target Geometry Hints use only the declared target row
  range; visible read-only occluders participate only in rasterization.

## Result

Ticket 19's measured gates pass on the locked environment. The retained
versioned raster seam is `gsplat-reference-rgb/v1` with runtime build
`sha256:a04a3840702bca8d86365dc44c8a693344e54fb09db8a2c2131a4ed711717e40`;
Ticket 20 can replace that identity without accepting old RGB as compatible.
