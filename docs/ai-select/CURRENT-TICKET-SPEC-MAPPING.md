# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

Read in this order:

1. Final Spec v2.0 Amendments 006→001;
2. Final Spec v2.0 where not amended;
3. this mapping;
4. ADRs 0027→0020 where current;
5. carried-over nonconflicting ADRs;
6. Context Amendments 006→001, then root `CONTEXT.md`;
7. `TICKET-GRAPH-V2.md`, `V2-REVIEW-STATUS.md`, affected tickets, code, tests, runtime declarations, and benchmark evidence.

Final Spec v1.3 remains historical provenance for the shipped runtime baseline.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001–006
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A–V2E
accepted cross-ticket     = Q4-B, Q5-D, Q6-B, Q7-B
next review item          = Q8 View Utility probe + cost + candidate pool
```

Accepted design does not make a parent envelope or implementation stage agent-ready.

## Accepted architecture

### Product and recovery

Automatic acquisition is default. Expert Recovery retains Add Observation and Continue Acquisition after the loop stops. Native Selection remains explicitly user-owned.

### Seed, discovery, and depth

CWED is internal rather than surface truth. S0/S1 Seeds remain parallel shadow variants. Core, seed-independent Discovery Envelope, and reversible Frontier are distinct. Production retains one Negative Mass; classified N is V2AX only.

### Consensus, readout, and update

- continuous q+s consensus over exact current Included Stable observations;
- deterministic bounded canonical recurrence with lagged Reliability;
- multi-channel same-decision P/K/C/F readout and regional residual;
- immutable-Evidence pseudo-mass update, robust relative weighting, maturity-gated absolute guard;
- mean/tail/View-weight convergence plus oscillation detection;
- non-convergence cannot establish Ready or publish Candidate.

### Target scope and Frontier Debt

- TargetScopeState has Scope Epoch and immutable Scope Revisions;
- Core grows but does not shrink inside an epoch;
- Discovery Envelope is a bounded, seed-independent provenance ledger;
- Frontier transitions are component-level and hysteretic;
- rejected Frontier remains ledger state, not Context;
- material Scope Delta always advances scope and forces a new canonical solve;
- old `scope-advanced` Consensus cannot feed Readiness or Candidate;
- scope churn has a finite per-attempt budget;
- Frontier Debt is structured by component: unobserved, conflict, and promotion-pending;
- a future EvidenceWorkingSet v2 projects explicit Core/active-Frontier/Context roles and exact scope identity.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Remaining gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX | reviewed-awaiting-decomposition | split A1/A2/AX; calibration/GPU gates |
| V2B | S0/S1 Seed + TargetScopeState | reviewed-awaiting-decomposition | split Seed, component scope, ledger, shadow stages |
| V2C | q+s canonical bounded solve/readout | reviewed-awaiting-decomposition | memory/identity/reference stages |
| V2D | lagged regional Reliability | reviewed-awaiting-decomposition | calibration/diagnostics/reference stages |
| V2E | weighted update + convergence + Scope Delta/Debt | reviewed-awaiting-decomposition | split update, scope state, re-solve, debt stages |
| V2F | View Utility | review-required / next | Q8 probe, approximation, cost, candidate pool, exploration |
| V2G | View/cost/scope budgets + termination | review-required | outcome taxonomy, deterministic cost, continuation |
| V2H | terminal publication | review-required | Readiness × StopReason and Limited consent |
| V2I | loop orchestration | review-required | identity hierarchy, scope re-solve journal, replay, cancel/suspend |
| V2J | UI + Expert Recovery | review-required | recovery availability, continuation, stale Candidate UX |

## Carry-over implementation

SAM 3 Image authoring, Stable Mask/Participation/User Confirmed authority, authoritative RGB and Direct P/N/V, Stable IDs and v1 Working Sets, Lift Readiness, atomic Candidate replacement, Native operations, User-added View foundation, lifecycle isolation, and locked-GPU identity infrastructure remain implemented v1.3 foundations.

## Documentation lifecycle

Current authority is Amendments 001–006 and ADRs through 0027. Implemented v1 snapshots stay under `history/v1/`. Superseded unimplemented planning envelopes were deleted and replaced. Context overlays remain temporary and must be folded into root `CONTEXT.md` only during one controlled consolidation, then deleted. EvidenceWorkingSet v1 remains shipped history; v2 scope semantics require an explicit migration rather than silent reinterpretation.

## Implementation gate

A V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark that exact stage `agent-ready`.
