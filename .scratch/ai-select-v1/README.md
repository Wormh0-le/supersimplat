# AI Select v1 — Implementation Ticket Graph v2.15

Status: **ready-for-agent planning graph — Final Spec v1.3 source-of-truth synchronized; current frontier Tickets 11 + 12**

Branch: `ai-select-v1`

## Authoritative source order

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`
3. ADR 0016
4. ADR 0017 where TargetGeometryHint / Prompt Support semantics are involved
5. ADR 0013 and ADR 0015 where not superseded
6. current Ticket acceptance criteria
7. implementation and tests

Final Spec v1.1, Amendments 001–005 and Final Spec v1.2 are historical only. ADR 0014 and DG-24 through DG-26 are historical where they conflict with ADR 0016 / Final Spec v1.3.

All 31 Ticket files contain a current mapping to Final Spec v1.3. Older spec names may remain only inside sections explicitly labeled historical provenance, historical implementation record, superseded surface, or migration input; they cannot be used as current closure sources.

## v2.14 review closures

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
- Every Ticket-local `Current Final Spec mapping` or equivalent current mapping resolves directly to Final Spec v1.3.
- TargetGeometryHint formal points are retained distinct first-hit support; Route B Prompt Support is independent from Geometry Quality.
- Old TargetGeometryHint schema/policy/digest identities fail closed and regenerate.
- Tickets 04C, 07, 02C, 07A, 07B, 08, 08A, 08B and 08C are implemented prerequisites, not current frontier work.
- Locked-GPU browser E2E for 08B and 08C completed on 2026-08-07 with no blocking issue reported.
- Ticket 09 is implemented: separated Gallery card states, read-only View RGB/Mask inspection, per-View read-only Camera Inspection, presentation-only filters, bounded thumbnails; no backend/fallback/tracker/ProposalDecision/Prompt-Brush/Negative-Box surface.
- Locked-GPU large-Gallery browser walkthrough for Ticket 09 passed on 2026-08-07.
- Tickets 11 and 12 are the current implementation frontier in parallel.

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
                                  ├──────────────► 08C reliable Prompt Support
                                  │                 (implemented; no blocker)
                                  ▼
                                09 Gallery
                              ┌────┴────┐
                              ▼         ▼
                             11        12
                              └────┬────┘
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
implemented prerequisites:
- 04C — SAM 3 Image migration
- 07 / 07A / 07B — Mask Review, Anchor acquisition, authoring/edit UX
- 02C — automatic runtime readiness
- 08 / 08A / 08B / 08C — target geometry, local views, per-View SAM acquisition, retained Prompt Support
- 09 — scalable Gallery, frustum sync and View camera/Mask inspection

ready now:
- 11 — User-added AIView Using Current or Adjusted Camera
- 12 — Explicit Mask Refresh + Evidence Dirty / Candidate Stale
```

Compatibility field:

```text
next_implementation_ticket = 11
```

Tickets 11 and 12 proceed in parallel. Ticket 14 requires both 11 and 12. Ticket 10 remains optional and off the core release path.

## One valid topological order

```text
01 → 02 → 03 → 04 → 05
→ 04A → 04B → 06 → 07 → 04C
→ 02C → 07A → 07B / 08 → 08A → 08B → 08C / 09
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
