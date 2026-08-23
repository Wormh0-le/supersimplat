# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no ticket is agent-ready**

## Current sources

1. Final Spec v2.0 Amendment 002;
2. Final Spec v2.0 Amendment 001;
3. Final Spec v2.0 where not amended;
4. ADR 0023, ADR 0022, residual ADR 0021, ADR 0020;
5. carried-over non-conflicting v1.3 decisions.

## Execution rules

- Runtime remains v1.3 until explicit reviewed cutovers.
- Parent tickets are capability envelopes, not executable slices.
- At most one agent-ready implementation stage may be in flight.
- Each stage uses TDD/code review and preserves the shipped baseline.
- Calibration, policy freeze, production promotion, cutover, and release qualification still require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Projected depth + CWED moments; V2AX experiment sidecar | — | V2B S1 path |
| V2B | Conservative Seed + Core/Envelope/Frontier | V2A for S1 only | V2E, V2F |
| V2C | Provisional Consensus + soft-mask readout | — | V2D |
| V2D | Observation Reliability over current P/N/V | V2C | V2E |
| V2E | Weighted aggregation + target-scope revision | V2B, V2D | V2F, V2H |
| V2F | View Utility + exploration + candidate pool | V2B, V2E | V2G, V2I |
| V2G | Dual budget, outcomes, termination, continuation policy | V2F | V2H, V2I |
| V2H | Terminal publication semantics | V2E, V2G | V2J |
| V2I | Browser loop orchestration + attempt/replay semantics | V2F, V2G | V2J |
| V2J | Acquisition UI + Expert Recovery | V2H, V2I | — |

`V2AX` is a nonblocking classified-N benchmark experiment after V2A2. It has no outgoing critical-path edge unless a later promotion decision creates one.

## Provisional dependency graph

```text
V2A ─────────────► V2B ───────┐
                               ├─► V2E ─► V2F ─► V2G ─┬─► V2H ─┐
V2C ─► V2D ────────────────────┘                      └─► V2I ─┤
                                                                  ▼
                                                    V2J UI + Expert Recovery

V2A2 ─► V2AX experiment (nonblocking sidecar)
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

- S0 and S1 seed variants are shadow-evaluated in parallel;
- Discovery Envelope is not derived solely from Seed;
- Frontier is reversible and cannot directly become Candidate;
- Core is monotonic only inside one stable input revision;
- high Core Coverage cannot hide material Frontier Debt;
- Expert Recovery is an independent discovery source.

## Product cutover intent

Default:

```text
Anchor → automatic bounded acquisition → Candidate/readiness
```

Secondary recovery after the loop stops:

```text
Add Observation / Use Current View
or
Continue Acquisition as a fresh bounded attempt
```

## Scope boundaries

- fixed-four remains regression/ablation baseline only;
- current production retains one Negative Mass channel;
- classified N is V2AX experiment only unless explicitly promoted;
- no Companion-autonomous product session or new transport;
- no automatic Native Selection application;
- no persistent Stop/Generate More/Regenerate controls;
- no standalone Browser depth artifact;
- no V2 policy enters production identity while still experimental.

## Agent-readiness

```text
reviewed parent direction = V2A, V2B
agent-ready stages        = none
next review item          = V2C/V2D/V2E recurrence
```
