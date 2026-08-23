# V2I — Browser loop orchestration, identities, and replay

Status: **review-required parent envelope; not agent-ready**

Blocked by: V2F, V2G  
Blocks: V2J

## Goal

Generalize the serial View pipeline into Browser-driven bounded acquisition over validated requests while coordinating View acquisition, canonical Consensus solves, material Scope Delta re-solves, budgets, cancellation, suspension, and deterministic journals.

## Required behavior

- no autonomous Companion product session or new transport;
- every request independently validates target, dependency, observation set, Scope Epoch/Revision, policy, and attempt identity;
- material Scope Delta commits a new Scope Revision and schedules a subsequent canonical solve before Utility/Readiness/publication;
- Scope Revision, Consensus Revision, Solver Iteration, acquisition iteration, and endpoint attempt IDs remain distinct;
- finite scope-revision budget is enforced by V2G semantics;
- Cancel immediately prevents later publication while process/GPU interruption remains best effort;
- completed Views/Masks/raw Evidence/prior Candidate remain inspectable;
- stale or late results cannot attach to a newer scope or dependency;
- Continue Acquisition is a fresh bounded attempt, not replay.

## Review gates

Identity hierarchy; journal lifetime; canonical replay versus wall-clock variation; scope-advanced scheduling; suspend/resume boundaries; continuation budget/identity; late-result handling.

## Validation families

Scope-delta re-solve state machine; budget/stop/cancel/suspend paths; stale scope rejection; replay determinism; existing generated-view regressions.

## Non-goals

No UI controls, publication policy, or Utility/budget math.
