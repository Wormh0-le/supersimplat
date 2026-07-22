# 12 — Explicit Repropagate + Dirty / Stale state model

Status: ready-for-agent

Blocked by: 09, 07, 05

## Final Spec mapping

- DG-10
- §36–43 Explicit Recompute
- MVP Phase 4 Repropagate

## Inputs / preconditions

- Stable masks
- Participation
- Current target/reference identity
- View registry

## Outputs / handoff artifacts

- propagationDirty
- liftDirty
- candidateStale
- Explicit Update Multi-view Masks

## What to build

Introduce explicit recompute semantics before Candidate application. Reference/Anchor Stable Mask
changes may dirty propagation; Repropagate is explicit, publishes new proposed/stable results atomically,
refreshes assessment/participation/readiness inputs, and never auto Re-Lifts.

## Acceptance criteria

- [ ] Domain exposes or derives propagationDirty, liftDirty, candidateStale, and contextSuspended with Final Spec meanings.
- [ ] Editing an unconfirmed Editing Mask does not dirty propagation/lift and does not stale Candidate.
- [ ] Confirming a normal Generated/User View Stable Mask dirties Lift but not propagation.
- [ ] Confirming a changed Anchor/reference Stable Mask sets propagationDirty and liftDirty.
- [ ] Exclude Included View or Include a View with Stable Mask dirties Lift without dirtying propagation.
- [ ] Adding a View with no Stable Mask changes neither propagation nor lift dirtiness.
- [ ] Gallery/frustum browsing changes neither propagation nor lift dirtiness.
- [ ] When propagationDirty is true, contextual toolbar shows `Update Multi-view Masks` as the required next step.
- [ ] `Update Multi-view Masks` is an explicit operation bound to the current stable reference input/revision.
- [ ] Repropagate may produce new Good/Review/Failed outcomes and refresh Participation/readiness inputs.
- [ ] Repropagate completion never auto Re-Lifts or publishes a new Candidate.
- [ ] Late Repropagate results with stale target/reference/dependency bindings are discarded.
- [ ] Repropagate failure preserves the previous Stable Masks and does not publish partial/proposed incomplete masks.
- [ ] Technical propagation failure remains distinct from a valid Review result.

## Failure / recovery criteria

- [ ] Repropagate failure keeps old Stable Masks and current Candidate state; no partial new mask set becomes stable.
- [ ] Cancellation/restart during propagation relies on request binding rejection, not cancellation success.

## Affected seams

- src/ai-select/dirty-state*
- src/ai-select/mask*
- Contextual toolbar
- Companion propagation orchestration over SAM runtime

## Validation

- npm test
- npm run test:companion
- npm run lint
- Dependency-table tests matching Final Spec §40
- Stale-result/cancel tests

## Non-goals

- No automatic Re-Lift
- No Candidate implementation in this ticket
