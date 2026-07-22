# 16 — Candidate → Native Set / Add / Remove / Intersect

Status: ready-for-agent

Blocked by: 15

## Final Spec mapping

- DG-07
- §64–67 Native Operations
- MVP Phase 6

## Inputs / preconditions

- Current Candidate
- Native Selection S
- Native SelectOp/EditHistory

## Outputs / handoff artifacts

- Set/Add/Remove/Intersect application
- CandidateApplicationRecord
- Candidate Applied UI state

## What to build

Bridge the current Candidate into native SuperSplat selection with the four Final Spec operations,
using existing SelectOp/EditHistory rather than a parallel AI history system.

## Acceptance criteria

- [ ] Candidate Ready exposes Set / Add / Remove / Intersect with exact semantics `S'=C`, `S'=S∪C`, `S'=S−C`, `S'=S∩C`.
- [ ] All four operations execute through existing native SelectOp/EditHistory semantics.
- [ ] Only a current non-stale Candidate can execute an operation.
- [ ] Uncertain remains diagnostic and is never implicitly included in native Candidate operations.
- [ ] Applying Candidate does not rerun AI inference.
- [ ] AI Select remains active and CurrentTargetContext remains available after application.
- [ ] CandidateApplicationRecord binds candidate ID/revision, operation, and associated native history command identity.
- [ ] Candidate Applied state shows the applied operation and provides `Show AI Result`.
- [ ] Candidate overlay is hidden/weak by default after application while Native Selection keeps normal SuperSplat visual style.
- [ ] Native Undo restores Native Selection without rerunning AI and returns application presentation to the appropriate Candidate-ready state.
- [ ] Native Redo reapplies the same native selection operation without rerunning AI.
- [ ] Native Selection-only changes do not stale Candidate because Native Selection is not an AI input dependency.
- [ ] Contextual toolbar implements Candidate Ready and Candidate Applied presentation.

## Failure / recovery criteria

- [ ] Operation failure leaves Native Selection/EditHistory unchanged and keeps Candidate current.
- [ ] Stale/suspended context disables all four operations.

## Affected seams

- src/ai-select/native-selection-bridge*
- src/selection.ts
- src/edit-history.ts
- SelectOp seam
- Contextual toolbar
- Candidate visualization

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Set/Add/Remove/Intersect algebra tests
- Native Undo/Redo workflow tests

## Non-goals

- No implicit Add mode
- No AI-specific parallel undo stack
