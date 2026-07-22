# 22 — Contract superseded legacy Object Selection product path

Status: ready-for-agent

Blocked by: 21

## Final Spec mapping

- ADR 0012 supersession
- Final migration contraction

## Inputs / preconditions

- Complete validated Final Spec v1.0 path
- Legacy ObjectSelectionSession product path

## Outputs / handoff artifacts

- One authoritative AI Select product model
- Legacy internals isolated/removed where superseded

## What to build

Only after the Final Spec path is complete and production-hardened, remove/isolate the superseded
user-visible Object Selection orchestration. Preserve validated low-level algorithms, Stable IDs,
SceneSnapshot, gsplat/SAM/Evidence/planner primitives, native selection integration, and benchmark assets.

## Acceptance criteria

- [ ] Production AI Select no longer depends on legacy ObjectSelectionSession as its user-visible lifecycle container.
- [ ] Production UI no longer exposes New/Add/Remove/Refine inference modes.
- [ ] Production AI Anchor path contains no PlayCanvas canvas-capture observation path.
- [ ] PromptLog/MaskTrack/complete FrameSet-MaskSet may remain only as internal compatibility/model-adapter/benchmark details where still justified.
- [ ] Preview → Confirm → Selection Commit → close is no longer an active product lifecycle.
- [ ] Old workflow tests asserting superseded behavior are removed/replaced while unrelated low-level correctness tests are preserved.
- [ ] Stable Gaussian IDs, SceneSnapshot, Companion readiness, gsplat/Contributor, SAM runtime, Evidence Policy mathematics, compatible planner primitives, SelectOp/EditHistory, and benchmark fixtures remain preserved where compatible.
- [ ] Code comments/docs no longer present superseded concepts as current architecture.
- [ ] AI Select remains a native Selection Tool, not a new workspace/app.
- [ ] Final full repository validation and locked GPU Final Spec regression pass.

## Failure / recovery criteria

- [ ] Contraction must not delete historical benchmark artifacts merely because terminology is legacy.
- [ ] Any compatibility shim retained after contraction is clearly non-normative and cannot leak legacy product semantics back into UI/domain.

## Affected seams

- src/object-selection-session.ts/factory
- legacy object-selection UI
- src/main.ts legacy wiring
- legacy transport/orchestration paths
- legacy workflow tests/docs

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run lint:locales
- npm run build
- Locked GPU Final Spec end-to-end regression
- Native SuperSplat regression

## Non-goals

- Do not remove validated foundations listed in ADR 0012
- Do not re-open DG-14
