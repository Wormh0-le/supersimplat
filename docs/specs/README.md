# AI Select v1.1 — Specification Index

This file is a navigation index, not an additional normative layer.

## Authoritative order

1. [`ai-select-final-spec-v1.1.md`](./ai-select-final-spec-v1.1.md)
2. [`ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`](./ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md)
3. [`ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`](./ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md)
4. [`ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md`](./ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md)
5. [`ai-select-final-spec-v1.1-amendment-004-sparse-key-view-mask-acquisition.md`](./ai-select-final-spec-v1.1-amendment-004-sparse-key-view-mask-acquisition.md)
6. [`ai-select-final-spec-v1.1-amendment-005-route-b-first-acquisition-extension-seam.md`](./ai-select-final-spec-v1.1-amendment-005-route-b-first-acquisition-extension-seam.md)
7. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md)
8. [`../adr/0012-adopt-ai-select-final-spec-v1.md`](../adr/0012-adopt-ai-select-final-spec-v1.md), where not superseded
9. [`../../CONTEXT.md`](../../CONTEXT.md)
10. [`../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`](../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md)
11. [`../decision-gates/DG-22-floating-prompt-edit-palette.md`](../decision-gates/DG-22-floating-prompt-edit-palette.md)
12. [`../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md`](../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md)
13. [`../decision-gates/DG-24-sparse-key-view-mask-acquisition-optional-tracking.md`](../decision-gates/DG-24-sparse-key-view-mask-acquisition-optional-tracking.md)
14. [`../decision-gates/DG-25-route-b-first-extensible-mask-acquisition.md`](../decision-gates/DG-25-route-b-first-extensible-mask-acquisition.md)
15. implementation tickets and tests

The Final Spec and normative amendments govern conflicts. Amendment 004 / DG-24 supersede the mandatory-tracking parts of Amendment 003 / DG-23. Amendment 005 / DG-25 further supersede the requirement to compare A/B/C/D or accept an acquisition-route ADR before implementing route B.

Object-level scope, conservative Anchor acquisition, deferred Gaussian ownership, and final P/N/V remain unchanged.

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
→ non-ownership 2.5D Target Bootstrap
→ adaptive sparse Key Views
→ route-B 3D-guided per-Key-View SAM
→ per-view Review / correction / Participation
→ Included Stable View Annotations
→ Mask-conditioned Gaussian Evidence (P / N / V)
→ Multi-view Evidence Aggregation
→ Gaussian Lifting
→ Candidate + Uncertain
→ Set / Add / Remove / Intersect
→ Native SuperSplat Selection
```

Routes C/D remain future optional experiments behind versioned sequence/reference extension interfaces and a later experiment-backed ADR.

## Current implementation graph

The machine-readable and audited graph is maintained under:

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md) plus [`../../.scratch/ai-select-v1/TRACEABILITY-v2.7.md`](../../.scratch/ai-select-v1/TRACEABILITY-v2.7.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)

The v2.7 retrofit segment is:

```text
04A → 04B → 07A → 07B
                    ↓
08 2.5D sparse Key-View planner
                    ↓
08A route-B per-Key-View SAM + extensible acquisition seam
                    ↓
09 → 11/12 → 14 P/N/V Lift
```

- 04A owns Prompt/proposal infrastructure.
- 04B owns locked real-adapter Box/Mask enablement.
- 07A owns conservative object-level Anchor acquisition; material ambiguity may remain explicit.
- 07B owns no-blind-spot Prompt/Edit palette interaction.
- 08 owns non-ownership 2.5D bootstrap, sparse Key Views, and append-only Generate More segments.
- 08A implements route B directly, retains route A fallback, and defines extension interfaces for future C/D experiments.
- 12 owns explicit per-view Mask refresh and dirty/stale lifecycle; optional repropagation remains capability-gated.
- 14/20 remain the only formal Gaussian ownership stages.

## Scope boundaries

- AI Select v1 targets one object instance; arbitrary part discovery and whole-image inventory are not mandatory.
- Early depth/first-hit support may guide planning and Prompt synthesis but cannot publish Gaussian ownership.
- Bootstrap support seeds but does not hard-bound the Evidence Working Set.
- Sparse Key Views are mandatory; dense tracking sequences and Bridge Views are not.
- Route B is selected and is not blocked by A/B/C/D comparison.
- Route A remains a declared regression baseline/fallback.
- C/D sequence/reference methods are defined as optional capability-gated extensions, not current implementations.
- Mask acquisition backend/score is separate from Lift Participation and P/N/V.
- Confirmed correction is per-view by default and does not automatically become tracker memory.
- Re-Lift remains explicit.
- Complete per-pixel Contributor remains a debug/reference backend only.
