# 18 — Scene mutation Suspended state + exact Undo recovery

Status: implemented

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

- [x] Selection-only and UI-only changes do not suspend or stale Evidence/Candidate.
- [x] Only actual current AI render/geometry/Gaussian identity/target transform dependency mutations suspend.
- [x] Suspended transition preserves Anchor/Views/Masks/Evidence/Candidate/Gallery read-only.
- [x] Suspended context cannot edit Masks, add Views, refresh Mask inference, recompute Evidence, Re-Lift, or apply Candidate.
- [x] The Suspended surface offers Undo Scene Change; the global AI Select
      lifecycle menu retains `选择另一个对象`. Restart is not reintroduced into
      the contextual 3D Toolbar.
- [x] Native Undo resumes only when effective TargetDependencyToken exactly matches the compatible pre-mutation state.
- [x] Recovery is semantic equality, not merely last-action-is-Undo.
- [x] Delete/Separate/Transform suspend when in dependency scope; unrelated edits do not globally invalidate.
- [x] Selection flags are excluded from authoritative render/Evidence dependency identity.
- [x] Async acceptance requires current context/revision/dependency plus artifact-specific identities.
- [x] v1 performs no cross-dependency partial RGB/Mask/Evidence remapping repair.

## Failure / recovery criteria

- [x] Late result after suspend/restart is discarded.
- [x] Non-exact Undo leaves context Suspended.
- [x] Restored context reuses artifacts only when all exact identities match.

## Validation

- npm test
- npm run lint
- npm run build
- Mutation matrix
- Suspend→exact Undo→resume with Evidence artifacts
- Stale async stress

## Non-goals

- No partial artifact remapping across incompatible dependency state

## Implementation record

- Effective target dependencies use semantic fingerprints of current render
  values, per-Gaussian transforms, deleted membership, content identity and
  world transform. Native selection and lock flags are explicitly excluded.
- Target-scoped editor mutation events synchronize the lifecycle immediately;
  unrelated Splats and presentation-only changes do not enter that route.
- Suspension logically cancels old request revisions while retaining Anchor,
  Gallery, Mask, Evidence and Candidate artifacts. Exact restoration mints a
  fresh request revision and reuses only the retained exact-bound products.
- The AI View Dock owns a compact read-only suspension surface with the native
  `Undo Scene Change` action. Global `选择另一个对象` ownership and the compact
  contextual 3D Toolbar remain unchanged.

## Validation record

- `npm test`: 629 browser/editor tests and 446 Companion tests passed; one
  Companion integration fixture was skipped as expected.
- `npm run lint` and `npm run lint:locales`: TypeScript/format compatibility
  passed and all eight translated locales match the 564-key English catalog.
- `npm run build`: release and service-worker bundles passed with only the
  existing dependency circularity, Sass deprecation, and Rollup `this`
  rewrite warnings.
- The mutation matrix covers visibility, transform, target pose,
  Delete/Separate membership, unrelated-Splat routing, every
  TargetDependencyToken field, and unchanged selection/UI semantics. Suspend
  → exact restoration retains Anchor Mask, Editing Mask, Stable Mask,
  Evidence identity and complete P/N/V artifacts, plus a fresh request
  identity; Generated View stale-async coverage rejects late work across the
  same transition.
- Touched-document links and manifest JSON parse successfully. This
  browser/editor lifecycle slice does not change renderer algorithms and
  therefore requires no locked-GPU validation.
