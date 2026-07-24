# 16 — Candidate → Native Set / Add / Remove / Intersect

Status: ready-for-agent — v2.2 FlashSplat-alignment review

Blocked by: 15

## Final Spec mapping

- Final Spec v1.1 §25
- Final Spec v1.1 Amendment 001 — Candidate and readiness propagation
- ADR 0013 implementation staging
- DG-07
- MVP Phase 6

## Inputs / preconditions

- Current non-stale Candidate
- Candidate Evidence backend identity/readiness
- Uncertain diagnostic set
- Native Selection S
- Native SelectOp/EditHistory

## Outputs / handoff artifacts

- Set/Add/Remove/Intersect application
- CandidateApplicationRecord
- Candidate Applied UI state

## What to build

Bridge the current Candidate into native SuperSplat selection with exact set algebra and native history. Evidence, Uncertain, and Out-of-Scope remain internal/diagnostic and are not implicitly applied.

Ticket 14 may produce a reference/PoC Candidate before Ticket 20 provides production same-decision Direct Evidence. The application seam must preserve that backend identity and must not present a reference-only Candidate as production-ready by accident.

## Acceptance criteria

- [ ] Candidate Ready exposes Set/Add/Remove/Intersect with `S'=C`, `S'=S∪C`, `S'=S−C`, `S'=S∩C`.
- [ ] Operations execute through existing SelectOp/EditHistory.
- [ ] Only current non-stale Candidate can execute.
- [ ] Candidate carries `rasterImplementationId`, Evidence backend kind/ID, `runtimeBuildId`, policy identity, and production-readiness state.
- [ ] Production/default application requires a Candidate from a renderer/runtime/backend accepted by current Selection Service readiness policy.
- [ ] Ticket 14 reference/PoC Candidates are explicitly development/reference-gated until Ticket 20/21 production readiness is satisfied; they are never silently labeled production.
- [ ] Tests may exercise native algebra with reference Candidates under an explicit test/development capability.
- [ ] Uncertain, Rejected, and Out-of-Scope are never implicitly included.
- [ ] Applying Candidate does not rerun Evidence/Lift.
- [ ] AI Select and CurrentTargetContext remain active after application.
- [ ] CandidateApplicationRecord binds Candidate revision, raster implementation, Evidence backend, runtime build, operation, and native history command.
- [ ] Candidate Applied shows operation and `Show AI Result`.
- [ ] Candidate overlay is de-emphasized after application while Native Selection retains native style.
- [ ] Native Undo/Redo changes Native Selection without rerunning AI.
- [ ] Native Selection-only changes do not stale Evidence or Candidate.
- [ ] Stale, suspended, renderer-incompatible, runtime-incompatible, reference-disallowed, or otherwise unverified Candidate disables all production operations with an actionable reason.

## Failure / recovery criteria

- [ ] Operation failure leaves Native Selection/EditHistory unchanged and Candidate current.
- [ ] Backend/readiness/implementation-identity failure never mutates Native Selection and does not destroy the inspectable Candidate.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Set algebra and Native Undo/Redo tests
- Reference-gated versus production-ready Candidate application tests
- CandidateApplicationRecord implementation/backend identity test
- Renderer/runtime incompatibility disables production application

## Non-goals

- No implicit Add mode
- No AI-specific parallel undo stack
- No runtime claim that reference/autograd Evidence is production same-decision Evidence