# Final Spec v1.1 Walkthrough Coverage — v2.4

## Typical Flows A–I — inherited product workflows

| ID | Flow | Ticket path |
|---|---|---|
| WF-A | Fast single-object | `02 → 03/04/05 → 04A Prompt/Proposal → 04B visual prompts → 07A ranking/accept/edit/confirm → 07B palette → 06/07 → 08/09 → 11/12 → 14 → 10/13 → 15 → 16` |
| WF-B | Adjust Anchor | `02 → 03 RGB-only final preview + true Retry → 04A/04B/07A Prompt/Mask authoring → 07B no-blind-spot interaction → 05 Confirm` |
| WF-C | Add a missing user View | `09 → 11 → Mask publication → 12 Evidence dirty → 14/15 → 13` |
| WF-D | Redraw bad Mask from scratch | `09 → 04A explicit Paint/Erase mode → 07A Confirm → 12 Evidence dirty → 15 explicit Re-Lift` |
| WF-E | Modify reference then Repropagate | `04A/04B/07A → 05 Confirm → 12 explicit Repropagate → 07/10 reassessment → 13 → 15` |
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
| WF-N | Three-Stage Anchor Mask | `04A → 04B → 07A → 05/07 integration → 07B → 08` | Enabled visual prompts produce bounded proposals; 2D-first ranking selects or reports ambiguity; only Confirm publishes Stable Anchor; palette preserves full editability; planner starts from resolved Anchor |
| WF-O | Visual Prompt Adapter | `04A → 04B → 07A` | Box/Mask constraints compile deterministically through truthful capabilities; unsupported families/combinations fail closed; ranking receives prompt-consistency facts |
| WF-P | Floating Prompt/Edit Palette | `07A fitted rect → 07B → 08` | Palette drags/snaps/collapses/hides inside fitted image; old covered area becomes immediately editable; Target Context reset restores default |

## WF-N detailed walkthrough

```text
Authoritative Anchor RGB
→ select Prompt tool
→ author Point / enabled Box / enabled mask constraint / supported Text
→ PromptState revision
→ bounded materially distinct AutoMaskProposalSet
→ 2D-first ProposalDecision
    ├── selected  → Accept → Editing Mask
    ├── ambiguous → choose/refine/manual edit
    └── unavailable → refine/Retry/manual Empty→Paint
→ Confirm Mask
→ Stable Mask
→ Ticket 07 ViewAssessment / Participation
→ Confirm Anchor
→ Ticket 07B no-blind-spot palette closure
→ Ticket 08 valid-pose adaptive planning
```

Required assertions:

- Prompt and Paint histories are separate.
- Model score is not a correctness probability or sole selector.
- A suspicious single candidate is not silently selected merely because it is unique.
- Optional Gaussian support is not ownership Evidence.
- Prior Stable Mask/Evidence/Candidate remain current until replacement Confirm.
- Generated View automatic publication is not silently replaced by the Anchor pipeline.

## WF-O detailed walkthrough

```text
PromptState with Point + Box / Mask Constraint
→ 04B capability/compiler validation
    ├── supported combination → locked adapter inference
    └── unsupported combination → fail closed before inference
→ bounded proposal alternatives + per-family consistency diagnostics
→ 07A hard consistency and ranking
```

Required assertions:

- Positive and negative support are advertised separately.
- No prompt is silently dropped.
- Box/Mask constraints are not silently converted to Points.
- Text remains disabled unless a later locked adapter enables it.
- Retry and stale-result identity include capability/compiler version.

## WF-P detailed walkthrough

```text
fitted authoritative image
→ expanded palette inside image rect
→ drag / edge snap / collapse
→ edit target touching edge or corner
→ Space held: palette hidden and non-hit-testable
→ Space released: prior palette state restored
→ Restart Target: default position and expanded/collapsed default restored
```

Required assertions:

- RGB/Mask/Prompt/pointer mapping never changes because of palette motion.
- The palette itself intercepts input only at its current visible bounds.
- Previous palette position immediately accepts Prompt/Edit input.
- Collapse removes the expanded hit region.
- Hidden opacity-zero elements do not retain pointer events.
- Palette state never enters PromptState, Mask history, Evidence, or Candidate identity.

## Reverse outcome-to-prerequisite validation

Starting from a valid native selection operation:

```text
Native operation (16)
← current non-stale Candidate (15/14)
← calibrated aggregation/classification and readiness (14/13/21)
← version-bound per-view P/N/V (14 reference, 20 production)
← Included Stable View Annotation (04–12)
← valid-pose Generated Views (08)
← no-blind-spot fitted-image authoring (07B)
← resolved Anchor Prompt/proposal and Stable confirmation (04B/07A/05)
← Prompt/proposal foundation (04A)
← authoritative RGB + exact CameraBinding (02/03/06/11)
← conservative Render Working Set + Stable IDs (01/19)
```

No final outcome depends on complete per-pixel Contributor publication. Reference Contributor is reachable only as a validation/diagnostic side path from Tickets 14/19/20/22.

## Error / degradation flows

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion Offline/incompatible | 02/21 | Native editor unaffected; reconnect/settings recovery |
| ERR-2 | Current RGB/Preview failure | 03/21 | Keep last valid preview as stale/not-current; true new-attempt Retry |
| ERR-3 | Mask/model technical failure | 04A/04B/07A/21 | Keep View/RGB/Prompt/prior Stable/edit state; Retry or manual recovery |
| ERR-4 | View Render Failure | 06/08/11/21 | Keep failed View record; retry / replacement / exclude |
| ERR-5 | Evidence production failure | 14/20/21 | Keep RGB/View/Stable Mask/Gallery/previous Candidate; retry Lift / inspect Mask / exclude / adjust-add View |
| ERR-6 | Lifting/aggregation failure | 14/15/21 | Keep stable inputs and previous Candidate; no partial replacement |
| ERR-7 | Repropagate failure | 12/21 | Keep old Stable Masks and matching Evidence/Candidate; no partial publication |
| ERR-8 | Reference Contributor failure | 03/14/20/22 | Diagnostic/reference path fails only; valid RGB and Direct Evidence remain valid |
| ERR-9 | Cached failure replay vs explicit Retry | 03/21 | Same attempt replay idempotent; explicit Retry creates a new actual attempt |
| ERR-10 | Scene Chunk Miss / incomplete Render Working Set | 19/20/21 | No partial Ready RGB/Evidence; load chunks or full fallback, then retry |
| ERR-11 | OOM/cancellation | 04A/04B/20/21 | No partial proposal/Evidence/Candidate; old valid artifacts retained; late results rejected |
| ERR-12 | Scene dependency mutation | 18 | Context Suspended/read-only; exact Undo or Restart |
| ERR-13 | Proposal ambiguous | 07A | Preserve alternatives, RGB, Prompt, prior Stable; choose/refine/Paint; no silent Stable publication |
| ERR-14 | Proposal unavailable | 04A/04B/07A | Preserve RGB/Prompt/prior Stable; Retry/refine/manual Empty→Paint; not Render Failed |
| ERR-15 | Generated camera outside valid indoor observation region | 08 | Reject candidate before gain ranking; use bounded replacement/local fallback or stop Limited; no invalid View publication |
| ERR-16 | Floating palette leaves stale blind region or stuck hidden state | 07B | Remove stale hit box immediately; restore prior visible state on keyup/blur; preserve Prompt/Mask artifacts and continue editing |

## Closure assertions

- RGB publication and Camera Inspection never require complete Contributor or Evidence.
- Prompt Authoring and direct Pixel Editing are separate explicit modes.
- Real Box/Mask capabilities are truthful and unsupported combinations fail closed.
- ProposalDecision and ViewAssessmentPolicy are separate.
- Only Confirm Mask replaces Stable Mask and invalidates dependent Evidence.
- Ticket 07A remains the Three-Stage Anchor algorithm completion gate.
- Ticket 07B removes permanent fitted-image toolbar blind spots before Ticket 08.
- Planner camera validity is evaluated before marginal gain; outside-room candidates cannot win by gain alone.
- Reference P/N/V precedes production same-decision CUDA.
- Evidence/reference Contributor failure cannot be misreported as RGB Render Failure.
- Every destructive/recompute action states retained artifacts and recovery.
