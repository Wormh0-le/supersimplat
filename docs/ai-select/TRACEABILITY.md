# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Implemented v1.3 traceability remains under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Coverage summary

C001–C012 remain implemented v1.3 foundations. Existing v2 requirements N001–N055 remain owned as previously mapped.

## Publication and consent requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N056 | Readiness × terminal outcome Candidate publication and explicit consent are completely mapped | V2H | accepted / decomposition pending |
| N057 | calibration, policy freeze, production promotion, cutover, and release qualification have explicit owners | unassigned | blocker |
| N058 | Candidate publication requires an exact current converged scope-stable production-identity snapshot | V2H/V2I | accepted / decomposition pending |
| N059 | only eligible Ready-low-gain normal success auto-publishes Candidate | V2H | accepted / decomposition pending |
| N060 | eligible Ready forced terminals require explicit `Use Ready Candidate` without recomputation | V2H/V2J | accepted / review-decomposition pending |
| N061 | eligible Limited terminals require explicit `Use Limited Candidate`; Not Ready never publishes | V2H/V2J | accepted / review-decomposition pending |
| N062 | scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, and late results cannot publish | V2H/V2I | accepted / decomposition pending |
| N063 | Re-Lift recomputes exact current Stable inputs and is not an alias for accepting an existing snapshot | V2H/V2J | accepted / review-decomposition pending |
| N064 | automatic and explicit terminal publication use idempotent Candidate Publication Attempt identity and atomic replacement | V2H/V2I | accepted / decomposition pending |
| N065 | running acquisition preserves prior Candidate inspection but temporarily blocks Candidate application without itself causing staleness | V2I/V2J | accepted / review-decomposition pending |
| N066 | Cancel never auto-publishes; an eligible pre-Cancel snapshot may be explicitly used through fresh publication identity | V2H/V2I/V2J | accepted / review-decomposition pending |

## Result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 66
mapped new requirements             = 65
unassigned release requirement      = N057
accepted cross-ticket decisions     = Q4-B through Q10-C
agent-ready stages                  = 0
next review item                    = V2J UI + Expert Recovery presentation
```