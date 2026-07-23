# Final Spec v1.1 → Ticket Traceability Matrix

A requirement counts as covered only when the mapped ticket contains an explicit acceptance/failure/validation criterion. A neighboring-subsystem mention does not count. Final Spec v1.0 requirements inherited by v1.1 remain in the matrix; DG-20 additions are included explicitly.

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
| R018 | Prompt triggers single-frame SAM feedback | 04, 05 |
| R019 | Brush updates Editing Mask locally | 04, 05 |
| R020 | Clear Mask and Restore Auto are distinct | 05 |
| R021 | Fully manual Mask is legal | 05, 11 |
| R022 | Mask-local Undo/Redo routes by focus | 05 |
| R023 | Anchor hard validation blocks Confirm | 05 |
| R024 | Anchor soft warning is user-overridable | 05 |
| R025 | Confirm Anchor atomically binds coherent Camera/RGB/Mask/policy/dependency identity | 05 |
| R026 | Confirm Anchor starts adaptive multi-view/initial auto-complete | 06, 08 |
| R027 | Generated View publishes progressively at RGB Ready | 06 |
| R028 | Initial Generated View automatic Mask production exists | 06 |
| R029 | Generated frustum selectable, not pose-editable | 06, 09 |
| R030 | Adaptive planner has bounded budget and no fixed user View count | 08 |
| R031 | Stop Generation preserves completed artifacts | 08 |
| R032 | Generate More is incremental | 08 |
| R033 | Regenerate Auto Views preserves user-owned Views | 08, 11 |
| R034 | Planner stop/gain uses target observation and diversity, not whole-scene denominator | 08, 13 |
| R035 | Gallery is single-row with stable order | 09 |
| R036 | Gallery status, participation, and selection visuals are separate | 09 |
| R037 | Gallery filters never change Participation | 09 |
| R038 | Needs Attention review queue exists | 09 |
| R039 | Frustum↔Gallery selection sync | 09 |
| R040 | Inspect AI Cameras reuses Camera Inspection without retargeting Anchor | 09 |
| R041 | No ordinary Delete View | 09 |
| R042 | User-added View: Use Current View | 11 |
| R043 | User-added View: Adjust New View via Camera Inspection | 11 |
| R044 | User-added View may have No Mask and supports Auto/Manual/Exclude | 11 |
| R045 | View source does not determine trust | 07, 11 |
| R046 | Mask Quality/Assessment and Participation are separate | 07 |
| R047 | Auto Good defaults Included | 07 |
| R048 | Auto Review defaults Excluded and does not secretly Lift | 07 |
| R049 | Review need not globally block Lift | 13 |
| R050 | ViewAssessmentPolicy is backend-owned and evidence-backed | 07, 10 |
| R051 | P0 Review reasons implemented | 07 |
| R052 | P1 cross-view/visible-support reasons implemented | 10 |
| R053 | No unified uncalibrated Confidence percentage | 07, 10 |
| R054 | User Confirmed authority cannot be overridden by assessor | 07, 10 |
| R055 | Review reason maps to localized recommended action | 07, 10 |
| R056 | Explicit propagation/Evidence/Lift dirty and Suspended model | 12, 18 |
| R057 | Editing Mask not Confirmed does not dirty/stale formal artifacts | 12, 15 |
| R058 | Anchor/reference Stable change dirties propagation, Anchor Evidence, and Lift | 12 |
| R059 | Normal View Stable/Participation changes dirty Evidence/Lift as specified | 12 |
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
| R074 | Candidate structural correction returns to observations + explicit Re-Lift | 15 |
| R075 | Candidate cannot be directly 3D patched | 15 |
| R076 | Native Set/Add/Remove/Intersect exact set algebra | 16 |
| R077 | Operations use Native SelectOp/EditHistory | 16 |
| R078 | AI Select remains active after Candidate application | 16 |
| R079 | Native Undo/Redo does not rerun AI | 16 |
| R080 | Candidate Applied preserves application correlation and Show AI Result | 16 |
| R081 | Undo and Fix only when safely undoable | 17 |
| R082 | Restart Current Target available at all lifecycle stages | 05, 17 |
| R083 | Restart preserves Native Selection/EditHistory/policy/cache and rotates targetContextId | 05, 17 |
| R084 | Continuous multi-object flow has no implicit Add/session stack | 17 |
| R085 | Tool switch disposes active AI target context | 17 |
| R086 | Selection/UI-only scene changes do not suspend | 18 |
| R087 | AI dependency mutation → Suspended with artifacts preserved read-only | 18 |
| R088 | Exact semantic Undo token restores compatible Suspended context | 18 |
| R089 | No cross-dependency partial artifact repair | 18 |
| R090 | Companion Offline leaves native SuperSplat functional | 02, 21 |
| R091 | Preview failure preserves last valid preview as stale/not-current + retry | 03, 21 |
| R092 | Mask failure preserves View and offers retry/manual/exclude | 06, 07, 11, 21 |
| R093 | View Render Failure offers retry/replacement/exclude | 06, 08, 11, 21 |
| R094 | Evidence/Lift failure preserves stable inputs and previous Candidate | 14, 15, 20, 21 |
| R095 | Cancellation/OOM cannot publish partial Ready artifacts | 20, 21 |
| R096 | Large SceneSnapshot/tensor/RGB data path is production-validated | 19 |
| R097 | Production Direct Evidence path is GPU-validated | 20, 21 |
| R098 | Mask/Evidence/thumbnail lifecycle is bounded | 20 |
| R099 | Planner/assessment/readiness/Evidence policies are benchmark-calibrated | 21 |
| R100 | Legacy product path contracts only after v1.1 replacement validation | 22 |
| R101 | RGB Ready does not require Contributor, Stable Mask, Evidence, or Candidate | 03, 04, 06, 11 |
| R102 | Explicit Retry creates a real new attempt for the same CameraBinding | 03, 21 |
| R103 | Same attempt may replay idempotently; CameraBinding is not jittered to bypass cache | 03, 21 |
| R104 | Successful RGB cannot be converted into View Failure by Evidence/reference Contributor failure | 03, 04, 06, 20, 21 |
| R105 | Stable Mask publication invalidates exact dependent per-view Evidence | 04, 12, 15 |
| R106 | Formal Evidence channels are per-view per-Gaussian P/N/V using alpha×incoming-T | 14, 20 |
| R107 | Mask policy includes strong positive, boundary/ignore, local negative, and far neutral regions | 14 |
| R108 | Soft weights and explicit ignore are allowed; positive/negative need not sum to one | 14 |
| R109 | Production RGB and Evidence share one authoritative decision source | 20 |
| R110 | Multi-pass production is allowed only when later passes reuse authoritative decisions | 20 |
| R111 | No nearest/top-k/distance/center/visibility-only attribution fallback | 14, 20, 21 |
| R112 | Render Working Set and Evidence Working Set are distinct | 14, 19, 20 |
| R113 | Non-Evidence Gaussians still participate in occlusion/transmittance | 14, 19, 20 |
| R114 | Per-view Evidence artifact binds Camera/RGB/Mask/policy/working sets/Stable IDs/runtime | 12, 14, 20 |
| R115 | Per-view raw Evidence supports Exclude/reinclude, Mask replacement, and incremental Re-Lift | 14, 15, 20 |
| R116 | Complete Contributor is debug/reference only | 03, 14, 19, 20, 22 |
| R117 | Cross-view assessment consumes version-bound P/N/V/visibility | 10 |
| R118 | Coverage uses Visible Mass over Core Target Set | 13 |
| R119 | Insufficient Visible Mass maps to Uncertain | 14, 13 |
| R120 | Mixed positive/negative support maps to Uncertain | 14, 20, 21 |
| R121 | Atomic accumulation is accepted by classification stability, not bit-exact sums | 20, 21 |
| R122 | Reference P/N/V PoC precedes production Direct Evidence | 14, 20 |
| R123 | Production Direct Evidence has pinned source/build/runtime ownership | 20, 21 |
| R124 | Evidence OOM/failure preserves RGB/View/Mask and publishes no partial artifact | 20, 21 |
| R125 | Reference Contributor failure does not block RGB or successful Direct Evidence | 03, 14, 20, 21, 22 |

## Reverse mapping result

Every active ticket maps back to at least one Final Spec v1.1, inherited v1.0, ADR 0013, migration, or hardening requirement. No orphan ticket remains. Tickets 14 and 20 are intentionally separate: Ticket 14 proves the Evidence model through a reference path; Ticket 20 owns the locked same-decision production implementation.