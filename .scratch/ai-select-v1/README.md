# AI Select v1 — Implementation Ticket Graph v2.11

Status: **ready-for-agent planning graph — Ticket 04C is the next implementation gate**

Branch: `ai-select-v1`

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`
3. ADR 0016
4. ADR 0013 and ADR 0015 where not superseded
5. current Ticket acceptance criteria
6. implementation and tests

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical only. ADR 0014 and DG-24 through DG-26 are historical where they conflict with ADR 0016 / Final Spec v1.3.

## v2.11 architecture correction

- Static Anchor and Key-View segmentation use official SAM 3 Image instance interactivity.
- SAM 3.1 Multiplex/private tracker heads are removed from the current static path.
- v1 Prompt tools are Positive Point, Negative Point and one Positive Instance Box.
- Negative Box, Prompt Brush, Mask Constraints and Text are removed.
- Previous logits are internal same-image refinement state.
- Single positive Point may return up to three candidates; Box/multiple Points/refinement return one.
- Anchor ambiguity is resolved by direct candidate choice, not a general cluster/ranker.
- Target geometry is one compact `TargetGeometryHintArtifact`.
- Key Views are 2–4 bounded local observations, not a general adaptive/free-space planner.
- Generated Views synthesize Box/Points and use SAM 3 Image single-mask mode.
- Mask Review and Lift Readiness are separate.
- Generic backend registry, Route B/C/D, sequence extensions and automatic Route-A fallback are removed from v1.

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
04A Prompt foundation           06 Progressive Generated RGB
 │                              │
 ▼                              ▼
04B historical Multiplex        07 MaskReview + Participation
 visual adapter baseline        │
 │                              │
 ▼                              │
04C SAM 3 Image Adapter         │
 + Prompt Contract Migration    │
 ├──────────────► 02C Automatic Readiness
 │
 └──────────────────┬───────────┘
                    ▼
07A Simplified Anchor Acquisition
 ├──────────────────────────────┐
 ▼                              ▼
07B Floating Point/Box +        08 TargetGeometryHint
Paint/Erase Palette                 + Local Key Views
                                    │
                                    ▼
                                08A Compact Image
                                Instance Contracts
                                    │
                                    ▼
                                08B 3D-guided
                                Per-View SAM 3 Image
                                    │
                                    ▼
                                09 Gallery / Inspection
                                 ├────────────┐
                                 ▼            ▼
                                11           12
                                 └──────┬─────┘
                                        ▼
                                       14 P/N/V + Candidate
                                     ┌──┴──┐
                                     ▼     ▼
                                    10    13 Lift Readiness
                                     └──┬──┘
                                        ▼
                                       15 → 16 → 17 → 18 → 19 → 20 → 21 → 22
```

## Current topological order

```text
01 → 02 → 03 → 04 → 05 → 04A → 04B → 04C → 02C
→ 06 → 07 → 07A → 07B / 08 → 08A → 08B → 09
→ 11 → 12 → 14 → 10 / 13 → 15 → 16 → 17 → 18
→ 19 → 20 → 21 → 22
```

04C and 06/07 are independent completed-history branches until their dependencies converge at 07A/08B. 07B and 08 run in parallel after 07A.

## Current implementation frontier

```text
next_implementation_ticket = 04C
```

04B is not reopened. It remains the historical implementation baseline and source of migration regressions.

After 04C:

1. complete 02C readiness against the new SAM 3 Image manifest;
2. correct Ticket 07 MaskReview semantics;
3. complete simplified 07A Anchor acquisition;
4. proceed with 07B and 08 in parallel;
5. then 08A → 08B → 09.

## Scope boundaries

- no static Multiplex/video tracker path;
- no Negative Box or Prompt Brush;
- no binary Brush-to-logits conversion;
- no generic candidate cluster/ranker;
- no adaptive room/free-space planner;
- no backend registry/Route C-D seam;
- no automatic route fallback;
- no ownership before Included Stable Masks → P/N/V;
- Complete Contributor remains reference/debug only.
