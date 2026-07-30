# ADR 0014 — Adopt Route-B-First Multi-View Mask Acquisition Architecture

- Status: Accepted
- Date: 2026-07-30
- Branch: ai-select-v1

## Context

AI Select originally explored object-level tracking as the primary mechanism for multi-view mask acquisition. After review, the production objective was refined: the system needs reliable object-level masks for Gaussian lifting, not necessarily continuous identity tracking.

The v1 implementation path therefore adopts sparse adaptive Key Views with 3D-guided per-view SAM acquisition as the default route.

## Decision

The default acquisition pipeline is:

```
Anchor Stable Mask
→ 2.5D object bootstrap
→ VisibleTargetSupportArtifact
→ Sparse Key Views
→ KeyViewPromptSynthesizer
→ per-Key-View SAM acquisition
→ Proposal Decision
→ View Assessment
→ Stable Mask publication
→ P/N/V Gaussian lifting
```

Tracker-based sequence propagation is not a mandatory dependency. Future sequence tracker or hybrid routes must integrate through extension interfaces without changing the default Route-B contracts.

## Contract boundaries

- VisibleTargetSupportArtifact provides reusable 3D support evidence for prompt synthesis.
- KeyViewPromptSynthesizer produces explicit PromptArtifacts.
- Acquisition backends produce proposal sets, not final Stable Masks.
- Decision, assessment and publication remain independent layers.
- Future sequence/reference capabilities are exposed through backend extensions.

## Consequences

Positive:

- Sparse-view optimization remains aligned with Gaussian lifting goals.
- Prompt generation, model inference and publication can be independently evaluated.
- Future tracker integration does not require replacing the acquisition architecture.

Negative:

- More artifact boundaries and contracts are introduced.
- Current single-frame mask flow requires refactoring.
