# 14A — Evidence Contract & Working Set

Status: implemented — execution stage of parent Ticket 14

Blocked by: none (Tickets 11 and 12 are implemented)

Blocks: 14B

## Current Final Spec mapping

- Parent Ticket 14
- Final Spec v1.3 §§20–22, 24–25
- ADR 0013
- ADR 0016 where geometry/Prompt acquisition boundaries apply

Final Spec v1.3 and the parent Ticket 14 remain authoritative. This stage only narrows implementation scope.

## Goal

Define the exact formal Evidence admission contract and Working Set boundaries required before reference P/N/V computation begins.

## Inputs / preconditions

- current `CurrentTargetContext` and dependency identity;
- current AIViews;
- authoritative RGB identity;
- Stable Mask identity;
- Participation state;
- Stable Gaussian IDs and SceneSnapshot;
- Render Working Set seam;
- versioned Evidence Policy;
- `TargetGeometryHintArtifact` only as localization / conservative Working-Set seed context.

## Outputs / handoff

- versioned per-view `GaussianEvidenceArtifact` contract;
- Core Target Set / Context Set / Evidence Working Set definitions;
- exact artifact identity/binding rules;
- admission/fail-closed validation helpers usable by 14B;
- fixtures for Included/Excluded/no-Stable-Mask and Working-Set boundary behavior.

## Acceptance criteria

- [x] Formal Evidence input is exactly a current View with Render Ready + Stable Mask + Participation Included and matching current identities.
- [x] Excluded Views and Views without Stable Mask are rejected before Evidence computation.
- [x] View role/source, Prompt geometry, SAM score, previous-logits refs and MaskReview reasons never become ownership Evidence.
- [x] Define Core Target Set, Context Set and Evidence Working Set without treating TargetGeometryHint as ownership.
- [x] Render Working Set remains conservative enough to preserve occluders/transmittance contributors outside Evidence Working Set.
- [x] Gaussians outside Evidence Working Set may composite but receive no P/N/V writes.
- [x] TargetGeometryHint may seed Evidence Working Set but is not a hard upper bound; later Included View support may expand it.
- [x] Working-Set boundary contact produces declared expansion/fail-closed diagnostics rather than silent truncation.
- [x] Per-view artifact binds target/context/dependency, CameraBinding, RGB, Stable Mask, Evidence Policy, Render/Evidence Working Sets, Stable IDs, raster/reference backend and runtime identity.
- [x] Incompatible identity changes invalidate the artifact deterministically.
- [x] Reference artifact identity cannot be mistaken for Ticket 20 production same-decision Evidence.
- [x] Artifact contract supports exclude/reinclude, Stable Mask replacement and incremental Re-Lift invalidation.

## Implementation evidence

- Browser contract and fail-closed admission: `src/ai-select/gaussian-evidence-contract.ts`.
- Companion contract mirror: `selection-service-companion/src/selection_service_companion/gaussian_evidence_contract.py`.
- Shared Unicode and IEEE-754 digest vector: `test/fixtures/ai-select-gaussian-evidence-contract-vectors.json`.
- Browser and Companion contract tests cover admission, exclusion, Stable Mask absence, Render/Evidence Working Set separation, boundary handling, identity invalidation, and reference-only backend identity.

This stage creates no P/N/V computation, aggregation, Candidate publication, UI action, or production same-decision GPU path. Those remain respectively 14B–14D and Ticket 20 work.

## Failure / recovery

- Missing Render Working Set, invalid Stable ID mapping, non-finite identity data or stale binding fails closed before 14B computation.
- Failure preserves RGB, Stable Masks, Participation and the prior Candidate.
- No partial Evidence artifact becomes current.

## Validation

- TypeScript/Python contract tests as applicable;
- Included/Excluded/no-Stable-Mask fixtures;
- out-of-scope occluder fixture;
- TargetGeometryHint-seed expansion fixture;
- Working-Set boundary fail-closed fixture;
- stale identity / incompatible runtime fixture.

## Non-goals

- No P/N/V numerical computation; 14B owns it.
- No multi-view classification; 14C owns it.
- No Candidate publication; 14D owns it.
- No Native Selection mutation.
- No production same-decision CUDA path; Ticket 20 owns it.
