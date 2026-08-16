# 18 — Scene mutation Suspended state + exact Undo recovery

Status: ready-for-agent — Final Spec v1.3 mapped

Blocked by: 17, 01

## Current Final Spec mapping

- Final Spec v1.3 §§4, 19, 22, 24
- DG-17 and DG-20 as historical suspension/ownership rationale where not superseded
- Historical Typical Flow I and MVP Phase 7 safety as implementation provenance

Final Spec v1.3 is the only current closure source.

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
- [ ] Suspended context cannot edit Masks, add Views, refresh Mask inference, recompute Evidence, Re-Lift, or apply Candidate.
- [ ] The Suspended surface offers Undo Scene Change; the global AI Select
      lifecycle menu retains `选择另一个对象`. Restart is not reintroduced into
      the contextual 3D Toolbar.
- [ ] Native Undo resumes only when effective TargetDependencyToken exactly matches the compatible pre-mutation state.
- [ ] Recovery is semantic equality, not merely last-action-is-Undo.
- [ ] Delete/Separate/Transform suspend when in dependency scope; unrelated edits do not globally invalidate.
- [ ] Selection flags are excluded from authoritative render/Evidence dependency identity.
- [ ] Async acceptance requires current context/revision/dependency plus artifact-specific identities.
- [ ] v1 performs no cross-dependency partial RGB/Mask/Evidence remapping repair.

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
