# Final Spec v1.3 Walkthrough Coverage — v2.12

## Typical flows

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-01 | SAM 3 Image migration | `04B → 04C` | Current static path uses official SAM 3 Image and rejects Multiplex manifest/artifacts |
| WF-02 | Parallel current frontier | `04C ∥ 07` | Model migration and MaskReview correction proceed independently and converge at 07A/08B |
| WF-03 | Automatic availability | `04C + 02 → 02C` | Only Connecting/Available/Unavailable appears; current SAM 3 Image profile validates |
| WF-04 | Authoritative RGB inference | `04C/08A` | Provider resolves exact RGB bytes/ref and rejects digest-only input |
| WF-05 | One-click Anchor | `04C + 07 → 07A` | Up to three candidates appear; user chooses/refines; no automatic correctness claim |
| WF-06 | Box/multi-point Anchor | `04C + 07 → 07A` | Single candidate, basic validity, Accept/Edit/Confirm |
| WF-07 | Opaque previous-logits refinement | `04C → 07A` | Companion-local logits ref refines chosen candidate before Accept and returns one Mask |
| WF-08 | Floating palette | `07A → 07B` | Positive/Negative Point, Positive Box, Paint/Erase only; no stale hit region |
| WF-09 | Geometry hint | `07A → 08` | Anchor produces deterministic compact TargetGeometryHint without ownership |
| WF-10 | Local Views | `08` | 2–4 framed local Views render nonblank authoritative RGB |
| WF-11 | Per-View contracts | `08 + 04C → 08A` | RGB-bound Prompt/request/result/ref identities validate without backend registry |
| WF-12 | 3D-guided per-View Mask | `08A + 07 → 08B` | Projected Box/Points run SAM 3 Image single-mask inference and Mask Review |
| WF-13 | Gallery inspection | `08B → 09` | Render, Prompt, inference, Review, Participation and Evidence remain separate |
| WF-14 | User-added View | `07B + 09 → 11` | Same RGB/image instance path and manual correction behavior apply |
| WF-15 | Refresh lifecycle | `09 → 12` | Prompt regeneration and Mask Retry are explicit; refs invalidate correctly; no automatic Re-Lift |
| WF-16 | Lift and optional diagnostics | `11/12 → 14/13 → 15/16`, optional `14 → 10` | Ticket 13 owns readiness; Ticket 10 may enrich conflict diagnostics but does not block release |

## Error and recovery flows

| ID | Failure | Ticket path | Required retained state / recovery |
|---|---|---|---|
| EF-01 | old Multiplex manifest active | `04C → 02C` | Availability Unavailable; native editor usable; operator installs current manifest |
| EF-02 | historical 04A removed Prompt artifact | `04A → 04C/08A` | fail current schema validation; no Negative Box/Brush conversion |
| EF-03 | Ticket 06 legacy fallback invoked | `06 → 08B/21` | reject as current production route; preserve RGB/manual recovery |
| EF-04 | RGB digest has no resolvable bytes/ref | `04C/08A/08B` | reject before inference; preserve Prompt/RGB-ready record |
| EF-05 | RGB ref digest/dimensions mismatch | `08A/08B` | fail closed; no partial Mask/ref result |
| EF-06 | binary Brush supplied as logits | `04C/08A` | reject artifact; keep Prompt/Editing state; no inference |
| EF-07 | Companion Instance replaces logits owner | `02C/04C/12` | invalidate ref; rerun current Points/Box without mask_input |
| EF-08 | stale candidate/logits lineage | `04C/07A/12` | reject cross-RGB/adapter/candidate ref; preserve prior Stable Mask |
| EF-09 | one-click candidate ambiguity | `07A` | retain bounded candidates; choose/add Point/add Box/manual recovery |
| EF-10 | no Anchor candidate | `07A` | preserve RGB and Stable history; adjust Prompt/Retry/Manual Draw |
| EF-11 | geometry extraction unavailable | `08` | preserve Anchor; offer limited local/user-added View path |
| EF-12 | local View blank or invalid | `08` | reject/replace within bounded policy; preserve completed Views |
| EF-13 | per-View SAM technical failure | `08B/09` | preserve RGB/prior Stable Mask; Retry/manual/exclude; no automatic fallback |
| EF-14 | semantic per-View unavailable or Review | `07/08B/09` | no arbitrary Stable Mask; adjust Prompt/View/manual or keep Review Excluded |
| EF-15 | weak Gaussian support / Ticket 10 absent | `13/21` | Lift Readiness Limited/Not Ready; release/readiness still work without optional Ticket 10 |
| EF-16 | Evidence/Lift failure | `14/20/21` | preserve Views and Stable Masks; Candidate remains prior/stale; explicit Retry |

## Coverage result

- typical walkthroughs: 16;
- error walkthroughs: 16;
- current model migration covered: yes;
- authoritative RGB provider input covered: yes;
- opaque previous-logits lifecycle covered: yes;
- removed Prompt families covered: yes;
- geometry/local-view simplification covered: yes;
- Mask Review/Lift Readiness/Ticket 10 boundary covered: yes;
- current ready frontier covered: yes;
- P/N/V ownership boundary covered: yes.
