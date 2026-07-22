# 20 — GPU Evidence aggregation + Mask/thumbnail working-set hardening

Status: ready-for-agent

Blocked by: 19, 14, 09

## Final Spec mapping

- §89 engineering items 15/17/24
- MVP Phase 7 performance

## Inputs / preconditions

- Large-scene cached render/contributor path
- Lifting pipeline
- Mask version artifacts
- 10–20+ View Gallery

## Outputs / handoff artifacts

- Production Evidence aggregation path
- Mask artifact lifecycle/GC
- Thumbnail/texture lifecycle
- Working-set profile

## What to build

Harden the evidence/artifact working set independently from scene rendering. Use GPU/tensor aggregation
when measured scale requires it; bound mask and thumbnail resource growth without breaking versioned
artifact correctness.

## Acceptance criteria

- [ ] Measure Evidence aggregation cost/memory on representative large scenes before selecting CPU vs GPU/tensor implementation.
- [ ] When naive/CPU aggregation is not production-suitable, implement a production GPU/tensor aggregation path preserving Evidence Policy semantics.
- [ ] GPU Evidence output matches reference fixtures within defined numeric tolerance and preserves unobserved/uncertain semantics.
- [ ] Mask artifact storage has explicit ownership and GC rules for superseded editing/auto/stable versions; current/referenced Stable artifacts are never collected prematurely.
- [ ] Restart Target and Regenerate Auto Views release target-local unreferenced artifacts without invalidating shared valid caches.
- [ ] Gallery thumbnail/texture lifecycle is bounded under 10–20+ Views and releases hidden/disposed target resources correctly.
- [ ] Working-set memory for RGB/contributor/mask/thumbnail artifacts is measured and documented.
- [ ] Artifact/cache reuse always validates target/view/mask/dependency revision identity before reuse.

## Failure / recovery criteria

- [ ] GPU aggregation OOM/failure fails closed; Ticket 21 completes end-to-end OOM recovery/atomic-publication validation.
- [ ] GC failure must not delete current Stable Mask or current Candidate inputs.

## Affected seams

- Companion Evidence aggregation
- src/ai-select mask artifact lifecycle
- Gallery thumbnail/texture lifecycle
- Memory profiling harness

## Validation

- Reference-vs-GPU evidence equivalence tests
- Locked GPU large-scene memory/profile
- Mask GC lifecycle tests
- Gallery 10–20+ resource stress

## Non-goals

- No planner/assessment threshold calibration
- No DG-14 provenance UI
