# AI Select v2.0 — Provisional Implementation Ticket Graph

Status: **accepted scope, pre-implementation review; no ticket is agent-ready**

Sources:

- Final Spec v2.0 Amendment 001;
- Final Spec v2.0, except where amended;
- ADR 0022, ADR 0021, ADR 0020;
- carried-over non-conflicting v1.3 decisions.

## Execution rules

- Runtime remains v1.3 until explicit reviewed cutovers.
- Parent tickets V2A–V2J are capability envelopes, not yet executable slices.
- At most one agent-ready implementation stage may be in flight.
- Every stage uses TDD and code review and preserves the shipped baseline.
- Calibration, policy freeze, production promotion, cutover, and release qualification still require explicit graph ownership.

## Ticket set

| ID | Capability | Blocked by | Blocks |
|---|---|---|---|
| V2A | Evidence-internal depth + depth-classified N | — | V2B, V2D, V2E |
| V2B | Conservative Seed + Core Target denominator | V2A | V2E, V2F |
| V2C | Provisional Consensus + soft-mask readout | — | V2D |
| V2D | Observation Reliability | V2A, V2C | V2E |
| V2E | Weighted Aggregation revision | V2A, V2B, V2D | V2H |
| V2F | View Utility + layered candidate pool | V2B | V2G, V2I |
| V2G | Dual budget, outcomes, termination, continuation policy | V2F | V2H, V2I |
| V2H | Terminal publication semantics | V2E, V2G | V2J |
| V2I | Browser loop orchestration + attempt/replay semantics | V2F, V2G | V2J |
| V2J | Acquisition UI + Expert Recovery | V2H, V2I | — |

## Provisional dependency graph

```text
V2A ─► V2B ─► V2F ─► V2G ─┬─► V2H ─┐
 │       │                  └─► V2I ─┤
 │       └──────► V2E ◄──────────────┘
 └─► V2D ◄─ V2C      │
         └───────────►┘
                              ▼
                 V2J UI + Expert Recovery
```

One provisional topological order:

```text
V2A, V2C → V2B → {V2D → V2E} ∥ V2F → V2G → {V2H, V2I} → V2J
```

The graph will be revised after each design review. V2A and V2C are the current review roots.

## Product cutover intent

### Default path

```text
Anchor → automatic bounded acquisition → Candidate/readiness
```

### Expert Recovery after the loop stops

```text
Add Observation / Use Current View
or
Continue Acquisition as a fresh bounded attempt
```

User-added View is retained and repositioned as recovery. It is not deleted, is not part of the automatic happy path, and is unavailable while the loop runs.

## Scope boundaries

- fixed-four remains a regression/ablation baseline only;
- no Companion-autonomous product session or new transport;
- no automatic Native Selection application;
- no persistent Stop/Generate More/Regenerate controls;
- Continue Acquisition is terminal recovery, not same-attempt replay;
- Add Observation uses the current validated User-added View foundations;
- User Confirmed Stable Masks retain authority;
- whole-frame rendered-depth protocol remains separately gated;
- region/per-pixel reliability remains out of scope without benchmark evidence;
- no V2 ticket enters production identity while still `experimental-v*`.

## Agent-readiness

```text
agent-ready tickets = none
next review item = V2A
```

See `CURRENT-TICKET-SPEC-MAPPING.md` and `V2-REVIEW-STATUS.md`.
