# Final Spec v1.3 → Ticket Traceability Matrix — v2.22

A requirement counts as covered only when a mapped parent Ticket contains explicit acceptance, failure, validation or migration criteria. Every parent Ticket-local current mapping points directly to Final Spec v1.3; older specs are historical provenance only. Ticket 14A–14D are execution stages under parent Ticket 14 and preserve the parent requirement mapping.

| ID   | Requirement                                                                                                                      | Ticket(s)                              |
| ---- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| R001 | AI Select selects one object instance per target context                                                                         | 01, 07A                                |
| R002 | Native Selection changes only through explicit native operations                                                                 | 16, 17                                 |
| R003 | Candidate never mutates Native Selection before Apply                                                                            | 14, 15, 16                             |
| R004 | all AI observation RGB uses authoritative gsplat and exact CameraBinding                                                         | 02, 03, 06, 11, 19                     |
| R005 | RGB Ready is independent from Mask, Evidence and Candidate                                                                       | 03, 06, 09, 11                         |
| R006 | asynchronous artifacts are identity-bound and stale results fail closed                                                          | 01, 03, 04C, 08, 08A, 08B, 12, 21      |
| R007 | explicit Retry creates a new attempt; same-attempt replay may be idempotent                                                      | 03, 04C, 08B, 12, 21                   |
| R008 | cancellation/OOM/model failure publishes no partial current artifact                                                             | 04C, 08B, 12, 20, 21                   |
| R009 | User Confirmed Stable Mask cannot be silently replaced                                                                           | 04, 04C, 07, 08B, 12, 21               |
| R010 | static instance segmentation uses official SAM 3 Image interactivity                                                             | 04C, 07A, 08B, 21                      |
| R011 | static path does not instantiate Multiplex video predictor/private tracker heads                                                 | 04C, 08B, 21                           |
| R012 | historical Multiplex manifest/artifacts are incompatible with current profile                                                    | 02C, 04C, 12, 21                       |
| R013 | v1 Prompt surface contains Positive Point, Negative Point and Positive Instance Box only                                         | 04C, 07A, 07B, 08A, 08B, 11            |
| R014 | Negative Box is absent from current schema, compiler and UI                                                                      | 04C, 07A, 07B, 08A, 08B, 21            |
| R015 | Prompt Brush and Mask Constraints are absent from current schema, compiler and UI                                                | 04C, 07B, 08A, 08B, 21                 |
| R016 | Paint/Erase remain Editing Mask operations and never enter inference                                                             | 04C, 07A, 07B, 11, 21                  |
| R017 | every inference request includes resolvable authoritative RGB bytes or current Companion RGB ref                                 | 04C, 08A, 08B, 11, 12, 21              |
| R018 | RGB digest-only input without resolvable bytes/ref fails before inference                                                        | 04C, 08A, 08B, 21                      |
| R019 | actual previous logits remain Companion-local behind opaque refs                                                                 | 02C, 04C, 08A, 12, 21                  |
| R020 | previous-logits ref binds Companion Instance, same View/RGB/adapter/source candidate                                             | 02C, 04C, 07A, 08A, 12, 21             |
| R021 | binary Brush or Editing Mask cannot validate as previous logits                                                                  | 04C, 07A, 08A, 12, 21                  |
| R022 | expired/refused logits ref falls back to fresh Point/Box inference without mask_input                                            | 04C, 07A, 11, 12, 21                   |
| R023 | one Positive Point may return at most three candidates                                                                           | 04C, 07A, 11, 21                       |
| R024 | Box, multiple Points or refinement return at most one candidate                                                                  | 04C, 07A, 08A, 08B, 11, 21             |
| R025 | raw model score may order preview but is not correctness probability                                                             | 04C, 07A, 08A                          |
| R026 | Anchor single-click ambiguity is resolved directly by user choice/refinement                                                     | 07A, 11                                |
| R027 | candidate refinement occurs before Accept while still in Prompt mode                                                             | 04C, 07A, 11                           |
| R028 | generic near-duplicate/material-distinct clustering is not a v1 closure gate                                                     | 07A, 08B, 21                           |
| R029 | Accept, Editing Mask, Paint/Erase, Confirm and Stable Mask remain distinct                                                       | 04, 05, 07A, 07B                       |
| R030 | only Confirm publishes Anchor Stable Mask                                                                                        | 04, 05, 07A                            |
| R031 | palette exposes only current Point/Box and Paint/Erase tools                                                                     | 07B, 11, 21                            |
| R032 | palette drag/collapse/Space-hide leaves no stale hit region                                                                      | 07B, 11, 21                            |
| R033 | Anchor Stable Mask produces one compact TargetGeometryHintArtifact                                                               | 08                                     |
| R034 | TargetGeometryHint visible Points are bounded, finite and deterministic                                                          | 08, 21                                 |
| R035 | TargetGeometryHint is localization context, not Gaussian ownership                                                               | 08, 13, 14, 20                         |
| R036 | default generated plan contains 2–4 bounded local Views                                                                          | 08, 21                                 |
| R037 | local Views validate projection, clipping and nonblank RGB                                                                       | 08, 21                                 |
| R038 | adaptive/free-space/room-scale planner is deferred                                                                               | 08, 21                                 |
| R039 | 07B and 08 run in parallel after 07A                                                                                             | 07A, 07B, 08                           |
| R040 | Tickets through 12 and parent Ticket 14 / stages 14A–14D are implemented prerequisites; Ticket 13 is the current parent frontier | 09, 11, 12, 13, 14, 14A, 14B, 14C, 14D |
| R041 | 02C may proceed after 04C; 07A requires both 04C and 07                                                                          | 02C, 07A                               |
| R042 | 08A defines compact RGB-bound Image Instance Prompt/Mask contracts                                                               | 08A                                    |
| R043 | current contracts require no backend registry, route bundle or sequence extension                                                | 08A, 08B, 12, 21                       |
| R044 | current flow has no automatic Route-A fallback                                                                                   | 06, 08A, 08B, 09, 12, 21               |
| R045 | Generated Prompts contain one Positive Box, 1–3 Positive Points and optional local Negative Points                               | 08B                                    |
| R046 | Generated per-View inference uses SAM 3 Image single-mask mode                                                                   | 08B, 11                                |
| R047 | semantic unavailable differs from technical inference failure                                                                    | 08A, 08B, 09, 12, 21                   |
| R048 | provider output cannot publish Stable Mask, Participation, Evidence or Candidate                                                 | 08A, 08B                               |
| R049 | Mask Review uses Prompt consistency, clipping, fragmentation and gross spill only                                                | 07, 08B, 21                            |
| R050 | propagation-uncertain is removed and weak/low Gaussian support belongs only to Ticket 13                                         | 07, 10, 13, 21                         |
| R051 | Ticket 10 cross-view Evidence conflict is optional and not a core release blocker                                                | 10, 13, 21                             |
| R052 | only Included Stable Masks contribute to P/N/V; future video tracking requires a new ADR                                         | 04C, 08A, 13, 14, 20, 21               |
| R053 | TargetGeometryHint formal visiblePoints are retained distinct first-hit support, never raw filtered-out samples                  | 08C                                    |
| R054 | Geometry Quality and Route B Prompt Support are independent states                                                               | 08C, 09                                |
| R055 | Prompt Support requires four distinct retained 3D samples and two distinct in-frame points per View                              | 08C                                    |
| R056 | old TargetGeometryHint schema/policy/digest identities fail closed and regenerate                                                | 08B, 08C, 21                           |

## Ticket 14 stage coverage

Parent Ticket 14 requirements are partitioned without changing requirement ownership:

- 14A — formal Evidence admission, identities and Working Sets;
- 14B — trusted reference per-view P/N/V computation;
- 14C — multi-view aggregation and Selected/Rejected/Uncertain/Out-of-Scope classification;
- 14D — atomic Candidate publication, stale/current binding and parent reference validation gate.

14D explicitly excludes Candidate provenance/source inspection and Gaussian-level Evidence inspection.

## Coverage result

- requirements: 56;
- unmapped requirements: 0;
- orphan active parent Tickets: 0;
- parent Ticket files with direct current Final Spec v1.3 mapping: 31/31;
- Ticket 14 execution-stage files mapped through parent 14 + Final Spec v1.3: 4/4;
- Ticket files with v1.1/v1.2 as current mapping authority: 0;
- older-spec references outside explicit historical/superseded/migration sections: 0;
- implemented prerequisite chain: through 12 and parent Ticket 14 / 14D;
- Ticket 09 locked-GPU large-Gallery browser walkthrough: passed 2026-08-07;
- current parent implementation frontier: 13;
- current Ticket 14 execution stage: none (all implemented);
- next implementation Ticket: 13;
- next implementation subticket: none;
- optional nonblocking Ticket: 10;
- current normative spec: Final Spec v1.3.
