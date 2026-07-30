# Final Spec v1.2 → Ticket Traceability Matrix — v2.10

A requirement counts as covered only when the mapped ticket contains an explicit acceptance, failure, validation, or implementation criterion. Final Spec v1.1 and Amendments 001–005 are historical and do not require a parallel overlay.

Current ticket-to-spec mapping is governed by `CURRENT-TICKET-SPEC-MAPPING.md`. Ticket-local v1.1/Amendment references are historical provenance only.

| ID   | Requirement                                                                                                                                           | Ticket(s)                        |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| R001 | AI Select is a native Selection Tool, not a separate workspace                                                                                        | 02, 22                           |
| R002 | Exactly one Current Target Context is authoritative                                                                                                   | 01, 17                           |
| R003 | One target object instance is selected per run; arbitrary parts and whole-image inventory are not required                                            | 01, 07A, 17                      |
| R004 | Native Selection changes only through explicit Set/Add/Remove/Intersect                                                                               | 16, 17                           |
| R005 | Candidate is derived and does not mutate Native Selection before explicit application                                                                 | 14, 15, 16                       |
| R006 | Current Target Context suspends on dependency mutation and resumes only after exact recovery or Restart                                               | 01, 18                           |
| R007 | Restart disposes target-local AI state without corrupting native scene state                                                                          | 05, 17, 18                       |
| R008 | Complete Contributor remains reference/debug only                                                                                                     | 14, 19, 20, 22                   |
| R009 | All AI observation RGB is authoritative gsplat output                                                                                                 | 02, 03, 06, 11, 19               |
| R010 | RGB Ready is independent from Mask, Evidence, and Candidate                                                                                           | 03, 06, 09, 11                   |
| R011 | CameraBinding, RGB, depth/support, Mask, Evidence, and Frustum identities remain coherent                                                             | 03, 08, 14, 19, 20               |
| R012 | Explicit Retry creates a new attempt; same-attempt replay may be idempotent                                                                           | 03, 08, 08B, 12, 21              |
| R013 | Cancellation correctness relies on stale-result rejection, not cancellation completion                                                                | 01, 03, 08B, 12, 18, 21          |
| R014 | No partial asynchronous artifact may publish Ready or Stable                                                                                          | 03, 04, 08, 08B, 14, 20, 21      |
| R015 | Renderer/model/backend/runtime incompatibility invalidates dependent artifacts                                                                        | 02, 03, 08A, 08B, 14, 20, 21     |
| R016 | All artifact/result identities are versioned, digest-bound, and fail closed                                                                           | 01, 03, 04, 08, 08A, 08B, 14, 20 |
| R017 | Prompt Authoring and direct Mask Pixel Editing are separate modes and histories                                                                       | 04A, 07A, 07B                    |
| R018 | Prompt capabilities are truthful and unsupported combinations fail before inference                                                                   | 04B, 07A, 08B, 21                |
| R019 | Anchor inference returns a bounded proposal set rather than one hidden Top-1 Mask                                                                     | 04A, 04B, 07A                    |
| R020 | Anchor exact duplicates and near-duplicates are clustered before decision                                                                             | 07A                              |
| R021 | Raw model score is not correctness probability or sole selector                                                                                       | 07A, 08B, 09                     |
| R022 | Materially distinct plausible Anchor proposals remain ambiguous                                                                                       | 07A                              |
| R023 | Only Confirm publishes an Anchor Stable Mask revision                                                                                                 | 04, 05, 07A                      |
| R024 | Confirmed Anchor Stable Mask is an identity seed, not ownership Evidence                                                                              | 05, 07A, 08, 14                  |
| R025 | Floating Prompt/Edit palette is draggable, collapsible, temporarily hideable, and leaves no stale hit region                                          | 07B, 11, 21                      |
| R026 | Palette state never enters PromptState, Mask, Evidence, Candidate, or Companion requests                                                              | 07B                              |
| R027 | 07B and 08 are parallel after 07A                                                                                                                     | 07A, 07B, 08                     |
| R028 | 07B remains required for complete Generated/User-added correction UX and release validation                                                           | 07B, 11, 21                      |
| R029 | Ticket 08 publishes a bounded replayable VisibleTargetSupportArtifact                                                                                 | 08                               |
| R030 | Visible support binds exact Anchor Camera/RGB/Stable Mask and policy identity                                                                         | 08                               |
| R031 | Visible support samples require finite world positions and deterministic encoding                                                                     | 08, 21                           |
| R032 | Optional stableGaussianId in visible support is provenance only, never ownership                                                                      | 08, 14                           |
| R033 | Background-dominated, separated, invalid-depth, or non-finite support lowers quality or fails closed                                                  | 08, 21                           |
| R034 | Visible support may guide framing, planning, Prompt synthesis, and Working Set seeding                                                                | 08, 08B, 14                      |
| R035 | Absence from visible support cannot classify Rejected or Out of Scope                                                                                 | 08, 14, 20                       |
| R036 | TargetBootstrapArtifact is lightweight and references visible support by digest                                                                       | 08                               |
| R037 | Bootstrap may seed but never hard-bound the Evidence Working Set                                                                                      | 08, 14, 20                       |
| R038 | Ticket 08 publishes immutable SparseKeyViewPlanSegment artifacts                                                                                      | 08                               |
| R039 | Planner evaluates validity before observation/diversity gain                                                                                          | 08                               |
| R040 | Default sparse planning requires no Bridge View, tracker envelope, dense sequence, or adjacency                                                       | 08, 08B                          |
| R041 | Generate More appends segments and preserves prior completed artifacts                                                                                | 08, 09, 12, 21                   |
| R042 | Regenerate Auto Views is the explicit planner-owned segment replacement operation                                                                     | 08, 09, 11                       |
| R043 | Ticket 08A owns acquisition contracts and registry, not production inference                                                                          | 08A                              |
| R044 | KeyViewPromptArtifact is immutable, capability-validated, inspectable, and replayable                                                                 | 08A, 08B                         |
| R045 | Acquisition providers consume Prompt artifacts rather than reinterpreting raw 3D support                                                              | 08A, 08B                         |
| R046 | Per-view provider returns PerViewMaskAcquisitionResult containing ProposalSet plus diagnostics only                                                   | 08A, 08B                         |
| R047 | Provider returns no Decision, Assessment, Stable publication, Participation, Evidence, or Candidate                                                   | 08A, 08B, 21                     |
| R048 | KeyViewMaskDecision is a distinct selected/ambiguous/unavailable artifact                                                                             | 08A, 08B                         |
| R049 | Decision membership validates against the exact ProposalSet artifact digest and acquisition attempt                                                   | 08A, 08B, 12, 21                 |
| R050 | Acquisition attempt identity distinguishes route, backend, retry, and fallback parent/reason                                                          | 08A, 08B, 12, 21                 |
| R051 | MaskAcquisitionBackend bundle contains real perView and optional sequence implementations                                                             | 08A                              |
| R052 | Bundle structure is the capability truth source and must match descriptor/backendKind                                                                 | 08A, 08B, 21                     |
| R053 | Route B is perView-only; Route C is sequence with optional perView; Route D has both                                                                  | 08A                              |
| R054 | Unsupported sequence/reference dispatch fails before inference or state mutation                                                                      | 08A, 08B, 12, 21                 |
| R055 | Sequence schemas exist for future C/D without implementing tracker behavior                                                                           | 08A                              |
| R056 | Ticket 08B implements KeyViewPromptSynthesizer separately from controller and provider                                                                | 08B                              |
| R057 | Prompt synthesis deterministically projects exact visible support into exact Key-View CameraBinding                                                   | 08B, 21                          |
| R058 | Unsupported Point/Box/ROI/Mask Prompt families are not silently dropped or converted                                                                  | 04B, 08B                         |
| R059 | Prompt regeneration is separate from SAM Retry                                                                                                        | 08B, 12                          |
| R060 | Route-B SAM inference is independent per Key View and requires no tracker memory                                                                      | 08B                              |
| R061 | Route-B ProposalSet is bounded and every Mask validates dimensions/digest                                                                             | 08B, 21                          |
| R062 | Key-View proposal decision deduplicates and clusters before conservative selection                                                                    | 08B                              |
| R063 | Materially distinct plausible Key-View proposals remain ambiguous                                                                                     | 08B, 09, 12                      |
| R064 | Ambiguous publishes no arbitrary Stable Mask and does not auto-fallback                                                                               | 08B, 09, 12, 21                  |
| R065 | Only selected proposals enter ViewAssessmentPolicy                                                                                                    | 07, 08B                          |
| R066 | ViewAssessment answers Mask quality, not target-instance candidate selection                                                                          | 07, 08B                          |
| R067 | MaskPublicationCoordinator is the only route-B automatic Stable publisher                                                                             | 08A, 08B                         |
| R068 | selected+Good publishes Auto Good and defaults Included                                                                                               | 07, 08B                          |
| R069 | selected+Review publishes Auto Review and defaults Excluded                                                                                           | 07, 08B                          |
| R070 | unavailable is a completed Decision with no eligible proposal, no Stable Mask, and Excluded Participation; it is not technical failure                | 08A, 08B, 09, 12, 21             |
| R071 | User Confirmed Stable authority cannot be silently replaced                                                                                           | 04, 07, 08B, 12, 21              |
| R072 | Route-A fallback is automatic only for declared technical/capability failures                                                                         | 08B, 12, 21                      |
| R073 | Semantic ambiguity, unavailable, contamination, Prompt inconsistency, clipping, fragmentation, or Review never auto-fallback                          | 08B, 12, 21                      |
| R074 | Route-A fallback uses a distinct parent-bound attempt and retains route-B failure provenance                                                          | 08A, 08B, 09, 12, 21             |
| R075 | Route-A output traverses the same ProposalSet, Decision, Assessment, and Publication layers                                                           | 08B, 21                          |
| R076 | Route-A Auto Good requires the same or stricter trust and contamination gates                                                                         | 08B, 21                          |
| R077 | Generated View orchestration separates planning, rendering, Prompt, acquisition, decision, assessment, and publication                                | 08B                              |
| R078 | RGB publishes progressively and never waits for acquisition                                                                                           | 06, 08B, 09, 11                  |
| R079 | Gallery presents Render, acquisition, Decision, Mask quality, Participation, and Evidence separately                                                  | 09                               |
| R080 | Gallery navigation/filtering never mutates formal state                                                                                               | 09                               |
| R081 | Backend/fallback provenance is inspectable but never a confidence percentage or trust grant                                                           | 09, 21                           |
| R082 | User-added Views use the same RGB/Prompt/acquisition/decision/assessment/publication pipeline                                                         | 11                               |
| R083 | User-added Views may remain RGB Ready with no Mask and Evidence Not Requested                                                                         | 11                               |
| R084 | Regenerate Auto Views cannot remove user-owned Views                                                                                                  | 08, 11                           |
| R085 | Dirty lifecycle distinguishes Prompt synthesis, acquisition, Evidence, Lift, and Candidate states                                                     | 12                               |
| R086 | Anchor Stable Mask change invalidates support, bootstrap, plan, Prompt, acquisition, Evidence, and Lift dependencies                                  | 08, 12                           |
| R087 | Confirmed per-view correction dirties only that View Evidence/Lift by default                                                                         | 12                               |
| R088 | No Prompt/Mask refresh or fallback automatically Re-Lifts                                                                                             | 12, 15                           |
| R089 | Only Render Ready + Stable Mask + Included Views contribute formal P/N/V                                                                              | 14, 20                           |
| R090 | Support, bootstrap, Prompt, model score, Decision, backend/fallback, tracker state, and View role are not P/N/V                                       | 14, 20                           |
| R091 | Render Working Set preserves compositing contributors while Evidence Working Set controls P/N/V writes                                                | 14, 19, 20                       |
| R092 | Later Included Views may expand Evidence Working Set beyond Anchor support/bootstrap seed                                                             | 14, 20                           |
| R093 | Unobserved or mixed Gaussian support becomes Uncertain, not default Rejected                                                                          | 14, 20                           |
| R094 | Candidate contains Selected only and publication is atomic                                                                                            | 14, 15, 20                       |
| R095 | Re-Lift is explicit and changed inputs make Candidate stale                                                                                           | 12, 14, 15                       |
| R096 | Native Set/Add/Remove/Intersect use Native Selection/EditHistory                                                                                      | 16                               |
| R097 | Undo-and-Fix restores pre-apply Native Selection and returns to correction flow                                                                       | 17                               |
| R098 | Future route C/D production requires a separate experiment-backed ADR                                                                                 | 08A, 08B, 12, 21                 |
| R099 | Final hardening covers support/planner/Prompt/proposal/fallback/resource/interaction failure matrices                                                 | 21                               |
| R100 | Legacy tracking-mandatory and complete-Contributor product paths are explicitly contracted out                                                        | 22                               |
| R101 | Attempt-level backend diagnostics have exactly one authority on PerViewMaskAcquisitionResult and are not duplicated in ProposalSet                    | 08A, 08B, 21                     |
| R102 | Legacy generated-view provider-returned Assessment is not part of the current acquisition result contract                                             | 08B, 12, 21                      |
| R103 | Generic route-B provenance does not use fixed maskSource='propagated' or GeneratedViewMaskPropagation as the truth source                             | 08B, 12, 21                      |
| R104 | Legacy generated-view-mask/v1 payloads and caches fail current contract validation and cannot be structurally rebound                                 | 08B, 12, 21                      |
| R105 | Ordinary UI exposes only Connecting/Available/Unavailable AI Select Availability and no endpoint, model selector, Ping, or raw runtime diagnostics    | 02C                              |
| R106 | Readiness starts asynchronously, uses single-flight automatic retry, and never blocks native editor startup                                           | 02C, 21                          |
| R107 | The Companion resolves one initialized Active Model Manifest; the browser binds it but never selects a model                                          | 02C, 21                          |
| R108 | Lightweight heartbeat is separate from full Runtime Profile validation and Companion Instance replacement triggers revalidation                       | 02C, 21                          |
| R109 | Capacity Busy and task-local failures do not change service Availability; service loss preserves local inspection/editing and valid native operations | 02C, 21                          |
| R110 | Loopback defaults and trusted-LAN endpoint/profile configuration remain operator/deployment-owned and are never auto-discovered                       | 02C, 21                          |

## Coverage result

- Current consolidated requirements: **110**
- Invalid ticket references: **0**
- Unmapped Final Spec v1.2 requirements: **0**
- Orphan tickets: **0**
- Historical overlay required: **no**
- Current ticket mapping authority present: **yes**
- Active ticket requires historical Amendment: **no**
- Route-B comparison gate required: **no**
- Current tracker implementation required: **no**

## Reverse ownership summary

```text
01–07A
= target, authoritative RGB, Prompt, Anchor Stable authority, local assessment

02C
= automatic runtime readiness + operator-owned Active Model + minimal Availability UI

07B
= complete no-blind-spot Prompt/Edit interaction

08
= VisibleTargetSupportArtifact + TargetBootstrapArtifact + SparseKeyViewPlanSegment

08A
= acquisition schemas + identity + Backend Bundle / Registry + optional sequence contracts
  + single diagnostics authority + exact Decision/ProposalSet binding

08B
= Prompt synthesis + route-B provider + ProposalSet Decision + assessment integration
  + publication + route-A B2 fallback + legacy acquisition migration

09 / 11 / 12
= inspection, user Views, refresh and dirty/stale lifecycle

14 / 20
= formal P/N/V ownership only

15–22
= correction, Native application, lifecycle, production hardening, legacy contraction
```
