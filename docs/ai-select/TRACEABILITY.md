# Final Spec v2.0 Current Traceability

Status: **current target coverage — pre-implementation review**  
Updated: 2026-08-23

Implemented v1.3 traceability remains under `docs/ai-select/history/v1/TRACEABILITY-V1.md`.

## Coverage summary

C001–C012 remain implemented v1.3 foundations. Existing v2 requirements N001–N043 remain owned as previously mapped.

## Acquisition identity and budget requirements

| ID | Requirement | Owner | Status |
|---|---|---|---|
| N044 | Acquisition Series contains the initial and fresh Continue Attempts under cumulative caps | V2G/V2I/V2J | accepted / review-decomposition pending |
| N045 | Attempt, Iteration, Utility, probe, endpoint, Consensus, and Scope identities remain hierarchical and distinct | V2I | accepted / decomposition pending |
| N046 | Browser owns an append-only digest-chained Decision Journal and product action sequence | V2I | accepted / decomposition pending |
| N047 | successful observations, selected candidates, deterministic cost, failures/replacements, and Scope Revisions use separate finite ledgers | V2G/V2I | accepted / decomposition pending |
| N048 | failed or Excluded work is free only for Successful Observation Budget and still consumes applicable cost/failure ledgers | V2G | accepted / decomposition pending |
| N049 | same-attempt replay reuses committed decisions/results without reranking or budget debit | V2I | accepted / decomposition pending |
| N050 | fresh retry/replacement uses new identities and declared budget debit; replacement follows committed ranking | V2G/V2I | accepted / decomposition pending |
| N051 | wall-clock/cache state does not alter canonical ranking or deterministic budget decisions | V2F/V2G/V2I | accepted / decomposition pending |
| N052 | Cancel closes publication authority immediately and discards late results while preserving completed artifacts | V2I/V2J | accepted / decomposition pending |
| N053 | exact Suspend/Resume continues only from a compatible journal boundary; otherwise the Attempt is stale | V2I | accepted / decomposition pending |
| N054 | Continue Acquisition creates a fresh Attempt with new per-Attempt allowances and preserved Series caps/artifacts | V2G/V2I/V2J | accepted / decomposition pending |
| N055 | Companion remains endpoint/derived-state owner, not an autonomous product-session authority | V2I | accepted / decomposition pending |
| N056 | Readiness × terminal outcome Candidate publication and explicit Limited consent are completely mapped | V2H | review-required / next |
| N057 | calibration, policy freeze, production promotion, cutover, and release qualification have explicit owners | unassigned | blocker |

## Result

```text
carried-over implemented requirements = 12
new v2 requirements                 = 57
mapped new requirements             = 56
unassigned release requirement      = N057
accepted cross-ticket decisions     = Q4-B through Q9-B
agent-ready stages                  = 0
next review item                    = V2H publication matrix
```
