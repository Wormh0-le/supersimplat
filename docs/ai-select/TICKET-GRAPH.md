# AI Select v1 — Implementation Ticket Graph v2.26

Status: **active implementation graph — Final Spec v1.3 synchronized; Ticket 16 core is implemented and Ticket 16A is current**

Branch: `ai-select-v1`

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
3. ADR 0016
4. ADR 0017 where TargetGeometryHint / Prompt Support semantics are involved
5. ADR 0013 and ADR 0015 where not superseded
6. current Ticket acceptance criteria
7. implementation and tests

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical only. ADR 0014 and DG-24 through DG-26 are historical where they conflict with ADR 0016 / Final Spec v1.3.

All 31 parent Ticket files contain a current mapping to Final Spec v1.3. Ticket 14A–14D and Ticket 16A are execution stages under their respective parent Tickets and do not create a second normative graph.

## Current review closures

- Static Anchor and Key-View segmentation use official SAM 3 Image instance interactivity.
- SAM 3.1 Multiplex/private tracker heads are removed from the current static path.
- v1 Prompt tools are Positive Point, Negative Point and one Positive Instance Box.
- Negative Box, Prompt Brush, Mask Constraints and Text are removed.
- Paint/Erase remain Editing Mask operations.
- Every provider request carries resolvable authoritative RGB, not only a digest.
- Actual previous logits remain Companion-local; browser state carries only an opaque same-Instance reference.
- Candidate refinement occurs before Accept while still in Prompt mode.
- Single Positive Point may return up to three candidates; Box/multiple Points/refinement return one.
- Target geometry is one compact `TargetGeometryHintArtifact`.
- Key Views are 2–4 bounded local observations, not a general adaptive/free-space planner.
- Generated Views synthesize Box/Points and use SAM 3 Image single-mask mode.
- Mask Review and Lift Readiness are separate; Ticket 13 is the sole visibility/readiness authority.
- Ticket 10 is an optional Evidence-conflict enhancement and does not block core release.
- Generic backend registry, Route B/C/D, sequence extensions and automatic Route-A fallback are removed from v1.
- Tickets 04C, 07, 02C, 07A, 07B, 08, 08A, 08B, 08C, 09, 11 and 12 are implemented prerequisites.
- Parent Ticket 14 is complete through 14A Evidence Contract & Working Set, 14B Reference Per-View P/N/V Evidence, 14C Multi-view Aggregation & Classification, and 14D Atomic Candidate Publication & Reference Validation.
- Ticket 13 is complete as the versioned reference/calibration Visible Evidence Coverage, View Diversity and Lift Readiness path.
- Ticket 15 is complete as the pre-apply Candidate correction and explicit Re-Lift path.
- Ticket 16's fail-closed native Candidate application core is complete.
- Ticket 16A is the current post-closure presentation stage for the real
  Candidate Overlay, fixed Toolbar, Status Bar and Dock cutover.

## Dependency graph

```text
01 CurrentTargetContext
 │
 ▼
02 AI Select shell + authoritative Anchor RGB
 ├───────────────────────┐
 ▼                       ▼
03 Camera Inspection     04 Anchor Mask lifecycle
 └──────────┬────────────┘
            ▼
05 Anchor editing / Confirm / Restart
 ├──────────────────────────────┐
 ▼                              ▼
04A historical Prompt           06 progressive RGB tracer
foundation                       │
 │                               ▼
 ▼                              07 MaskReview correction
04B historical Multiplex         │
visual adapter                   │
 │                               │
 ▼                               │
04C SAM 3 Image                  │
+ Prompt/RGB/ref migration       │
 ├──────────────► 02C readiness  │
 └──────────────────┬────────────┘
                    ▼
07A simplified Anchor acquisition
 ├──────────────────────────────┐
 ▼                              ▼
07B Point/Box +                 08 TargetGeometryHint
Paint/Erase palette                + local Key Views
                                    │
                                    ▼
                                08A compact image
                                instance contracts
                                    │
                                    ▼
                                08B per-View SAM 3 Image
                                  ├──────────────► 08C reliable Prompt Support
                                  │
                                  ▼
                                09 Gallery
                              ┌────┴────┐
                              ▼         ▼
                             11        12
                              └────┬────┘
                                   ▼
                       14A Evidence contract + Working Set
                                   │
                                   ▼
                       14B Reference per-View P/N/V
                                   │
                                   ▼
                       14C Aggregation + classification
                                   │
                                   ▼
                       14D Atomic Candidate publication
                              ┌────┴────┐
                              ▼         ▼
                       10 optional      13 Lift Readiness
                       diagnostics       │
                                         ▼
                      15 → 16 → 16A → 17 → 18 → 19 → 20 → 21 → 22
```

Ticket 10 does not block Ticket 13, Ticket 21 or native application.

## Current implementation frontier

```text
implemented prerequisites:
- 04C — SAM 3 Image migration
- 07 / 07A / 07B — Mask Review, Anchor acquisition, authoring/edit UX
- 02C — automatic runtime readiness
- 08 / 08A / 08B / 08C — target geometry, local views, per-View SAM acquisition, retained Prompt Support
- 09 — scalable Gallery, frustum sync and View camera/Mask inspection
- 11 — user-added AIView using current or adjusted camera
- 12 — Explicit Mask Refresh + Evidence Dirty / Candidate Stale
- 14A — Evidence Contract & Working Set
- 14B — Reference Per-View P/N/V Evidence
- 14C — Multi-view Aggregation & Classification
- 14D — Atomic Candidate Publication & Reference Validation
- 13 — Visible Evidence Coverage + View Diversity + Lift Readiness
- 15 — Candidate correction + explicit Evidence-aware Re-Lift
- 16 — Candidate → Native Set / Add / Remove / Intersect core

current parent compatibility frontier:
- 16 — Native Candidate operations

current execution stage:
- 16A — AI View Dock + Candidate viewport presentation

follows 16A:
- 17 — Applied Undo-and-Fix + complete Restart + multi-object/tool-switch lifecycle

current implementation stage:
- 16A — post-closure Ticket 16 presentation integration
```

Compatibility fields:

```text
next_implementation_ticket = 16
next_implementation_subticket = 16A
```

Ticket 16 is the current parent compatibility frontier with 16A as its sole
active execution stage. Ticket 16's application core, Ticket 15 and their
Ticket 13 / parent Ticket 14 prerequisites remain implemented. Ticket 17
follows 16A. Ticket 10 remains optional and off the core release path.

## One valid topological order

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B / 08 → 08A → 08B → 08C / 09
→ 11 → 12 → 14A → 14B → 14C → 14D → 13
→ 15 → 16 → 16A → 17 → 18 → 19 → 20 → 21 → 22

10 may execute any time after parent Ticket 14 + 09 + 07 and is not on the core release path.
```

## Scope boundaries

- no static Multiplex/video tracker path;
- no Negative Box or Prompt Brush;
- no binary Brush-to-logits conversion;
- no raw logits tensor in browser state;
- no digest-only unresolved RGB inference request;
- no generic candidate cluster/ranker;
- no adaptive room/free-space planner;
- no backend registry/Route C-D seam;
- no automatic route fallback;
- no visibility-readiness claims outside Ticket 13;
- no ownership before Included Stable Masks → P/N/V;
- no Candidate provenance browser or Gaussian Evidence inspector in Ticket 14D;
- no Candidate Overlay membership stored in Native SplatState or EditHistory;
- no duplicate Native Candidate Operations in both Dock and Toolbar after Ticket 16A closure;
- Complete Contributor remains reference/debug only.

See `docs/ai-select/TICKET-14-SPLIT.md` and the `docs/ai-select/tickets/14A-*` through `14D-*` stage contracts.
