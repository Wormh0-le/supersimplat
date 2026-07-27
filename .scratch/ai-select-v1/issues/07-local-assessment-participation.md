# 07 — Local ViewAssessmentPolicy + Participation + actionable Review

Status: implemented — 2026-07-27

Blocked by: 06

## Final Spec mapping

- Final Spec v1.1 §§13, 23, 26
- DG-06, DG-19, DG-20
- MVP Phase 4 P0

## Inputs / preconditions

- AIViews with independent render/mask/evidence states
- Mask geometry
- Propagation metadata
- Versioned low-cost Gaussian support/visibility diagnostics

## Outputs / handoff artifacts

- Good/Review/Failed assessment
- Structured ReviewReason[]
- Participation authority/defaults
- Reason→Action UI mapping

## What to build

Implement P0 local assessment without requiring complete per-pixel Contributor. Use Mask geometry, propagation metadata, and available versioned support/visibility diagnostics. Formal P/N/V may refine assessment later but is not a prerequisite for ordinary Review state.

## Acceptance criteria

- [x] Assessment produces Good / Review / Failed only from available version-bound evidence.
- [x] Review Reasons are Companion-owned structured codes; frontend does not invent causes.
- [x] P0 reasons are limited to target-at-boundary, fragmented-mask, weak-gaussian-support, and propagation-uncertain when supported.
- [x] `weak-gaussian-support` uses a declared support/visibility diagnostic or later P/N/V; it is not inferred from complete Contributor availability alone.
- [x] Missing support evidence yields no fabricated weak-support reason.
- [x] Multiple reasons and deterministic primary/actionable subset are supported.
- [x] Frontend maps reason codes to localized static actions and does not expose raw algorithm diagnostics as user claims.
- [x] No unified uncalibrated AI Confidence percentage is shown.
- [x] Auto Good defaults Included; Auto Review defaults Excluded; Failed/no Stable Mask/Render Failed default Excluded.
- [x] Evidence Failed remains distinct from Render Failed and may be actionable only when Evidence was actually requested.
- [x] User may Confirm Review as-is, producing User Confirmed Stable Mask + Included.
- [x] Prompt/Brush/Clear+Manual/Exclude remain correction options.
- [x] User-confirmed authority cannot be silently revoked or down-weighted by reassessment.
- [x] View source does not determine trust.
- [x] Assessment binds RGB/Stable Mask/policy/support identity; stale reasons disappear after revision change.

## Failure / recovery criteria

- [x] Assessment failure fails closed without inventing semantics and does not corrupt Participation.
- [x] Mask failure preserves View/RGB and exposes retry/manual/exclude.

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run lint:locales
- P0 reason fixtures with and without support diagnostics
- Participation/user-authority transitions

## Non-goals

- No cross-view reason
- No identity-drift
- No Candidate provenance

## Implementation record

- Companion owns `local-view-assessment/v1`, deterministic P0 reason ordering, actionable reason selection, geometry/propagation assessment, and the optional versioned Gaussian-support probe.
- Support diagnostics carry a concrete `supportDiagnosticId` bound to scene, View, RGB, Stable Mask, and observed-Gaussian count. Spatial-scene Generated Views omit support assessment until a matching complete-scene diagnostic is available, so missing evidence cannot become a weak-support claim.
- Browser validation fails closed on assessment/status/reason/identity/count contradictions. Automatic Good/Review/Failed defaults are centralized and independent from View source.
- Confirm Review as-is publishes a User Confirmed Stable Mask and Included participation. Subsequent automatic reassessment cannot replace that authority, and reasons bound to a replaced Stable Mask are not exposed.
- AI View cards expose separate RGB, Mask Quality, Participation, and Evidence states; localized P0 reasons and static correction actions; Retry Mask; Confirm as-is; and Include/Exclude. Generated-view Prompt/Brush/Clear+Manual correction is handed off through the selected-view Mask authoring surface rather than duplicating an editor in the card.
- `CONTEXT.md` and the Companion README record the assessment and publication contracts. Final Spec, ADRs, runtime lock, Evidence Policy, and calibration were not changed.

## Validation record

Validated on 2026-07-27:

- `npm test`: 277 TypeScript/editor tests and 240 Companion tests passed.
- `npm run lint`: passed, including Prettier/ESLint compatibility for 181 TypeScript source files.
- `npm run lint:locales`: all 8 translated locales match the 420-key English source.
- `npm run build`: passed; existing `mediabunny` circular-dependency and legacy Sass warnings remain.
- Narrow P0 reason, missing/present support diagnostic, contradictory identity/count, participation, stable-revision, failure-recovery, and user-authority tests passed.

Production GPU/SAM browser validation did not run in this implementation environment. This slice is Companion policy, protocol validation, editor lifecycle, and UI work; it neither claims nor changes the production same-decision P/N/V Evidence path. Complete Contributor remains unchanged as a reference/debug backend.
