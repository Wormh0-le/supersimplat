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

## Consequences

- Ticket 04C becomes the next implementation gate and migrates model, Prompt schema, capabilities, artifacts, tests, and Model Manifest identity.
- Ticket 02C waits for 04C so readiness validates the correct active static-image adapter.
- Tickets 07, 07A, 07B, 08, 08A, 08B, 09, 12, 13, and 21 are narrowed accordingly.
- Existing SAM 3.1 Multiplex and `generated-view-mask/v1` artifacts cannot validate as current artifacts.
- Existing User Confirmed Stable Masks remain authoritative through migration.
- Final Spec v1.3 is normative. This ADR supersedes conflicting route/backend/planner details in ADR 0014 and DG-24 through DG-26, while retaining their historical rationale.
