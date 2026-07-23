# 22 — Contract superseded legacy product and Contributor paths

Status: ready-for-agent — v2.2 re-audited

Blocked by: 21

## Final Spec mapping

- Final Spec v1.1 §§0, 19, 30 Stage 5
- ADR 0012 as partially superseded by ADR 0013
- Final migration contraction

## Inputs / preconditions

- Complete validated Final Spec v1.1 path
- Production same-decision Direct Evidence
- Legacy ObjectSelectionSession product path
- Complete Contributor reference backend

## Outputs / handoff artifacts

- One authoritative AI Select product model
- Legacy orchestration isolated/removed
- Contributor explicitly constrained to debug/reference use

## What to build

Only after the v1.1 path is production-hardened, remove or isolate superseded user-visible orchestration and any normal-path dependency on complete per-pixel Contributor. Preserve validated foundations and historical benchmark/reference assets.

## Acceptance criteria

- [ ] Production AI Select no longer depends on ObjectSelectionSession as lifecycle container.
- [ ] Production UI no longer exposes New/Add/Remove/Refine inference modes.
- [ ] Production Anchor contains no PlayCanvas capture path.
- [ ] PromptLog/MaskTrack/FrameSet/MaskSet remain only where explicitly justified as internal adapters/fixtures.
- [ ] Preview → Confirm → Selection Commit → close is not active product lifecycle.
- [ ] Complete Contributor is not required for RGB Ready, Anchor Confirm, formal Lift, or Candidate publication.
- [ ] Complete Contributor remains available only as a clearly named debug/reference backend for fixtures and diagnostics.
- [ ] Contributor failure cannot invalidate successful RGB or Direct Evidence.
- [ ] Old workflow tests are removed/replaced while low-level correctness/reference fixtures remain.
- [ ] Preserve Stable IDs, SceneSnapshot/spatial working sets, authoritative RGB, SAM, P/N/V policy, reference Contributor, planner primitives, native SelectOp/EditHistory, and benchmark assets where compatible.
- [ ] Comments/docs do not present v1.0 Contributor production semantics or legacy sessions as current architecture.
- [ ] AI Select remains a native Selection Tool, not a workspace/app.
- [ ] Final repository and locked GPU v1.1 regression pass.

## Failure / recovery criteria

- [ ] Contraction does not delete historical benchmark/reference artifacts merely because terminology is legacy.
- [ ] Retained shims are explicitly non-normative and cannot leak legacy semantics into UI/domain.
- [ ] Removal occurs only after replacement validation, not by assumption.

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU Final Spec v1.1 end-to-end regression
- Reference Contributor diagnostics regression
- Native SuperSplat regression

## Non-goals

- Do not remove validated foundations retained by ADR 0012/0013
- Do not re-open DG-14