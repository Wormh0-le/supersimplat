# AI Select Final Spec v2.0 Amendment 008 — Hierarchical acquisition identity, deterministic budgets, and Browser Decision Journal

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–007  
**Decision record:** `docs/adr/0029-adopt-browser-journal-and-layered-acquisition-identities.md`

## 1. Purpose

The amended v2 architecture now defines adaptive View selection, iterative Consensus, Scope Revision, and Expert Recovery. The original phrases “whole loop = one attempt” and “failed Views are free” are insufficient for that system. This amendment adopts:

- hierarchical acquisition identities that preserve existing endpoint attempt IDs;
- a Browser-owned append-only Decision Journal;
- deterministic multi-dimensional budget ledgers;
- an exact distinction among replay, fresh retry, replacement, resume, and Continue Acquisition;
- fail-closed Cancel/Suspend semantics without a Companion-autonomous product session.

Runtime remains the implemented v1.3 baseline until reviewed stages are calibrated and explicitly promoted.

## 2. Superseded and clarified clauses

This amendment supersedes conflicting V2G/V2I language that treated the complete acquisition loop as one flat attempt or described a failed View as consuming no budget of any kind.

The valid meaning is:

```text
one target-local Acquisition Series
contains one initial Acquisition Attempt
and zero or more fresh Continue Acquisition Attempts
```

Existing geometry, plan, probe, render, Prompt, Mask, review, publication, Evidence, Consensus, and Scope identities remain distinct. They must not be collapsed into one loop ID.

## 3. Runtime authority

The Browser remains the product-loop authority. It:

- commits the next acquisition decision;
- owns the attempt/iteration budget ledger;
- maintains the target-local Decision Journal;
- decides whether a result is current, replayed, stale, cancelled, suspended, or terminal;
- invokes independently validated Companion endpoints.

The Companion may own idempotency caches, ViewUtilityProbe results, q/s state, Consensus/Scope caches, and other disposable derived state. It does not run an autonomous product session and does not choose the next product action without a Browser request.

## 4. Identity hierarchy

The canonical hierarchy is:

```text
TargetContextId + exact DependencyToken
└── AcquisitionSeriesId
    ├── AcquisitionAttemptId
    │   ├── AcquisitionIterationId
    │   │   ├── UtilityDecisionId
    │   │   ├── ProbeAttemptId[]
    │   │   ├── selected View identity
    │   │   └── endpoint attempt IDs
    │   │       ├── RenderAttemptId
    │   │       ├── PromptSynthesisAttemptId
    │   │       ├── MaskAttemptId
    │   │       ├── ReviewAttemptId
    │   │       ├── MaskPublicationAttemptId
    │   │       └── EvidenceAttemptId
    │   ├── ConsensusRevisionId[]
    │   └── ScopeRevisionId[]
    └── later Continue Acquisition Attempts
```

### 4.1 Acquisition Series

A Series binds one target/dependency lineage and the cumulative safety cap for the initial attempt plus all continuations. Restart, a new Current Target Context, or an incompatible dependency identity terminates or invalidates the Series.

### 4.2 Acquisition Attempt

The initial automatic run and every Continue Acquisition action create separate Attempts. Continue Acquisition is not same-attempt replay, endpoint retry, resume, or a persistent Generate More control.

### 4.3 Acquisition Iteration

One Iteration binds one canonical planning state, one committed utility ranking, one selected candidate, its formal acquisition pipeline, and the resulting Consensus/Scope/Readiness work. A material Scope Delta may require multiple canonical Consensus solves inside the same View Iteration; those solves are Scope/Consensus revisions, not additional observations.

### 4.4 Existing endpoint identities

Existing endpoint attempt IDs remain independently validated and idempotent. Reusing one endpoint attempt ID means replay; issuing a new endpoint attempt ID means fresh work.

## 5. Browser-owned append-only Decision Journal

Each Acquisition Attempt owns one append-only, digest-chained journal. It is target-local product state for the active session, not a semantic-object database. Browser-reload persistence is not required unless a later explicit recovery feature adopts it.

Canonical entry families include:

```text
AttemptStarted
BudgetSnapshotBound
IterationStarted
CandidatePoolBound
ProbeShortlistBound
UtilityRankingCommitted
CandidateSelected
BudgetDebited
EndpointRequestCommitted
EndpointOutcomeCommitted
ObservationPublished
ConsensusRevisionCommitted
ScopeRevisionCommitted
IterationCompleted
AttemptSuspended
AttemptResumed
AttemptTerminated
```

Each entry binds at least:

- monotonic journal ordinal;
- previous-entry digest and entry digest;
- exact target, dependency, Series, Attempt, and Iteration identities;
- relevant artifact and policy digests;
- budget state before and after the decision;
- request/result digest and decision reason where applicable.

A decision is committed before subsequent work may redefine it. Companion cache state or GPU load cannot silently rewrite the committed candidate ordering.

## 6. Deterministic budget ledger

One Attempt has versioned finite ledgers for at least:

1. **Successful Observation Budget** — consumed only when a current Included Stable Mask and current Direct Evidence form a usable observation;
2. **Selected Candidate Attempt Budget** — consumed when a winning candidate begins formal full-resolution acquisition;
3. **Deterministic Cost Budget** — consumed by versioned cost units for probes, formal acquisition, SAM, Evidence, Consensus solves, and mandatory Scope re-solves;
4. **Replacement/Failure Budget** — bounds same-stage failures, fresh retries, and candidate replacement;
5. **Scope Revision Budget** — bounds material Scope churn as adopted by Amendment 006.

The Acquisition Series also owns finite cumulative caps, including continuation count and cumulative deterministic cost/resource allowance. Exact values are calibration-owned.

### 6.1 Failed work

A failed or Excluded View does not consume Successful Observation Budget, but it does consume the selected-candidate, deterministic-cost, and applicable failure/replacement ledgers. Therefore technical failure does not steal a valid-observation slot and is never free unlimited work.

### 6.2 Cost authority

Canonical ranking and termination consume deterministic cost units derived from versioned inputs such as probe class, resolution, Render Working Set size, tile/intersection work class, SAM resolution class, and solve/scope revision class.

Measured wall-clock latency, GPU load, and cache hits are telemetry and operational-safety inputs only. They may trigger an explicit timeout/cancel/failure outcome, but they do not reorder candidates or alter a replayed canonical budget decision.

## 7. Replay, fresh retry, and replacement

### 7.1 Same-attempt replay

The same Attempt, journal state, endpoint attempt ID, and request identity replay an already committed decision or result. Replay:

- does not regenerate the candidate pool or utility ranking;
- does not debit budget again;
- does not consult new wall-clock measurements for canonical policy;
- returns the recorded result when available.

If an exact derived result must be recomputed after a Companion restart, its digest must match the journal-bound expected identity. A mismatch is `replay-conflict` or stale failure, never a silently accepted new result.

### 7.2 Fresh retry

A fresh retry uses a new endpoint attempt ID and consumes the relevant retry/failure and deterministic-cost ledgers. It cannot masquerade as replay.

### 7.3 Candidate replacement

When the selected candidate fails and policy permits replacement, the next candidate comes from the already committed ranking for that Iteration. Replacement does not rerun utility scoring against transient runtime conditions. A new ranking requires a new Iteration or a new canonical planning state.

## 8. Observation and terminal outcome taxonomy

Iteration outcomes include at least:

```text
observation-ready
observation-excluded
probe-failed
render-failed
mask-unavailable
mask-failed
evidence-failed
consensus-non-converged
scope-advanced
```

Terminal outcomes include at least:

```text
ready-low-gain
marginal-gain-exhausted
successful-observation-budget-exhausted
candidate-attempt-budget-exhausted
deterministic-cost-budget-exhausted
scope-revision-budget-exhausted
no-feasible-view
failure-circuit-open
cancelled
suspended
stale
```

`scope-advanced` is not a publication terminal. It requires the mandatory canonical re-solve from Amendment 006 unless the Scope Revision budget is exhausted. The mapping from Readiness plus terminal outcome to Candidate publication remains Amendment/V2H review work.

## 9. Cancel

Cancel appends a terminal journal entry and closes the Attempt publication gate immediately. Any later in-flight result is discarded as non-current even if the GPU/process cannot be interrupted.

Completed current Views, Stable Masks, raw Evidence, Scope/Consensus revisions, and the prior inspectable Candidate remain preserved. A later Add Observation or Continue Acquisition creates fresh work; it never resumes the cancelled Attempt.

## 10. Suspend and exact resume

Suspension changes product authority immediately and resumes, if allowed, only from the last complete journal boundary. In-flight late results are discarded.

The same Attempt may resume only when exact dependency, target, policy, journal, Scope, and Consensus identities remain compatible and no authoritative observation correction invalidated the epoch. It reuses the remaining Attempt budget.

If compatibility is not exact, the old Attempt becomes stale. Further automation requires a fresh Continue Acquisition Attempt under a compatible current Series or a new Series after identity rotation.

## 11. Continue Acquisition

Continue Acquisition creates a fresh Attempt inside the current Acquisition Series.

It resets versioned per-Attempt allowances, including observation, candidate/replacement, failure, cost, and Scope Revision allowances. It does not reset:

- Series cumulative caps or continuation count;
- current Stable Views, Participation, and raw Evidence;
- TargetScopeState, Core/Frontier, and discovery ledger;
- current complete Consensus/Scope identities;
- prior Candidate and its current/stale status;
- prior attempted/discovered candidate provenance.

Starting a continuation does not by itself change Candidate identity. A new Stable observation, material Scope change, or other bound input change applies the existing stale rules.

## 12. Validation

Later stages must cover:

- hierarchy and exact identity binding;
- append-only hash-chain validation and journal conflict handling;
- replay versus fresh retry budget behavior;
- committed ranking replacement without reranking;
- failed-work budget matrix and failure circuit;
- deterministic cost independence from wall-clock/cache state;
- Cancel late-result rejection;
- exact Suspend/Resume and incompatible stale paths;
- Continue per-Attempt reset with Series cumulative cap;
- Scope/Consensus revision accounting distinct from View Iterations;
- preservation of v1.3 endpoint idempotency and generated-view-controller regressions.

## 13. Remaining review gates

This amendment does not choose numeric budgets, cost-unit coefficients, persistence beyond the active Browser session, or the Readiness × terminal-outcome Candidate publication matrix. V2H must close publication and explicit Limited consent; V2J must close presentation and recovery availability; calibration and production promotion still require explicit owners.
