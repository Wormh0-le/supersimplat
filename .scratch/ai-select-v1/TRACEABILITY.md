# Final Spec v1.3 → Ticket Traceability Matrix — v2.11

A requirement counts as covered only when a mapped Ticket contains explicit acceptance, failure, validation or migration criteria.

| ID | Requirement | Ticket(s) |
|---|---|---|
| R001 | AI Select selects one object instance per target context | 01, 07A |
| R002 | Native Selection changes only through explicit native operations | 16, 17 |
| R003 | Candidate never mutates Native Selection before Apply | 14, 15, 16 |
| R004 | All AI observation RGB uses authoritative gsplat and exact CameraBinding | 02, 03, 06, 11, 19 |
| R005 | RGB Ready is independent from Mask, Evidence and Candidate | 03, 06, 09, 11 |
| R006 | asynchronous artifacts are identity-bound and stale results fail closed | 01, 03, 04C, 08, 08A, 08B, 12, 21 |
| R007 | explicit Retry creates a new attempt; same-attempt replay may be idempotent | 03, 04C, 08B, 12, 21 |
| R008 | cancellation/OOM/model failure publishes no partial current artifact | 04C, 08B, 12, 20, 21 |
| R009 | User Confirmed Stable Mask cannot be silently replaced | 04, 04C, 07, 08B, 12, 21 |
| R010 | static instance segmentation uses official SAM 3 Image interactivity | 04C, 07A, 08B, 21 |
| R011 | static path does not instantiate Multiplex video predictor/private tracker heads | 04C, 08B, 21 |
| R012 | historical Multiplex manifest/artifacts are incompatible with current profile | 02C, 04C, 12, 21 |
| R013 | v1 Prompt surface contains Positive Point, Negative Point and Positive Instance Box only | 04C, 07A, 07B, 08A, 08B, 11 |
| R014 | Negative Box is absent from current schema, compiler and UI | 04C, 07A, 07B, 08A, 08B, 21 |
| R015 | Prompt Brush and Mask Constraints are absent from current schema, compiler and UI | 04C, 07B, 08A, 08B, 21 |
| R016 | Paint/Erase remain Editing Mask operations and never enter inference | 04C, 07A, 07B, 11, 21 |
| R017 | previous-prediction logits are internal continuous same-image refinement artifacts | 04C, 08A, 12, 21 |
| R018 | binary Brush data cannot validate as previous logits | 04C, 08A, 21 |
| R019 | one positive Point may return at most three candidates | 04C, 07A, 11, 21 |
| R020 | Box, multiple Points or refinement return at most one candidate | 04C, 07A, 08A, 08B, 11, 21 |
| R021 | raw model score may order preview but is not correctness probability | 04C, 07A, 08A |
| R022 | Anchor single-click ambiguity is resolved directly by user choice/refinement | 07A, 09, 11 |
| R023 | generic near-duplicate/material-distinct clustering is not a v1 closure gate | 07A, 08B, 21 |
| R024 | Accept, Editing Mask, Paint/Erase, Confirm and Stable Mask remain distinct | 04, 05, 07A, 07B |
| R025 | only Confirm publishes Anchor Stable Mask | 04, 05, 07A |
| R026 | palette exposes only current Point/Box and Paint/Erase tools | 07B, 11, 21 |
| R027 | palette drag/collapse/Space-hide leaves no stale hit region | 07B, 11, 21 |
| R028 | Anchor Stable Mask produces one compact TargetGeometryHintArtifact | 08 |
| R029 | TargetGeometryHint visible points are bounded, finite and deterministic | 08, 21 |
| R030 | TargetGeometryHint is localization context, not Gaussian ownership | 08, 13, 14 |
| R031 | default generated plan contains 2–4 bounded local Views | 08, 21 |
| R032 | local Views validate projection, clipping and nonblank RGB | 08, 21 |
| R033 | adaptive/free-space/room-scale planner is deferred | 08, 21 |
| R034 | 07B and 08 run in parallel after 07A | 07A, 07B, 08 |
| R035 | 08A defines compact Image Instance Prompt/Mask contracts | 08A |
| R036 | current contracts require no backend registry, route bundle or sequence extension | 08A, 08B, 12, 21 |
| R037 | current flow has no automatic Route-A fallback | 08A, 08B, 09, 12, 21 |
| R038 | Generated Prompts contain one Positive Box, 1–3 positive Points and optional local negative Points | 08B |
| R039 | Generated per-View inference uses SAM 3 Image single-mask mode | 08B, 11 |
| R040 | semantic unavailable differs from technical inference failure | 08A, 08B, 09, 12, 21 |
| R041 | provider output cannot publish Stable Mask, Participation, Evidence or Candidate | 08A, 08B |
| R042 | Mask Review uses Prompt consistency, clipping, fragmentation and gross spill only | 07, 08B, 21 |
| R043 | propagation-uncertain is removed from current Mask Review | 07, 08B, 21 |
| R044 | weak-gaussian-support belongs to Ticket 13 Lift Readiness | 07, 13, 21 |
| R045 | Good/Review/Failed defaults preserve Participation and user authority | 07, 08B, 11 |
| R046 | dirty lifecycle separates geometry, plan, Prompt, Mask, Evidence, Lift and Candidate | 12 |
| R047 | only Included Stable Masks contribute to P/N/V | 13, 14, 20 |
| R048 | future video tracking requires a new measured experiment-backed ADR | 04C, 08A, 21 |

## Coverage result

- requirements: 48;
- unmapped requirements: 0;
- orphan active Tickets: 0;
- current implementation frontier: 04C;
- current normative spec: Final Spec v1.3.
