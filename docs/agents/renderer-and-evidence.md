# Renderer and Evidence

Read this file for gsplat, CUDA, authoritative RGB, P/N/V, CWED/depth moments, Working Sets, q+s readout, Reliability, or reference Contributor.

## Current implementation versus target

Current Direct Evidence produces P/N/V plus optional boundary diagnostics and one Negative Mass channel. Pinned gsplat exposes projected depth, but the project-owned Direct Evidence ABI does not consume it yet.

The reviewed target adds internal depth moments, bounded q+s recurrence, and multi-channel consensus readout. Classified N and leave-one-out Reliability are not production prerequisites.

## Same-decision production Evidence

Production uses `w = alpha × incoming transmittance`. Authoritative RGB, Direct Evidence, and reviewed readout moments must share projected inputs, ordering, validity, transmittance, accepted weight, and termination decisions.

## CWED contract

```text
M0=Σw; M1=Σwz; M2=Σwz²
CWED=M1/M0
variance=max(0,M2/M0-CWED²)
```

CWED is internal, invalid at low M0, weakened at high variance, and is not first-hit/surface truth.

## Consensus readout contract

For frozen `Core ∪ Frontier ∪ Context` semantic scope:

```text
q̃ = 0.5 + s(q - 0.5)
M_scope    = Σ w
M_fg       = Σ w q̃
M_known    = Σ w s
M_core     = Σ_Core w
M_frontier = Σ_Frontier w
```

Derived `P/K/C/F` require valid scope mass. Render-only and Out-of-Scope Gaussians still occlude and affect transmittance/termination but do not write semantic moments. Readout maps remain Companion-local and are not visibility authority.

## Reliability semantics

- current production channels remain Positive, one Negative, and Visible Mass;
- Reliability weights P/N only; raw V remains realized visibility;
- trusted comparison requires valid semantic-scope mass and knownness;
- positive interior receives bounded Frontier/unknown protection;
- negative ring has no symmetric exemption;
- boundary is low-weight/diagnostic; Far Neutral is excluded;
- insufficient comparison support is neutral;
- User Confirmed/manual observations remain full-weight;
- leave-one-out is offline/reference-only.

## Canonical recurrence constraints

- exact current Included Stable set defines canonical input;
- arrival order/cache history cannot define semantics;
- same-round Reliability feedback is forbidden;
- scope remains frozen during solve;
- non-convergence cannot publish Candidate;
- GPU optimizations require cold canonical reference equivalence.

## Seed and Working Sets

S0 uses P/N/V+connectivity; S1 adds soft center-depth consistency. Failed S1 cannot erase Discovery Envelope support. Render Working Set preserves occlusion; Evidence Working Set identifies writes; boundary contact remains discovery input.

## Reference and production claims

Complete Contributor remains reference/debug. Pin source/runtime/GPU/schema/policy. Measure numerical parity, registers/global writes, latency, VRAM, order independence, self-influence gap, Seed/Frontier recovery, and Candidate quality. Experimental identities are not production-ready.
