# 08B — 3D-guided per-Key-View SAM production acquisition

Status: planned — route B selected

Blocked by: 08A, 04B, 07

Blocks: 09

## Final Spec mapping

- Final Spec v1.2 §§12–18, 27–29
- DG-26 Decisions 2–6 and 8
- Ticket 08 visible support/bootstrap/planner artifacts
- Ticket 08A acquisition contracts and backend registry

## Purpose

Implement the selected v1 production Mask acquisition route:

```text
VisibleTargetSupportArtifact
+ TargetBootstrapArtifact
+ authoritative Key-View RGB / CameraBinding
→ KeyViewPromptSynthesizer
→ KeyViewPromptArtifact
→ route-B per-view SAM provider
→ KeyViewMaskProposalSet
→ KeyViewMaskDecisionPolicy
→ ViewAssessmentPolicy
→ MaskPublicationCoordinator
```

Route B is implemented directly. No A/B/C/D comparison or acquisition-route ADR blocks this ticket.

Route A remains a regression baseline and automatic fallback only for declared technical/capability failures.

Routes C/D are not implemented.

## Inputs / preconditions

- Ticket 08 exact `VisibleTargetSupportArtifact`;
- Ticket 08 exact `TargetBootstrapArtifact`;
- Ticket 08 immutable `SparseKeyViewPlanSegment`;
- authoritative RGB and CameraBinding for every Key View;
- Ticket 08A schemas, validators, backend bundle and registry;
- Ticket 04B truthful Prompt adapter capabilities;
- Ticket 07 `ViewAssessmentPolicy`;
- Stable Mask registry and stale-result gate;
- current route-A baseline provider;
- locked model manifest/runtime identity.

## Outputs / handoff artifacts

- production `KeyViewPromptSynthesizer`;
- versioned Prompt synthesis policy;
- registered route-B `per-view-sam` backend bundle;
- route-B `MultiViewMaskAcquisitionProvider` implementation;
- `KeyViewMaskProposalSet` production artifacts;
- `KeyViewMaskDecisionPolicy` implementation;
- `MaskPublicationCoordinator` implementation;
- route-A B2 fallback orchestration;
- progressive per-view acquisition/proposal/decision/assessment/publication states;
- generic acquisition status/provenance for Ticket 09;
- exact refresh/dirty dependencies for Ticket 12;
- production quality/resource/downstream validation report.

# Phase 1 — KeyViewPromptSynthesizer

Implement a dedicated service equivalent to:

```ts
interface KeyViewPromptSynthesizer {
    synthesize(
        request: KeyViewPromptSynthesisRequest
    ): Promise<KeyViewPromptArtifact>;
}
```

It consumes exact current support/bootstrap/plan/View/RGB/capability/policy identities.

Supported Prompt families may include:

- visibility-aware projected positive support points;
- projected robust target center;
- projected Box/ROI from support/extent;
- local negative points or region around the target;
- compatible projected Mask input when the adapter truthfully supports it;
- object scale, clipping, boundary, support-loss, and contamination diagnostics.

Requirements:

- deterministic output for exact inputs;
- canonical Prompt ordering and digest;
- support projected using the exact Key-View CameraBinding;
- points/regions clipped to the exact image dimensions;
- unsupported Prompt types fail before inference;
- insufficient support yields structured diagnostics and Review/Failed recovery, not an oversized guessed target;
- Prompt artifact is independently inspectable/replayable;
- Prompt regeneration is separate from SAM Retry.

# Phase 2 — route-B backend registration

Register a backend bundle equivalent to:

```text
backendKind = per-view-sam
perView = route-B provider
sequence = absent
```

The descriptor and actual bundle MUST pass Ticket 08A validation.

Route B never fabricates sequence sessions, references, auxiliary frames, or repropagation capability.

# Phase 3 — route-B SAM provider

The provider consumes authoritative RGB plus `KeyViewPromptArtifact` and returns a bounded `KeyViewMaskProposalSet`.

Requirements:

- independent inference per Key View;
- no adjacent-frame/tracker-memory dependency;
- bounded candidate count;
- exact Mask dimensions and digest validation;
- raw model scores retained only as diagnostics;
- backend/model/runtime identity explicit;
- per-view attempt independently retryable;
- same-attempt replay idempotent where supported;
- explicit Retry creates a new attempt;
- RGB Ready never waits for inference;
- technical failure publishes no partial ProposalSet or Stable Mask.

# Phase 4 — KeyViewMaskDecisionPolicy

Implement conservative decision over one exact ProposalSet.

Processing order:

```text
schema / Mask validity
→ hard Prompt consistency eligibility
→ exact deduplication
→ near-duplicate clustering
→ structural and contamination gates
→ selected / ambiguous / unavailable
```

Rules:

- raw model score is never sole selector;
- one credible proposal cluster may become `selected`;
- representative selection inside a duplicate cluster may use model score as a secondary tie-break;
- multiple materially distinct plausible clusters become `ambiguous`;
- neighbour-object pollution or hard Prompt conflict cannot become Auto Good;
- zero eligible proposal becomes `unavailable`;
- ambiguous preserves ProposalSet for Review and selects no hidden Stable Mask.

# Phase 5 — ViewAssessmentPolicy integration

Only `selected` enters assessment.

Extend/integrate Ticket 07 assessment inputs to consume exact selected-Mask and acquisition diagnostics without changing ownership semantics.

Assessment remains:

```text
Good / Review / Failed
```

Potential reasons include:

- target at boundary;
- fragmented Mask;
- weak declared support;
- projected-support inconsistency;
- neighbour contamination risk;
- clipping/poor render where supported.

Assessment does not re-run target-instance candidate selection.

# Phase 6 — MaskPublicationCoordinator

Implement backend-neutral publication transitions:

```text
selected + Good
→ publish Auto Good Stable Mask
→ default Included

selected + Review
→ publish Auto Review Stable Mask
→ default Excluded

ambiguous
→ retain Review ProposalSet
→ publish no new Stable Mask
→ Excluded

unavailable
→ Mask Failed
→ publish no Stable Mask
→ Excluded
```

Requirements:

- validate exact ProposalSet/Decision/Assessment membership and identity;
- atomic publication;
- no partial Mask becomes Stable;
- do not overwrite a current User Confirmed Stable Mask;
- preserve prior Stable Mask on failure;
- provenance records Prompt, backend, model/runtime, attempt, fallback, Decision and assessment policy identities;
- backend identity does not itself imply trust or Participation.

# Phase 7 — route-A B2 fallback

Automatic route-A fallback is allowed only after route-B technical/capability failure.

Eligible reasons:

- route-B backend unavailable;
- required Prompt capability unavailable while route A remains executable;
- route-B technical compatibility rejection;
- recoverable route-B inference failure;
- route-B OOM with declared route-A lower-resource availability.

Ineligible outcomes:

- Decision `ambiguous`;
- neighbour contamination;
- Prompt consistency failure;
- fragmentation or boundary clipping;
- Assessment `Review`;
- existing User Confirmed Stable Mask.

Fallback rules:

- create a new route-A attempt;
- bind `fallbackOfAttemptId` and structured technical reason;
- retain route-B failure record;
- run the same ProposalSet → Decision → Assessment → Publication chain;
- use the same or stricter decision/contamination/assessment thresholds;
- allow Auto Good only after all gates pass;
- expose fallback provenance to Ticket 09;
- never represent a route-A result as route B.

# Phase 8 — controller and scheduler integration

Refactor the existing Generated View pipeline so orchestration is separate from algorithms:

```text
plan
→ render RGB and publish immediately
→ synthesize Prompt artifact
→ dispatch backend through registry
→ receive ProposalSet
→ decide
→ assess selected Mask
→ publish through coordinator
```

Required seams:

- `generated-view-controller.ts` coordinates jobs but contains no geometric Prompt algorithm, SAM selection, decision or assessment implementation;
- `generated-view-service.ts` exposes Ticket 08A contracts;
- Companion state owns bounded model scheduling, dispatch, replay, cancellation and cleanup;
- Mask registry stores generic acquisition provenance without tracker internals;
- readiness reports exact selected backend descriptor/bundle;
- Gallery consumes generic acquisition/proposal/decision status;
- optional future sequence dispatch remains a separate unused seam.

# Acceptance criteria

## Prompt synthesis

- [ ] Exact inputs produce deterministic `KeyViewPromptArtifact`.
- [ ] Projected support uses the exact Key-View CameraBinding and image dimensions.
- [ ] Positive support is visibility-aware.
- [ ] Box/ROI/local-negative/Mask constraints appear only when capabilities support them.
- [ ] Unsupported Prompt families fail closed rather than being dropped/converted.
- [ ] Diagnostics explain support loss, clipping, boundary risk, and likely neighbour contamination.
- [ ] Prompt artifact can be replayed independently from inference.

## Provider and proposals

- [ ] Route-B bundle registers as perView-only.
- [ ] Provider returns bounded ProposalSet, not one hidden final Mask.
- [ ] Every candidate Mask validates dimensions/digest.
- [ ] Every Key View has independent attempt/retry identity.
- [ ] Same-attempt replay is idempotent; explicit Retry is new work.
- [ ] RGB Ready does not wait for Prompt synthesis or inference.
- [ ] OOM/cancellation/failure publishes no partial ProposalSet/Stable Mask.

## Decision

- [ ] Exact and near-duplicate clustering is deterministic.
- [ ] Hard Prompt contradiction makes a proposal ineligible.
- [ ] Raw model score is not the sole selector.
- [ ] One credible cluster may be selected.
- [ ] Materially distinct plausible alternatives remain ambiguous.
- [ ] Ambiguous publishes no arbitrary Stable Mask.
- [ ] Zero eligible proposal becomes unavailable.

## Assessment/publication

- [ ] Only selected proposals are assessed.
- [ ] Decision and assessment policy identities are independent.
- [ ] selected+Good publishes Auto Good+Included.
- [ ] selected+Review publishes Auto Review+Excluded.
- [ ] ambiguous/unavailable publish no new Stable Mask.
- [ ] User Confirmed Stable Mask is never overwritten silently.
- [ ] Failure preserves View/RGB/frustum/prior Stable Mask.
- [ ] No publication automatically creates P/N/V or Re-Lifts.

## B2 fallback

- [ ] Automatic fallback triggers only for enumerated technical/capability failures.
- [ ] Ambiguous/Review/contamination/clipping/fragmentation never trigger automatic fallback.
- [ ] Fallback attempt binds parent and reason.
- [ ] Route-A result uses the same Proposal/Decision/Assessment/Publication layers.
- [ ] Route-A Auto Good requires same or stricter thresholds.
- [ ] Route-B failure and route-A provenance remain inspectable.

## Architecture

- [ ] Provider returns no ViewAssessmentResult.
- [ ] Controller contains no hidden Top-1/assessment/publication policy.
- [ ] Registry bundle structure is the actual capability source.
- [ ] Route B has no sequence/reference methods.
- [ ] Unsupported future extension calls fail without state mutation.
- [ ] Prompt synthesis, inference, decision, assessment, publication and Participation are independently testable.

## Production validation

- [ ] Frozen sparse-Key-View scenes and review protocol are versioned.
- [ ] Per-view acceptable-mask rate and neighbour contamination are reported.
- [ ] selected/ambiguous/unavailable rates are reported.
- [ ] Manual correction burden, latency, peak VRAM, fallback rate and recovery are reported.
- [ ] Final Gaussian precision/recall, background contamination, Mixed/Uncertain ratio and Add/Remove burden proxy are reported.
- [ ] Route A remains a tested fallback/regression baseline.
- [ ] C/D implementation or comparison is not required for closure.

# Failure / recovery criteria

- Backend unavailable: preserve completed Views/RGB/Masks; attempt eligible route-A fallback or offer manual/exclude.
- Prompt synthesis insufficient: Review/Failed with adjusted View/manual Prompt/Exclude recovery.
- Route-B OOM: no partial publication; eligible B2 fallback only when declared safe.
- Ambiguous: retain ProposalSet; user refines/chooses/paints; no automatic route A.
- Neighbour-instance risk: Review, not silent Auto Good or fallback.
- Stale Anchor/support/bootstrap/segment/View/RGB/Prompt/backend/attempt result: discard.
- Publication conflict with User Confirmed Stable: retain user authority and store no automatic replacement as current Stable.
- Unsupported sequence/reference method: structured capability failure, no mutation.

# Validation commands and fixtures

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run lint:locales`
- `npm run build`
- locked-runtime route-B acquisition smoke
- frozen sparse-Key-View benchmark
- table/chairs and similar-instance contamination regression
- occlusion/reappearance and poor-render regression
- Prompt synthesis digest golden vectors
- ProposalSet/Decision clustering golden vectors
- ambiguous-no-Stable regression
- selected/assessment/publication transition tests
- backend registry route-B fixture
- technical-fallback eligibility matrix
- route-A same-or-stricter threshold regression
- stale support/bootstrap/segment/View/Prompt/backend rejection
- cancellation/OOM atomicity
- final P/N/V Gaussian outcome validation

# Non-goals

- No camera generation; Ticket 08 owns it.
- No Anchor ProposalDecision; Ticket 07A owns it.
- No acquisition schema foundation; Ticket 08A owns it.
- No A/B/C/D route-selection spike.
- No tracker, Bridge View, dense trajectory, reference memory or repropagation implementation.
- No Gallery implementation; Ticket 09 owns presentation.
- No dirty-state orchestration; Ticket 12 owns it.
- No P/N/V Evidence or Gaussian ownership.
- No whole-image object inventory.
- No arbitrary part-level selection requirement.
- No automatic Re-Lift.
