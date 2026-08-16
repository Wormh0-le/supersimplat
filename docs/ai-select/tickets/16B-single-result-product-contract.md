# 16B — Single-result Mask product contract + execution-frontier correction

Status: ready-for-agent — post-16A visual-review follow-up

Blocked by: 16A, 16, 15, 07A, 04C

## Current Final Spec mapping

- Parent Ticket 16 / Final Spec v1.3 §§4, 6–8, 16–19, 22, 24–26
- Ticket 16A as the implemented presentation baseline
- ADR 0016 as historical authority for the SAM 3 Image/minimal-multiview
  decision where it is not superseded by this stage
- Post-16A operator visual-review decisions recorded by this Ticket and stages
  16C–16G

Final Spec v1.3 remains the current authority when this Ticket starts. This
stage must publish the superseding ADR and update the current specification
before dependent stages close. It must not rewrite historical ADRs or completed
Ticket evidence.

## Inputs / preconditions

- Ticket 16A implementation and completed operator visual review
- Existing single-retained-result browser/runtime behavior
- Existing internal mask-proposal endpoint and
  `ProposalSet` / `ProposalDecision` compatibility envelope
- Existing Prompt, Editing Mask, Stable Mask, Review and previous-logits
  lineage contracts
- Existing attempt identity, cancellation, replay and Companion admission/cache

## Outputs / handoff artifacts

- One current product contract for single-result Mask authoring
- A superseding ADR for single-result authoring and product recovery/planning
  controls
- Truthful editor/Companion capability handshake
- Removal of unreachable Proposal-choice presentation and public authoring APIs
- Versioned initial-plan range of `4–8` automatic Generated Views
- Updated Final Spec, glossary, lifecycle guidance, mapping and traceability
- Stable compatibility seam for the retained internal Proposal wire envelope

## What to build

Make the product contract match the behavior already exposed to operators: an
operator-authored Prompt request produces one usable Mask or unavailable, and
a usable result automatically becomes the Editing Mask. There is no user
Proposal selection or Accept step. The planner-owned automatic Generated-View
path remains a separate publication authority: after browser Review, an
eligible result may publish directly as Stable without first creating Editing
or requiring user confirmation.

This stage also establishes the normative product decision that persistent
planning controls and explicit Render/Prompt/Mask retry commands are being
retired by stages 16D and 16G. It does not remove attempt identity, replay,
transport recovery or Companion correctness infrastructure.

## Acceptance criteria

### Single-result authoring

- [ ] Current product terminology describes one usable Mask or unavailable.
- [ ] A valid result from operator-authored Prompt/refinement input
      automatically becomes the Editing Mask.
- [ ] A reviewed planner-owned automatic Generated-View result may publish
      directly as Stable: Auto Good defaults Included, Auto Review defaults
      Excluded, and Failed/semantic-unavailable publishes no Stable Mask.
- [ ] Direct automatic publication may not replace User Confirmed authority.
- [ ] An automatically published Stable Mask with no Editing Mask is a valid,
      confirmed state; later correction creates an independent Editing draft
      and preserves that Stable revision until explicit Confirm Mask.
- [ ] No current UI state requires Proposal selection, preview or acceptance.
- [ ] User-facing `Proposal`, ambiguous-choice and
      selected-awaiting-accept terminology is removed from presentation state,
      public authoring APIs and current locale strings.
- [ ] Unreachable preview/accept public wrappers are removed without removing
      Mask Review, refinement fallback or previous-logits lineage.
- [ ] Multiple or malformed usable results fail closed at the current
      compatibility boundary rather than exposing a chooser.
- [ ] Review metadata propagates with the sole usable result.
- [ ] `singlePointMultimask` is reported as `false`, and editor readiness no
      longer requires a capability the runtime intentionally does not provide.

### Compatibility boundary

- [ ] The internal mask-proposal endpoint and
      `ProposalSet` / `ProposalDecision` wire envelope remain temporarily
      supported.
- [ ] Compatibility identities, eligibility, Review, refinement fallback and
      previous-logits lineage remain exact.
- [ ] No new cross-runtime single-Mask schema is introduced in this stage.
- [ ] Browser code outside the compatibility adapter consumes the single-result
      product model rather than Proposal plurality.

### Normative documentation

- [ ] A new accepted ADR supersedes conflicting multi-candidate-choice clauses
      and explicit Generate More consequences in ADR 0016 without rewriting it.
- [ ] The ADR distinguishes removed product retry commands from retained
      execution-attempt and replay infrastructure.
- [ ] The fixed-offset initial planner schedules `4–8` automatic Generated
      Views, excluding the Anchor and User-added Views. Candidate validity
      failures may leave fewer usable Views and remain inspectable.
- [ ] The planner policy/configuration identity and tests reflect the new range;
      existing offset, framing and validity semantics remain unchanged, and no
      adaptive quality claim is introduced.
- [ ] Final Spec, domain glossary, lifecycle/protocol guidance, current mapping,
      traceability and reusable interface guidance agree on the new contract.
- [ ] Completed Tickets and historical ADRs retain their implementation record
      and are marked superseded only where their current-facing behavior
      conflicts.
- [ ] The local control plane records 16A as implemented with completed visual
      review, 16B as the current stage and 17 as following 16G.

## Failure / recovery criteria

- [ ] An unavailable provider result publishes no Editing or Stable Mask.
- [ ] A malformed or multiple-result compatibility response cannot partially
      publish one arbitrary result.
- [ ] Expired refinement lineage still falls back through the existing fresh
      inference path.
- [ ] A capability mismatch fails with an actionable readiness reason and does
      not mutate Mask state.

## Validation

- `rtk npm test`
- `rtk npm run lint`
- `rtk npm run lint:locales`
- Editor/Companion capability-handshake tests with
  `singlePointMultimask: false`
- Single usable result, unavailable result, operator-authored automatic Editing
  Mask adoption, automatic Generated-View direct Stable publication,
  Stable-without-Editing correction, malformed/multiple-result rejection,
  Review and refinement-fallback tests
- Initial planner schedules `4–8` automatic Generated Views, excludes Anchor
  and User-added Views from the count, and preserves failed/partial records
- Documentation/traceability consistency checks

## Non-goals

- No replacement of the internal Proposal wire envelope
- No new segmentation model, weight, renderer or CUDA behavior
- No camera-planner quality improvement
- No removal of attempt identity, stale-result checks, cancellation,
  idempotent replay, transport cache-miss resubmission or Companion admission
- No implementation of Ticket 17 Restart, Undo and Fix or multi-target lifecycle
