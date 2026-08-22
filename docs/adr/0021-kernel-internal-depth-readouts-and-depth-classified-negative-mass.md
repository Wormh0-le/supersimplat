# ADR 0021: Kernel-internal depth readouts and depth-classified Negative Mass

Status: accepted (companion to Final Spec v2.0; accepted 2026-08-22)

Date: 2026-08-22

## Context

The next architecture derives a precision-first Conservative Seed Support from
Anchor production Direct Evidence. Two failure modes motivated a depth signal:
CPU first-hit mean projection lets floaters and foreground translucent splats
steal first-hit support, and a single undifferentiated Negative Mass channel
cannot distinguish leakage in front of the local surface from true background
behind it — both feed directly into Reliability Weighting quality.

A standalone rendered-depth seam (new protocol artifact, back-projection,
association tolerances, identity) was evaluated and deferred: a scalar depth
image does not identify a Gaussian, nearest-mean association reintroduces the
approximation it was meant to remove, and an ID-buffer readout is the same
kernel work as the chosen alternative. The Direct Evidence kernel already
computes per-Gaussian `alpha × transmittance` weights with camera-space depth
available at every contribution, so the needed signals are additional readouts
of an existing authoritative computation, not a new visibility authority.

## Decision

1. Add an expected-depth channel (`Σ wᵢ·zᵢ / Σ wᵢ`) inside the production
   Direct Evidence kernel family, computed from the same accepted Gaussian
   sequence and the same `alpha × T` values. The Same Decision Source
   invariant applies; no independent re-rasterization may re-decide
   boundary-sensitive acceptance or termination.
2. Add a consensus-state-weighted soft-mask readout from the same raster
   family, consumed Companion-side only for residual computation.
3. Both readouts are kernel-internal. They are never published as standalone
   protocol artifacts and never cross the Browser/Companion boundary.
4. Revise Negative Mass semantics in place: counter-evidence is classified by
   expected depth into in-front-of-local-surface (leakage, floater) versus
   behind-it (true background at object edges). Reliability Weighting consumes
   the classified channels. The revision must not turn mask distrust into
   "not observed".
5. Authoritative whole-frame geometric visibility (rendered depth as a
   protocol artifact) stays out of scope, gated on the coverage/utility
   branches proving a need.

## Consequences

- Seed construction gains floater rejection and depth-consistent adjacency at
  near-zero marginal compute and zero protocol cost.
- Negative Mass becomes two semantically distinct channels; aggregation,
  reliability, diagnostics, and the `production-direct` Evidence identity all
  rotate to the revised contract.
- The v1.3 single-channel Negative Mass definition is superseded; consumers
  that assumed one undifferentiated ring must migrate.
- Because depth rides the Direct Evidence identity, any change to the readout
  rotates production identity like any other Evidence policy change.
- If whole-frame geometric visibility is later required, it is a separate,
  explicitly-gated seam — this ADR neither provides nor precludes it.
