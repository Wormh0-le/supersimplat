# Adopt single-result Mask authoring and retire explicit recovery and planning controls

Status: accepted

Date: 2026-08-16

## Context

The SAM 3 Image compatibility protocol can represent a bounded proposal set
and decision, but the product retains at most one eligible result. The editor
already has two distinct publication authorities: operator-authored Prompt
results enter the editable draft workflow, while reviewed planner-owned
Generated-View results may publish directly as Stable. Keeping Proposal
selection and acceptance in the public model makes unreachable states appear
current and makes the runtime advertise single-point multimask behavior that
the product intentionally rejects.

The first bounded local plan also needs enough observations without requiring
operators to manage a persistent planning queue. Execution attempts,
idempotent replay, stale-result rejection, cancellation, cache recovery and
Companion admission remain correctness infrastructure; they are not product
retry controls.

## Decision

1. An operator-authored Point, Box or refinement request has one product
   result: exactly one usable Mask with its Review and optional refinement
   lineage, or semantic unavailable. A usable result automatically becomes
   the Editing Mask. There is no Proposal chooser, preview or Accept step.
2. Multiple usable results, malformed results or mismatched identities fail
   closed before product state changes. The existing internal
   `/ai-select/mask-proposals` endpoint and `ProposalSet` / `ProposalDecision`
   envelope remain a temporary compatibility seam; the browser collapses that
   envelope at the transport boundary and introduces no new cross-runtime
   schema in this stage.
3. The readiness handshake reports `singlePointMultimask: false` and requires
   that value. Previous-prediction logits remain Companion-local; expired
   lineage continues through the existing fresh single-result inference path.
4. A reviewed planner-owned automatic Generated-View result remains a
   separate publication authority. Good may publish directly as Stable and
   defaults Included; Review may publish directly as Stable and defaults
   Excluded; Failed or unavailable publishes no Stable Mask. Automatic
   publication never replaces User Confirmed authority.
5. Stable-without-Editing is a valid confirmed state. Later correction creates
   an independent Editing draft and preserves the Stable revision until
   explicit Confirm Mask.
6. The versioned fixed-offset planner schedules an initial `4–8` automatic
   Generated Views, excluding the Anchor and User-added Views. The current
   deterministic configuration schedules four. Existing offset, framing and
   validity semantics remain unchanged; invalid candidates may leave fewer
   usable Views and remain inspectable. This is not an adaptive-quality claim.
7. Persistent Stop, Generate More and Regenerate controls, plus identical-input
   Render, Prompt and Mask retry commands, are retired from the current product
   contract and removed by Tickets 16D and 16G. A failure-only initial-planning
   recovery remains. Attempt identity, same-attempt replay, cancellation,
   transport/cache recovery, admission and stale-result checks remain required.

## Consequences

- This ADR supersedes ADR 0016 Decision items 5 and 7, Decision item 9's
  `2–4` range, and its candidate-choice and explicit Generate More product
  consequences. ADR 0016 remains the historical authority for the SAM 3 Image
  migration and bounded-local-view rationale where not superseded here.
- Browser authoring code outside the compatibility adapter consumes a singular
  Mask result. Compatibility proposal types and endpoint tests remain internal
  until a later protocol migration replaces them deliberately.
- Review, refinement fallback and previous-logits lineage survive the
  contraction; only plurality and acceptance state leave the product surface.
- Ticket 16B establishes the contract and capability/planner identities.
  Tickets 16C–16G complete the presentation and obsolete-control removal; they
  must not remove execution-attempt or replay correctness infrastructure.
- No model, checkpoint, renderer, Evidence policy or CUDA behavior changes.
