# 14 — Reference P/N/V Evidence + Gaussian Lifting → Candidate / Uncertain

Status: ready-for-agent — v2.6 DG-24 alignment

Blocked by: 11, 12

## Final Spec mapping

- Final Spec v1.1 §§14–22, 24.3, 30 Stage 1–2
- Final Spec v1.1 Amendments 001, 003, and 004
- ADR 0013
- DG-20, DG-24, and retired DG-03 semantics
- FlashSplat-style direct-Evidence design: reference/algorithm stage
- MVP Phase 5 reference Evidence/Lift

## Inputs / preconditions

- Included Stable View Annotations only
- Stable Gaussian IDs and SceneSnapshot
- Render Working Set seam
- Versioned Mask/Evidence Policy
- Dirty-state and artifact identity model
- AIView role/acquisition backend as diagnostic metadata only

## Outputs / handoff artifacts

- Reference per-view GaussianEvidenceArtifact
- P/N/V and optional boundaryMass
- Core Target Set / Context Set and Evidence Working Set seam
- Multi-view Evidence aggregation
- Atomic reference Candidate and Uncertain
- Rejected/Out-of-Scope internal classes
- Reference backend identity and fixtures for Ticket 20

## What to build

Validate FlashSplat-style lifting mathematics before production CUDA optimization. Implement a trusted reference path using stock gsplat autograd/feature rendering, complete Contributor, or another declared reference method.

This ticket defines Mask-conditioned P/N/V, per-view artifacts, multi-view aggregation, and four-state classification. Ticket 20 owns production RGB-forward decision equivalence.

DG-24 does not alter this ownership boundary. Anchor/bootstrap/Mask-acquisition artifacts help obtain Stable Masks; they do not become Gaussian ownership inputs.

## Acceptance criteria

### Exact Evidence semantics

- [ ] Formal input is exactly current AIViews with Render Ready + Stable Mask + Participation Included, plus target/dependency/policy/working-set identities.
- [ ] Excluded Views and Views without Stable Mask do not contribute.
- [ ] Key-View/User-added/optional auxiliary role alone never contributes Evidence.
- [ ] For View `v`, pixel `p`, Gaussian `g`, reference contribution is `w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)`.
- [ ] `P(v,g) = Σ positiveWeight(v,p) × w(v,p,g)`.
- [ ] `N(v,g) = Σ negativeWeight(v,p) × w(v,p,g)`.
- [ ] `V(v,g) = Σ roiOrVisibleWeight(v,p) × w(v,p,g)`.
- [ ] Positive, negative, and visible weights are independently versioned and need not sum to one.
- [ ] Do not assume `P + N = V` or apply Contributor mass-conservation admission.
- [ ] Define/version Strong Positive Interior, Boundary/Ignore Band, Local Negative Context Ring, Far Neutral Region, and optional soft weights.
- [ ] Far image exterior is not automatically strong negative.
- [ ] Prompt score, acquisition backend score, optional tracker confidence/memory score, and View role are not formal ownership Evidence.

### Scene and Working Set semantics

- [ ] Define Core Target Set, Context Set, and Evidence Working Set.
- [ ] Full conservative Render Working Set preserves all required occluders/transmittance contributors.
- [ ] Gaussians outside the Evidence Working Set still participate in compositing but receive no P/N/V writes.
- [ ] A target hidden by an out-of-scope occluder proves target-only rasterization is incorrect.
- [ ] TargetBootstrapArtifact may seed an initial conservative Working Set but cannot classify ownership.
- [ ] Bootstrap support is not a hard Evidence Working Set upper bound.
- [ ] Later Included Stable View support can expand the Evidence Working Set.
- [ ] Evidence touching a Working Set boundary triggers declared expansion/fail-closed diagnostics rather than silent truncation.
- [ ] Absence from Anchor bootstrap alone cannot classify a Gaussian as Rejected or Out of Scope.

### Artifact and policy semantics

- [ ] Per-view artifact binds Camera, RGB, Stable Mask, policy, Render/Evidence Working Sets, Stable IDs, raster implementation, reference backend, and runtime.
- [ ] Mask acquisition backend/attempt/Prompt identity may be recorded as Mask provenance but cannot replace Stable Mask digest or Evidence backend identity.
- [ ] Reference artifact cannot be mistaken for Ticket 20 production Evidence.
- [ ] Incompatible renderer/runtime/backend changes invalidate artifacts.
- [ ] Artifact supports exclude/reinclude, Stable Mask replacement, incremental Re-Lift, and exact invalidation.
- [ ] Preserve per-view raw P/N/V before aggregation.
- [ ] Define/version aggregation using effective Evidence, Visible Mass, supporting/conflicting Views, and optional boundary/footprint/diversity diagnostics.
- [ ] Benchmark raw-mass summation and per-view confidence cap/normalization so one close/high-resolution View cannot dominate silently.
- [ ] Selected, Rejected, Uncertain, and Out of Scope remain distinct.
- [ ] Unobserved/insufficient V is Uncertain, never default Rejected.
- [ ] Material positive+negative/mixed support is Uncertain.
- [ ] Candidate contains Selected only; Uncertain is diagnostic.

### Reference comparison and quality gate

- [ ] At least one trusted reference method is mandatory; use Contributor and stock-gsplat autograd together when both are available.
- [ ] Discrepancies are characterized rather than hidden by threshold tuning.
- [ ] Compare max/p95/p99 error, relative error, support differences, threshold-near count, and classification differences.
- [ ] Fixtures cover strong positive, local background, boundary mixed, unobserved, occlusion, multiple Views, large cross-boundary Gaussian, thin structures, and high occlusion.
- [ ] Include sparse Key-View, Generate More segment, and corrected Stable Mask fixtures.
- [ ] Report Gaussian precision/recall, novel-view rendered-mask IoU, background contamination, mixed ratio, user Add/Remove burden proxy, single-vs-multi-view effect, and View-exclusion correctness.

### Candidate publication

- [ ] Reference Lift publication is atomic and never mutates Native Selection/EditHistory.
- [ ] Candidate records enough bound identity to determine current/stale state.
- [ ] Candidate retains raster implementation, Evidence backend, runtime, and policy identity.
- [ ] Stable input or incompatible renderer/runtime/backend change makes Candidate stale; explicit Re-Lift is required.
- [ ] Reference Candidate is clearly pre-production until Tickets 20/21 close.

## Failure / recovery criteria

- [ ] Evidence/Lift failure preserves Views, Stable Masks, Gallery, and prior Candidate; no partial replacement.
- [ ] Missing Render Working Set, invalid Stable ID mapping, or non-finite Evidence fails closed.
- [ ] Reference Contributor failure never relabels valid RGB as Render Failed.
- [ ] One reference backend may fall back to another declared trusted reference, never nearest/top-k/distance/center attribution.
- [ ] Mask acquisition failure is upstream and cannot be reinterpreted as Evidence output.

## Affected seams

- Companion evidence/reference adapter
- Companion lifting/aggregation policy
- Candidate/Evidence identity state
- Candidate/Uncertain overlays
- Reference fixtures and benchmark harness

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Reference P/N/V fixtures
- Contributor and autograd comparison where available
- P/N/V independence tests
- Out-of-scope occluder fixture
- Bootstrap-seed expansion fixture
- sparse Key-View/Participation fixture
- corrected Stable Mask fixture
- multi-view dominance and atomic publication tests
- backend/raster/runtime invalidation tests

## Non-goals

- No Native Set/Add/Remove/Intersect.
- No Mask-acquisition confidence or bootstrap support as ownership Evidence.
- No production same-decision CUDA kernel; Ticket 20 owns it.
- No claim that reference/autograd Evidence is production RGB-equivalent.
- No Candidate provenance/source inspector.
