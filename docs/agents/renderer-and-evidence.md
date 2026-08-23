# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V Evidence, working sets, lifting, provisional consensus rendering, or the reference Contributor backend.

## Current implementation versus v2 target

The shipped Direct Evidence ABI currently produces P/N/V (plus optional boundary diagnostics). Final Spec v2.0 targets Evidence-Internal Depth and depth-classified Negative Mass, but those channels are **not implemented yet**. Do not assume camera-space `z` is already present in the current CUDA ABI; prove the data path from code before changing the kernel.

## Same-decision production Evidence

Production Evidence uses the actual alpha-compositing contribution:

```text
w = alpha × incoming transmittance
```

Authoritative RGB and production Evidence share the accepted projected data, front-to-back ordering, sigma/alpha evaluation, validity thresholds, incoming transmittance, contribution weight, and termination decisions.

Multiple passes are allowed only when later work reuses authoritative accepted decisions or an explicitly reviewed equivalent seam. Identical formulas in independently deciding kernels do not establish same-decision behavior.

## Evidence semantics

- Current production channels are per-view, per-Gaussian Positive Mass, Negative Mass, and Visible Mass.
- Missing, unusable, excluded, or unobserved Evidence is not negative.
- Boundary/ignore regions are neutral or low-weight.
- Material positive and negative support yields Uncertain/Mixed rather than a forced binary result.
- V2 reliability may weight semantic P/N only; raw V remains the realized-visibility source unless a later accepted decision changes it.
- Any split of Negative Mass changes schema, consumers, reference parity, policy identity, and production identity; it is not merely an internal comment-level change.

## V2 depth and soft-mask review gate

Before V2A or V2C becomes agent-ready, the reviewed contract must define:

- where camera-space depth enters the CUDA/reference path;
- whether expected depth and depth classification require one traversal, two traversals, or retained accepted-contribution data;
- zero-mass and mixed-surface behavior;
- the exact front/near/behind channel schema;
- the provisional-consensus representation and soft-mask rendering input;
- reference parity, ABI migration, runtime identity, performance, and OOM gates.

Do not call contribution-weighted expected depth a visible-surface truth without a calibrated qualification.

## Working sets

- Render Working Set preserves complete-scene RGB, occlusion, transmittance, and termination.
- Evidence Working Set identifies Stable IDs receiving Evidence writes.
- Gaussians outside the Evidence Working Set may still be required render occluders.
- Core Target denominator changes must not shrink silently or manufacture high coverage.
- Scene Chunk Miss and incomplete render scope fail closed.

## Reference Contributor backend

Complete per-pixel Contributor IDs/weights remain diagnostics and reference comparison only. Reference failure never converts valid RGB into Render Failed. Production must not silently fall back to nearest-Gaussian, top-k, center projection, or visibility-only attribution.

## Production claims

Pin source, compiler/runtime, GPU architecture, schema, policy identity, and benchmark inputs. Measure classification stability, register/global-write cost, atomic contention, latency, VRAM, and OOM behavior. Experimental policy IDs are not production-ready identities.
