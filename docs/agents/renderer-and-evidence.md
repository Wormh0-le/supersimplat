# Renderer and Evidence

Read for gsplat, CUDA, RGB, P/N/V, CWED, Working Sets, q+s readout, Reliability, Target Scope, or reference Contributor.

## Current versus target

Current Direct Evidence produces immutable single-N P/N/V and uses EvidenceWorkingSet v1 Core/Context roles. Pinned gsplat exposes projected depth, but project CUDA does not yet consume it. The target adds internal depth/readout moments and a separate TargetScopeState; classified N remains experimental.

## Same-decision rule

Authoritative RGB, Direct Evidence, CWED moments, and consensus readout reuse the accepted front-to-back alpha/transmittance decision chain. Independently re-deciding formulas do not establish same-decision behavior.

## Consensus/update contract

- q/s readout uses `M_scope/M_fg/M_known/M_core/M_frontier` and derives P/K/C/F.
- Render-only occluders affect transmittance but not semantic moments.
- Each iteration reaggregates immutable normalized per-View masses.
- `q=(a+P)/(a+b+P+N)`; `s=(1-exp(-E/tau_E))*(1-exp(-V/tau_V))`.
- Reliability multiplies P/N only; V remains unweighted.
- Non-convergence, oscillation, stale scope, and scope-advanced output cannot publish Candidate.

## Scope/Working Set migration

TargetScopeState is semantic authority for Core, Envelope, Frontier, rejected ledger, and Context. EvidenceWorkingSet v2 must project Core + active Frontier + required Context with exact scope binding. Rejected Frontier is not Context. The v1 contract must remain unchanged until an explicit schema/consumer/runtime-identity migration.

## Production claims

Pin source/runtime/GPU/schema/policy/reduction/scope identities. Measure readout channels, q/s and scope memory, componentization, atomics/registers, latency, VRAM/OOM, warm/cold equivalence, convergence, scope churn, and density-invariant Debt. Experimental identities cannot enter production before calibration and explicit promotion.

## Reference paths

Complete Contributor, V2AX classified N, and leave-one-out Reliability remain reference/benchmark paths and never silently become product authority.
