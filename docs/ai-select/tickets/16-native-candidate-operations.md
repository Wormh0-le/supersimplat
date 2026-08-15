# 16 — Candidate → Native Set / Add / Remove / Intersect

Status: implemented — 2026-08-14 — Final Spec v1.3 mapped

Blocked by: 15

## Current Final Spec mapping

- Final Spec v1.3 §§22, 24
- ADR 0013 implementation staging where not superseded
- DG-07 and Final Spec v1.1 Amendment 001 as historical native-application/readiness rationale only
- MVP Phase 6 as historical implementation provenance
- Ticket 16A as the post-closure AI View Dock and Candidate viewport-presentation stage

Final Spec v1.3 is the only current closure source.

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

- [x] Candidate Ready exposes Set/Add/Remove/Intersect with `S'=C`, `S'=S∪C`, `S'=S−C`, `S'=S∩C`.
- [x] Operations execute through existing SelectOp/EditHistory.
- [x] Only current non-stale Candidate can execute.
- [x] Candidate carries `rasterImplementationId`, Evidence backend kind/ID, `runtimeBuildId`, policy identity, and production-readiness state.
- [x] Production/default application requires a Candidate from a renderer/runtime/backend accepted by current Selection Service readiness policy.
- [x] Ticket 14 reference/PoC Candidates are explicitly development/reference-gated until Ticket 20/21 production readiness is satisfied; they are never silently labeled production.
- [x] Tests may exercise native algebra with reference Candidates under an explicit test/development capability.
- [x] Uncertain, Rejected, and Out-of-Scope are never implicitly included.
- [x] Applying Candidate does not rerun Evidence/Lift.
- [x] AI Select and CurrentTargetContext remain active after application.
- [x] CandidateApplicationRecord binds Candidate revision, raster implementation, Evidence backend, runtime build, operation, and native history command.
- [x] The implemented closure surface showed Candidate Applied operation and
      `Show AI Result`; Ticket 16A supersedes that Dock presentation without
      changing this Ticket's application semantics.
- [x] Candidate overlay is de-emphasized after application while Native Selection retains native style.
- [x] Native Undo/Redo changes Native Selection without rerunning AI.
- [x] Native Selection-only changes do not stale Evidence or Candidate.
- [x] Stale, suspended, renderer-incompatible, runtime-incompatible, reference-disallowed, or otherwise unverified Candidate disables all production operations with an actionable reason.

## Failure / recovery criteria

- [x] Operation failure leaves Native Selection/EditHistory unchanged and Candidate current.
- [x] Backend/readiness/implementation-identity failure never mutates Native Selection and does not destroy the inspectable Candidate.

## Implementation evidence

- `CandidateApplicationController` owns fail-closed applicability, exact runtime/policy identity checks, Candidate Applied state, overlay emphasis, and the immutable `CandidateApplicationRecord`.
- `SelectOpCandidateNativeSelection` maps Selected Stable Gaussian IDs and commits Set/Add/Remove/Intersect through `SelectOp` and transactional `EditHistory.addFromFactory`.
- The Dock exposes all four explicit operations, actionable disabled reasons, applied-operation status, and `Show AI Result`.
- Reference Candidate schema v2 declares `productionReadiness: reference-only`; default production application remains blocked. The explicit `?aiSelect.referenceCandidateApplication=development` capability is the only reference path.
- The application handoff also accepts a publisher-validated `production-ready` Candidate only when its Direct Evidence renderer/backend/runtime/policy identity exactly matches readiness. Ticket 20 still owns the live production publisher and capability composition.
- Focused tests cover all four set operations, Selected-only application, the real `SelectOp`/`EditHistory` adapter and Undo/Redo, reference and synthetic production-ready gates, identity/readiness blockers, queued staleness, operation failure, discarded-redo cleanup, and observer isolation.

“Candidate overlay” in this Ticket means the minimal Candidate/Uncertain Dock
status visualization established by Ticket 14D. Application de-emphasizes that
status while native selection retains its editor styling; `Show AI Result`
restores the status emphasis. This Ticket does not introduce a new spatial 3D
Candidate renderer.

## Post-closure presentation follow-up

Ticket 16 remains implemented as the owner of applicability, exact set algebra,
the Native `SelectOp`/`EditHistory` adapter and `CandidateApplicationRecord`.
Ticket 16A replaces the closure-time Dock presentation with a real,
non-destructive main-viewport Candidate Overlay, moves the four operations to
the fixed AI Select Toolbar, adds the Status Bar Candidate projection and
removes the old `Show AI Result`. Ticket 16A must reuse rather than reimplement
this Ticket's application core.

## Validation

- [x] `npm test` — 544 Node tests and 445 Companion tests passed; 1 Companion test skipped.
- [x] `npm run lint`
- [x] `npm run lint:locales` — all 8 non-English locales match the 513-key English catalog.
- [x] `npm run build`
- [x] Set algebra and Native Undo/Redo tests
- [x] Reference-gated versus synthetic production-ready application-seam tests; the live Ticket 20 production publisher does not exist yet.
- [x] CandidateApplicationRecord implementation/backend identity test
- [x] Renderer/runtime incompatibility disables production application

Production same-decision GPU Evidence was not exercised by this Ticket; Tickets
20/21 retain that validation and release-calibration ownership.

## Non-goals

- No implicit Add mode
- No AI-specific parallel undo stack
- No runtime claim that reference/autograd Evidence is production same-decision Evidence
