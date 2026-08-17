# 22 — Contract superseded legacy product and Contributor paths

Status: closed — 2026-08-17; Final Spec v1.3 core graph complete

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

- [x] Production AI Select no longer depends on ObjectSelectionSession as lifecycle container.
- [x] Production UI no longer exposes New/Add/Remove/Refine inference modes.
- [x] Production Anchor contains no PlayCanvas capture path.
- [x] PromptLog/MaskTrack/FrameSet/MaskSet remain only where explicitly justified as historical adapters/fixtures.
- [x] Preview → Confirm → Selection Commit → close is not an active product lifecycle.
- [x] Complete Contributor is not required for RGB Ready, Anchor Confirm, formal Lift, or Candidate publication.
- [x] Complete Contributor remains available only as a clearly named debug/reference backend for fixtures and diagnostics.
- [x] Contributor failure cannot invalidate successful RGB or Direct Evidence.
- [x] Static SAM 3.1 Multiplex/private-head adapters cannot advertise Ready for current image-instance segmentation.
- [x] Negative Box, Prompt Brush, Mask Constraints and Text Prompt cannot re-enter current PromptState, capability records or UI.
- [x] Legacy `generated-view-mask/v1`, `maskSource: 'propagated'`, provider-returned Assessment, backend registry, Route B/C/D and automatic fallback state cannot validate as current.
- [x] Old workflow tests are removed/replaced while low-level correctness/reference fixtures remain.
- [x] Preserve Stable IDs, SceneSnapshot/spatial working sets, authoritative RGB, current SAM 3 Image adapter, P/N/V policy, reference Contributor, bounded local-view primitives, native SelectOp/EditHistory, and benchmark assets where compatible.
- [x] Comments/docs do not present v1.0/v1.1/v1.2 Contributor, Multiplex, route or legacy-session semantics as current architecture.
- [x] AI Select remains a native Selection Tool, not a workspace/app.
- [x] Final repository and locked GPU Final Spec v1.3 regression pass.

## Failure / recovery criteria

- [x] Contraction does not delete historical benchmark/reference artifacts merely because terminology is legacy.
- [x] Retained shims are explicitly non-normative and cannot leak legacy semantics into UI/domain.
- [x] Removal occurs only after replacement validation, not by assumption.
- [x] Existing User Confirmed Stable Masks remain inspectable and authoritative under their exact identities.

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

## Implementation record — 2026-08-17

- Removed the browser `ObjectSelectionSession` domain, factory, editor bridge,
  panel, toolbar, styles, transport methods and workflow tests. The production
  adapter now composes only current AI Select renderer, Mask, geometry, View,
  Evidence and Candidate provider interfaces.
- Removed public Companion Object Selection Session and Frame Set routes plus
  their workflow/control-plane tests. Frozen in-process PromptLog, MaskTrack,
  FrameSet and MaskSet helpers remain reference-only for benchmark replay.
- Contracted SAM 3 Image Prompt capabilities to the five current fields and
  exact-key validation. Removed Prompt families cannot re-enter readiness or
  compiler capability records as false placeholders.
- Removed Reference Candidate from the current Runtime Profile and the product
  application composition root. Complete Contributor and Multiplex remain
  explicitly named reference/fixture paths and cannot gate RGB, Direct
  Evidence, formal Re-Lift, Candidate publication or native application.
- Marked the legacy `generated-view-mask/v1` helper and propagated source as a
  frozen fixture seam with no product route; current rejection regressions
  remain.
- Moved the Dock's eager readiness subscription after render-owned DOM
  initialization; the locked browser regression discovered the ordering bug
  and a focused regression test now protects it.
- Advanced the mapping, graph, manifest, traceability, walkthrough, migration,
  audit and Final Spec closure records to v2.38 with no next core Ticket.
- Validation passed: `rtk npm test` (628 browser/editor and 441 Companion
  tests; two expected skips), explicit `rtk npm run test:companion`, lint,
  locale lint, build, four locked SAM 3 Image GPU tests, seven locked Direct
  Evidence GPU tests, three locked spatial-render parity tests, static legacy
  audits, a locked browser Final Spec regression through the calibrated
  `not-ready` Re-Lift branch, manifest/link validation and `git diff --check`.
- Final Standards and Spec review axes both passed with no findings.
- Full evidence is recorded in [Ticket 22 legacy contraction closeout](../benchmarks/22-legacy-contraction-closeout.md).
