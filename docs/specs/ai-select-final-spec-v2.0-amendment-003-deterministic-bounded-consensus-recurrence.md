# AI Select Final Spec v2.0 Amendment 003 — Deterministic bounded consensus recurrence

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001 and 002  
**Decision record:** `docs/adr/0024-deterministic-bounded-consensus-recurrence.md`

## 1. Purpose

Final Spec v2.0 introduced Provisional 3D Consensus, Observation Reliability, and weighted aggregation, but did not define their recurrence. This amendment adopts a continuous, deterministic, bounded batch solve over the exact current Included Stable observation set.

The solve is Companion-local derived computation. It does not create ownership, Candidate authority, or Native Selection authority.

## 2. Clarified clauses

This amendment clarifies Final Spec v2.0 §§5 and 7.1–7.3 and the V2C/V2D/V2E parent envelopes.

The phrase “one revision per Included publication” means one **public atomic Consensus Revision**. That revision may contain multiple private bounded Solver Iterations.

Amendments 001 and 002 remain current. Current production remains the implemented v1.3 runtime until explicit reviewed cutover stages land.

## 3. Consensus state

For every Stable Gaussian ID in the frozen solve scope, Provisional Consensus maintains:

- `q_i ∈ [0,1]`: continuous membership tendency;
- `s_i ∈ [0,1]`: support/knownness;
- one exact scope binding identifying Core, Frontier, Context, or Out-of-Scope membership for the solve.

`q_i` is not a calibrated probability and is never Candidate membership by itself.

`s_i` distinguishes cases that one scalar cannot:

```text
q≈0.5, low s  = unknown / weakly observed
q≈0.5, high s = materially conflicting evidence
```

Raw per-View P/N/V Evidence remains immutable.

## 4. Canonical solve input

One canonical solve binds the exact current:

- target and dependency identity;
- stable input revision;
- Included Stable View set and artifact digests;
- immutable per-View P/N/V;
- Seed prior identity;
- frozen Core / Discovery Envelope / Frontier revision;
- consensus, reliability, and aggregation policy identities.

The input set is canonicalized independently of View arrival order. Equal canonical inputs must produce equivalent canonical outputs within the declared numerical tolerance.

## 5. Initialization

The initial state `(q^(0), s^(0))` is derived from:

- a finite, weak Conservative Seed prior;
- a uniform-weight aggregate over the complete current Included Evidence set;
- neutral, low-support initialization for plausible Frontier or otherwise unknown support.

The Seed prior must not overpower increasing real Evidence. Exact prior strengths and transforms are calibration-owned and remain review/decomposition inputs.

Warm-up may use uniform observation reliability. User Confirmed/manual observation authority remains preserved.

## 6. Bounded recurrence

For Solver Iteration `r ≥ 1`:

1. render the consensus readout from `(q^(r-1), s^(r-1))` under each Included View;
2. compute Observation Reliability from that lagged state only;
3. aggregate immutable P/N using the iteration reliability weights while preserving raw V unweighted;
4. update `(q^(r), s^(r))` from the weighted aggregate and the finite prior.

Same-iteration feedback is forbidden:

```text
ω^(r) may consume q^(r-1), s^(r-1)
ω^(r) may not consume q^(r), s^(r)
```

The exact readout, residual equation, q/s transform, convergence metric, thresholds, and maximum iteration count remain calibration- or later-review-owned. They must be finite, versioned, deterministic, and bounded.

## 7. Public revision and atomicity

A new Included Stable observation, Stable Mask revision, Participation change, or authoritative input revision may request one new Consensus Revision.

The previous complete revision remains current until the bounded solve finishes. Partial Solver Iterations are never published as current state.

A complete revision records at least:

- canonical input digest;
- policy identities;
- iteration count;
- convergence status;
- q/s output digest;
- frozen scope revision;
- derived scope-delta digest, when present.

Consensus arrays remain Companion-local and do not become a Browser protocol artifact.

## 8. Scope freeze and two-phase commit

Core, Discovery Envelope, and Frontier are frozen throughout one canonical solve.

After the solve ends, the final q/s state and current immutable Evidence may derive a proposed scope delta:

- Frontier promotion to Core;
- Frontier retention;
- Frontier rejection;
- Discovery Envelope expansion.

The scope delta commits atomically after the Consensus Revision. Newly committed scope does not trigger another solve inside the same revision; it becomes input to the next acquisition or explicit recomputation.

Core remains monotonic only inside one stable input revision. Frontier remains reversible.

## 9. Incremental optimization

Warm starts, cached per-View terms, and incremental aggregation are performance optimizations only.

For the same canonical input, an incremental solve must agree with a cold canonical full solve within a declared tolerance. A material mismatch fails closed; arrival order or cache history must not define product semantics.

## 10. Non-convergence

If the bounded solve reaches its maximum iteration count without satisfying the convergence contract:

- publish a `non-converged` / Limited diagnostic result, not a Ready consensus;
- do not publish or replace Candidate from that result;
- preserve all valid Views, Stable Masks, raw Evidence, and the prior inspectable Candidate;
- allow further automatic acquisition, Mask correction, or Expert Recovery;
- never silently use the final oscillating iteration as production truth.

## 11. Product and authority boundaries

Provisional Consensus:

- is Companion-local, disposable, target-local derived state;
- may inform Reliability, weighted aggregation, Frontier/Core proposals, View Utility, and Lift Readiness;
- never mutates Stable Mask, Participation, Candidate, Native Selection, or EditHistory;
- never replaces raw P/N/V or raw V as observation truth.

## 12. Remaining review gates

Before V2C/V2D/V2E decomposition, later review must close:

- the same-decision soft-mask / trust / Frontier readout;
- residual support and visibility gating;
- exact q/s initialization and update transforms;
- convergence metric and numerical tolerance;
- robust residual normalization and degenerate-view handling;
- promotion/rejection thresholds and release calibration ownership.

## 13. Non-goals

This amendment does not:

- choose production numerical thresholds;
- adopt leave-one-out reliability as the production path;
- make per-pixel or region reliability product scope;
- change the current one-channel Negative Mass decision;
- publish Consensus to the Browser;
- change Candidate or Native Selection authority.
