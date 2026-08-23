# V2G — Deterministic budgets, outcomes, failure circuit, and termination

Status: **reviewed parent envelope — Q9-B accepted; awaiting decomposition; not agent-ready**

Blocked by: V2F  
Blocks: V2H, V2I

## Authority

Final Spec Amendments 006–008; ADRs 0027–0029; Lift Readiness remains separate publication authority.

## Goal

Own the deterministic budget ledger, structured iteration/terminal outcomes, replacement/failure circuit, and bounded termination used by Browser orchestration.

## Accepted budget model

Per Attempt:

- Successful Observation Budget;
- Selected Candidate Attempt Budget;
- Deterministic Cost Budget;
- Replacement/Failure Budget;
- Scope Revision Budget.

Per Series:

- cumulative deterministic resource cap;
- finite continuation count and other calibrated hard caps.

A failed/Excluded View consumes no Successful Observation slot but consumes applicable candidate-attempt, cost, and failure/replacement budgets. Replay consumes no new budget; fresh retry does.

## Accepted deterministic behavior

- wall-clock/cache state is telemetry and operational safety, not canonical cost/ranking;
- replacement follows the already committed utility ranking;
- all ledgers and transitions are journal-bound and finite;
- scope-advanced requires mandatory re-solve unless Scope Revision budget ends the Attempt;
- fixed-four remains an ablation baseline, never fallback.

## Outcome families

Iteration: observation-ready/excluded, probe/render/mask/Evidence failures, consensus-non-converged, scope-advanced.

Terminal: ready-low-gain, marginal-gain-exhausted, observation/candidate/cost/scope budget exhausted, no-feasible-view, failure-circuit-open, cancelled, suspended, stale.

## Remaining gates before decomposition

- numeric budget and deterministic cost-unit calibration;
- exact failure-stage grouping and circuit thresholds;
- Q10 Readiness × terminal-outcome publication matrix;
- Continue Series-cap presentation shared with V2J;
- production identity and release calibration owner.

## Validation families

Budget transition table; replay/no-debit; fresh retry/debit; failed-work matrix; committed-ranking replacement; deterministic cost versus wall-clock variation; failure circuit; Series continuation caps; structured stop reasons.

## Non-goals

No Candidate publication policy, UI, or Companion-autonomous session.
