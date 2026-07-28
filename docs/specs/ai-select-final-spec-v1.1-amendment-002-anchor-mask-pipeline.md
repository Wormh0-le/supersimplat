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

# A1. Decision Gate status

Final Spec v1.1 §0.2 is extended with:

```text
DG-21  CLOSED
Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline
```

DG-21 decides that Anchor Mask authoring follows:

```text
Prompt Authoring
→ Proposal Generation
→ Proposal Ranking / Ambiguity Decision
→ Candidate Acceptance / Editing
→ Confirm Mask
→ Stable Anchor Mask
```

Ticket 04A implements the Prompt/proposal foundation. Ticket 07A is the completion owner for the full pipeline.

---

# A2. Product definition clarification

The AI Select product definition is clarified:

> In the AI View Dock, users author explicit point, Box, mask-constraint, and capability-gated text prompts, inspect one or more model proposals, resolve ambiguity, and optionally perform direct Paint/Erase correction before confirming a Stable Mask.

A single positive click remains a valid low-friction entry, but the product MUST NOT assume that one click uniquely identifies one correct object or part.

---

# A3. Runtime ownership

Final Spec v1.1 §4 is extended.

Browser Editor owns:

```text
per-view PromptState
Prompt/Edit tool mode
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
proposal decision diagnostics
```

A backend MAY combine proposal generation and ranking internally, but the product/artifact boundary must preserve the identities and states defined below.

---

# A4. PromptState domain

Add the following normative per-view domain:

```ts
interface PromptState {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    revision: number;

    positivePoints: readonly PointPrompt[];
    negativePoints: readonly PointPrompt[];
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
- invalidate Evidence/Candidate before a new Stable Mask is confirmed;
- silently overwrite a locally edited Editing Mask;
- attach to a newer RGB revision.

---

# A5. Prompt adapter capabilities

Prompt support MUST be explicit and versioned.

```ts
interface PromptAdapterCapabilities {
    points: boolean;
    negativePoints: boolean;
    boxes: boolean;
    maskInput: boolean;
    negativeMaskConstraints: boolean;
    text: boolean;
    multiCandidateOutput: boolean;
    capabilityDigest: string;
}
```

The UI and protocol MUST reject or disable unsupported prompt types.

The system MUST NOT infer support from a model marketing name, accept an unsupported prompt, or silently ignore it.

Text Prompt is capability-gated. Final Spec v1.1 does not require every installed SAM adapter to support text.

---

# A6. Prompt and Edit tools

The selected AI View has two separate tool groups.

## A6.1 Prompt tools

```text
Positive Point
Negative Point
Box
Positive Prompt Brush / Mask Constraint
Negative Prompt Brush / Mask Constraint
Text Prompt — when supported
```

Prompt tools update PromptState and may request new proposals.

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

Pointer behavior MUST be determined by the active tool.

```text
click under Point tool  → point prompt
drag under Box tool     → box prompt
drag under Prompt Brush → prompt constraint
drag under Paint/Erase  → Editing Mask pixel change
```

There is no implicit long-press/drag behavior that changes the Mask without an explicit Edit tool.

Prompt and Editing histories MUST be independent and focus-routed.

---

# A7. Three-Stage Anchor Mask Pipeline

## A7.1 Stage 1 — Prompt-conditioned Proposal Generation

Input:

```text
authoritative Anchor RGB
+ exact PromptState
+ model / adapter / capability identity
+ proposal policy
```

Output:

```ts
interface AutoMaskProposalSet {
    schemaVersion: number;
    viewId: string;
    rgbDigest: string;
    promptStateDigest: string;
    modelManifestDigest: string;
    adapterCapabilityDigest: string;
    proposalPolicyVersion: string;
    proposals: readonly AutoMaskProposal[];
}
```

Each proposal MUST contain:

```text
proposalId
Mask artifact + digest
source/model candidate index
raw model score when available
declared score semantics
prompt-consistency facts
```

The Companion MUST preserve a bounded set of structurally valid alternatives needed by the current policy. It MUST NOT immediately collapse all candidates solely by raw model score.

Stage 1 does not publish Stable Mask.

## A7.2 Stage 2 — 2D-first Proposal Ranking

Proposal ranking MUST be versioned and 2D-first.

The ranking policy MUST consider:

```text
hard point/Box/mask prompt consistency
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

The raw model score MUST NOT be presented or treated as a calibrated correctness probability unless separately benchmarked and declared.

Low-cost Gaussian support MAY be used as a computability check, gross sanity signal, or bounded tie-breaker.

It MUST NOT:

```text
become formal P/N/V Evidence
classify Gaussian ownership
be the sole candidate selector
replace 2D prompt consistency
use nearest/top-k/distance attribution as formal semantics
turn weak center-projection support into automatic proposal destruction
```

Suggested decision:

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

Automatic selection is allowed only when one candidate is uniquely eligible or a benchmark-calibrated margin separates it from materially different alternatives.

## A7.3 Stage 3 — Acceptance / Editing / Confirm

Selected proposal:

```text
AutoMaskProposal
→ accepted auto proposal
→ Editing Mask
```

Ambiguous decision:

```text
preserve alternatives
→ user chooses candidate or refines prompts
→ Editing Mask
```

Unavailable decision:

```text
preserve RGB and PromptState
→ refine prompts / manual Paint / Retry
```

Paint/Erase can modify Editing Mask after proposal acceptance.

Only Confirm Mask publishes a Stable Mask.

---

# A8. Proposal ambiguity

Ambiguity is a first-class pre-Stable state.

Examples:

```text
nested-part-vs-whole
similar-score-different-area
multiple-disconnected-targets
box-spill
prompt-conflict
neighbour-object-leak-risk
insufficient-decision-margin
```

When ambiguous, the UI MUST:

- preserve materially distinct alternatives;
- show an actionable reason;
- support explicit candidate choice;
- support additional point/Box/mask/text prompts where available;
- support manual Paint/Erase recovery.

It MUST NOT:

- silently auto-publish a candidate as Stable;
- convert ambiguity into View Render Failure;
- expose an uncalibrated confidence percentage.

---

# A9. Proposal decision versus View Assessment

Proposal decision and ViewAssessmentPolicy are distinct.

```text
ProposalDecision
= pre-Stable candidate choice

ViewAssessmentPolicy
= post-Stable quality / participation assessment
```

After Confirm Mask:

```text
Stable Mask
→ ViewAssessmentPolicy
→ Good / Review / Failed
→ Participation default
```

Ticket 07 rules remain unchanged:

```text
Auto Good → Included
Auto Review → Excluded
User Confirmed → Included
Failed/no Stable Mask → Excluded
```

A user may explicitly select/edit/confirm a proposal that was previously ambiguous. The resulting Stable Mask is assessed normally.

---

# A10. Mask lifecycle amendment

Final Spec v1.1 §§10–11 are extended with these states:

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

These states do not replace AIView render/mask/evidence state separation.

Normative lifecycle:

```text
Prompt change
→ proposal state changes
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

`Restore Auto` MUST restore the latest explicitly accepted valid auto proposal for the current RGB/Prompt identity. It must not select the current highest raw model score implicitly.

---

# A11. Confirm Anchor amendment

Final Spec v1.1 §12 hard validation is extended.

Confirm Anchor MUST be blocked when:

- the latest Prompt/proposal request is pending;
- the ProposalDecision is ambiguous and no candidate has been explicitly accepted/edited;
- no current Stable Mask exists;
- Editing Mask/Stable Mask/RGB identities conflict;
- existing hard gates fail.

Proposal ambiguity is not itself a permanent failure. The user can resolve it through candidate selection, prompt refinement, or manual editing.

The support probe remains a computability gate. It is not proposal-ranking ownership Evidence.

---

# A12. Failure taxonomy and recovery

Final Spec v1.1 §§7.2 and 28 are extended.

```text
maskProposalFailed
= model/runtime/transport failure

maskProposalUnavailable
= no eligible prompt-consistent proposal

maskProposalAmbiguous
= multiple materially different plausible proposals

maskArtifactInvalid
= returned proposal artifact is invalid
```

All preserve:

```text
AIView
authoritative RGB
PromptState
prior Stable Mask
prior Evidence/Candidate where still identity-compatible
```

Recovery:

```text
Retry
add/remove Point
draw/tighten Box
add prompt constraint
choose alternative
Paint/Erase manually
Clear prompts
Restart Target
```

Legacy `anchorMaskUnavailable` MAY remain as a transport compatibility code during migration, but the current domain/UI MUST distinguish the causes above.

No proposal failure may relabel successful RGB as Render Failed.

---

# A13. Dirty and recompute semantics

Prompt, proposal, and unconfirmed Editing changes do not dirty formal Evidence or Candidate.

The existing table in §24.2 is extended:

| Operation | Proposal | Per-view Evidence | Lift |
|---|---:|---:|---:|
| Change PromptState | Dirty/recompute | unchanged | unchanged |
| Accept another proposal | current Editing changes | unchanged | unchanged |
| Paint/Erase unconfirmed Editing Mask | unchanged | unchanged | unchanged |
| Confirm new Stable Mask | current | corresponding View Dirty | Dirty |
| Clear prompts while prior Stable exists | cleared | unchanged | unchanged |

---

# A14. Engineering staging

Final Spec v1.1 §30 is extended before Evidence Stage 1.

## Stage M1 — Prompt/Proposal Foundation

- generic PromptState;
- adapter capability declaration;
- Point / Box / mask-constraint protocol;
- capability-gated Text;
- bounded multi-candidate proposal artifact;
- Prompt/Edit toolbar separation;
- stale/retry/cancellation semantics.

Implementation owner: Ticket 04A.

## Stage M2 — Ranking and End-to-End Anchor Quality

- 2D-first ranking;
- candidate hierarchy;
- ambiguity decision;
- alternative selection;
- Editing/Confirm integration;
- Ticket 05/07 integration;
- frozen real-scene benchmark;
- locked SAM 3.1 browser/GPU validation.

Implementation/completion owner: Ticket 07A.

Ticket 08 Adaptive View Planner starts after Stage M2.

---

# A15. Required validation additions

The v1.1 acceptance gates are extended with:

1. Point-only versus Point+Box quality comparison.
2. Positive/negative point constraint tests.
3. Prompt Brush versus direct Paint separation.
4. Multiple proposal preservation.
5. Nested part/whole ambiguity fixture.
6. Table-top versus adjacent-chair contamination fixture.
7. Proposal unavailable versus model failure distinction.
8. Manual recovery from every proposal state.
9. No Stable/Evidence/Candidate invalidation before Confirm.
10. Real SAM 3.1 locked-runtime validation; fake predictor tests alone are insufficient for Ticket 07A closure.
11. Model score ablation showing it is not the sole ranking basis.
12. Optional Gaussian support ablation confirming that support is bounded and not the primary selector.

Required product metric set:

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

The affected graph segment becomes:

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

Tickets 05–07 are already implemented and are treated as retrofit consumers. Their affected suites must be rerun after 04A/07A.

Ticket 08 MUST depend on Ticket 07A.

---

# A17. Non-goals

This amendment does not:

- require text prompting in every runtime;
- mandate an external semantic detector;
- create semantic object persistence;
- change Generated View planning policy;
- change formal P/N/V Evidence;
- allow a proposal to bypass Stable Mask confirmation;
- merge ProposalDecision with ViewAssessment confidence;
- introduce direct 3D Candidate editing;
- guarantee that every single click is unambiguous.
