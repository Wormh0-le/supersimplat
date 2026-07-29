# AI Select v1 — Implementation Ticket Graph v2.4

Status: **ready-for-agent — Ticket 04B is the next adapter gate; Ticket 07A is reopened; Ticket 07B follows algorithm closure**

Authoritative source order:

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. `docs/specs/ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`
3. `docs/specs/ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`
4. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`
5. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` where not superseded
6. `CONTEXT.md`
7. `docs/decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`
8. `docs/decision-gates/DG-22-floating-prompt-edit-palette.md`
9. `AGENTS.md`
10. Current implementation and tests

The Final Spec and amendments remain authoritative. DG-21 records Three-Stage Anchor ownership. DG-22 refines fitted-image toolbar interaction without changing Prompt/Mask/Evidence lifecycle semantics.

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

v2.4 retains the 22 numbered tickets and adds four retrofit tickets: **04A**, **04B**, **07A**, and **07B**.

## v2.4 corrections incorporated

- Ticket 04A remains implemented and owns PromptState, explicit Prompt/Edit tools, capability negotiation, and bounded proposal infrastructure.
- Ticket 04B owns real non-text visual-prompt adapter enablement: Positive/Negative Box and Positive/Negative Mask Constraint according to truthful locked-runtime capabilities.
- Ticket 04B forwards independently validated adapter candidates only; all ranking, clustering, representative selection, ambiguity, and `ProposalDecision` ownership remains in Ticket 07A.
- Text Prompt remains a future capability-gated extension and is not required by Ticket 04B.
- Ticket 07A is reopened after algorithm review. Its Phase 4 Dock/fitted-image/schema-v2 publication fixes remain accepted.
- Ticket 07A must still complete single-candidate quality gating, calibrated 2D-first ranking, structured rejection reasons, near-duplicate clustering before truncation, production-resolution performance, and frozen-scene/ablation validation.
- Ticket 07B owns the draggable, collapsible, Space-hide floating Prompt/Edit palette defined by DG-22.
- Ticket 07B may optionally add a non-relocating opacity assist; automatic relocation is not a closure requirement.
- Ticket 07B preserves the fitted-image rule and removes permanent interaction blind spots.
- Ticket 08 follows 07B and continues to own valid indoor Generated View poses plus adaptive information gain.
- `ProposalDecision` remains pre-Stable and distinct from Ticket 07 `ViewAssessmentPolicy`.
- Generated View automatic Stable Mask publication remains unchanged unless explicitly revised later.
- Ticket 14 owns reference P/N/V semantics; Ticket 20 owns production same-decision Direct Evidence.

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
 ├──────────────────────────────┐
 ▼                              ▼
04A Prompt Authoring            06 First Generated AIView + Initial Auto Mask
 + Proposal Foundation           │
 │                               ▼
 ▼                              07 Local Assessment + Participation
04B Visual Prompt Adapter        │
 Enablement                      │
 └──────────────────┬────────────┘
                    ▼
07A Reopened Three-Stage Anchor Ranking / Ambiguity / Acceptance
                    │
                    ▼
07B Floating Prompt/Edit Palette UX Hardening
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

Ticket 04A and Ticket 06 may proceed after Ticket 05. Ticket 04B follows 04A. Ticket 04B and completed Ticket 07 converge at reopened Ticket 07A. Ticket 07B follows 07A and removes the fitted-image toolbar blind spot before Ticket 08 begins.

Structural graph root: **Ticket 01**. Ticket status remains recorded in each ticket; graph audit validates scope/dependency correctness rather than inferring completion.

## One valid topological order

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

## Audit artifacts

- `TRACEABILITY.md`: Final Spec v1.1 / Amendments 001–002 / DG-20–22 / inherited requirements mapped to tickets.
- `FOUR-PASS-AUDIT.md`: five-pass v2.4 graph, spec→ticket, ticket→spec, outcome→prerequisite, and workflow/failure audit. Filename retained for compatibility.
- `WALKTHROUGHS.md`: inherited workflows, visual-prompt adapter flow, Three-Stage Anchor flow, floating-palette flow, reverse outcome backtrace, and proposal/planner failures.
- `manifest.json`: machine-readable v2.4 graph and audit metadata.

## Implementation rules

- Ticket 04A is an implemented foundation ticket, not the final quality gate.
- Ticket 04B enables real Box/Mask Prompt adapter semantics. It performs no cross-candidate ranking, clustering, representative selection, ambiguity decision, or Stable publication.
- Ticket 07A is reopened and remains the only ticket permitted to claim the Three-Stage Anchor Mask Pipeline complete.
- Phase 4 Dock/fitted-image/schema-v2 fixes remain valid but do not satisfy the reopened algorithm/calibration gates.
- Ticket 07B changes palette presentation and pointer routing only; it must not alter PromptState, ProposalDecision, Mask lifecycle, or Evidence semantics.
- Ticket 07B closure requires drag, collapse, Space temporary hide, and immediate removal of stale hit regions; automatic relocation is optional and deferred.
- Ticket 08 owns Generated View camera validity/adaptive planning, not Anchor proposal ranking or palette UX.
- Ticket 14 is a reference correctness/quality gate, not production GPU completion.
- Ticket 20 is the first ticket permitted to claim production same-decision Direct Evidence after locked GPU validation.
- Complete Contributor remains reference/debug only.
