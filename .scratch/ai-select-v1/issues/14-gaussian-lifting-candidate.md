# 14 — Reference P/N/V Evidence + Gaussian Lifting → Candidate / Uncertain

Status: ready-for-agent — v2.2 FlashSplat-alignment review

Blocked by: 11, 12

## Final Spec mapping

- Final Spec v1.1 §§14–22, 24.3, 30 Stage 1–2
- ADR 0013
- FlashSplat-style direct-Evidence design: reference/algorithm stage
- DG-20 and DG-03 retired semantics
- MVP Phase 5 reference Evidence/Lift

## Inputs / preconditions

- Included Stable View Annotations
- Stable Gaussian IDs and SceneSnapshot
- Render Working Set seam
- Versioned Mask/Evidence Policy
- Dirty-state and artifact identity model

## Outputs / handoff artifacts

- Reference per-view GaussianEvidenceArtifact
- P/N/V and optional boundaryMass
- Core Target Set / Context Set and Evidence Working Set seam
- Multi-view Evidence aggregation
- Atomic reference Candidate and Uncertain
- Rejected/Out-of-Scope internal classes
- Reference backend identity and fixtures for Ticket 20

## What to build

Validate the FlashSplat-style lifting mathematics before production CUDA optimization. Implement a trusted, independently testable reference path using stock gsplat autograd/feature rendering, the existing complete Contributor backend, or another declared reference method.

This ticket defines the mask-conditioned P/N/V contract, per-view artifact, multi-view aggregation, and four-state classification. It does not claim that the reference backend shares the production RGB forward decision chain; Ticket 20 owns that trust boundary.

## Acceptance criteria

### Exact Evidence semantics

- [ ] Formal input is exactly current Included Stable View Annotations plus target/dependency/policy/working-set identities.
- [ ] Excluded Views and Views without Stable Mask do not contribute.
- [ ] For View `v`, pixel `p`, Gaussian `g`, reference contribution is actual `w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)`.
- [ ] `P(v,g) = Σp positiveWeight(v,p) × w(v,p,g)`.
- [ ] `N(v,g) = Σp negativeWeight(v,p) × w(v,p,g)`.
- [ ] `V(v,g) = Σp roiOrVisibleWeight(v,p) × w(v,p,g)`; V is local valid observation mass, not whole-image/frustum membership.
- [ ] Positive, negative, and visible weights are independently versioned and need not sum to one.
- [ ] The implementation does not assume `P + N = V`, and does not apply Contributor-style alpha mass-conservation admission to P/N/V.
- [ ] Define/version Strong Positive Interior, Boundary/Ignore Band, Local Negative Context Ring, Far Neutral Region, and optional soft weights.
- [ ] Far image exterior is not automatically strong negative.

### Scene and Working Set semantics

- [ ] Define Core Target Set, Context Set, and Evidence Working Set.
- [ ] The full conservative Render Working Set continues to provide all occluders/transmittance contributors required by the authoritative render scope.
- [ ] Gaussians outside the Evidence Working Set, including non-target occluders, participate in ordering/compositing but receive no P/N/V writes.
- [ ] Reference fixtures include a target hidden by an out-of-scope/non-target occluder and prove that target-only rasterization would be incorrect.

### Artifact and policy semantics

- [ ] Per-view GaussianEvidenceArtifact binds Camera, RGB, Stable Mask, policy, Render/Evidence Working Sets, Stable IDs, reference backend identity, and implementation/runtime identity.
- [ ] Artifact records `backendKind=reference` or an equivalent non-production identity; it cannot be mistaken for Ticket 20 same-decision production Evidence.
- [ ] Artifact supports exclude/reinclude, Stable Mask replacement, incremental Re-Lift, and exact invalidation.
- [ ] Preserve per-view raw P/N/V before cross-view aggregation.
- [ ] Define/version multi-view aggregation using effective evidence, visible mass, supporting/conflicting Views, and optional boundary/footprint/diversity diagnostics.
- [ ] Benchmark raw-mass summation and a versioned per-view confidence cap/normalization strategy so one close/high-resolution/large-footprint View cannot dominate without explicit policy.
- [ ] Selected, Rejected, Uncertain, and Out of Scope remain distinct.
- [ ] Unobserved/insufficient V is Uncertain, never default Rejected.
- [ ] Material positive+negative/mixed support is Uncertain.
- [ ] Candidate contains Selected only; Uncertain is diagnostic.

### Reference comparison and quality gate

- [ ] At least one trusted reference method is mandatory; use complete Contributor and stock-gsplat autograd/feature rendering together when both are available.
- [ ] Reference outputs are compared on declared fixtures; discrepancies are characterized rather than hidden by threshold tuning.
- [ ] Compare max/p95/p99 absolute error, relative error, nonzero-support differences, threshold-near Gaussian count, and final classification differences.
- [ ] Include fixtures for strong positive, local background, boundary mixed, unobserved, occlusion, multiple Views, large Gaussian spanning foreground/background, thin structures, and high occlusion.
- [ ] Report Gaussian precision/recall, novel-view rendered-mask IoU where available, background contamination, mixed ratio, user Add/Remove burden proxy, single-vs-multi-view effect, and View-exclusion incremental correctness.

### Candidate publication

- [ ] Reference Lift publication is atomic and never mutates Native Selection/EditHistory.
- [ ] Candidate records enough bound identity to determine current/stale state without DG-14 UI.
- [ ] Stable input change makes Candidate stale; explicit Re-Lift is required.
- [ ] Reference Candidate is clearly identified as pre-production until Ticket 20/21 production readiness is satisfied.

## Failure / recovery criteria

- [ ] Evidence/Lift failure preserves Views, Stable Masks, Gallery, and prior Candidate; no partial replacement publishes.
- [ ] Missing Render Working Set, invalid Stable ID mapping, or non-finite Evidence fails closed.
- [ ] Complete Contributor reference failure does not relabel valid RGB as Render Failed; it only blocks that reference comparison.
- [ ] Failure of one reference backend may use another declared trusted reference, but never silently substitutes nearest/top-k/distance/center attribution.

## Affected seams

- Companion evidence.py / reference adapter
- Companion lifting/aggregation policy
- src/ai-select Candidate/Evidence identity state
- Candidate/Uncertain overlays
- Reference fixtures and benchmark harness

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Reference P/N/V fixtures
- Contributor and autograd/feature-rendering reference comparison where available
- P/N/V independence/no-mass-conservation tests
- Out-of-scope occluder fixture
- Multi-view dominance and atomic publication tests

## Non-goals

- No Native Set/Add/Remove/Intersect
- No production same-decision CUDA kernel; Ticket 20 owns it
- No claim that reference/autograd Evidence is production RGB-equivalent
- No Candidate provenance/source inspector