# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted parent scope; decomposition pending; no stage is agent-ready**

Sources: Final Spec v2.0 with Amendments 001–009, ADRs 0020–0030 where current, carried-over nonconflicting v1.3 contracts, and the accepted Q11 V2J interface contract.

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
| V2H | two-gate terminal publication/consent | V2E, V2G, V2I | V2J |
| V2I | Browser Journal/identity/replay/orchestration | V2F, V2G | V2H, V2J |
| V2J | acquisition UI + Expert Recovery | V2H, V2I | — |

## Reviewed publication lifecycle

```text
complete terminal snapshot
        ↓
Publication Eligibility Gate
        ↓
Ready + ready-low-gain       → automatic Candidate
Ready + forced terminal      → Use Ready Candidate
Limited + eligible terminal  → Use Limited Candidate
Not Ready / incompatible     → no Candidate
```

Re-Lift recomputes exact current inputs; it does not accept an existing snapshot. A running Acquisition Attempt keeps the prior Candidate inspectable but temporarily blocks applying it.

## Reviewed V2J presentation lifecycle

```text
running Attempt
  ├─ passive inspection → keep running
  └─ authoritative edit → pause-pending → safe boundary → requested edit
                                                ↓
                               explicit Resume (compatible/no change)
                               or Continue (fresh Attempt after change)
```

- one compact Session Strip projects cross-View workflow and publication state;
- main 3D toolbar owns Anchor/View spatial authoring and Candidate Native operations;
- a read-only Spatial Edit HUD accompanies Anchor/Observation drafts;
- existing live frustum manipulation and Navigator/frustum/Dock linkage are preserved;
- Dock Evidence changes only at successful staged/completed render boundaries.

## Experimental/reference sidecars

- V2AX depth-classified Negative Evidence;
- V2D leave-one-out Reliability reference;
- V2F fixed-four ablation and full-render-all-candidates oracle.

They do not block the critical path unless a later promotion decision creates an explicit edge.

## Agent readiness

```text
reviewed parent direction = V2A–V2J
agent-ready stages        = none
next review item          = parent-ticket decomposition
```
