# 08B — 3D-guided per-Key-View SAM production acquisition

Status: planned — route B selected

Blocked by: 08A, 04B, 07

Blocks: 09

## Final Spec mapping

- Final Spec v1.2 §§12–18, 27–29
- DG-26 Decisions 2–6 and 8
- ADR 0014 as subordinate Route-B-first rationale
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
→ PerViewMaskAcquisitionResult
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
- `PerViewMaskAcquisitionResult` production artifacts;
- `KeyViewMaskProposalSet` production artifacts;
- `KeyViewMaskDecisionPolicy` implementation;
- `MaskPublicationCoordinator` implementation;
- route-A B2 fallback orchestration;
- progressive per-view acquisition/proposal/decision/assessment/publication states;
- generic acquisition status/provenance for Ticket 09;
- exact refresh/dirty dependencies for Ticket 12;
- explicit migration from the legacy generated-view Mask contract;
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

The provider consumes authoritative RGB plus `KeyViewPromptArtifact` and returns a `PerViewMaskAcquisitionResult` containing one bounded `KeyViewMaskProposalSet` and one attempt-level `backendDiagnostics` authority.

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
- ProposalSet contains no duplicate attempt-level backend diagnostics;
- a successful result may contain an empty ProposalSet;
- technical failure publishes no partial result, ProposalSet, or Stable Mask.

A successful empty ProposalSet is not a backend failure. It proceeds to `KeyViewMaskDecisionPolicy` and becomes `unavailable`.

# Phase 4 — KeyViewMaskDecisionPolicy

Implement conservative decision over one exact ProposalSet.

Processing order:

```text
schema / Mask validity
→ exact ProposalSet identity binding
→ hard Prompt consistency eligibility
→ exact deduplication
→ near-duplicate clustering
→ structural and contamination gates
→ selected / ambiguous / unavailable
```

Rules:

- every Decision binds target/context/View/acquisition attempt and exact `proposalSetArtifactDigest`;
- raw model score is never sole selector;
- one credible proposal cluster may become `selected`;
- representative selection inside a duplicate cluster may use model score as a secondary tie-break;
- multiple materially distinct plausible clusters become `ambiguous`;
- neighbour-object pollution or hard Prompt conflict cannot become Auto Good;
- zero eligible proposal becomes `unavailable`;
- ambiguous preserves ProposalSet for Review and selects no hidden Stable Mask;
- proposal IDs from another ProposalSet or attempt are rejected even when values collide.

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

`ambiguous` and `unavailable` never receive a fabricated Assessment.

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
→ acquisition Ready
→ Decision Unavailable
→ publish no Stable Mask
→ Excluded
```

`unavailable` is a valid Decision after successful acquisition. It MUST remain distinct from technical acquisition failure, protocol rejection, cancellation, or OOM.

Requirements:

- validate exact ProposalSet/Decision/Assessment membership and identity;
- validate exact `proposalSetArtifactDigest` and acquisition attempt on Decision;
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
- Decision `unavailable` after successful acquisition;
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
→ receive PerViewMaskAcquisitionResult / ProposalSet
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

# Phase 9 — legacy generated-view contract migration

The current implementation contains a legacy single-frame contract equivalent to:

```text
GeneratedViewMaskRequest
→ AISelectGeneratedViewMaskProvider.produceGeneratedViewMask
→ GeneratedViewMaskResponse {
     maskSource: 'propagated'
     maskPropagation
     mask
     assessment
   }
→ controller publishes Stable Mask and Participation directly
```

08B MUST explicitly retire or isolate that contract.

Migration requirements:

- supersede `GeneratedViewMaskResponse.assessment`; provider responses contain no Assessment;
- supersede the fixed `maskSource: 'propagated'` interpretation with backend-neutral acquisition provenance;
- replace `GeneratedViewMaskPropagation` as the generic truth source with Prompt artifact diagnostics, ProposalSet candidate diagnostics, and attempt-level backend diagnostics;
- controller no longer derives Stable publication or Participation directly from a provider response;
- legacy `generated-view-mask/v1` payloads and cached results cannot validate as Ticket 08A/08B artifacts;
- migration uses explicit contract/version incompatibility rather than structural best-effort rebinding;
- prior User Confirmed Stable Masks remain authoritative through migration;
- old route-A baseline may remain behind a dedicated adapter, but it emits the new ProposalSet/result contract and is visibly route A.

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
- [ ] Provider returns `PerViewMaskAcquisitionResult` with bounded ProposalSet, not one hidden final Mask.
- [ ] Attempt-level backend diagnostics exist only on the result envelope.
- [ ] Every candidate Mask validates dimensions/digest.
- [ ] Every Key View has independent attempt/retry identity.
- [ ] Same-attempt replay is idempotent; explicit Retry is new work.
- [ ] RGB Ready does not wait for Prompt synthesis or inference.
- [ ] Successful empty ProposalSet is represented and proceeds to `unavailable`.
- [ ] OOM/cancellation/technical failure publishes no partial result/ProposalSet/Stable Mask.

## Decision

- [ ] Exact and near-duplicate clustering is deterministic.
- [ ] Every Decision binds the exact ProposalSet digest and attempt.
- [ ] Hard Prompt contradiction makes a proposal ineligible.
- [ ] Raw model score is not the sole selector.
- [ ] One credible cluster may be selected.
- [ ] Materially distinct plausible alternatives remain ambiguous.
- [ ] Ambiguous publishes no arbitrary Stable Mask.
- [ ] Zero eligible proposal becomes unavailable.
- [ ] Cross-attempt proposal ID collision cannot satisfy Decision membership.

## Assessment/publication

- [ ] Only selected proposals are assessed.
- [ ] Decision and assessment policy identities are independent.
- [ ] selected+Good publishes Auto Good+Included.
- [ ] selected+Review publishes Auto Review+Excluded.
- [ ] ambiguous/unavailable publish no new Stable Mask.
- [ ] unavailable remains acquisition-ready/decision-unavailable, not technical Mask failure.
- [ ] User Confirmed Stable Mask is never overwritten silently.
- [ ] Failure preserves View/RGB/frustum/prior Stable Mask.
- [ ] No publication automatically creates P/N/V or Re-Lifts.

## B2 fallback

- [ ] Automatic fallback triggers only for enumerated technical/capability failures.
- [ ] Ambiguous/unavailable/Review/contamination/clipping/fragmentation never trigger automatic fallback.
- [ ] Fallback attempt binds parent and reason.
- [ ] Route-A result uses the same Proposal/Decision/Assessment/Publication layers.
- [ ] Route-A Auto Good requires same or stricter thresholds.
- [ ] Route-B failure and route-A provenance remain inspectable.

## Legacy migration

- [ ] `GeneratedViewMaskResponse.assessment` is removed or isolated behind a non-current compatibility adapter.
- [ ] `maskSource: 'propagated'` is not the generic source for route-B results.
- [ ] controller performs no direct provider-response Assessment or Stable publication policy.
- [ ] legacy `generated-view-mask/v1` result cannot pass new validators or attach to a new attempt.
- [ ] migration preserves User Confirmed Stable authority and prior inspectable state.
- [ ] route-A compatibility adapter emits the new result/ProposalSet contract.

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
- [ ] selected/ambiguous/unavailable rates are reported separately from technical failure rate.
- [ ] Manual correction burden, latency, peak VRAM, fallback rate and recovery are reported.
- [ ] Final Gaussian precision/recall, background contamination, Mixed/Uncertain ratio and Add/Remove burden proxy are reported.
- [ ] Route A remains a tested fallback/regression baseline.
- [ ] C/D implementation or comparison is not required for closure.

# Failure / recovery criteria

- Backend unavailable: preserve completed Views/RGB/Masks; attempt eligible route-A fallback or offer manual/exclude.
- Prompt synthesis insufficient: Review/Failed with adjusted View/manual Prompt/Exclude recovery.
- Route-B OOM: no partial publication; eligible B2 fallback only when declared safe.
- Ambiguous: retain ProposalSet; user refines/chooses/paints; no automatic route A.
- Unavailable after successful acquisition: retain acquisition result and diagnostics; offer Prompt/View adjustment, Retry, manual correction, or Exclude; no automatic route A.
- Neighbour-instance risk: Review, not silent Auto Good or fallback.
- Stale Anchor/support/bootstrap/segment/View/RGB/Prompt/backend/attempt result: discard.
- Publication conflict with User Confirmed Stable: retain user authority and store no automatic replacement as current Stable.
- Legacy contract/cache mismatch: reject as incompatible, never structurally rebind.
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
- exact ProposalSet digest/attempt membership tests
- cross-attempt proposal ID collision regression
- ambiguous-no-Stable regression
- unavailable-versus-technical-failure regression
- selected/assessment/publication transition tests
- backend registry route-B fixture
- technical-fallback eligibility matrix
- route-A same-or-stricter threshold regression
- legacy generated-view contract/cache rejection
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
