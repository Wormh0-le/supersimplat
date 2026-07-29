# DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline

- **Status:** CLOSED
- **Date:** 2026-07-28
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendment 002
- **Foundation owner:** Ticket 04A
- **Visual-prompt adapter owner:** Ticket 04B
- **Algorithmic completion owner:** Ticket 07A
- **Interaction follow-up:** Ticket 07B under DG-22

## Decision question

How should AI Select turn user intent on an authoritative Anchor RGB into a Stable Anchor Mask when one point can correspond to several plausible SAM proposals, the point-only path may return an oversized Mask or overloaded unavailable result, and direct pixel editing conflicts with Box/Prompt-Brush interaction?

## Context

The product correctly separates:

```text
RGB
PromptState
AutoMaskProposalSet
ProposalDecision
Editing Mask
Stable Mask
Evidence
Candidate
```

The weak path was:

```text
click
→ point-only model request
→ choose highest-scored point-consistent candidate
→ Editing Mask
```

Observed problems include:

- a table-top Point including neighbouring chairs;
- nested part/object/group proposals collapsed before inspection;
- raw model score acting as the main ordering signal;
- several causes reported as one unavailable state;
- drag conflicts between Box, Prompt Brush, and Paint;
- Prompt constraints and direct bitmap corrections sharing one interaction mode.

Ticket 07 `ViewAssessmentPolicy` starts after Stable Mask publication and cannot choose the pre-Stable proposal.

## Decision

Adopt:

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

Implementation ownership is refined as:

```text
Ticket 04A
= PromptState + explicit Prompt/Edit tools
  + adapter capability contract + bounded proposal set

Ticket 04B
= locked real-adapter Box / Mask Constraint enablement
  + deterministic visual-prompt compilation

Ticket 07A
= proposal generation integration
  + 2D-first ranking / ambiguity
  + acceptance/editing/confirm integration
  + locked-runtime quality/calibration/performance validation

Ticket 07B / DG-22
= fitted-image floating palette with drag/collapse/Space-hide/no blind region
```

Ticket 07A remains the completion owner for the Three-Stage Anchor Mask Pipeline. Ticket 07B changes presentation and pointer routing only.

## Decision 1 — Anchor scope and reusable tooling

The mandatory Three-Stage pipeline applies to the Anchor Mask.

PromptState and Prompt/Edit tools may be reused for Generated and User-added View correction, but this decision does not replace the current Generated View automatic Stable Mask + ViewAssessment publication contract.

## Decision 2 — Prompt Authoring and Pixel Editing are separate

Prompt Authoring expresses model constraints:

```text
Positive/Negative Point
Positive/Negative Box when supported
Positive/Negative Mask Constraint when supported
Positive/Negative Text when supported
```

Pixel Editing directly changes Editing Mask:

```text
Paint
Erase
```

The two modes have separate state and histories. Box drag only acts in Box mode, Prompt Brush only authors Mask constraints, and Paint/Erase only modify Editing Mask.

## Decision 3 — Capabilities are explicit and truthful

Prompt support is declared by a versioned adapter capability contract, not inferred from model name.

Positive and negative support is explicit per prompt family. Unsupported tools are disabled/rejected and never silently ignored.

Ticket 04A established the generic capability/protocol seam. Ticket 04B enables real non-text visual prompts only after locked-runtime validation. Text remains an optional later capability.

A one-candidate point-only result is a legal compatibility proposal set but cannot alone satisfy Ticket 07A production quality closure.

## Decision 4 — Preserve proposals before selection

The Companion preserves a deterministic bounded proposal set. Every proposal binds:

```text
Target/context dependency
View and RGB digest
PromptState digest
model manifest
adapter capability/compiler identity
proposal policy
ranking policy
attempt identity
Mask artifact digest
raw model score and declared semantics
```

No Anchor proposal becomes Stable automatically.

Near-duplicate clustering and materially distinct representative selection occur before bounded truncation under Ticket 07A.

## Decision 5 — Ranking is 2D-first

Stage 2 prioritizes:

1. hard prompt consistency;
2. relative candidate geometry and nesting;
3. 2D structural quality;
4. model-declared score;
5. optional low-cost Gaussian support sanity.

A unique candidate is not automatically trustworthy. Ticket 07A must apply a structural single-candidate quality gate and calibrated decision margin.

Low-cost Gaussian support may detect gross incompatibility or break a tie between otherwise comparable 2D candidates. It cannot be the primary selector, ownership Evidence, or a replacement for P/N/V.

## Decision 6 — Ambiguity is a first-class state

When materially different candidates remain plausible without a calibrated stable margin:

```text
ProposalDecision = ambiguous
```

The system preserves alternatives and allows:

- candidate choice;
- Point/Box/Mask/Text refinement where supported;
- manual Paint/Erase recovery.

It must not silently select an oversized Mask or report ambiguity as a technical failure.

## Decision 7 — ProposalDecision and ViewAssessment are distinct

```text
ProposalDecision
= which pre-Stable proposal seeds Editing Mask?

ViewAssessmentPolicy
= is the confirmed Stable Mask suitable for participation?
```

They remain separate and do not form one confidence value. Ticket 07 continues to own Good / Review / Failed and Participation after Stable publication.

## Decision 8 — Stable Mask authority is unchanged

```text
Prompt / Proposal changes
→ Stable Mask unchanged

Accepted proposal / Paint / Erase
→ Editing Mask only

Confirm Mask
→ new Stable Mask revision
→ exact dependent Evidence/Candidate invalidation
```

A prior Stable Mask remains authoritative until replacement Confirm succeeds.

## Decision 9 — Error taxonomy is refined

```text
maskProposalFailed
maskProposalUnavailable
maskProposalAmbiguous
maskArtifactInvalid
```

Candidate-level rejection causes remain structured so unavailable does not collapse every failure into generic prompt conflict.

## Decision 10 — Text remains capability-gated

Text/concept prompting is planned, not mandatory in the current implementation sequence. It becomes usable only when a locked versioned adapter advertises support and passes runtime validation.

No external detector or semantic object database is required.

## Decision 11 — Ticket 08 follows resolved authoring

Adaptive Generated View planning consumes a confirmed Anchor from the completed Three-Stage pipeline and follows DG-22 no-blind-spot palette closure.

This does not make ranking or palette interaction part of the planner. It prevents planner evaluation from being dominated by unresolved Anchor authoring defects.

## Rejected alternatives

### Tune point-only thresholds

Rejected because threshold tuning cannot resolve nested part/object/group ambiguity and may increase unavailable results.

### Select the highest raw model score

Rejected because the score is adapter-local and not established as calibrated user-intent correctness.

### Always select smallest or largest Point-containing Mask

Rejected because either bias fails for part-versus-whole intent and neighbouring-object leakage.

### Make Gaussian support the primary selector

Rejected because support diagnostics are not same-decision ownership Evidence.

### Require a semantic detector first

Rejected for v1 because arbitrary parts and unknown objects do not require category semantics. Text/concept adapters remain optional.

### Treat Paint strokes as prompts automatically

Rejected because it destroys the distinction between model constraints and explicit pixel correction.

### Silently convert unsupported Box/Mask prompts into Points

Rejected because it misrepresents adapter capability and loses user intent.

## Consequences

### Positive

- richer user intent with explicit visual prompts;
- multiple proposals preserved before selection;
- ambiguity becomes recoverable;
- existing Stable/Evidence lifecycle remains intact;
- future text/concept support does not require a product rewrite;
- Ticket 08 receives a reliable confirmed Anchor.

### Costs

- prompt/proposal domain and adapter compiler;
- ranking policy and frozen-scene benchmark;
- candidate-choice UI;
- additional inference and ranking cost;
- real Box/Mask adapter validation;
- affected Ticket 05/07 regressions must be rerun.

## Non-goals

DG-21 does not:

- change the AI Select tool model;
- change Stable Mask confirmation semantics;
- require semantic labels or Text Prompt;
- implement Adaptive Generated View planning;
- change Generated View automatic Mask publication;
- implement formal P/N/V Evidence;
- create a second 3D editor;
- guarantee every single click is unambiguous.

## Required implementation sequence

```text
04A Prompt Authoring / Proposal Foundation
  ↓
04B Visual Prompt Adapter Enablement
  ↓
07A Reopened Ranking / Ambiguity / Acceptance / Production Validation
  ↓
07B DG-22 Floating Prompt/Edit Palette
  ↓
08 Adaptive Generated View Planner
```

Tickets 04A and 05 provide the existing editor/Undo/Confirm seams. Ticket 04B enables real visual prompts. Ticket 07A integrates Ticket 07 assessment semantics without merging ProposalDecision and ViewAssessment. Ticket 07B preserves the fitted-image rule while removing permanent interaction blind spots.
