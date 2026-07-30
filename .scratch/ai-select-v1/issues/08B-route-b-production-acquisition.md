# 08B — 3D-guided Per-View SAM 3 Image Acquisition

Status: planned — simplified v1.3 production path

Blocked by: 08A, 04C, 07

Blocks: 09

## Final Spec mapping

- Final Spec v1.3 §§9–19, 24–26
- ADR 0016

## Purpose

Implement independent instance Mask generation for each bounded local Key View using the same official SAM 3 Image adapter as Anchor acquisition.

```text
TargetGeometryHintArtifact
+ LocalKeyViewPlan
+ authoritative Key-View RGB / CameraBinding
→ project one Positive Instance Box
+ 1–3 Positive Points
+ optional 0–2 Negative Points
→ ImageInstancePromptArtifact
→ ImageInstanceMaskRequest with resolvable authoritative RGB
→ SAM 3 Image, multimask_output=false
→ one Mask or semantic unavailable
→ MaskReviewPolicy
→ automatic Stable publication or Review/manual recovery
```

No route comparison or tracker experiment blocks this ticket.

## Phase 1 — 3D-guided Prompt synthesis

Implement a deterministic service that:

- projects exact current visible geometry through the exact Key-View CameraBinding;
- creates one Positive Instance Box in authoritative pixel XYXY;
- selects 1–3 projected Positive Points inside reliable visible support;
- may add 0–2 Negative Points in clearly local background/neighbour regions;
- clips all coordinates to exact image dimensions;
- binds geometry, plan, Camera, RGB, adapter capability and synthesis policy identities;
- reports limited support/clipping diagnostics;
- fails conservatively rather than inventing an oversized target.

It MUST NOT synthesize:

- Negative Box;
- Prompt Brush or Mask Constraint;
- Text Prompt;
- concept-level normalized CXCYWH Box;
- previous logits from another View.

Generated automatic requests normally do not use previous logits. Point refinement on a correction surface may use only a valid same-View opaque ref from 04C/08A.

Prompt regeneration is distinct from inference Retry.

## Phase 2 — per-View inference

Use the 04C `ImageInstanceMaskProvider` with:

```text
multimask_output=false
```

Requirements:

- request contains exact authoritative RGB bytes or current Companion RGB ref;
- provider verifies RGB digest and dimensions before inference;
- digest-only unresolved RGB is rejected;
- independent inference per View;
- no Multiplex/video/tracker session;
- no adjacent-frame memory;
- exact request/result/Companion identity;
- at most one usable Mask;
- exact Mask dimensions and digest;
- raw score retained only as diagnostics;
- raw previous-logits tensor never crosses the browser boundary;
- explicit Retry creates a new attempt;
- RGB Ready does not wait for inference;
- technical failure publishes no partial Mask/ref/Stable state.

An empty valid result is semantic unavailable, not transport/runtime failure.

## Phase 3 — basic Mask Review

Only a returned Mask enters Ticket 07 `MaskReviewPolicy`.

Review may use:

- Point consistency;
- Positive Box overlap/spill;
- empty/full-frame validity;
- meaningful clipping ratio;
- severe fragmentation;
- obvious neighbour contamination.

It does not rerun instance candidate selection. `weak-gaussian-support` is handled only by Ticket 13 Lift Readiness.

## Phase 4 — publication

```text
Mask + Good
→ publish Auto Good Stable Mask
→ default Included

Mask + Review
→ publish Auto Review Stable Mask
→ default Excluded

Mask + Failed
→ no new automatic Stable Mask
→ Excluded

semantic unavailable
→ no new Stable Mask
→ Excluded

technical failure
→ preserve RGB and prior Stable Mask
```

User Confirmed Stable authority is never silently replaced.

## Phase 5 — orchestration and migration

Refactor Generated View orchestration into:

```text
local plan
→ render and publish RGB
→ synthesize instance Prompt
→ infer SAM 3 Image Mask from exact RGB request
→ review
→ publish
```

Migration requirements:

- retire/isolate `GeneratedViewMaskResponse.assessment` provider coupling;
- retire generic `maskSource: 'propagated'`;
- retire static Multiplex/propagation execution;
- reject `generated-view-mask/v1` cached payloads as current;
- reject Negative Box/Mask Constraint Prompt artifacts;
- reject raw logits tensors or stale Companion refs in browser requests;
- remove generic backend registry/route/fallback dependencies;
- preserve User Confirmed Stable Masks and manual corrections.

## Removed v1 requirements

08B no longer owns:

- generic ProposalSet clustering;
- selected/ambiguous/unavailable Decision policy for normal Generated Views;
- material-distinct candidate analysis;
- backend registry dispatch;
- Route-A automatic fallback;
- sequence extension;
- tracker references or repropagation;
- adaptive planner logic.

Anchor one-point candidate choice remains Ticket 07A only.

## Acceptance criteria

### Prompt synthesis

- [ ] exact geometry/View inputs produce deterministic Prompt artifacts.
- [ ] Generated Prompts contain one Positive Box, 1–3 Positive Points and at most two Negative Points.
- [ ] removed Prompt families never appear.
- [ ] insufficient support yields structured Limited/Review recovery.

### Inference

- [ ] every Generated View uses official SAM 3 Image single-mask inference.
- [ ] every request resolves exact authoritative RGB and matching dimensions.
- [ ] no current path creates Multiplex/video/tracker session.
- [ ] result contains at most one usable Mask.
- [ ] semantic unavailable differs from technical failure.
- [ ] Retry/stale/cancellation/OOM behavior is fail-closed.
- [ ] raw logits tensors do not cross the browser boundary.

### Review/publication

- [ ] only returned Masks are reviewed.
- [ ] Good/Review/Failed use Ticket 07 semantics.
- [ ] `propagation-uncertain` and `weak-gaussian-support` are absent from per-View Mask Review.
- [ ] automatic Stable publication respects User Confirmed authority.
- [ ] no publication creates P/N/V or Re-Lifts.

### Migration

- [ ] legacy propagated/provider-assessment contracts are not current.
- [ ] old Multiplex/Prompt schema artifacts cannot attach.
- [ ] no backend registry or automatic fallback is required.
- [ ] existing manual/User Confirmed Masks remain inspectable and authoritative.

## Validation

- deterministic 3D projection fixtures;
- authoritative RGB payload/ref fixture;
- SAM 3 Image per-View GPU fixture;
- generated single-mask cardinality test;
- clipping/fragmentation/Box-spill review fixtures;
- semantic-unavailable versus technical-failure fixture;
- stale/Retry/OOM/cancellation tests;
- Companion-replacement ref rejection;
- legacy Multiplex/cache/schema rejection;
- controller separation tests;
- repository test/lint/locales/build.

## Non-goals

- No video tracking or Multiplex workload.
- No generic candidate cluster/ranker.
- No backend registry/Route B-C-D abstraction.
- No automatic Route-A fallback.
- No P/N/V or Candidate.
