# 14 — Reference P/N/V Evidence + Gaussian Lifting → Candidate / Uncertain

Status: in-progress — 14A and 14B implemented; 14C is the current execution stage

Blocked by: 11, 12

## Current Final Spec mapping

- Final Spec v1.3 §§20–22, 24–25
- ADR 0013
- ADR 0016 where it narrows geometry, Prompt and per-View acquisition semantics
- DG-20 and DG-26 as historical ownership-boundary rationale only where not superseded
- FlashSplat-style direct-Evidence design: reference/algorithm stage

Final Spec v1.3 is the only current closure source. Final Spec v1.2 route/backend artifacts are historical and are not current Evidence inputs.

## Inputs / preconditions

- Included Stable View Annotations only;
- Stable Gaussian IDs and SceneSnapshot;
- Render Working Set seam;
- Versioned Mask/Evidence Policy;
- Dirty-state and artifact identity model;
- `TargetGeometryHintArtifact`, Prompt artifacts, SAM scores, previous-logits refs and MaskReview results as diagnostic provenance only;
- View role and source as diagnostic metadata only.

## Outputs / handoff artifacts

- reference per-view `GaussianEvidenceArtifact`;
- P/N/V and optional boundary mass;
- Core Target Set / Context Set and Evidence Working Set seam;
- multi-view Evidence aggregation;
- atomic reference Candidate and Uncertain;
- Rejected/Out-of-Scope internal classes;
- reference backend identity and fixtures for Ticket 20.

## What to build

Validate FlashSplat-style lifting mathematics before production CUDA optimization. Implement a trusted reference path using stock gsplat autograd/feature rendering, complete Contributor, or another declared reference method.

This ticket defines Mask-conditioned P/N/V, per-view artifacts, multi-view aggregation, and four-state classification. Ticket 20 owns production RGB-forward decision equivalence.

Final Spec v1.3 preserves the ownership boundary: target geometry, Prompt, SAM output metadata, refinement state and Mask Review help obtain Stable Masks or prepare Working Sets; they do not classify Gaussian ownership.

## Acceptance criteria

### Exact Evidence semantics

- [ ] Formal input is exactly current AIViews with Render Ready + Stable Mask + Participation Included, plus target/dependency/policy/working-set identities.
- [ ] Excluded Views and Views without Stable Mask do not contribute.
- [ ] Key/User-added role alone never contributes Evidence.
- [ ] For View `v`, pixel `p`, Gaussian `g`, reference contribution is `w(v,p,g) = alpha(v,p,g) × incomingTransmittance(v,p,g)`.
- [ ] `P(v,g) = Σ positiveWeight(v,p) × w(v,p,g)`.
- [ ] `N(v,g) = Σ negativeWeight(v,p) × w(v,p,g)`.
- [ ] `V(v,g) = Σ roiOrVisibleWeight(v,p) × w(v,p,g)`.
- [ ] Positive, negative, and visible weights are independently versioned and need not sum to one.
- [ ] Do not assume `P + N = V` or apply Contributor mass-conservation admission.
- [ ] Define/version Strong Positive Interior, Boundary/Ignore Band, Local Negative Context Ring, Far Neutral Region, and optional soft weights.
- [ ] Far image exterior is not automatically strong negative.
- [ ] TargetGeometryHint points/extent, Prompt geometry, raw SAM score, previous logits, MaskReview reason, inference diagnostics and View role are not formal ownership Evidence.

### Scene and Working Set semantics

- [ ] Define Core Target Set, Context Set, and Evidence Working Set.
- [ ] Full conservative Render Working Set preserves all required occluders/transmittance contributors.
- [ ] Gaussians outside Evidence Working Set still participate in compositing but receive no P/N/V writes.
- [ ] A target hidden by an out-of-scope occluder proves target-only rasterization is incorrect.
- [ ] `TargetGeometryHintArtifact` may seed an initial conservative Evidence Working Set but cannot classify ownership.
- [ ] TargetGeometryHint is not a hard Evidence Working Set upper bound.
- [ ] Later Included Stable View support can expand the Evidence Working Set.
- [ ] Evidence touching a Working Set boundary triggers declared expansion/fail-closed diagnostics rather than silent truncation.
- [ ] Absence from Anchor-visible geometry alone cannot classify a Gaussian as Rejected or Out of Scope.

### Artifact and policy semantics

- [ ] Per-view artifact binds Camera, RGB, Stable Mask, policy, Render/Evidence Working Sets, Stable IDs, raster implementation, reference backend, and runtime.
- [ ] Prompt/inference/review identities may be retained as Stable Mask provenance but cannot replace Stable Mask digest or Evidence backend identity.
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
- [ ] Include bounded local Key Views, Generate More, semantic Mask unavailable, Auto Review Excluded, User Confirmed correction and TargetGeometryHint-seed expansion fixtures.
- [ ] Report Gaussian precision/recall, novel-view rendered-mask IoU, background contamination, mixed ratio, user Add/Remove burden proxy, single-vs-multi-view effect, and View-exclusion correctness.

### Candidate publication

- [ ] Reference Lift publication is atomic and never mutates Native Selection/EditHistory.
- [ ] Candidate records enough bound identity to determine current/stale state.
- [ ] Candidate retains raster implementation, Evidence backend, runtime, and policy identity.
- [ ] Stable input or incompatible renderer/runtime/backend change makes Candidate stale; explicit Re-Lift is required.
- [ ] Reference Candidate is clearly pre-production until Tickets 20/21 close.

## Failure / recovery criteria

- Evidence/Lift failure preserves Views, Stable Masks, Gallery, Mask Review state and prior Candidate; no partial replacement.
- Missing Render Working Set, invalid Stable ID mapping, or non-finite Evidence fails closed.
- Reference Contributor failure never relabels valid RGB as Render Failed.
- One reference backend may fall back to another declared trusted reference, never nearest/top-k/distance/center attribution.
- Mask inference or semantic unavailable is upstream and cannot be reinterpreted as Evidence output.
- A View without a Stable Mask contributes no Evidence.

## Affected seams

- Companion evidence/reference adapter;
- Companion lifting/aggregation policy;
- Candidate/Evidence identity state;
- Candidate/Uncertain overlays;
- reference fixtures and benchmark harness.

## Validation

- `npm test`
- `npm run test:companion`
- `npm run lint`
- `npm run build`
- reference P/N/V fixtures
- Contributor and autograd comparison where available
- P/N/V independence tests
- out-of-scope occluder fixture
- TargetGeometryHint-seed expansion fixture
- bounded local Key-View/Participation fixture
- no-Stable-Mask/no-Evidence fixture
- semantic-unavailable non-Evidence fixture
- corrected Stable Mask fixture
- multi-view dominance and atomic publication tests
- backend/raster/runtime invalidation tests

## Non-goals

- No Native Set/Add/Remove/Intersect.
- No geometry/Prompt/SAM/refinement/MaskReview confidence as ownership Evidence.
- No production same-decision CUDA kernel; Ticket 20 owns it.
- No claim that reference/autograd Evidence is production RGB-equivalent.
- No Candidate provenance/source inspector.
