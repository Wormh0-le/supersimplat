# AI Select v1 — Implementation Ticket Graph v2.38

Status: **implemented core graph — Tickets through 22 closed**

Branch: `ai-select-v1`

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
3. ADR 0018
4. ADR 0016
5. ADR 0017 where TargetGeometryHint / Prompt Support semantics are involved
6. ADR 0013 and ADR 0015 where not superseded
7. current Ticket acceptance criteria
8. implementation and tests

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical only. ADR 0014 and DG-24 through DG-26 are historical where they conflict with ADR 0016 / Final Spec v1.3.

All 31 parent Ticket files contain a current mapping to Final Spec v1.3. Ticket
14A–14D and Ticket 16A–16G are execution stages under their respective parent
Tickets and do not create a second normative graph. Ticket 16B published the
accepted ADR 0018 and current-spec correction before its dependents; Tickets
16C–16G completed the accepted Inspector, shell, Work Area, Toolbar and
obsolete-control closure.

## Current review closures

- Static Anchor and Key-View segmentation use official SAM 3 Image instance interactivity.
- SAM 3.1 Multiplex/private tracker heads are removed from the current static path.
- v1 Prompt tools are Positive Point, Negative Point and one Positive Instance Box.
- Negative Box, Prompt Brush, Mask Constraints and Text are removed.
- Paint/Erase remain Editing Mask operations.
- Every provider request carries resolvable authoritative RGB, not only a digest.
- Actual previous logits remain Companion-local; browser state carries only an opaque same-Instance reference.
- Opaque refinement follows the sole current result while still in Prompt mode.
- Point, Box and refinement requests return at most one result, which enters Editing Mask automatically.
- Target geometry is one compact `TargetGeometryHintArtifact`.
- Initial planning schedules `4–8` bounded automatic Generated Views,
  excluding the Anchor and User-added Views; it is not a general
  adaptive/free-space planner.
- Generated Views synthesize Box/Points and use SAM 3 Image single-mask mode.
- Mask Review and Lift Readiness are separate; Ticket 13 is the sole visibility/readiness authority.
- Ticket 10 is an optional Evidence-conflict enhancement and does not block core release.
- Generic backend registry, Route B/C/D, sequence extensions and automatic Route-A fallback are removed from v1.
- Tickets 04C, 07, 02C, 07A, 07B, 08, 08A, 08B, 08C, 09, 11 and 12 are implemented prerequisites.
- Parent Ticket 14 is complete through 14A Evidence Contract & Working Set, 14B Reference Per-View P/N/V Evidence, 14C Multi-view Aggregation & Classification, and 14D Atomic Candidate Publication & Reference Validation.
- Ticket 13 is complete as the versioned Visible Evidence Coverage, View
  Diversity and Lift Readiness authority; Ticket 21 promotes its calibrated
  policy to the production Re-Lift path.
- Ticket 15 is complete as the pre-apply Candidate correction and explicit Re-Lift path.
- Ticket 16's fail-closed native Candidate application core is complete.
- Ticket 16A is implemented as the functional Candidate Overlay, Toolbar,
  Status Bar and Dock-cutover baseline.
- Ticket 16B is implemented as the single-result authoring, capability-truth
  and `4–8` initial automatic-View contract baseline.
- Tickets 16C–16G implemented the post-16A Inspector, canvas-first shell, Work
  Area, compact Toolbar and obsolete-control integration closure.
- Ticket 17 implemented exact-command Undo-and-Fix, complete target Restart,
  the global lifecycle menu, multi-object continuity and tool-switch disposal.
- Ticket 18 implemented target-scoped semantic suspension, read-only artifact
  retention and exact Native Undo recovery.
- Ticket 22 removed the browser ObjectSelectionSession lifecycle and public
  Companion session/Frame Set routes. Current Prompt capabilities contain only
  supported families; complete Contributor and Multiplex remain reference-only.

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
                      15 → 16 → 16A → 16B
                                       ├────────► 16C ─┐
                                       ├────────► 16D ─┴► 16E ─┐
                                       └────────► 16F ──────────┴► 16G
                                                                  │
                                                                  ▼
                                       17 → 18 → 19 → 20 → 21 → 22
```

Ticket 10 does not block Ticket 13, Ticket 21 or native application.

## Current implementation frontier

```text
implemented prerequisites:
- 04C, 07, 02C, 07A, 07B
- 08, 08A, 08B, 08C
- 09, 11, 12
- 14A–14D and parent Ticket 14
- 13 — Lift Readiness
- 15 — Candidate correction / Re-Lift
- 16 — Candidate → Native Set / Add / Remove / Intersect core
- 16A — AI View Dock + Candidate viewport presentation baseline
- 16B — single-result Mask contract + 4–8 initial Views
- 16C — Mask state truth + compact Inspector
- 16D — canvas-first shell + stable Navigator
- 16E — 2D Work Area + floating palette + explicit Re-Lift
- 16F — compact viewport Toolbar + non-destructive Anchor adjustment
- 16G — obsolete-control retirement + integrated visual closure
- 17 — exact Undo-and-Fix + Restart + multi-target/tool-switch lifecycle
- 18 — Scene mutation Suspended state + exact Undo recovery
- 19 — Large SceneSnapshot + authoritative RGB / Render Working Set hardening
- 20 — Same-decision GPU Evidence + artifact / working-set hardening
- 21 — Core failure, calibration and release hardening
- 22 — Legacy product/Contributor/SAM/Prompt contraction

current parent compatibility frontier:
- none — the Final Spec v1.3 core graph is implemented

current execution stage:
- none
```

Compatibility fields:

```text
next_implementation_ticket = none
next_implementation_subticket = none
```

Ticket 17 closes the implemented Ticket 16G Toolbar/presentation seam without
reintroducing retired 3D More/Restart or identical-input product Retry/planning
controls. Tickets 18 through 22 consume those lifecycle/render/Evidence seams
and are implemented. Ticket 10 remains optional and off the core release
path.

## One valid topological order

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B / 08 → 08A → 08B → 08C / 09
→ 11 → 12 → 14A → 14B → 14C → 14D → 13
→ 15 → 16 → 16A → 16B → 16C / 16D / 16F → 16E → 16G
→ 17 → 18 → 19 → 20 → 21 → 22

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
- no persistent planning controls, explicit product Retry commands or
  Proposal-choice UI after Ticket 16G closure;
- Complete Contributor remains reference/debug only.

See `docs/ai-select/TICKET-14-SPLIT.md`, the
`docs/ai-select/tickets/14A-*` through `14D-*` stage contracts and the
`docs/ai-select/tickets/16A-*` through `16G-*` presentation-stage contracts.
