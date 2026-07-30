# 07A — Simplified Object-level Anchor Acquisition

Status: blocked — waits for Ticket 04C and Ticket 07 correction

Blocked by: 04A, 04C, 05, 07

Blocks: 07B, 08

## Final Spec mapping

- Final Spec v1.3 §§4, 6–8, 14–16, 24–26
- ADR 0016

## Purpose

Complete an object-level Anchor Stable Mask through the official SAM 3 Image instance interface without a general candidate clustering/ranking system.

```text
Prompt-conditioned instance prediction
→ direct candidate choice where single-click ambiguity exists
→ basic Prompt/Mask validity and Review
→ Accept
→ Editing Mask
→ Confirm
→ Anchor Stable Mask
```

## Prompt modes

### One positive point only

```text
multimask_output=true
→ 1–3 bounded candidates
→ exact duplicate removal allowed
→ highest model score may be default preview
→ user chooses/refines before Accept
```

The model score is not correctness probability and never auto-confirms.

### Box, multiple Points, or previous-logits refinement

```text
multimask_output=false
→ at most one candidate
→ basic validity/Review
→ Accept or refine/manual recovery
```

## Required validity

- exact RGB/Prompt/adapter/runtime/attempt identity;
- non-empty, non-full-frame Mask;
- Positive Points inside;
- Negative Points outside;
- Positive Instance Box has meaningful overlap and no gross spill;
- severe fragmentation or material boundary clipping enters Review;
- stale candidates cannot attach to newer Prompt/RGB;
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

Paint/Erase never reruns SAM and never enter PromptState. Confirm is the only Anchor Stable publication action.

## Recovery

- one-point ambiguity: choose candidate, add Point, add Box, Retry, or Manual Draw;
- no candidate: adjust Point/Box, Retry, or Empty→Paint;
- Review: Accept for editing, refine Prompt, or Manual Draw;
- technical failure: preserve RGB and prior Stable Mask;
- old 04B Multiplex result: reject by adapter/schema identity.

## Acceptance criteria

- [ ] One positive point retains at most three candidates.
- [ ] Box/multiple-Point/refinement requests retain at most one candidate.
- [ ] User candidate choice resolves one-point material ambiguity.
- [ ] Raw model score only controls default preview ordering.
- [ ] Point and Positive Box consistency are enforced.
- [ ] Negative Box and Mask Constraint evaluators are absent.
- [ ] Basic clipping/fragmentation/spill review works.
- [ ] Accept, Editing Mask, Confirm and Stable Mask remain distinct.
- [ ] previous logits refine only the same image/lineage.
- [ ] manual recovery exists from every state.
- [ ] confirmed Anchor is a later geometry identity seed, not Gaussian ownership.

## Validation

- locked SAM 3 Image adapter smoke;
- one-point three-candidate walkthrough;
- Box/multiple-Point single-candidate walkthrough;
- previous-logits refinement walkthrough;
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
