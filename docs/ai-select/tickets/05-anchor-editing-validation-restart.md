# 05 — Anchor editing + support validation + atomic Confirm Anchor + early Restart

Status: implemented — 2026-07-25

Blocked by: 03, 04

## Current Final Spec mapping

- Final Spec v1.3 §§4–7, 19, 22, 24
- DG-09, DG-11, DG-12 and DG-20 as historical editing/confirmation rationale where not superseded
- MVP Phase 2 as historical implementation provenance

Final Spec v1.3 is the only current closure source. Prompt/model details below are historical where superseded by Tickets 04C and 07A.

## Inputs / preconditions

- RGB-ready Anchor AIView
- Editing/Stable Mask
- Camera Inspection
- CurrentTargetContext
- Stable Gaussian ID / Render Working Set support-probe seam

## Outputs / handoff artifacts

- Complete Anchor authoring flow
- Validated/confirmed Anchor revision
- Versioned mask-conditioned Gaussian support result
- Early Restart flow

## What to build

Complete Anchor authoring and recovery. Anchor validation proves computability and coherent Camera/RGB/Mask/support identity. Confirm Anchor no longer requires complete Contributor publication or formal multi-view Evidence.

The support probe is a cheap computability gate, not a hidden lifting implementation. It must not reintroduce complete Contributor production into Anchor confirmation.

## Acceptance criteria

- [x] Prompt refinement and Paint/Erase modify only the pre-confirmation Mask state until Confirm Mask.
- [x] Clear creates an empty Editing Mask; Restore Auto restores the latest valid auto mask and is disabled when none exists.
- [x] Fully manual Clear → Paint → Confirm produces User Confirmed Stable Mask.
- [x] Mask Editor has independent Undo/Redo with explicit focus routing.
- [x] Anchor Validation evaluates computational suitability, not semantic target confidence.
- [x] Hard validation blocks unavailable authoritative RGB, empty/nearly-empty Mask, no computable Gaussian support, pending latest Mask inference revision, invalid Stable ID/Render Working Set, or mismatched Camera/RGB/Mask identity.
- [x] Gaussian support is obtained from a versioned low-cost support/visibility probe with explicit input identity; it is not complete Contributor publication and is not formal P/N/V Evidence.
- [x] The support probe may answer only whether useful Gaussian support is computable/observable under the declared policy; it must not classify Selected/Rejected ownership or become a Candidate source.
- [x] The normal Confirm Anchor path does not invoke the complete Contributor backend. Any reference operation used for diagnostics is explicit, bounded, and outside the product hard gate.
- [x] Soft warnings such as image-boundary contact, extreme size, fragmentation, or weak visible support remain user-overridable.
- [x] Validation refreshes against the latest exact revisions and never confirms stale output.
- [x] Changing Anchor after target intent warns before discarding unconfirmed Prompt/Editing state.
- [x] Confirm Anchor atomically publishes CameraBinding, RGB digest, Stable Mask+digest, Mask Evidence Policy version, TargetDependencyToken, and Scene/Splat identity.
- [x] Complete Contributor identity is not part of the formal Anchor binding.
- [x] Formal per-view/multi-view Evidence and Candidate are not prerequisites for Confirm Anchor.
- [x] Confirmed Anchor remains locked until an explicit allowed adjustment/restart flow.
- [x] Restart is available during Anchor Draft, Camera Inspection, Mask Editing, validation, and confirmed-Anchor early stages.
- [x] Early Restart disposes target-local Anchor/View/Mask/Evidence-status/review/readiness state, rotates targetContextId, and preserves Native Selection/EditHistory/policy/runtime caches.
- [x] Restart during Camera Inspection restores saved Scene View before constructing the new Anchor.
- [x] Restart confirmation states clearly that Native Selection does not change.

## Failure / recovery criteria

- [x] Mask inference failure preserves View/RGB and supports Retry Auto Mask / Manual Draw / later Exclude.
- [x] Support-probe/validation failure offers Fix Mask / Adjust Anchor / Restart and does not relabel RGB as Render Failed.
- [x] Unavailable debug/reference Contributor data does not make an otherwise computable Anchor invalid.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion for support-probe/Mask changes
- Binding mismatch and no-complete-Contributor Confirm tests
- Test that support probe cannot publish Candidate/Evidence or call the production reference-Contributor path implicitly
- Manual focus/restart walkthrough

## Non-goals

- No Generated Views beyond Confirm transition
- No formal P/N/V artifact
- No Candidate
- No complete Contributor production or tolerance tuning

## Historical implementation record — 2026-07-25

Editor (TypeScript):

- `src/ai-select/mask-registry.ts` — `clearEditing`, `restoreEditing`, `latestAutoMask`: Clear publishes an empty manual draft; Restore Auto / mask-local Undo/Redo navigate retained Editing-chain versions only.
- `src/ai-select/mask-controller.ts` — Clear / Restore Auto / `undoMaskEdit` / `redoMaskEdit`, locked-Anchor mutation rejection and exact RGB/context invalidation.
- `src/ai-select/mask-analysis.ts` — union-find 4-connected component/area/boundary analysis.
- `src/ai-select/anchor-validation.ts` — versioned validation policy with hard blocks and soft warnings.
- `src/ai-select/support-probe.ts` — versioned computability probe whose response is restricted to `{computable, observedGaussianCount}`; ownership/Evidence-shaped fields fail closed.
- `src/ai-select/anchor-confirmation.ts` — local evaluation, support probe, fresh re-validation and atomic ConfirmedAnchor publication.
- Transport, UI and localization seams for support probe, validation, Confirm, Adjust and Restart.

Companion (Python):

- pure-CPU support-probe policy and versioned request/response route;
- no P/N/V or Contributor computation;
- same-attempt replay versus new-attempt execution and bounded operation admission.

## Validation recorded — 2026-07-25

- `npm test` — 224 editor tests passed.
- `npm run test:companion` — 215 tests passed.
- lint, locale lint and build passed.
- code review findings around component labelling, duplicated helpers and missing Adjust Anchor control were fixed.

Known gaps / handoff notes:

- The support probe is a CPU computability seam, not the same-decision production Evidence path. Ticket 20 owns formal P/N/V.
- Current Prompt candidate/refinement semantics are owned by Tickets 04C and 07A.
- No GPU validation was required for the pure-CPU support probe.