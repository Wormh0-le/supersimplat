# V2I — Browser orchestration, hierarchical identity, Decision Journal, and replay

Status: **reviewed parent envelope — Q9-B accepted; awaiting decomposition; not agent-ready**

Blocked by: V2F, V2G  
Blocks: V2J

## Authority

Final Spec Amendment 008 / ADR 0029; existing Browser generated-view controller, endpoint idempotency, stale-result, and lifecycle contracts.

## Goal

Generalize the serial generated-view pipeline into Browser-driven adaptive acquisition without replacing existing endpoint attempt IDs or introducing a Companion-autonomous session.

## Accepted identity model

```text
Target/dependency
→ Acquisition Series
→ Attempt
→ Iteration
→ Utility/Probe/selected View/endpoint attempts
+ Consensus Revision
+ Scope Revision
```

Initial automation and every Continue action are separate Attempts in one cumulatively capped Series.

## Accepted Decision Journal

The Browser owns one append-only digest-chained journal per Attempt. It commits candidate pool/ranking/selection, budget transitions, endpoint requests/outcomes, observation publication, Consensus/Scope revisions, and terminal state. Companion caches are derived and cannot redefine journal decisions.

## Accepted replay/lifecycle behavior

- same endpoint attempt + same journal state = replay, no rerank or budget debit;
- fresh retry = new endpoint attempt + declared budget debit;
- replacement follows the committed ranking;
- Cancel appends terminal state, closes publication authority, and discards late results;
- Suspend resumes only from the last complete compatible journal boundary with remaining budget;
- incompatible resume marks the Attempt stale;
- Continue creates a fresh Attempt with new per-Attempt budgets and retained Series caps/artifacts;
- existing complete Views/Masks/Evidence and prior Candidate remain preserved according to current stale rules.

## Remaining gates before decomposition

- exact Journal entry schemas and storage lifetime inside the active Browser session;
- endpoint request/result digest integration and replay-conflict surface;
- mapping from existing `runOrdinal`/attempt ordinals to the new hierarchy;
- queue boundaries, operational timeout, and stale callback tests;
- Q10 publication state consumption and V2J presentation;
- stage decomposition and production migration order.

## Validation families

Identity collision/rotation; hash-chain integrity; exact replay; fresh retry; Companion restart recompute digest match; Cancel late result; exact Suspend/Resume; incompatible stale; Continue Attempt/Series cap; serial queue regressions; no autonomous session.

## Non-goals

No new transport, Candidate publication policy, UI control design, or wall-clock-based canonical ranking.
