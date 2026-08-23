# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V, CWED/depth moments, Working Sets, q+s consensus rendering, or reference Contributor.

## Current implementation versus target

Current Direct Evidence produces P/N/V plus optional boundary diagnostics and one Negative Mass channel. Pinned gsplat exposes projected Gaussian depth in raster metadata, but the project-owned Direct Evidence CUDA ABI does not yet consume it.

The reviewed target adds internal depth moments and a q+s consensus recurrence. Neither classified N nor a Browser consensus artifact is a production prerequisite.

## Same-decision production Evidence

Production uses:

```text
w = alpha × incoming transmittance
```

Authoritative RGB and Direct Evidence share projected inputs, front-to-back ordering, sigma/alpha validity, transmittance, accepted weight, and termination.

## CWED contract

```text
M0 = Σw
M1 = Σwz
M2 = Σwz²
CWED = M1/M0
variance = max(0, M2/M0 - CWED²)
```

CWED is internal, invalid at low M0, weakened at high variance, and is not first-hit or authoritative surface depth.

## Evidence and consensus semantics

- Current production channels are Positive, one Negative, and Visible Mass.
- Missing/unusable/excluded/unobserved is not negative.
- Reliability weights semantic P/N only; raw V remains realized visibility.
- `q` is membership tendency; `s` is support/knownness.
- Consensus readout must consume lagged q/s and must not create an independent visibility authority.
- The exact soft foreground/support/trust readout and residual gating remain Q5 review items.
- Classified N is V2AX experiment only.

## Canonical recurrence constraints

- Canonical solve uses the exact current Included Stable observation set.
- View arrival order and cache history cannot change canonical semantics.
- One public revision may contain bounded private iterations.
- Same-round Reliability feedback is forbidden.
- Scope remains frozen during the solve.
- Non-convergence cannot publish Candidate.
- Any GPU optimization requires cold canonical reference equivalence.

## Seed and Working Sets

- S0 uses P/N/V and connectivity; S1 adds soft center-depth consistency.
- A failed S1 score cannot erase plausible support from Discovery Envelope.
- Render Working Set preserves complete visibility/transmittance.
- Evidence Working Set identifies write targets; boundary contact remains a discovery source.
- Core Target, Discovery Envelope, and Frontier must not be conflated.

## Reference and production claims

Complete Contributor remains reference/debug. Pin source/runtime/GPU/schema/policy inputs. Measure numerical stability, latency, memory, convergence, order independence, Seed quality, Frontier recovery, and Candidate quality. Experimental identities are not production-ready.
