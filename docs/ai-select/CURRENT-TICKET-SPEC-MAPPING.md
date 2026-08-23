# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

1. `docs/specs/ai-select-final-spec-v2.0-amendment-002-seed-discovery-depth-staging.md`
2. `docs/specs/ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`
3. `docs/specs/ai-select-final-spec-v2.0.md`, except where amended
4. this mapping
5. ADR 0023
6. ADR 0022
7. residual ADR 0021
8. ADR 0020
9. carried-over ADR 0019, residual ADR 0018, unconflicted ADRs 0016/0017/0013/0015
10. context amendments 002 and 001, then root `CONTEXT.md`
11. `docs/ai-select/TICKET-GRAPH-V2.md`
12. `docs/ai-select/V2-REVIEW-STATUS.md`
13. affected ticket, implementation, tests, runtime declarations, and benchmark evidence

Final Spec v1.3 remains historical provenance for the shipped baseline under `docs/ai-select/history/v1/`.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001/002
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A, V2B
next review item          = V2C/V2D/V2E recurrence
```

Accepted scope or a reviewed parent envelope does not make an implementation stage agent-ready.

## Accepted product/architecture decisions

### Automation and recovery

- automatic acquisition is the default;
- Expert Recovery after termination retains Add Observation and Continue Acquisition;
- Native Selection remains explicitly user-owned.

### Seed, discovery, and depth

- internal depth is Contribution-Weighted Expected Depth (CWED), not surface truth;
- Direct Evidence depth support accumulates M0/M1/M2 from the accepted sequence;
- S0 and S1 Conservative Seed variants are shadow-evaluated in parallel;
- Gaussian-center depth consistency is a soft Seed feature, never a permanent discovery boundary;
- Core Target, Discovery Envelope, and Discovery Frontier are distinct;
- Discovery Envelope is seed-independent and Frontier is reversible;
- Core is monotonic only within one stable input revision;
- Core Coverage and Frontier Debt are separate;
- View Utility must balance Core, Frontier, Uncertain, diversity, and cost;
- current production keeps one Negative Mass channel;
- depth-classified N is a nonblocking V2AX experiment.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Key remaining review/decomposition gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX sidecar | reviewed-awaiting-decomposition | split A1/A2/AX; thresholds and GPU gates remain calibration-owned |
| V2B | S0/S1 Seed + Core/Envelope/Frontier | reviewed-awaiting-decomposition | split Seed, scope state, promotion, and shadow validation stages |
| V2C | Provisional Consensus | review-required / next | q0, state representation, recurrence, soft-mask seam |
| V2D | Observation Reliability | review-required / next | equation, lag, warm-up, Frontier protection, exemptions |
| V2E | Weighted Aggregation + scope revision | review-required / next | recurrence ordering, promotion, convergence, incremental equivalence |
| V2F | View Utility | review-required | prediction probe, approximation, cost, exploration schedule |
| V2G | Budgets + termination | review-required | outcome taxonomy, deterministic cost, continuation budget |
| V2H | Terminal publication | review-required | Readiness × StopReason matrix and Limited consent |
| V2I | Loop orchestration | review-required | identity hierarchy, journal, replay, cancel/suspend |
| V2J | Acquisition UI + Expert Recovery | review-required | recovery availability, continuation, stale Candidate UX |

## Carry-over implementation

The following v1.3 foundations remain implemented and must stay green:

- SAM 3 Image single-result authoring;
- Anchor, TargetGeometryHint, Stable Mask, Participation, and User Confirmed authority;
- authoritative gsplat RGB and same-decision Direct P/N/V;
- Stable IDs, SceneSnapshot, Render/Evidence Working Sets and boundary contact;
- Lift Readiness, atomic Candidate replacement, and Native operations;
- User-added View implementation as Expert Recovery migration foundation;
- dirty/stale/suspend/replay/failure isolation;
- production identity and locked-GPU benchmark infrastructure.

## Documentation lifecycle

### Current

- Final Spec v2.0 with Amendments 001/002;
- ADRs 0023/0022, residual ADR 0021, ADR 0020, and carried-over nonconflicting ADRs;
- current mapping, traceability, manifest, review status, graph, and V2 ticket envelopes;
- context amendments 002/001 over root `CONTEXT.md`.

### Historical

- implemented v1 control-plane snapshots under `docs/ai-select/history/v1/`;
- Final Spec v1.3 and older specifications;
- closed v1 ticket files and acceptance evidence;
- ADR 0021's original mandatory-classified-N decision, preserved in its partially superseded record.

### Deprecated or removed

- root glossary definitions conflicting with Context Amendment 002 are deprecated until controlled consolidation;
- old unimplemented V2A/V2B envelope files were deleted and replaced, not archived;
- the removal-oriented V2J file remains deleted;
- root v1 graph/audit/walkthrough paths remain compatibility pointers only.

## Implementation gate

A V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark the exact stage `agent-ready`.
