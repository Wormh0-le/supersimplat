# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

1. `docs/specs/ai-select-final-spec-v2.0-amendment-004-consensus-readout-regional-reliability.md`
2. `docs/specs/ai-select-final-spec-v2.0-amendment-003-deterministic-bounded-consensus-recurrence.md`
3. `docs/specs/ai-select-final-spec-v2.0-amendment-002-seed-discovery-depth-staging.md`
4. `docs/specs/ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`
5. `docs/specs/ai-select-final-spec-v2.0.md`, except where amended
6. this mapping
7. ADR 0025
8. ADR 0024
9. ADR 0023
10. ADR 0022
11. residual ADR 0021
12. ADR 0020
13. carried-over ADR 0019, residual ADR 0018, and unconflicted ADRs 0016/0017/0013/0015
14. context amendments 004/003/002/001, then root `CONTEXT.md`
15. `docs/ai-select/TICKET-GRAPH-V2.md`
16. `docs/ai-select/V2-REVIEW-STATUS.md`
17. affected ticket, implementation, tests, runtime declarations, and benchmark evidence

Final Spec v1.3 remains historical provenance for the shipped baseline under `docs/ai-select/history/v1/`.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001–004
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B recurrence; Q5-D readout/residual
next review item          = Q6 q/s update + Reliability normalization + convergence
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
- Core/Envelope/Frontier/Context are frozen during the solve;
- Scope Delta commits only after the solve and affects a later solve;
- warm/incremental solve must agree with a cold canonical solve;
- non-convergence is Limited/fail-closed and cannot publish Candidate.

### Consensus readout and Reliability

- production uses a multi-channel same-decision readout, not a single whole-frame soft mask;
- support-aware membership is `q̃=0.5+s(q-0.5)`;
- readout moments derive soft foreground, knownness, Core fraction, and Frontier fraction under valid semantic-scope mass;
- render-only/out-of-scope Gaussians continue to occlude but do not write semantic moments;
- Reliability uses separately normalized Strong Positive Interior and Local Negative Ring residuals; Boundary is low-weight/diagnostic and Far Neutral is excluded;
- positive disagreement receives bounded asymmetric Frontier/unknown protection; negative-ring conflict does not receive a symmetric exemption;
- insufficient comparison support yields neutral weight with a diagnostic reason;
- User Confirmed/manual observations retain semantic weight `1.0`;
- leave-one-out consensus is a nonblocking offline reference benchmark, not the production path.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Key remaining review/decomposition gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX sidecar | reviewed-awaiting-decomposition | split A1/A2/AX; thresholds and GPU gates remain calibration-owned |
| V2B | S0/S1 Seed + Core/Envelope/Frontier | reviewed-awaiting-decomposition | split Seed, scope state, promotion, and shadow validation stages |
| V2C | q+s Consensus + bounded solve + multi-channel readout | review-required / Q4+Q5 accepted | Q6 q/s transforms; convergence; channel layout/performance; identity |
| V2D | lagged regional Observation Reliability + LOO reference | review-required / Q4+Q5 accepted | robust normalization; warm-up/floor; degenerate scale; calibration |
| V2E | weighted aggregation + two-phase scope revision | review-required / Q4+Q5 accepted | q/s update; Frontier Debt; convergence tolerance; scope thresholds |
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

- Final Spec v2.0 with Amendments 001–004;
- ADRs 0025/0024/0023/0022, residual ADR 0021, ADR 0020, and carried-over nonconflicting ADRs;
- current mapping, traceability, manifest, review status, graph, and V2 ticket envelopes;
- context amendments 004/003/002/001 over root `CONTEXT.md`.

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
