# Final Spec v1.1 Walkthrough Coverage

## Typical Flows A–I — inherited product workflows

| ID | Flow | Ticket path |
|---|---|---|
| WF-A | Fast single-object | `02 → 04/05 → 06 (RGB + Initial Auto Mask) → 07 → 08/09 → 11/12 → 14 reference Evidence/Lift → 10/13 → 15 → 16` |
| WF-B | Adjust Anchor | `02 → 03 RGB-only final preview + true Retry → 05` |
| WF-C | Add a missing user View | `09 → 11 → Mask publication → 12 Evidence dirty → 14/15 → 13` |
| WF-D | Redraw bad Mask from scratch | `09 → 05 Mask editor → 12 Evidence dirty → 15 explicit Re-Lift` |
| WF-E | Modify reference then Repropagate | `05 → 12 explicit Repropagate → 07/10 reassessment → 13 → 15` |
| WF-F | Select multiple objects | `16 → 17 Restart → 02... → 16 → 17` |
| WF-G | Candidate structural error | `14/15 → 09/07/11/08 correction → 12 dirty → 15` |
| WF-H | Fix after Candidate applied | `16 → 17 Undo and Fix → 15` |
| WF-I | Scene mutation + Undo | `18 Suspended with Evidence/Candidate retained → exact Native Undo → resume` |

## v1.1 architecture walkthroughs

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-J | RGB Ready without Mask/Evidence | `03/06/11` | View displays authoritative RGB with Mask=None or pending and Evidence=not-requested; no Contributor gate |
| WF-K | Stable Mask → Evidence dirty → explicit Lift | `04/05/11 → 12 → 14/15` | Confirm Mask invalidates only dependent per-view Evidence; Candidate changes only after explicit atomic Re-Lift |
| WF-L | Reference Evidence PoC → production Direct Evidence | `14 → 19 → 20 → 21` | P/N/V policy is validated before same-decision CUDA productionization and calibration |
| WF-M | Spatial scene with local Evidence writes | `19 → 20` | Full Render Working Set preserves occlusion; Evidence Working Set limits writes only |

## Reverse outcome-to-prerequisite validation

Starting from a valid native selection operation and walking backward:

```text
Native operation (16)
← current non-stale Candidate (15/14)
← calibrated aggregation/classification and readiness (14/13/21)
← version-bound per-view P/N/V (14 reference, 20 production)
← Included Stable View Annotation (04–12)
← authoritative RGB + exact CameraBinding (02/03/06/11)
← complete conservative Render Working Set + Stable IDs (01/19)
```

No final outcome depends on complete per-pixel Contributor publication. The reference Contributor backend is reachable only as a validation/diagnostic side path from Tickets 14/19/20/22.

## Error / degradation flows

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion Offline/incompatible | 02/21 | Native editor unaffected; reconnect/settings recovery |
| ERR-2 | Current RGB/Preview failure | 03/21 | Keep last valid preview as stale/not-current; true new-attempt Retry |
| ERR-3 | Mask generation failure | 06/07/11/21 | Keep View/RGB; retry auto / manual / exclude |
| ERR-4 | View Render Failure | 06/08/11/21 | Keep failed View record; retry / replacement / exclude |
| ERR-5 | Evidence production failure | 14/20/21 | Keep RGB/View/Stable Mask/Gallery/previous Candidate; retry Lift / inspect Mask / exclude / adjust-add View |
| ERR-6 | Lifting/aggregation failure | 14/15/21 | Keep stable inputs and previous Candidate; no partial replacement |
| ERR-7 | Repropagate failure | 12/21 | Keep old Stable Masks and matching Evidence/Candidate; no partial publication |
| ERR-8 | Reference Contributor failure | 03/14/20/22 | Diagnostic/reference path fails only; valid RGB and successful Direct Evidence remain valid |
| ERR-9 | Cached failure replay versus explicit Retry | 03/21 | Same attempt replay is idempotent; explicit Retry creates a new actual attempt for same CameraBinding |
| ERR-10 | Scene Chunk Miss / incomplete Render Working Set | 19/20/21 | No partial Ready RGB/Evidence; load missing chunks or full-working-set fallback, then retry |
| ERR-11 | OOM/cancellation | 20/21 | No partial Evidence/Candidate; old valid artifacts retained; late results rejected by identity |
| ERR-12 | Scene dependency mutation | 18 | Context Suspended/read-only with artifacts retained; exact Undo or Restart recovery |

## Closure assertions

- RGB publication and Camera Inspection never require complete Contributor or Evidence.
- Stable Mask publication and Evidence invalidation are independent and version-bound.
- Cross-view assessment and Coverage consume the Evidence contract only after Ticket 14 defines it.
- Production same-decision Evidence occurs only after reference PoC and large-scene render-path hardening.
- Evidence/reference Contributor failure cannot be misreported as RGB Render Failure.
- Every destructive/recompute action states retained artifacts and recovery.