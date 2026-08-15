# 15 — Pre-apply Candidate correction + explicit Evidence-aware Re-Lift

Status: implemented (2026-08-13) — reference/debug Re-Lift vertical slice

Blocked by: 14, 13, 12, 09

## Current Final Spec mapping

- Final Spec v1.3 §§19–22, 24
- DG-15 and DG-20 as historical correction/ownership rationale where not superseded
- Historical Typical Flow G as implementation provenance

Final Spec v1.3 is the only current closure source.

## Inputs / preconditions

- Candidate Ready/Stale
- Gallery/Review/Mask/Participation controls
- Per-view Evidence artifacts and dirty identities
- Explicit Re-Lift

## Outputs / handoff artifacts

- Correction flow
- Candidate Stale transitions
- Evidence reuse/recompute plan
- Updated atomic Candidate

## What to build

Implement structural correction before Candidate application. Users change observations and explicitly Re-Lift. Re-Lift reuses exact matching per-view Evidence and recomputes only missing/stale artifacts before aggregation/classification.

## Acceptance criteria

- [x] Candidate Ready exposes `Fix AI Result`.
- [x] Correction preserves current Candidate as reference while returning to View/Mask/Participation controls.
- [x] Browsing or editing an unconfirmed Editing Mask does not stale Candidate or Evidence.
- [x] Confirmed Stable Mask, Camera/RGB revision, Evidence Policy/Working Set change, or Participation change updates exact dirty/stale state.
- [x] Stale Candidate cannot execute Set/Add/Remove/Intersect.
- [x] Candidate Stale toolbar exposes `Update 3D Candidate`.
- [x] Update resolves exact Included Stable View set, reuses matching per-view Evidence, recomputes stale/missing P/N/V, aggregates, classifies, and publishes atomically.
- [x] Excluded View artifacts may remain cached but do not contribute.
- [x] Failed Re-Lift does not promote a partial artifact or stale Candidate.
- [x] Guidance may suggest Fix Mask / Exclude / Generate More / Add View but never invents DG-14 provenance.
- [x] Candidate cannot be directly 3D painted/patched/merged.
- [x] Small final edits remain native-selection work after application.

## Failure / recovery criteria

- [x] Failed Evidence recomputation or aggregation leaves previous Candidate stale/reference only.
- [x] Correction exit preserves Stable inputs unless explicit Restart occurs.

## Implementation evidence

- Browser-owned `AISelectCandidateCorrectionController` retains the inspectable
  Candidate, plans exact per-View reuse/recompute, rejects an input race before
  publication, and publishes only a complete replacement.
- `POST /ai-select/candidate-re-lifts` is a strict cross-runtime boundary. It
  accepts the packed full-scene Render Working Set, exact Included Stable View
  inputs, optional current Evidence, and returns per-View P/N/V plus one bound
  reference Candidate.
- Companion orchestration ignores Excluded Views for production/aggregation,
  recomputes stale or missing artifacts, and constructs the Candidate only
  after all Included Views succeed.
- The route validates the registered full-scene Render Working Set and locked
  reference backend/runtime identity before either cache reuse or recompute,
  and occupies the Companion's single global AI operation slot throughout the
  transaction.
- The Dock exposes `Fix AI Result` and `Update 3D Candidate`. Ticket 16 remains
  the owner of native Set/Add/Remove/Intersect; reference Candidates remain
  application-blocked.
- Formal Lift Readiness stays withheld from this live reference slice because
  no target-local Core Target Working Set builder exists yet. Whole-scene IDs
  remain a conservative reference Evidence/classification scope but are not
  presented as target Observation Coverage.
- This is reference/debug Contributor work. It does not implement or validate
  Ticket 20's production same-decision Direct Evidence kernel.
- The live reference path keeps complete Contributor tensors typed through
  validation and performs bounded, vectorized CPU accumulation only for
  non-neutral Mask regions. It does not truncate contributors or change the
  reference Evidence policy. Browser transport bounds a non-responsive
  Re-Lift at 120 seconds, publishes the failure on every pending Evidence
  record, and preserves the previous inspectable Candidate.
- The Dock's bottom action well is height-bounded rather than fixed-height;
  action groups use responsive button grids and scroll only after reaching the
  bound, so wrapped labels do not squeeze or clip lifecycle controls.

## Post-closure presentation follow-up

Ticket 15 remains implemented as the owner of pre-apply Correction and explicit
Evidence-aware Re-Lift semantics. Ticket 16A owns the later cross-surface
`Back to Candidate` integration required by the accepted Toolbar/Dock design:
it exits Correction without publishing the retained editing draft, restores
application when Stable inputs are unchanged, and otherwise keeps Candidate
stale until explicit update. This follow-up does not reopen or replace Ticket
15's implemented Re-Lift core.

## Validation

- npm test
- npm run lint
- npm run lint:locales
- npm run build
- Per-view Evidence reuse/invalidation tests
- browse/editing-no-stale versus Stable-input-stale workflows
- failed recompute preserves prior Candidate

## Non-goals

- No Applied Undo-and-Fix
- No Candidate provenance/source inspector
- No production Direct Evidence kernel
