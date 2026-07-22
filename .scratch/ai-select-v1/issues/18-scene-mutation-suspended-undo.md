# 18 — Scene mutation Suspended state + exact Undo recovery

Status: ready-for-agent

Blocked by: 17, 01

## Final Spec mapping

- DG-17
- §72 Scene Mutation
- Typical Flow I
- MVP Phase 7 safety

## Inputs / preconditions

- CurrentTargetContext + semantic dependency token
- Scene/EditHistory mutation events
- Existing AI artifacts

## Outputs / handoff artifacts

- Suspended state
- Read-only preserved AI context
- Exact semantic Undo recovery

## What to build

Replace fail-and-restart behavior for relevant scene dependency mutations with Final Spec Suspended
semantics. Preserve artifacts read-only and auto-resume only when effective dependency identity exactly
returns to the pre-mutation semantic state.

## Acceptance criteria

- [ ] Selection-only and editor/UI-only changes do not suspend or stale AI artifacts.
- [ ] Only mutations affecting actual current AI render/geometry/Gaussian identity/target transform dependency scope suspend the context.
- [ ] Relevant mutation transitions CurrentTargetContext to Suspended without deleting Anchor/Views/Masks/Candidate/Gallery.
- [ ] Suspended context remains inspectable/read-only but cannot edit masks, add Views, Repropagate, Re-Lift, or apply Candidate.
- [ ] Scene Suspended contextual toolbar offers Undo Scene Change / Restart Current Target recovery.
- [ ] Native Undo auto-resumes only when effective TargetDependencyToken exactly matches the compatible pre-mutation semantic state.
- [ ] Recovery is based on semantic/restorable dependency equality, not merely detecting that the last action was Undo.
- [ ] Delete / Separate / Transform of target dependency suspend; exact Undo may restore only when Splat identity/membership/render/transform state matches.
- [ ] Unrelated scene edits outside actual dependency scope do not globally invalidate the target.
- [ ] Selection flags are excluded from authoritative AI render dependency identity so Candidate application cannot self-suspend.
- [ ] All async result acceptance continues to require matching targetContextId + contextRevision + dependency identity.
- [ ] v1.0 performs no partial artifact repair/remapping after incompatible mutation.

## Failure / recovery criteria

- [ ] Late result after suspend/restart is discarded.
- [ ] Undo that does not exactly restore dependency identity leaves context Suspended.

## Affected seams

- src/ai-select/target-dependency*
- src/ai-select/current-target-context*
- Scene/edit mutation events
- Native Undo/EditHistory events
- Contextual toolbar

## Validation

- npm test
- npm run lint
- npm run build
- Mutation matrix: selection/UI/transform/delete/separate/unrelated edit
- Suspend→exact Undo→resume tests
- Stale async stress

## Non-goals

- No partial RGB/contributor/mask remapping repair
