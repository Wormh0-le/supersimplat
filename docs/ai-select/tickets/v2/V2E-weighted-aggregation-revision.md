# V2E — Weighted aggregation and target-scope revision

Status: **review-required parent envelope; not agent-ready**

Blocked by: V2B, V2D  
Blocks: V2F, V2H

## Authority

- Final Spec v2.0 §7.3 as amended by Amendment 002;
- ADR 0023;
- current immutable P/N/V and existing aggregation/Lift Readiness seams.

## Goal

Generalize the current one-shot aggregation into a bounded incremental revision over immutable single-N P/N/V Evidence, reliability weights, Core Target state, and reversible Discovery Frontier state.

## Inputs / preconditions

- current per-View `positiveMass`, `negativeMass`, `visibleMass` artifacts;
- view-level Reliability from V2D;
- Core/Envelope/Frontier state from V2B;
- consensus recurrence decisions from the joint V2C/D/E review.

## Outputs / handoff

- versioned weighted aggregate with P/N weighting only and raw V preserved;
- incremental revision equivalent to full recomputation for identical inputs;
- Selected/Rejected/Uncertain inputs for provisional consensus and eventual Candidate publication;
- Core Observation Coverage input and a separate Frontier Debt/readiness input;
- reviewed Core-promotion / Frontier-rejection handoff without direct Candidate mutation;
- exact policy and revision identities.

## Required invariants

- Missing, unusable, or excluded observations remain unobserved, never negative.
- Current single Negative Mass remains the production input; V2AX is optional diagnostics only.
- Core and Frontier are not collapsed into one denominator or one binary classification.
- Frontier membership is reversible; Core does not shrink inside one stable input revision.
- An authoritative Stable input revision may rotate/rebuild Core through a new identity rather than preserving an early error forever.
- Weighted incremental output equals full recomputation within the declared numerical tolerance.
- Lift Readiness remains the publication authority.
- v1.3 runtime behavior remains unchanged until an explicit production cutover.

## Review gates before decomposition

- exact recurrence among aggregate, consensus, reliability, and scope revision;
- whether Core promotion occurs before or after one consensus revision;
- Frontier Debt representation and aggregation inputs;
- convergence and maximum-revision semantics;
- numerical tolerance and deterministic journal/replay behavior.

## Validation families

- incremental/full equivalence;
- raw-V unchanged under reliability weighting;
- Core promotion and Frontier rejection ordering;
- revision rotation and stale dependency handling;
- confirmation-bias and seed-lock adversarial fixtures;
- production identity fail-closed tests.

## Non-goals

- No classified-N production migration, View Utility scoring, terminal publication, or Native Selection mutation.
