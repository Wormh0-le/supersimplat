# 07A — Complete Three-Stage Anchor Mask Pipeline + Ranking / Ambiguity UX

Status: implemented — Phase 4 browser closure validated 2026-07-29

Blocked by: 04A, 05, 07

Blocks: 08

## Final Spec mapping

- Final Spec v1.1 §§10–13, 23, 26, 30–32
- Final Spec v1.1 Amendment 002 — Prompt Authoring and Three-Stage Anchor Mask Pipeline
- DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
- DG-12 Anchor Validation & Confirm Gate
- DG-19 Review Reason & Quality Explanation
- MVP Phase 2/4 Anchor quality hardening

## Completion ownership

Ticket 07A is the end-to-end completion owner for:

```text
Phase 0 — Prompt/Edit interaction hardening inherited from 04A browser validation
Stage 1 — Prompt-conditioned Proposal Generation integration
Stage 2 — 2D-first Proposal Ranking / Ambiguity Decision
Stage 3 — Candidate Acceptance / Editing / Confirm
```

Ticket 04A implemented `PromptState`, explicit tools, adapter capability negotiation, the generic proposal protocol, and a bounded `AutoMaskProposalSet` seam. Ticket 07A turns that foundation into a production-quality Anchor Mask workflow and validates all stages together.

## Context

The current point-only compatibility path can still produce two recurrent failures:

```text
one click on table top
→ oversized table + neighbouring chairs mask

otherwise plausible prompt
→ overloaded proposal-unavailable result
```

Ticket 07 assesses an already published Stable Mask. It cannot decide which pre-Stable proposal should seed the Editing Mask. `ProposalDecision` therefore remains separate from `ViewAssessmentPolicy`.

Ticket 04A browser validation also exposed interaction problems that must be resolved before Stage 3 can be considered usable:

1. Paint/Erase drag behaves like a sequence of isolated stamps, and Undo operates stamp-by-stamp rather than stroke-by-stroke.
2. Positive/negative Point prompts have weak on-canvas feedback, so users cannot reliably see the active tool, authored prompts, pending inference, or result state.
3. Prompt Undo/Redo/Clear are functionally necessary but currently consume excessive primary UI space and are hard to distinguish from Mask Undo/Redo/Clear.
4. All supported and unsupported tools are presented as text buttons in one dense right-side block, which will not scale once proposal alternatives and ambiguity actions are added.

These are not cosmetic-only issues. Atomic strokes and explicit prompt feedback are required recovery primitives for ambiguous and unavailable proposal states.

## Inputs / preconditions

- Implemented Ticket 04A `PromptState`, adapter capabilities, request/result identity, and bounded `AutoMaskProposalSet`
- Exact Anchor RGB / CameraBinding / context identity
- Existing Editing Mask / Stable Mask lifecycle
- Ticket 05 Anchor validation and support-probe seam
- Ticket 07 `ViewAssessmentPolicy` and Participation semantics
- Frozen real-scene Anchor RGB with reviewed reference masks
- Locked SAM 3.1 or declared replacement adapter/runtime

## Outputs / handoff artifacts

- Atomic stroke editing semantics and browser interaction fixtures
- Persistent prompt visualization and explicit proposal-state feedback
- Compact Prompt/Edit toolbar information architecture
- Versioned `anchor-mask-ranking/v1` policy
- Per-proposal 2D feature records
- Optional bounded support-sanity records
- `ProposalDecision`: selected / ambiguous / unavailable
- Alternative-proposal chooser and actionable ambiguity UX
- Accepted proposal → Editing Mask integration
- Refined proposal failure taxonomy
- Locked-runtime quality benchmark and thresholds
- Confirmed Anchor contract safe for Ticket 08

# Phase 0 — Prompt/Edit interaction hardening

Phase 0 is an entry gate for the ranking and acceptance work. It does not change the Prompt/Mask lifecycle established by Tickets 04A and 05.

## 0.1 Atomic Paint/Erase strokes

One pointer gesture MUST be one Mask-history command:

```text
pointerdown
→ begin stroke

pointermove / coalesced events
→ collect samples and interpolate continuously

pointerup
→ commit one stroke command
→ push one Mask Undo unit
```

Required behavior:

- one `pointerdown → pointerup` gesture is one atomic Paint or Erase command;
- interpolation between samples prevents visible gaps during fast movement;
- `pointercancel`, tool switch, View switch, Restart, and context disposal cannot publish a partial command;
- Undo removes one complete stroke;
- Redo restores one complete stroke;
- dirty-region patches MAY be used instead of cloning the full Mask per sample;
- Paint/Erase never mutates `PromptState`;
- a local committed stroke supersedes a late proposal/ranking result unless the user explicitly accepts that result.

Suggested command shape:

```ts
interface MaskStrokeCommand {
    tool: 'paint' | 'erase';
    radiusPx: number;
    samples: readonly PixelPoint[];
    dirtyBounds: PixelRect;
    beforePatch: BinaryMaskPatch;
    afterPatch: BinaryMaskPatch;
}
```

## 0.2 Persistent prompt feedback

Prompt authoring MUST provide immediate feedback before model inference completes.

Required on-canvas representation:

```text
Positive Point  → persistent + marker
Negative Point  → persistent − or × marker
Positive Box    → solid rectangle
Negative Box    → dashed rectangle
Prompt Brush    → polarity-distinct translucent stroke
```

Color alone is insufficient; polarity must also be represented by shape, icon, or line style.

Required active-tool feedback:

- Point+ and Point− use distinct cursors;
- Paint/Erase show the effective brush-radius cursor;
- the selected tool is unambiguous without reading a status paragraph;
- authored prompt markers remain visible while proposals are pending and after results return.

Required state acknowledgement:

```text
prompt accepted locally
→ proposal pending
→ proposal selected / ambiguous / unavailable / failed
```

The UI SHOULD expose a compact prompt summary such as:

```text
+ points 2 · − points 1 · boxes 0 · prompt revision 4
```

## 0.3 Prompt history versus Mask history

Prompt and Mask histories remain separate domain histories.

Required semantics:

```text
Prompt Undo / Redo
→ changes PromptState only

Mask Undo / Redo
→ changes Editing Mask only
```

`Clear Prompts` remains necessary but is a secondary/destructive prompt action. It MUST NOT clear Editing Mask, Stable Mask, Evidence, Candidate, or Native Selection.

UI requirements:

- the active history scope is explicit;
- tooltips or accessible labels distinguish “Undo prompt” from “Undo Mask stroke”;
- disabled Undo/Redo states reflect the active history only;
- Clear Prompts is not presented as an equally prominent primary action beside Point/Paint tools;
- keyboard shortcuts remain deterministic and focus-routed.

## 0.4 Phase 0 acceptance gate

Stage 1–3 implementation may proceed in the same development run, but Ticket 07A cannot close unless:

- one rapid curved Paint/Erase drag produces a continuous stroke;
- one Undo removes the entire drag;
- one Redo restores the entire drag;
- Point+ / Point− markers are persistent and polarity-distinct;
- pending/result proposal state is visible;
- Prompt Undo never changes Editing Mask;
- Mask Undo never changes PromptState;
- Clear Prompts preserves Stable Mask and downstream artifacts until a later Confirm changes Stable Mask.

# Stage 1 — Proposal Generation integration

Consume Ticket 04A output without collapsing materially distinct alternatives.

Stage 1 MUST:

- preserve a deterministic bounded candidate set;
- preserve raw model score and declared semantics;
- bind every proposal to exact RGB, PromptState, model, adapter, capability, policy, and attempt identities;
- reject invalid candidates individually without discarding valid alternatives;
- retain diagnostics explaining why no eligible candidate remained;
- expose proposal pending/success/failure state independently from RGB and Stable Mask state.

Stage 1 MUST NOT:

- publish Stable Mask;
- select solely because `out_probs` or another raw model score is largest;
- turn ambiguity into `anchorMaskUnavailable`;
- require complete Contributor or formal P/N/V.

A one-element compatibility proposal set is legal for transport regression. Ticket 07A cannot close its production quality gate unless the locked backend can provide materially distinct alternatives, or an explicit versioned proposal-generation layer produces them.

# Stage 2 — 2D-first Proposal Ranking

## 2.1 Ranking principle

Anchor Mask intent is primarily an interactive 2D segmentation problem. Ranking is therefore 2D-first.

Required feature groups:

```text
A. Hard prompt consistency
B. Candidate hierarchy / relative geometry
C. 2D structural quality
D. Model-declared score
E. Optional low-cost Gaussian support sanity
```

No single feature is a correctness probability.

## 2.2 Hard prompt consistency

A candidate is ineligible when it violates an active hard constraint, including:

- positive Point outside Mask;
- negative Point inside Mask;
- positive Box below required fill/containment policy;
- negative Box above allowed overlap policy;
- positive/negative Mask constraint above disagreement threshold;
- active Text constraint unsupported or unfulfilled under declared adapter semantics;
- dimensions, RGB, Prompt, adapter, or policy identity mismatch.

Positive and negative support for each prompt family is capability-gated. Hard filters and thresholds MUST be versioned and tested.

## 2.3 Candidate hierarchy and relative geometry

Compare candidates to one another, not only against global thresholds.

Record at least:

- area fraction and bounding box;
- connected-component count;
- component containing each positive Point;
- containment/nesting graph;
- pairwise IoU and area ratio;
- boundary-contact fraction;
- compactness/perimeter proxy;
- positive-Point distance to boundary;
- Box fill and spill ratios;
- prompt-Mask overlap;
- material-distinctness used to deduplicate alternatives.

For a Point inside nested Masks, the policy must distinguish:

```text
local part
whole object
object plus neighbouring objects
```

It MUST NOT assume the smallest or largest Point-containing Mask is always correct.

## 2.4 Model score semantics

The model score is one feature only.

The policy MUST:

- retain the adapter-declared score name and semantics;
- avoid exposing it as `Confidence XX%`;
- avoid treating it as calibrated IoU or user-intent correctness unless separately proven;
- report score ablations on frozen real scenes.

## 2.5 Optional Gaussian support sanity

Low-cost Gaussian diagnostics MAY provide:

- proposal computability check;
- gross support sparsity warning;
- bounded tie-breaker between otherwise comparable 2D candidates;
- detection of obviously disconnected projected support.

They MUST NOT:

- become formal P/N/V Evidence;
- classify Gaussian ownership;
- be the primary selector;
- override hard 2D prompt consistency;
- use nearest/top-k/distance attribution as formal semantics;
- reject all editable candidates merely because center-projection support is weak.

The ranking output MUST record whether optional support participated, its policy identity, and whether removing it changes the decision.

## 2.6 Versioned decision

```ts
interface ProposalRankingFeatures {
    promptConsistency: PromptConsistencyFeatures;
    areaFraction: number;
    boundingBox: PixelBox;
    connectedComponentCount: number;
    positivePointBoundaryDistances: readonly number[];
    pairwiseRelations: readonly ProposalRelation[];
    boundaryContactFraction: number;
    compactness?: number;
    modelScore?: number;
    optionalSupportSanity?: {
        policyId: string;
        computable: boolean;
        observedGaussianCount?: number;
        supportConcentration?: number;
    };
}

interface ProposalDecision {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    promptStateDigest: string;
    proposalSetDigest: string;
    rankingPolicyVersion: string;
    status: 'selected' | 'ambiguous' | 'unavailable';
    selectedProposalId?: string;
    alternativeProposalIds: readonly string[];
    reasons: readonly ProposalDecisionReason[];
}
```

## 2.7 Automatic selection gate

Auto-select only when:

- exactly one eligible candidate remains; or
- Top-1 has a benchmark-calibrated decision margin over materially different alternatives;
- no ambiguity reason is active;
- the decision is stable under declared numeric/model-score perturbations.

Candidate ambiguity reasons include:

```text
nested-part-vs-whole
similar-score-different-area
multiple-disconnected-targets
box-spill
prompt-conflict
neighbour-object-leak-risk
model-score-disagreement
insufficient-decision-margin
```

Thresholds are policy data, never frontend constants.

# Stage 3 — Acceptance / Editing / Confirm

## 3.1 Selected

```text
selected AutoMaskProposal
→ explicit Accept Candidate
→ seed/replace Editing Mask
```

This remains unconfirmed. The previous Stable Mask remains authoritative until Confirm Mask succeeds.

## 3.2 Ambiguous

When ambiguous:

- preserve eligible bounded candidates;
- display 2–4 materially distinct alternatives where available;
- mark a suggested default without claiming certainty;
- allow alternative selection, positive/negative Point, Box refinement, prompt constraint, supported Text, Paint/Erase, or prompt reset.

An ambiguous proposal MUST NOT publish Stable automatically. Explicit candidate choice resolves proposal ambiguity and seeds Editing Mask.

## 3.3 Unavailable

When no eligible proposal exists:

- preserve RGB and PromptState;
- expose structured causes;
- allow prompt revision, Retry, and manual Empty → Paint;
- do not relabel View as Render Failed.

Use distinct states:

```text
maskProposalFailed       model/runtime/transport failure
maskProposalUnavailable  no eligible prompt-consistent proposal
maskProposalAmbiguous    several materially different plausible proposals
maskArtifactInvalid      invalid proposal artifact
```

Legacy `anchorMaskUnavailable` may be mapped at transport compatibility boundaries only.

## 3.4 Manual editing

Paint/Erase changes Editing Mask only.

After local editing:

- accepted proposal identity remains available for correctness/debug;
- source becomes `hybrid` or `manual`;
- ranking is not silently rerun;
- PromptState is not inferred or rewritten from pixels;
- “Use edit as prompt constraint” requires a future explicit action/capability.

## 3.5 Confirm and assessment integration

```text
Editing Mask
→ Confirm Mask
→ new Stable Mask revision
→ Ticket 07 ViewAssessmentPolicy
→ Good / Review / Failed
→ Participation default
```

Keep the two decisions separate:

```text
ProposalDecision
= which pre-Stable proposal seeds Editing Mask?

ViewAssessment
= is the confirmed Stable Mask suitable for participation?
```

Confirm Anchor remains governed by Ticket 05 and Amendment 002:

- no latest Prompt/proposal/ranking/edit operation is pending;
- unresolved ambiguity has been explicitly resolved or bypassed by manual editing;
- a current Stable Mask exists after Confirm Mask;
- exact RGB/Mask/Camera identity matches;
- support computability gate passes;
- soft warnings remain user-overridable.

A user-confirmed manual/hybrid Mask may proceed even when automatic ranking was ambiguous or unavailable.

# Scope relative to non-Anchor Views

The domain and toolbar may be reused for Generated and User-added View correction. Ticket 07A's mandatory Three-Stage automatic selection and benchmark gate apply to the Anchor path.

This ticket MUST NOT break the current Generated View contract in which an automatic Stable Mask and assessment can publish atomically. Extending proposal alternatives to automatic Generated View publication requires an explicit later policy/ticket or Ticket 12 Repropagate integration.

# UI information architecture

The current dense right-side text-button block is not the target 07A interaction model.

Required structure:

```text
Image surface
├─ compact contextual Prompt/Edit toolbar
├─ persistent prompt and Mask overlays
└─ active cursor / pending feedback

Proposal / status panel
├─ current proposal state
├─ compact Prompt summary
├─ materially distinct alternatives
├─ ambiguity/failure reason
└─ recommended corrective actions

Primary action area
├─ Retry / Update Proposals
├─ Accept Candidate
└─ Confirm Mask
```

Required toolbar behavior:

- Prompt tools and Edit tools are visually grouped but not mixed;
- supported primary tools are directly accessible;
- unsupported capabilities remain discoverable with an explicit reason, but do not occupy the full primary toolbar as a row of disabled text buttons;
- icon controls MUST provide tooltip and accessible labels;
- selected tool, active history scope, and destructive actions are visually distinct;
- Prompt Undo/Redo are contextual secondary controls;
- Mask Undo/Redo are contextual secondary controls;
- Clear Prompts and Clear Editing Mask are separate actions with separate effects;
- brush size is contextual to the active brush tool;
- proposal alternatives use thumbnails, overlay cycling, or an equivalent bounded chooser;
- no uncalibrated confidence percentage is shown;
- Ticket 07 Mask Quality and Participation remain separate rows from `ProposalDecision`.

Visual polish beyond these information-architecture and feedback requirements is not a closure gate. Correct interaction semantics and comprehensibility are closure gates.

# Required proposal states

```text
No prompts
Prompt authored
Generating proposals
Proposal selected
Proposal ambiguous
Proposal unavailable
Proposal failed
Editing
Stable confirmed
```

# Acceptance criteria

## Phase 0 interaction correctness

- [ ] One Paint/Erase pointer gesture creates one atomic Mask command.
- [ ] Rapid curved strokes are continuous without visible sampling gaps.
- [ ] One Mask Undo/Redo removes/restores one complete stroke.
- [ ] `pointercancel` and lifecycle disposal publish no partial stroke.
- [ ] Positive/negative Point prompts have persistent polarity-distinct markers.
- [ ] Point/Paint/Erase active cursors communicate the active operation.
- [ ] Prompt acknowledgement and proposal pending/result status are visible.
- [ ] Prompt and Mask histories remain separate and focus-routed.
- [ ] Clear Prompts preserves Editing Mask, Stable Mask, Evidence, Candidate, and Native Selection.

## Pipeline

- [ ] Stage 1 returns a bounded identity-bound proposal set.
- [ ] Production validation uses a backend capable of meaningful proposal alternatives or a declared alternative generator.
- [ ] Stage 2 is versioned, 2D-first, and not model-score-only.
- [ ] Stage 3 requires explicit proposal acceptance and Stable Mask confirmation.
- [ ] Pipeline is replayable from RGB + PromptState + model/adapter/policy identities.
- [ ] Proposal, decision, Editing, and Stable states are distinct.

## Ranking and ambiguity

- [ ] Positive/negative Point, Box, Mask constraints, and supported Text participate according to capability.
- [ ] Candidate hierarchy and pairwise material-distinctness are computed.
- [ ] Nested part/whole alternatives can trigger ambiguity.
- [ ] Neighbour-object leakage can trigger ambiguity rather than silent auto-selection.
- [ ] Weak optional Gaussian support does not destroy otherwise editable proposals.
- [ ] Model score remains declared but uncalibrated unless proven.
- [ ] Auto-selection margins are benchmark-derived and policy-versioned.
- [ ] Decision stability is tested under repeated model/numeric runs.

## Recovery

- [ ] Ambiguous preserves alternatives and offers selection/refinement/manual editing.
- [ ] Unavailable preserves RGB and PromptState.
- [ ] Technical failure is distinct from unavailable/ambiguous.
- [ ] Existing Stable Mask remains current until replacement Confirm succeeds.
- [ ] Late proposal/ranking results cannot replace newer Prompt or local edits.
- [ ] Manual Paint/Erase recovers from every proposal state.

## Ticket 05 / 07 integration

- [ ] Confirm Anchor blocks pending/unresolved Prompt/proposal/ranking/edit state.
- [ ] Proposal ambiguity and Ticket 07 Review are separate.
- [ ] User-confirmed authority remains final for Participation defaults.
- [ ] Stable Mask replacement invalidates only exact dependent Evidence/Candidate state.
- [ ] Existing Generated View auto-publication and assessment regressions pass.

## UI / comprehensibility

- [ ] The active Prompt/Edit tool is unambiguous on image and toolbar.
- [ ] Prompt summary and authored prompt overlays match the current PromptState revision.
- [ ] Unsupported capabilities are discoverable with a reason without dominating the primary toolbar.
- [ ] Prompt Undo/Redo/Clear and Mask Undo/Redo/Clear have distinct labels and effects.
- [ ] Suggested candidate, accepted candidate, Editing Mask, and Stable Mask are not visually conflated.
- [ ] Ambiguity and failure states expose actionable next steps.

# Required real-scene validation

Fake-predictor tests are insufficient for closure.

Frozen authoritative gsplat RGB cases must include:

- table top surrounded by chairs;
- whole table versus table-top part;
- chair beside table with similar color;
- cabinet door versus whole cabinet;
- monitor versus wall/desk;
- thin object;
- object touching image boundary;
- fragmented 3DGS render;
- small object;
- no valid proposal;
- multiple plausible nested proposals.

Report:

```text
first-interaction acceptable-mask rate
acceptable mask after one refinement
mean prompt actions
neighbour-object contamination
reference-mask IoU where available
false auto-selection rate
ambiguous rate
proposal-unavailable rate
manual recovery success
stroke continuity / undo correctness
latency
peak VRAM
```

Mandatory regression:

```text
one positive click on table top
→ must not silently auto-select table + multiple chairs
```

Acceptable outcomes:

- table-top proposal selected;
- table/part ambiguity shown;
- prompt refinement requested.

An oversized contaminated Mask is not an acceptable silent success.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- Locked SAM 3.1/replacement adapter GPU benchmark
- Real browser Point+/Point− marker and proposal-state walkthrough
- Real browser continuous Paint/Erase stroke + one-step Undo/Redo walkthrough
- Real browser Prompt/Edit history-scope walkthrough
- Real browser proposal alternative-selection walkthrough
- Frozen-scene ranking and model-score/support ablations
- Stale async and Retry stress
- Ticket 05 Confirm and Ticket 07 Assessment integration
- Generated View automatic publication regression

# Suggested implementation sequence

```text
Phase 0A  atomic stroke transaction + interpolation + Mask history
Phase 0B  prompt markers, cursors, summary, pending/result feedback
Phase 1   preserve/generate materially distinct proposals
Phase 2A  2D feature extraction and pairwise hierarchy
Phase 2B  versioned ranking and ambiguity policy
Phase 3A  proposal chooser and Accept Candidate
Phase 3B  manual/hybrid Editing and Confirm integration
Phase 3C  toolbar/status/action information-architecture pass
Phase 4   frozen-scene benchmark, ablations, locked-runtime validation
```

Do not defer Phase 0 until after ranking. Stage 3 recovery depends on correct stroke and history semantics.

# Non-goals

- No Adaptive Generated View planner; Ticket 08 owns it.
- No cross-view proposal ranking.
- No formal P/N/V Evidence.
- No semantic object database.
- No requirement to enable Text in Phase A.
- No direct 3D Candidate editing.
- No use of support probe as Gaussian ownership classification.
- No broad visual redesign of SuperSplat outside the AI View Dock.
- No requirement for final-production icon artwork or animation polish.

# Dependency update

The v2.3 retrofit graph remains:

```text
03 + 04 → 05 → 06 → 07
          │         │
          └→ 04A ──┘
                ↓
               07A
                ↓
               08
```

Ticket 04A depends on the existing Ticket 05 Mask editor/Undo/Confirm seams. Ticket 07A depends on Ticket 04A and completed Ticket 07 assessment semantics. Ticket 08 MUST depend on 07A.

## Phase 4 implementation record — 2026-07-29

Ticket 07A was reopened after browser validation exposed Dock layout,
interaction-rectangle, failure-presentation, and proposal-publication defects.
The closure pass changed the editor UI and the browser/Companion proposal
identity seam; Ticket 08 was not started.

Implemented:

- moved the Prompt/Edit toolbar into the exact fitted image surface;
- split proposal/status information into its own scrollable region and kept
  primary actions in a separate fixed region;
- added a native pointer/keyboard vertical Dock separator;
- added a `ResizeObserver`-driven contain rectangle shared exactly by the
  authoritative RGB, Mask canvas, Prompt overlay, box preview, and pointer
  mapping;
- made the space outside that rectangle neutral and non-interactive;
- localized the compact Prompt summary and reduced failure presentation to
  one user-facing message plus collapsed technical details;
- moved the generated-view Gallery into the scrollable information region and
  isolated toolbar pointer events from image authoring;
- fixed `maskArtifactInvalid` at its source. Python serialized an exact model
  score as `1.0`, while the browser parsed and reserialized the same Number as
  `1`, so the two runtimes computed different proposal-set digests. Proposal
  identity now canonicalizes every number by its IEEE-754 binary64 value, with
  a shared cross-language digest vector. `AutoMaskProposalSet` is explicitly
  schema v2 so recorded v1 artifacts cannot be mistaken for the new identity
  contract. Companion capabilities advertise
  `autoMaskProposalSetSchemaV2`, and editor readiness rejects an older
  Companion before any proposal request.

Real browser closure validation used
`/home/ubuntu/wormh01e/gaussian/restroom/test_breakroom.ply` (176,594 splats)
with the locked gsplat renderer and installed SAM 3.1 model:

```text
Dock height:                 419 px → 503 px by native separator drag
authoritative fitted rect:   x 148.421875, y 361, 795.140625 × 455
RGB / Mask / interaction:    exact shared rectangle
normal positive point:       HTTP 200, schema v2, 1 proposal, selected
toolbar click isolation:     0 Mask proposal requests
invalid-artifact injection:  1 localized message; technical details collapsed
```

Evidence is captured by
`.scratch/ai-select-v1/browser-validation/07a-browser-loop.mjs`; the successful
and injected-failure screenshots were inspected in the form consumed by the
browser.

Validation:

```text
npm test              315 TypeScript/Node tests + 245 Companion tests passed
npm run lint          passed
npm run lint:locales  464 keys synchronized
npm run build         passed (existing dependency warnings only)
real browser/GPU      authoritative gsplat Anchor + real SAM proposal passed
```

This closure did not change Final Spec, ADRs, the runtime lock, ranking policy,
Evidence/Assessment policy, or calibration. It is production prompt/Mask-path
work, not a reference Contributor or mocked GPU path. The reference/debug
Contributor backend and legacy migration code remain intact.

The targeted browser closure above does not manufacture new frozen-scene
quality metrics, ablations, latency, or peak-VRAM results beyond the real
breakroom regression. Those broader benchmark requirements remain governed by
the existing locked-runtime validation records and should not be inferred from
this targeted closure run alone.
