# Final Spec v1.1 → Ticket Traceability Matrix — v2.5

A requirement counts as covered only when the mapped ticket contains an explicit acceptance/failure/validation criterion. Final Spec v1.0 requirements inherited by v1.1 remain included; DG-20–23 and Amendments 001–003 are explicit.

| ID | Requirement | Ticket(s) |
|---|---|---|
| R001 | AI Select is a native Selection Tool, not a workspace | 02, 22 |
| R002 | Exactly one Current Target Context | 01, 17 |
| R003 | DG-14 Candidate provenance UI remains out of scope | 07, 09, 10, 14, 15, 20, 22 |
| R004 | All AI RGB is authoritative gsplat output | 02, 03, 06, 11, 19 |
| R005 | Frustum and gsplat use the same CameraBinding | 02, 03, 06, 11 |
| R006 | Preview/result latest-only binding | 01, 02, 03, 18, 21 |
| R007 | AI work binds targetContextId + dependency identity | 01, 02, 18 |
| R008 | Current View First Anchor | 02 |
| R009 | Activation does not move Editor Camera | 02 |
| R010 | Explicit Camera Inspection | 03, 09, 11 |
| R011 | Observer camera is not Anchor CameraBinding | 03, 05 |
| R012 | Dragging updates Camera/frustum only; final RGB at manipulation end | 03 |
| R013 | Return restores Scene View; Reset Anchor exists | 03 |
| R014 | Prompt/target intent protects Anchor changes | 05 |
| R015 | View may be RGB Ready without Mask or Evidence | 04, 06, 11 |
| R016 | Render, Mask, Evidence, and Lift failures are distinct | 03, 04, 06, 09, 21 |
| R017 | Stable/Editing Mask isolation | 04, 05, 12 |
| R018 | Prompt changes request model feedback without hidden apply | 04, 05, 04A |
| R019 | Paint/Erase updates Editing Mask locally | 04, 05, 04A |
| R020 | Clear Mask and Restore Auto are distinct | 05, 04A, 07A |
| R021 | Fully manual Mask is legal | 05, 11, 07A |
| R022 | Mask-local Undo/Redo routes by focus | 05, 04A |
| R023 | Anchor hard validation blocks Confirm | 05, 07A |
| R024 | Anchor soft warning is user-overridable | 05, 07A |
| R025 | Confirm Anchor atomically binds Camera/RGB/Mask/policy/dependency | 05, 07A |
| R026 | Confirm Anchor starts adaptive multi-view completion | 06, 08 |
| R027 | Generated View publishes progressively at RGB Ready | 06, 08A |
| R028 | Generated View automatic Mask production exists | 06, 08A |
| R029 | Generated frustum selectable, not pose-editable | 06, 09 |
| R030 | Adaptive planner has bounded budget and no fixed user View count | 08 |
| R031 | Stop Generation preserves completed artifacts | 08 |
| R032 | Generate More is incremental | 08 |
| R033 | Regenerate Auto Views preserves user-owned Views | 08, 11 |
| R034 | Planner gain uses target observation/diversity, not whole-scene denominator | 08, 13 |
| R035 | Gallery is scalable with stable order | 09 |
| R036 | Gallery status, Participation, role, and selection remain separate | 09 |
| R037 | Gallery filters never change Participation | 09 |
| R038 | Needs Attention review queue exists | 09 |
| R039 | Frustum↔Gallery selection sync | 09 |
| R040 | Inspect AI Cameras reuses Camera Inspection without retargeting Anchor | 09 |
| R041 | No ordinary Delete View | 09 |
| R042 | User-added View: Use Current View | 11 |
| R043 | User-added View: Adjust New View | 11 |
| R044 | User-added View may have No Mask and supports Auto/Manual/Exclude | 11 |
| R045 | View source does not determine trust | 07, 11 |
| R046 | Mask Assessment and Participation are separate | 07, 07A, 09 |
| R047 | Auto Good defaults Included where policy permits | 07 |
| R048 | Auto Review defaults Excluded and does not secretly Lift | 07 |
| R049 | Review need not globally block Lift | 13 |
| R050 | ViewAssessmentPolicy is backend-owned and evidence-backed | 07, 10 |
| R051 | P0 Review reasons implemented | 07 |
| R052 | P1 cross-view/visible-support reasons implemented | 10 |
| R053 | No unified uncalibrated Confidence percentage | 07, 10, 07A, 08A |
| R054 | User Confirmed authority cannot be overridden by assessor | 07, 10, 07A |
| R055 | Review reason maps to localized action | 07, 10 |
| R056 | Explicit propagation/Evidence/Lift dirty and Suspended model | 12, 18 |
| R057 | Unconfirmed Editing Mask does not dirty formal artifacts | 12, 15, 04A, 07A |
| R058 | Anchor/reference Stable change dirties propagation, Anchor Evidence, Lift | 12 |
| R059 | Normal View Stable/Participation changes dirty Evidence/Lift | 12 |
| R060 | Repropagate is explicit | 12 |
| R061 | Repropagate never automatically Re-Lifts | 12 |
| R062 | Repropagate failure preserves old Stable Masks | 12, 21 |
| R063 | Observation Coverage is target-scoped Visible Evidence | 13 |
| R064 | View Diversity is separate from View count | 13 |
| R065 | Lift Readiness is Not Ready/Limited/Ready | 13 |
| R066 | Stop/planner completion refreshes readiness | 13 |
| R067 | Lift consumes Included Stable View Annotations only | 14 |
| R068 | Unobserved is not Rejected by default | 14, 13 |
| R069 | Candidate and Uncertain are distinct | 14 |
| R070 | Lift does not mutate Native Selection | 14 |
| R071 | Candidate publication is atomic | 14, 15, 21 |
| R072 | Stable input change makes Candidate Stale | 12, 14, 15 |
| R073 | Stale Candidate cannot apply native operations | 14, 15, 16 |
| R074 | Candidate structural correction returns to observations + Re-Lift | 15 |
| R075 | Candidate cannot be directly 3D patched | 15 |
| R076 | Native Set/Add/Remove/Intersect exact set algebra | 16 |
| R077 | Operations use Native SelectOp/EditHistory | 16 |
| R078 | AI Select remains active after Candidate application | 16 |
| R079 | Native Undo/Redo does not rerun AI | 16 |
| R080 | Candidate Applied preserves correlation and Show AI Result | 16 |
| R081 | Undo and Fix only when safely undoable | 17 |
| R082 | Restart Current Target available at all stages | 05, 17 |
| R083 | Restart preserves Native Selection/EditHistory/policy/cache and rotates context | 05, 17 |
| R084 | Continuous multi-object flow has no implicit Add/session stack | 17 |
| R085 | Tool switch disposes active AI target context | 17 |
| R086 | Selection/UI-only scene changes do not suspend | 18 |
| R087 | AI dependency mutation → Suspended with artifacts preserved | 18 |
| R088 | Exact semantic Undo token restores compatible context | 18 |
| R089 | No cross-dependency partial artifact repair | 18 |
| R090 | Companion Offline leaves native SuperSplat functional | 02, 21 |
| R091 | Preview failure preserves last valid preview + retry | 03, 21 |
| R092 | Mask/tracker failure preserves View and offers recovery | 06, 07, 08A, 09, 11, 21, 07A |
| R093 | View Render Failure offers retry/replacement/exclude | 06, 08, 11, 21 |
| R094 | Evidence/Lift failure preserves stable inputs and previous Candidate | 14, 15, 20, 21 |
| R095 | Cancellation/OOM cannot publish partial Ready artifacts | 20, 21, 04A, 04B, 08A |
| R096 | Large SceneSnapshot/tensor/RGB path is production-validated | 19 |
| R097 | Production Direct Evidence path is GPU-validated | 20, 21 |
| R098 | Mask/Evidence/thumbnail lifecycle is bounded | 20, 04A, 07A, 08A, 09 |
| R099 | Planner/assessment/readiness/Evidence policies are benchmark-owned | 08, 10, 13, 21 |
| R100 | Legacy product path contracts only after replacement validation | 22 |
| R101 | RGB Ready does not require Contributor/Stable Mask/Evidence/Candidate | 03, 04, 06, 11 |
| R102 | Explicit Retry creates a new attempt for same CameraBinding | 03, 08A, 21 |
| R103 | Same attempt may replay idempotently; no camera jitter cache bypass | 03, 08A, 21 |
| R104 | Successful RGB cannot become View Failure due to Evidence/reference failure | 03, 04, 06, 20, 21 |
| R105 | Stable Mask publication invalidates dependent per-view Evidence | 04, 12, 15, 07A |
| R106 | Formal Evidence is per-view per-Gaussian P/N/V using alpha×incoming-T | 14, 20 |
| R107 | Mask policy has strong positive, ignore boundary, local negative, far neutral | 14 |
| R108 | Soft weights/ignore allowed; positive/negative need not sum to one | 14 |
| R109 | Production RGB and Evidence share one decision source | 20 |
| R110 | Multi-pass production only reuses authoritative decisions | 20 |
| R111 | No nearest/top-k/distance/center attribution fallback | 14, 20, 21 |
| R112 | Render Working Set and Evidence Working Set are distinct | 14, 19, 20 |
| R113 | Non-Evidence Gaussians still participate in occlusion/transmittance | 14, 19, 20 |
| R114 | Evidence artifact binds Camera/RGB/Mask/policy/sets/IDs/runtime | 12, 14, 20 |
| R115 | Raw Evidence supports Exclude/reinclude, Mask replacement, incremental Re-Lift | 14, 15, 20 |
| R116 | Complete Contributor is debug/reference only | 03, 14, 19, 20, 22 |
| R117 | Cross-view assessment consumes version-bound P/N/V/visibility | 10 |
| R118 | Coverage uses Visible Mass over Core Target Set | 13 |
| R119 | Insufficient Visible Mass maps to Uncertain | 14, 13 |
| R120 | Mixed positive/negative support maps to Uncertain | 14, 20, 21 |
| R121 | Atomic accumulation accepted by classification stability, not bit-exact sums | 20, 21 |
| R122 | Reference P/N/V PoC precedes production Direct Evidence | 14, 20 |
| R123 | Production Direct Evidence has pinned source/build/runtime | 20, 21 |
| R124 | Evidence OOM/failure preserves RGB/View/Mask and no partial artifact | 20, 21 |
| R125 | Reference Contributor failure does not block RGB/Direct Evidence | 03, 14, 20, 21, 22 |
| R126 | RGB/Evidence bind rasterImplementationId/backend/runtimeBuildId | 14, 16, 19, 20, 21 |
| R127 | RGB-only and later Evidence use compatible raster identity | 19, 20, 21 |
| R128 | PromptState is versioned, RGB-bound, and cannot mutate Stable Mask | 04A, 07A |
| R129 | Prompt/Edit tools and pointer semantics are explicit | 04A, 04B, 07B |
| R130 | Prompt support is declared per family and polarity | 04A, 04B |
| R131 | Unsupported Prompt types are disabled/rejected, never ignored | 04A, 04B |
| R132 | Stage 1 preserves bounded proposals and raw-score semantics | 04A, 04B, 07A |
| R133 | Proposal decision cannot collapse solely to raw model score | 07A |
| R134 | Stage 2 is 2D-first with Prompt consistency and structural quality | 07A |
| R135 | Low-cost Gaussian support is optional diagnostics, not ownership | 07A |
| R136 | Ambiguity is first-class and preserves alternatives/actions | 07A |
| R137 | ProposalDecision is separate from ViewAssessment/Participation | 07, 07A |
| R138 | Only Confirm publishes Stable; unconfirmed work does not dirty formal artifacts | 04A, 07A, 12 |
| R139 | Proposal failed/unavailable/ambiguous/artifact-invalid remain distinct | 07A, 21 |
| R140 | 07A requires locked real-model quality validation | 07A |
| R141 | Mandatory Three-Stage pipeline applies to Anchor | 04A, 07A |
| R142 | Planner follows resolved Anchor and validates pose before gain | 08 |
| R143 | Box/Mask capabilities require truthful locked adapter; Text optional | 04B |
| R144 | Visual Prompts compile deterministically; unsupported combinations fail closed | 04B |
| R145 | Palette supports drag/snap/collapse/Space hide inside fitted image | 07B |
| R146 | Palette move/collapse/hide restores hit testing immediately | 07B |
| R147 | Palette state is Target Context-scoped and resets on Restart | 07B |
| R148 | v1 targets one object instance; arbitrary parts and whole-image inventory are not required | 07A, 08A |
| R149 | Confirmed Anchor Stable Mask is object-identity seed, not Gaussian ownership | 07A, 08, 14 |
| R150 | Early depth/first-hit support is 2.5D bootstrap only | 08, 14 |
| R151 | Planner outputs ordered Key/Bridge sequence with validity/gain/transition separated | 08 |
| R152 | Tracking membership is distinct from Lift Participation | 08, 09, 14 |
| R153 | Production multi-view Mask path uses object-level tracking; single-frame SAM remains explicit baseline/fallback | 06, 08A |
| R154 | Only confirmed correction Stable Masks enter tracker memory; repropagate is explicit | 08A, 12 |
| R155 | Bridge Views default Excluded and do not automatically contribute Evidence | 08, 09, 14 |
| R156 | Tracking artifacts bind Anchor/plan/backend/runtime/reference/attempt identities | 08A, 12 |
| R157 | Tracker confidence and bootstrap support are not P/N/V ownership Evidence | 08A, 14, 20 |
| R158 | Final ownership remains Included Stable Masks → per-view P/N/V → multi-view classification | 14, 20 |
| R159 | Tracked Mask publication is progressive/atomic; tracker failure preserves RGB/prior Stable state | 08A, 09, 12 |

## Reverse mapping result

Every active ticket, including retrofit Tickets 04A, 04B, 07A, 07B, and 08A, maps back to Final Spec v1.1, Amendments 001–003, DG-20–23, inherited v1.0, migration, or hardening requirements. No orphan ticket remains.

04A owns Prompt/proposal infrastructure. 04B owns real visual-prompt adapter enablement. 07A owns conservative object-level Anchor acquisition. 07B owns fitted-image palette interaction. 08 owns non-ownership 2.5D Key/Bridge sequence planning. 08A owns tracking/correction memory and fallback. 12 owns explicit repropagation. 14/20 remain the reference/production P/N/V ownership stages.