# DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline

- **Status:** CLOSED
- **Date:** 2026-07-28
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendment 002
- **Implementation owners:** Tickets 04A and 07A
- **Completion owner:** Ticket 07A

## Decision question

How should AI Select turn user intent on an authoritative Anchor RGB into a Stable Anchor Mask when one point can correspond to several plausible SAM proposals, the current point-only path may return an oversized Mask or overloaded `anchorMaskUnavailable`, and direct pixel editing conflicts with Box-drag interaction?

## Context

The existing implementation correctly separates:

```text
RGB
Editing Mask
Stable Mask
Evidence
Candidate
```

It provides positive/negative point prompts, direct Brush Add/Erase, atomic Stable Mask confirmation, and Anchor support validation.

The remaining weakness is the pre-Stable decision path:

```text
click
→ point-only SAM request
→ choose highest-scored point-consistent candidate
→ Editing Mask
```

Observed problems:

- a point on a table top may include neighbouring chairs;
- nested part/object/group proposals are collapsed before the user can inspect them;
- raw model score is the main ordering signal;
- several distinct causes are reported as `anchorMaskUnavailable`;
- drag is already bound to pixel Brush, leaving no unambiguous Box gesture;
- Prompt constraints and direct bitmap corrections share one interaction mode.

Ticket 07 ViewAssessmentPolicy starts after Stable Mask publication and cannot choose the pre-Stable proposal.

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

Ownership:

```text
Ticket 04A
= PromptState + explicit Prompt/Edit tools
  + adapter capability contract + bounded proposal set

Ticket 07A
= 2D-first ranking + ambiguity UX
  + acceptance/editing integration
  + locked-runtime quality validation
```

Ticket 07A is the completion owner.

## Decision 1 — Anchor scope and reusable tooling

The mandatory Three-Stage pipeline applies to the Anchor Mask.

PromptState and the Prompt/Edit toolbar should be reusable for Generated and User-added View correction, but DG-21 does not silently replace the current Generated View automatic Stable Mask + ViewAssessment publication contract.

## Decision 2 — Prompt Authoring and Pixel Editing are separate

Prompt Authoring expresses model constraints:

```text
Positive/Negative Point
Positive/Negative Box when supported
Positive/Negative Mask Constraint
Positive/Negative Text when supported
```

Pixel Editing directly changes Editing Mask:

```text
Paint
Erase
```

The two modes have separate state and histories. Pointer behavior is explicit: Box drag only in Box mode, prompt stroke only in Prompt Brush mode, pixel edit only in Paint/Erase mode.

## Decision 3 — Capabilities are explicit

Prompt support is declared by a versioned adapter capability contract, not inferred from model name.

Positive and negative support is explicit per prompt family. Unsupported tools are disabled/rejected and never silently ignored.

The current point-only adapter remains a valid compatibility backend. A one-candidate result is a legal proposal set, but it cannot by itself satisfy Ticket 07A's production multi-candidate quality gate unless a separate versioned proposal generator supplies meaningful alternatives.

## Decision 4 — Preserve proposals before selection

The Companion preserves a deterministic bounded proposal set. Every proposal binds:

```text
Target/context dependency
View and RGB digest
PromptState digest
model manifest
adapter capability identity
proposal policy
attempt identity
Mask artifact digest
raw model score and declared semantics
```

No proposal becomes Stable automatically on the Anchor path.

## Decision 5 — Ranking is 2D-first

Stage 2 prioritizes:

1. hard prompt consistency;
2. relative candidate geometry and nesting;
3. 2D structural quality;
4. model-declared score;
5. optional low-cost Gaussian support sanity.

Low-cost Gaussian support may detect gross incompatibility or break a tie between otherwise comparable 2D candidates. It cannot be the primary selector, formal ownership Evidence, or a replacement for P/N/V.

This preserves the Anchor problem as interactive 2D segmentation while allowing bounded scene-aware sanity checks.

## Decision 6 — Ambiguity is a first-class state

When materially different candidates remain plausible without a calibrated stable margin:

```text
ProposalDecision = ambiguous
```

The system preserves alternatives and allows:

- candidate choice;
- Point/Box/mask/Text refinement where supported;
- manual Paint/Erase recovery.

It must not silently choose an oversized Mask or report ambiguity as a technical failure.

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

Legacy transport codes may be mapped during migration, but browser/domain state preserves the distinction.

## Decision 10 — Text is capability-gated

Text/concept prompting is planned, not mandatory in Phase A. It becomes usable only when a locked versioned adapter advertises support and passes runtime validation.

No external detector or semantic object database is required.

## Decision 11 — Ticket 08 follows 07A

Adaptive Generated View planning should consume a confirmed Anchor from the completed Three-Stage pipeline. Ticket 08 therefore depends on Ticket 07A.

This does not make ranking part of the planner; it prevents planner quality evaluation from being dominated by the known point-only Anchor weakness.

## Rejected alternatives

### Tune point-only thresholds

Rejected because threshold tuning cannot resolve nested part/object/group ambiguity and may increase unavailable results.

### Select the highest raw model score

Rejected because the score is adapter-local and not established as calibrated user-intent correctness.

### Always select smallest or largest point-containing Mask

Rejected because either bias fails for part-versus-whole intent and neighbouring-object leakage.

### Make Gaussian support the primary selector

Rejected because the current support probe is a computability diagnostic, not same-decision ownership Evidence.

### Require a semantic detector first

Rejected for v1 because arbitrary parts and unknown objects do not require category semantics. Text/concept adapters remain optional.

### Treat Paint strokes as prompts automatically

Rejected because it destroys the distinction between model constraints and explicit pixel correction.

## Consequences

### Positive

- richer intent with fewer accidental masks;
- Box and negative prompts become first-class;
- multiple proposals are not discarded prematurely;
- ambiguity is recoverable;
- existing Stable/Evidence lifecycle remains intact;
- future text/concept support does not require a product rewrite;
- Ticket 08 receives a more reliable Anchor.

### Costs

- new prompt/proposal domain state;
- generic adapter protocol;
- ranking policy and real-scene benchmark;
- candidate-choice UI;
- additional inference latency/VRAM;
- affected Ticket 05/07 regressions must be rerun.

### Risks and controls

- ranking overfit → frozen benchmark + versioned policy;
- too many alternatives → bounded material-distinct set;
- support-probe misuse → 2D-first/no-ownership constraints;
- capability drift → capability digest + runtime identity;
- stale UI → exact Prompt/RGB/attempt binding;
- confusing interaction → explicit Prompt/Edit tools.

## Non-goals

DG-21 does not:

- change the AI Select tool model;
- change Stable Mask confirmation semantics;
- require semantic labels;
- implement Adaptive Generated View planning;
- change Generated View automatic Mask publication;
- implement formal P/N/V Evidence;
- make Candidate provenance UI normative;
- create a second 3D editor;
- guarantee every single click is unambiguous.

## Required implementation sequence

Because Tickets 05–07 already exist, the retrofit sequence is:

```text
04A Prompt Authoring / Proposal Foundation
  ↓
07A Ranking / Ambiguity / Acceptance / Production Validation
  ↓
08 Adaptive View Planner
```

Ticket 04A consumes existing Ticket 05 editor/Undo/Confirm seams; Ticket 07A integrates existing Ticket 07 assessment semantics.