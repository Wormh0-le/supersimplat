# 05 — Anchor editing + support validation + atomic Confirm Anchor + early Restart

Status: ready-for-agent — v2.2 FlashSplat-alignment review

Blocked by: 03, 04

## Final Spec mapping

- Final Spec v1.1 §§10–12, 24
- DG-09, DG-11, DG-12, DG-20
- MVP Phase 2

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

- [ ] Prompt refine and Brush Add/Erase modify only Editing Mask until Confirm Mask.
- [ ] Clear creates an empty Editing Mask; Restore Auto restores the latest valid auto mask and is disabled when none exists.
- [ ] Fully manual Clear → Brush → Confirm produces User Confirmed Stable Mask.
- [ ] Mask Editor has independent Undo/Redo with explicit focus routing.
- [ ] Anchor Validation evaluates computational suitability, not semantic target confidence.
- [ ] Hard validation blocks unavailable authoritative RGB, empty/nearly-empty Mask, no computable Gaussian support, pending latest Mask/SAM revision, invalid Stable ID/Render Working Set, or mismatched Camera/RGB/Mask identity.
- [ ] Gaussian support is obtained from a versioned low-cost support/visibility probe with explicit input identity; it is not complete Contributor publication and is not formal P/N/V Evidence.
- [ ] The support probe may answer only whether useful Gaussian support is computable/observable under the declared policy; it must not classify Selected/Rejected ownership or become a Candidate source.
- [ ] The normal Confirm Anchor path does not invoke the complete Contributor backend. Any reference operation used for diagnostics is explicit, bounded, and outside the product hard gate.
- [ ] Soft warnings such as image-boundary contact, extreme size, fragmentation, or weak visible support remain user-overridable.
- [ ] Validation refreshes against the latest exact revisions and never confirms stale output.
- [ ] Changing Anchor after target intent warns before discarding unconfirmed Prompt/Editing state.
- [ ] Confirm Anchor atomically publishes CameraBinding, RGB digest, Stable Mask+digest, Mask Evidence Policy version, TargetDependencyToken, and Scene/Splat identity.
- [ ] Complete Contributor identity is not part of the formal Anchor binding.
- [ ] Formal per-view/multi-view Evidence and Candidate are not prerequisites for Confirm Anchor.
- [ ] Confirmed Anchor remains locked until an explicit allowed adjustment/restart flow.
- [ ] Restart is available during Anchor Draft, Camera Inspection, Mask Editing, validation, and confirmed-Anchor early stages.
- [ ] Early Restart disposes target-local Anchor/View/Mask/Evidence-status/review/readiness state, rotates targetContextId, and preserves Native Selection/EditHistory/policy/runtime caches.
- [ ] Restart during Camera Inspection restores saved Scene View before constructing the new Anchor.
- [ ] Restart confirmation states clearly that Native Selection does not change.

## Failure / recovery criteria

- [ ] Mask/SAM failure preserves View/RGB and supports Retry Auto Mask / Manual Draw / later Exclude.
- [ ] Support-probe/validation failure offers Fix Mask / Adjust Anchor / Restart and does not relabel RGB as Render Failed.
- [ ] Unavailable debug/reference Contributor data does not make an otherwise computable Anchor invalid.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- npm run test:companion for support-probe/SAM changes
- Binding mismatch and no-complete-Contributor Confirm tests
- Test that support probe cannot publish Candidate/Evidence or call the production reference-Contributor path implicitly
- Manual focus/restart walkthrough

## Non-goals

- No Generated Views beyond Confirm transition
- No formal P/N/V artifact
- No Candidate
- No complete Contributor production or tolerance tuning