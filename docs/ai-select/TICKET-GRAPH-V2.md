# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no ticket is agent-ready**

## Current sources

Final Spec v2.0 with Amendments 001–005; ADRs 0020–0026 where current; carried-over nonconflicting v1.3 decisions.

## Execution rules

Runtime remains v1.3 until explicit reviewed cutovers. Parent tickets are capability envelopes, not executable slices. At most one exact agent-ready stage may be in flight. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Projected depth + CWED moments; V2AX sidecar | — | V2B S1 path |
| V2B | Conservative Seed + Core/Envelope/Frontier | V2A for S1 only | V2E, V2F |
| V2C | q+s Consensus/readout + deterministic bounded solve | — | V2D |
| V2D | lagged regional Observation Reliability | V2C | V2E |
| V2E | weighted q/s update + convergence + two-phase scope revision | V2B, V2D | V2F, V2H |
| V2F | View Utility + exploration + candidate pool | V2B, V2E | V2G, V2I |
| V2G | budget, outcomes, termination, continuation | V2F | V2H, V2I |
| V2H | terminal publication semantics | V2E, V2G | V2J |
| V2I | Browser loop orchestration + identity/replay | V2F, V2G | V2J |
| V2J | Acquisition UI + Expert Recovery | V2H, V2I | — |

`V2AX` and the V2D leave-one-out path are nonblocking reference experiments.

## Provisional dependency graph

```text
V2A ─────────────► V2B ───────┐
                               ├─► V2E ─► V2F ─► V2G ─┬─► V2H ─┐
V2C ─► V2D ────────────────────┘                      └─► V2I ─┤
                                                                  ▼
                                                    V2J UI + Expert Recovery
```

## Accepted consensus/update architecture

```text
exact current Included Stable observations
        ↓
finite scope/provenance pseudo-mass prior
+ uniform immutable Evidence aggregate
        ↓
q^(0), s^(0)
        ↓
┌──────────────────────────────────────────┐
│ lagged P/K/C/F readout                   │
│ → regional residual                     │
│ → neutral or robust/absolute omega       │
│ → weighted immutable P/N + unweighted V  │
│ → finite-posterior q and support s       │
│ → convergence / oscillation diagnostics  │
└──────── deterministic + bounded ─────────┘
        ↓
one atomic Consensus Revision
        ↓
post-solve Scope Delta (Q7 pending)
```

Key invariants:

- no iterative Evidence double counting;
- q is not calibrated probability; s separates unknown from conflict;
- weights are independent `[r_min,1]`, not sum normalized;
- absolute guard is consensus-maturity gated;
- convergence checks mean, tail, and View-weight drift for consecutive iterations;
- period-two oscillation is explicit;
- scope is frozen during solve;
- non-convergence cannot publish Candidate.

## Reviewed Seed/discovery architecture

Seed initializes but does not bound Core discovery. Discovery Envelope is seed-independent, Frontier reversible, Core monotonic only inside one stable input revision, and Core Coverage cannot hide Frontier Debt.

## Product cutover intent

Default: `Anchor → automatic bounded acquisition → Candidate/readiness`.

Secondary terminal recovery: Add Observation / Use Current View or Continue Acquisition as a fresh bounded attempt.

## Scope boundaries

Fixed-four is regression baseline only. Production retains one N channel. No automatic Native Selection application, persistent planning controls, standalone Browser depth/consensus artifact, or experimental policy in production identity.

## Agent-readiness

```text
accepted cross-ticket = Q4-B, Q5-D, Q6-B
agent-ready stages    = none
next review item      = Q7 Scope Delta + Frontier Debt
```
