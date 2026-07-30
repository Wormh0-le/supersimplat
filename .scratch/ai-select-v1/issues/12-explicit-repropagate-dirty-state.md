# 12 — Explicit Mask Refresh + Evidence Dirty / Candidate Stale

Status: blocked — waits for 08B and 09

Blocked by: 08B, 09, 07, 05

## Final Spec mapping

- Final Spec v1.3 §§16, 19–21, 24–26
- ADR 0016

## Purpose

Implement explicit recompute semantics for the simplified static-image pipeline.

```text
Anchor Stable change
→ TargetGeometryHint dirty
→ local Key-View plan dirty
→ dependent per-View Prompt/Mask dirty

View Camera/RGB change
→ that View Prompt/Mask/Evidence dirty

Stable Mask or Participation change
→ that View Evidence dirty
→ Lift dirty
→ Candidate stale
```

No refresh action automatically Re-Lifts.

## Formal dirty state

- `targetGeometryDirty`;
- `localKeyViewPlanDirty`;
- `promptDirtyViewIds`;
- `maskInferenceDirtyViewIds`;
- `evidenceDirtyViewIds`;
- `liftDirty`;
- `candidateStale`.

There is no current propagation/sequence/reference dirty state.

## Prompt and Mask refresh

### Regenerate 3D-guided Prompt

- consumes exact current TargetGeometryHint, local plan, View Camera/RGB, adapter capability and synthesis policy;
- creates a new immutable `ImageInstancePromptArtifact`;
- does not run SAM unless the user invokes a combined Refresh action;
- never changes Stable Mask or Evidence.

### Retry / Refresh Auto Mask

- consumes exact current Prompt artifact and resolvable authoritative RGB artifact/reference;
- creates a new inference attempt;
- uses the single Active SAM 3 Image provider from 04C;
- produces at most one Mask for generated 3D-guided requests;
- runs Mask Review and publication through current layers;
- never silently overwrites User Confirmed Stable Mask;
- affects only the selected View.

## Previous logits lifecycle

- actual logits tensors remain Companion-local;
- browser state contains only opaque `PreviousPredictionLogitsRef` metadata;
- a ref is reusable only for explicit Point refinement in Prompt mode on the same View/RGB/adapter/Companion/candidate lineage;
- candidate change, camera/RGB change, adapter/runtime change, Companion Instance replacement, state eviction or target disposal invalidates it;
- ordinary Retry does not silently reuse a ref;
- missing/expired ref causes fresh inference from current Points/Box without `mask_input`;
- no binary Prompt Brush or Editing Mask is converted into logits;
- ref changes do not dirty Evidence until a new Stable Mask is published.

## Identity and migration

Reject as current:

- SAM 3.1 Multiplex static artifacts;
- `generated-view-mask/v1` responses/cache;
- `maskSource: 'propagated'` generic provenance;
- provider-returned Assessment coupling;
- Negative Box / Mask Constraint / Prompt Brush artifacts;
- raw logits tensor in browser Prompt/request payload;
- backend registry/fallback/sequence identities.

Existing User Confirmed Stable Masks remain current when their own RGB/Mask identity remains valid.

## Acceptance criteria

- [ ] Anchor Stable change invalidates geometry, plan and dependent View Prompt/Mask work.
- [ ] geometry or local plan replacement invalidates only bound dependants.
- [ ] Camera/RGB change dirties only that View plus downstream Lift.
- [ ] unconfirmed Editing changes do not dirty Evidence.
- [ ] Prompt regeneration and Mask Retry remain separate operations.
- [ ] explicit Retry creates a new inference attempt.
- [ ] every inference request resolves exact authoritative RGB bytes/ref.
- [ ] previous-logits ref validates exact same-image and same-Companion lineage.
- [ ] Companion replacement or expired ref falls back to fresh no-logits inference.
- [ ] semantic unavailable differs from technical failure.
- [ ] failure preserves prior Stable Mask and matching Evidence/Candidate state.
- [ ] no backend fallback or propagation dirty state exists.
- [ ] old Multiplex/Prompt/cache artifacts fail current validation.
- [ ] no refresh automatically Re-Lifts.

## Validation

- dirty dependency table tests;
- Prompt-only regeneration tests;
- per-View RGB resolution/Retry/stale-result tests;
- previous-logits ref lineage and Companion-replacement invalidation;
- semantic-unavailable versus technical failure;
- User Confirmed preservation;
- old schema/cache rejection;
- Generate More no-dirty regression;
- repository test/lint/build.

## Non-goals

- No backend registry or automatic route fallback.
- No tracker references or repropagation.
- No Evidence computation or Candidate implementation.
- No continuous inference while editing.
