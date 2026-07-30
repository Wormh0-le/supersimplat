# 22 — Contract superseded legacy product and Contributor paths

Status: ready-for-agent — Final Spec v1.3 final contraction

Blocked by: 21

## Current Final Spec mapping

- Final Spec v1.3 §§0, 16, 20–25
- ADR 0012 as historical product-path rationale where compatible with ADR 0013 and ADR 0016
- Final migration contraction

Final Spec v1.3 is the only current implementation and closure source. Final Spec v1.1/v1.2 paths are migration inputs only.

## Inputs / preconditions

- Complete validated Final Spec v1.3 path
- Production same-decision Direct Evidence
- Legacy ObjectSelectionSession product path
- Complete Contributor reference backend
- Historical Multiplex, removed Prompt-family and `generated-view-mask/v1` seams

## Outputs / handoff artifacts

- One authoritative AI Select product model
- Legacy orchestration isolated/removed
- Contributor explicitly constrained to debug/reference use
- Superseded SAM/Prompt/backend-route artifacts unable to validate as current

## What to build

Only after the Final Spec v1.3 path is production-hardened, remove or isolate superseded user-visible orchestration and any normal-path dependency on complete per-pixel Contributor, static Multiplex, removed Prompt families, generic acquisition routes or legacy Generated Mask contracts. Preserve validated foundations and historical benchmark/reference assets.

## Acceptance criteria

- [ ] Production AI Select no longer depends on ObjectSelectionSession as lifecycle container.
- [ ] Production UI no longer exposes New/Add/Remove/Refine inference modes.
- [ ] Production Anchor contains no PlayCanvas capture path.
- [ ] PromptLog/MaskTrack/FrameSet/MaskSet remain only where explicitly justified as historical adapters/fixtures.
- [ ] Preview → Confirm → Selection Commit → close is not an active product lifecycle.
- [ ] Complete Contributor is not required for RGB Ready, Anchor Confirm, formal Lift, or Candidate publication.
- [ ] Complete Contributor remains available only as a clearly named debug/reference backend for fixtures and diagnostics.
- [ ] Contributor failure cannot invalidate successful RGB or Direct Evidence.
- [ ] Static SAM 3.1 Multiplex/private-head adapters cannot advertise Ready for current image-instance segmentation.
- [ ] Negative Box, Prompt Brush, Mask Constraints and Text Prompt cannot re-enter current PromptState, capability records or UI.
- [ ] Legacy `generated-view-mask/v1`, `maskSource: 'propagated'`, provider-returned Assessment, backend registry, Route B/C/D and automatic fallback state cannot validate as current.
- [ ] Old workflow tests are removed/replaced while low-level correctness/reference fixtures remain.
- [ ] Preserve Stable IDs, SceneSnapshot/spatial working sets, authoritative RGB, current SAM 3 Image adapter, P/N/V policy, reference Contributor, bounded local-view primitives, native SelectOp/EditHistory, and benchmark assets where compatible.
- [ ] Comments/docs do not present v1.0/v1.1/v1.2 Contributor, Multiplex, route or legacy-session semantics as current architecture.
- [ ] AI Select remains a native Selection Tool, not a workspace/app.
- [ ] Final repository and locked GPU Final Spec v1.3 regression pass.

## Failure / recovery criteria

- [ ] Contraction does not delete historical benchmark/reference artifacts merely because terminology is legacy.
- [ ] Retained shims are explicitly non-normative and cannot leak legacy semantics into UI/domain.
- [ ] Removal occurs only after replacement validation, not by assumption.
- [ ] Existing User Confirmed Stable Masks remain inspectable and authoritative under their exact identities.

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU Final Spec v1.3 end-to-end regression
- Static Multiplex/private-head absence audit
- Removed Prompt schema/UI audit
- Legacy Generated Mask/backend-route rejection regression
- Reference Contributor diagnostics regression
- Native SuperSplat regression

## Non-goals

- Do not remove validated foundations retained by ADR 0012/0013/0016
- Do not re-open DG-14
- No new model, Prompt family, backend registry or tracking architecture