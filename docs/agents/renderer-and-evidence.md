# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V, CWED/depth moments, Working Sets, lifting, provisional soft-mask rendering, or reference Contributor.

## Current implementation versus target

Current Direct Evidence produces P/N/V plus optional boundary diagnostics and one Negative Mass channel. Pinned gsplat already exposes projected Gaussian depth in raster metadata, but the project-owned Direct Evidence CUDA ABI does not yet consume it.

The reviewed target adds an internal depth-moment path; it does not make classified N a production prerequisite.

## Same-decision production Evidence

Production uses:

```text
w = alpha × incoming transmittance
```

Authoritative RGB and Direct Evidence share projected inputs, front-to-back ordering, sigma/alpha validity, transmittance, accepted weight, and termination.

## CWED contract

The reviewed internal moments are:

```text
M0 = Σw
M1 = Σwz
M2 = Σwz²
CWED = M1/M0
variance = max(0, M2/M0 - CWED²)
```

- accumulate from the accepted Direct Evidence sequence;
- low `M0` is invalid, not a trusted depth;
- high variance weakens depth-consistency use;
- CWED is not first-hit or authoritative visible-surface depth;
- moments stay Companion-internal and do not create a Browser protocol artifact.

## Evidence semantics

- Current production channels are Positive, one Negative, and Visible Mass.
- Missing/unusable/excluded/unobserved is not negative.
- Reliability may weight semantic P/N; raw V remains realized visibility.
- Material positive and negative support yields Uncertain/Mixed.
- Depth-classified N is V2AX experiment only. Any promotion requires explicit schema, reference, consumer, policy, Runtime Profile, and production-identity migration.

## Seed and Working Sets

- S0 uses P/N/V and connectivity; S1 adds soft center-depth consistency.
- A failed S1 score cannot erase plausible support from Discovery Envelope.
- Render Working Set preserves complete visibility/transmittance.
- Evidence Working Set identifies write targets but boundary contact remains a discovery source.
- Core Target, Discovery Envelope, and Frontier must not be conflated.

## Reference and production claims

Complete Contributor remains reference/debug. Pin source/runtime/GPU/schema/policy inputs. Measure numerical stability, latency, registers/global writes, VRAM, OOM, Seed quality, Frontier recovery, and Candidate quality. Experimental identities are not production-ready.
