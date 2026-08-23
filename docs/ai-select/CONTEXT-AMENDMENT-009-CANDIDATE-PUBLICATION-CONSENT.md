# AI Select Context Amendment 009 — Candidate publication and consent

Status: **current vocabulary overlay**  
Applies after Context Amendments 008→001 and before conflicting root `CONTEXT.md` definitions.

## Candidate Publication Snapshot

An immutable, exact-identity result binding the current Stable observations, production Evidence, converged Consensus, current scope, Readiness, terminal outcome, and production identity. It is eligible input to publication but is not itself a Candidate.

## Publication Eligibility

The fail-closed gate requiring current compatible identity, converged non-oscillating Consensus, current scope with no pending material delta, complete Evidence/readiness/production identity, and no stale/Suspended/late state.

## Automatic Candidate Publication

Atomic publication performed only for a publication-eligible `Ready + ready-low-gain` normal-success terminal. It never applies Native Selection.

## Use Ready Candidate

An explicit user action that atomically publishes an already-computed publication-eligible Ready snapshot from a forced or cancelled terminal. It does not recompute.

## Use Limited Candidate

An explicit user action that atomically publishes an already-computed publication-eligible Limited snapshot. It is explicit consent to Limited quality and does not recompute or apply Native Selection.

## Candidate Publication Attempt

The idempotent target-local attempt identity used by automatic or explicit Candidate replacement. An explicit publication after Cancel does not reopen the cancelled Acquisition Attempt.

## Re-Lift

A user-requested recomputation over exact current Stable inputs. It is not Continue Acquisition and is not the action for accepting an existing terminal snapshot. Ready may publish from the explicit recomputation; Limited requires `Use Limited Candidate`.

## Candidate Application Gate

The product gate controlling whether Set/Add/Remove/Intersect may consume the current AI Candidate. It is temporarily closed while an Acquisition Attempt runs and permanently closed for stale Candidates. Closing it does not itself change Candidate identity.

## Prior Candidate

The last atomically published Candidate. It remains inspectable until replaced or invalidated. Starting acquisition alone does not stale it; bound input changes do.