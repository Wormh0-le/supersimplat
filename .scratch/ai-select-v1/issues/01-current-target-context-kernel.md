# 01 — CurrentTargetContext lifecycle kernel

Status: ready-for-agent — v2.2 re-audited

Blocked by: none

## Final Spec mapping

- Final Spec v1.1 §§4, 7, 18, 24, 29 and inherited v1.0 Current Target Context rules
- DG-16, DG-17, DG-20 identity foundation
- MVP Phase 0–1

## Inputs / preconditions

- Selected visible Target Splat identity
- Current effective target dependency identity

## Outputs / handoff artifacts

- CurrentTargetContext state
- TargetDependencyToken
- AIRequestBinding
- Request acceptance/rejection primitives
- Extensible artifact-specific identity seam

## What to build

Create the minimal editor-side domain kernel under `src/ai-select/`. Establish lifecycle and stale-result correctness without wiring new behavior into legacy ObjectSelectionSession or pre-building future stores.

## Acceptance criteria

- [ ] Use a dedicated `src/ai-select/` seam.
- [ ] Represent exactly one active user-visible Current Target Context; no persistent target-session stack.
- [ ] Context has targetContextId, monotonic revision, target identity, dependency token, and active/suspended/disposed lifecycle.
- [ ] TargetDependencyToken represents effective render, geometry, Gaussian identity/membership, and transform dependencies required downstream.
- [ ] AIRequestBinding binds at least targetContextId + contextRevision + dependencyToken.
- [ ] Result publication requires a current matching active context and effective dependency identity.
- [ ] Context revision rejects older results even when cancellation fails.
- [ ] The binding model can be extended by later tickets with Camera/RGB/Mask/Policy/Working-Set identities without weakening the base check.
- [ ] Dependency mismatch may suspend; exact semantic restoration may resume; disposed context never resumes.
- [ ] Restart/disposal primitives never mutate Native Selection or Native EditHistory.
- [ ] Do not pre-build speculative AIView/Mask/Evidence/Candidate/Planner stores.

## Failure / recovery criteria

- [ ] Cancellation failure cannot compromise correctness.
- [ ] Invalid/empty dependency identity fails closed.

## Validation

- npm test
- npm run lint
- Focused create/revise/stale/wrong-context/suspend/exact-resume/disposed-no-resume tests

## Non-goals

- No UI wiring
- No Companion protocol changes
- No renderer/SAM/Evidence implementation
- No AIView/Mask/Candidate implementation