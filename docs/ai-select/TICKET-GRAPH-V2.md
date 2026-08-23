# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted product scope — pre-implementation review; not agent-ready**

Source: `docs/specs/ai-select-final-spec-v2.0.md`, ADR 0020 and ADR 0021.  
Current gate: `docs/ai-select/V2-REVIEW-STATUS.md`.

## Execution rule

- No V2 ticket is currently agent-ready.
- Accepted scope is not permission to implement.
- At most one reviewed implementation stage may be in flight.
- Every implementation stage uses TDD, code review, repository validation, and the required locked-GPU gate.
- Shipped behavior remains v1.3 until an explicit reviewed cutover.
- Experimental policy identities never satisfy production readiness.

## Ticket lifecycle

```text
accepted-scope
→ review-required
→ agent-ready
→ in-progress
→ implemented
→ calibrated
→ production-promoted
```

V2A–V2J are currently `review-required`.

## Provisional parent set

| ID | Capability | Spec | Provisional dependencies |
|---|---|---|---|
| V2A | Evidence-Internal Depth + depth-classified Negative Mass | §5 | — |
| V2B | Conservative Seed Support + Core Target denominator | §4 | V2A |
| V2C | Provisional Consensus + soft-mask readout | §5, §7.1 | — |
| V2D | Observation Reliability | §7.2 | V2A, V2C |
| V2E | Weighted aggregation revision | §7.3 | V2A, V2B, V2D |
| V2F | View Utility + layered candidate pool | §6.1–§6.2 | V2B |
| V2G | Budgets, outcomes, failure and termination | §6.3–§6.4 | V2F |
| V2H | Terminal publication semantics | §6.4 | V2E, V2G |
| V2I | Browser loop orchestration + attempt semantics | §3, §8 | V2F, V2G |
| V2J | Acquisition UI + recovery/capability cutover | §10 | V2H, V2I |

## Provisional dependency shape

```text
V2A ─► V2B ─► V2F ─► V2G ─┬─► V2H ─┐
  └────► V2D ◄──── V2C      └─► V2I ─┴─► V2J
          │
          └─► V2E ─────────────► V2H
```

This graph is **not yet closed**:

- V2B/V2E ownership of denominator expansion is unresolved.
- V2C/V2D/V2E require one explicit recurrence model.
- V2F requires a ViewUtilityProbe/approximation seam.
- V2G/V2I require an outcome taxonomy, identity hierarchy and deterministic cost/replay model.
- V2H requires a complete Readiness × StopReason publication matrix.
- V2J requires a reviewed recovery decision before User-added View removal.
- calibration, policy freeze, production-identity promotion, cutover and release qualification require explicit graph ownership.

## Review frontier

```text
first: V2A feasibility and contract review
then:  V2C/V2D/V2E recurrence review
```

V2A and V2C are conceptual roots, but only the user-guided review determines when either becomes agent-ready.

## Parent-ticket rule

V2A–V2J are capability umbrellas. Before implementation, each affected parent must be split into small independently testable stages. A parent ticket must not combine CUDA/ABI, protocol migration, algorithm, cache/replay, UI and production promotion in one coding session.

## Current non-goals

- no implementation during control-plane review;
- no hidden fixed-four fallback;
- no new autonomous Companion session;
- no unreviewed standalone depth protocol;
- no silent production-identity reuse after schema/policy change;
- no deletion of shipped v1.3 recovery capability before its cutover decision;
- no claim of production readiness from an `experimental-v*` policy.
