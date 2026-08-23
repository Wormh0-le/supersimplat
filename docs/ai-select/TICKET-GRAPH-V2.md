# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no ticket is agent-ready**

## Sources

Final Spec v2.0 with Amendments 001–007; ADRs 0020–0028 where current; carried-over nonconflicting v1.3 decisions.

## Execution rules

Runtime remains v1.3 until explicit reviewed cutovers. Parent tickets are capability envelopes, not executable slices. At most one exact agent-ready stage may be in flight. Calibration, policy freeze, production promotion, cutover, and release qualification require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Projected depth + CWED moments; V2AX sidecar | — | V2B S1 path |
| V2B | Conservative Seed + TargetScopeState foundations | V2A for S1 only | V2E, V2F |
| V2C | q+s Consensus/readout + deterministic bounded solve | — | V2D |
| V2D | lagged regional Observation Reliability | V2C | V2E |
| V2E | weighted q/s update + convergence + component scope revision | V2B, V2D | V2F, V2H |
| V2F | layered candidate pool + hybrid ViewUtilityProbe | V2B, V2E | V2G, V2I |
| V2G | deterministic budgets, outcomes, termination, continuation | V2F | V2H, V2I |
| V2H | terminal publication semantics | V2E, V2G | V2J |
| V2I | Browser loop orchestration + identity/journal/replay | V2F, V2G | V2J |
| V2J | Acquisition UI + Expert Recovery | V2H, V2I | — |

`V2AX`, leave-one-out Reliability, fixed-four, and full-render-all-candidates are nonblocking experiments/baselines.

## Dependency graph

```text
V2A ─────────────► V2B ───────┐
                               ├─► V2E ─► V2F ─► V2G ─┬─► V2H ─┐
V2C ─► V2D ────────────────────┘                      └─► V2I ─┤
                                                                  ▼
                                                    V2J UI + Expert Recovery
```

## Accepted View Utility architecture

```text
Layer 0 hint offsets
+ Layer 1 sparse target-scope shell
+ Layer 2 bounded component-Debt cameras
        ↓
deterministic geometric pruning
        ↓
deterministic shortlist
        ↓
low-resolution complete-occlusion ViewUtilityProbe
        ↓
Core / Frontier Debt / Uncertain / diversity / cost score
        ↓
one winner only
        ↓
authoritative RGB → SAM → Evidence → Consensus
```

The probe is prospective only. Canonical cost uses deterministic units; wall-clock is telemetry/operational safety. Candidate identities, probe outputs, and caches bind exact target/dependency/scope/q-s/policy/working-set inputs.

## Product cutover intent

Default: `Anchor → automatic bounded acquisition → Candidate/readiness`.

Terminal Expert Recovery: Add Observation / Use Current View or Continue Acquisition as a fresh bounded attempt.

## Agent-readiness

```text
reviewed parent direction = V2A–V2F
accepted decisions        = Q4-B, Q5-D, Q6-B, Q7-B, Q8-C
agent-ready stages        = none
next review item          = Q9 V2G/V2I budgets + identity + replay
```
