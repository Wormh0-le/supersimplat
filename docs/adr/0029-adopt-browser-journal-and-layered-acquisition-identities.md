# ADR 0029: Browser-owned Decision Journal and hierarchical acquisition identities

Status: accepted  
Date: 2026-08-23

## Context

Adaptive acquisition contains View probing, formal rendering, SAM, Evidence, bounded Consensus iterations, material Scope re-solves, retry/replacement, suspension, and Expert Recovery continuation. A single whole-loop attempt ID cannot express those boundaries, while wall-clock budgets would make replay depend on transient GPU load.

The implemented Browser controller already has a serial queue, a run identity, and separate geometry/plan/render/Prompt/Mask/review/publication attempt ordinals. Replacing those identities would discard proven idempotency and stale-result behavior.

## Decision

1. Keep Browser authority over the product loop and use existing independently validated endpoint attempt identities.
2. Add Acquisition Series, Attempt, and Iteration identities above the endpoint layer; keep Consensus and Scope Revision identities distinct from View Iterations.
3. Maintain one Browser-owned append-only, digest-chained Decision Journal per Attempt.
4. Use deterministic multi-dimensional budget ledgers: successful observations, selected candidate attempts, deterministic cost, replacement/failure, Scope Revisions, and Series cumulative caps.
5. A failed View is free only with respect to Successful Observation Budget; it still consumes formal-attempt, cost, and failure budgets.
6. Same-attempt replay reuses committed decisions/results without reranking or budget debit. Fresh retry requires a new endpoint attempt identity and budget debit.
7. Cancel closes publication authority immediately; exact Suspend/Resume continues only from a compatible journal boundary.
8. Continue Acquisition creates a fresh Attempt with new per-Attempt allowances inside the same cumulatively capped Series.
9. Do not introduce a Companion-autonomous acquisition session.

## Consequences

- Product decisions are deterministic despite wall-clock/GPU variation.
- Identity and journal schemas are more complex and require extensive replay/failure tests.
- Budget accounting distinguishes useful observations from expensive failed work.
- Continue Acquisition is useful but bounded across the target lifecycle.
- V2H still owns Candidate publication semantics; V2J owns presentation.
