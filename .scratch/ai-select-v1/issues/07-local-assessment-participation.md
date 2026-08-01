# 07 — Local MaskReviewPolicy + Participation

Status: implemented — `local-view-assessment/v2` Mask Review + centralized Participation defaults

Blocked by: 06

Blocks: 07A, 08B

Runs in parallel with: 04C

## Implementation record

- Companion `view_assessment.py` is the v1.3 Mask Review policy: reasons
  `prompt-inconsistent`, `target-materially-clipped`, `severely-fragmented`,
  `box-spill-or-neighbour-leak`, `empty-or-degenerate-mask`, ordered
  deterministically with actionable reasons capped at two. Boundary Review
  requires ≥8 contact pixels and ≥0.2 contact ratio; fragmentation requires
  ≥16 disconnected pixels and ≥10% disconnected mass; Box spill is measured
  outside the Box expanded by 2px and flagged only when gross (≥16px and
  ≥20%); empty/degenerate (<4px)/full-frame (≥98%) Masks fail with one
  structured reason. Point/Box consistency is evaluated only when that
  Prompt family exists; the current Generated View flow supplies synthesized
  include points only, so Negative Point/Box reasons stay unevaluated there.
- `propagation-uncertain` and the Propagation/Support diagnostics are deleted
  from the policy, the wire identity, the editor schema, and the UI;
  `weak-gaussian-support` moves to Ticket 13 Lift Readiness.
- Editor `view-assessment.ts` validates the v2 schema fail-closed (retired v1
  reasons/identity fields are rejected, never rebound) and requires every
  Review reason to be backed by its measured diagnostic.
- Participation defaults are centralized in `defaultViewParticipation`
  (`src/ai-select/view-assessment.ts`), independent from View role:
  automatic Good → Included; automatic Review/Failed/unavailable → Excluded;
  User Confirmed → Included unless the user explicitly excludes.
- Mask production failure preserves the prior Stable Mask, its assessment,
  and Participation authority (`failViewMask` no longer revokes them);
  `produceViewMask` keeps the User Confirmed early-return guard.

## Follow-up for Ticket 12

The current flow never re-runs automatic Mask production over a View that
already has a Stable Mask, so this is latent today: a successful automatic
re-publication applies the automatic Participation default, which would
overwrite an explicit user Exclude on an Auto Good Stable Mask. Ticket 12's
dirty/refresh lifecycle must carry Participation authority across refresh
rather than re-applying defaults.

## Final Spec mapping

- Final Spec v1.3 §§7, 13–15, 18–19, 24–26
- ADR 0016

## Purpose

Keep low-cost per-View Mask usability review and Participation, while removing tracker- and Gaussian-readiness semantics from Mask quality.

## Inputs

- exact View RGB and Mask identity;
- current instance Prompt artifact where model inference produced the Mask;
- Mask geometry;
- source authority: automatic or User Confirmed;
- optional declared Box/Point consistency diagnostics.

## Outputs

```text
Good / Review / Failed
+ structured MaskReviewReason[]
+ default Participation
```

## Current v1 reasons

At minimum:

```text
prompt-inconsistent
target-materially-clipped
severely-fragmented
box-spill-or-neighbour-leak
empty-or-degenerate-mask
```

Rules:

- reasons are deterministic and versioned;
- boundary review uses a meaningful ratio/margin, not any one-pixel contact;
- fragmentation requires material disconnected mass, not merely multiple tiny components;
- Point/Box inconsistency is evaluated only when the Prompt family exists;
- no unified AI Confidence percentage is shown.

## Removed/moved reasons

- `propagation-uncertain` is deleted from the ordinary v1 path because there is no tracker propagation.
- `weak-gaussian-support` moves to Ticket 13 Lift Readiness and is not a Mask-quality claim.
- missing Gaussian support cannot make an otherwise valid Mask Review or Failed.

## Participation defaults

```text
Auto Good Stable Mask   → Included
Auto Review Stable Mask → Excluded
Failed / unavailable    → Excluded
User Confirmed Stable   → Included unless user explicitly excludes
```

User-confirmed authority cannot be silently revoked by later automatic review.

## Acceptance criteria

- [x] Good/Review/Failed derives only from exact current Mask/Prompt geometry and policy identity.
- [x] Prompt inconsistency, clipping, severe fragmentation and gross Box spill have structured reasons.
- [x] any-boundary-contact no longer automatically causes Review.
- [x] `propagation-uncertain` is absent from current schemas/UI.
- [x] `weak-gaussian-support` is absent from MaskReviewPolicy and owned by Ticket 13.
- [x] missing optional diagnostics never fabricate a reason.
- [x] automatic and User Confirmed authority remain distinct.
- [x] Participation defaults are centralized and independent from View role.
- [x] failure preserves prior Stable Mask and Participation authority.

## Validation

- geometry threshold fixtures;
- Prompt consistency fixtures;
- thin-object and image-edge fixtures;
- moved/deleted reason schema rejection;
- Participation and User Confirmed authority regressions;
- repository test/lint/locales/build.

## Non-goals

- No candidate choice or proposal ranking.
- No cross-view assessment.
- No P/N/V or Lift Readiness calculation.
- No tracker confidence.
