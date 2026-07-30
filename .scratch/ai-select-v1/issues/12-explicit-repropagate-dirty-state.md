# 12 — Explicit Mask refresh + Evidence Dirty / Candidate Stale model

Status: blocked — waits for 08B and 09

Blocked by: 08B, 09, 07, 05

## Final Spec mapping

- Final Spec v1.2 §§16–18, 21, 27–29
- DG-26 Decisions 5 and 8

## Inputs / preconditions

- Stable Masks and Participation;
- AIView Camera/RGB identity;
- Current target identity;
- View registry;
- `VisibleTargetSupportArtifact` identity;
- `TargetBootstrapArtifact` identity;
- immutable `SparseKeyViewPlanSegment` identity;
- `KeyViewPromptArtifact` identity;
- acquisition backend descriptor/bundle identity;
- acquisition attempt/fallback identity;
- ProposalSet/Decision/Assessment/publication identities;
- optional future sequence/reference identity only when an adopted backend implements it.

## Outputs / handoff artifacts

- `promptSynthesisDirtyViewIds`;
- `maskAcquisitionDirtyViewIds`;
- optional future `propagationDirty`;
- `evidenceDirtyViewIds`;
- `liftDirty`;
- `candidateStale`;
- explicit per-view `Regenerate Prompts` where needed;
- explicit per-view `Refresh Auto Mask`;
- optional `Update Multi-view Masks` only under an adopted propagation capability.

## What to build

Implement explicit recompute semantics for the layered route-B pipeline:

```text
support/bootstrap/segment/View change
→ Prompt artifact dirty
→ acquisition dirty

Stable Mask / Participation / Camera change
→ per-view Evidence dirty
→ Lift dirty
→ Candidate stale
```

No refresh action automatically Re-Lifts.

## Acceptance criteria

### Generic dirty-state semantics

- [ ] Domain exposes/derives Prompt synthesis dirty, Mask acquisition dirty, optional propagation dirty, Evidence dirty, Lift dirty, Candidate stale, and context Suspended states.
- [ ] Editing an unconfirmed Mask changes none of the formal Evidence/Candidate states.
- [ ] Confirming a normal View Stable Mask marks only that View Evidence dirty and Lift dirty.
- [ ] Confirming changed Anchor Stable Mask invalidates visible support, bootstrap, planner segments, dependent Prompt/acquisition work, Anchor Evidence, and Lift.
- [ ] Replacing `VisibleTargetSupportArtifact` invalidates dependent bootstrap, plan segments, Prompt artifacts and acquisition attempts.
- [ ] Replacing bootstrap or segment invalidates only artifacts that bind the replaced digest.
- [ ] Excluding an Included View preserves artifacts and marks Lift dirty.
- [ ] Including a View with Stable Mask marks Lift dirty and Evidence dirty when no exact artifact exists.
- [ ] Adding a View with no Stable Mask changes neither Evidence nor Lift dirtiness.
- [ ] New CameraBinding/RGB revision marks that View Prompt/acquisition/Evidence dirty and Lift dirty.
- [ ] Gallery/frustum browsing changes no dirty state.
- [ ] Generate More appends a segment without dirtying prior completed View artifacts.

### Prompt regeneration

- [ ] `Regenerate Prompts` consumes exact support/bootstrap/segment/View/RGB/capability/policy identity.
- [ ] Prompt regeneration creates a new immutable Prompt artifact and does not run SAM automatically unless the user invokes the combined Refresh action.
- [ ] Reusing an exact current Prompt artifact for a new SAM Retry is allowed.
- [ ] Prompt regeneration never overwrites Stable Mask or Evidence.

### Default per-view refresh

- [ ] `Refresh Auto Mask` uses the current exact Prompt artifact or explicitly regenerates it under a declared combined policy.
- [ ] Refresh resolves the backend through `MaskAcquisitionBackendRegistry`.
- [ ] Refresh creates a new acquisition attempt and never mutates the old attempt in place.
- [ ] Same-attempt replay may be idempotent; explicit Retry creates a real new attempt.
- [ ] Refresh affects only the selected View unless a future adopted backend declares wider dependencies.
- [ ] Provider result traverses ProposalSet → Decision → Assessment → Publication; refresh does not bypass layers.
- [ ] Ambiguous refresh retains ProposalSet and publishes no arbitrary Stable Mask.
- [ ] A refreshed automatic result never silently overwrites a current User Confirmed Stable Mask.
- [ ] Successful Stable replacement marks only matching per-view Evidence dirty and Lift dirty.
- [ ] Failure preserves prior Stable Mask and matching Evidence/Candidate state.
- [ ] Late results with stale target/support/bootstrap/segment/View/RGB/Prompt/backend/attempt identity are discarded.

### Route-A fallback lifecycle

- [ ] Automatic fallback is permitted only for the Final Spec v1.2 technical/capability reason set.
- [ ] Ambiguous, Review, contamination, clipping, and fragmentation never mark the View fallback-eligible.
- [ ] Fallback creates a separate attempt bound to `fallbackOfAttemptId` and reason.
- [ ] Route-B failure record remains inspectable after a route-A result.
- [ ] Route-A result follows the same Decision/Assessment/Publication and dirty rules.

### Correction semantics

- [ ] Confirming a per-view manual correction publishes a Stable Mask and dirties only that View Evidence/Lift.
- [ ] Confirming a correction does not automatically create tracker memory or dirty unrelated Views.
- [ ] If a future tracker/hybrid capability exists, `Use as Tracking Reference` is a separate explicit action.
- [ ] Only that explicit action may create/replace a CorrectionReference and set `propagationDirty=true`.

### Optional propagation

- [ ] `propagationDirty` and `Update Multi-view Masks` are absent/disabled when no sequence backend exists.
- [ ] If later enabled, Update consumes exact current Anchor, references, sequence plan, backend/runtime/policy identity.
- [ ] Repropagation creates a new bound run and never mutates an old run.
- [ ] Full/range/segment propagation modes are explicit policy choices.
- [ ] Repropagation never automatically produces Evidence or Candidate.
- [ ] Failure preserves prior Stable Masks and matching Evidence/Candidate.

### Evidence/Candidate lifecycle

- [ ] Only confirmed Stable Mask/Participation/Camera changes invalidate formal per-view Evidence.
- [ ] Prompt, ProposalSet, Decision, model/backend scores, fallback status, and optional tracker confidence are not P/N/V.
- [ ] No Prompt regeneration, Mask refresh, fallback, or optional propagation automatically Re-Lifts.

## Failure / recovery criteria

- No partial Prompt/Proposal/Decision/Mask/Evidence becomes current.
- Cancellation/restart correctness relies on binding rejection, not cancellation success.
- Acquisition OOM/unavailable preserves previous Stable Masks and offers eligible fallback/manual/exclude recovery.
- Ambiguous remains Review state, not a technical failure.
- Stale support/bootstrap/segment/View/RGB/Prompt/backend result cannot attach to a newer revision.
- Unsupported sequence/reference call returns structured capability failure without dirty-state mutation.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- dependency-table tests matching Final Spec v1.2 §21
- support/bootstrap/segment/Prompt dirty propagation tests
- Prompt-only regeneration tests
- per-view Refresh attempt/replay/stale-result tests
- ambiguous-no-Stable regression
- technical fallback eligibility matrix
- correction Confirm without propagation-dirty regression
- optional reference/repropagate tests only under capability fixture
- failure preserving prior Stable/Evidence/Candidate
- Generate More append-only no-dirty regression

## Non-goals

- No acquisition backend implementation; Ticket 08B owns it.
- No Prompt synthesis implementation; Ticket 08B owns it.
- No mandatory tracker or repropagation action.
- No automatic Re-Lift.
- No Evidence computation or Candidate implementation.
- No continuous refresh while Paint/Prompt editing.
