# AI Select Final Spec v1.1 — Amendment 002

## Prompt Authoring and Three-Stage Anchor Mask Pipeline

**Status:** Normative amendment to Final Spec v1.1  
**Date:** 2026-07-28  
**Applies to:** `ai-select-v1`  
**Amends:** Final Spec v1.1 §§0, 1–4, 7, 10–13, 23–24, 26, 28, 30–32  
**Related:** DG-21, Tickets 04A/07A, DG-09, DG-12, DG-19  
**Does not supersede:** Amendment 001 renderer/Evidence identity requirements

This amendment is part of Final Spec v1.1 and has equal normative force for the clauses it amends.

It strengthens Anchor Mask authoring without changing:

- RGB / Mask / Evidence / Candidate lifecycle separation;
- Stable Mask confirmation authority;
- Direct P/N/V Evidence semantics;
- Native Selection operations;
- Adaptive Generated View policy ownership.

---

# A0. Scope

The mandatory Three-Stage pipeline in this amendment applies to the **Anchor Mask**.

The PromptState domain and Prompt/Edit toolbar SHOULD be reusable for Generated and User-added View correction. This amendment does not silently replace the current Generated View contract in which an automatic Stable Mask and ViewAssessment may publish atomically. Extending multi-proposal acceptance to automatic Generated View publication requires an explicit later policy/ticket or Ticket 12 Repropagate integration.

A single positive click remains a valid low-friction entry. The product MUST NOT assume that one click uniquely identifies one correct object or part.

---

# A1. Decision Gate and ownership

Final Spec v1.1 §0.2 is extended with:

```text
DG-21  CLOSED
Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
```

Anchor authoring follows:

```text
Prompt Authoring
→ Stage 1: Prompt-conditioned Proposal Generation
→ Stage 2: 2D-first Ranking / Ambiguity Decision
→ Stage 3: Candidate Acceptance / Editing / Confirm
→ Stable Anchor Mask
```

Implementation ownership:

```text
Ticket 04A
= PromptState + explicit tools + adapter capabilities + bounded proposal set

Ticket 07A
= ranking + ambiguity + acceptance/editing integration
  + end-to-end locked-runtime quality validation
```

Ticket 07A is the completion owner for the full Three-Stage Anchor Mask Pipeline.

---

# A2. Product definition clarification

The AI Select product definition is extended:

> In the AI View Dock, users author explicit point, Box, mask-constraint, and capability-gated Text prompts, inspect one or more model proposals, resolve ambiguity, and optionally perform direct Paint/Erase correction before confirming a Stable Anchor Mask.

Prompt Authoring and Pixel Editing are different operations and different state histories.

---

# A3. Runtime ownership

Browser Editor owns:

```text
per-view PromptState
active Prompt/Edit tool
Prompt-local history
proposal presentation and user choice
Editing Mask pixel history
Stable Mask confirmation
```

Selection Service Companion owns:

```text
adapter capability declaration
prompt-conditioned proposal generation
bounded proposal artifact production
versioned proposal-ranking policy
ProposalDecision diagnostics
```

A backend MAY combine proposal generation and ranking internally, but the product/artifact boundary MUST preserve the identities and states defined below.

---

# A4. PromptState domain

```ts
interface PointPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    xPx: number;
    yPx: number;
}

interface BoxPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    x0Px: number;
    y0Px: number;
    x1Px: number;
    y1Px: number;
}

interface MaskConstraintPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    artifact: BinaryMaskArtifact;
}

interface TextPrompt {
    promptId: string;
    polarity: 'include' | 'exclude';
    text: string;
    locale?: string;
}

interface PromptState {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    revision: number;
    points: readonly PointPrompt[];
    boxes: readonly BoxPrompt[];
    maskConstraints: readonly MaskConstraintPrompt[];
    textPrompts: readonly TextPrompt[];
    digest: string;
}
```

Every PromptState MUST bind the exact authoritative RGB it addresses.

PromptState is neither an Editing Mask nor a Stable Mask.

Prompt revisions MUST NOT:

- mutate the current Stable Mask;
- invalidate formal Evidence/Candidate before a new Stable Mask is confirmed;
- silently overwrite locally edited pixels;
- attach to a newer RGB revision.

---

# A5. Prompt adapter capabilities

Prompt support MUST be explicit and versioned.

```ts
interface PromptAdapterCapabilities {
    points: boolean;
    negativePoints: boolean;
    boxes: boolean;
    negativeBoxes: boolean;
    maskInput: boolean;
    negativeMaskConstraints: boolean;
    text: boolean;
    negativeText: boolean;
    multiCandidateOutput: boolean;
    capabilityDigest: string;
}
```

The UI and protocol MUST disable or reject unsupported prompt types. They MUST NOT infer support from a model name, accept unsupported input, or silently ignore it.

Text and negative Text are capability-gated. Final Spec v1.1 does not require every installed SAM adapter to support them.

A single-candidate adapter may return a one-element proposal set for compatibility. Ticket 07A cannot close its production quality gate unless the locked backend provides materially distinct alternatives or an explicit versioned proposal generator provides them.

---

# A6. Prompt and Edit tools

## A6.1 Prompt tools

```text
Positive Point
Negative Point
Positive Box
Negative Box — when supported
Positive Prompt Brush / Mask Constraint
Negative Prompt Brush / Mask Constraint
Positive Text Prompt — when supported
Negative Text Prompt — when supported
```

Prompt tools update PromptState and may request proposals.

## A6.2 Edit tools

```text
Paint
Erase
Brush Size
Mask Undo
Mask Redo
Clear
Restore Accepted Auto
```

Edit tools modify Editing Mask only.

## A6.3 Pointer semantics

```text
click under Point tool   → point prompt
drag under Box tool      → Box prompt
drag under Prompt Brush  → mask constraint
drag under Paint/Erase   → Editing Mask pixel edit
```

There is no implicit long-press/drag behavior that changes Mask pixels without an explicit Edit tool.

Prompt history and Editing history MUST be independent and focus-routed.

---

# A7. Stage 1 — Prompt-conditioned Proposal Generation

Input:

```text
authoritative Anchor RGB
+ exact PromptState
+ model / adapter / capability identity
+ proposal policy
+ attempt identity
```

Output:

```ts
interface AutoMaskProposal {
    proposalId: string;
    mask: BinaryMaskArtifact;
    sourceIndex: number;
    modelScore?: number;
    modelScoreSemantics?: string;
    promptConsistency: PromptConsistencyFacts;
}

interface AutoMaskProposalSet {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    promptStateDigest: string;
    modelManifestDigest: string;
    adapterCapabilityDigest: string;
    proposalPolicyVersion: string;
    proposals: readonly AutoMaskProposal[];
    truncation?: ProposalTruncationRecord;
}
```

Every proposal MUST bind exact RGB, PromptState, model, adapter, capability, policy, and attempt identities.

The Companion MUST preserve a deterministic bounded set of structurally valid alternatives required by policy. It MUST NOT collapse all candidates solely by raw model score.

Invalid candidates may be rejected individually without discarding valid alternatives. Stage 1 does not publish Stable Mask.

---

# A8. Stage 2 — 2D-first Proposal Ranking

Ranking MUST be versioned and 2D-first.

Required feature groups:

```text
hard Point/Box/mask/Text prompt consistency
candidate area and bounding geometry
connected components
candidate containment/nesting
pairwise IoU and area ratio
boundary contact
positive-point distance to boundary
Box fill/spill
prompt-mask overlap
model score with declared semantics
```

The raw model score MUST NOT be exposed or treated as calibrated correctness probability unless separately benchmarked and declared.

Low-cost Gaussian support MAY be used only as:

- computability check;
- gross support sanity signal;
- bounded tie-breaker;
- detector of clearly disconnected projected support.

It MUST NOT:

```text
become formal P/N/V Evidence
classify Gaussian ownership
be the primary selector
replace hard 2D prompt consistency
use nearest/top-k/distance attribution as formal semantics
turn weak center-projection support into automatic proposal destruction
```

```ts
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

Automatic selection is allowed only when one candidate is uniquely eligible, or a benchmark-calibrated and repeatably stable margin separates it from materially different alternatives.

---

# A9. Stage 3 — Acceptance / Editing / Confirm

Selected:

```text
selected AutoMaskProposal
→ explicitly accepted auto proposal
→ Editing Mask
```

Ambiguous:

```text
preserve alternatives
→ user chooses candidate or refines PromptState
→ Editing Mask
```

Unavailable:

```text
preserve RGB and PromptState
→ refine prompts / Retry / manual Empty → Paint
```

Paint/Erase may modify Editing Mask after proposal acceptance.

Only Confirm Mask publishes a Stable Mask.

Paint/Erase MUST NOT rewrite PromptState. Proposal ranking MUST NOT rerun silently after direct pixel edits.

---

# A10. Ambiguity

Ambiguity is a first-class pre-Stable state.

Examples:

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

When ambiguous, the UI MUST:

- preserve materially distinct alternatives;
- show structured actionable reasons;
- support explicit candidate choice;
- support prompt refinement;
- support manual Paint/Erase recovery.

It MUST NOT silently auto-publish an ambiguous candidate, report ambiguity as View Render Failure, or expose an uncalibrated confidence percentage.

---

# A11. ProposalDecision versus ViewAssessment

```text
ProposalDecision
= pre-Stable proposal choice

ViewAssessmentPolicy
= post-Stable quality and Participation assessment
```

After Confirm Mask:

```text
Stable Mask
→ ViewAssessmentPolicy
→ Good / Review / Failed
→ Participation default
```

Ticket 07 rules remain unchanged. A user may explicitly select/edit/confirm a proposal that was previously ambiguous; the resulting Stable Mask is assessed normally.

---

# A12. Lifecycle and dirty semantics

Additional pre-Stable states:

```text
Prompt None
Prompt Authored
Proposal Pending
Proposal Selected
Proposal Ambiguous
Proposal Unavailable
Editing Mask
Stable Mask
```

Normative lifecycle:

```text
Prompt change
→ proposal changes
→ Stable Mask unchanged

Accept proposal
→ Editing Mask changes
→ Stable Mask unchanged

Paint/Erase
→ Editing Mask changes
→ PromptState unchanged

Confirm Mask
→ new Stable Mask revision
→ dependent per-view Evidence stale
→ Included Candidate stale
```

`Restore Accepted Auto` MUST restore the latest explicitly accepted valid proposal for the current RGB/Prompt identity. It MUST NOT select the current highest raw score implicitly.

| Operation | Proposal | Per-view Evidence | Lift |
|---|---:|---:|---:|
| Change PromptState | Dirty/recompute | unchanged | unchanged |
| Accept another proposal | current Editing changes | unchanged | unchanged |
| Paint/Erase unconfirmed Editing Mask | unchanged | unchanged | unchanged |
| Confirm new Stable Mask | current | corresponding View Dirty | Dirty |
| Clear prompts while prior Stable exists | cleared | unchanged | unchanged |

---

# A13. Confirm Anchor amendment

Confirm Anchor MUST be blocked when:

- the latest Prompt/proposal request is pending;
- ProposalDecision is ambiguous and no proposal has been accepted or manually replaced;
- no current Stable Mask exists;
- Editing/Stable/RGB identities conflict;
- existing Ticket 05 hard gates fail.

Ambiguity is recoverable through candidate choice, prompt refinement, or manual editing.

The support probe remains a computability gate. It is not proposal-ranking ownership Evidence.

---

# A14. Failure taxonomy

```text
maskProposalFailed
= model/runtime/transport failure

maskProposalUnavailable
= no eligible prompt-consistent proposal

maskProposalAmbiguous
= several materially different plausible proposals

maskArtifactInvalid
= invalid proposal artifact
```

All preserve:

```text
AIView
authoritative RGB
PromptState
prior Stable Mask
prior Evidence/Candidate where identity-compatible
```

Recovery includes Retry, Point/Box/mask/Text refinement where supported, alternative selection, manual Paint/Erase, clear prompts, or Restart Target.

Legacy `anchorMaskUnavailable` MAY remain at a transport compatibility boundary, but browser/domain state MUST distinguish the causes above.

No proposal failure may relabel successful RGB as Render Failed.

---

# A15. Engineering stages and validation

## Stage M1 — Prompt/Proposal Foundation

Owner: Ticket 04A.

- PromptState and capability declaration;
- explicit Prompt/Edit tools;
- Point/Box/mask-constraint protocol;
- capability-gated Text;
- bounded proposal artifact;
- stale/retry/cancellation semantics.

## Stage M2 — Ranking and End-to-End Anchor Quality

Owner/completion gate: Ticket 07A.

- 2D-first ranking;
- candidate hierarchy and ambiguity;
- alternative selection;
- Editing/Confirm integration;
- Ticket 05/07 integration;
- frozen real-scene benchmark;
- locked SAM 3.1 or replacement-adapter browser/GPU validation.

Required validation additions:

1. Point-only versus Point+Box quality comparison.
2. Positive/negative prompt constraints.
3. Prompt Brush versus direct Paint separation.
4. Multiple proposal preservation.
5. Nested part/whole ambiguity fixture.
6. Table-top versus adjacent-chair contamination fixture.
7. Unavailable versus technical failure distinction.
8. Manual recovery from every proposal state.
9. No Stable/Evidence/Candidate invalidation before Confirm.
10. Locked real-model validation; fake-predictor tests alone are insufficient for 07A closure.
11. Model-score ablation.
12. Optional-support ablation proving support is not the primary selector.
13. Existing Generated View automatic publication regression.

Required metrics:

```text
first-interaction acceptable-mask rate
acceptable mask after one refinement
mean prompt actions
neighbour-object contamination
reference IoU where available
false auto-selection rate
ambiguous rate
proposal-unavailable rate
manual recovery success
latency
peak VRAM
```

---

# A16. Ticket graph amendment

Because Tickets 05–07 were implemented before this amendment, 04A/07A are retrofit hardening tickets.

```text
03 + 04 → 05 → 06 → 07
          │         │
          └→ 04A ──┘
                ↓
               07A
                ↓
               08
```

Ticket 04A depends on the existing Ticket 05 editor/Undo/Confirm seams. Ticket 07A depends on Ticket 04A and Ticket 07 assessment semantics. Ticket 08 MUST depend on Ticket 07A.

Affected Ticket 05/07 regression suites MUST be rerun after 04A/07A.

---

# A17. Non-goals

This amendment does not:

- require Text in every runtime;
- mandate an external semantic detector;
- create semantic object persistence;
- change Generated View planning policy;
- silently replace Generated View automatic Stable Mask publication;
- change formal P/N/V Evidence;
- allow proposals to bypass Stable Mask confirmation;
- merge ProposalDecision with ViewAssessment;
- introduce direct 3D Candidate editing;
- guarantee every single click is unambiguous.