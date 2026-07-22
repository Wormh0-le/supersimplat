# Final Spec v1.0 → Ticket Traceability Matrix

A requirement counts as covered only when the mapped ticket contains explicit acceptance/failure criteria; neighboring-subsystem mentions do not count.

| ID | Requirement | Ticket(s) |
|---|---|---|
| R001 | AI Select is a native Selection Tool, not a workspace | 02, 22 |
| R002 | Exactly one Current Target Context | 01, 17 |
| R003 | DG-14 Candidate provenance UI is out of scope | 14, 15, 21, 22 |
| R004 | All AI RGB is authoritative gsplat output | 02, 03, 06, 11 |
| R005 | Frustum and gsplat use the same CameraBinding | 02, 03, 06, 11 |
| R006 | Preview/result latest-only binding | 01, 02, 03, 18, 21 |
| R007 | AI request/result binds targetContextId + dependency identity | 01, 02, 18 |
| R008 | Current View First Anchor | 02 |
| R009 | Activation does not move Editor Camera | 02 |
| R010 | Explicit Camera Inspection | 03, 09, 11 |
| R011 | Observer camera != Anchor CameraBinding | 03, 05 |
| R012 | Interactive low-res/RGB-only/throttled preview; final-resolution on manipulation end | 03 |
| R013 | Return restores Scene View; Reset Anchor exists | 03 |
| R014 | Prompt/target intent protects Anchor changes | 05 |
| R015 | View may exist without Mask | 04, 06, 11 |
| R016 | View render failure != Mask failure | 04, 06, 07 |
| R017 | Stable/Editing Mask isolation | 04, 05 |
| R018 | Prompt single-frame SAM feedback | 04, 05 |
| R019 | Brush updates Editing Mask locally | 04, 05 |
| R020 | Clear Mask and Restore Auto are distinct | 05 |
| R021 | Fully manual mask is legal | 05, 11 |
| R022 | Mask-local Undo/Redo routes by focus | 05 |
| R023 | Anchor hard validation blocks Confirm | 05 |
| R024 | Anchor soft warning is user-overridable | 05 |
| R025 | Confirm Anchor atomically binds coherent Anchor revision | 05 |
| R026 | Confirm Anchor starts adaptive multi-view/initial auto-complete | 06, 08 |
| R027 | Initial Generated View publishes progressively before Mask completion | 06 |
| R028 | Initial Generated View automatic Mask propagation exists | 06 |
| R029 | Generated frustum selectable, not pose-editable | 06, 09 |
| R030 | Adaptive planner has bounded min/max and no fixed user count | 08 |
| R031 | Stop Generation preserves completed artifacts | 08 |
| R032 | Generate More is incremental | 08 |
| R033 | Regenerate Auto Views preserves user-owned Views | 08, 11 |
| R034 | Planner stop/readiness uses target observation/diversity, not whole-scene denominator | 08, 13 |
| R035 | Gallery is single-row with stable order | 09 |
| R036 | Gallery status/participation/selection visual dimensions are separate | 09 |
| R037 | Gallery filter does not change Participation | 09 |
| R038 | Needs Attention review queue exists | 09 |
| R039 | Frustum↔Gallery selection sync | 09 |
| R040 | Inspect AI Cameras uses Camera Inspection without retargeting Anchor | 09 |
| R041 | No ordinary Delete View in v1.0 | 09 |
| R042 | User-added View: Use Current View | 11 |
| R043 | User-added View: Adjust New View via Camera Inspection | 11 |
| R044 | User-added View may have No Mask and supports Auto/Manual/Exclude | 11 |
| R045 | View source does not determine trust | 07, 11 |
| R046 | Mask Quality/Assessment and Participation are separate | 07 |
| R047 | Auto Good defaults Included | 07 |
| R048 | Auto Review defaults Excluded and does not secretly Lift | 07 |
| R049 | Review need not globally block Lift | 13 |
| R050 | ViewAssessmentPolicy is backend-owned and evidence-backed | 07, 10 |
| R051 | P0 reasons implemented | 07 |
| R052 | P1 cross-view/visible-support reasons implemented | 10 |
| R053 | No unified uncalibrated Confidence % | 07, 10 |
| R054 | User Confirmed authority cannot be overridden by assessor | 07, 10 |
| R055 | Review reason maps to localized recommended action | 07, 10 |
| R056 | Explicit Dirty/Stale/Suspended model | 12, 18 |
| R057 | Editing Mask not Confirmed does not dirty/stale | 12, 15 |
| R058 | Anchor/reference Stable change dirties propagation + lift | 12 |
| R059 | Normal View Stable/Participation changes dirty Lift only | 12 |
| R060 | Repropagate is explicit | 12 |
| R061 | Repropagate never automatically Re-Lifts | 12 |
| R062 | Repropagate failure preserves old Stable Masks | 12, 21 |
| R063 | Observation Coverage is contributor/target-scoped | 13 |
| R064 | View Diversity is separate from View count | 13 |
| R065 | Lift Readiness is Not Ready/Limited/Ready | 13 |
| R066 | Stop/planner completion immediately refreshes readiness when available | 13 |
| R067 | Lift consumes Included Stable View Annotations only | 14 |
| R068 | Unobserved is not Rejected by default | 14 |
| R069 | Candidate and Uncertain are distinct | 14 |
| R070 | Lift does not mutate Native Selection | 14 |
| R071 | Candidate publication is atomic | 14, 21 |
| R072 | Stable input change makes Candidate Stale | 14, 15 |
| R073 | Stale Candidate cannot apply native operations | 14, 15, 16 |
| R074 | Candidate structural correction returns to View/Mask/Participation + explicit Re-Lift | 15 |
| R075 | Candidate cannot be directly 3D patched in v1.0 | 15 |
| R076 | Native Set/Add/Remove/Intersect exact set algebra | 16 |
| R077 | Operations use Native SelectOp/EditHistory | 16 |
| R078 | AI Select remains active after Candidate application | 16 |
| R079 | Native Undo/Redo does not rerun AI | 16 |
| R080 | Candidate Applied Show AI Result / application correlation | 16 |
| R081 | Undo and Fix only when safely undoable | 17 |
| R082 | Restart Current Target available at all lifecycle stages | 05, 17 |
| R083 | Restart preserves Native Selection/EditHistory/runtime policy/cache and rotates targetContextId | 05, 17 |
| R084 | Continuous multi-object flow has no implicit Add mode/session stack | 17 |
| R085 | Tool switch exits/disposes AI target context | 17 |
| R086 | Selection/UI-only scene changes do not suspend | 18 |
| R087 | AI dependency mutation → Suspended, artifacts preserved read-only | 18 |
| R088 | Exact semantic Undo token restores Suspended context | 18 |
| R089 | No partial artifact repair in v1.0 | 18 |
| R090 | Companion Offline leaves native SuperSplat functional | 02, 21 |
| R091 | Preview failure preserves last valid preview + retry | 03, 21 |
| R092 | Mask failure preserves View and offers retry/manual/exclude | 06, 07, 11, 21 |
| R093 | View render failure offers retry/replacement/exclude | 06, 07, 08, 21 |
| R094 | Lifting failure preserves Views/Stable Masks/Gallery; Candidate unchanged | 14, 21 |
| R095 | Cancellation/OOM cannot publish partial ready artifacts | 21 |
| R096 | Large SceneSnapshot and gsplat tensor/contributor cache are production-validated | 19 |
| R097 | GPU Evidence aggregation/working-set path is production-validated | 20 |
| R098 | Mask artifact GC and thumbnail lifecycle are bounded | 20 |
| R099 | Planner/assessment/readiness/camera policies are benchmark-calibrated | 21 |
| R100 | Legacy New/Add/Remove/Refine + preview-confirm-close product path is contracted only after replacement is validated | 22 |
