# Adopt SAM 3 Image instance workflow and minimal multi-view architecture

Status: accepted

Date: 2026-07-30

## Context

The current static Anchor and visual-Prompt implementation loads the SAM 3.1 Multiplex video predictor, extracts detector/tracker internals, constructs a private single-image session, and invokes private tracker-head methods. SAM 3.1 Multiplex is designed for high-throughput multi-object video tracking, while AI Select v1 performs one-object static-image instance segmentation on an Anchor and a few independently rendered Key Views.

The existing Prompt surface also models Negative Box and positive/negative Mask Constraints. The official static instance interface supports positive/negative Points, a positive instance Box, and previous-prediction logits for refinement. A user-authored binary Prompt Brush is not equivalent to previous low-resolution model logits.

The resulting mismatch creates unnecessary private-API risk and drives speculative complexity into candidate clustering, backend registries, route fallback, sequence extensions, quality reasons, 2.5D artifacts, and camera planning.

## Decision

1. Static Anchor and Key-View segmentation use the official SAM 3 Image model with instance interactivity enabled and the public image instance prediction surface.
2. SAM 3.1 Multiplex is removed from the current static-image production path. It remains only a historical benchmark or a future video-tracking experiment behind a new ADR.
3. AI Select v1 PromptState contains Positive Point, Negative Point, and at most one Positive Instance Box. Negative Box, Prompt Brush, positive/negative Mask Constraints, and Text Prompt are removed.
4. Previous-prediction logits are an internal same-image refinement artifact, not a user Prompt or binary Mask.
5. Exactly one positive point may request up to three masks. A Box, multiple Points, or previous-logits refinement requests one mask.
6. Paint and Erase remain direct Editing Mask operations and never enter model inference.
7. Anchor ambiguity is resolved directly by user candidate choice. Generic near-duplicate/material-distinct clustering and automatic Top-1 calibration are not v1 requirements.
8. Anchor-visible geometry is compressed into one `TargetGeometryHintArtifact`; it does not carry Gaussian ownership.
9. v1 generates 2–4 bounded local Key Views rather than a general adaptive/free-space observation planner.
10. Generated Key Views synthesize one positive instance Box, 1–3 positive Points, and optional local negative Points, then run SAM 3 Image in single-mask mode.
11. Mask Review is separated from Lift Readiness. `propagation-uncertain` is removed; `weak-gaussian-support` moves to Lift Readiness.
12. The current generic backend registry, Route B/C/D bundle, sequence extension, and automatic Route-A fallback are removed from v1 planning.

## Prior inspiration and deliberate divergence

This section is non-normative design provenance. It explains the origin of several product ideas but does not add requirements beyond Final Spec v1.3 and the Decision above.

[ArtisanGS](https://research.nvidia.com/labs/sil/projects/ArtisanGS/) ([paper](https://arxiv.org/abs/2602.10173)) demonstrates an interactive 3DGS-selection workflow that propagates user-guided 2D masks to a binary Gaussian selection while allowing users to inspect and correct errors. Its automatic path lifts the initial masked surface into a target point cloud, generates a dense turnaround sequence around that target, uses Cutie video mask tracking with user reference-frame corrections, and aggregates the multi-view masks by optimizing a one-channel value per Gaussian through the splat renderer.

AI Select v1.3 retains the following design principles:

- **2D-first user intent.** A user establishes an object instance in an authoritative rendered image before any Gaussian ownership decision.
- **Human-in-the-loop correction.** Automatic masks remain inspectable and correctable through candidate choice, Point refinement, Paint/Erase, Manual Draw, Confirm, Include/Exclude, and User-added Views.
- **Visible-surface localization.** Anchor depth/first-hit support is lifted into bounded visible 3D points and robust center/extent in `TargetGeometryHintArtifact`.
- **Geometry-guided multi-view observation.** The visible target hint guides additional camera views and per-View prompts rather than treating the Anchor first-hit set as final ownership.
- **Renderer-mediated 3D selection.** Multi-view Stable Masks are converted to Gaussian selection through the authoritative splat renderer without scene-specific semantic-feature training.
- **Explicit 2D/3D selection boundaries.** Editing a 2D Mask, computing a Gaussian Candidate, and applying Native Set/Add/Remove/Intersect remain distinct operations.

AI Select v1.3 deliberately diverges in the following ways:

- ArtisanGS uses a dense full-circle turnaround sequence and reports robust operation around approximately 50 tracking views; v1.3 starts with 2–4 bounded local Key Views and explicit `Generate More`.
- ArtisanGS treats rendered views as an ordered video and uses Cutie memory/reference frames; v1.3 runs independent SAM 3 Image instance inference for each View and has no current tracker memory or cross-View sequence state.
- ArtisanGS aggregates masks by optimizing and thresholding a one-channel per-Gaussian mask feature; v1.3 uses explicit per-View P/N/V contribution Evidence and preserves `Selected`, `Rejected`, `Uncertain`, and `Out of Scope` as separate classes.
- ArtisanGS exposes manual frustum/depth projection as first-class selection tools; v1.3 currently uses depth/first-hit geometry for localization and prompting, not as an immediate Native Selection mutation.
- ArtisanGS may pre-segment with intersecting frusta when references are declared unoccluded; v1.3 permits `TargetGeometryHintArtifact` to seed an Evidence Working Set but never hard-bounds ownership from Anchor-visible support alone.

No `VideoObjectTracker`, `SequenceMaskProvider`, or tracker-memory contract is reserved in the current v1 protocol. Future video tracking requires a separate `SequenceInstanceTracker` ADR and measured evidence that an ordered-view workload exists and that tracking materially improves quality, latency, or correction burden over independent SAM 3 Image inference. That ADR must specify sequence identity, reference-frame insertion, drift handling, resource limits, cancellation/failure isolation, User Confirmed authority, migration, and how tracker outputs enter the existing Mask Review and Stable publication layers without changing P/N/V ownership semantics.

## Consequences

- Ticket 04C becomes the next implementation gate and migrates model, Prompt schema, capabilities, artifacts, tests, and Model Manifest identity.
- Ticket 02C waits for 04C so readiness validates the correct active static-image adapter.
- Tickets 07, 07A, 07B, 08, 08A, 08B, 09, 12, 13, and 21 are narrowed accordingly.
- Existing SAM 3.1 Multiplex and `generated-view-mask/v1` artifacts cannot validate as current artifacts.
- Existing User Confirmed Stable Masks remain authoritative through migration.
- Final Spec v1.3 is normative. This ADR supersedes conflicting route/backend/planner details in ADR 0014 and DG-24 through DG-26, while retaining their historical rationale.
