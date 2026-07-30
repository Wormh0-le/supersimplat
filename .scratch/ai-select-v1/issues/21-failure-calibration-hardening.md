# 21 — Retry / cancellation / OOM / atomic publication + calibration hardening

Status: ready-for-agent — Final Spec v1.2 aligned

Blocked by: 20, 18, 02C, 07B, 08B, 10, 13

## Final Spec mapping

- Final Spec v1.2 §§4, 7, 17–18, 21–28
- DG-26
- ADR 0013
- ADR 0014 as subordinate Route-B-first rationale
- ADR 0015 for automatic readiness and operator-owned Active Model resolution

## Inputs / preconditions

- complete Final Spec v1.2 product flow;
- Ticket 02C automatic readiness and minimal Availability UI;
- Ticket 07B complete correction UX;
- production Direct Evidence path;
- locked GPU/model route-B acquisition runtime;
- frozen support/bootstrap/planner/acquisition benchmark scenes;
- route-A B2 fallback;
- backend bundle/registry and schema compatibility fixtures;
- exact ProposalSet/Decision identity validators;
- legacy generated-view acquisition contract/cache fixtures;
- optional future tracker/hybrid runtime only when separately adopted by ADR;
- fault-injection hooks.

## Outputs / handoff artifacts

- end-to-end failure hardening;
- versioned policy thresholds/margins;
- support/planner/route-B resource-envelope validation;
- acquisition bundle/dispatch compatibility results;
- route-A fallback eligibility and trust results;
- unavailable-versus-technical-failure validation;
- legacy contract migration/retention results;
- interaction release validation including Ticket 07B;
- stress and repeatability results;
- locked production evidence record.

## What to build

Close the production-hardening loop for the selected Final Spec v1.2 flow. Calibrate existing semantics and validate retained-state/recovery behavior. Introduce no new product model or acquisition backend.

## Acceptance criteria

### Retry, cancellation, and atomicity

- [ ] Explicit Retry creates a true new attempt for support extraction, planning, render, Prompt synthesis where explicitly requested, route-B acquisition, route-A fallback and Evidence operations.
- [ ] Same-attempt replay remains idempotent where supported.
- [ ] Cancellation correctness never depends on cancellation finishing before stale work returns.
- [ ] OOM/kernel/model failure during support/render/Prompt/SAM/Evidence/Lift never publishes partial Ready artifacts.
- [ ] Atomic publication is validated for support, bootstrap, plan segment, RGB/View, Prompt artifact, acquisition result, ProposalSet, Decision, Stable Mask, per-view Evidence and Candidate.
- [ ] RGB failure preserves last valid preview only as stale/not-current and exposes Retry.
- [ ] Lift failure preserves stable inputs and leaves Candidate unchanged/not-current.

### Service availability and recovery

- [ ] Native editor startup and native tools remain usable while the Companion is Connecting or Unavailable.
- [ ] Steady heartbeat is lightweight and never repeats checkpoint hashing or full compatibility validation.
- [ ] First connection, recovery, and Companion Instance replacement run exact Runtime Profile validation.
- [ ] Exactly one initialized Companion-owned Active Model Manifest is bound; the browser never selects a model.
- [ ] Busy, task progress, and task-local failure do not change AI Select Availability.
- [ ] Same-identity connection interruption retries only the current matching operation once under a new attempt ID.
- [ ] Changed Companion/runtime/model identity preserves inspectable target state and performs no silent work replay.
- [ ] Ordinary UI exposes no endpoint, model selector, Ping, manual readiness check, raw diagnostic, or dedicated recovery action.

### Route-B layered failure behavior

- [ ] Invalid support fails to Limited/unavailable with actionable local/user-added recovery.
- [ ] Insufficient 3D-guided Prompt support fails to Review/Failed, not silent oversized success.
- [ ] Provider returns no hidden final Mask, Assessment, Participation or Evidence.
- [ ] Attempt-level backend diagnostics have exactly one authority on the acquisition result envelope.
- [ ] ProposalSet dedup/clustering and selected/ambiguous/unavailable are repeatable.
- [ ] Every Decision binds exact target/context/View/acquisition attempt and `proposalSetArtifactDigest`.
- [ ] Proposal ID collision across attempts cannot satisfy Decision membership.
- [ ] Ambiguous retains proposals, publishes no Stable Mask and never triggers automatic route-A fallback.
- [ ] Unavailable after successful acquisition remains acquisition-ready/decision-unavailable, publishes no Stable Mask, and never triggers automatic route-A fallback.
- [ ] Technical backend/protocol/OOM failure produces no fabricated unavailable Decision.
- [ ] Neighbour contamination, Prompt inconsistency, clipping, fragmentation and Assessment Review never trigger automatic fallback.
- [ ] Per-view technical failure preserves View/RGB/prior Stable Mask and exposes Retry, eligible route-A fallback, manual correction or Exclude.
- [ ] User Confirmed Stable Mask cannot be overwritten by automatic refresh/fallback.
- [ ] Corrected Stable Mask does not create tracker memory or refresh unrelated Views.

### Route-A B2 fallback

- [ ] Fallback triggers only for enumerated technical/capability reasons.
- [ ] Every fallback has a distinct attempt, parent attempt and reason.
- [ ] Route-B failure remains inspectable after fallback success.
- [ ] Route-A ProposalSet traverses the same Decision, Assessment and Publication layers.
- [ ] Route-A Auto Good uses the same or stricter thresholds and contamination gates.
- [ ] Route-A/route-B/backend identities cannot collide.
- [ ] No undisclosed fallback occurs.

### Backend registry and future extensions

- [ ] Backend descriptor and actual bundle structure cannot contradict each other.
- [ ] Route-B bundle has perView and no sequence extension.
- [ ] Unknown/stale backend identity fails before inference or mutation.
- [ ] Unsupported sequence/reference operations fail before state mutation.
- [ ] Optional C/D schemas remain forward-compatible with current RGB, ProposalSet, publication and P/N/V artifacts.
- [ ] Future C/D hardening is out of scope unless a separate ADR adopts one.

### Legacy generated-view migration

- [ ] `GeneratedViewMaskResponse.assessment` is absent from the current provider result path.
- [ ] `maskSource: 'propagated'` is not used as generic route-B provenance.
- [ ] `GeneratedViewMaskPropagation` is not the generic diagnostics authority.
- [ ] controller performs no direct provider-response Stable publication or Participation policy.
- [ ] legacy `generated-view-mask/v1` payload/cache cannot validate against the current result/ProposalSet contract.
- [ ] migration rejects incompatible legacy artifacts rather than structurally rebinding them.
- [ ] current User Confirmed Stable Masks remain authoritative across migration.
- [ ] route-A compatibility adapter emits current result/ProposalSet/Decision artifacts and remains visibly route A.

### Dirty/stale and retained state

- [ ] Stress stale-result rejection across Anchor/support/bootstrap/segment/View/RGB/Prompt/backend/attempt churn, Stop, Restart, Suspended/Undo, Evidence recomputation and cancellation.
- [ ] Generate More appends without dirtying prior completed artifacts.
- [ ] Prompt-only regeneration does not mutate Stable Mask or Evidence.
- [ ] No Mask refresh/fallback automatically Re-Lifts.
- [ ] Ambiguous/unavailable review artifacts without Stable replacement do not dirty exact prior Evidence solely by existing.
- [ ] Evidence failure preserves RGB/View/Stable/Gallery/proposal review/prior Candidate.
- [ ] Reference Contributor failure does not block valid RGB or successful Direct Evidence.
- [ ] Offline/upgrade/incompatible states preserve native SuperSplat and expose recovery.

### Calibration

- [ ] Calibrate support sampling count, ordering, quality and resource cap.
- [ ] Calibrate Camera observer placement, preview behavior and inference resolutions.
- [ ] Calibrate sparse planner budget, marginal gain, diversity, early stop and Generate More segment size.
- [ ] Calibrate Prompt point/Box/ROI/local-negative/Mask-input policies.
- [ ] Calibrate ProposalSet dedup/clustering and hard-consistency gates.
- [ ] Calibrate selected/ambiguous/unavailable boundaries.
- [ ] Report unavailable Decision rate separately from technical acquisition-failure rate.
- [ ] Calibrate route-B acceptable-mask rate, neighbour contamination and manual correction burden.
- [ ] Calibrate B2 fallback technical eligibility and same-or-stricter route-A trust threshold.
- [ ] Calibrate per-view scheduler concurrency and peak VRAM envelope.
- [ ] Calibrate Core/Context/Evidence Working Set and Render Working Set parity, including support/bootstrap-seed expansion.
- [ ] Calibrate positive/boundary/local-negative Mask policy and P/N/V margins.
- [ ] Validate mixed/unobserved classifications under repeated atomic accumulation.
- [ ] Calibrate Coverage, Readiness, assessment and cross-view false-positive/false-negative behavior.

### Release interaction gate

- [ ] Ticket 07B drag/collapse/Space-hide behavior works across Anchor, Generated and User-added correction surfaces.
- [ ] No stale palette hit region remains after move/collapse/hide/disposal.
- [ ] Gallery exposes render/acquisition/decision/Mask/Participation/Evidence separately.
- [ ] Gallery distinguishes acquisition technical failure from Decision unavailable.
- [ ] Fallback provenance and ambiguous/unavailable review remain understandable without exposing a misleading confidence percentage.

### Production identity record

- [ ] Record exact raster/Evidence/runtime/model/backend/Prompt/acquisition-result/ProposalSet/decision/assessment/publication/planner identities.
- [ ] Validate RGB-only versus RGB+Evidence parity for same raster identity and inputs.
- [ ] Inject Evidence RGB-digest mismatch and verify no publication/rebinding.
- [ ] Validate incompatible renderer/acquisition/runtime migration blocks stale reuse until explicit recovery.
- [ ] Distinguish support/Prompt/acquisition diagnostics from formal P/N/V and reference checks from production same-decision validation.

## Failure / recovery criteria

- Every injected failure documents retained state, disabled operations and recovery.
- No failure silently downgrades to stale-but-applicable Candidate, approximate attribution, hidden Top-1 Mask, fabricated unavailable Decision or undisclosed fallback.
- Renderer/backend/runtime incompatibility disables production application without destroying inspectable artifacts or mutating Native Selection.
- Unsupported optional extension calls produce structured capability failure and no dirty-state mutation.
- Interaction failure cannot leave a permanent uneditable image region.

## Validation

- full repository checks
- locked GPU/model route-B fault injection
- support/bootstrap/planner fault injection
- same-binding Retry/cache tests
- support/bootstrap/segment/View/RGB/Prompt/backend stale-result tests
- Generate More append-only preservation tests
- selected/ambiguous/unavailable repeatability
- unavailable-versus-technical-failure matrix
- exact Decision-to-ProposalSet digest/attempt tests
- proposal ID collision across attempts
- single backend-diagnostics authority tests
- technical fallback eligibility matrix
- route-A same-or-stricter threshold validation
- User Confirmed authority preservation
- legacy generated-view contract/cache migration rejection
- capability bundle/dispatch tests
- unsupported sequence/reference no-mutation tests
- Ticket 07B browser interaction release walkthrough
- Ticket 02C fake-timer heartbeat/backoff, single-flight, instance-replacement, and availability walkthrough
- RGB-only versus RGB+Evidence parity
- Stable Mask/RGB digest mismatch
- renderer/acquisition migration invalidation and recovery
- reference/production identity separation
- frozen route-B benchmark calibration
- atomic repeatability/classification stability
- stale async stress
- Review false-positive/false-negative evaluation

## Non-goals

- No acquisition-route selection; route B is selected.
- No A/B/C/D comparison gate.
- No tracker/hybrid implementation or hardening without a separate future ADR.
- No new generic cross-view semantic identity classifier.
- No Candidate provenance UI.
