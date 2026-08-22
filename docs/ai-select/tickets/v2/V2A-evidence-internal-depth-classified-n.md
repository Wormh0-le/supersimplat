# V2A — Evidence-Internal Depth + depth-classified Negative Mass

Status: **planned — accepted v2.0 scope; not implemented** (see `docs/ai-select/TICKET-GRAPH-V2.md`)

Blocked by: none
Blocks: V2B, V2D, V2E

## Final Spec v2.0 mapping

- Final Spec v2.0 §5; ADR 0021
- Carry-over: v1.3 §20 same-decision rendering invariants; Ticket 20
  production same-decision Evidence identity

## Goal

Add two kernel-internal readouts to the Direct Evidence kernel family — the
expected-depth channel and the depth classification of Negative Mass — without
publishing any new protocol artifact.

## Inputs / preconditions

- Production same-decision Direct Evidence CUDA path (Ticket 20, implemented):
  `selection-service-companion/src/selection_service_companion/cuda/direct_evidence.cu`
  already computes per-Gaussian `accepted_weight = alpha × T` with
  camera-space z available per contribution;
- Direct Evidence implementation identity (exact-key validation + checksum
  binding);
- Reference (non-CUDA) backend parity requirements.

## Outputs / handoff

- Expected-depth channel `Σ wᵢ·zᵢ / Σ wᵢ` accumulated inside the kernel from
  the same accepted Gaussian sequence and `alpha × T` weights;
- Depth classification of each N contribution: in-front-of-local-surface
  (leakage/floater) versus behind-it (true background at object edges),
  relative to the local surface expected depth;
- Companion-side consumption API for V2B (seed depth-consistency filter,
  adjacency gating) and V2D/V2E (classified N into reliability weighting and
  aggregation);
- Extended Direct Evidence identity binding covering the new readouts.

## Acceptance criteria

- [ ] Expected-depth channel is computed inside the kernel from the same
      accepted sequence and weights; no independent approximate
      re-rasterization exists.
- [ ] Depth classification distinguishes front-of-surface from behind-surface
      counter-evidence; classified N is consumable by reliability weighting
      and aggregation.
- [ ] Depth classification never turns Mask distrust into "not observed":
      raw V is unweighted and unaffected.
- [ ] No standalone depth protocol artifact crosses the Browser/Companion
      boundary; authoritative whole-frame rendered depth is NOT introduced
      (parked, separately gated open question).
- [ ] Sigma/alpha/termination expressions remain aligned across kernels per
      the kernel header mandate.
- [ ] The new readouts are bound into the Direct Evidence implementation
      identity; incompatible identity fails closed.
- [ ] Reference-backend behavior is defined and tested for parity where the
      reference path runs.
- [ ] `_collect_first_hit_support` (`target_geometry.py`) is not repurposed
      into an ownership or depth source.

## Validation

- Companion CUDA/reference tests for depth channel and classification;
- identity-binding fail-closed tests;
- `rtk npm test` (includes Companion tests).

## Non-goals

- No seed computation (V2B), no consensus soft-mask readout (V2C), no
  reliability or aggregation change.
- No rendered-depth protocol artifact, no new visibility tolerance.
- No v1.3 production behavior change before supersession.
