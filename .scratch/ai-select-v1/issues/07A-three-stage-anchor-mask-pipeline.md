# 07A — Simplified Object-level Anchor Acquisition

Status: implemented — `anchor-mask-ranking/v3` + proposal set schema v4 + per-candidate Mask Review

Blocked by: 04A, 04C, 05, 07

Blocks: 07B, 08

## Implementation record

- Contract rotation (both sides, fail-closed): proposal set schemaVersion
  3 → 4, ranking policy `anchor-mask-ranking/v2` → `anchor-mask-ranking/v3`,
  ProposalDecision schemaVersion 1 → 2. Proposal policy
  `auto-mask-proposals/bounded-source-order-v2` and the 04C multimask
  (≤3 for one include Point, ≤1 otherwise) and opaque logits-ref contracts
  are unchanged.
- Removed v1 complexity (`src/ai-select/mask-proposal.ts`,
  Companion `proposal_ranking.py`): pairwise containment/IoU,
  material-distinctness, compactness, box fill/spill feature vectors,
  prompt-mask overlap, boundary distances, `optionalSupportSanity`
  (Gaussian support is Ticket 13 Lift Readiness, never an Anchor selector),
  and all eight ranking reason codes with the Top-1 margin calibration.
- `ProposalRankingFeatures` v3 is exactly what candidate choice consumes:
  prompt consistency echo, `eligible`, `areaFraction`,
  `connectedComponentCount`, model score echo. Eligibility requires every
  declared prompt fact and a non-failed Mask Review; the editor rejects an
  `eligible` candidate that contradicts either.
- Per-candidate `review`: the Ticket 07 `local-view-assessment/v2` policy
  now also assesses Anchor candidates Companion-side
  (`assess_local_view` with the exact instance Prompt family). Candidates
  carry a `ViewAssessmentShape` (no Stable-Mask input identity);
  `view_assessment.local_view_assessment_payload` is the single serializer
  shared with Stable-Mask View assessments. Editor validation reuses
  `isViewAssessmentShape` (evidence-backed reasons only).
- `ProposalDecision` v2: enumerates exactly the eligible candidates in
  deterministic default-preview order — highest raw model score, ties by
  source order (`defaultPreviewProposalOrder`, mirrored in
  `decide_proposals`). The score only orders the preview and never
  auto-confirms; `selected`/`ambiguous`/`unavailable` derive purely from
  the eligible count, and the editor re-derives and rejects any other
  decision shape. Structured ranking reasons are deleted; Mask-quality
  claims live on the per-candidate Review.
- Editor-side bound enforcement: `maskResponseMatchesRequest` rejects a
  response whose candidate count exceeds
  `maximumAutoMaskProposalCount(promptState, hasRefinement)`.
- Declared prompt facts must be the exact three-key record; a partial or
  invalid declaration falls back to recomputation, which emits the same
  three keys (Box fact vacuous without a Box family, meaningful overlap
  with one). A declared out-of-frame Box fails closed instead of silently
  evaporating from consistency evaluation.
- Anchor Dock: the candidate dropdown lists the decision's alternatives
  (score-ordered); the prompt status line shows the previewed candidate's
  localized Review reasons (`ai-select.review.reason.*`) and a
  refinement-fallback hint (`ai-select.proposal.refinement-fallback`,
  all 9 locales) when the Companion discarded an expired/foreign logits
  ref. The eight retired `ai-select.proposal.reason.*` keys are deleted
  from every locale.
- Accept → Editing Mask → Paint/Erase → Confirm → Anchor Stable Mask is
  unchanged (Tickets 04/05); Accept still requires an eligible candidate
  from the decision's alternatives, and Paint/Erase never re-enters
  Prompt mode. Old 04B Multiplex artifacts remain rejected by
  adapter/manifest identity (regression test retained).

## Follow-ups (not in scope)

- The legacy reference-adapter frame-set path still declares a two-key
  `promptConsistency` at proposal top level, which the editor has always
  rejected; unreachable through the current SAM 3 Image adapter.
- Companion-restart walkthrough and locked-adapter GPU smoke remain
  operator-side validation (the GPU test skips without
  `SUPERSPLAT_SAM3_IMAGE_GPU_CHECKPOINT`).

## Final Spec mapping

- Final Spec v1.3 §§4, 6–8, 14–16, 24–26
- ADR 0016

## Purpose

Complete an object-level Anchor Stable Mask through the official SAM 3 Image instance interface without a general candidate clustering/ranking system.

```text
Prompt-conditioned instance prediction
→ direct candidate choice where single-click ambiguity exists
→ optional Point refinement while still in Prompt mode
→ basic Prompt/Mask validity and Review
→ Accept
→ Editing Mask
→ Confirm
→ Anchor Stable Mask
```

## Prompt modes

### One Positive Point only

```text
multimask_output=true
→ 1–3 bounded candidates
→ exact duplicate removal allowed
→ highest model score may be default preview
→ user chooses or refines before Accept
```

The model score is not correctness probability and never auto-confirms.

### Box, multiple Points, or previous-logits refinement

```text
multimask_output=false
→ at most one candidate
→ basic validity/Review
→ Accept or continue Prompt/manual recovery
```

A previous-logits refinement uses only the opaque Companion-owned ref associated with the currently chosen preview candidate. Candidate choice and Point refinement occur before `Accept` while the surface remains in Prompt mode.

After `Accept`, the Mask enters Editing mode. Paint/Erase never become SAM Prompts. Returning from Editing to Prompt mode is explicit, preserves the prior Stable Mask, and creates a new inference attempt.

## Required validity

- exact RGB/Prompt/adapter/runtime/Companion/attempt identity;
- resolvable authoritative RGB, not digest-only input;
- non-empty, non-full-frame Mask;
- Positive Points inside;
- Negative Points outside;
- Positive Instance Box has meaningful overlap and no gross spill;
- severe fragmentation or material boundary clipping enters Review;
- stale candidates or previous-logits refs cannot attach to newer Prompt/RGB/Companion state;
- no Prompt or proposal mutates a prior Stable Mask.

## Removed v1 complexity

This ticket no longer requires:

- generic near-duplicate clustering;
- materially-distinct cluster discovery;
- automatic Top-1 margin calibration;
- general candidate ranking feature pipelines;
- repeated-run stability as a closure gate;
- Gaussian support as Anchor target selector;
- Negative Box or Mask Constraint consistency;
- whole-image object inventory.

Exact duplicate removal and bounded candidate transport remain allowed.

## Accept / Edit / Confirm

```text
candidate chosen or single candidate valid
→ explicit Accept
→ Editing Mask

Editing Mask
→ Paint / Erase
→ explicit Confirm
→ Anchor Stable Mask
```

Paint/Erase never rerun SAM and never enter PromptState. Confirm is the only Anchor Stable publication action.

## Recovery

- one-point ambiguity: choose candidate, add Point, add Box, Retry, or Manual Draw;
- missing/expired logits ref: rerun current Points/Box without `mask_input`;
- no candidate: adjust Point/Box, Retry, or Empty→Paint;
- Review: Accept for editing, refine Prompt before Accept, or Manual Draw;
- technical failure: preserve RGB and prior Stable Mask;
- old 04B Multiplex result: reject by adapter/schema identity.

## Acceptance criteria

- [x] one Positive Point retains at most three candidates.
- [x] Box/multiple-Point/refinement requests retain at most one candidate.
- [x] user candidate choice resolves one-point material ambiguity.
- [x] raw model score only controls default preview ordering.
- [x] Point and Positive Box consistency are enforced.
- [x] Negative Box and Mask Constraint evaluators are absent.
- [x] basic clipping/fragmentation/spill review works.
- [x] candidate refinement occurs before Accept and uses an opaque same-Companion logits ref.
- [x] Companion replacement or missing ref falls back to fresh no-logits inference.
- [x] Accept, Editing Mask, Confirm and Stable Mask remain distinct.
- [x] manual recovery exists from every state.
- [x] confirmed Anchor is a later geometry identity seed, not Gaussian ownership.

## Validation

- locked SAM 3 Image adapter smoke;
- authoritative RGB request fixture;
- one-point three-candidate walkthrough;
- Box/multiple-Point single-candidate walkthrough;
- previous-logits-ref and Companion-restart walkthrough;
- Prompt consistency and stale-result regressions;
- Accept/Edit/Confirm browser tests;
- old Multiplex artifact rejection;
- repository test/lint/locales/build.

## Non-goals

- No whole-image inventory.
- No arbitrary part discovery.
- No general candidate cluster/ranker.
- No camera planning or multi-view tracking.
- No P/N/V or Gaussian ownership.
