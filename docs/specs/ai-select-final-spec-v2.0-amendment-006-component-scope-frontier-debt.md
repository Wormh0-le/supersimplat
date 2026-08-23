# AI Select Final Spec v2.0 Amendment 006 — Component-level Target Scope and structured Frontier Debt

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–005  
**Decision record:** `docs/adr/0027-adopt-component-scope-state-and-mandatory-resolve.md`

## 1. Purpose

Amendments 002–005 established a seed-independent Discovery Frontier and a frozen-scope q+s solve, but did not define how target scope changes after a converged Consensus Revision or how unresolved Frontier affects Readiness. This amendment adopts a component-level Target Scope State, structured Frontier Debt, and mandatory re-solve after every material Scope Delta.

Runtime remains the implemented v1.3 baseline until reviewed stages are calibrated and explicitly promoted.

## 2. Clarified and superseded clauses

This amendment clarifies Final Spec v2.0 §§4, 6–8 and Amendments 002–005.

The earlier phrase “Core is monotonic within one stable input revision” is narrowed to the **Scope Epoch** contract below. Adding a new observation changes canonical solve input but does not by itself permit Core shrinkage. Authoritative correction or removal of evidence may rotate the Scope Epoch and rebuild Core.

The v1.3 `EvidenceWorkingSet` Core/Context schema remains shipped history. It must not be silently reinterpreted to encode Frontier as Context.

## 3. Target Scope State

The Companion maintains a target-local derived `TargetScopeState` containing at least:

```text
scopeEpochId
scopeRevision
core components / Stable IDs
discovery-envelope ledger
active Frontier components
rejected/reopened Frontier ledger
required Context Stable IDs
component-policy and provenance digests
```

Target Scope State is not ownership, Candidate, or Native Selection.

### 3.1 Scope Epoch

A Scope Epoch is the interval in which Core is monotonic.

- Adding a new Generated or User-added observation does not rotate the epoch.
- Core may grow but does not shrink inside the epoch.
- Correcting an existing Stable Mask, changing its Included/Excluded Participation, removing/replacing an existing observation, Restarting the target, or changing incompatible target/dependency identity rotates or invalidates the epoch.
- Exact dependency restoration may reuse an earlier compatible state only when all bound identities match; lifecycle details remain a V2I gate.

### 3.2 Scope Revision

A Scope Revision is one immutable Core/Envelope/Frontier/Context snapshot inside an epoch. Every canonical solve binds one exact Scope Revision.

## 4. Component-level state

Scope transitions use deterministic, versioned spatial components as the primary decision unit. Component construction is scale-aware and records lineage when an Envelope expansion splits or merges components. A reviewed policy may create deterministic subcomponents before transition; arbitrary per-Gaussian threshold flicker is not the canonical state machine.

Active Frontier component states are:

```text
new
observing
conflicted
promotion-pending
retained
reopened
```

`rejected` components remain in a ledger and are inactive until new authoritative observation or discovery provenance reopens them.

Rejected Frontier is not automatically Context. Rejection means “not currently plausible enough to investigate,” not “proven background.”

## 5. Bounded Discovery Envelope ledger

Within one Scope Epoch, the Discovery Envelope ledger is append-only and deduplicated by exact discovery-source identity. Active Frontier membership remains reversible.

Valid seed-independent discovery sources include:

- Evidence Working Set boundary contact;
- Core-external support from a new Included Stable observation;
- coherent cross-View support;
- TargetGeometryHint-local or Target-Splat-local reviewed support;
- User Confirmed Expert Recovery observations.

Envelope growth is target-local, spatially bounded, budgeted, and provenance-recorded. Seed failure or S1 depth inconsistency cannot erase otherwise plausible Envelope support.

## 6. Promotion, retention, rejection, and reopening

### 6.1 Promotion to Core

A Frontier component or deterministic subcomponent may promote only from a converged canonical solve and versioned hysteresis requiring the policy-selected combination of:

- high q and sufficient s;
- adequate raw visibility;
- acceptable P/N conflict;
- coherent support from independent observation directions;
- reviewed spatial/connectivity conditions;
- stability across complete Consensus Revisions.

User Confirmed/manual observations are stronger semantic provenance and may reduce an automatic multi-View requirement, but they do not bypass Stable identity, visibility, component coherence, Candidate publication, or Native Selection authority.

Promotion is irreversible inside the current Scope Epoch.

### 6.2 Retention

Low support, low visibility, recent discovery, or unresolved conflict retains a component in active Frontier. “Not yet observed” is never a rejection reason.

### 6.3 Rejection

Rejection requires high enough support to make a persistent background/negative conclusion, no material positive support, and a versioned hysteresis condition. Low s, low V, insufficient comparison support, or a failed S1 depth score cannot reject a component.

A rejected component may reopen only after a new authoritative observation or discovery-source digest. It cannot oscillate between rejected and active on unchanged inputs.

## 7. Scope Delta

After a complete converged Consensus Revision, the Companion may derive:

```text
ScopeDelta
  promoteToCore[]
  retainFrontier[]
  rejectFrontier[]
  expandEnvelope[]
  reopenFrontier[]
  reasons / provenance / policy digest
```

Core, Envelope, and Frontier remain frozen throughout the solve. A non-converged or oscillating solve may publish diagnostics but cannot mutate scope.

### 7.1 Empty delta

When no material Scope Delta exists, the converged revision may proceed to Frontier Debt, Lift Readiness, View Utility, and terminal evaluation.

### 7.2 Material delta and mandatory re-solve

When a material Scope Delta exists:

1. commit a new Scope Revision atomically;
2. mark the just-completed Consensus result `scope-advanced` and publication-ineligible;
3. run a new canonical solve bound to the new Scope Revision;
4. compute Readiness and Candidate eligibility only from a converged result whose Scope Revision remains current and yields no further material delta.

A Candidate may never combine q/s solved under one scope with Core/Frontier semantics from another.

## 8. Bounded scope churn

Solver Iterations, Scope Revisions, and acquisition/View iterations are distinct counters.

Every acquisition attempt has a finite `maximumScopeRevisions`. The same discovery-source digest cannot expand twice; promotion is irreversible within the epoch; rejection cannot reopen without new provenance.

If the Scope Revision budget is exhausted while material churn remains:

```text
result = Limited
reason = scope-revision-budget-exhausted
automatic Candidate publication = forbidden
```

Whether an explicitly consented Limited Candidate may later publish remains a V2H decision.

## 9. Structured Frontier Debt

Frontier Debt is component-level derived state, not Gaussian count and not one opaque scalar.

It records at least:

```text
totalDebt
maximumComponentDebt
activeComponentCount
unobservedDebt
conflictDebt
promotionPendingDebt
component records
```

Each component record binds:

- component and lineage identity;
- bounded density-normalized materiality;
- discovery provenance;
- q/s and raw visibility summaries;
- positive/negative supporting Views;
- current state, age, reasons, and component debt.

Primary debt families are:

- **Unobserved Debt:** plausible material support lacks adequate visibility/knownness;
- **Conflict Debt:** support is observed but semantic evidence remains materially inconsistent;
- **Promotion-pending Debt:** evidence is strong but hysteresis or independent confirmation is incomplete.

A component materiality function may combine bounded opacity/Gaussian mass, visible/projected support, extent, and target-local relevance. Raw Gaussian count alone is invalid; each component is capped to prevent density from dominating.

A versioned summary maps structured debt to `clear / low / material / unresolved`. Exact functions and thresholds are calibration-owned.

## 10. Readiness integration

High Core Observation Coverage cannot hide material Frontier Debt.

Conceptually:

```text
Ready
= sufficient Core Coverage
+ sufficient View Diversity
+ Frontier Debt clear/low
+ no high-value feasible View
+ complete current identities
```

Material or unresolved high-priority Debt blocks Ready. Depending on Core quality, remaining Utility, and terminal budget state, it contributes to Limited or Not Ready. Exact threshold and terminal matrices remain V2G/V2H work.

## 11. Working Set migration

`TargetScopeState` is the semantic scope authority. A future `EvidenceWorkingSet v2` is a projection bound to the exact Scope Epoch/Revision:

```text
Evidence write IDs
= Core
∪ active Frontier
∪ required Context
```

Roles remain explicit; Frontier is never encoded as Context. The Render Working Set continues to preserve complete-scene occlusion, transmittance, and termination.

The implemented v1 EvidenceWorkingSet remains unchanged until an explicit migration stage rotates schema, policy, consumers, and production identity.

## 12. Validation

Later stages must cover:

- deterministic componentization and split/merge lineage;
- promotion/rejection hysteresis and User Confirmed provenance;
- rejection is not Context and can reopen only on new evidence;
- Core monotonicity within an epoch and rebuild on epoch rotation;
- material Scope Delta always forces a new canonical solve;
- no Candidate from a stale or scope-advanced result;
- finite Scope Revision budget and churn diagnostics;
- density-invariant component Debt;
- Unobserved/Conflict/Promotion-pending Debt behavior;
- Working Set v2 role and identity migration.

## 13. Remaining review gates

This amendment does not choose component thresholds, adjacency constants, materiality weights, debt thresholds, or budget numbers. V2F must define how View Utility consumes structured Debt; V2G/V2I must define budget and orchestration identities; V2H must close the terminal publication matrix; calibration and production promotion still require explicit owners.
