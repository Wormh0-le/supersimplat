# Final Spec v1.1 Walkthrough Coverage — v2.3

## Typical Flows A–I — inherited product workflows

| ID | Flow | Ticket path |
|---|---|---|
| WF-A | Fast single-object | `02 → 03/04/05 → 04A Prompt/Proposal → 07A ranking/accept/edit/confirm → 06/07 → 08/09 → 11/12 → 14 → 10/13 → 15 → 16` |
| WF-B | Adjust Anchor | `02 → 03 RGB-only final preview + true Retry → 04A/07A Prompt/Mask authoring → 05 Confirm` |
| WF-C | Add a missing user View | `09 → 11 → Mask publication → 12 Evidence dirty → 14/15 → 13` |
| WF-D | Redraw bad Mask from scratch | `09 → 04A explicit Paint/Erase mode → 07A Confirm → 12 Evidence dirty → 15 explicit Re-Lift` |
| WF-E | Modify reference then Repropagate | `04A/07A → 05 Confirm → 12 explicit Repropagate → 07/10 reassessment → 13 → 15` |
| WF-F | Select multiple objects | `16 → 17 Restart → 02... → 16 → 17` |
| WF-G | Candidate structural error | `14/15 → 09/07/11/08 correction → 12 dirty → 15` |
| WF-H | Fix after Candidate applied | `16 → 17 Undo and Fix → 15` |
| WF-I | Scene mutation + Undo | `18 Suspended with Evidence/Candidate retained → exact Native Undo → resume` |

## Architecture walkthroughs

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-J | RGB Ready without Mask/Evidence | `03/06/11` | View displays authoritative RGB with Mask=None or pending and Evidence=not-requested; no Contributor gate |
| WF-K | Stable Mask → Evidence dirty → explicit Lift | `04/05/07A/11 → 12 → 14/15` | Only Confirm Mask invalidates exact dependent Evidence; Candidate changes only after explicit atomic Re-Lift |
| WF-L | Reference Evidence PoC → production Direct Evidence | `14 → 19 → 20 → 21` | P/N/V policy is validated before same-decision CUDA productionization and calibration |
| WF-M | Spatial scene with local Evidence writes | `19 → 20` | Full Render Working Set preserves occlusion; Evidence Working Set limits writes only |
| WF-N | Three-Stage Anchor Mask | `04A → 07A → 05/07 integration → 08` | Explicit Point/Box/mask/Text capabilities produce bounded proposals; 2D-first ranking selects or reports ambiguity; only Confirm publishes Stable Anchor; planner starts from resolved Anchor |

## WF-N detailed walkthrough

```text
Authoritative Anchor RGB
→ select Prompt tool
→ author Point / Box / mask constraint / supported Text
→ PromptState revision
→ bounded AutoMaskProposalSet
→ 2D-first ProposalDecision
    ├── selected  → Accept → Editing Mask
    ├── ambiguous → choose/refine/manual edit
    └── unavailable → refine/Retry/manual Empty→Paint
→ Confirm Mask
→ Stable Mask
→ Ticket 07 ViewAssessment / Participation
→ Confirm Anchor
→ Ticket 08 valid-pose adaptive planning
```

Required assertions:

- Prompt and Paint histories are separate.
- Model score is not a correctness probability or sole selector.
- Optional Gaussian support is not ownership Evidence.
- Prior Stable Mask/Evidence/Candidate remain current until replacement Confirm.
- Generated View automatic publication is not silently replaced by the Anchor pipeline.

## Reverse outcome-to-prerequisite validation

Starting from a valid native selection operation:

```text
Native operation (16)
← current non-stale Candidate (15/14)
← calibrated aggregation/classification and readiness (14/13/21)
← version-bound per-view P/N/V (14 reference, 20 production)
← Included Stable View Annotation (04–12)
← resolved Anchor Prompt/proposal and Stable confirmation (04A/07A/05)
← authoritative RGB + exact CameraBinding (02/03/06/11)
← conservative Render Working Set + Stable IDs (01/19)
```

No final outcome depends on complete per-pixel Contributor publication. Reference Contributor is reachable only as a validation/diagnostic side path from Tickets 14/19/20/22.

## Error / degradation flows

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion Offline/incompatible | 02/21 | Native editor unaffected; reconnect/settings recovery |
| ERR-2 | Current RGB/Preview failure | 03/21 | Keep last valid preview as stale/not-current; true new-attempt Retry |
| ERR-3 | Mask/model technical failure | 04A/07A/21 | Keep View/RGB/Prompt/prior Stable/edit state; Retry or manual recovery |
| ERR-4 | View Render Failure | 06/08/11/21 | Keep failed View record; retry / replacement / exclude |
| ERR-5 | Evidence production failure | 14/20/21 | Keep RGB/View/Stable Mask/Gallery/previous Candidate; retry Lift / inspect Mask / exclude / adjust-add View |
| ERR-6 | Lifting/aggregation failure | 14/15/21 | Keep stable inputs and previous Candidate; no partial replacement |
| ERR-7 | Repropagate failure | 12/21 | Keep old Stable Masks and matching Evidence/Candidate; no partial publication |
| ERR-8 | Reference Contributor failure | 03/14/20/22 | Diagnostic/reference path fails only; valid RGB and Direct Evidence remain valid |
| ERR-9 | Cached failure replay vs explicit Retry | 03/21 | Same attempt replay idempotent; explicit Retry creates a new actual attempt |
| ERR-10 | Scene Chunk Miss / incomplete Render Working Set | 19/20/21 | No partial Ready RGB/Evidence; load chunks or full fallback, then retry |
| ERR-11 | OOM/cancellation | 04A/20/21 | No partial proposal/Evidence/Candidate; old valid artifacts retained; late results rejected |
| ERR-12 | Scene dependency mutation | 18 | Context Suspended/read-only; exact Undo or Restart |
| ERR-13 | Proposal ambiguous | 07A | Preserve alternatives, RGB, Prompt, prior Stable; choose/refine/Paint; no silent Stable publication |
| ERR-14 | Proposal unavailable | 04A/07A | Preserve RGB/Prompt/prior Stable; Retry/refine/manual Empty→Paint; not Render Failed |
| ERR-15 | Generated camera outside valid indoor observation region | 08 | Reject candidate before gain ranking; use bounded replacement/local fallback or stop Limited; no invalid View publication |

## Closure assertions

- RGB publication and Camera Inspection never require complete Contributor or Evidence.
- Prompt Authoring and direct Pixel Editing are separate explicit modes.
- ProposalDecision and ViewAssessmentPolicy are separate.
- Only Confirm Mask replaces Stable Mask and invalidates dependent Evidence.
- Ticket 07A is the Three-Stage Anchor completion gate; Ticket 08 follows it.
- Planner camera validity is evaluated before marginal gain; outside-room candidates cannot win by gain alone.
- Reference P/N/V precedes production same-decision CUDA.
- Evidence/reference Contributor failure cannot be misreported as RGB Render Failure.
- Every destructive/recompute action states retained artifacts and recovery.