# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no ticket is agent-ready**

## Current sources

Final Spec v2.0 with Amendments 001–006; ADRs 0020–0027 where current; carried-over nonconflicting v1.3 decisions.

## Execution rules

Runtime remains v1.3 until explicit reviewed cutovers. Parent tickets are capability envelopes, not executable slices. At most one exact agent-ready stage may be in flight. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Projected depth + CWED moments; V2AX sidecar | — | V2B S1 path |
| V2B | Conservative Seed + component TargetScopeState | V2A for S1 only | V2E, V2F |
| V2C | q+s Consensus/readout + deterministic bounded solve | — | V2D |
| V2D | lagged regional Observation Reliability | V2C | V2E |
| V2E | weighted q/s update + convergence + Scope Delta/Debt | V2B, V2D | V2F, V2H |
| V2F | View Utility probe + exploration + candidate pool | V2B, V2E | V2G, V2I |
| V2G | View/cost/scope budgets, outcomes, termination | V2F | V2H, V2I |
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

## Accepted iterative architecture

```text
Seed + seed-independent Envelope
        ↓
component TargetScopeState
        ↓
exact Scope Revision + Included Stable Evidence
        ↓
deterministic bounded q+s solve
        ↓
regional Reliability + immutable-Evidence update
        ↓
converged Consensus Revision
        ↓
component Scope Delta
  ├─ empty ─────────────► Debt / Readiness / Utility
  └─ material ─► new Scope Revision ─► mandatory new solve
```

Key invariants:

- Core is monotonic inside a Scope Epoch;
- Envelope ledger is bounded/provenance-recorded; active Frontier is reversible;
- rejected Frontier is not Context and reopens only on new provenance;
- promotion/rejection is component-level and hysteretic;
- Frontier Debt distinguishes unobserved, conflict, and promotion-pending components;
- pre-delta/scope-advanced Consensus cannot publish;
- Scope Revision churn is finite;
- EvidenceWorkingSet v2 must preserve explicit roles and exact scope identity.

## Product cutover intent

Default: `Anchor → automatic bounded acquisition → Candidate/readiness`.

Secondary terminal recovery: Add Observation / Use Current View or Continue Acquisition as a fresh bounded attempt.

## Scope boundaries

Fixed-four is regression baseline only. Production retains one N channel. No automatic Native Selection application, persistent planning controls, standalone Browser depth/consensus artifact, or experimental policy in production identity.

## Agent-readiness

```text
reviewed parent direction = V2A–V2E
accepted cross-ticket     = Q4-B, Q5-D, Q6-B, Q7-B
agent-ready stages        = none
next review item          = Q8 View Utility probe + cost + candidate pool
```
