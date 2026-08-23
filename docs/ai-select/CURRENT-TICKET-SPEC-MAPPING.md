# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**  
Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

Read in this order:

1. Final Spec v2.0 Amendments 005, 004, 003, 002, 001;
2. Final Spec v2.0 where not amended;
3. this mapping;
4. ADRs 0026, 0025, 0024, 0023, 0022, residual ADR 0021, ADR 0020;
5. carried-over nonconflicting ADRs;
6. context amendments 005–001, then root `CONTEXT.md`;
7. `TICKET-GRAPH-V2.md`, `V2-REVIEW-STATUS.md`, affected tickets, code, tests, runtime declarations, and benchmark evidence.

Final Spec v1.3 remains historical provenance for the shipped baseline.

## Runtime and planning status

```text
normative target          = Final Spec v2.0 + Amendments 001–005
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 stages     = none
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B, Q5-D, Q6-B for V2C/V2D/V2E
next review item          = Q7 Scope Delta + Frontier Debt
```

Accepted design does not make a parent envelope or implementation stage agent-ready.

## Accepted architecture

### Product and recovery

Automatic acquisition is default. Expert Recovery retains Add Observation and Continue Acquisition after the loop stops. Native Selection remains explicitly user-owned.

### Seed, discovery, and depth

- CWED is an internal statistic, not surface truth;
- S0/S1 Seeds run in parallel shadow evaluation;
- Core, seed-independent Discovery Envelope, and reversible Frontier are distinct;
- Core Coverage and Frontier Debt are separate;
- production retains one Negative Mass; classified N is V2AX only.

### Consensus readout and recurrence

- q+s continuous consensus;
- deterministic bounded canonical solve over exact current Included Stable observations;
- multi-channel same-decision `P/K/C/F` readout;
- trusted asymmetric regional residual;
- LOO is offline reference only;
- scope frozen during solve and post-solve two-phase delta;
- non-convergence cannot establish Ready or publish Candidate.

### q/s update, Reliability, and convergence

- each iteration reaggregates immutable Evidence from finite pseudo-mass priors;
- previous q/s is not re-added as Evidence;
- `q=(a+P)/(a+b+P+N)`;
- `s=(1-exp(-E/tau_E))*(1-exp(-V/tau_V))`;
- neutral/exempt Views keep weight `1.0`;
- eligible automatic Views use independent median/MAD relative weights with non-zero floor;
- a maturity-gated absolute residual guard may further cap weights;
- convergence requires material mean drift, tail drift, and View-weight drift for consecutive iterations;
- period-two oscillation is explicit; maximum iterations is finite.

## Current v2 mapping

| Ticket | Scope | Lifecycle | Remaining gate |
|---|---|---|---|
| V2A | projected depth + CWED moments + V2AX | reviewed-awaiting-decomposition | split A1/A2/AX; calibration/GPU gates |
| V2B | S0/S1 Seed + Core/Envelope/Frontier | reviewed-awaiting-decomposition | split Seed/scope/shadow stages |
| V2C | q+s canonical bounded solve/readout | review-required, Q4–Q6 accepted | Q7 scope semantics; memory/identity; decomposition |
| V2D | lagged regional Reliability | review-required, Q4–Q6 accepted | calibration/diagnostics; decomposition |
| V2E | weighted update/convergence/scope delta | review-required, Q4–Q6 accepted | Q7 Scope Delta and Frontier Debt |
| V2F | View Utility | review-required | prediction probe, cost, exploration schedule |
| V2G | budgets + termination | review-required | outcome taxonomy, deterministic cost, continuation |
| V2H | terminal publication | review-required | Readiness × StopReason and Limited consent |
| V2I | loop orchestration | review-required | identity hierarchy, journal, replay, cancel/suspend |
| V2J | UI + Expert Recovery | review-required | recovery availability, continuation, stale Candidate UX |

## Carry-over implementation

SAM 3 Image authoring, Stable Mask/Participation/User Confirmed authority, authoritative RGB and Direct P/N/V, Stable IDs and Working Sets, Lift Readiness, atomic Candidate replacement, Native operations, User-added View foundation, lifecycle isolation, and locked-GPU identity infrastructure remain implemented v1.3 foundations.

## Documentation lifecycle

Current authority is Amendments 001–005 and ADRs through 0026. Implemented v1 control-plane snapshots stay under `history/v1/`. Superseded unimplemented planning envelopes were deleted and replaced. Context overlays remain temporary and must be folded into root `CONTEXT.md` only during one controlled consolidation, then deleted.

## Implementation gate

A V2 stage may start only when this mapping and `V2-REVIEW-STATUS.md` both mark that exact stage `agent-ready`.
