# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V Evidence, working sets, Gaussian Lifting, or the reference Contributor backend.

## Same-decision Direct Evidence

Production Evidence uses actual alpha-compositing contribution:

```text
w = alpha × incoming transmittance
```

RGB and production Evidence share the same authoritative decision source for:

- projected Gaussian data;
- front-to-back ordering;
- sigma and alpha evaluation;
- validity thresholds;
- incoming transmittance;
- `alpha × T` weight;
- early termination.

One CUDA launch is not required. Multiple passes are valid only when later passes reuse authoritative decisions instead of independently re-deciding boundary-sensitive acceptance or termination. Identical formulas in separate kernels do not prove same-decision behavior.

## Evidence semantics

- Production channels are per-view, per-Gaussian Positive Mass (P), Negative Mass (N), and Visible Mass (V).
- Positive Evidence comes from strong target regions.
- Negative Evidence comes from explicit local background or context regions, not the entire image exterior by default.
- Boundary and ignore regions are neutral or low-weight and may produce a separate diagnostic channel.
- Missing, unusable, excluded, or unobserved Evidence is not negative.
- Material positive and negative support classifies a Gaussian as Uncertain or Mixed rather than forcing a binary result.
- `Uncertain` is diagnostic and excluded from native Candidate application.
- Evidence Policy is versioned, replayable, and benchmark-calibrated.

## Render and Evidence working sets

- Render Working Set contains every Gaussian or chunk required to reproduce complete-scene RGB, occlusion, transmittance, and termination for a CameraBinding.
- Evidence Working Set contains only Stable Gaussian IDs receiving P/N/V writes, normally Core Target plus Context.
- Gaussians outside Evidence Working Set may still be required Render Working Set occluders.
- Never rasterize only Evidence Working Set when it changes visibility or transmittance.
- Spatial reduction must be conservative and validated against a full-scene or reference path.
- Scene Chunk Miss fails closed; a partial Render Working Set never publishes a Ready View.

## Per-view Evidence artifact

A formal per-view Evidence artifact binds at least:

```text
target/context/dependency identity
CameraBinding digest
authoritative RGB digest
Stable Mask digest
Evidence Policy digest
Render Working Set token
Evidence Working Set token
Stable Gaussian IDs
P / N / V arrays
raster/evidence implementation identity
```

Any material dependency change invalidates the artifact. Editing an unpublished Mask does not invalidate current Evidence; publishing a new Stable Mask does.

## Reference Contributor backend

- Complete per-pixel Contributor IDs and weights exist only for diagnostics, fixtures, and reference comparison.
- Contributor alpha reconciliation and mass-conservation checks remain valid for the reference backend.
- Reference Contributor failure never turns valid RGB into Render Failed.
- Production never silently falls back to nearest-Gaussian, top-k, distance, center projection, or visibility-only attribution.
- Keep the reference backend and its fixtures until the production path passes declared equivalence and quality gates.

## Implementation sequence

```text
reference P/N/V PoC
→ policy and quality validation
→ same-decision production Evidence path
→ artifact/cache integration
→ calibration and OOM/cancellation hardening
```

## CUDA and renderer conventions

- Pin source, compiler and runtime assumptions, and supported GPU architecture.
- Preserve front-to-back order and Stable ID mapping.
- Never silently truncate Evidence or Contributor output.
- Detect overflow and capacity failure explicitly.
- Measure register pressure, global writes, atomic contention, latency, and VRAM.
- Treat atomic FP32 accumulation as numerically non-associative; validate classification stability rather than claiming bit-exact sums.
- Do not call a separate kernel production-equivalent merely because it uses the same formula as authoritative RGB.

Production claims require the locked runtime and GPU validation described in [Execution and verification](execution-and-verification.md).
