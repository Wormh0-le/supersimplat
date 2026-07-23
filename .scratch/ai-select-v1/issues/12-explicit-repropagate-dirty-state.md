# 12 — Explicit Repropagate + Evidence Dirty / Candidate Stale model

Status: ready-for-agent — v2.2 re-audited

Blocked by: 09, 07, 05

## Final Spec mapping

- Final Spec v1.1 §§11, 18, 24
- DG-10, DG-20
- MVP Phase 4

## Inputs / preconditions

- Stable Masks
- Participation
- AIView Camera/RGB identity
- Current target/reference identity
- View registry

## Outputs / handoff artifacts

- propagationDirty
- evidenceDirtyViewIds
- liftDirty
- candidateStale
- Explicit Update Multi-view Masks

## What to build

Implement explicit recompute semantics including per-view Evidence invalidation. Repropagate remains explicit and never auto-Re-Lifts. Stable input changes mark only the dependent Evidence/Candidate state dirty.

## Acceptance criteria

- [ ] Domain exposes or derives propagationDirty, evidenceDirtyViewIds, liftDirty, candidateStale, and contextSuspended.
- [ ] Editing an unconfirmed Editing Mask changes none of those formal states.
- [ ] Confirming a normal View Stable Mask marks that View Evidence dirty and Lift dirty, but not propagation.
- [ ] Confirming changed Anchor/reference Stable Mask marks propagation dirty, Anchor Evidence dirty, and Lift dirty.
- [ ] Excluding an Included View preserves its artifact for possible reuse but marks Lift dirty.
- [ ] Including a View with Stable Mask marks Lift dirty and its Evidence dirty when no exact matching artifact exists.
- [ ] Adding a View with no Stable Mask changes neither Evidence nor Lift dirtiness.
- [ ] Publishing a new CameraBinding/RGB revision marks that View Evidence dirty and Lift dirty.
- [ ] Gallery/frustum browsing changes no dirty state.
- [ ] Propagation Dirty exposes `Update Multi-view Masks`.
- [ ] Repropagate binds current reference identity and publishes Mask revisions atomically.
- [ ] Repropagate may refresh assessment/Participation/readiness inputs but never auto-produces Evidence or Candidate.
- [ ] Late results with stale target/reference/dependency identity are discarded.
- [ ] Repropagate failure preserves prior Stable Masks and matching Evidence/Candidate state.
- [ ] Technical failure remains distinct from valid Review.

## Failure / recovery criteria

- [ ] No partial proposed Mask or Evidence becomes stable.
- [ ] Cancellation/restart correctness relies on binding rejection, not cancellation success.

## Validation

- npm test
- npm run test:companion
- npm run lint
- Dependency-table tests matching Final Spec v1.1 §24
- Mask/RGB/Participation → Evidence dirty transition tests
- Stale-result/cancel tests

## Non-goals

- No automatic Re-Lift
- No Evidence computation or Candidate implementation