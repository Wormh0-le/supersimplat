# V2G — View, cost, and scope-revision budgets; failure and termination

Status: **review-required parent envelope; not agent-ready**

Blocked by: V2F  
Blocks: V2H, V2I

## Goal

Define bounded acquisition over three distinct resources: successful View count, deterministic acquisition cost, and Scope Revision churn, plus failure/replacement and stop semantics.

## Accepted inputs

- View Utility and candidate pool;
- Lift Readiness and structured Frontier Debt;
- Q7 finite `maximumScopeRevisions` requirement;
- failure and stop-reason families.

## Required behavior

- Solver Iterations, Scope Revisions, and View acquisitions are distinct counters;
- either View or cost budget exhaustion stops new acquisition;
- material Scope Delta may trigger re-solve only while the scope-revision budget remains;
- exhaustion with material scope churn produces Limited `scope-revision-budget-exhausted` and forbids automatic Candidate publication;
- failed Views do not consume successful-View budget, but their measured/deterministic cost and failure caps remain explicit;
- Ready alone does not stop while calibrated marginal gain remains material;
- fixed-four remains regression baseline only.

## Review gates

Outcome taxonomy; deterministic cost units versus wall-clock diagnostics; continuation budget reset; replacement/circuit breaker; interactions among View, cost, and scope budgets; complete stop-reason names and handoff to V2H/V2I.

## Validation families

Each budget exhaustion; scope churn cap; failed/replacement sequence; tightened marginal gain; deterministic stop reasons; continuation budget interaction.

## Non-goals

No Candidate publication UI or numeric calibration values.
