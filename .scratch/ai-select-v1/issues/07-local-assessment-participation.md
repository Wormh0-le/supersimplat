# 07 — Local ViewAssessmentPolicy + Participation + actionable Review

Status: ready-for-agent — v2.2 re-audited

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

- [ ] Assessment produces Good / Review / Failed only from available version-bound evidence.
- [ ] Review Reasons are Companion-owned structured codes; frontend does not invent causes.
- [ ] P0 reasons are limited to target-at-boundary, fragmented-mask, weak-gaussian-support, and propagation-uncertain when supported.
- [ ] `weak-gaussian-support` uses a declared support/visibility diagnostic or later P/N/V; it is not inferred from complete Contributor availability alone.
- [ ] Missing support evidence yields no fabricated weak-support reason.
- [ ] Multiple reasons and deterministic primary/actionable subset are supported.
- [ ] Frontend maps reason codes to localized static actions and does not expose raw algorithm diagnostics as user claims.
- [ ] No unified uncalibrated AI Confidence percentage is shown.
- [ ] Auto Good defaults Included; Auto Review defaults Excluded; Failed/no Stable Mask/Render Failed default Excluded.
- [ ] Evidence Failed remains distinct from Render Failed and may be actionable only when Evidence was actually requested.
- [ ] User may Confirm Review as-is, producing User Confirmed Stable Mask + Included.
- [ ] Prompt/Brush/Clear+Manual/Exclude remain correction options.
- [ ] User-confirmed authority cannot be silently revoked or down-weighted by reassessment.
- [ ] View source does not determine trust.
- [ ] Assessment binds RGB/Stable Mask/policy/support identity; stale reasons disappear after revision change.

## Failure / recovery criteria

- [ ] Assessment failure fails closed without inventing semantics and does not corrupt Participation.
- [ ] Mask failure preserves View/RGB and exposes retry/manual/exclude.

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