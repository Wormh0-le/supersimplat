# ADR 0030: Adopt two-gate Candidate publication and explicit terminal consent

Status: accepted (2026-08-23)

## Context

ADR 0020 correctly adopted automatic Candidate publication for the normal `Ready + ready-low-gain` terminal, but the later acquisition design introduced forced budget terminals, no-feasible/failure outcomes, Cancel snapshots, scope advancement, non-convergence, and explicit Expert Recovery. Treating every non-normal terminal as “publish nothing; click Re-Lift” conflates recomputation with consent and discards already-computed, identity-correct Ready or Limited snapshots.

At the same time, automatically publishing every Ready result would make abnormal termination appear equivalent to normal completion and would weaken the meaning of terminal reasons.

## Decision

1. Candidate publication requires both a hard Publication Eligibility Gate and a Readiness/Terminal/Consent decision.
2. Only an eligible `Ready + ready-low-gain` normal terminal auto-publishes.
3. Eligible Ready results at forced terminals require `Use Ready Candidate`.
4. Eligible Limited results require `Use Limited Candidate`.
5. Not Ready, scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, or late results cannot publish.
6. `Use Ready/Limited Candidate` publishes an immutable existing snapshot through a new idempotent Candidate Publication Attempt; it does not recompute.
7. Re-Lift remains recomputation. Ready may publish from the explicit recomputation; Limited still requires distinct consent.
8. A running Acquisition Attempt temporarily blocks applying an AI Candidate but does not itself make the prior Candidate stale. Cancel may restore application if the Candidate remains current.
9. Candidate publication never self-applies Native Selection.

## Consequences

- normal success remains frictionless;
- forced or Limited outcomes remain legible and explicitly consented;
- Re-Lift no longer doubles as acceptance of an already-computed result;
- V2H gains a complete testable matrix rather than ad hoc terminal branches;
- V2J must present state-specific actions without showing every recovery control at once;
- a new Candidate Publication Attempt identity/journal seam is required;
- ADR 0020 is partially superseded only where it required all other terminals to publish nothing/readiness-only or used Re-Lift as the only Limited consent path.

## Rejected alternatives

- Auto-publish every eligible Ready result: too easy to disguise abnormal termination as normal success.
- Publish only at ready-low-gain and require Re-Lift everywhere else: conflates recomputation with consent and adds needless work.
- Allow explicit publication from Not Ready or incompatible snapshots: violates fail-closed publication authority.