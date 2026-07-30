# Final Spec v1.3 Walkthrough Coverage — v2.11

## Typical flows

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-01 | SAM 3 Image migration | `04B → 04C` | Current static path uses official SAM 3 Image and rejects Multiplex manifest/artifacts |
| WF-02 | Automatic availability | `04C + 02 → 02C` | Only Connecting/Available/Unavailable appears; current SAM 3 Image profile validates |
| WF-03 | One-click Anchor | `04C → 07A` | Up to three candidates appear; user chooses or refines; no automatic correctness claim |
| WF-04 | Box/multi-point Anchor | `04C → 07A` | Single candidate, basic validity, Accept/Edit/Confirm |
| WF-05 | Previous-logits refinement | `04C → 07A` | Added Point reuses exact same-image logits and returns one refined Mask |
| WF-06 | Floating palette | `07A → 07B` | Positive/Negative Point, Positive Box, Paint/Erase only; no stale hit region |
| WF-07 | Geometry hint | `07A → 08` | Anchor produces deterministic compact TargetGeometryHint without ownership |
| WF-08 | Local Views | `08` | 2–4 framed local Views render nonblank authoritative RGB |
| WF-09 | Per-View contracts | `08 + 04C → 08A` | Prompt/result/logits identities validate without backend registry |
| WF-10 | 3D-guided per-View Mask | `08A + 07 → 08B` | Projected Box/Points run SAM 3 Image single-mask inference and Mask Review |
| WF-11 | Gallery inspection | `08B → 09` | Render, Prompt, inference, Review, Participation and Evidence remain separate |
| WF-12 | User-added View | `07B + 09 → 11` | Same image instance path and manual correction behavior apply |
| WF-13 | Refresh lifecycle | `09 → 12` | Prompt regeneration and Mask Retry are explicit; no automatic Re-Lift |
| WF-14 | Lift and native apply | `11/12 → 14/13 → 15/16` | Only Included Stable Masks contribute P/N/V before explicit native operation |

## Error and recovery flows

| ID | Failure | Ticket path | Required retained state / recovery |
|---|---|---|---|
| EF-01 | old Multiplex manifest active | `04C → 02C` | Availability Unavailable; native editor usable; install/select current manifest operator-side |
| EF-02 | old Negative Box/Mask Constraint artifact | `04C/08A` | fail schema validation; no conversion to Points |
| EF-03 | binary Brush supplied as logits | `04C/08A` | reject artifact; keep Prompt/Editing state; no inference |
| EF-04 | stale previous logits | `04C/12` | reject cross-RGB/adapter/candidate lineage; refine from current result |
| EF-05 | one-click candidate ambiguity | `07A` | retain bounded candidates; choose/add Point/add Box/manual recovery |
| EF-06 | no Anchor candidate | `07A` | preserve RGB and Stable history; adjust Prompt/Retry/Manual Draw |
| EF-07 | geometry extraction unavailable | `08` | preserve Anchor; offer limited local/user-added View path |
| EF-08 | local View blank or invalid | `08` | reject/replace within bounded policy; preserve completed Views |
| EF-09 | per-View SAM technical failure | `08B/09` | preserve RGB/prior Stable Mask; Retry/manual/exclude; no automatic fallback |
| EF-10 | semantic per-View unavailable | `08B/09` | no Stable Mask; adjust Prompt/View/manual; not service failure |
| EF-11 | Mask Review clipping/fragmentation | `07/08B` | Auto Review Excluded; inspect/refine/Paint/Confirm as-is where allowed |
| EF-12 | weak Gaussian support | `13` | Lift Readiness Limited/Not Ready; Generate More or add Included View; Mask quality unchanged |
| EF-13 | stale refresh result | `12` | discard result; prior Stable/Evidence/Candidate retained |
| EF-14 | Evidence/Lift failure | `14/20/21` | preserve Views and Stable Masks; Candidate remains prior/stale; explicit Retry |

## Coverage result

- typical walkthroughs: 14;
- error walkthroughs: 14;
- current model migration covered: yes;
- removed Prompt families covered: yes;
- geometry/local-view simplification covered: yes;
- Mask Review/Lift Readiness separation covered: yes;
- P/N/V ownership boundary covered: yes.
