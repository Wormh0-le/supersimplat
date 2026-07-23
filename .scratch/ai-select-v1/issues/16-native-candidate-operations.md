# 16 — Candidate → Native Set / Add / Remove / Intersect

Status: ready-for-agent — v2.2 re-audited

Blocked by: 15

## Final Spec mapping

- Final Spec v1.1 §25
- DG-07
- MVP Phase 6

## Inputs / preconditions

- Current non-stale Candidate
- Uncertain diagnostic set
- Native Selection S
- Native SelectOp/EditHistory

## Outputs / handoff artifacts

- Set/Add/Remove/Intersect application
- CandidateApplicationRecord
- Candidate Applied UI state

## What to build

Bridge the current Candidate into native SuperSplat selection with exact set algebra and native history. Evidence, Uncertain, and Out-of-Scope remain internal/diagnostic and are not implicitly applied.

## Acceptance criteria

- [ ] Candidate Ready exposes Set/Add/Remove/Intersect with `S'=C`, `S'=S∪C`, `S'=S−C`, `S'=S∩C`.
- [ ] Operations execute through existing SelectOp/EditHistory.
- [ ] Only current non-stale Candidate can execute.
- [ ] Uncertain, Rejected, and Out-of-Scope are never implicitly included.
- [ ] Applying Candidate does not rerun Evidence/Lift.
- [ ] AI Select and CurrentTargetContext remain active after application.
- [ ] CandidateApplicationRecord binds Candidate revision, operation, and native history command.
- [ ] Candidate Applied shows operation and `Show AI Result`.
- [ ] Candidate overlay is de-emphasized after application while Native Selection retains native style.
- [ ] Native Undo/Redo changes Native Selection without rerunning AI.
- [ ] Native Selection-only changes do not stale Evidence or Candidate.
- [ ] Stale/suspended context disables all operations.

## Failure / recovery criteria

- [ ] Operation failure leaves Native Selection/EditHistory unchanged and Candidate current.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Set algebra and Native Undo/Redo tests

## Non-goals

- No implicit Add mode
- No AI-specific parallel undo stack