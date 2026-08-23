# ADR 0021: Kernel-internal depth readouts and depth-classified Negative Mass

Status: partially superseded by ADR 0023 (accepted 2026-08-22; partial supersession accepted 2026-08-23)

Date: 2026-08-22

## Context

The next architecture derives a precision-first Conservative Seed Support from Anchor production Direct Evidence. Two failure modes motivated a depth signal: CPU first-hit mean projection lets floaters and foreground translucent splats steal first-hit support, and a single undifferentiated Negative Mass channel cannot distinguish leakage in front of the local surface from true background behind it — both feed directly into Reliability Weighting quality.

A standalone rendered-depth seam (new protocol artifact, back-projection, association tolerances, identity) was evaluated and deferred: a scalar depth image does not identify a Gaussian, nearest-mean association reintroduces the approximation it was meant to remove, and an ID-buffer readout is the same kernel work as the chosen alternative. The Direct Evidence kernel already computes per-Gaussian `alpha × transmittance` weights with camera-space depth available at every contribution, so the needed signals are additional readouts of an existing authoritative computation, not a new visibility authority.

## Decision at acceptance

1. Add an expected-depth channel (`Σ wᵢ·zᵢ / Σ wᵢ`) inside the production Direct Evidence kernel family, computed from the same accepted Gaussian sequence and the same `alpha × T` values. The Same Decision Source invariant applies; no independent re-rasterization may re-decide boundary-sensitive acceptance or termination.
2. Add a consensus-state-weighted soft-mask readout from the same raster family, consumed Companion-side only for residual computation.
3. Both readouts are kernel-internal. They are never published as standalone protocol artifacts and never cross the Browser/Companion boundary.
4. Revise Negative Mass semantics in place: counter-evidence is classified by expected depth into in-front-of-local-surface versus behind-it. Reliability Weighting consumes the classified channels.
5. Authoritative whole-frame geometric visibility stays out of scope unless separately adopted.

## Consequences recorded at acceptance

- Seed construction was expected to gain floater rejection and depth-consistent adjacency without a new Browser protocol.
- Negative Mass was expected to split into production channels, rotating aggregation, reliability, diagnostics, and production identity.
- Changes to the Direct Evidence readout rotate implementation identity.

## Partial supersession by ADR 0023

ADR 0023 preserves decisions 1 and 3 with narrower terminology: the readout is Contribution-Weighted Expected Depth plus depth moments/variance and is not authoritative surface truth. Decision 2 remains subject to the V2C recurrence review.

Decision 4 and its mandatory production consequences are superseded. Depth-classified Negative Evidence is now a nonblocking experiment (`V2AX`); current production retains one `negativeMass` channel until a later evidence-backed schema and identity promotion.
