# AI Select Domain and Sources of Truth

Read this file for AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Current baseline

The implementation target is **AI Select Final Spec v1.3**. It uses the official SAM 3 Image instance-interaction path for static Anchor and Key-View segmentation. Target geometry is compact Prompt/framing context without Gaussian ownership; Included Stable Masks drive P/N/V Gaussian Evidence and lifting.

Final Spec v1.1, its Amendments, Final Spec v1.2, ADR 0014, and DG-24 through DG-26 are historical where they conflict with Final Spec v1.3, ADR 0016, or ADR 0017. Old implementation, fixtures, issues, and tests do not restore superseded behavior.

## Sources of truth

Before changing non-trivial AI Select behavior, inspect these sources in order:

1. `docs/specs/ai-select-final-spec-v1.3.md`
2. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
3. `docs/adr/0016-adopt-sam3-image-instance-workflow-and-minimal-multiview.md`
4. `docs/adr/0017-separate-geometry-quality-from-route-b-prompt-support.md` when TargetGeometryHint or Prompt Support is involved
5. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md` and `docs/adr/0015-automate-readiness-and-keep-model-resolution-operator-owned.md` where not superseded
6. `CONTEXT.md`
7. The associated implementation ticket under `docs/ai-select/tickets/` and its audit or traceability artifacts under `docs/ai-select/`
8. The nearest implementation and tests
9. Dependency and runtime declarations when installation, rendering, inference, CUDA, or calibration is affected

For domain work outside non-trivial AI Select behavior, read `CONTEXT.md` and the ADRs that touch the area being changed. Use the terms defined in `CONTEXT.md`; surface conflicts with an ADR explicitly.

Final Spec v1.3 is authoritative for current product, interaction, lifecycle, acquisition, geometry, lifting semantics, and engineering boundaries. Frozen benchmark fixtures, manifests, and records are authoritative only for the benchmark data they describe.

## Product model

```text
Camera View
    ↓
Authoritative gsplat RGB
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Mask-Conditioned Gaussian Evidence (P / N / V)
    ↓
Multi-view Evidence Aggregation
    ↓
Gaussian Lifting
    ↓
AI Candidate + Uncertain
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

The following boundaries define the product:

- AI Select is a SuperSplat Selection Tool, not a separate semantic-object workspace.
- AI Candidate is derived state, not a second editable 3D model.
- Structural corrections use Views, Stable Masks, Participation, and explicit Re-Lift.
- Small final corrections use native SuperSplat selection tools after Candidate application.
- Cross-target persistent truth is Native Selection and Native EditHistory, not an AI target-session stack.
- RGB Ready, Mask Ready, Evidence Ready, and Candidate Ready are distinct states.
- Complete per-pixel Contributor is a debug/reference capability, not the production lifting contract.

## Deferred product scope

DG-14 remains deferred. Do not add the following without a later specification decision:

- user-facing Candidate provenance or source inspection;
- Gaussian-level Evidence inspection;
- persistent Candidate history;
- reopening or restoring previous target AI contexts.

Minimal internal revision and fingerprint metadata required for correctness remains required.

## Legacy vocabulary

Treat these as migration or reference concepts rather than current product architecture:

- ObjectSelectionSession as the user-visible lifecycle;
- Prompt Log as product source of truth;
- Mask Track or Mask Set as the top-level Mask model;
- New, Add, Remove, or Refine as AI inference modes;
- Frame Set or ordered video-tracker orchestration;
- PlayCanvas-captured Anchor RGB;
- complete Contributor on the normal RGB, Anchor, or lifting critical path;
- one-shot Preview → Confirm → Close;
- fixed Correction Round UX;
- whole-scene raw-count coverage.

Use `legacy`, `reference`, or `debug` when a historical term could be mistaken for current behavior. `Add` and `Remove` are reserved for native Candidate application operations.
