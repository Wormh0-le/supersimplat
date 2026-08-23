# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Implemented v1.3 traceability remains under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Carried-over implemented foundations

C001–C012 remain implemented v1.3 foundations: target/Stable identity, authoritative RGB, SAM 3 Image, Stable Mask/Participation/User Confirmed authority, single-N Direct P/N/V, v1 Working Sets/boundary contact, Lift Readiness, atomic Candidate/stale blocking, Native operations, suspension/Undo, and User-added View recovery foundation.

## New v2 target requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N001–N004 | projected depth, CWED moments, non-authoritative semantics, V2AX experiment | V2A | reviewed/decomposition-pending |
| N005–N014 | S0/S1 Seed, seed-independent discovery, Core Coverage, Frontier Debt, readiness inputs | V2B/V2E/V2G | reviewed/decomposition-pending |
| N015–N019 | continuous q+s bounded recurrence, lagged Reliability, P/N weighting with raw V | V2C/V2D/V2E | reviewed/decomposition-pending |
| N020–N035 | View Utility, budgets, publication, loop, cancellation, Expert Recovery, retired persistent controls | V2F–V2J | accepted/review-required |
| N036 | calibration, policy freeze, production promotion, cutover, and qualification have explicit owners | unassigned | blocker |
| N037–N043 | frozen-scope solve, non-convergence gate, immutable reaggregation, pseudo-mass q/s, robust Reliability, convergence, regional/LOO split | V2C/V2D/V2E | reviewed/decomposition-pending |
| N044 | TargetScopeState separates Scope Epoch/Revision, Core, Envelope ledger, Frontier, rejected ledger, and Context | V2B/V2E | accepted/reviewed-parent |
| N045 | Core is monotonic inside a Scope Epoch; authoritative correction/removal may rotate the epoch | V2B/V2E/V2I | accepted/reviewed-parent |
| N046 | Envelope expansion is bounded, seed-independent, provenance-recorded, and deduplicated | V2B/V2E | accepted/reviewed-parent |
| N047 | Frontier promotion/rejection/reopen is component-level, hysteretic, and rejected Frontier is not Context | V2B/V2E | accepted/reviewed-parent |
| N048 | material Scope Delta advances scope and forces a new canonical solve before Readiness/Candidate | V2C/V2E/V2H/V2I | accepted/reviewed-parent |
| N049 | Scope Revision churn has a finite per-attempt budget and fails Limited/closed | V2G/V2I | accepted-scope/review-required |
| N050 | Frontier Debt is structured by component and distinguishes unobserved, conflict, and promotion-pending debt | V2E/V2F/V2G | accepted/reviewed-parent |
| N051 | EvidenceWorkingSet v2 projects explicit Core/active-Frontier/Context roles and exact scope identity | V2B/V2E | accepted/decomposition-pending |

## Coverage result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 51
mapped new requirements             = 50
unassigned release requirement      = N036
accepted cross-ticket decisions     = Q4-B, Q5-D, Q6-B, Q7-B
reviewed parent direction           = V2A–V2E
agent-ready stages                  = 0
next review item                    = Q8 View Utility probe + cost + candidate pool
```

No implementation closure may be claimed while N036 is unassigned or relevant stages remain review-required/decomposition-pending.
