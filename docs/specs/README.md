# AI Select v1.1 — Specification Index

This file is a navigation index, not an additional normative layer.

## Authoritative order

1. [`ai-select-final-spec-v1.1.md`](./ai-select-final-spec-v1.1.md)
2. [`ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`](./ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md)
3. [`ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`](./ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md)
4. [`ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md`](./ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md)
5. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md)
6. [`../adr/0012-adopt-ai-select-final-spec-v1.md`](../adr/0012-adopt-ai-select-final-spec-v1.md), where not superseded
7. [`../../CONTEXT.md`](../../CONTEXT.md)
8. [`../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`](../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md)
9. [`../decision-gates/DG-22-floating-prompt-edit-palette.md`](../decision-gates/DG-22-floating-prompt-edit-palette.md)
10. [`../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md`](../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md)
11. implementation tickets and tests

The Final Spec and normative amendments govern conflicts. Amendment 003 / DG-23 refine 07A Stage-2 closure, define object-level 2.5D Key/Bridge sequence planning, introduce Ticket 08A tracking, and preserve final P/N/V ownership.

## Current product chain

```text
Camera View
→ Authoritative gsplat RGB
→ PromptState
→ AutoMaskProposalSet
→ conservative ProposalDecision
    ├── Selected
    ├── Ambiguous
    └── Unavailable
→ Editing Mask
→ Confirm Mask
→ object-level Anchor Stable Mask
→ 2.5D Target Bootstrap
→ ordered Key / Bridge View sequence
→ object-level Mask tracking + correction references
→ Included Stable View Annotations
→ Mask-conditioned Gaussian Evidence (P / N / V)
→ Multi-view Evidence Aggregation
→ Gaussian Lifting
→ Candidate + Uncertain
→ Set / Add / Remove / Intersect
→ Native SuperSplat Selection
```

## Current implementation graph

The machine-readable and audited graph is maintained under:

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)

The v2.5 retrofit segment is:

```text
04A → 04B → 07A → 07B
                    ↓
08 2.5D Key/Bridge planner
                    ↓
08A object-level tracking
                    ↓
09 → 11/12 → 14 P/N/V Lift
```

- 04A owns Prompt/proposal infrastructure.
- 04B owns locked real-adapter Box/Mask enablement.
- 07A owns conservative object-level Anchor acquisition; material ambiguity may remain explicit.
- 07B owns no-blind-spot Prompt/Edit palette interaction.
- 08 owns non-ownership 2.5D bootstrap and ordered Key/Bridge planning.
- 08A owns tracker spike, production object-level tracking, correction memory, and single-frame fallback.
- 12 owns explicit tracker repropagate and dirty/stale lifecycle.
- 14/20 remain the only formal Gaussian ownership stages.

## Scope boundaries

- AI Select v1 targets one object instance; arbitrary part discovery and whole-image inventory are not mandatory.
- Early depth/first-hit support may guide planning but cannot publish Gaussian ownership.
- Tracking membership is separate from Lift Participation.
- Bridge Views default Excluded.
- Tracker confidence is not P/N/V Evidence.
- Only confirmed Stable Masks can become correction references or Lift inputs.
- Repropagate and Re-Lift remain explicit and separate.
- Complete per-pixel Contributor remains a debug/reference backend only.