# AI Select v1 — Implementation Ticket Graph v2.12

Status: **ready-for-agent planning graph**

Branch: `ai-select-v1`

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`
3. ADR 0016
4. ADR 0013 and ADR 0015 where not superseded
5. current Ticket acceptance criteria
6. implementation and tests

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical only. ADR 0014 and DG-24 through DG-26 are historical where they conflict with ADR 0016 / Final Spec v1.3.

## v2.12 review closures

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
- Ticket 04A and Ticket 06 old Prompt/fallback language is explicitly historical.

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
                                08B per-View
                                SAM 3 Image
                                    │
                                    ▼
                                09 Gallery
                                 ├────────────┐
                                 ▼            ▼
                                11           12
                                 └──────┬─────┘
                                        ▼
                                       14 P/N/V + Candidate
                                      ┌─┴──────────┐
                                      ▼            ▼
                                10 optional       13 Lift Readiness
                                diagnostics        │
                                                   ▼
                                15 → 16 → 17 → 18 → 19 → 20 → 21 → 22
```

Ticket 10 does not block Ticket 13, Ticket 21 or native application.

## Current implementation frontier

```text
ready now:
- 04C — critical SAM 3 Image migration gate
- 07  — parallel MaskReview policy correction
```

Compatibility field:

```text
next_implementation_ticket = 04C
```

After 04C, Ticket 02C may proceed independently. Ticket 07A begins after both 04C and 07. Ticket 07B and 08 then proceed in parallel.

## One valid topological order

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B / 08 → 08A → 08B → 09
→ 11 → 12 → 14 → 13 → 15 → 16 → 17 → 18
→ 19 → 20 → 21 → 22

10 may execute any time after 14 + 09 + 07 and is not on the core release path.
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
- Complete Contributor remains reference/debug only.
