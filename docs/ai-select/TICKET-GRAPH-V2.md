# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no ticket is agent-ready**

## Current sources

1. Final Spec v2.0 Amendment 004;
2. Amendment 003;
3. Amendment 002;
4. Amendment 001;
5. Final Spec v2.0 where not amended;
6. ADR 0025, ADR 0024, ADR 0023, ADR 0022, residual ADR 0021, ADR 0020;
7. carried-over non-conflicting v1.3 decisions.

## Execution rules

- Runtime remains v1.3 until explicit reviewed cutovers.
- Parent tickets are capability envelopes, not executable slices.
- At most one agent-ready implementation stage may be in flight.
- Each stage uses TDD/code review and preserves the shipped baseline.
- Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Projected depth + CWED moments; V2AX sidecar | — | V2B S1 path |
| V2B | Conservative Seed + Core/Envelope/Frontier | V2A for S1 only | V2E, V2F |
| V2C | q+s Consensus + bounded solve + multi-channel readout | — | V2D |
| V2D | lagged regional Reliability + LOO reference | V2C | V2E |
| V2E | weighted aggregation + q/s update + scope revision | V2B, V2D | V2F, V2H |
| V2F | View Utility + exploration + candidate pool | V2B, V2E | V2G, V2I |
| V2G | Dual budget, outcomes, termination, continuation | V2F | V2H, V2I |
| V2H | Terminal publication semantics | V2E, V2G | V2J |
| V2I | Browser loop orchestration + attempt/replay | V2F, V2G | V2J |
| V2J | Acquisition UI + Expert Recovery | V2H, V2I | — |

Nonblocking sidecars:

```text
V2A2 → V2AX classified-N experiment
V2C/V2D → leave-one-out Reliability reference benchmark
```

Neither sidecar has a critical-path edge unless a later promotion decision creates one.

## Provisional dependency graph

```text
V2A ─────────────► V2B ───────┐
                               ├─► V2E ─► V2F ─► V2G ─┬─► V2H ─┐
V2C ─► V2D ────────────────────┘                      └─► V2I ─┤
                                                                  ▼
                                                    V2J UI + Expert Recovery
```

One provisional topological order:

```text
{V2A, V2C} → {V2B, V2D} → V2E → V2F → V2G → {V2H, V2I} → V2J
```

## Reviewed Seed/discovery architecture

```text
Conservative Seed S_0
        ↓
Core C_t         Discovery Envelope E_t
        └──────► Frontier F_t = E_t - C_t
                         ↓
Core Coverage + Frontier Debt + Uncertain + Diversity
                         ↓
                    View Utility
```

Seed never hard-bounds discovery; Frontier is reversible; Core is monotonic only inside one stable input revision; Expert Recovery is an independent discovery source.

## Accepted consensus and Reliability architecture

```text
exact Included Stable observation set
        ↓
finite Seed prior + uniform aggregate
        ↓
q^(0), s^(0)
        ↓
lagged same-decision readout:
M_scope / M_fg / M_known / M_core / M_frontier
        ↓
trusted regional Reliability ω^(r)
        ↓
weighted P/N + raw V
        ↓
q^(r), s^(r)
        ↓
deterministic bounded convergence
        ↓
one atomic Consensus Revision
        ↓
post-solve Scope Delta
```

- production Reliability uses positive-interior, negative-ring, and low-weight/diagnostic boundary residuals;
- positive Frontier protection is asymmetric;
- insufficient comparison support is neutral;
- User Confirmed/manual observations retain full semantic weight;
- leave-one-out consensus is reference-only;
- non-convergence cannot establish Ready or Candidate.

## Product cutover intent

```text
Anchor → automatic bounded acquisition → Candidate/readiness
                                     ↘ Expert Recovery after stop
```

## Scope boundaries

- fixed-four remains regression/ablation baseline only;
- current production retains one Negative Mass channel;
- classified N and leave-one-out Reliability are nonblocking experiments/references;
- no Companion-autonomous product session or new transport;
- no automatic Native Selection application;
- no persistent Stop/Generate More/Regenerate controls;
- no standalone Browser depth or consensus artifact;
- no experimental policy enters production identity.

## Agent-readiness

```text
reviewed parent direction = V2A, V2B
accepted cross-ticket     = Q4-B recurrence + Q5-D readout/residual
agent-ready stages        = none
next review item          = Q6 q/s update + Reliability normalization + convergence
```
