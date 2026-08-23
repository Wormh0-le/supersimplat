# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Implemented v1.3 traceability remains under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Carried-over implemented foundations

C001–C012 remain implemented v1.3 foundations: target/Stable identity, authoritative RGB, SAM 3 Image, Stable Mask/Participation/User Confirmed authority, single-N Direct P/N/V, Working Sets/boundary contact, Lift Readiness, atomic Candidate/stale blocking, Native operations, suspension/Undo, and User-added View recovery foundation.

## New v2 target requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N001–N004 | projected depth, CWED moments, non-authoritative semantics, V2AX experiment | V2A | reviewed/decomposition-pending |
| N005–N014 | S0/S1 Seed, TargetScopeState, component Frontier, Debt, readiness inputs | V2B/V2E/V2G | reviewed/decomposition-pending |
| N015–N019 | continuous q+s canonical solve, lagged Reliability, P/N weighting with unweighted V | V2C/V2D/V2E | reviewed/decomposition-pending |
| N020–N035 | View Utility, budgets, publication, orchestration, cancellation, Expert Recovery | V2F–V2J | accepted/review-required |
| N036 | calibration, policy freeze, production promotion, cutover, qualification have explicit owners | unassigned | blocker |
| N037–N043 | frozen scope, fail-closed convergence, immutable reaggregation, pseudo-mass q/s, robust Reliability, regional readout | V2C/V2D/V2E | reviewed/decomposition-pending |
| N044 | candidate pool is deterministic, finite, layered, and component-Debt aware | V2F | accepted/reviewed-parent |
| N045 | all candidates pass geometry pruning; only a deterministic shortlist receives an occlusion-aware raster probe | V2F | accepted/reviewed-parent |
| N046 | ViewUtilityProbe is prospective only and never becomes RGB, Evidence, Coverage, Readiness, or Candidate authority | V2F | accepted/reviewed-parent |
| N047 | complete Render Working Set and render-only occluders remain active in the low-resolution probe | V2F | accepted/reviewed-parent |
| N048 | canonical View Utility cost uses deterministic units; wall-clock cannot alter candidate ranking | V2F/V2G/V2I | accepted/review-required |
| N049 | full authoritative RGB/SAM/Evidence runs only for the selected winner on the product path | V2F/V2I | accepted/review-required |
| N050 | predicted Core/Frontier/Uncertain gains are recorded against realized outcomes for calibration | V2F/calibration owner TBD | accepted/owner-incomplete |
| N051 | probe and scoring identities bind target, dependency, scope, q/s, candidate, policies, and Render Working Set | V2F/V2I | accepted/review-required |

## Coverage result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 51
mapped new requirements             = 50
unassigned release requirement      = N036
reviewed parent direction           = V2A–V2F
accepted decisions                  = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C
agent-ready stages                  = 0
next review item                    = Q9 V2G/V2I budgets + identity + replay
```

No implementation closure may be claimed while N036 is unassigned or relevant stages remain review-required/decomposition-pending.
