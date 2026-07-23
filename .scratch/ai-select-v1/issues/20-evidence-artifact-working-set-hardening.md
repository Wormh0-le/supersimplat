# 20 — Same-decision GPU Evidence + artifact / working-set hardening

Status: ready-for-agent — v2.2 re-audited

Blocked by: 19, 14, 09

## Final Spec mapping

- Final Spec v1.1 §§16–19, 30 Stage 3–5, 31–32
- ADR 0013
- DG-20
- MVP Phase 7 production Evidence

## Inputs / preconditions

- Reference P/N/V policy and fixtures from Ticket 14
- Validated large-scene authoritative RGB / Render Working Set path
- Stable Mask artifacts
- 10–20+ View Gallery
- Locked/pinned CUDA runtime ownership

## Outputs / handoff artifacts

- Production same-decision Direct Evidence path
- Versioned per-view GaussianEvidenceArtifact/cache
- Evidence Working Set mapping
- Complete Contributor debug/reference boundary
- Mask/Evidence/thumbnail lifecycle and memory profile

## What to build

Implement the production path that accumulates per-Gaussian P/N/V from the same authoritative raster decision source as RGB. Do not publish complete per-pixel Contributor in the normal product path. Harden artifact identity, memory, GC, and Working Set behavior.

## Acceptance criteria

- [ ] Production Evidence uses the same accepted Gaussian sequence, alpha, incoming T, `alpha × T`, validity, and termination decisions as authoritative RGB.
- [ ] One literal CUDA launch is not required, but later passes may not independently re-decide boundary-sensitive acceptance/termination.
- [ ] Production output is per-view Stable-ID-indexed P/N/V plus optional boundaryMass, not a complete per-pixel Contributor buffer.
- [ ] Render Working Set remains complete for occlusion/transmittance; Evidence Working Set only gates P/N/V writes.
- [ ] Stable global-to-Evidence-local mapping rejects missing/duplicate/out-of-range IDs.
- [ ] GaussianEvidenceArtifact binds Camera, RGB, Stable Mask, policy, Render/Evidence Working Sets, Stable IDs, and implementation/runtime identity.
- [ ] Reference-vs-production P/N/V agrees within declared numerical policy and produces stable final classification.
- [ ] Repeat identical inputs enough times to characterize atomicAdd reduction-order variation; threshold margins must prevent classification flips.
- [ ] No silent truncation, overflow, nearest/top-k/distance/center fallback, or best-effort publication.
- [ ] Existing complete Contributor remains available only behind explicit debug/reference capability and may fail without blocking successful RGB/Direct Evidence.
- [ ] Per-view artifact reuse validates every dependency and supports Exclude/reinclude and incremental Re-Lift.
- [ ] Measure latency, VRAM, write bandwidth, register pressure, and atomic contention on representative scenes.
- [ ] Mask and Evidence artifact storage has ownership/GC rules; current/referenced Stable Mask and Candidate inputs are never prematurely collected.
- [ ] Restart Target and Regenerate Auto Views release unreferenced target-local artifacts without invalidating valid shared caches.
- [ ] Gallery thumbnail/texture lifecycle is bounded under 10–20+ Views.
- [ ] Working-set memory for RGB/Mask/Evidence/reference Contributor/thumbnail artifacts is measured and documented.

## Failure / recovery criteria

- [ ] Evidence OOM/kernel/artifact failure preserves RGB/View/Stable Mask and previous Candidate; no partial Evidence publishes.
- [ ] GC failure cannot delete current Stable Mask, current per-view Evidence, or current Candidate inputs.
- [ ] Reference Contributor failure affects diagnostics only.

## Validation

- Locked GPU same-decision tests
- Reference-vs-production P/N/V and classification fixtures
- Full versus spatial Render Working Set Evidence parity
- Repeated-run classification stability
- Large-scene memory/latency profile
- Mask/Evidence GC lifecycle tests
- Gallery resource stress

## Non-goals

- No planner/assessment threshold calibration; Ticket 21 owns calibration
- No DG-14 provenance UI