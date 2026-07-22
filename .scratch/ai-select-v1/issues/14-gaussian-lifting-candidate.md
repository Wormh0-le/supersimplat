# 14 — Included Stable Views → Gaussian Lifting → Candidate / Uncertain

Status: ready-for-agent

Blocked by: 13

## Final Spec mapping

- §51–58 Lifting/Candidate
- DG-03 retired semantics
- MVP Phase 5

## Inputs / preconditions

- Included Stable View Annotations
- Core/Context set
- Versioned Evidence Policy
- Current dependency identity

## Outputs / handoff artifacts

- Atomic Candidate
- Uncertain overlay data
- Rejected/Out-of-scope internal classes as needed
- Candidate current/stale identity

## What to build

Adapt the existing Evidence Policy mathematics to the Final Spec input model. Publish Candidate/Uncertain
as derived AI artifacts without touching Native Selection.

## Acceptance criteria

- [ ] Lift input is exactly the current Included Stable View Annotation set plus versioned target/dependency/policy identity.
- [ ] Excluded Views and Views without valid Stable Mask do not contribute.
- [ ] Evidence preserves observed positive/negative/uncertain semantics; unobserved is never defaulted to Rejected.
- [ ] Candidate and Uncertain are separate artifacts; Uncertain is diagnostic only.
- [ ] Out-of-scope/context Gaussians can be kept outside operation semantics according to policy rather than forced into Candidate.
- [ ] Lift publication is atomic; partial evidence/Candidate output is never exposed as Candidate Ready.
- [ ] Lift never modifies Native Selection or Native EditHistory.
- [ ] Candidate stores enough internal input revision/fingerprint identity to determine whether it matches current Included Stable Inputs, without adding DG-14 provenance UI.
- [ ] Stable Input change after successful Lift makes Candidate Stale; stale Candidate cannot execute native operations.
- [ ] Contextual toolbar exposes `Update 3D Candidate` when stale and Candidate Ready only for a current successful lift.
- [ ] Re-Lift is explicit and is not triggered automatically by Repropagate or Stable input changes.
- [ ] Candidate Ready visualization uses strong Candidate overlay; Uncertain uses distinct diagnostic overlay.

## Failure / recovery criteria

- [ ] Lifting failure preserves Views, Stable Masks, Gallery, and the last valid Candidate if one exists; failed lift does not publish a replacement Candidate.
- [ ] OOM/atomic-publication hardening is completed later in Ticket 21, but this ticket must already fail closed.

## Affected seams

- src/ai-select/candidate*
- src/ai-select/dirty-state*
- Companion evidence.py / lifting adapter
- Companion atomic lift publication
- 3D Candidate/Uncertain overlays

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Locked GPU lifting validation
- Evidence fixtures: positive/negative/unobserved/conflict

## Non-goals

- No Native Set/Add/Remove/Intersect
- No Candidate provenance/source inspector
