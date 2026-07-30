# AI Select v1 — Implementation Ticket Graph v2.6

Status: **ready-for-agent planning graph — Ticket 04B remains the next implementation gate**

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. Amendments 001–004, latest amendment governing conflicts
3. ADR 0013
4. ADR 0012 where not superseded
5. `CONTEXT.md`
6. DG-21, DG-22, DG-23, DG-24, with DG-24 governing multi-view Mask acquisition
7. `AGENTS.md`
8. Current implementation and tests

Branch: `ai-select-v1`

Baseline: `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`

v2.6 retains 22 numbered tickets and five retrofit tickets: **04A**, **04B**, **07A**, **07B**, and **08A**.

## v2.6 D-double-prime corrections

- AI Select v1 targets one object instance; arbitrary part discovery and whole-image inventory are not mandatory.
- Ticket 07A remains conservative object-level Anchor acquisition; materially distinct plausible alternatives may remain `ambiguous`.
- Ticket 08 owns a non-ownership TargetBootstrapArtifact and adaptive sparse Key Views.
- `Generate More` appends immutable plan segments and does not invalidate completed segment artifacts.
- Ticket 08A is a multi-view Mask acquisition spike plus implementation ticket.
- The default candidate route is enhanced 3D-guided independent SAM per Key View.
- Current projected-support + single-frame SAM remains route A and fallback.
- Tracker/hybrid routes are optional benchmark candidates and require a later ADR before production adoption.
- Bridge Views, transition envelopes, correction memory, and repropagation are not mandatory v1 contracts.
- Confirming a correction is per-view by default; optional `Use as Tracking Reference` is a separate action only when capability exists.
- Target bootstrap seeds but never hard-bounds the final Evidence Working Set.
- Ticket 14/20 remain the only formal Gaussian ownership stages.

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
08 2.5D Bootstrap + Adaptive Sparse Key-View Planner
                    │
                    ▼
08A Multi-view Mask Acquisition Spike + 3D-guided per-Key-View SAM
                    │
                    ▼
09 Scalable Gallery + Inspect AI Cameras / Acquisition Status
 ├──────────────────┐
 ▼                  ▼
11 User-added View  12 Explicit Mask Refresh + Dirty/Stale
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

Ticket 04A and Ticket 06 may proceed after Ticket 05. Ticket 04B follows 04A. Ticket 04B and completed Ticket 07 converge at 07A. Ticket 07B follows 07A. Ticket 08 produces sparse non-ownership Key Views; Ticket 08A acquires their Masks; Ticket 09/12 consume those artifacts before Ticket 14 final lifting.

## One valid topological order

`01 → 02 → 03 → 04 → 05 → 04A → 04B → 06 → 07 → 07A → 07B → 08 → 08A → 09 → 11 → 12 → 14 → 10 → 13 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22`

## Audit artifacts

- `TRACEABILITY.md`: Final Spec v1.1 / Amendments 001–004 / DG-20–24 mapped to tickets.
- `FOUR-PASS-AUDIT.md`: five-pass v2.6 graph, artifact-dependency, reverse-scope, workflow, and failure audit.
- `WALKTHROUGHS.md`: inherited flows plus D-double-prime sparse Key-View acquisition paths.
- `manifest.json`: machine-readable v2.6 graph and audit metadata.

## Implementation rules

- Ticket 04B remains the next executable implementation ticket.
- Ticket 07A must fail conservatively on material ambiguity.
- Ticket 07B changes presentation/pointer routing only.
- Ticket 08 may use early geometry for planning/Prompt synthesis but cannot publish ownership or Masks.
- Ticket 08 must not require a tracker transition envelope.
- Ticket 08A starts with a bounded acquisition spike and may close v1 without a tracker.
- A later ADR is mandatory before tracker/hybrid production adoption.
- Confirmed correction does not automatically create reference memory.
- Key-View role and Mask backend never imply Lift Participation.
- Bootstrap support is not a hard Evidence Working Set upper bound.
- Ticket 14 is the reference correctness/quality gate; Ticket 20 owns production same-decision Evidence.
- Complete Contributor remains reference/debug only.
