# AI Select Specification Index

## Current normative specification

1. [`ai-select-final-spec-v1.3.md`](./ai-select-final-spec-v1.3.md)
2. [`../adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md`](../adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md)
3. [`../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`](../adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md), where not superseded
4. [`../adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md`](../adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md), where not superseded
5. [`../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`](../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md)
6. current Ticket acceptance criteria and tests

`ai-select-final-spec-v1.3.md` is the only current product and engineering specification. Ticket Graph v2.12 closes the RGB-input, opaque previous-logits state, current-frontier and optional cross-view diagnostic boundaries without adding a new product feature.

## Current product decisions

- Static Anchor and Key-View segmentation use official SAM 3 Image instance interactivity.
- SAM 3.1 Multiplex is not a current static-image production dependency.
- v1 Prompt tools are Positive Point, Negative Point and one Positive Instance Box.
- Negative Box, Prompt Brush, Mask Constraints and Text Prompt are removed.
- Paint/Erase remain Editing Mask operations.
- A SAM provider request contains resolvable authoritative RGB, not only a digest.
- Actual previous-prediction logits remain Companion-local; the browser receives only an opaque same-Instance reference.
- One Positive Point may return up to three candidates; Box, multiple Points or refinement return one.
- Anchor ambiguity is resolved directly by user choice/refinement before Accept.
- Anchor-visible geometry is one compact `TargetGeometryHintArtifact`.
- v1 uses 2–4 bounded local Key Views, not a general adaptive/free-space planner.
- Generated Views use projected Box/Points and SAM 3 Image single-mask inference.
- Mask Review is separate from Lift Readiness.
- Ticket 13 is the sole visibility/readiness authority; Ticket 10 cross-view conflict diagnostics are optional and do not block release.
- No current generic backend registry, Route B/C/D bundle, sequence extension or automatic Route-A fallback is required.

## Current product chain

```text
Camera View
→ authoritative gsplat RGB
→ Positive/Negative Points + optional Positive Instance Box
→ SAM 3 Image instance prediction
→ candidate choice/refinement where needed
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
04B historical Multiplex baseline
→ 04C SAM 3 Image + Prompt/RGB/refinement migration ──→ 02C readiness

06 implemented progressive RGB tracer
→ 07 MaskReview correction

04C + 07
→ 07A simplified Anchor acquisition
   ├→ 07B Point/Box + Paint/Erase palette
   └→ 08 TargetGeometryHint + local Key Views
       → 08A compact image instance contracts
       → 08B per-View SAM 3 Image acquisition
       → 09 Gallery
       → 11 / 12
       → 14 / 13 Lift and Readiness
```

Current ready frontier:

```text
04C — critical model migration gate
07  — parallel MaskReview policy correction
```

Ticket 10 is an optional post-Evidence enhancement and is not a Ticket 21 core release blocker.

## Historical specifications and rationale

The following are retained for history only:

- Final Spec v1.1 and Amendments 001–005;
- Final Spec v1.2;
- ADR 0014;
- DG-20 through DG-26 where superseded by ADR 0016 / Final Spec v1.3;
- Ticket 04A generic Prompt surface;
- Ticket 06 projected-support/Multiplex Mask and production-fallback handoff.

They must not be reconstructed as current requirements.

## Planning artifacts

- [`../../.scratch/ai-select-v1/README.md`](../../.scratch/ai-select-v1/README.md)
- [`../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md`](../../.scratch/ai-select-v1/CURRENT-TICKET-SPEC-MAPPING.md)
- [`../../.scratch/ai-select-v1/manifest.json`](../../.scratch/ai-select-v1/manifest.json)
- [`../../.scratch/ai-select-v1/TRACEABILITY.md`](../../.scratch/ai-select-v1/TRACEABILITY.md)
- [`../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md`](../../.scratch/ai-select-v1/FOUR-PASS-AUDIT.md)
- [`../../.scratch/ai-select-v1/WALKTHROUGHS.md`](../../.scratch/ai-select-v1/WALKTHROUGHS.md)
