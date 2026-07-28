# DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline

- **Status:** CLOSED
- **Date:** 2026-07-28
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendment 002
- **Implementation owners:** Tickets 04A and 07A
- **Completion owner:** Ticket 07A

## Decision question

How should AI Select turn user intent on an authoritative Anchor RGB into a Stable Anchor Mask when one point may correspond to several valid SAM proposals, the current point-only adapter may return an oversized mask or `anchorMaskUnavailable`, and direct pixel editing currently conflicts with Box-drag interaction?

## Context

The existing implementation correctly separates:

```text
RGB
Editing Mask
Stable Mask
Evidence
Candidate
```

It also provides positive/negative point prompts, direct Brush Add/Erase, atomic Stable Mask confirmation, and Anchor support validation.

However, the current interaction and model contract collapse several distinct concerns:

```text
click
→ point-only SAM request
→ choose highest-scored point-consistent candidate
→ Editing Mask
```

Problems observed in real scenes include:

- a point on a table top yields a mask covering neighbouring chairs;
- several plausible nested masks exist but only one is returned to the UI;
- raw model score is used as the main ordering signal;
- all candidates may be rejected and surfaced as the overloaded `anchorMaskUnavailable`;
- image drag is already bound to pixel Brush, so Box prompt authoring has no clean gesture;
- prompt constraints and direct bitmap edits are not separate user modes.

Ticket 07 ViewAssessmentPolicy begins only after a Stable Mask exists. It cannot decide which pre-Stable model proposal should seed the Editing Mask.

## Decision

Adopt a Three-Stage Anchor Mask Pipeline:

```text
Prompt Authoring
    ↓
Stage 1 — Prompt-conditioned Proposal Generation
    ↓
Stage 2 — 2D-first Proposal Ranking / Ambiguity Decision
    ↓
Stage 3 — Candidate Acceptance / Editing / Confirm
    ↓
Stable Anchor Mask
```

### Ticket ownership

```text
Ticket 04A
= Prompt Authoring + generic multi-prompt protocol + bounded proposal set

Ticket 07A
= Stage 2 ranking + ambiguity UX + Stage 3 integration
  + end-to-end production validation
```

Ticket 07A is the completion owner for the full pipeline.

## Decision 1 — Prompt Authoring and pixel editing are separate modes

Prompt Authoring expresses model constraints:

```text
Positive Point
Negative Point
Box
Positive/Negative Mask Constraint
Text Prompt when capability exists
```

Pixel Editing directly changes the current Editing Mask:

```text
Paint
Erase
```

The two modes have separate state and histories.

No pointer gesture has hidden semantics. Drag means Box only in Box mode, prompt stroke only in Prompt Brush mode, and bitmap edit only in Paint/Erase mode.

## Decision 2 — Model capabilities are explicit

Prompt support is determined by a versioned adapter capability contract, not by the model name or UI assumption.

The current point-only SAM 3.1 adapter remains valid. Box, mask input, negative mask constraints, text, and multi-candidate support are enabled only when the selected adapter advertises and implements them.

The UI must not accept unsupported prompts and silently ignore them.

## Decision 3 — Preserve proposals before selection

A model response may contain multiple plausible masks. The Companion preserves a bounded, identity-bound proposal set.

Every proposal binds:

```text
Target / context dependency
View and RGB digest
PromptState digest
model manifest
adapter capability identity
proposal policy
attempt identity
mask artifact digest
raw model score and score semantics where available
```

No proposal becomes Stable automatically.

## Decision 4 — Ranking is 2D-first

Anchor Mask authoring is primarily an interactive 2D segmentation problem.

Stage 2 must prioritize:

1. hard prompt consistency;
2. relative candidate geometry and nesting;
3. 2D structural quality;
4. model-declared score;
5. optional low-cost Gaussian support sanity.

The system may use low-cost Gaussian support to detect gross incompatibility or as a bounded tie-breaker. It may not use support-probe center projection as the sole selector, formal ownership evidence, or a replacement for P/N/V.

This decision avoids making Anchor Mask quality depend on an approximate 3D attribution path while still allowing scene information to catch obvious failures.

## Decision 5 — Ambiguity is a first-class product state

When several materially different candidates remain plausible and no calibrated margin separates them:

```text
ProposalDecision = ambiguous
```

The system must:

- preserve alternatives;
- show an actionable reason;
- allow candidate selection;
- allow additional point/box/mask/text prompts;
- allow manual Paint/Erase recovery.

It must not silently choose an oversized mask or convert ambiguity into a technical failure.

## Decision 6 — Proposal decision and View Assessment are different

```text
ProposalDecision
= which proposal should seed Editing Mask?

ViewAssessmentPolicy
= is the confirmed Stable Mask suitable for participation?
```

They remain separate state machines and must not be merged into a single confidence number.

Ticket 07 continues to own Good / Review / Failed and Participation defaults after Stable Mask publication.

## Decision 7 — Stable Mask authority is unchanged

The existing lifecycle remains normative:

```text
Prompt / Proposal changes
→ no Stable Mask mutation

Accepted proposal
→ Editing Mask only

Paint / Erase
→ Editing Mask only

Confirm Mask
→ new Stable Mask revision
→ exact dependent Evidence/Candidate invalidation
```

A prior Stable Mask remains current until a replacement Confirm succeeds.

## Decision 8 — Error taxonomy is refined

Replace overloaded product use of `anchorMaskUnavailable` with distinct states:

```text
maskProposalFailed
maskProposalUnavailable
maskProposalAmbiguous
maskArtifactInvalid
```

Legacy transport codes may be mapped during migration, but the browser/domain state must preserve the difference.

## Decision 9 — Text Prompt is capability-gated

Text/concept prompting is a planned prompt type, not a mandatory Phase A backend requirement.

The data model and toolbar may reserve it. It becomes usable only when a locked, versioned adapter advertises support and passes model/runtime validation.

No external detector or semantic object database is required by this decision.

## Decision 10 — Ticket 08 follows the completed Anchor pipeline

Adaptive Generated View planning should consume a confirmed Anchor from the completed Three-Stage pipeline.

Ticket 08 therefore depends on Ticket 07A. This does not make proposal ranking part of the planner; it prevents planner evaluation from being dominated by a known weak point-only Anchor input.

## Rejected alternatives

### A. Keep point-only inference and tune thresholds

Rejected because threshold tuning does not resolve nested part/object/group ambiguity and can increase `anchorMaskUnavailable`.

### B. Select the highest raw model score

Rejected because the score is adapter-local and not established as calibrated user-intent correctness.

### C. Always select the smallest point-containing mask

Rejected because users may intend a whole object, and thin/fragmented parts make smallest-mask bias unstable.

### D. Always select the largest point-containing mask

Rejected because it causes neighbouring-object leakage.

### E. Make Gaussian support the primary selector

Rejected because the current support probe is an approximate computability diagnostic, not same-decision ownership Evidence.

### F. Run a semantic detector first as a mandatory dependency

Rejected for v1 because category semantics are not necessary for arbitrary parts and unknown objects. Text/concept adapters remain optional extensions.

### G. Treat direct Brush edits as model prompts automatically

Rejected because it destroys the distinction between prompt constraints and explicit user-authored pixel corrections.

## Consequences

### Positive

- richer user intent with fewer accidental masks;
- Box and negative prompts become first-class;
- multiple SAM proposals are not discarded prematurely;
- ambiguity becomes recoverable rather than a false success/failure;
- existing Stable Mask and Evidence lifecycles remain intact;
- text/concept support can be added without another product rewrite;
- Ticket 08 receives a more reliable Anchor.

### Costs

- new prompt and candidate domain state;
- a generic adapter protocol beyond points;
- proposal-ranking policy and benchmark dataset;
- a candidate-choice UI;
- additional runtime latency/VRAM for multiple proposals;
- affected Ticket 05/07 tests must be rerun.

### Risks and controls

- ranking overfit → frozen real-scene benchmark and versioned policy;
- too many alternatives → bounded material-distinct proposal set;
- support-probe misuse → explicit 2D-first and no-ownership constraints;
- text capability drift → explicit capability and runtime identity;
- stale UI results → exact Prompt/RGB/attempt binding;
- confusing toolbar → explicit Prompt/Edit mode separation.

## Non-goals

DG-21 does not:

- change the AI Select tool model;
- change Stable Mask confirmation semantics;
- require semantic labels;
- implement adaptive Generated View planning;
- implement formal P/N/V Evidence;
- make Candidate provenance UI normative;
- create a second 3D editor;
- guarantee that every single click produces an unambiguous object.

## Required implementation sequence

```text
04A Prompt Authoring / Proposal Foundation
  ↓
07A Ranking / Ambiguity / Acceptance / Production Validation
  ↓
08 Adaptive View Planner
```
