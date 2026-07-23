# 18 — Scene mutation Suspended state + exact Undo recovery

Status: ready-for-agent — v2.2 re-audited

Blocked by: 17, 01

## Final Spec mapping

- Final Spec v1.1 §29
- DG-17, DG-20
- Typical Flow I
- MVP Phase 7 safety

## Inputs / preconditions

- CurrentTargetContext + semantic dependency token
- Scene/EditHistory mutation events
- Anchor/View/Mask/Evidence/Candidate artifacts

## Outputs / handoff artifacts

- Suspended state
- Read-only preserved AI context
- Exact semantic Undo recovery

## What to build

Suspend on actual render/geometry/identity dependency mutation. Preserve artifacts for inspection, but make dependent RGB/Evidence/Candidate inapplicable until exact semantic dependency restoration.

## Acceptance criteria

- [ ] Selection-only and UI-only changes do not suspend or stale Evidence/Candidate.
- [ ] Only actual current AI render/geometry/Gaussian identity/target transform dependency mutations suspend.
- [ ] Suspended transition preserves Anchor/Views/Masks/Evidence/Candidate/Gallery read-only.
- [ ] Suspended context cannot edit Masks, add Views, Repropagate, recompute Evidence, Re-Lift, or apply Candidate.
- [ ] Toolbar offers Undo Scene Change / Restart Current Target.
- [ ] Native Undo resumes only when effective TargetDependencyToken exactly matches the compatible pre-mutation state.
- [ ] Recovery is semantic equality, not merely last-action-is-Undo.
- [ ] Delete/Separate/Transform suspend when in dependency scope; unrelated edits do not globally invalidate.
- [ ] Selection flags are excluded from authoritative render/Evidence dependency identity.
- [ ] Async acceptance requires current context/revision/dependency plus artifact-specific identities.
- [ ] v1.1 performs no cross-dependency partial RGB/Mask/Evidence remapping repair.

## Failure / recovery criteria

- [ ] Late result after suspend/restart is discarded.
- [ ] Non-exact Undo leaves context Suspended.
- [ ] Restored context reuses artifacts only when all exact identities match.

## Validation

- npm test
- npm run lint
- npm run build
- Mutation matrix
- Suspend→exact Undo→resume with Evidence artifacts
- Stale async stress

## Non-goals

- No partial artifact remapping across incompatible dependency state