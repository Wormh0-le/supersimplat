# SuperSimPlat AI Select — Domain Context

This context defines the current **AI Select Final Spec v1.0** vocabulary for turning a user's object-level intent into a native SuperSplat Gaussian Selection.

The current product model supersedes the older PoC workflow based on a user-visible `Object Selection Session`, `Prompt Log`, `Mask Track`, `New/Add/Remove/Refine`, fixed Correction Rounds, and one-shot Selection Commit. Those terms remain documented in the **Legacy PoC Vocabulary** section only for compatibility with existing code, fixtures, benchmark records, and migration work.

## Current Product Vocabulary

**AI Select**  
A SuperSplat Selection Tool that builds an AI Candidate from gsplat-rendered multi-view observations and then applies that Candidate through native selection operations. AI Select is not a separate semantic-object workspace or persistent object database.  
_Avoid_: standalone segmentation app, semantic object manager

**Gaussian Selection**  
The native editor set of Gaussian indices/IDs targeted by an existing SuperSplat operation, independent of how those Gaussians were inferred.  
_Avoid_: 3D mask, semantic object

**AI Candidate**  
The transient Gaussian set produced by Gaussian Lifting from the current Included Stable View Annotations. It may be visualized together with Uncertain Gaussians but does not modify Native Selection until the user explicitly chooses Set, Add, Remove, or Intersect.  
_Avoid_: committed selection, editable 3D mask

**AITarget / Target Splat**  
The one Active Splat currently targeted by AI Select, bound to the scene/splat dependency state required by rendering and lifting. AI Select v1.0 does not combine candidate IDs across multiple Target Splats in one target context.  
_Avoid_: whole scene, persistent semantic instance

**Stable Gaussian ID**  
An editor-owned identity that refers to the same Gaussian throughout a compatible immutable target-content state, independent of PLY row, renderer ordering, draw order, or Companion tensor position.  
_Avoid_: render index, tensor row, file row

**Scene Snapshot**  
An immutable, versioned representation of the Target Splat geometry/appearance and effective render semantics supplied to the Companion. It is transient inference input, not a saved project or semantic sidecar.  
_Avoid_: source PLY identity, project save, object cache

**Current Target Context**  
The single user-visible AI Select context for the object currently being worked on. It owns the Anchor, AI Views, Mask versions, Participation, Coverage/Readiness, Candidate, and Uncertain state. `Restart Current Target` disposes it and creates a new context while Native Selection/EditHistory and runtime caches remain.  
_Avoid_: persistent multi-object session stack

**Runtime Context**  
Reusable non-semantic infrastructure such as loaded models, scene tensors, gsplat caches, contributor caches, Stable ID mappings, Companion connection, and planner/policy settings. Runtime cache reuse does not preserve a previous target's AI View context.  
_Avoid_: saved target session

**CameraBinding**  
The versioned camera truth shared by gsplat AI rasterization and the corresponding 3D Frustum. It uniquely determines pose, intrinsics, resolution, clipping, and camera convention.  
_Avoid_: viewport screenshot metadata, approximate camera pose

**Editor Camera**  
The camera used by the user to navigate the main PlayCanvas/SuperSplat 3D viewport. It is not automatically moved when AI Select activates or Generated Views are produced.  
_Avoid_: Anchor Camera, Generated View camera

**Anchor View**  
The first AI View for the current target. Its CameraBinding is initialized from the Current Editor Camera, while its authoritative AI RGB is rendered by gsplat. Prompting/mask authoring identifies the target represented by this view.  
_Avoid_: PlayCanvas screenshot, generated view

**Anchor Validation**  
The automatic hard/soft validation that determines whether the current Anchor RGB/Mask/Contributor binding is computationally suitable to continue. It does not decide whether the user's semantic target choice is “correct.”  
_Avoid_: target confidence percentage, semantic correctness score

**Generated View**  
A planner-owned AI View rendered by gsplat to increase target observation/diversity without moving the visible Editor Camera. Auto-generated Views may be replaced by planner regeneration; they are not user-owned camera assets.  
_Avoid_: source capture, camera animation

**User-added View**  
An AI View explicitly created from the user's chosen camera (`Use Current View` or `Adjust New View`). It is user-owned relative to planner regeneration, but remains target-local and is discarded on Restart Current Target.  
_Avoid_: persistent project camera

**AI View**  
A target-local observation record that may contain CameraBinding, gsplat RGB, Contributor artifact, source, render status, Participation, and zero or more Mask versions. A View can be valid without a Mask.  
_Avoid_: inseparable Camera+RGB+Mask tuple

**AI View Dock**  
The bottom editing surface for gsplat AI RGB, Gallery navigation, 2D Mask prompting/brush editing, Mask version state, View assessment, and related actions. Main 3D viewport remains responsible for Frustums, Candidate/Uncertain overlays, and native selection visualization.  
_Avoid_: separate AI workspace

**Camera Inspection**  
An explicit mode that saves the user's Scene View Camera, moves the Editor Camera to an external observer pose, and exposes the Anchor/selected AI View Frustum for spatial inspection/manipulation. Exiting restores the saved Scene View. The observer pose is never silently adopted as the Anchor.  
_Avoid_: normal scene navigation

**MaskAnnotation**  
A versioned 2D annotation bound to one AI View and the RGB digest from which it was authored/generated. It may originate from single-frame SAM, propagation, manual authoring, or a hybrid workflow.  
_Avoid_: Gaussian Selection, 3D mask

**Stable Mask**  
The currently published MaskAnnotation version permitted to participate in Observation Coverage and Gaussian Lifting. It is referenced by `stableMaskId`.  
_Avoid_: current brush canvas, draft mask

**Editing Mask**  
An unpublished MaskAnnotation version being generated or edited. It is referenced by `editingMaskId` and does not replace the Stable Mask until Confirm Mask atomically publishes it.  
_Avoid_: stable lifting input

**Confirm Mask**  
The explicit atomic publication that promotes the current Editing Mask to the new Stable Mask. It is not Candidate application and does not modify Native Selection.  
_Avoid_: Selection Commit

**Mask Quality / View Assessment**  
The automatic quality state attached to a generated/automatic Mask/View, typically Auto Good, Auto Review, or Failed. It is separate from Participation.  
_Avoid_: participation flag, unified confidence probability

**Review Reason**  
A structured evidence-backed reason explaining why an automatic Mask/View needs inspection. Reasons must be supported by measurable mask, propagation, gsplat contributor/visibility, or cross-view evidence.  
_Avoid_: free-form AI guess, uncalibrated `Confidence XX%`

**ViewAssessmentPolicy**  
The Companion-side versioned policy that derives Good/Review/Failed plus structured Review Reasons from available evidence. It does not override a user-confirmed Stable Mask.  
_Avoid_: SAM confidence passthrough

**Participation**  
Whether one AI View's Stable Mask participates in Coverage/Lifting: `Included` or `Excluded`. Participation is independent from Mask Quality. Auto Good defaults Included; Auto Review defaults Excluded; User Confirmed defaults Included; Failed/no Stable Mask is Excluded.  
_Avoid_: quality score

**Included Stable View Annotation**  
An AI View with a render-ready authoritative observation, an Included participation state, and a Stable Mask version. This is the effective per-view input unit for Gaussian Lifting.  
_Avoid_: every generated view, every mask draft

**Observation Coverage**  
The measured fraction/extent of the relevant target/core Gaussian evidence actually observed through valid gsplat contributors from Included Stable Views. It is not raw view count and must not use whole-scene Gaussian count as the target denominator.  
_Avoid_: number of cameras, whole-scene coverage

**View Diversity**  
A separate measure of directional/viewpoint diversity over useful observations. More Views do not automatically imply higher diversity.  
_Avoid_: view count

**Lift Readiness**  
The derived state `Not Ready`, `Limited`, or `Ready`, based on usable observation and diversity rather than a universal fixed View count. Review Views may remain excluded while Lift is still allowed if the remaining Included evidence is sufficient.  
_Avoid_: fixed N-view gate

**Adaptive View Planner**  
The planner that incrementally generates useful cameras based on target observation, directional diversity, and marginal gain, subject to bounded budgets. The user may Stop Generation, Generate More Views, or Add a View manually.  
_Avoid_: fixed `4/8` generation schedule

**Selection Evidence**  
Per-Gaussian positive, negative, and unobserved evidence accumulated only from valid Included observations under a versioned Evidence Policy. Missing/unusable observation remains unobserved rather than automatically negative.  
_Avoid_: simple majority vote, final mask

**Evidence Policy**  
A versioned, replayable rule that interprets Selection Evidence into selected, rejected, and uncertain states for a declared render/contributor configuration. Policy changes require explicit versioning and benchmark calibration.  
_Avoid_: magic threshold, hidden confidence rule

**Gaussian Lifting**  
The operation that maps Included Stable View Annotations and contributor evidence into the 3D AI Candidate plus Uncertain classification. Re-Lift is explicit after stable upstream inputs change.  
_Avoid_: direct 3D mask painting

**Uncertain Gaussian**  
A Gaussian whose available observation is absent, insufficient, or materially conflicting. It is displayed diagnostically and excluded from Candidate application unless future evidence resolves it.  
_Avoid_: rejected/background Gaussian

**Candidate Stale**  
A state where the current Candidate no longer corresponds to the current stable AI input set (for example, a Stable Mask or Participation changed). It remains inspectable but cannot be applied until explicit Re-Lift succeeds.  
_Avoid_: scene suspension

**Suspended Context**  
A Current Target Context whose underlying scene/render/geometry/identity dependency no longer matches the artifacts it contains. The context is preserved for inspection and exact Undo recovery but cannot be edited, lifted, or applied while suspended.  
_Avoid_: Candidate stale, destroyed session

**TargetDependencyToken**  
A semantic identity for the target dependencies relevant to AI rendering/lifting, covering render state, geometry, Gaussian identity/membership, and world/target transform as needed. Exact Undo may restore the same semantic token.  
_Avoid_: monotonic global scene counter only

**AIRequestBinding**  
The minimum async identity binding carried by AI requests/results: `targetContextId`, `contextRevision`, and `dependencyToken`. A non-matching result is stale and must be discarded regardless of whether cancellation succeeded.  
_Avoid_: request ID alone

**Restart Current Target / 重新选择对象**  
The action that abandons the current target attempt, disposes all target-local Anchor/View/Mask/Candidate state, retains Native Selection/EditHistory and runtime caches, then starts again from the current saved Scene View.  
_Avoid_: exit AI Select, clear native selection

**Native Candidate Operation**  
One of `Set`, `Add`, `Remove`, or `Intersect`, applying the current valid AI Candidate to Native SuperSplat Selection through existing selection/EditHistory semantics.  
_Avoid_: inference mode, Prompt operation

**Set**  
Apply `S' = C`, replacing Native Selection with the current AI Candidate.

**Add**  
Apply `S' = S ∪ C`, unioning the current AI Candidate into Native Selection.

**Remove**  
Apply `S' = S − C`, subtracting the current AI Candidate from Native Selection.

**Intersect**  
Apply `S' = S ∩ C`, intersecting Native Selection with the current AI Candidate.

**Transient AI Selection State**  
Anchor/Views/Masks/Candidate state that exists only for the current target context/runtime. v1.0 does not persist or reopen previous target contexts as semantic project data.  
_Avoid_: object annotation database, persistent AI session

## Selection Service and Runtime Vocabulary

**Selection Service**  
The single-user inference service used by the editor for AI Select on the same machine or a trusted local network. It is not a public authenticated multi-tenant backend.

**Selection Service Companion**  
The separately installed local Python runtime/package implementing the Selection Service. It isolates CUDA, gsplat, SAM, generated-view, assessment, and lifting dependencies from the browser editor distribution.

**Selection Service Endpoint**  
The explicitly configured loopback or trusted-LAN address through which the editor reaches the Companion. It is not automatically discovered.

**Selection Service Readiness**  
The condition in which a reachable Companion has passed capability compatibility for the required protocol, renderer, model adapter/checkpoint, Model Manifest, and locked runtime. Reachable alone is not Ready.

**Companion Process Ownership**  
The operator starts/stops/upgrades the Companion; the browser only owns its target/request resources. Closing or losing the editor does not authoritatively terminate the Companion process.

**Model Manifest**  
The immutable identity of the promptable-mask/model adapter, model artifact/checkpoint, source revision, license metadata, and material runtime configuration used for an AI execution.

**Model Installation**  
An operator-initiated, manifest-verified acquisition of separately distributed model weights into the Companion runtime. Weights are not embedded in the browser/editor distribution.

**Companion Upgrade**  
Operator-initiated replacement of a stopped Companion runtime with a locked version. Do not silently migrate live AI contexts across incompatible runtime identities.

**Trusted-LAN Mode**  
Opt-in deployment of the Companion on a private operator-managed network under explicit endpoint/origin/security policy. It is not an Internet service.

**Companion Session Capacity**  
The maximum concurrently admitted Companion execution contexts. Capacity/admission is a runtime policy and must not be conflated with the user-visible Current Target Context model.

**Selection Service Transport Baseline**  
The browser-compatible secure-context policy for reaching the Companion. Loopback is the default; trusted-LAN requirements remain explicit and fail closed when browser permission/certificate/origin requirements are not met.

**Standalone Gaussian Scene**  
An already reconstructed Gaussian scene that is the sole scene input to AI Select. Original capture images, camera trajectories, sparse reconstructions, and reconstruction-time metadata are not required AI Select inputs.

## Legacy PoC Vocabulary — Superseded for Product Architecture

The following concepts remain valid only when reading historical implementation, fixtures, old issues, or PoC benchmark records. They MUST NOT be treated as the target AI Select v1.0 product model.

**Object Selection Session (legacy)**  
The old user-visible lifetime that bundled prompting, preview correction, Candidate state, and one final commit. Replaced by `Current Target Context` plus independent View/Mask/Candidate lifecycles.

**Prompt Log (legacy product role)**  
The old authoritative chronological sequence of accepted point prompts and New/Add/Remove/Refine operations. Final Spec v1.0 does not use Prompt Log as the product source of truth; prompt data may still exist inside MaskAnnotation provenance, SAM requests, compatibility code, or frozen benchmarks.

**Frame Set (legacy product role)**  
The old immutable ordered batch of Anchor + Generated Views processed as one promptable-mask unit. Final Spec v1.0 models Views independently in an AI View registry and allows progressive publication, user-added Views, and Views with no Mask.

**Mask Track (legacy product role)**  
The old include/exclude track composed chronologically across a Frame Set. Final Spec v1.0 uses independent versioned MaskAnnotations per AI View as the top-level mask model.

**Mask Set (legacy product role)**  
The old complete all-tracks/all-views publication unit. Final Spec v1.0 does not require every View to have a Mask before valid target progress can be published.

**New / Add / Remove / Refine (legacy inference modes)**  
Old AI workflow modes used to modify Prompt Log/Mask Tracks/Candidate before one final commit. They are superseded as product interaction modes. `Add` and `Remove` now refer to native Candidate application operations together with `Set` and `Intersect`.

**Correction Round (legacy)**  
The old bounded inference-preview refresh count. Final Spec v1.0 has explicit Mask confirmation, Repropagate, Re-Lift, Generate More, and correction workflows instead of a product-level fixed correction-round budget.

**Selection Commit (legacy product action)**  
The old single action that handed selected Candidate IDs to the editor and ended the session. Final Spec v1.0 uses explicit Set/Add/Remove/Intersect native operations and keeps AI Select/current target context active after application.

**Cancel (legacy session semantics)**  
The old action that restored entry selection and closed the Object Selection Session. Final Spec separates Restart Current Target, Exit AI Select, native Undo, and mask/candidate correction semantics.

## Benchmark Vocabulary

These terms remain valid for frozen/controlled PoC benchmark infrastructure even where their historical records use legacy workflow vocabulary.

**Benchmark Prompt Log**  
A frozen, point-only benchmark interaction input captured before a trial. It bounds the manual interaction supplied to that historical benchmark revision. It does not define current product-state ownership.

**PoC Technical Specification**  
The decision-ready description of a historical/controlled object-selection experiment, its interfaces, comparison methods, test scenes, acceptance gates, and unresolved technical risks. It is not the current AI Select Final Spec.

**PoC Acceptance Criteria**  
Predeclared, replayable conditions used to judge a frozen PoC benchmark. Do not tune acceptance gates after observing trial scores merely to obtain a pass.

**PoC Trial**  
One replay of a frozen benchmark input under its declared configuration/seed.

**PoC Run Record**  
An immutable, version-bound record of one PoC trial and its bound inputs, outputs, diagnostics, timing/VRAM, artifact hashes, and scoring evidence as defined by that benchmark revision.

**Blind Prediction**  
A prediction phase that cannot access Benchmark Ground Truth before the candidate artifact is persisted/sealed.

**Overlap Safety Gate**  
A controlled benchmark gate limiting wrongly selected distractor Stable Gaussian IDs independently of aggregate precision.

**Benchmark Ground Truth**  
A frozen, method-independent selected/rejected/ambiguous Gaussian classification used only for evaluation. Ambiguous truth is excluded from forced selected/rejected scoring according to the benchmark definition.

## Naming Rule

When new code or documentation concerns the Final Spec v1.0 product, use the **Current Product Vocabulary** above.

When touching legacy fixtures or migration code, qualify superseded concepts with `legacy` in comments/documentation when ambiguity is possible.

Do not overload the same word across layers when it changes semantics—for example, do not call an AI inference mode `Add` in new v1.0 code, because `Add` is now a native Candidate application operation.
