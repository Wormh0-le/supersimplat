# AI Select v1.1 — Specification Index

This file is a navigation index, not an additional normative layer.

## Authoritative order

1. [`ai-select-final-spec-v1.1.md`](./ai-select-final-spec-v1.1.md)
2. [`ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`](./ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md)
3. [`ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`](./ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md)
4. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md)
5. [`../adr/0012-adopt-ai-select-final-spec-v1.md`](../adr/0012-adopt-ai-select-final-spec-v1.md), where not superseded
6. [`../../CONTEXT.md`](../../CONTEXT.md)
7. [`../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`](../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md)
8. [`../decision-gates/DG-22-floating-prompt-edit-palette.md`](../decision-gates/DG-22-floating-prompt-edit-palette.md)
9. implementation tickets and tests

The Final Spec and normative amendments govern conflicts. DG-21 records Three-Stage Anchor rationale and ownership. DG-22 refines fitted-image palette interaction without changing Prompt/Mask/Evidence lifecycle semantics.

## Current product chain

```text
Camera View
→ Authoritative gsplat RGB
→ PromptState
→ AutoMaskProposalSet
→ ProposalDecision
    ├── Selected
    ├── Ambiguous
    └── Unavailable
→ Editing Mask
→ Confirm Mask
→ Stable Mask
→ Included Stable View Annotations
→ Mask-Conditioned Gaussian Evidence (P / N / V)
→ Multi-view Evidence Aggregation
→ Gaussian Lifting
→ Candidate + Uncertain
→ Set / Add / Remove / Intersect
→ Native SuperSplat Selection
```

## Current implementation graph

The machine-readable and audited implementation graph is maintained under:

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)

The v2.4 retrofit segment is:

```text
03 + 04 → 05 → 06 → 07
          │         │
          └→ 04A → 04B
                     └────┐
                          ▼
                         07A reopened
                          │
                          ▼
                         07B floating palette
                          │
                          ▼
                          08
```

- Ticket 04A owns Prompt Authoring and bounded proposal infrastructure.
- Ticket 04B owns locked real-adapter Box and Mask Constraint enablement; Text remains optional.
- Reopened Ticket 07A is the algorithmic completion gate for the Three-Stage Anchor Mask Pipeline.
- Ticket 07B owns DG-22 draggable/collapsible/auto-avoiding palette interaction.
- Ticket 08 owns valid-pose Adaptive Generated View planning.

## Scope boundaries

- The mandatory Three-Stage proposal pipeline applies to the Anchor Mask.
- Prompt/Edit tooling may be reused for correction on other AI Views.
- Generated View automatic Stable Mask + ViewAssessment publication is not silently replaced by Amendment 002.
- Low-cost Gaussian support may assist proposal sanity checks but is not P/N/V ownership Evidence.
- Palette interaction is editor-local and does not change PromptState, Stable Mask, Evidence, or Candidate identity.
- Complete per-pixel Contributor remains a debug/reference backend only.
