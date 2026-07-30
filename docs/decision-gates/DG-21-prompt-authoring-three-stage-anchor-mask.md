# DG-21 — Prompt Authoring Layer + Three-Stage Anchor Mask Pipeline

- **Status:** CLOSED; Stage-2 closure refined by DG-23 / Amendment 003; multi-view continuation superseded by DG-24 / Amendment 004
- **Date:** 2026-07-28
- **Applies to:** `ai-select-v1`
- **Normative spec:** Final Spec v1.1 + Amendments 002–004
- **Foundation owner:** Ticket 04A
- **Visual-prompt adapter owner:** Ticket 04B
- **Anchor completion owner:** Ticket 07A
- **Interaction follow-up:** Ticket 07B under DG-22
- **Multi-view continuation:** Tickets 08/08A under DG-24

## Decision question

How should AI Select turn user intent on an authoritative Anchor RGB into a Stable Anchor Mask when one Prompt can correspond to several plausible model proposals and direct Pixel Editing must remain distinct from Prompt constraints?

## Decision

Adopt:

```text
Prompt Authoring
→ Stage 1: Prompt-conditioned object proposals
→ Stage 2: conservative 2D-first ProposalDecision
→ Stage 3: Accept / Editing / Confirm
→ object-level Anchor Stable Mask
```

Ownership:

```text
04A = PromptState + Prompt/Edit tools + capabilities + bounded proposal foundation
04B = locked real-adapter Box / Mask Constraint enablement
07A = Anchor proposal integration + conservative decision + Accept/Edit/Confirm
07B = fitted-image floating palette with drag/collapse/Space-hide/no blind region
08  = 2.5D sparse Key-View planning
08A = multi-view Mask acquisition spike + 3D-guided per-Key-View SAM
```

Ticket 07A remains the completion owner for the Anchor Three-Stage pipeline. Amendment 003 supersedes the earlier expectation that materially distinct plausible candidates must be automatically resolved through a benchmark-calibrated Top-1 margin.

DG-24 supersedes DG-23's mandatory tracking continuation. The confirmed Anchor seeds sparse 3D-guided multi-view Mask acquisition; tracking is optional and benchmark-gated.

## Anchor scope

The mandatory Three-Stage pipeline applies to the Anchor Mask and targets one object instance.

Prompt/Edit tooling may be reused for Generated and User-added View correction. Generated View production Mask acquisition is separately defined by Amendment 004 and Ticket 08A.

DG-21 does not require whole-image object inventory, scene-wide semantic discovery, or arbitrary part-level selection.

## Prompt Authoring and Pixel Editing are separate

Prompt constraints:

```text
Positive/Negative Point
Positive/Negative Box when supported
Positive/Negative Mask Constraint when supported
Positive/Negative Text when supported
```

Pixel edits:

```text
Paint
Erase
```

They have separate state, histories, and pointer semantics. Unsupported Prompt types are disabled/rejected and never silently ignored or converted to Points.

## Capabilities are explicit

Prompt support is declared by a versioned adapter capability contract. Positive/negative support is explicit per family.

04A establishes the capability/protocol seam. 04B enables real non-text visual prompts only after locked-runtime validation. Text remains optional.

## Preserve proposals before decision

The Companion preserves a deterministic bounded proposal set. Every proposal binds target/context, View/RGB, PromptState, model, adapter/compiler, proposal/decision policy, attempt, Mask digest, and raw-score semantics.

```text
adapter candidates
→ validation
→ exact dedup
→ near-duplicate clustering
→ representative per cluster
→ bounded materially distinct clusters
```

No Anchor proposal becomes Stable automatically.

## Conservative 2D-first decision

Priority:

1. hard Prompt consistency;
2. object-instance structural credibility;
3. relative candidate geometry/nesting;
4. model score for cluster representative/default preview only;
5. optional low-cost Gaussian support diagnostics.

A unique candidate is not automatically trustworthy. A structural quality gate must detect excessive area, substantial disconnected components, boundary contact, Box spill, constraint disagreement, neighbour leakage, and equivalent-run instability.

Minimum policy:

```text
0 eligible clusters → unavailable
1 credible cluster → selected
1 risky cluster → ambiguous
2+ materially distinct plausible clusters → ambiguous
```

The benchmark validates false-auto-selection, contamination, recovery, stability, and performance. It does not need to establish a general correctness probability or automatic Top-1 margin.

## Ambiguity is first-class

`ambiguous` preserves alternatives and allows candidate choice, Prompt refinement, and Paint/Erase recovery. It must not be converted into technical failure or silent oversized success.

`unavailable` preserves RGB, PromptState, prior Stable Mask, and manual recovery.

## ProposalDecision and ViewAssessment remain distinct

```text
ProposalDecision
= which pre-Stable proposal may seed Editing Mask?

ViewAssessmentPolicy
= is the confirmed Stable Mask suitable for Participation?
```

Ticket 07 continues to own Good / Review / Failed and Participation after Stable publication.

## Stable authority is unchanged

```text
Prompt/proposal changes
→ prior Stable Mask unchanged

Accept/Paint/Erase
→ Editing Mask only

Confirm Mask
→ new Stable Mask revision
→ exact downstream invalidation
```

The confirmed Anchor becomes an object-identity seed for DG-24 bootstrap, sparse Key-View planning, and 3D-guided Prompt synthesis. It is not formal Gaussian ownership.

## Error taxonomy

Keep distinct:

```text
maskProposalFailed
maskProposalUnavailable
maskProposalAmbiguous
maskArtifactInvalid
```

Candidate-level rejection causes remain structured and actionable.

## Rejected alternatives

- Tune point-only thresholds as the full solution.
- Select highest raw model score.
- Always choose smallest/largest Point-containing Mask.
- Make Gaussian support the primary selector.
- Require a semantic detector or whole-image inventory first.
- Treat Paint as Prompt automatically.
- Convert unsupported visual Prompts into Points.
- Require a generic calibrated Top-1 ranker to resolve material ambiguity.

## Consequences

Positive:

- richer explicit user intent;
- proposal alternatives preserved;
- conservative object-level Anchor acquisition;
- ambiguity remains recoverable;
- Stable/Evidence lifecycle preserved;
- DG-24 receives a confirmed identity seed.

Costs:

- Prompt/proposal domain and adapter compiler;
- near-duplicate clustering and structural diagnostics;
- candidate-choice/recovery UI;
- locked-runtime contamination/performance benchmark;
- real Box/Mask adapter validation.

## Required sequence

```text
04A Prompt / Proposal Foundation
→ 04B Visual Prompt Adapter Enablement
→ 07A Object-level Anchor Acquisition
→ 07B Floating Prompt/Edit Palette
→ 08 2.5D Sparse Key-View Planner
→ 08A Multi-view Mask Acquisition
```

## Non-goals

DG-21 does not change Confirm-only Stable semantics, implement camera planning/Mask acquisition, implement P/N/V Evidence, create a second 3D editor, guarantee every Prompt is unambiguous, or require whole-image object inventory.
