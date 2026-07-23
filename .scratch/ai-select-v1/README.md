# AI Select v1 — Implementation Ticket Graph v2.2

Status: **ready-for-agent after five-pass bidirectional traceability audit**

Authoritative source order:

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`
3. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` where not superseded
4. `CONTEXT.md`
5. `AGENTS.md`
6. Current implementation and tests

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

This v2.2 supersedes the v2.1 local ticket graph. It retains 22 tickets but changes Evidence ownership and the dependency order required by Final Spec v1.1 / ADR 0013.

## v2.2 corrections incorporated

- Camera Inspection and AIView Render Ready depend on authoritative RGB only, not complete Contributor or formal Evidence.
- Explicit Retry creates a real new render attempt for the same CameraBinding; same-attempt replay remains idempotent.
- Stable Mask publication invalidates exact per-view Evidence by dependency identity.
- Ticket 14 now owns the reference P/N/V Evidence contract, Mask Evidence policy, per-view artifact, multi-view aggregation, and Candidate PoC.
- Ticket 10 cross-view assessment and Ticket 13 Coverage/Readiness now follow Ticket 14 rather than consuming undefined Evidence.
- Ticket 19 owns SceneSnapshot, authoritative RGB, and conservative Render Working Set hardening; complete Contributor is reference/debug only.
- Ticket 20 owns the production same-decision Direct Evidence path and artifact/working-set hardening.
- Ticket 21 owns true Retry, Evidence/OOM/atomic failure hardening, classification stability, and policy calibration.
- Ticket 22 contracts both the legacy Object Selection workflow and complete Contributor production dependency.
- Error/recovery coverage now includes Evidence Failure, reference Contributor failure, cached-failure Retry semantics, Scene Chunk Miss, and atomic Evidence publication.

## Dependency graph

```text
01 CurrentTargetContext kernel
 │
 ▼
02 AI Select shell + authoritative gsplat Anchor
 ├───────────────┐
 ▼               ▼
03 Camera        04 Anchor AIView + Mask/Evidence lifecycle
   Inspection +
   RGB Retry
 └───────┬───────┘
         ▼
05 Anchor editing + support Validation + Confirm + Early Restart
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
 ├──────────────────┐
 ▼                  ▼
11 User-added View  12 Repropagate + Evidence Dirty/Stale
 └──────────┬───────┘
            ▼
14 Reference P/N/V Evidence + Gaussian Lifting/Candidate
            │
            ▼
10 Cross-view Assessment
            │
            ▼
13 Visible Evidence Coverage + Diversity + Lift Readiness
            │
            ▼
15 Candidate correction + Evidence-aware explicit Re-Lift
            │
            ▼
16 Native Set/Add/Remove/Intersect
            │
            ▼
17 Applied Undo-and-Fix + Restart + multi-object/tool-switch
            │
            ▼
18 Scene Mutation Suspended + Exact Undo Recovery
            │
            ▼
19 Large SceneSnapshot + authoritative RGB / Render Working Set
            │
            ▼
20 Same-decision GPU Evidence + artifact/working-set hardening
            │
            ▼
21 Retry/OOM/atomic publication + calibration hardening
            │
            ▼
22 Contract legacy product and Contributor paths
```

Structural graph root: **Ticket 01**. Implementation progress/closure remains recorded in each ticket; the audit validates scope and dependency correctness rather than inferring code completion.

## Topological order

`01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

## Audit artifacts

- `TRACEABILITY.md`: 125 Final Spec v1.1/inherited requirements mapped to tickets, plus reverse mapping result.
- `FOUR-PASS-AUDIT.md`: five-pass graph, spec→ticket, ticket→spec, outcome→prerequisite, and workflow/failure audit. Filename retained for compatibility.
- `WALKTHROUGHS.md`: inherited Flows A–I, four v1.1 architecture flows, reverse outcome backtrace, and 12 failure/degradation walkthroughs.
- `manifest.json`: machine-readable v2.2 graph and audit metadata.

## Implementation rule

Ticket 14 is a reference correctness/quality gate, not production GPU completion. Ticket 20 is the first ticket permitted to claim production same-decision Direct Evidence, and only after locked GPU validation. Complete Contributor remains available solely as an explicit reference/debug backend.