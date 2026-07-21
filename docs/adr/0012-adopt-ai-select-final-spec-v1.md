# ADR 0012: Adopt AI Select Final Spec v1.0 and Supersede the Legacy Object Selection Session Model

- **Status:** Accepted
- **Date:** 2026-07-21
- **Applies to:** `ai-select-v1`
- **Implementation baseline:** `42f6013438f1271fcd35a4bfdc9ba5a3eb719c06`
- **Normative product spec:** `docs/specs/ai-select-final-spec-v1.0.md`

## Context

The repository's PoC evolved around a user-visible `ObjectSelectionSession` model:

```text
Prompt
→ Prompt Log
→ New / Add / Remove / Refine
→ Frame Set / Mask Tracks
→ Evidence Snapshot
→ Candidate preview
→ Confirm / Selection Commit
→ close session
```

That architecture produced valuable technical foundations: Stable Gaussian IDs, immutable Scene Snapshots, a locked gsplat renderer, same-rasterization contributor attribution, SAM integration, Generated View planning/preflight, Selection Evidence, native `SelectOp`/`EditHistory` integration, and reproducible benchmark fixtures.

However, product walkthroughs and failure-flow review exposed structural problems in the old interaction/domain model:

- AI observation RGB and editor rendering could diverge, especially for the Anchor;
- View and Mask lifecycles were coupled through a complete Frame Set / Mask Set publication model;
- Prompt Log and Mask Tracks owned too much product state;
- `New/Add/Remove/Refine` mixed inference correction semantics with selection-set semantics;
- one-shot `Confirm → Selection Commit → close` prevented iterative multi-view review/correction after Candidate creation;
- the old session model did not cleanly express user-added Views, independent stable/editing Mask versions, Participation, explicit Repropagate/Re-Lift, Candidate stale state, target restart, or scene-mutation suspension/Undo recovery;
- fixed or batch-oriented View semantics conflicted with adaptive progressive planning and scalable Gallery workflows.

The approved Final Spec v1.0 defines a different product model:

```text
Camera View
    ↓
gsplat RGB / Contributor
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Gaussian Lifting
    ↓
AI Candidate
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

## Decision

Adopt `docs/specs/ai-select-final-spec-v1.0.md` as the normative current-version product, interaction, lifecycle, and engineering baseline.

Where the Final Spec conflicts with historical PoC implementation, tests, glossary entries, issues, or ADR assumptions, the Final Spec and this ADR govern new `ai-select-v1` work unless a later approved ADR/spec revision explicitly supersedes them.

### 1. Replace the user-visible session model with one Current Target Context

At most one user-visible `CurrentTargetContext` exists at a time.

It owns target-local:

- Anchor;
- Generated Views;
- User-added Views;
- Mask versions;
- Participation;
- Coverage / Lift Readiness;
- Candidate;
- Uncertain.

`Restart Current Target` disposes that target-local context while retaining Native Selection, Native EditHistory, AI Select activation, tool/policy settings, and reusable runtime caches.

v1.0 does not implement a persistent previous-target AI session stack.

### 2. Make gsplat authoritative for all AI observation rendering

All AI RGB, including Anchor Preview/Final, Generated Views, and User-added Views, comes from the locked gsplat observation renderer.

PlayCanvas/SuperSplat remains the interactive editor renderer.

A versioned `CameraBinding` is the shared source of truth for both gsplat rasterization and the corresponding 3D Frustum.

PlayCanvas canvas capture is not a valid authoritative AI Anchor path in the Final Spec implementation.

### 3. Replace Frame Set / Mask Set as the top-level product model

AI Views are independent records. A View may be render-ready while having no Mask.

Masks are independent, versioned `MaskAnnotation` objects with explicit:

- `stableMaskId`;
- `editingMaskId`;
- atomic Confirm Mask publication.

Automatic SAM/propagation may still use internal batching/tracking structures, but Prompt Log / Mask Track / Mask Set are no longer the product-level source of truth.

### 4. Separate Mask Quality from Participation

Automatic assessment produces Good / Review / Failed plus evidence-backed Review Reasons.

Participation is independently Included / Excluded.

Default policy:

- Auto Good → Included;
- Auto Review → Excluded;
- User Confirmed → Included;
- Failed / no stable mask → Excluded.

Do not expose an uncalibrated unified `Confidence XX%` as if it were a correctness probability.

### 5. Make Candidate a derived, non-directly-edited result

The AI Candidate is derived from Included Stable View Annotations through Gaussian Lifting.

AI Select v1.0 does not add a second 3D Candidate-painting system. Structural errors are corrected by changing View/Mask/Participation inputs and explicitly Re-Lifting. Small final corrections are performed after applying the Candidate using native SuperSplat selection tools.

### 6. Replace inference-mode Add/Remove with native Candidate operations

`New / Add / Remove / Refine` are superseded as current product inference modes.

Candidate application uses the four native selection semantics:

```text
Set       S' = C
Add       S' = S ∪ C
Remove    S' = S − C
Intersect S' = S ∩ C
```

These operations must continue through existing native `SelectOp` / `EditHistory` behavior.

Applying a Candidate does not close AI Select or destroy the Current Target Context.

### 7. Add explicit stale and suspended lifecycle semantics

Stable upstream AI input changes make Candidate stale and require explicit Re-Lift before Candidate application.

Scene/render/geometry/identity dependency changes suspend the Current Target Context rather than immediately destroying it.

A semantic `TargetDependencyToken` must allow exact Undo recovery when the target dependency returns to the prior compatible state.

### 8. Bind async work to target context and dependency identity

Async AI requests/results must bind at least:

```text
targetContextId
contextRevision
dependencyToken
```

Mismatched late results are discarded. Correctness must not depend on cancellation successfully stopping already-running CPU/GPU work.

### 9. Use adaptive, progressive View planning

Generated Views are planner-owned and may publish progressively.

Planning is driven by target observation, View Diversity, and marginal gain under bounded resource budgets—not a fixed user-facing view count or whole-scene Gaussian denominator.

The user may Stop Generation, Generate More Views incrementally, or Add a View manually.

### 10. Defer Candidate provenance UI

DG-14 remains deferred from v1.0:

- Candidate provenance/source-inspection UI;
- Gaussian-level evidence inspector;
- Candidate history browser;
- reopen previous target AI contexts.

Internal revision/fingerprint metadata required for correctness and stale detection remains required.

## Retained Technical Foundations

This ADR does **not** authorize a full rewrite of the repository.

The following foundations should be preserved and evolved where compatible:

- editor-owned Stable Gaussian ID mapping;
- immutable Scene Snapshot serialization and validation;
- locked gsplat backend and authoritative same-rasterization RGB/alpha/contributor path;
- contributor mass-conservation/fail-closed validation;
- SAM runtime/model adapter and locked dependency model;
- Generated View camera generation, preflight, and validated geometric primitives that remain policy-compatible;
- Selection Evidence / Evidence Policy mathematics where compatible with Included Stable View inputs;
- native `SelectOp` / `EditHistory` integration;
- Companion readiness/transport/runtime ownership boundaries;
- reproducible benchmark fixtures, Ground Truth, runtime locks, and scoring infrastructure.

Reuse algorithms and trust-boundary proofs; replace obsolete product orchestration.

## Superseded Product/Domain Concepts

The following are no longer normative product architecture for new v1.0 work:

- `ObjectSelectionSession` as the user-visible lifecycle container;
- Prompt Log as the authoritative product-state model;
- Mask Track as the top-level user mask model;
- complete Frame Set / Mask Set as the required progressive-publication unit;
- `New / Add / Remove / Refine` as AI interaction modes;
- fixed Correction Round UX/budget as the product correction model;
- PlayCanvas-captured Anchor RGB as AI observation truth;
- one-shot `Preview → Confirm → Selection Commit → close session`;
- whole-scene raw Gaussian count as the observation-coverage denominator.

These concepts may remain temporarily in legacy implementation, compatibility code, historical fixtures, and benchmark records during migration. Their existence does not grant them authority over Final Spec v1.0 behavior.

## Migration Strategy

Use incremental tracer-bullet migration rather than a big-bang rewrite.

Recommended order:

1. adopt Final Spec / repository contract / vocabulary;
2. introduce the Current Target Context domain kernel, TargetDependencyToken, and AIRequestBinding;
3. introduce CameraBinding and an end-to-end authoritative gsplat Anchor tracer bullet;
4. retire the PlayCanvas canvas Anchor inference path;
5. introduce AI View registry and independent versioned MaskAnnotation lifecycle;
6. add Anchor Validation;
7. adapt Generated View planning to progressive adaptive target-observation/diversity semantics;
8. evolve existing quality diagnostics into ViewAssessmentPolicy + Review Reasons;
9. implement Participation, Observation Coverage, View Diversity, and Lift Readiness;
10. adapt Evidence/Lifting to Included Stable View Annotations;
11. expose Candidate + Uncertain and native Set/Add/Remove/Intersect;
12. complete correction, restart, scalable Gallery, suspension, and exact Undo recovery flows.

Legacy tests that assert explicitly superseded behavior should be replaced with tests for the new invariant, while unrelated lower-level tests and proofs should remain intact.

## Branch Decision

The `ai-select-v1` implementation branch is intentionally forked from:

```text
42f6013438f1271fcd35a4bfdc9ba5a3eb719c06
```

This baseline retains useful preceding PoC/benchmark/planner corrections while avoiding later commits that substantially deepen the superseded `New/Add/Remove/Refine → Confirm/Commit` and prompt-staging product model.

The later `kimi` branch remains useful as a reference/source for validated algorithms, tests, benchmark/scoring work, and implementation details. Compatible slices may be ported deliberately after checking them against Final Spec v1.0; do not wholesale merge old workflow semantics into `ai-select-v1`.

## Consequences

### Positive

- product/domain terminology matches the approved user workflow;
- AI rendering has one authoritative observation renderer;
- View, Mask, Candidate, and Native Selection lifecycles become independently testable;
- async correctness and scene mutation recovery are explicit;
- existing renderer/evidence/SAM investments remain reusable;
- native SuperSplat selection/edit history stays authoritative;
- future provenance features can be added without contaminating the v1.0 core model.

### Costs

- substantial refactoring is required in the current editor-side session/panel orchestration;
- existing Prompt Log / Mask Track tests cannot all remain normative;
- Companion contracts must evolve from complete batch publication toward independent/progressive artifacts;
- Coverage/Lift readiness policy requires new target-scoped calibration;
- migration temporarily carries legacy and v1 models side-by-side.

### Risk control

- keep renderer/contributor correctness proofs and locked runtime intact;
- migrate one vertical slice at a time;
- run baseline and boundary-specific tests before and after each migration slice;
- fail closed on camera/protocol/dependency ambiguity;
- do not claim production GPU completeness without the exact locked GPU validation path.

## Non-Goals

This ADR does not:

- define DG-14 Candidate provenance/source-inspection UI;
- introduce persistent semantic objects or project-side AI object databases;
- turn the Companion into a public/multi-user backend;
- replace native SuperSplat selection/edit history;
- require hashing every Gaussian on every edit;
- mandate a specific UI implementation beyond the Final Spec behavior;
- invalidate historical benchmark records merely because their vocabulary is legacy.

## Follow-up

The next implementation step after this contract migration is the `CurrentTargetContext` domain kernel followed quickly by the first end-to-end `CameraBinding → gsplat Anchor RGB` tracer bullet.
