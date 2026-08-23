# V2E — Weighted update, component Scope Delta, and Frontier Debt

Status: **reviewed parent envelope — Q4–Q7 accepted; awaiting stage decomposition; not agent-ready**

Blocked by: V2B, V2D  
Blocks: V2F, V2H

## Authority

Final Spec Amendments 002–006; ADRs 0023–0027; immutable single-N P/N/V and Lift Readiness contracts.

## Goal

Own the canonical immutable-Evidence q/s update, convergence result, component-level post-solve Scope Delta, mandatory re-solve handoff, and structured Frontier Debt.

## Accepted update

```text
P_i = sum_c omega_c * Pbar_ic
N_i = sum_c omega_c * Nbar_ic
V_i = sum_c Vbar_ic
q_i = (a_i + P_i) / (a_i + b_i + P_i + N_i)
s_i = (1-exp(-(P_i+N_i)/tau_E)) * (1-exp(-V_i/tau_V))
```

Previous q/s is never re-added as Evidence. Reliability affects P/N only.

## Accepted scope contract

- solve binds one frozen TargetScopeState revision;
- only a converged solve may promote/retain/reject/reopen/expand;
- transitions are component-level and hysteretic;
- promotion is irreversible inside the Scope Epoch;
- rejection requires high support and persistent negative/background conclusion; low s/V cannot reject;
- rejected Frontier is not Context and reopens only on new provenance;
- material Scope Delta advances Scope Revision and forces a new canonical solve;
- pre-delta/scope-advanced output cannot feed Readiness or Candidate;
- no material delta allows structured Debt and Readiness evaluation;
- scope churn is bounded by a separate finite revision budget.

## Structured Frontier Debt

Produce component records and aggregate summaries for Unobserved, Conflict, and Promotion-pending Debt. Materiality is bounded/density-normalized and cannot be raw Gaussian count. Emit `clear/low/material/unresolved` summary with exact policy identity.

## Outputs / handoff

Weighted aggregate, q/s, convergence diagnostics, Scope Delta and digest, TargetScopeState revision, scope-advanced/current status, component Debt ledger/summary, Core Coverage input, Working Set v2 projection input, exact policy identities.

## Stage-level gates

Component policy/lineage, hysteresis, Debt materiality/status, maximum scope revisions, Selected/Rejected/Uncertain diagnostics, Working Set v2 migration, numerical tolerance, production promotion owner.

## Validation families

No double counting; raw-V invariant; convergence; component promotion/rejection/reopen; rejected-not-Context; Core monotonicity/epoch rotation; material delta mandatory re-solve; stale scope publication block; finite scope churn; density-invariant Debt; Working Set role migration.

## Non-goals

No classified-N migration, View Utility scoring, terminal publication, Native mutation, or gradient/logit optimization.
