# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

1. `docs/specs/ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`
2. `docs/specs/ai-select-final-spec-v2.0.md`, except where amended
3. this mapping
4. ADR 0022
5. ADR 0021
6. ADR 0020
7. carried-over ADR 0019, residual ADR 0018, unconflicted ADRs 0016/0017/0013/0015
8. `docs/ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md`, then `CONTEXT.md`
9. `docs/ai-select/TICKET-GRAPH-V2.md`
10. `docs/ai-select/V2-REVIEW-STATUS.md`
11. affected ticket, implementation, tests, runtime declarations, and benchmark evidence

Final Spec v1.3 is historical provenance for the shipped baseline under `docs/ai-select/history/v1/`.

## Runtime and planning status

```text
normative target          = amended Final Spec v2.0
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 tickets    = none
review frontier           = V2A, then V2C
```

Accepted scope does not make a ticket agent-ready.

## Accepted product orientation

```text
default:
Anchor → automatic acquisition → terminal Candidate/readiness

expert recovery after the loop stops:
Add Observation / Use Current View
or Continue Acquisition
```

User-added View is retained as a secondary recovery capability. The previous v2 clause and obsolete V2J ticket that removed it are superseded/deleted. Persistent planning controls remain retired.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Key review gate |
|---|---|---|---|
| V2A | Depth readout + classified N | review-required | depth data path, traversal, schema, identity |
| V2B | Conservative Seed + denominator | review-required | representation, connectivity, fallback, expansion owner |
| V2C | Provisional Consensus | review-required | q0, state, recurrence, soft-mask seam |
| V2D | Observation Reliability | review-required | equation, lag, guardrails, provenance exemptions |
| V2E | Weighted Aggregation | review-required | recurrence integration and incremental equivalence |
| V2F | View Utility | review-required | prediction probe, approximation, cost, candidate pool |
| V2G | Budgets + termination | review-required | outcome taxonomy, deterministic cost, continuation budget |
| V2H | Terminal publication | review-required | complete Readiness × StopReason matrix and consent |
| V2I | Loop orchestration | review-required | identity hierarchy, journal, replay, cancel/suspend |
| V2J | Acquisition UI + Expert Recovery | review-required | recovery availability, Add Observation, Continue Acquisition, stale Candidate UX |

The dependency graph is provisional until these review gates close.

## Carry-over implementation

The following v1.3 foundations remain implemented and must stay green:

- SAM 3 Image single-result authoring;
- Anchor, TargetGeometryHint, Stable Mask, Participation, and User Confirmed authority;
- authoritative gsplat RGB and same-decision Direct P/N/V;
- Stable IDs, SceneSnapshot, Render/Evidence Working Sets;
- Lift Readiness, atomic Candidate replacement, and Native operations;
- User-added View implementation as a migration foundation;
- dirty/stale/suspend/replay/failure isolation;
- production identity and locked-GPU benchmark infrastructure.

## Documentation lifecycle

### Current

- amended Final Spec v2.0 and ADRs 0022/0021/0020;
- current mapping, traceability, manifest, review status, V2 graph, and V2 tickets;
- root `CONTEXT.md` plus the current Expert Recovery context amendment.

### Historical

- implemented v1 control-plane snapshots under `docs/ai-select/history/v1/`;
- Final Spec v1.3 and older specifications;
- closed v1 ticket files and acceptance evidence.

### Deprecated or removed

- root glossary definition `User-added View (superseded)` is deprecated by the context amendment;
- `docs/ai-select/tickets/v2/V2J-acquisition-ui-user-added-view-removal.md` is removed and replaced by the Expert Recovery ticket;
- old root v1 graph/audit/walkthrough paths are compatibility pointers only.

## Implementation gate

A V2 ticket may start only when this mapping and `V2-REVIEW-STATUS.md` both mark the exact stage `agent-ready`.
