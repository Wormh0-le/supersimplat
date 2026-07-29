# Final Spec v1.1 Walkthrough Coverage — v2.5

## Typical Flows A–I — inherited product workflows

| ID | Flow | Ticket path |
|---|---|---|
| WF-A | Fast single-object | `02 → 03/04/05 → 04A → 04B → 07A → 07B → 08 → 08A → 09 → 11/12 → 14 → 10/13 → 15 → 16` |
| WF-B | Adjust Anchor | `02 → 03 RGB Retry → 04A/04B/07A → 07B → 05 Confirm` |
| WF-C | Add a missing user View | `09 → 11 → Mask publication → 12 Evidence dirty → 14/15 → 13` |
| WF-D | Redraw bad Mask from scratch | `09 → 04A Paint/Erase → Confirm → 12 dirty → 15 explicit Re-Lift` |
| WF-E | Modify reference then Repropagate | `04A/04B/07A or 09 correction → Confirm → 12 explicit tracker Repropagate → 07/10 reassessment → 13 → 15` |
| WF-F | Select multiple objects | `16 → 17 Restart → 02... → 16 → 17` |
| WF-G | Candidate structural error | `14/15 → 09/07/11/08 correction → 12 dirty → 15` |
| WF-H | Fix after Candidate applied | `16 → 17 Undo and Fix → 15` |
| WF-I | Scene mutation + Undo | `18 Suspended → exact Native Undo → resume` |

## Architecture walkthroughs

| ID | Flow | Ticket path | Required result |
|---|---|---|---|
| WF-J | RGB Ready without Mask/Evidence | `03/06/08A/11` | Authoritative RGB publishes independently; no Contributor gate |
| WF-K | Stable Mask → Evidence dirty → explicit Lift | `04/05/07A/08A/11 → 12 → 14/15` | Only Confirmed Stable inputs invalidate Evidence; Candidate changes only after explicit Re-Lift |
| WF-L | Reference Evidence → production Direct Evidence | `14 → 19 → 20 → 21` | P/N/V validated before same-decision CUDA productionization |
| WF-M | Full occlusion + local Evidence writes | `19 → 20` | Full Render Working Set preserves occlusion; Evidence Working Set limits writes |
| WF-N | Object-level Anchor acquisition | `04A → 04B → 07A → 05/07 → 07B` | Conservative proposal decision; material ambiguity remains recoverable; Confirm publishes identity seed |
| WF-O | Visual Prompt Adapter | `04A → 04B → 07A` | Truthful Box/Mask compilation; unsupported combinations fail closed |
| WF-P | Floating Prompt/Edit Palette | `07A fitted rect → 07B` | Drag/snap/collapse/Space-hide with no stale blind region |
| WF-Q | D′ object tracking pipeline | `07A/07B → 08 → 08A → 09/12 → 14` | 2.5D bootstrap guides ordered Key/Bridge tracking; final ownership waits for P/N/V |
| WF-R | Confirmed correction keyframe | `09 correction → Confirm → 12 explicit Repropagate → 08A → 07/09 → 14/15` | Confirmed correction enters tracker memory; prior Stable/Evidence/Candidate survive failure |

## WF-N — object-level Anchor

```text
Authoritative Anchor RGB
→ Point / enabled Box / enabled Mask Constraint
→ PromptState revision
→ candidates
→ exact dedup + near-duplicate clustering
→ conservative ProposalDecision
    ├── one credible cluster → selected → Accept → Editing Mask
    ├── risky or material alternatives → ambiguous → choose/refine/Paint
    └── no eligible cluster → unavailable → refine/Retry/manual
→ Confirm Mask
→ Anchor Stable Mask
→ Ticket 07 assessment/Participation
→ Confirm Anchor
```

Assertions:

- Prompt and Paint histories are separate.
- Model score is not correctness probability or sole selector.
- Suspicious single candidate is gated.
- Multiple materially distinct plausible clusters remain `ambiguous`.
- No generic calibrated Top-1 ranker is required.
- Optional Gaussian support is not ownership Evidence.
- Anchor Stable Mask is identity seed, not Candidate.

## WF-O — Visual Prompt Adapter

```text
PromptState with Point + Box / Mask Constraint
→ 04B capability/compiler validation
    ├── supported → locked adapter inference
    └── unsupported → fail closed before inference
→ independently validated candidates
→ 07A clustering / hard consistency / decision
```

Assertions:

- Positive and negative capabilities are separate.
- No Prompt is dropped or converted to Points.
- 04B performs no ranking/ambiguity decision.
- Text remains disabled unless later enabled by locked adapter.

## WF-P — Floating palette

```text
fitted authoritative image
→ expanded palette inside image
→ drag / edge snap / collapse
→ edit edge/corner target
→ Space hides and removes hit testing
→ keyup/blur restores prior state
→ Restart Target restores default palette state
```

Assertions:

- Palette motion changes no RGB/Mask/Prompt coordinate mapping.
- Only current visible bounds intercept input.
- Old position becomes immediately editable.
- Palette state never enters PromptState, Mask history, Evidence, or Candidate identity.

## WF-Q — D′ object tracking pipeline

```text
Confirmed object-level Anchor Stable Mask
→ TargetBootstrapArtifact from depth / first-hit visible support
    ├── center / extent / ROI / framing
    └── no Gaussian ownership
→ candidate cameras
→ validity gate
→ adaptive Key View selection
→ ordered sequence + bounded Bridge insertion
→ authoritative RGB publishes progressively
→ Ticket 08A object-level tracker
→ per-view Tracked Mask Review / Auto Stable / Failed
→ Ticket 09 review
→ Participation remains independent of Anchor/Key/Bridge role
→ explicit Update Multi-view Masks when dirty
→ Included Stable View Annotations
→ Ticket 14 per-view P/N/V
→ final Candidate + Uncertain
```

Assertions:

- Invalid pose cannot win by information gain.
- Bridge Views exist for transition continuity and default Excluded.
- Tracker role/confidence does not authorize Lift.
- Current projected-support + single-frame SAM remains explicit baseline/fallback.
- Tracker backend is selected only after 08A spike and ADR.
- Formal ownership occurs only in Tickets 14/20.

## WF-R — correction keyframe

```text
Tracked View is Review / drift suspected
→ user Prompt/Paint correction
→ Editing Mask only
→ Confirm correction
→ Stable Mask + CorrectionReference revision
→ propagationDirty
→ explicit Update Multi-view Masks
→ new bound tracking run
→ atomic replacement of dependent tracked Mask revisions
→ assessment / Participation refresh
→ Evidence dirty for changed Included Stable Views
→ explicit Re-Lift
```

Assertions:

- Unconfirmed correction never enters tracker memory.
- Bridge correction may be reference memory while remaining Excluded.
- Repropagate failure preserves prior Stable Masks and matching Candidate/Evidence.
- Repropagate never automatically Re-Lifts.
- Late results are rejected against Anchor/plan/reference/backend identities.

## Reverse outcome-to-prerequisite validation

```text
Native operation (16)
← current Candidate (15/14)
← readiness and version-bound per-view P/N/V (13/14/20)
← Included Stable View Annotations (09/11/12)
← object-level tracking + correction memory (08A)
← valid ordered Key/Bridge plan + 2.5D bootstrap (08)
← no-blind-spot authoring (07B)
← confirmed object-level Anchor (04B/07A/05)
← Prompt/proposal foundation (04A)
← authoritative RGB + CameraBinding (02/03/06/11)
← Render Working Set + Stable IDs (01/19)
```

No final outcome depends on complete per-pixel Contributor publication. Reference Contributor remains a validation/debug side path.

## Error / degradation flows

| ID | Failure | Ticket(s) | Required retained state / recovery |
|---|---|---|---|
| ERR-1 | Companion Offline/incompatible | 02/21 | Native editor unaffected; reconnect/settings recovery |
| ERR-2 | RGB/Preview failure | 03/21 | Keep last valid preview stale/not-current; real Retry |
| ERR-3 | Anchor model failure | 04A/04B/07A/21 | Keep RGB/Prompt/prior Stable/edit state; Retry/manual recovery |
| ERR-4 | View Render Failure | 06/08/11/21 | Keep View record; retry/replacement/exclude |
| ERR-5 | Evidence failure | 14/20/21 | Keep RGB/View/Stable/Gallery/prior Candidate |
| ERR-6 | Lift/aggregation failure | 14/15/21 | Keep stable inputs and previous Candidate |
| ERR-7 | Repropagate failure | 12/21 | Keep prior Stable Masks and matching Evidence/Candidate |
| ERR-8 | Reference Contributor failure | 03/14/20/22 | Diagnostic path fails only |
| ERR-9 | Cached replay vs Retry | 03/08A/21 | Same attempt idempotent; Retry creates new attempt |
| ERR-10 | Scene Chunk Miss / incomplete Render Working Set | 19/20/21 | No partial Ready artifact; load/fallback/retry |
| ERR-11 | OOM/cancellation | 04A/04B/08A/20/21 | No partial proposal/Mask/Evidence/Candidate; old artifacts retained |
| ERR-12 | Scene dependency mutation | 18 | Suspended/read-only; exact Undo or Restart |
| ERR-13 | Proposal ambiguous | 07A | Preserve clusters/RGB/Prompt/prior Stable; refine/choose/Paint |
| ERR-14 | Proposal unavailable | 04A/04B/07A | Preserve RGB/Prompt/prior Stable; Retry/refine/manual |
| ERR-15 | Invalid indoor camera | 08 | Reject before gain; bounded replacement/local fallback/Limited |
| ERR-16 | Palette stale blind region/stuck hidden | 07B | Remove stale hit box; restore on keyup/blur |
| ERR-17 | Tracker failure or unsupported runtime | 08A | Preserve RGB/prior Stable; Retry/baseline fallback/manual/exclude |
| ERR-18 | Identity drift / instance switch suspicion | 08A/09/12 | Review/fail closed; correction reference + explicit Repropagate |

## Closure assertions

- RGB publication never requires complete Contributor or Evidence.
- Prompt Authoring and Pixel Editing remain separate.
- 04B capabilities are truthful and fail closed.
- 07A is conservative object-level Anchor acquisition, not a generic calibrated ranker.
- Only Confirm replaces Stable Mask.
- 08 uses geometry for planning, not ownership.
- Key/Bridge role is separate from Participation.
- 08A begins with a backend spike and preserves the single-frame baseline/fallback.
- Confirmed corrections enter tracker memory only through explicit repropagation.
- Tracker confidence is not P/N/V.
- Reference P/N/V precedes production same-decision CUDA.
- Every destructive/recompute action states retained artifacts and recovery.