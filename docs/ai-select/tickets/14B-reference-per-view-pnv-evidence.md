# 14B — Reference Per-View P/N/V Evidence

Status: ready-for-agent — execution stage of parent Ticket 14

Blocked by: none (14A implemented)

Blocks: 14C

## Current Final Spec mapping

- Parent Ticket 14
- Final Spec v1.3 §§20–22, 24–25
- ADR 0013

Final Spec v1.3 and parent Ticket 14 remain authoritative.

## Goal

Implement and validate a trusted reference path for per-view Mask-conditioned Gaussian Positive Mass (P), Negative Mass (N) and Visible Mass (V), preserving the exact Evidence semantics required by parent Ticket 14.

## Inputs / preconditions

- admitted 14A per-view Evidence inputs and Working Sets;
- exact Stable Gaussian ID mapping;
- versioned pixel-region / Evidence Policy;
- one or more declared trusted reference backends (Contributor, stock-gsplat autograd/feature rendering, or another explicitly validated reference method).

## Outputs / handoff

- populated reference per-view `GaussianEvidenceArtifact`;
- raw P/N/V arrays indexed by Stable Gaussian ID;
- optional boundary diagnostics kept separate from P/N/V;
- reference backend / raster / runtime identity;
- comparison fixtures and numerical discrepancy report for 14C/14D.

## Acceptance criteria

- [ ] Reference contribution uses `w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)`.
- [ ] `P(v,g) = Σ positiveWeight(v,p) × w(v,p,g)`.
- [ ] `N(v,g) = Σ negativeWeight(v,p) × w(v,p,g)`.
- [ ] `V(v,g) = Σ roiOrVisibleWeight(v,p) × w(v,p,g)`.
- [ ] Positive, negative and visible weights are independently versioned; implementation does not assume `P + N = V`.
- [ ] Strong Positive Interior, Boundary/Ignore Band, Local Negative Context Ring and Far Neutral Region are explicitly represented by policy.
- [ ] Far image exterior is not automatically strong negative.
- [ ] Raw per-view P/N/V is preserved before aggregation.
- [ ] Gaussians outside Evidence Working Set receive no P/N/V writes while still participating in Render Working Set compositing when required.
- [ ] Non-finite or incomplete Evidence fails closed and no partial artifact publishes.
- [ ] At least one trusted reference backend is mandatory; Contributor and stock-gsplat autograd are compared together when both are available.
- [ ] Backend discrepancies are measured rather than hidden by threshold changes.
- [ ] Comparison reports max/p95/p99 error, relative error, support differences and threshold-near differences where applicable.
- [ ] Fixtures cover positive interior, local background, boundary mixed, unobserved, occlusion, large cross-boundary Gaussian and thin structures.

## Failure / recovery

- Reference backend failure does not relabel valid RGB as Render Failed.
- A failed backend may fall back only to another declared trusted reference backend, never nearest/top-k/distance/center attribution.
- Failure preserves all upstream artifacts and prior Candidate.

## Validation

- reference P/N/V fixtures;
- P/N/V independence tests;
- Contributor/autograd comparison where available;
- Stable-ID mapping tests;
- out-of-scope occluder test;
- non-finite/partial publication tests;
- deterministic artifact identity tests.

## Non-goals

- No final multi-view classification; 14C owns it.
- No Candidate publication or UI; 14D owns it.
- No production same-decision CUDA Evidence; Ticket 20 owns it.
- No geometry/Prompt/SAM/review confidence as ownership Evidence.
