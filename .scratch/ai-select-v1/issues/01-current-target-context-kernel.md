# 01 — CurrentTargetContext lifecycle kernel

Status: ready-for-agent

Blocked by: none

## Final Spec mapping

- §5 Current Target Context
- DG-16
- DG-17 async/dependency foundation
- MVP Phase 0–1

## Inputs / preconditions

- Selected visible Target Splat identity
- Current effective Target dependency identity

## Outputs / handoff artifacts

- CurrentTargetContext state
- TargetDependencyToken
- AIRequestBinding
- Request acceptance/rejection semantics

## What to build

Create the minimal editor-side Final Spec domain kernel under a dedicated `src/ai-select/` seam.
This is the only intentional prefactoring ticket. It establishes lifecycle and stale-result correctness
without wiring the new product flow into the old ObjectSelectionSession.

## Acceptance criteria

- [ ] Create a dedicated `src/ai-select/` domain seam rather than extending legacy ObjectSelectionSession with the new lifecycle.
- [ ] Represent exactly one active user-visible Current Target Context at a time; do not introduce a persistent AI session stack.
- [ ] CurrentTargetContext has a unique `targetContextId`, monotonic context revision, target identity, dependency token, and explicit `active | suspended | disposed` lifecycle.
- [ ] TargetDependencyToken structurally represents the effective target render / geometry / Gaussian identity / world-transform dependency identity required by later tickets.
- [ ] AIRequestBinding binds at least `targetContextId + contextRevision + dependencyToken`.
- [ ] A result can publish only while its request binding still matches the current active context and effective dependency identity.
- [ ] Context revision changes reject older results even when transport cancellation fails.
- [ ] A dependency mismatch can suspend the context; exact semantic dependency restoration can resume a suspended context.
- [ ] A disposed context can never resume, even when an old dependency state later reappears.
- [ ] Restart/disposal primitives never mutate Native Selection or Native EditHistory.
- [ ] Do not pre-build future AIViewStore, MaskStore, CandidateStore, PlannerService, or other speculative architecture.

## Failure / recovery criteria

- [ ] Cancellation failure must not compromise correctness; old results remain rejected by binding checks.
- [ ] Invalid/empty dependency identities fail closed rather than accepting ambiguous results.

## Affected seams

- src/ai-select/
- src/scene-snapshot.ts / existing identity types as references
- TypeScript test harness

## Validation

- npm test
- npm run lint
- Focused tests: create, revise, stale binding, wrong context ID, suspend, exact resume, disposed-no-resume

## Non-goals

- No UI wiring
- No Companion protocol changes
- No renderer/SAM work
- No AIView/Mask/Candidate implementation
