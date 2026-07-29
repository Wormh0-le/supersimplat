# AI Select v1 — Implementation Ticket Graph v2.5

Status: **ready-for-agent planning graph — Ticket 04B remains the next implementation gate**

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. `docs/specs/ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`
3. `docs/specs/ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`
4. `docs/specs/ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md`
5. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`
6. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` where not superseded
7. `CONTEXT.md`
8. `docs/decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`
9. `docs/decision-gates/DG-22-floating-prompt-edit-palette.md`
10. `docs/decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md`
11. `AGENTS.md`
12. Current implementation and tests

The Final Spec and amendments remain authoritative. DG-23 refines the Anchor ranking closure and adds object-level 2.5D planning/tracking while preserving final P/N/V ownership.

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

v2.5 retains 22 numbered tickets and adds five retrofit tickets: **04A**, **04B**, **07A**, **07B**, and **08A**.

## v2.5 corrections incorporated

- AI Select v1 targets one object instance; arbitrary part discovery and whole-image object inventory are not mandatory.
- Ticket 04A remains implemented and owns PromptState, explicit Prompt/Edit tools, capabilities, and bounded proposal infrastructure.
- Ticket 04B owns real non-text visual-prompt adapter enablement and performs no ranking, clustering, ambiguity, or Stable publication.
- Ticket 07A is narrowed to conservative object-level Anchor acquisition.
- The previous benchmark-calibrated automatic Top-1 margin requirement is superseded by Amendment 003.
- Ticket 07A still owns near-duplicate clustering, hard Prompt consistency, structural quality gating, structured reasons, false-auto-selection/contamination benchmarks, and explicit Accept/Edit/Confirm.
- Materially distinct plausible object candidates may remain `ambiguous` and require user refinement.
- Ticket 07B owns the draggable, collapsible, Space-hide palette; automatic relocation remains optional/deferred.
- Ticket 08 now owns a non-ownership `TargetBootstrapArtifact`, valid adaptive Key Views, Bridge Views, transition cost, and ordered `TrackingSequencePlan`.
- Ticket 08A owns the tracker-backend spike, later implementation ADR, production object-level tracking, correction memory, and declared single-frame SAM fallback.
- Ticket 06 remains complete; its projected-support + single-frame SAM path is the tracer-bullet baseline/fallback.
- Ticket 09 presents Anchor/Key/Bridge roles, tracking/Mask/reference status, and Participation separately.
- Ticket 12 owns explicit tracker repropagate and dirty/stale lifecycle.
- Ticket 14/20 remain the only formal Gaussian ownership stages; tracker confidence and bootstrap support are not P/N/V.

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
04A Prompt Authoring            06 First Generated AIView + baseline Auto Mask
 + Proposal Foundation           │
 │                               ▼
 ▼                              07 Local Assessment + Participation
04B Visual Prompt Adapter        │
 Enablement                      │
 └──────────────────┬────────────┘
                    ▼
07A Object-level Anchor Acquisition / Conservative ProposalDecision
                    │
                    ▼
07B Floating Prompt/Edit Palette UX
                    │
                    ▼
08 2.5D Bootstrap + Adaptive Key/Bridge Sequence Planner
                    │
                    ▼
08A Object-level Mask Tracking + Correction Memory
                    │
                    ▼
09 Scalable Gallery + Inspect AI Cameras / Tracking Status
 ├──────────────────┐
 ▼                  ▼
11 User-added View  12 Explicit Tracker Repropagate + Dirty/Stale
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

Ticket 04A and Ticket 06 may proceed after Ticket 05. Ticket 04B follows 04A. Ticket 04B and completed Ticket 07 converge at 07A. Ticket 07B follows 07A. Ticket 08 produces the ordered non-ownership sequence; Ticket 08A produces tracked Masks; Ticket 09/12 consume those tracking artifacts before Ticket 14 final lifting.

Structural graph root: **Ticket 01**.

## One valid topological order

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

## Audit artifacts

- `TRACEABILITY.md`: Final Spec v1.1 / Amendments 001–003 / DG-20–23 mapped to tickets.
- `FOUR-PASS-AUDIT.md`: five-pass v2.5 graph, bidirectional scope, reverse dependency, and workflow/failure audit.
- `WALKTHROUGHS.md`: inherited flows plus D′ sequence/tracking/correction paths.
- `manifest.json`: machine-readable v2.5 graph and audit metadata.

## Implementation rules

- Ticket 04B is still the next executable implementation ticket.
- Ticket 07A cannot claim completion from browser layout fixes or fake-predictor tests alone.
- Ticket 07A does not need a general calibrated Top-1 ranker; it must fail conservatively on material ambiguity.
- Ticket 07B changes presentation/pointer routing only.
- Ticket 08 may use early geometry for planning but cannot publish ownership or Masks.
- Ticket 08A starts with a bounded tracker spike; a separate ADR locks the backend before production closure.
- Ticket 06 baseline remains runnable and explicitly identified as fallback when used.
- Tracking membership never implies Lift Participation; Bridge Views default Excluded.
- Confirmed correction frames enter tracker memory only through Ticket 12 explicit repropagate.
- Ticket 14 is the reference correctness/quality gate; Ticket 20 owns production same-decision Evidence.
- Complete Contributor remains reference/debug only.