# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V Evidence, working sets, Gaussian Lifting, or the reference Contributor backend.

## Same-decision production Evidence

Production Evidence uses the actual alpha-compositing contribution:

```text
w = alpha × incoming transmittance
```

Authoritative RGB and production Evidence must share the decisions that determine projected data, front-to-back order, sigma/alpha evaluation, validity thresholds, incoming transmittance, contribution weight, and early termination.

Multiple passes are valid only when later passes reuse those authoritative decisions. Identical formulas in independently deciding kernels do not establish same-decision behavior.

## Evidence semantics

- Per-view, per-Gaussian production channels are Positive Mass (P), Negative Mass (N), and Visible Mass (V).
- Positive Evidence comes from strong target regions; Negative Evidence comes from explicit local background/context, not the entire exterior by default.
- Boundary/ignore regions are neutral or low-weight and may have a diagnostic channel.
- Missing, unusable, excluded, or unobserved Evidence is not negative.
- Material positive and negative support yields Uncertain/Mixed rather than a forced binary result.
- Uncertain is diagnostic and excluded from native Candidate application.
- Evidence Policy is versioned, replayable, and benchmark-calibrated.

## Working sets

- Render Working Set contains every Gaussian or chunk required to reproduce complete-scene RGB, occlusion, transmittance, and termination for a CameraBinding.
- Evidence Working Set contains only Stable IDs receiving P/N/V writes, normally Core Target plus Context.
- Gaussians outside the Evidence Working Set may still be required render occluders.
- Never rasterize only the Evidence Working Set when it changes visibility or transmittance.
- Validate spatial reduction against a full-scene or reference path. Scene Chunk Miss fails closed; partial rendering never publishes a Ready View.

## Per-view Evidence artifact

A formal artifact binds all material identity, including target/context/dependency, CameraBinding, authoritative RGB, Stable Mask, Evidence Policy, render/evidence working sets, Stable IDs, P/N/V arrays, and raster/Evidence implementation identity.

Any material dependency change invalidates the artifact. Editing an unpublished Mask does not invalidate current Evidence; publishing a new Stable Mask does.

## Reference Contributor backend

Complete per-pixel Contributor IDs/weights are for diagnostics, fixtures, and reference comparison. Reference failure never converts valid RGB into Render Failed. Production must not silently fall back to nearest-Gaussian, top-k, distance, center-projection, or visibility-only attribution.

Keep reference fixtures until the production path passes declared equivalence and quality gates.

## CUDA and production claims

- Pin source, compiler/runtime assumptions, and supported GPU architecture.
- Preserve front-to-back order and Stable ID mapping; never silently truncate output.
- Detect overflow and capacity failure explicitly.
- Measure register pressure, global writes, atomic contention, latency, VRAM, and OOM behavior where material.
- Treat FP32 atomic accumulation as non-associative; validate classification stability rather than claiming bit-exact sums.
- Do not call a separate kernel production-equivalent merely because it uses the same formula.

Production claims require the locked runtime and GPU evidence defined in [Project verification](execution-and-verification.md).
