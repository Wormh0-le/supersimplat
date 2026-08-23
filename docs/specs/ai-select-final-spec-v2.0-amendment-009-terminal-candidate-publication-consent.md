# AI Select Final Spec v2.0 Amendment 009 — Terminal Candidate publication and explicit consent

**Status:** Current normative amendment / accepted 2026-08-23  
**Applies to:** Final Spec v2.0 with Amendments 001–008  
**Decision record:** `docs/adr/0030-adopt-two-gate-candidate-publication.md`

## 1. Purpose

The amended v2 architecture now distinguishes normal success, forced terminal boundaries, cancellation, non-convergence, Scope advancement, and stale/suspended lifecycle states. Readiness alone is therefore insufficient to decide whether a new Candidate may publish.

This amendment adopts a two-gate publication model:

```text
Publication Eligibility
        +
Readiness × Terminal Outcome × Consent Class
        ↓
Candidate publication decision
```

It preserves automatic atomic publication at the normal `ready-low-gain` terminal, introduces explicit `Use Ready Candidate` and `Use Limited Candidate` actions for eligible non-normal terminals, separates those consent actions from Re-Lift, and forbids publication from incompatible or incomplete results.

Runtime remains the implemented v1.3 baseline until reviewed stages are calibrated and explicitly promoted.

## 2. Superseded and clarified clauses

This amendment preserves ADR 0020's normal-success auto-publication and manual Native Selection boundary, but supersedes the clauses that required every non-`ready-low-gain` result to publish nothing/readiness-only or used Re-Lift as the sole way to accept an already-computed Limited result.

The following remain unchanged:

- Candidate publication is atomic and identity-bound;
- Candidate never self-applies Native Selection;
- Set/Add/Remove/Intersect remain explicit user actions;
- the prior Candidate is preserved until an eligible replacement commits;
- Lift Readiness remains the quality authority;
- Re-Lift never starts or resumes automatic acquisition.

## 3. Candidate Publication Snapshot

A `CandidatePublicationSnapshot` is one immutable, target-local derived snapshot that binds at least:

- exact target context and dependency identity;
- exact current Included Stable observation set and artifact digests;
- immutable production Direct Evidence set and aggregation identity;
- one complete converged Consensus Revision;
- the exact current Scope Epoch and Scope Revision;
- proof that no material Scope Delta remains pending;
- current Lift Readiness and structured Frontier Debt;
- terminal outcome and Acquisition Attempt/Journal identity;
- complete production Runtime Profile / Candidate identity inputs.

A snapshot is not yet a Candidate. It is the only input from which automatic or explicit terminal publication may occur.

## 4. Publication Eligibility Gate

A snapshot is `publication-eligible` only when all of the following hold:

```text
exact current target/dependency identity
AND exact current Stable observation/Evidence set
AND converged, non-oscillating Consensus
AND current Scope Revision
AND no material Scope Delta pending
AND current aggregation/readiness/policy identities
AND complete production identity
AND not stale
AND not suspended
AND not a partial or late result
```

The following are publication-ineligible regardless of any previously computed Readiness label:

- `scope-advanced` result awaiting the mandatory re-solve;
- Scope Revision budget exhaustion while a material Scope Delta remains;
- non-converged or period-two oscillating Consensus;
- stale or incompatible target/dependency/policy identity;
- Suspended target without exact restoration;
- incomplete Evidence, aggregation, readiness, or production identity;
- partial Solver Iterations or in-flight endpoint results;
- a late result arriving after Cancel or a newer journal state.

Publication ineligibility never destroys independently valid Views, Stable Masks, raw Evidence, prior Scope/Consensus revisions, or the prior inspectable Candidate.

## 5. Consent classes

An eligible snapshot receives exactly one publication consent class:

```text
auto-ready
explicit-ready
explicit-limited
forbidden
```

### 5.1 `auto-ready`

Only a publication-eligible `Ready + ready-low-gain` normal-success terminal receives `auto-ready`.

The Candidate publishes automatically and atomically. It remains inspectable and never executes a Native Selection operation by itself.

### 5.2 `explicit-ready`

A publication-eligible `Ready` snapshot produced by a forced or abnormal terminal requires `Use Ready Candidate`.

Eligible forced terminals include, when a current snapshot exists:

- Successful Observation Budget exhausted;
- Selected Candidate Attempt Budget exhausted;
- Deterministic Cost Budget exhausted;
- no feasible View;
- failure circuit open;
- user Cancel after a complete snapshot was committed.

The explicit action publishes the bound snapshot without rerunning View Utility, Consensus, or Re-Lift.

### 5.3 `explicit-limited`

A publication-eligible `Limited` snapshot may be accepted only through `Use Limited Candidate`.

Eligible terminal families include:

- marginal gain exhausted before Ready;
- budget exhaustion;
- no feasible View;
- failure circuit open;
- user Cancel after a complete Limited snapshot was committed.

The action is explicit acceptance of the current Limited-quality result. It does not imply that the result is Ready and does not apply Native Selection.

### 5.4 `forbidden`

Publication is forbidden for:

- `Not Ready`;
- any publication-ineligible snapshot;
- stale, Suspended, scope-advanced, non-converged, oscillating, or incomplete results;
- Scope Revision budget exhaustion with unresolved material Scope change.

No user action may bypass this gate.

## 6. Canonical publication matrix

| Readiness / state | Terminal outcome | Publication behavior |
|---|---|---|
| Ready | `ready-low-gain` | automatic atomic publication |
| Ready | eligible budget/no-feasible/failure terminal | explicit `Use Ready Candidate` |
| Ready | Cancel with an eligible pre-Cancel snapshot | explicit `Use Ready Candidate` after terminal |
| Limited | marginal-gain/budget/no-feasible/failure terminal | explicit `Use Limited Candidate` |
| Limited | Cancel with an eligible pre-Cancel snapshot | explicit `Use Limited Candidate` after terminal |
| Not Ready | any terminal | no Candidate publication |
| any | scope-advanced / material Scope Delta pending | mandatory re-solve; no publication |
| any | Scope Revision budget exhausted with material delta | no publication |
| any | non-converged / oscillating | no publication |
| any | stale / incompatible | no publication |
| any | Suspended | no publication until exact restoration and reevaluation |

`Ready + marginal-gain-exhausted` is not a second normal-success state. A valid policy must normalize it to `ready-low-gain`; otherwise it is a policy/configuration error and fails closed.

## 7. Explicit publication attempts

`Use Ready Candidate` and `Use Limited Candidate` create a new `CandidatePublicationAttemptId` bound to the immutable snapshot. They do not reopen a cancelled Acquisition Attempt, consume a new View budget, or rerun the solver.

The Browser records the explicit request/result and snapshot digest before atomic Candidate replacement. Replaying the same publication attempt is idempotent; a new snapshot requires a new publication attempt identity.

The labels are product semantics, not aliases for Re-Lift.

## 8. Re-Lift semantics

Re-Lift remains a fresh computation over exact current Stable inputs. It is not the action for accepting an already-computed terminal snapshot and it never starts automatic acquisition.

- If an explicit Re-Lift produces a publication-eligible Ready result, it may atomically publish a Candidate as the user-requested recomputation result.
- If it produces Limited, publication still requires a distinct `Use Limited Candidate` action.
- If it produces Not Ready or an ineligible result, no Candidate publishes.

Thus Re-Lift means **recompute**, while `Use Ready/Limited Candidate` means **accept the already-computed snapshot**.

## 9. Prior Candidate and application gate

A prior Candidate remains inspectable until atomically replaced or made stale by a bound input change.

Starting an Acquisition Attempt or Continue Acquisition does not by itself stale the prior Candidate. While any Acquisition Attempt is running:

```text
Candidate inspection = allowed
Set/Add/Remove/Intersect from AI Candidate = temporarily blocked
```

This prevents a Native application from racing with an asynchronous Candidate replacement. To apply a still-current prior Candidate, the user may Cancel the running Attempt; application becomes available again if no intervening input change made the Candidate stale.

A new Stable observation, Participation correction, material Scope change, or other Candidate-bound input change applies the existing stale rules.

## 10. Cancel, Suspend, and Continue

- Cancel immediately closes the current Acquisition Attempt's automatic publication gate and rejects late results.
- A complete eligible snapshot committed before Cancel may later be used through a fresh explicit Candidate Publication Attempt.
- Suspend never creates a new Candidate. Exact restoration must reestablish compatible current identities before publication or application.
- Continue Acquisition starts a fresh Acquisition Attempt under Amendment 008. It preserves the prior Candidate identity until a bound input changes, but temporarily closes Candidate application while running.

## 11. Atomicity and failure

Automatic and explicit publication use the same production Candidate contract:

- exact production Direct Evidence and checksum-bound identities;
- all-or-nothing Candidate replacement;
- no partial membership publication;
- prior Candidate preserved on failure;
- stale or mismatched result rejected;
- no automatic Native Selection operation.

## 12. Validation

Later implementation stages must cover:

- the complete matrix above;
- eligibility failure for scope-advanced/non-converged/stale/Suspended results;
- automatic Ready-low-gain publication;
- explicit Ready and Limited snapshot publication without recomputation;
- idempotent Candidate Publication Attempt replay;
- Cancel with and without a committed eligible snapshot;
- Re-Lift Ready versus Limited behavior;
- prior Candidate inspection and temporary application blocking while acquisition runs;
- atomic replacement/failure preservation;
- policy-error normalization for `Ready + marginal-gain-exhausted`.

## 13. Remaining review gates

V2J must define the progressive-disclosure UI, action availability, labels, Candidate/current/stale presentation, and Expert Recovery layout. Numeric quality thresholds remain calibration-owned. Policy freeze, production promotion, cutover, and release qualification still require explicit graph owners.

## 14. Non-goals

This amendment does not:

- auto-apply Native Selection;
- publish Not Ready or incompatible results;
- turn Cancel into resume;
- make Re-Lift a continuation control;
- expose internal Consensus, Frontier, or Utility maps by default;
- choose production calibration values.