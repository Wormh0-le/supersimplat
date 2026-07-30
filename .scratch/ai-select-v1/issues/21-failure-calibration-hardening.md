# 21 — Retry / Cancellation / OOM / Atomic Publication + Calibration Hardening

Status: blocked — waits for complete v1.3 flow

Blocked by: 20, 18, 02C, 07B, 08B, 10, 13

## Final Spec mapping

- Final Spec v1.3 §§4–6, 14–25
- ADR 0013
- ADR 0015
- ADR 0016

## Purpose

Close production failure, calibration and release behavior for the simplified SAM 3 Image + local multi-view flow. Introduce no new Prompt family, backend registry, tracker or automatic fallback.

## Required hardening

### Runtime and readiness

- current Active Model Manifest is the SAM 3 Image instance adapter from 04C;
- historical Multiplex-only manifests fail current compatibility;
- Native SuperSplat remains usable while Connecting/Unavailable;
- heartbeat is lightweight and full validation runs only on connection/recovery/Instance change;
- Busy and task-local failures do not change service Availability.

### Retry, cancellation and atomicity

- explicit Retry creates a new render, geometry, plan, Prompt, Mask, Evidence or Lift attempt as applicable;
- same-attempt replay is idempotent where supported;
- cancellation correctness relies on stale identity rejection;
- OOM/model/kernel failure publishes no partial Mask, logits, geometry, Evidence or Candidate;
- User Confirmed Stable Mask cannot be overwritten automatically.

### SAM 3 Image behavior

- no current static path instantiates Multiplex video predictor or private tracker-head session;
- one-point multimask returns at most three candidates;
- Box/multiple-Point/refinement returns at most one candidate;
- previous logits bind exact same-image lineage;
- binary Brush cannot validate as logits;
- Negative Box, Prompt Brush, Mask Constraints and Text are absent from current schema/UI;
- Paint/Erase never enter model requests;
- semantic unavailable differs from technical inference failure.

### Geometry and local Views

- TargetGeometryHint is bounded, deterministic and non-ownership;
- local View count, offsets and framing are calibrated for useful target projection;
- invalid/blank/clipped Views fail conservatively;
- Generate More appends a bounded local batch and preserves completed artifacts;
- no room-scale free-space/adaptive planner is introduced.

### Mask Review and Lift Readiness

- Prompt consistency, clipping, fragmentation and gross Box spill are calibrated as Mask Review;
- `propagation-uncertain` is absent;
- `weak-gaussian-support` is evaluated only by Ticket 13 Lift Readiness;
- Good/Review/Failed defaults and User Confirmed authority are stable;
- Lift Readiness coverage/diversity calibration remains separate from per-View Mask quality.

### Migration

Reject or isolate:

- static SAM 3.1 Multiplex artifacts and manifests;
- `generated-view-mask/v1` cache;
- provider-returned Assessment coupling;
- `maskSource: 'propagated'` generic provenance;
- Negative Box/Mask Constraint Prompt artifacts;
- generic backend registry, Route B/C/D and automatic Route-A fallback state.

Existing User Confirmed Stable Masks survive when their own exact RGB/Mask identity remains valid.

### Interaction release gate

- 07B palette exposes Positive Point, Negative Point, Positive Instance Box, Paint and Erase only;
- drag/collapse/Space-hide leaves no stale hit region;
- Gallery exposes Render, Prompt, Mask inference, Mask Review, Participation and Evidence separately;
- no obsolete backend/fallback/tracker controls or Prompt Brush/Negative Box actions appear.

## Acceptance criteria

- [ ] full current Runtime Profile admits only the 04C static adapter;
- [ ] all async artifact families pass Retry/stale/cancellation/OOM atomicity tests;
- [ ] static Multiplex/private-head call audit is clean;
- [ ] multimask/single-mask/refinement policies are repeatable;
- [ ] removed Prompt schemas and old cache/manifests fail closed;
- [ ] TargetGeometryHint/local View resource envelope is calibrated;
- [ ] Mask Review and Lift Readiness reasons are correctly separated;
- [ ] semantic unavailable and technical failure are separately presented;
- [ ] User Confirmed authority survives refresh/migration;
- [ ] Evidence/Lift failure preserves Views and Stable Masks;
- [ ] current Gallery/palette interaction release checks pass;
- [ ] production identity record binds renderer, SAM image adapter, Prompt, geometry, review and Evidence policies.

## Validation

- full repository checks;
- locked SAM 3 Image GPU fault injection;
- static Multiplex absence audit;
- Prompt schema/migration fixtures;
- one-point multimask and single-mask refinement repeatability;
- TargetGeometryHint/local View stress;
- Mask Review/Lift Readiness calibration matrix;
- stale async stress and User Confirmed preservation;
- Ticket 07B browser interaction walkthrough;
- Ticket 02C readiness/Instance replacement walkthrough;
- RGB/Evidence parity and Candidate atomicity.

## Non-goals

- No video tracking or Multiplex production hardening.
- No backend route comparison.
- No automatic Route-A fallback.
- No new Prompt family.
- No Candidate provenance UI.
