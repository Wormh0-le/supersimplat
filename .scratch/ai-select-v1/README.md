# AI Select v1 — Implementation Ticket Graph v2.3

Status: **ready-for-agent — Ticket 04A implemented; Ticket 07A is the next completion gate**

Authoritative source order:

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. `docs/specs/ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`
3. `docs/specs/ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`
4. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`
5. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` where not superseded
6. `CONTEXT.md`
7. `docs/decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`
8. `AGENTS.md`
9. Current implementation and tests

Amendment 001 governs renderer/Evidence implementation identity and RGB continuity. Amendment 002 governs Prompt Authoring and the Three-Stage Anchor Mask Pipeline. DG-21 records the accepted rationale and ticket ownership; the Final Spec and amendments remain authoritative.

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

v2.3 supersedes the v2.2 local ticket graph. It retains the 22 numbered tickets and adds two retrofit hardening tickets: **04A** and **07A**.

## v2.3 corrections incorporated

- Ticket 04A separates Prompt Authoring from direct Pixel Editing and introduces versioned PromptState, explicit adapter capabilities, and bounded multi-candidate proposal artifacts.
- Ticket 04A depends on existing Ticket 05 Mask editor/Undo/Confirm seams; it is not incorrectly placed before Ticket 05.
- Ticket 04A is implemented. Its browser validation found interaction-hardening work that is now an explicit Phase 0 entry gate in Ticket 07A: atomic Paint/Erase strokes, stroke-level Undo/Redo, persistent prompt markers, active cursors, and visible proposal state.
- Ticket 07A is the completion owner for interaction hardening, 2D-first proposal ranking, Ambiguous/Unavailable states, proposal acceptance, Editing/Confirm integration, compact Proposal UX, and locked real-model quality validation.
- `ProposalDecision` remains pre-Stable and distinct from Ticket 07 `ViewAssessmentPolicy`.
- The mandatory Three-Stage pipeline applies to the Anchor; Generated View automatic Stable Mask publication remains unchanged unless explicitly revised later.
- Ticket 08 depends on Ticket 07A and owns candidate-camera validity as well as information gain, including indoor/outside-room rejection.
- Camera Inspection and AIView RGB Ready remain independent from complete Contributor and formal Evidence.
- Ticket 14 owns reference P/N/V semantics; Ticket 20 owns production same-decision Direct Evidence.
- Complete Contributor remains an explicit debug/reference backend only.

## Dependency graph

```text
01 CurrentTargetContext kernel
 │
 ▼
02 AI Select shell + authoritative gsplat Anchor
 ├───────────────────┐
 ▼                   ▼
03 Camera            04 Anchor AIView + Mask/Evidence lifecycle
   Inspection +       │
   RGB Retry           │
 └──────────┬──────────┘
            ▼
05 Anchor editing + support Validation + Confirm + Early Restart
 ├──────────────────────┐
 ▼                      ▼
04A Prompt Authoring    06 First Generated AIView + Initial Auto Mask
 + Proposal Foundation   │
 │                       ▼
 │                      07 Local Assessment + Participation
 └──────────────┬────────┘
                ▼
07A Interaction hardening + Three-Stage Anchor Ranking / Ambiguity / Acceptance
                │
                ▼
08 Adaptive Planner + valid indoor observation poses
                │
                ▼
09 Scalable Gallery + Inspect AI Cameras
 ├──────────────────┐
 ▼                  ▼
11 User-added View  12 Repropagate + Evidence Dirty/Stale
 └──────────┬───────┘
            ▼
14 Reference P/N/V Evidence + Gaussian Lifting/Candidate
 ├──────────────────┐
 ▼                  ▼
10 Cross-view P1    13 Visible Evidence Coverage + Readiness
 Assessment          │
 └──────────────────┘
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

Ticket 04A and the existing Ticket 06→07 path converge at Ticket 07A. Ticket 08 cannot start until 07A completes. Tickets 10 and 13 remain parallel consumers of Ticket 14.

Structural graph root: **Ticket 01**. Ticket status remains recorded in each ticket; graph audit validates scope/dependency correctness rather than inferring implementation completion.

## One valid topological order

`01 → 02 → 03 → 04 → 05 → 04A → 06 → 07 → 07A → 08 → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

## Audit artifacts

- `TRACEABILITY.md`: 142 Final Spec v1.1 / Amendments 001–002 / inherited requirements mapped to tickets.
- `FOUR-PASS-AUDIT.md`: five-pass v2.3 graph, spec→ticket, ticket→spec, outcome→prerequisite, and workflow/failure audit. Filename retained for compatibility.
- `WALKTHROUGHS.md`: inherited workflows, architecture flows, Three-Stage Anchor flow, reverse outcome backtrace, and proposal/planner failure walkthroughs.
- `manifest.json`: machine-readable v2.3 graph and audit metadata.

## Implementation rules

- Ticket 04A is an implemented foundation ticket, not the final quality gate.
- Ticket 07A begins with Phase 0 interaction hardening; ranking must not be considered complete while Paint/Erase remains stamp-based or Prompt feedback remains ambiguous.
- Ticket 07A is the only ticket permitted to claim the Three-Stage Anchor Mask Pipeline complete.
- Ticket 08 owns Generated View camera validity/adaptive planning, not Anchor proposal ranking.
- Ticket 14 is a reference correctness/quality gate, not production GPU completion.
- Ticket 20 is the first ticket permitted to claim production same-decision Direct Evidence, after locked GPU validation.
- Complete Contributor is reference/debug only.
