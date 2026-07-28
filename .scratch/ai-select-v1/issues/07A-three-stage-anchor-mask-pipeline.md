# 07A — Complete Three-Stage Anchor Mask Pipeline + Ranking / Ambiguity UX

Status: ready-for-agent — DG-21 / Final Spec v1.1 Amendment 002 approved

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
Stage 1 — Prompt-conditioned Proposal Generation
Stage 2 — 2D-first Proposal Ranking / Ambiguity Decision
Stage 3 — Candidate Acceptance / Editing / Confirm
```

Ticket 04A implements Stage 1's PromptState, explicit tools, adapter capability contract, and bounded proposal artifact. Ticket 07A integrates that output into a production-quality Anchor Mask workflow and validates all three stages together.

## Context

The current point-only path selects the highest-scored SAM candidate that satisfies basic point and area checks. Real scenes expose two recurrent failures:

```text
one click on table top
→ oversized table + neighbouring chairs mask

otherwise plausible prompt
→ overloaded anchorMaskUnavailable
```

Ticket 07 assesses an already published Stable Mask. It cannot decide which pre-Stable proposal should seed the Editing Mask. ProposalDecision therefore remains separate from ViewAssessmentPolicy.

## Inputs / preconditions

- Ticket 04A PromptState, adapter capabilities, and AutoMaskProposalSet
- Exact Anchor RGB / CameraBinding / context identity
- Existing Editing Mask / Stable Mask lifecycle
- Ticket 05 Anchor validation and support-probe seam
- Ticket 07 ViewAssessmentPolicy and Participation semantics
- Frozen real-scene Anchor RGB with reviewed reference masks
- Locked SAM 3.1 or declared replacement adapter/runtime

## Outputs / handoff artifacts

- Versioned `anchor-mask-ranking/v1` policy
- Per-proposal 2D feature records
- Optional bounded support-sanity records
- ProposalDecision: selected / ambiguous / unavailable
- Alternative-proposal chooser and actionable ambiguity UI
- Accepted proposal → Editing Mask integration
- Refined proposal failure taxonomy
- Locked-runtime quality benchmark and thresholds
- Confirmed Anchor contract safe for Ticket 08

# Stage 1 — Proposal Generation integration

Consume Ticket 04A output without collapsing alternatives.

Stage 1 MUST:

- preserve a deterministic bounded candidate set;
- preserve raw model score and declared semantics;
- bind every proposal to exact RGB, PromptState, model, adapter, capability, policy, and attempt identities;
- reject invalid candidates individually without discarding valid alternatives;
- retain diagnostics explaining why no eligible candidate remained.

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

- positive point outside Mask;
- negative point inside Mask;
- positive Box below required fill/containment policy;
- negative Box above allowed overlap policy;
- positive/negative mask constraint above disagreement threshold;
- active Text constraint unsupported or unfulfilled under adapter semantics;
- dimensions, RGB, Prompt, adapter, or policy identity mismatch.

Positive and negative support for each prompt family is capability-gated. Hard filters and thresholds MUST be versioned and tested.

## 2.3 Candidate hierarchy and relative geometry

Compare candidates to one another, not only against global thresholds.

Record at least:

- area fraction and bounding box;
- connected-component count;
- component containing each positive point;
- containment/nesting graph;
- pairwise IoU and area ratio;
- boundary-contact fraction;
- compactness/perimeter proxy;
- positive-point distance to boundary;
- Box fill and spill ratios;
- prompt-mask overlap;
- material-distinctness used to deduplicate alternatives.

For a point inside nested masks, the policy must distinguish:

```text
local part
whole object
object plus neighbouring objects
```

It MUST NOT assume the smallest or largest point-containing Mask is always correct.

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
→ explicitly accepted auto proposal
→ seed/replace Editing Mask
```

This remains unconfirmed. The previous Stable Mask remains authoritative until Confirm Mask succeeds.

## 3.2 Ambiguous

When ambiguous:

- preserve eligible bounded candidates;
- display 2–4 materially distinct alternatives where available;
- mark a suggested default without claiming certainty;
- allow alternative selection, positive/negative point, Box refinement, prompt constraint, Text where supported, Paint/Erase, or prompt reset.

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

- a current Stable Mask exists;
- no latest Prompt/proposal/edit operation is pending;
- unresolved ambiguity has been explicitly resolved or bypassed by manual editing;
- exact RGB/Mask/Camera identity matches;
- support computability gate passes;
- soft warnings remain user-overridable.

A user-confirmed manual/hybrid Mask may proceed even when automatic ranking was ambiguous or unavailable.

# Scope relative to non-Anchor Views

The domain and toolbar may be reused for Generated and User-added View correction. Ticket 07A's mandatory three-stage automatic selection and benchmark gate apply to the Anchor path.

This ticket MUST NOT break the current Generated View contract in which an automatic Stable Mask and assessment can publish atomically. Extending proposal alternatives to automatic Generated View publication requires an explicit later policy/ticket or Ticket 12 Repropagate integration.

# UI requirements

Required proposal states:

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

- screenshot-tool-style Prompt/Edit toolbar from Ticket 04A;
- candidate thumbnails/overlays for materially distinct alternatives;
- selected/suggested candidate indication;
- structured ambiguity reason and corrective actions;
- explicit Accept Candidate and Confirm Mask;
- no uncalibrated confidence percentage;
- Ticket 07 Mask Quality and Participation remain separate rows.

# Acceptance criteria

## Pipeline

- [ ] Stage 1 returns a bounded identity-bound proposal set.
- [ ] Production validation uses a backend capable of meaningful proposal alternatives or a declared alternative generator.
- [ ] Stage 2 is versioned, 2D-first, and not model-score-only.
- [ ] Stage 3 requires explicit Stable Mask confirmation.
- [ ] Pipeline is replayable from RGB + PromptState + model/adapter/policy identities.
- [ ] Proposal, decision, Editing, and Stable states are distinct.

## Ranking and ambiguity

- [ ] Positive/negative Point, Box, mask constraints, and supported Text participate according to capability.
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

- [ ] Confirm Anchor blocks pending/unresolved prompt/proposal/edit state.
- [ ] Proposal ambiguity and Ticket 07 Review are separate.
- [ ] User-confirmed authority remains final for Participation defaults.
- [ ] Stable Mask replacement invalidates only exact dependent Evidence/Candidate state.
- [ ] Existing Generated View auto-publication and assessment regressions pass.

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
- Real browser Prompt/Edit/alternative-selection walkthrough
- Frozen-scene ranking and model-score/support ablations
- Stale async and Retry stress
- Ticket 05 Confirm and Ticket 07 Assessment integration
- Generated View automatic publication regression

# Non-goals

- No Adaptive Generated View planner; Ticket 08 owns it.
- No cross-view proposal ranking.
- No formal P/N/V Evidence.
- No semantic object database.
- No requirement to enable Text in Phase A.
- No direct 3D Candidate editing.
- No use of support probe as Gaussian ownership classification.

# Dependency update

The v2.3 retrofit graph is:

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