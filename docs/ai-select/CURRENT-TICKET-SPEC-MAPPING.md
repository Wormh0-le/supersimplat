# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

1. `docs/specs/ai-select-final-spec-v2.0-amendment-003-deterministic-bounded-consensus-recurrence.md`
2. `docs/specs/ai-select-final-spec-v2.0-amendment-002-seed-discovery-depth-staging.md`
3. `docs/specs/ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`
4. `docs/specs/ai-select-final-spec-v2.0.md`, except where amended
5. this mapping
6. ADR 0024
7. ADR 0023
8. ADR 0022
9. residual ADR 0021
10. ADR 0020
11. carried-over ADR 0019, residual ADR 0018, and unconflicted ADRs 0016/0017/0013/0015
12. context amendments 003/002/001, then root `CONTEXT.md`
13. `docs/ai-select/TICKET-GRAPH-V2.md`
14. `docs/ai-select/V2-REVIEW-STATUS.md`
15. affected ticket, implementation, tests, runtime declarations, and benchmark evidence

Final Spec v1.3 remains historical provenance for the shipped baseline under `docs/ai-select/history/v1/`.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001/002/003
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A, V2B
accepted recurrence model = Q4-B for V2C/V2D/V2E
next review item          = Q5 consensus readout + reliability residual
```

Accepted scope or a reviewed cross-ticket decision does not make an implementation stage agent-ready.

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
- View Utility must balance Core, Frontier, Uncertain, diversity, duplication, and cost;
- current production keeps one Negative Mass channel;
- depth-classified N is a nonblocking V2AX experiment.

### Consensus recurrence

- Provisional Consensus stores continuous membership tendency `q` and independent support/knownness `s`;
- canonical output is a deterministic bounded batch solve over the exact current Included Stable observation set;
- q/s initialize from a finite Seed prior plus a uniform aggregate over all current Included Evidence;
- Reliability iteration `r` consumes only q/s from iteration `r-1`;
- one public atomic Consensus Revision may contain multiple private Solver Iterations;
- View arrival order and cache history cannot define canonical output;
- Core/Envelope/Frontier are frozen during the solve;
- Scope Delta commits only after the solve and affects a subsequent solve;
- warm/incremental solve is an optimization and must agree with a cold canonical solve;
- non-convergence is Limited/fail-closed and cannot publish Candidate.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Key remaining review/decomposition gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX sidecar | reviewed-awaiting-decomposition | split A1/A2/AX; thresholds and GPU gates remain calibration-owned |
| V2B | S0/S1 Seed + Core/Envelope/Frontier | reviewed-awaiting-decomposition | split Seed, scope state, promotion, and shadow validation stages |
| V2C | q+s Consensus + bounded canonical solve | review-required / Q4 accepted | Q5 readout; q/s transforms; convergence; memory/identity |
| V2D | lagged Observation Reliability | review-required / Q4 accepted | Q5 residual/gating; warm-up; robust normalization; exemptions |
| V2E | weighted aggregation + two-phase scope revision | review-required / Q4 accepted | q/s update; Frontier Debt; convergence tolerance; scope thresholds |
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

- Final Spec v2.0 with Amendments 001/002/003;
- ADRs 0024/0023/0022, residual ADR 0021, ADR 0020, and carried-over nonconflicting ADRs;
- current mapping, traceability, manifest, review status, graph, and V2 ticket envelopes;
- context amendments 003/002/001 over root `CONTEXT.md`.

### Historical

- implemented v1 control-plane snapshots under `docs/ai-select/history/v1/`;
- Final Spec v1.3 and older specifications;
- closed v1 ticket files and acceptance evidence;
- superseded clauses retained in accepted ADR/spec history.

### Deprecated or removed

- root glossary definitions conflicting with current Context Amendments are deprecated until controlled consolidation;
- old unimplemented V2A/V2B envelope files were deleted and replaced;
- the removal-oriented V2J file remains deleted;
- root v1 graph/audit/walkthrough paths remain compatibility pointers only.

## Implementation gate

A V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark the exact stage `agent-ready`.
