# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

Read in this order:

1. Final Spec v2.0 Amendments 007 → 001;
2. Final Spec v2.0 where not amended;
3. this mapping;
4. ADRs 0028 → 0020 where current;
5. carried-over nonconflicting ADRs;
6. Context Amendments 007 → 001, then root `CONTEXT.md`;
7. `TICKET-GRAPH-V2.md`, `V2-REVIEW-STATUS.md`, affected tickets, code, tests, runtime declarations, and benchmark evidence.

Final Spec v1.3 remains historical provenance for the shipped runtime baseline.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001–007
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A–V2F
accepted cross-ticket     = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C
next review item          = Q9 V2G/V2I budgets + identity + replay
```

Accepted design does not make a parent envelope or implementation stage agent-ready.

## Accepted architecture summary

- automatic acquisition is default; Expert Recovery retains Add Observation and Continue Acquisition after termination;
- S0/S1 Seed shadow evaluation; Seed-independent Envelope and reversible component Frontier;
- continuous q+s deterministic bounded Consensus with regional Reliability and finite pseudo-mass update;
- component TargetScopeState, structured Frontier Debt, mandatory re-solve after material Scope Delta;
- finite layered View candidate pool;
- geometry pruning for all candidates, then low-resolution occlusion-aware probe for a deterministic shortlist;
- full authoritative RGB/SAM/Evidence only for the winner;
- View Utility and probe outputs remain prospective and never become Evidence, Readiness, Candidate, or Native authority;
- canonical ranking uses deterministic cost units; wall-clock remains telemetry/operational safety only;
- current production keeps one Negative Mass; classified N and leave-one-out Reliability remain nonblocking experiments.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Remaining gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX | reviewed-awaiting-decomposition | split A1/A2/AX; calibration/GPU gates |
| V2B | S0/S1 Seed + TargetScopeState foundations | reviewed-awaiting-decomposition | split Seed, scope, Working Set v2, shadow stages |
| V2C | q+s canonical bounded solve/readout | reviewed-awaiting-decomposition | memory/identity/performance stages |
| V2D | lagged regional Reliability | reviewed-awaiting-decomposition | calibration/diagnostics/LOO stages |
| V2E | weighted q/s update + component Scope Delta/Debt | reviewed-awaiting-decomposition | scope schema and calibration stages |
| V2F | layered pool + hybrid ViewUtilityProbe | reviewed-awaiting-decomposition | split pool/pruning/probe/scoring/calibration stages |
| V2G | budgets, failures, termination, continuation | review-required / next | deterministic accounting, outcomes, replacement, continuation |
| V2H | terminal publication | review-required | Readiness × StopReason and explicit Limited consent |
| V2I | loop orchestration, identity, replay | review-required / next | hierarchy, journal, replay, cancel/suspend/continue |
| V2J | UI + Expert Recovery | review-required | recovery surface, continuation, stale Candidate UX |

## Carry-over implementation

SAM 3 Image authoring, Stable Mask/Participation/User Confirmed authority, authoritative RGB and Direct P/N/V, Stable IDs and Working Sets, Lift Readiness, atomic Candidate replacement, Native operations, User-added View foundation, lifecycle isolation, and locked-GPU identity infrastructure remain implemented v1.3 foundations.

## Documentation lifecycle

Current authority is Amendments 001–007 and ADRs through 0028. Implemented v1 snapshots remain under `history/v1/`. Superseded unimplemented planning envelopes were deleted and replaced. Context overlays are temporary and must be folded into root `CONTEXT.md` during one controlled consolidation, then deleted.

## Implementation gate

A V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark that exact stage `agent-ready`.
