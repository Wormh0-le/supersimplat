# AI Select v1 — Implementation Ticket Graph v2.1

Status: **ready-for-agent after four-pass traceability audit**

Authoritative source order:

1. `docs/specs/ai-select-final-spec-v1.0.md`
2. `docs/adr/0012-adopt-ai-select-final-spec-v1.md`
3. `CONTEXT.md`
4. `AGENTS.md`
5. Current implementation and tests

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

This v2.1 supersedes the prior local ticket graphs.

## Corrections incorporated

- Initial Generated View Mask Propagation has explicit ownership in Ticket 06.
- Confirm Anchor atomic binding/lock is explicit in Ticket 05.
- Review Reason → localized recommended action mapping is explicit in Ticket 07/10.
- Gallery explicitly forbids ordinary Delete View in v1.0.
- Stop Generation → Lift Readiness integration is explicit in Ticket 13.
- Error/recovery criteria cover Companion Offline, Preview, Mask, View Render, Lift, Repropagate, cancellation and OOM.
- Former oversized production-hardening work is split into Tickets 19–21.
- Gallery and P1 cross-view assessment are separated into Tickets 09 and 10.
- Contextual-toolbar states remain owned by corresponding vertical feature tickets.

## Dependency graph

```text
01 CurrentTargetContext kernel
 │
 ▼
02 AI Select shell + authoritative gsplat Anchor
 ├───────────────┐
 ▼               ▼
03 Camera        04 Anchor Mask versioning
   Inspection
 └───────┬───────┘
         ▼
05 Anchor editing + Validation + Confirm Anchor + Early Restart
         │
         ▼
06 First Generated AIView + Initial Auto Mask
         │
         ▼
07 Local Assessment + Participation
         │
         ▼
08 Adaptive Planner
         │
         ▼
09 Scalable Gallery + Inspect AI Cameras
 ├──────────────┬──────────────┐
 ▼              ▼              ▼
10 Cross-view   11 User-added  12 Explicit Repropagate
   Assessment      AIView         + Dirty/Stale
 └──────────────┬───────┬──────┘
                ▼
13 Coverage + Diversity + Lift Readiness
                │
                ▼
14 Gaussian Lifting → Candidate / Uncertain
                │
                ▼
15 Pre-apply Candidate Correction + explicit Re-Lift
                │
                ▼
16 Native Set/Add/Remove/Intersect
                │
                ▼
17 Applied Undo-and-Fix + Full Restart + Multi-object / Tool switch
                │
                ▼
18 Scene Mutation Suspended + Exact Undo Recovery
                │
                ▼
19 Large SceneSnapshot + gsplat Render/Contributor Cache
                │
                ▼
20 GPU Evidence + Mask/Thumbnail Working Set
                │
                ▼
21 Failure Injection + OOM/Atomic Publication + Calibration
                │
                ▼
22 Contract Legacy Product Path
```

Initial frontier: **Ticket 01 only**.

## Audit artifacts

- `TRACEABILITY.md`: 100 Final Spec requirements mapped to implementation tickets.
- `FOUR-PASS-AUDIT.md`: graph, reverse-traceability, scope, workflow/error audit.
- `WALKTHROUGHS.md`: Typical Flows A–I plus all specified failure/degradation walkthroughs.
- `manifest.json`: machine-readable graph/audit metadata.
