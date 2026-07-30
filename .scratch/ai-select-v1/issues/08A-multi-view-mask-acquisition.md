# 08A — Multi-view Mask acquisition spike + 3D-guided per-Key-View SAM

Status: planned — D-double-prime architecture closed by DG-24; production acquisition route remains spike-gated

Blocked by: 08

Blocks: 09

## Final Spec mapping

- Final Spec v1.1 §§18–20, 23–24, 27–32
- Final Spec v1.1 Amendments 003 and 004
- DG-24
- Ticket 06 progressive Generated View baseline
- Ticket 07 ViewAssessmentPolicy

## Purpose

Turn a confirmed object-level Anchor Stable Mask, a TargetBootstrapArtifact, and sparse authoritative Key-View RGBs into reliable per-view object Masks for final P/N/V lifting.

The default candidate production route is enhanced 3D-guided independent SAM inference per Key View. Object tracking is evaluated as an optional augmentation, not assumed as a mandatory dependency.

## Inputs / preconditions

- confirmed Anchor Stable Mask;
- current Target Context and exact Anchor/RGB/Mask identity;
- Ticket 08 TargetBootstrapArtifact;
- Ticket 08 immutable SparseKeyViewPlanSegment artifacts;
- authoritative RGB for every Key View;
- Ticket 04B truthful visual-Prompt capabilities;
- Ticket 07 local Mask assessment;
- Stable Mask registry and stale-result gate;
- current projected-support + single-frame SAM baseline.

## Outputs / handoff artifacts

- bounded multi-view Mask acquisition spike report;
- acquisition-route ADR;
- versioned 3D-guided Prompt synthesis policy;
- per-Key-View Mask acquisition attempts and diagnostics;
- progressive per-view Mask proposal / Stable / Review / Failed states;
- explicit backend/model/runtime identity;
- optional tracker/hybrid capability contract only if selected;
- exact dirty/stale dependencies for Ticket 12;
- acquisition status for Ticket 09.

# Phase 0 — finding-the-unknowns acquisition spike

Production closure MUST NOT assume that tracking is necessary.

Compare at least:

```text
A. current projected-support + independent single-frame SAM
B. enhanced 3D-guided per-Key-View SAM
C. object-level VOS tracker over an ordered/dense rendered sequence
D. hybrid: independent Key-View references + tracker between references
```

All routes use authoritative gsplat RGB and comparable object/view fixtures.

Evaluate:

- per-view acceptable-mask rate;
- neighbouring-instance contamination;
- identity-switch rate where applicable;
- Mask drift where applicable;
- recovery after manual correction;
- sensitivity to sparse viewpoint change;
- occlusion and reappearance;
- poor/fragmented 3DGS rendering;
- number of required Key / auxiliary frames;
- latency and peak VRAM;
- deterministic replay and resource cleanup;
- deployability, dependency, and licensing constraints;
- final Gaussian precision / recall;
- background Gaussian contamination;
- Mixed / Uncertain ratio;
- user correction and Add / Remove burden proxy.

The spike output MUST state:

- selected default route or explicit no-go;
- supported Prompt families;
- backend/model/runtime identity;
- supported resolution and bounded View count;
- resource envelope;
- fallback conditions;
- known failure signals;
- whether tracker/hybrid benefit is large enough to justify optional production capability.

Default exit rule:

```text
If enhanced 3D-guided per-Key-View SAM meets the locked
Gaussian quality, latency, and user-effort targets,
tracker augmentation is not required for v1.
```

A separate ADR locks the selected production route before this ticket closes.

# Default production contract — enhanced per-Key-View SAM

## 3D-guided Prompt synthesis

For every Key View, synthesize a deterministic PromptState from supported inputs such as:

- projected Anchor visible-support positive points;
- projected target center and extent;
- positive Box / ROI;
- local negative points or negative region outside the projected target;
- compatible projected Mask input when supported;
- object scale, clipping, and boundary diagnostics.

Prompt synthesis binds:

```text
targetContextId
scene / splat revision
Anchor CameraBinding + RGB digest
Anchor Stable Mask digest
TargetBootstrapArtifact digest
SparseKeyViewPlanSegment digest
Key-View CameraBinding + RGB digest
adapter capability digest
Prompt synthesis policy digest
PromptState digest
model / adapter / runtime identity
attempt identity
```

Unsupported Prompt types fail closed and are never silently dropped or converted.

## Independent execution

Each Key View runs an independent prompt-conditioned attempt. It does not require adjacent frames, tracker memory, or a dense sequence.

The selected route may produce:

```text
Mask Generating
Auto Stable Mask
Mask Review
Mask Failed
```

RGB Ready never waits for Mask acquisition.

## Publication

Successful output is validated and atomically published as one bound per-view Mask revision under the existing Mask registry.

Automatic acquisition MUST NOT silently replace a current user-confirmed Stable Mask. It may publish a new Review proposal or require explicit refresh/acceptance under the selected policy.

Mask failure preserves View/RGB/frustum and prior Stable Mask.

## Fallback

The Ticket 06 projected-support + single-frame SAM route remains runnable as baseline and fallback.

Fallback identity and diagnostics are explicit. A fallback result is not represented as another backend.

# Optional tracker / hybrid augmentation

Tracker or hybrid production work exists only if the spike ADR selects it.

If selected, the ADR and implementation MUST define:

- capability advertisement;
- ordered auxiliary-frame contract;
- transition/resource envelope;
- tracker session identity and lifecycle;
- auxiliary / Bridge role semantics;
- correction-reference policy;
- identity-drift fail-closed behavior;
- fallback to independent per-view acquisition;
- explicit repropagation integration with Ticket 12.

Confirming a per-view correction does not automatically enter tracker memory. `Use as Tracking Reference` is a separate explicit capability-gated action.

Auxiliary / Bridge frames default Excluded from Lift. Tracker confidence remains a Mask diagnostic and is not P/N/V Evidence.

# Acceptance criteria

## Spike / ADR gate

- [ ] Frozen benchmark scenes, Key Views, optional dense sequences, and review protocol are versioned.
- [ ] Routes A–D use authoritative RGB and comparable inputs.
- [ ] Final Gaussian outcomes and user effort are reported, not only 2D Mask scores.
- [ ] Route B is treated as the default candidate and can close v1 without a tracker.
- [ ] A production acquisition-route ADR is accepted before closure.

## 3D-guided Prompt synthesis

- [ ] Prompt synthesis is deterministic and artifact-bound.
- [ ] Positive support is visibility-aware and clipped to the exact Key View.
- [ ] Box/ROI and local-negative constraints are used only when adapter capabilities support them.
- [ ] Bootstrap support is localization context, not ownership or a hard Gaussian search bound.
- [ ] Prompt synthesis diagnostics explain insufficient support, projection loss, edge clipping, and likely neighbour contamination.

## Per-view lifecycle

- [ ] RGB Ready does not wait for acquisition.
- [ ] Each Key View has an independent attempt and Retry identity.
- [ ] Same-attempt replay is idempotent; explicit Retry creates a new attempt.
- [ ] Success atomically publishes only a bound per-view Mask revision.
- [ ] Failure preserves RGB/View/frustum/prior Stable Mask.
- [ ] No partial Mask artifact becomes Stable.
- [ ] User-confirmed Stable Mask is not overwritten silently.
- [ ] Key-View role does not override Ticket 07 assessment or Participation.

## Optional tracker capability

- [ ] No tracker-specific artifact or UI is mandatory when route B is selected.
- [ ] If tracker/hybrid is selected, all additional capabilities and identities are explicit.
- [ ] Suspected identity drift becomes Review/failure, not silent Auto Good.
- [ ] Optional tracker failure can fall back to independent per-view acquisition where supported.
- [ ] Tracker confidence is not P/N/V ownership Evidence.

## Affected implementation seams

- [ ] `generated-view-controller.ts` separates RGB rendering from per-view Mask acquisition jobs.
- [ ] `generated-view-service.ts` exposes versioned acquisition requests/responses and backend identity.
- [ ] Companion state owns bounded model scheduling, replay, cancellation, and cleanup.
- [ ] `mask-registry.ts` records acquisition provenance without conflating it with Stable authority.
- [ ] readiness/capability negotiation reports the selected route and optional tracker support.

# Failure / recovery criteria

- Acquisition backend unavailable: preserve completed Views/RGB/Masks; offer baseline fallback/manual correction/Exclude.
- OOM/cancellation: publish no partial Stable Mask; retain prior artifacts; reject late results.
- Insufficient projected support: mark Review/Failed with retry, adjusted View, manual Prompt, or Exclude recovery.
- Neighbour-instance risk: fail closed to Review, not silent Auto Good.
- Stale Anchor/bootstrap/segment/View/Prompt/backend result: discard.
- Optional tracker failure: do not disable valid default per-view acquisition.

# Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run build`
- locked-runtime acquisition smoke
- frozen sparse-Key-View benchmark
- table/chairs and similar-instance contamination regression
- occlusion/reappearance and poor-render regression
- Prompt synthesis digest golden vectors
- stale Anchor/bootstrap/segment/View/Prompt/backend rejection
- baseline fallback regression
- optional tracker/hybrid benchmark only when evaluated
- final P/N/V Gaussian outcome comparison

# Non-goals

- No camera generation; Ticket 08 owns it.
- No Anchor ProposalDecision; Ticket 07A owns it.
- No mandatory tracker, Bridge View, or dense trajectory.
- No Gallery implementation; Ticket 09 owns presentation.
- No dirty-state orchestration; Ticket 12 owns it.
- No P/N/V Evidence or Gaussian ownership.
- No whole-image object inventory.
- No arbitrary part tracking requirement.
- No automatic Re-Lift.
