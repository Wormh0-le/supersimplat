# Lifecycle and Protocol Invariants

Amended v2.0 is target; implemented v1.3 remains runtime until explicit reviewed cutover. Exact stage must be agent-ready in mapping and review status.

## Acquisition identities and Journal

- Preserve existing endpoint attempt IDs; never collapse them into one loop ID.
- Series → Attempt → Iteration sits above Utility/probe/endpoint attempts and Consensus/Scope revisions.
- Browser owns the append-only digest-chained Decision Journal and commits ranking/selection/budget transitions before dependent work.
- Companion owns validated endpoints and disposable caches, not an autonomous product session.

## Budget/replay

- Successful observations, selected candidate attempts, deterministic cost, failure/replacement, Scope Revisions, and Series caps are separate finite ledgers.
- Failed/Excluded work does not consume a successful-observation slot but consumes applicable work/failure budgets.
- Same-attempt replay does not rerank or debit again.
- Fresh retry uses a new endpoint attempt ID and budget debit.
- Replacement follows the committed ranking.
- Wall-clock/cache state cannot change canonical ranking.

## Cancel, Suspend, Continue

- Cancel closes the Attempt publication gate immediately; late results are discarded while complete artifacts remain.
- Suspend resumes the same Attempt only from an exact compatible journal boundary with remaining budget; otherwise it becomes stale.
- Continue Acquisition is a fresh Attempt with reset per-Attempt allowances and preserved Series caps/current stable artifacts.
- Starting Continue alone does not stale Candidate; a bound input change applies existing stale rules.

Stable Mask, Participation, raw Evidence, Scope, Consensus, Candidate, and Native Selection remain distinct. Candidate changes Native Selection only through explicit native EditHistory operations.
