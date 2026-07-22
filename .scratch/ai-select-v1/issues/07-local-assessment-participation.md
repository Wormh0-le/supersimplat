# 07 — Local ViewAssessmentPolicy + Participation + actionable Review

Status: ready-for-agent

Blocked by: 06

## Final Spec mapping

- DG-06
- DG-19
- §29–33 Review/Participation
- MVP Phase 4 P0

## Inputs / preconditions

- AIViews with render/mask states
- Mask geometry
- Contributor support
- Propagation metadata

## Outputs / handoff artifacts

- Good/Review/Failed assessment
- Structured ReviewReason[]
- Participation authority/defaults
- Reason→Action UI mapping

## What to build

Evolve existing quality diagnostics into Final Spec local/P0 ViewAssessmentPolicy. Keep machine
assessment, user confirmation, and Lift Participation as independent dimensions.

## Acceptance criteria

- [ ] Automatic assessment produces Good / Review / Failed only from evidence available to ViewAssessmentPolicy.
- [ ] Review Reasons are structured codes produced by Companion policy; frontend does not invent backend causes.
- [ ] P0 user-visible reasons are limited to evidence-backed target-at-boundary, fragmented-mask, weak-gaussian-support, and propagation-uncertain when corresponding evidence exists.
- [ ] Multiple Review Reasons may exist and assessment exposes a deterministic Primary Reason/top actionable subset.
- [ ] Frontend maps structured reason codes to localized static recommended actions; normal UI shows actionable explanation rather than raw entropy/logits/cosine diagnostics.
- [ ] Normal UI never displays one unified uncalibrated `AI Confidence %`.
- [ ] Auto Good defaults to Included.
- [ ] Auto Review defaults to Excluded and unresolved Needs Attention.
- [ ] Failed, No Stable Mask, Mask Failed, and Render Failed are Excluded and remain distinct from valid Review.
- [ ] A valid Review mask can be Confirmed as-is, becoming User Confirmed Stable Mask with Participation=Included.
- [ ] Prompt/Brush/Clear+Manual remain available correction choices for Review.
- [ ] Explicit user Exclude resolves the user's review task; system-auto-excluded Review stays actionable until user decision.
- [ ] Automatic reassessment cannot silently revoke User Confirmed authority or secretly down-weight it in Lift.
- [ ] View source (auto-generated/user-added/replacement) does not itself determine trust or participation.
- [ ] Assessment metadata binds to the relevant RGB/Stable Mask/policy revision so stale reasons disappear after a new mask revision.

## Failure / recovery criteria

- [ ] Assessment failures fail closed without inventing unsupported semantics.
- [ ] Mask failure recovery keeps the View and exposes Retry Auto Mask / Manual Draw / Exclude.

## Affected seams

- src/ai-select/view-assessment*
- src/ai-select/participation*
- AI View selected detail
- Frontend localization/action mapping
- Companion ViewAssessmentPolicy over existing diagnostics/evidence

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run lint:locales
- P0 reason fixtures
- Participation/user-authority transition tests

## Non-goals

- No identity-drift emission
- No unified Confidence %
- No Candidate provenance
