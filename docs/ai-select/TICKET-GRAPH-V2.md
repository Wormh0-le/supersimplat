# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted amended scope, pre-implementation review; no stage is agent-ready**

Sources: Final Spec v2.0 with Amendments 001–008, ADRs 0020–0029 where current, and carried-over nonconflicting v1.3 contracts.

## Parent capabilities

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | projected depth/CWED; V2AX sidecar | — | V2B S1 |
| V2B | Seed + TargetScopeState/Frontier | V2A for S1 | V2E, V2F |
| V2C | q+s canonical solve/readout | — | V2D |
| V2D | lagged regional Reliability | V2C | V2E |
| V2E | weighted update/convergence/Scope Delta | V2B, V2D | V2F, V2H |
| V2F | hybrid View Utility/candidate pool | V2B, V2E | V2G, V2I |
| V2G | deterministic budgets/outcomes/termination | V2F | V2H, V2I |
| V2H | terminal publication/consent | V2E, V2G | V2J |
| V2I | Browser Journal/identity/replay/orchestration | V2F, V2G | V2J |
| V2J | acquisition UI + Expert Recovery | V2H, V2I | — |

## Reviewed acquisition lifecycle

```text
Acquisition Series
├── initial bounded Attempt
└── optional fresh Continue Attempts

Attempt
├── Browser append-only Decision Journal
├── deterministic multi-budget ledger
└── Iterations
    ├── committed Utility ranking
    ├── probe/full-acquisition endpoint attempts
    ├── one usable observation or structured failure
    └── Consensus/Scope revisions
```

Same-attempt replay reuses committed decisions and results. Fresh retry/replacement consumes declared budgets. Cancel/Suspend are fail-closed; Continue is a new Attempt under a cumulative Series cap.

## Experimental/reference sidecars

- V2AX depth-classified Negative Evidence;
- V2D leave-one-out Reliability reference;
- V2F fixed-four ablation and full-render-all-candidates oracle.

They do not block the critical path unless a later promotion decision creates an explicit edge.

## Agent readiness

```text
reviewed parent direction = V2A–V2G, V2I
agent-ready stages        = none
next review item          = V2H publication matrix
```
