# AI Select Specification Index

## Current normative specification

1. [`ai-select-final-spec-v1.2.md`](./ai-select-final-spec-v1.2.md)
2. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md), where not superseded by Final Spec v1.2
3. [`../../CONTEXT.md`](../../CONTEXT.md), where not superseded
4. implementation tickets and tests

`ai-select-final-spec-v1.2.md` is the only current product and engineering specification. Implementation agents, acceptance reviews, and traceability MUST use it directly.

## Current decision rationale

- [`../adr/0014-adopt-route-b-first-multiview-mask-acquisition.md`](../adr/0014-adopt-route-b-first-multiview-mask-acquisition.md) — accepted Route-B-first architecture rationale, subordinate to Final Spec v1.2
- [`../decision-gates/DG-20-mask-conditioned-direct-gaussian-evidence.md`](../decision-gates/DG-20-mask-conditioned-direct-gaussian-evidence.md)
- [`../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md`](../decision-gates/DG-21-prompt-authoring-three-stage-anchor-mask.md)
- [`../decision-gates/DG-22-floating-prompt-edit-palette.md`](../decision-gates/DG-22-floating-prompt-edit-palette.md)
- [`../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md`](../decision-gates/DG-23-object-level-tracking-deferred-gaussian-ownership.md)
- [`../decision-gates/DG-24-sparse-key-view-mask-acquisition-optional-tracking.md`](../decision-gates/DG-24-sparse-key-view-mask-acquisition-optional-tracking.md)
- [`../decision-gates/DG-25-route-b-first-extensible-mask-acquisition.md`](../decision-gates/DG-25-route-b-first-extensible-mask-acquisition.md)
- [`../decision-gates/DG-26-consolidated-v1.2-route-b-acquisition-architecture.md`](../decision-gates/DG-26-consolidated-v1.2-route-b-acquisition-architecture.md)

ADR 0014 and the DGs explain why decisions were made. They are subordinate rationale, not alternative current product specifications.

## Historical specifications

The following files are retained for decision history only and have no current normative force:

- [`ai-select-final-spec-v1.1.md`](./ai-select-final-spec-v1.1.md)
- [`ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md`](./ai-select-final-spec-v1.1-amendment-001-renderer-evidence-identity.md)
- [`ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md`](./ai-select-final-spec-v1.1-amendment-002-anchor-mask-pipeline.md)
- [`ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md`](./ai-select-final-spec-v1.1-amendment-003-object-level-tracking-mask-acquisition.md)
- [`ai-select-final-spec-v1.1-amendment-004-sparse-key-view-mask-acquisition.md`](./ai-select-final-spec-v1.1-amendment-004-sparse-key-view-mask-acquisition.md)
- [`ai-select-final-spec-v1.1-amendment-005-route-b-first-acquisition-extension-seam.md`](./ai-select-final-spec-v1.1-amendment-005-route-b-first-acquisition-extension-seam.md)

Do not merge the historical amendment chain when implementing current work. Final Spec v1.2 already consolidates its retained requirements and current replacements.

## Current product chain

```text
Camera View
→ authoritative gsplat RGB
→ PromptState
→ conservative object-level Anchor Stable Mask
→ VisibleTargetSupportArtifact
→ TargetBootstrapArtifact
→ adaptive sparse Key Views
→ KeyViewPromptSynthesizer
→ route-B per-view SAM ProposalSet
→ KeyViewMaskDecisionPolicy
→ ViewAssessmentPolicy
→ MaskPublicationCoordinator
→ Included Stable View Annotations
→ P/N/V Gaussian Evidence
→ Gaussian Candidate + Uncertain
→ Native Set / Add / Remove / Intersect
```

Route A remains a technical fallback and regression baseline. Routes C/D remain future optional experiments behind the backend bundle/registry and sequence extension contracts plus a later experiment-backed ADR.

## Current implementation graph

The machine-readable and audited graph is maintained under:

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)
- [`../../.scratch/ai-select-v1/WALKTHROUGHS.md`](../../.scratch/ai-select-v1/WALKTHROUGHS.md)

The current acquisition segment is:

```text
07A
├── 07B Floating Palette UX
└── 08 Visible Support + Bootstrap + Sparse Planner
    → 08A Contracts + Backend Registry
    → 08B Route-B Production Acquisition
    → 09 Gallery / Inspection
    → 11 / 12
    → 14 P/N/V Lift
```

## Scope boundaries

- AI Select v1 targets one object instance.
- Early support geometry is localization/planning/Prompt context, never ownership.
- Sparse Key Views are mandatory; dense tracking sequences and Bridge Views are not.
- Prompt synthesis, inference, proposal decision, assessment, publication, Participation, and P/N/V are separate layers.
- Route B is selected and is not blocked by route comparison.
- Route-A fallback is automatic only for technical/capability failures and remains fully provenance-bound.
- C/D sequence/reference methods are optional future extensions, not current implementations.
- Confirmed correction is per-view by default.
- Re-Lift remains explicit.
- Complete Contributor remains reference/debug only.
