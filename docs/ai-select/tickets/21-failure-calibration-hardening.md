# 21 — Attempt / Cancellation / OOM / Atomic Publication + Calibration Hardening

Status: closed — 2026-08-17; Ticket 22 is current

Blocked by: 20, 18, 02C, 07B, 08B, 13

Optional input, not blocker: 10

## Final Spec mapping

- Final Spec v1.3 §§4–6, 14–25
- ADR 0013
- ADR 0015
- ADR 0016
- ADR 0019
- Tickets 16B and 16G for current product recovery/planning-control retirement

## Purpose

Close production failure, calibration and release behavior for the simplified SAM 3 Image + local multi-view flow. Introduce no new Prompt family, backend registry, tracker, automatic fallback or product retry/planner control. Optional Ticket 10 cross-view diagnostics do not block core release closure.

## Required hardening

### Runtime and readiness

- current Active Model Manifest is the SAM 3 Image instance adapter from 04C;
- historical Multiplex-only manifests fail current compatibility;
- Native SuperSplat remains usable while Connecting/Unavailable;
- heartbeat is lightweight and full validation runs only on connection/recovery/Instance change;
- Busy and task-local failures do not change service Availability;
- Companion Instance replacement invalidates Companion-local RGB/logits refs without invalidating independent User Confirmed Stable Masks.

### Attempt identity, replay, cancellation and atomicity

- every normal new user intent creates a distinct render, geometry, plan,
  Prompt, Mask, Evidence or Lift attempt as applicable;
- same-attempt replay is idempotent where supported;
- cancellation correctness relies on stale identity rejection;
- OOM/model/kernel failure publishes no partial Mask, refinement ref, geometry, Evidence or Candidate;
- User Confirmed Stable Mask cannot be overwritten automatically;
- product surfaces expose no identical-input Render, Prompt, Mask, Evidence or
  Lift retry command; initial planning failure retains the single accepted
  failure-only retry exception and creates a fresh bounded planning attempt.

### SAM 3 Image behavior

- no current static path instantiates Multiplex video predictor or private tracker-head session;
- every inference request resolves exact authoritative RGB bytes or current Companion RGB ref;
- digest-only RGB input fails before inference;
- every Point/Box/refinement request returns at most one candidate;
- actual previous logits remain Companion-local and refs bind exact same-image/Companion/candidate lineage;
- Companion replacement/expired ref falls back to fresh no-logits inference;
- binary Brush cannot validate as a logits ref;
- Negative Box, Prompt Brush, Mask Constraints and Text are absent from current schema/UI;
- Paint/Erase never enter model requests;
- semantic unavailable differs from technical inference failure.

### Geometry and local Views

- TargetGeometryHint is bounded, deterministic and non-ownership;
- local View count, offsets and framing are calibrated for useful target projection;
- invalid/blank/clipped Views fail conservatively;
- initial planning schedules the accepted `4–8` automatic Generated Views,
  excluding the Anchor and User-added Views; its
  failure-only retry preserves valid completed artifacts and starts a distinct
  planning attempt;
- Generate More and Regenerate Plan/Auto Views are absent from the current
  product surface;
- no room-scale free-space/adaptive planner is introduced.

### Mask Review and Lift Readiness

- Prompt consistency, clipping, fragmentation and gross Box spill are calibrated as Mask Review;
- `propagation-uncertain` is absent;
- weak/low Gaussian visibility support is evaluated only by Ticket 13 Lift Readiness;
- optional Ticket 10 cross-view conflict diagnostics do not own visibility readiness and are not required for release;
- Good/Review/Failed defaults and User Confirmed authority are stable;
- Lift Readiness coverage/diversity calibration remains separate from per-View Mask quality.

### Migration

Reject or isolate:

- static SAM 3.1 Multiplex artifacts and manifests;
- `generated-view-mask/v1` cache;
- provider-returned Assessment coupling;
- `maskSource: 'propagated'` generic provenance;
- Negative Box/Mask Constraint Prompt artifacts;
- raw logits tensors in browser Prompt/request state;
- generic backend registry, Route B/C/D and automatic Route-A fallback state;
- former Ticket 06 production-fallback language.

Existing User Confirmed Stable Masks survive when their own exact RGB/Mask identity remains valid.

### Interaction release gate

- 07B palette exposes Positive Point, Negative Point, Positive Instance Box, Paint and Erase only;
- drag/collapse/Space-hide leaves no stale hit region;
- Gallery exposes Render, Prompt, Mask inference, Mask Review, Participation and Evidence separately;
- no identical-input Render/Prompt/Mask retry or persistent planner action is
  present; initial planning failure recovery is the only product retry icon;
- no obsolete backend/fallback/tracker controls or Prompt Brush/Negative Box actions appear.

## Acceptance criteria

- [x] full current Runtime Profile admits only the 04C static adapter.
- [x] all async artifact families pass distinct-attempt, idempotent replay,
      stale-result, cancellation and OOM atomicity tests.
- [x] static Multiplex/private-head call audit is clean.
- [x] provider request always contains resolvable authoritative RGB.
- [x] opaque logits refs never expose raw tensors and invalidate on Companion replacement.
- [x] multimask/single-mask/refinement policies are repeatable.
- [x] removed Prompt schemas and old cache/manifests fail closed.
- [x] TargetGeometryHint/local View resource envelope is calibrated.
- [x] The `4–8` initial automatic Generated-View range passes latency, memory,
      failure and partial-usable-output calibration without fabricating Ready
      Views.
- [x] Mask Review and Lift Readiness reasons are correctly separated.
- [x] core release passes with Ticket 10 absent.
- [x] semantic unavailable and technical failure are separately presented.
- [x] User Confirmed authority survives refresh/migration.
- [x] Evidence/Lift failure preserves Views and Stable Masks.
- [x] current Gallery/palette interaction release checks pass.
- [x] obsolete product retry/planning commands remain absent and initial
      planning failure recovery is the only retry exception.
- [x] production identity record binds renderer, SAM image adapter, Prompt, geometry, review and Evidence policies.

## Validation

- full repository checks;
- locked SAM 3 Image GPU fault injection;
- static Multiplex absence audit;
- authoritative RGB payload/ref resolution;
- Prompt schema/migration fixtures;
- Point/Box/refinement single-result repeatability;
- opaque logits ref and Companion-replacement invalidation;
- TargetGeometryHint/local View stress;
- Mask Review/Lift Readiness calibration matrix;
- release walkthrough without Ticket 10;
- distinct-attempt/replay/stale async stress and User Confirmed preservation;
- Ticket 07B browser interaction walkthrough;
- Ticket 02C readiness/Instance replacement walkthrough;
- RGB/Evidence parity and Candidate atomicity.

## Non-goals

- No video tracking or Multiplex production hardening.
- No backend route comparison.
- No automatic Route-A fallback.
- No new Prompt family.
- No Candidate provenance UI.

## Implementation record — 2026-08-17

- Runtime readiness now publishes one fail-closed production identity record
  that binds the locked renderer/runtime, current SAM 3 Image Model Manifest,
  Prompt compiler/synthesis, TargetGeometryHint/local-View, Mask Review,
  production Direct Evidence/aggregation and Lift Readiness identities. The
  browser validates its checksum and all cross-capability bindings before
  reporting Available.
- ADR 0019 records the production Candidate, identity and bounded replay
  decision without changing Ticket 22's legacy-contraction ownership.
- Candidate Re-Lift now consumes exact current `production-direct` Evidence
  artifacts, evaluates and publishes Ticket 13 Lift Readiness from that exact
  aggregation, and publishes a `production-ready` Candidate only for Limited
  or Ready. Native application
  remains gated by the exact accepted `productionIdentityDigest` carried by
  the Candidate publication/application record. The
  complete-Contributor Candidate path remains reference-only for Ticket 22.
- Direct Evidence, Prompt synthesis and Candidate Re-Lift gained replayable
  execution admissions. Same-attempt success/failure is idempotent, normal
  new intents use distinct IDs, and OOM/failure cannot publish a partial
  artifact. Existing browser stale-result rejection remains the cancellation
  correctness boundary.
- Browser exit/restart sends exact target disposal to the Companion. Admission,
  Prompt/result and logits cleanup is target-identity-safe, so delayed Target-A
  cleanup cannot erase a newer Target-B attempt or reusable runtime caches.
- Partial local plans retain failed slots as inspectable Excluded Views without
  rendering or fabricating RGB Ready. All-failed initial plans still fail and
  keep the sole failure-only fresh planning attempt.
- Mask Review thresholds now have a digest-bound descriptor. Ticket 13
  readiness thresholds are promoted to `lift-readiness/production-v1`; weak
  Visible Mass remains outside Mask Review and Ticket 10 remains optional.
- Calibration measurements, locked GPU results and release checks are recorded
  in [Ticket 21 failure and calibration hardening](../benchmarks/21-failure-calibration-hardening.md).
- Final validation passed: `rtk npm test` (650 browser/editor tests and 483
  Companion tests, with two expected environment-gated skips), `rtk npm run
lint`, `rtk npm run lint:locales`, `rtk npm run build`, four locked SAM 3
  Image GPU tests including OOM fault injection, seven locked Direct Evidence
  GPU tests, JSON/diff checks, and clean Standards/Spec review axes.
