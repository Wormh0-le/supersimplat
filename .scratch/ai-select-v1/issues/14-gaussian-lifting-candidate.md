# 14 — Reference P/N/V Evidence + Gaussian Lifting → Candidate / Uncertain

Status: ready-for-agent — v2.2 re-audited

Blocked by: 11, 12

## Final Spec mapping

- Final Spec v1.1 §§14–22, 24.3, 30 Stage 1–2
- ADR 0013
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
- Atomic Candidate and Uncertain
- Rejected/Out-of-Scope internal classes
- Reference fixtures for Ticket 20

## What to build

Validate the new lifting architecture before production CUDA optimization. Implement a trusted, independently testable reference path using stock gsplat autograd/feature rendering, the existing complete Contributor backend, or another declared reference method. Define Mask-conditioned P/N/V, artifact identity, multi-view aggregation, and four-state classification. This ticket reverses the v2.1 dependency: Evidence semantics must exist before cross-view assessment and Coverage can consume them.

## Acceptance criteria

- [ ] Formal input is exactly current Included Stable View Annotations plus target/dependency/policy/working-set identities.
- [ ] Excluded Views and Views without Stable Mask do not contribute.
- [ ] For each View/Gaussian, reference Evidence computes P/N/V from actual `alpha × incoming transmittance` semantics.
- [ ] Define/version Strong Positive Interior, Boundary/Ignore Band, Local Negative Context Ring, Far Neutral Region, and optional soft weights.
- [ ] Far image exterior is not automatically strong negative.
- [ ] Define Core Target Set, Context Set, and Evidence Working Set; non-target occluders remain in Render Working Set.
- [ ] Per-view GaussianEvidenceArtifact binds Camera, RGB, Stable Mask, policy, Render/Evidence Working Sets, Stable IDs, and implementation identity.
- [ ] Artifact supports exclude/reinclude, Stable Mask replacement, incremental Re-Lift, and exact invalidation.
- [ ] Preserve per-view raw P/N/V before cross-view aggregation.
- [ ] Define/version multi-view aggregation using effective evidence, visible mass, supporting/conflicting Views, and optional boundary/footprint/diversity diagnostics.
- [ ] Selected, Rejected, Uncertain, and Out of Scope remain distinct.
- [ ] Unobserved/insufficient Visible Mass is Uncertain, never default Rejected.
- [ ] Material positive+negative/mixed support is Uncertain.
- [ ] Candidate contains Selected only; Uncertain is diagnostic.
- [ ] Reference output is compared against existing complete Contributor aggregation on declared fixtures; discrepancies are characterized rather than hidden by threshold tuning.
- [ ] Include fixtures for strong positive, local background, boundary mixed, unobserved, occlusion, multiple Views, and large Gaussian spanning foreground/background.
- [ ] Lift publication is atomic and never mutates Native Selection/EditHistory.
- [ ] Candidate records enough bound identity to determine current/stale state without DG-14 UI.
- [ ] Stable input change makes Candidate stale; explicit Re-Lift is required.
- [ ] Reference PoC reports Gaussian precision/recall, rendered novel-view mask IoU where available, background contamination, mixed ratio, and single-vs-multi-view effect.

## Failure / recovery criteria

- [ ] Evidence/Lift failure preserves Views, Stable Masks, Gallery, and prior Candidate; no partial replacement publishes.
- [ ] Missing Render Working Set, invalid Stable ID mapping, or non-finite Evidence fails closed.
- [ ] Complete Contributor reference failure does not relabel valid RGB as Render Failed; it only blocks that reference comparison.

## Affected seams

- Companion evidence.py / reference adapter
- Companion lifting/aggregation policy
- src/ai-select candidate/evidence identity state
- Candidate/Uncertain overlays
- Reference fixtures and benchmark harness

## Validation

- npm test
- npm run test:companion
- npm run lint
- npm run build
- Reference P/N/V fixtures
- Contributor-reference comparison
- Multi-view classification and atomic publication tests

## Non-goals

- No Native Set/Add/Remove/Intersect
- No production same-decision CUDA kernel; Ticket 20 owns it
- No Candidate provenance/source inspector