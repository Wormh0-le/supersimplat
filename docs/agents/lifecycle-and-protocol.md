# Lifecycle and Protocol Invariants

These are amended v2.0 target invariants. Follow [Domain authority](domain.md) for implementation eligibility and the distinction between target and shipped behavior.

## Acquisition identities and Journal

- Preserve endpoint attempt IDs under Series → Attempt → Iteration.
- Browser owns the append-only Decision Journal and deterministic budget transitions.
- Same-attempt replay never reranks or debits again; fresh retry uses new identity and budget.
- Cancel closes the Acquisition Attempt publication gate immediately; late results are discarded.
- Suspend resumes the same Attempt only from an exact compatible Journal boundary with remaining budget.
- Continue Acquisition is a fresh Attempt under the current Series cap.

## Candidate publication

- Candidate publication consumes one immutable Candidate Publication Snapshot.
- Eligibility requires exact current Stable observations/Evidence, converged non-oscillating Consensus, current Scope with no material delta, current readiness/policies, and complete production identity.
- Only eligible `Ready + ready-low-gain` auto-publishes.
- Forced-terminal Ready requires `Use Ready Candidate`; eligible Limited requires `Use Limited Candidate`.
- Not Ready, scope-advanced, unresolved Scope-budget exhaustion, non-converged, oscillating, stale, Suspended, incomplete, and late results cannot publish.
- Explicit Use actions are idempotent Candidate Publication Attempts and do not recompute.
- Re-Lift recomputes exact current Stable inputs and never restarts acquisition.
- Candidate publication is atomic and never self-applies Native Selection.

## Prior Candidate and application

- Starting acquisition alone does not stale a prior Candidate.
- While an Attempt runs, the Candidate remains inspectable but Set/Add/Remove/Intersect from it are temporarily blocked.
- A bound Stable observation, Participation, Scope, dependency, or policy change applies normal staleness.
- Cancel may restore application of a still-current prior Candidate.

Stable Mask, Participation, raw Evidence, Scope, Consensus, Candidate, and Native Selection remain distinct authorities.
