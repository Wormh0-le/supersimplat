# 07 — Local MaskReviewPolicy + Participation

Status: ready-for-agent — v1.3 policy correction may run in parallel with Ticket 04C

Blocked by: 06

Blocks: 07A, 08B

Runs in parallel with: 04C

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

- [ ] Good/Review/Failed derives only from exact current Mask/Prompt geometry and policy identity.
- [ ] Prompt inconsistency, clipping, severe fragmentation and gross Box spill have structured reasons.
- [ ] any-boundary-contact no longer automatically causes Review.
- [ ] `propagation-uncertain` is absent from current schemas/UI.
- [ ] `weak-gaussian-support` is absent from MaskReviewPolicy and owned by Ticket 13.
- [ ] missing optional diagnostics never fabricate a reason.
- [ ] automatic and User Confirmed authority remain distinct.
- [ ] Participation defaults are centralized and independent from View role.
- [ ] failure preserves prior Stable Mask and Participation authority.

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
