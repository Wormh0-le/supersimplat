# 07A — Complete Three-Stage Anchor Mask Pipeline + Proposal Ranking / Ambiguity UX

Status: proposed — ready-for-agent after 04A and DG-21 / Final Spec v1.1 Amendment 002 approval

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

This ticket is the end-to-end completion owner for:

```text
Stage 1 — Prompt-conditioned Proposal Generation
Stage 2 — 2D-first Proposal Ranking and Ambiguity Decision
Stage 3 — Candidate Acceptance / Editing / Confirm
```

Ticket 04A supplies the PromptState, tool modes, generic adapter protocol, and bounded proposal set. Ticket 07A makes that foundation a production Anchor Mask workflow.

## Context

The current point-only path selects the highest-scored SAM candidate that satisfies basic point and area checks. Real scenes show two recurrent failures:

```text
one click on a table top
→ oversized table + neighbouring chairs mask

otherwise plausible prompt
→ anchorMaskUnavailable
```

Ticket 07 can assess an already published Stable Mask, but it does not determine which model proposal should seed the Editing Mask. Ticket 07A adds a pre-Stable proposal decision layer. It does not replace Ticket 07 ViewAssessmentPolicy.

## Inputs / preconditions

- Ticket 04A `PromptState` and `AutoMaskProposalSet`
- Exact Anchor RGB / CameraBinding / context identity
- Existing Editing Mask / Stable Mask lifecycle
- Ticket 05 Anchor validation and support-probe seam
- Ticket 07 local ViewAssessmentPolicy and Participation semantics
- Frozen real-scene Anchor RGB/ground-truth or reviewed reference masks
- Locked SAM 3.1 runtime for production-quality validation

## Outputs / handoff artifacts

- Versioned `anchor-mask-ranking/v1` policy
- Per-proposal 2D feature record
- Optional low-cost support-sanity feature record
- `ProposalDecision` with selected / ambiguous / unavailable states
- Candidate chooser and ambiguity actions
- Accepted Auto Mask → Editing Mask integration
- Refined Mask failure taxonomy
- Real-scene quality benchmark and thresholds
- Ticket 08-safe confirmed Anchor input

## What to build

## Stage 1 — Prompt-conditioned Proposal Generation

Consume Ticket 04A output.

Stage 1 MUST:

- preserve multiple bounded candidates;
- preserve raw model score and declared semantics;
- bind every proposal to exact RGB, PromptState, model, adapter, policy, and attempt identities;
- reject structurally invalid masks without discarding valid alternatives;
- retain enough diagnostics to explain why no prompt-consistent candidate remained.

Stage 1 MUST NOT:

- publish Stable Mask;
- select a candidate solely because it has the largest `out_probs`;
- turn ambiguity into `anchorMaskUnavailable`;
- require complete Contributor or formal P/N/V.

## Stage 2 — 2D-first Proposal Ranking

### 2.1 Ranking principle

Anchor Mask intent is first a 2D interactive-segmentation problem. The authoritative ranking policy is therefore 2D-first.

Required feature groups:

```text
A. Hard prompt consistency
B. Candidate hierarchy / relative geometry
C. 2D structural quality
D. Model-declared score
E. Optional low-cost Gaussian support sanity
```

No single feature is a correctness probability.

### 2.2 Hard prompt consistency

A candidate is ineligible when it violates a hard prompt constraint, including:

- a positive point is outside the mask;
- a negative point is inside the mask;
- an active positive box has insufficient required overlap/containment under policy;
- a negative box violates exclusion policy;
- positive/negative mask constraints exceed declared disagreement limits;
- dimensions or RGB/Prompt identities mismatch.

Hard filters and thresholds MUST be versioned and tested.

### 2.3 Candidate hierarchy and relative geometry

The policy SHOULD compare candidates to one another, not only to global constants.

Record at least:

- area fraction;
- bounding box;
- connected-component count;
- component containing each positive point;
- containment/nesting relation between candidates;
- pairwise IoU;
- area ratio between nested candidates;
- boundary contact;
- compactness / perimeter proxy;
- positive-point distance to candidate boundary;
- box fill and spill ratios;
- prompt-mask overlap.

For a point inside several nested masks, the policy must be able to distinguish:

```text
small local part
whole object
object plus neighbouring objects
```

It MUST NOT assume the smallest or largest candidate is always correct.

### 2.4 Model score semantics

The SAM/model score is one ranking feature only.

The policy MUST:

- preserve the adapter-declared score name/semantics;
- avoid exposing it as `Confidence XX%`;
- avoid treating it as calibrated IoU or correctness probability unless separately proven;
- benchmark score usefulness on frozen real scenes.

### 2.5 Optional Gaussian support sanity

Low-cost Gaussian diagnostics MAY be used as:

- candidate computability check;
- gross support sparsity warning;
- tie-breaker when two 2D candidates are otherwise comparable;
- detector for obviously disconnected projected support.

They MUST NOT:

- become formal P/N/V Evidence;
- classify Gaussian ownership;
- be the sole reason to choose a mask;
- replace 2D prompt consistency;
- use nearest/top-k/distance attribution as production semantics;
- reject all editable candidates merely because the center-projection support probe is weak.

This keeps Anchor proposal selection primarily 2D while exploiting scene information only as a bounded sanity signal.

### 2.6 Versioned decision

Suggested output:

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

### 2.7 Automatic selection gate

Auto-select only when:

- exactly one eligible candidate remains; or
- Top-1 has a benchmark-calibrated decision margin over materially different alternatives; and
- no ambiguity reason is active.

Examples of ambiguity reasons:

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

Thresholds are policy data, not UI constants.

## Stage 3 — Candidate Acceptance / Editing / Confirm

### 3.1 Selected

When the decision is `selected`:

```text
selected AutoMaskProposal
→ accepted auto proposal
→ seed/replace Editing Mask
```

This remains unconfirmed. Existing Stable Mask remains authoritative until Confirm Mask.

### 3.2 Ambiguous

When the decision is `ambiguous`:

- preserve all eligible bounded candidates;
- show 2–4 materially distinct alternatives when available;
- highlight the proposed default without claiming certainty;
- offer:
  - select an alternative;
  - add positive/negative point;
  - draw/tighten Box;
  - add prompt constraint;
  - enter Paint/Erase editing;
  - clear/restart prompts.

The system MUST NOT publish an ambiguous candidate as Stable automatically.

A user's explicit candidate choice resolves proposal ambiguity and creates/updates Editing Mask.

### 3.3 Unavailable

When no eligible candidate exists:

- keep RGB and PromptState;
- expose structured causes;
- allow prompt revision, manual Empty → Paint flow, and Retry;
- do not relabel the View as Render Failed.

Deprecate overloaded `anchorMaskUnavailable` semantics in favor of:

```text
maskProposalFailed       technical model/runtime failure
maskProposalUnavailable  no eligible prompt-consistent candidate
maskProposalAmbiguous    several plausible candidates
maskArtifactInvalid      invalid output artifact
```

A compatibility adapter MAY map legacy errors, but the product state must preserve the distinction.

### 3.4 Manual editing

Paint/Erase changes the Editing Mask only.

After local pixel editing:

- the accepted proposal remains recorded as provenance for correctness/debug;
- the Editing Mask source becomes `hybrid` or `manual`;
- proposal ranking is not silently rerun;
- PromptState is not rewritten from painted pixels;
- the user may explicitly choose “Use edit as prompt constraint” in a future capability, but that is not implicit.

### 3.5 Confirm and assessment integration

Confirm Mask:

```text
current Editing Mask
→ new Stable Mask revision
→ Ticket 07 local ViewAssessmentPolicy
→ Good / Review / Failed
→ Participation default
```

Proposal decision and ViewAssessment are separate:

```text
ProposalDecision
= which 2D candidate should seed Editing Mask?

ViewAssessment
= is the resulting Stable Mask suitable for participation?
```

Ticket 07A must not collapse these into one confidence value.

Confirm Anchor remains governed by Ticket 05:

- current Stable Mask exists;
- no latest Prompt/proposal/edit operation is pending;
- exact RGB/Mask/Camera identity matches;
- support computability gate passes;
- soft warnings remain user-overridable.

A user-confirmed manually edited Mask may proceed even if automatic proposal ranking was ambiguous.

## UI requirements

Add a selected-view proposal surface adjacent to the Prompt/Edit toolbar.

Required states:

```text
No prompts
Generating proposals
Proposal selected
Proposal ambiguous
Proposal unavailable
Editing
Stable confirmed
```

Required UI:

- candidate thumbnails/overlays for materially distinct alternatives;
- selected/default candidate indication;
- structured ambiguity reason;
- prompt refinement shortcuts;
- explicit Accept Candidate;
- explicit Confirm Mask;
- no uncalibrated confidence percentage;
- preserve Ticket 07 Mask Quality and Participation as separate rows.

## Acceptance criteria

### Pipeline

- [ ] Stage 1 returns a bounded identity-bound proposal set.
- [ ] Stage 2 uses versioned 2D-first ranking and does not select solely by model score.
- [ ] Stage 3 requires explicit Stable Mask confirmation.
- [ ] The complete pipeline is replayable from RGB + PromptState + model/adapter/policy identities.
- [ ] Candidate/Editing/Stable states are distinct.

### Ranking and ambiguity

- [ ] Positive/negative points, Box, and mask constraints participate in hard consistency.
- [ ] Candidate hierarchy and pairwise relations are computed.
- [ ] Nested part/whole alternatives can trigger ambiguity.
- [ ] Large neighbouring-object leakage can trigger ambiguity/review rather than silent auto-selection.
- [ ] Weak optional Gaussian support does not destroy otherwise editable proposals.
- [ ] Model score is preserved but never treated as calibrated correctness probability.
- [ ] Auto-selection margins are benchmark-derived and policy-versioned.

### Recovery

- [ ] `maskProposalAmbiguous` preserves candidates and offers candidate selection/prompt refinement/manual editing.
- [ ] `maskProposalUnavailable` preserves RGB and PromptState.
- [ ] Model failure is distinct from unavailable and ambiguous.
- [ ] Existing Stable Mask remains current until a new Confirm succeeds.
- [ ] Late/stale ranking or proposal results cannot replace a newer Editing Mask.
- [ ] Manual Paint/Erase can recover from every proposal state.

### Ticket 05 / 07 integration

- [ ] Confirm Anchor cannot run against pending prompt/proposal/edit state.
- [ ] Proposal ambiguity and Ticket 07 Review are represented separately.
- [ ] User Confirmed authority remains final for Participation defaults.
- [ ] Stable Mask replacement invalidates only exact dependent Evidence/Candidate state as already specified.

## Required real-scene validation

The ticket cannot be closed with fake-predictor contract tests alone.

Use frozen authoritative gsplat RGB cases including:

- table top surrounded by chairs;
- full table versus table-top part;
- chair beside table with similar color;
- cabinet door versus whole cabinet;
- monitor versus wall/desk;
- thin object;
- object touching image boundary;
- highly fragmented 3DGS render;
- small object;
- no valid proposal;
- multiple plausible nested proposals.

Report:

```text
first-interaction acceptable-mask rate
acceptable mask after one refinement
mean number of prompt actions
neighbour-object contamination
reference-mask IoU where available
ambiguous rate
false auto-selection rate
proposal-unavailable rate
manual recovery success
latency and peak VRAM
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

An oversized contaminated mask is not an acceptable silent success.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- Locked SAM 3.1 GPU benchmark
- Real browser Prompt/Edit/alternative-selection walkthrough
- Frozen-scene ranking benchmark
- Stale async and Retry stress
- Ticket 05 Confirm and Ticket 07 Assessment integration tests

## Non-goals

- No Generated View adaptive camera planner; Ticket 08 owns it.
- No cross-view proposal ranking.
- No formal P/N/V Evidence.
- No semantic object database.
- No requirement that Text Prompt be production-enabled in Phase A.
- No direct 3D Candidate editing.
- No use of support probe as Gaussian ownership classification.

## Dependency graph update

The implementation graph should become:

```text
03 + 04
   ↓
  04A
   ↓
  05
   ↓
  06
   ↓
  07
   ↓
  07A
   ↓
  08
```

Because Tickets 05–07 are already implemented, 04A/07A are retrofit hardening tickets. Closure requires rerunning their affected validation suites.

Ticket 08 MUST depend on 07A so adaptive planning consumes a confirmed Anchor produced by the completed quality pipeline rather than the current point-only compatibility path.
