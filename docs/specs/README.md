# AI Select Specification Index

## Current normative specification

1. [`ai-select-final-spec-v1.3.md`](./ai-select-final-spec-v1.3.md)
2. [`../adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md`](../adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md)
3. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md), where not superseded
4. [`../adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md`](../adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md), where not superseded
5. [`../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`](../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md)
6. implementation tickets and tests

`ai-select-final-spec-v1.3.md` is the only current product and engineering specification.

## Current product decisions

- Static Anchor and Key-View segmentation use the official SAM 3 Image instance path.
- SAM 3.1 Multiplex is not a current static-image production dependency.
- v1 Prompt tools are Positive Point, Negative Point, and one Positive Instance Box.
- Negative Box, Prompt Brush, Mask Constraints, and Text Prompt are removed from v1.
- Previous-prediction logits are internal refinement state, not a Prompt or binary Brush Mask.
- One positive point may return up to three candidates; Box, multiple Points, or refinement return one.
- Paint/Erase remain Editing Mask operations.
- Anchor-visible geometry is one compact `TargetGeometryHintArtifact`.
- v1 uses 2–4 bounded local Key Views, not a general adaptive/free-space planner.
- Generated Views use projected Box/Points and SAM 3 Image single-mask inference.
- Mask Review is separate from Lift Readiness.
- No current generic backend registry, Route B/C/D bundle, sequence extension, or automatic Route-A fallback is required.

## Current product chain

```text
Camera View
→ authoritative gsplat RGB
→ Positive/Negative Points + optional Positive Instance Box
→ SAM 3 Image instance prediction
→ candidate choice where needed
→ Accept / Edit / Confirm
→ Anchor Stable Mask
→ TargetGeometryHintArtifact
→ bounded local Key Views
→ projected Box + Points
→ per-View SAM 3 Image single-mask prediction
→ Mask Review / Stable Mask / Participation
→ Included Stable Masks
→ P/N/V Gaussian Evidence
→ Candidate + Uncertain
→ Native Set / Add / Remove / Intersect
```

## Current implementation graph

```text
04B historical Multiplex/visual adapter baseline
→ 04C SAM 3 Image Adapter + Prompt Contract Migration
   ├→ 02C Automatic Runtime Readiness
   └→ 07A Simplified Anchor Acquisition
       ├→ 07B Point/Box + Paint/Erase Palette
       └→ 08 TargetGeometryHint + Local Key Views
           → 08A Compact Image Instance Mask Contracts
           → 08B 3D-guided per-View SAM 3 Image Acquisition
           → 09 Gallery
           → 11 / 12
           → 14 / 13 Lift and Readiness
```

## Historical specifications and rationale

The following are retained for history only:

- Final Spec v1.1 and Amendments 001–005;
- Final Spec v1.2;
- ADR 0014;
- DG-20 through DG-26 where superseded by ADR 0016 / Final Spec v1.3.

They must not be reconstructed as current requirements. The former v1.2 text remains available in repository history.

## Planning artifacts

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`](../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)
- [`../../.scratch/ai-select-v1/WALKTHROUGHS.md`](../../.scratch/ai-select-v1/WALKTHROUGHS.md)
