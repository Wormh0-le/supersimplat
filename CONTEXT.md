# SuperSimPlat AI Select — Domain Context

This context defines the current **AI Select Final Spec v1.1** vocabulary for turning a user's object-level intent into a native SuperSplat Gaussian Selection.

Final Spec v1.1 retains the v1.0 product/lifecycle model while replacing complete per-pixel Contributor artifacts as the production lifting representation with **Mask-Conditioned Direct Gaussian Evidence**. Historical v1.0 Contributor terminology remains valid only for migration, reference fixtures, diagnostics, and the explicit debug/reference backend.

## Current Product Vocabulary

**AI Select**  
A native SuperSplat Selection Tool that builds an AI Candidate from authoritative gsplat multi-view observations, versioned 2D Masks, and per-Gaussian Evidence, then applies that Candidate through native selection operations. AI Select is not a separate workspace, persistent object database, or second 3D editing system.  
_Avoid_: standalone segmentation app, semantic object manager

**Gaussian Selection**  
The editor-owned native set of Gaussian IDs/indices targeted by existing SuperSplat operations, independent of how those Gaussians were inferred.  
_Avoid_: 3D mask, semantic object

**AI Candidate**  
The transient Selected Gaussian set produced by Gaussian Lifting from the current Included Stable View Annotations and their valid Evidence. It does not modify Native Selection until the user explicitly chooses Set, Add, Remove, or Intersect.  
_Avoid_: committed selection, editable 3D mask

**AITarget / Target Splat**  
The one Active Splat currently targeted by AI Select, bound to the scene/splat dependency state required by rendering and lifting. AI Select v1.1 does not combine Candidate IDs across multiple Target Splats in one Current Target Context.  
_Avoid_: whole scene, persistent semantic instance

**Stable Gaussian ID**  
An editor-owned unsigned identity referring to the same Gaussian throughout one compatible immutable target-content state, independent of PLY row, renderer order, draw order, spatial chunk order, or Companion tensor position.  
_Avoid_: render index, tensor row, file row

## Scene and Spatial Data Vocabulary

**Scene Snapshot**  
An immutable, versioned representation of Target Splat geometry, appearance, identity, and effective render semantics supplied to the Companion. It is transient inference input, not saved semantic project state.  
_Avoid_: source PLY identity, project save, object cache

**Packed SceneSnapshot**  
The structure-of-arrays typed-binary Scene Snapshot representation. It preserves editor-owned Stable Gaussian IDs and effective render semantics without a per-Gaussian JSON object graph.  
_Avoid_: screenshot, base64 object list

**Snapshot Content Digest**  
The strong cached identity of a Packed SceneSnapshot's canonical logical metadata and typed bytes. It is independent of network chunking and is not a TargetDependencyToken.  
_Avoid_: editor semantic revision, upload ID

**Binary SceneSnapshot Registration**  
The versioned begin/chunk/commit protocol that transfers a Packed SceneSnapshot atomically. Only a fully validated committed snapshot may enter the Companion runtime cache.  
_Avoid_: partial snapshot cache entry, one giant JSON request

**Spatial Scene Manifest**  
The immutable control-plane description of all spatial binary chunks for one Scene Snapshot. It preserves the same scene identity while allowing CameraBinding-specific payload residency.  
_Avoid_: camera-specific scene version, source-file partitioning

**Spatial Chunk**  
An immutable bounded SoA payload with chunk identity, content digest, global ordinal data, and conservative world-space support bounds. It is not a visibility result.  
_Avoid_: PlayCanvas visible list, center-only culling

**Render Working Set**  
The conservative CameraBinding-specific set of spatial chunks/Gaussians required to reproduce complete-scene authoritative RGB, occlusion, transmittance, and termination. A spatially reduced Render Working Set is valid only when it is render-equivalent to the complete scene under the declared policy.  
_Avoid_: target-only Gaussian subset, approximate visible list

**Evidence Working Set**  
The target-local Stable Gaussian set that receives P/N/V Evidence writes, normally Core Target Set plus Context Set. Gaussians outside this set may still participate in the Render Working Set and affect occlusion/transmittance.  
_Avoid_: the only Gaussians rasterized, visibility set

**WorkingSetToken**  
A deterministic identity for a sorted, validated working set and its governing policy. Render and Evidence Working Sets must not be conflated when their membership or semantics differ.  
_Avoid_: upload order, residency state, TargetDependencyToken

**Scene Chunk Miss**  
A bound Companion response stating that a complete required Render Working Set is known but one or more validated payloads are not resident. It is never a partially rendered Ready AI View.  
_Avoid_: best-effort partial render

## Target and View Lifecycle Vocabulary

**Current Target Context**  
The single user-visible AI Select context for the object currently being worked on. It owns Anchor, AI Views, Mask versions, Participation, Evidence dependencies, Coverage/Readiness, Candidate, and Uncertain state. Restart Current Target disposes it while preserving Native Selection/EditHistory and reusable runtime caches.  
_Avoid_: persistent multi-object session stack

**Runtime Context**  
Reusable non-semantic infrastructure such as loaded models, scene tensors, RGB/Evidence caches, reference Contributor caches, Stable ID mappings, Companion connection, and planner/policy settings. Runtime cache reuse does not preserve a previous target's AI View context.  
_Avoid_: saved target session

**CameraBinding**  
The versioned camera truth shared by authoritative gsplat rendering and the corresponding 3D Frustum. It uniquely determines pose, intrinsics, resolution, clipping, and camera convention.  
_Avoid_: viewport screenshot metadata, approximate pose

**Editor Camera**  
The user's navigation camera for the main PlayCanvas/SuperSplat viewport. It is not automatically moved when AI Select activates or Generated Views are produced.  
_Avoid_: Anchor Camera, Generated View camera

**Anchor View**  
The first AI View for the Current Target Context. Its CameraBinding is initialized from the Current Editor Camera; its authoritative observation RGB is rendered by gsplat. Prompting/mask authoring identifies the target represented by this View.  
_Avoid_: PlayCanvas screenshot, generated view

**Generated View**  
A planner-owned AI View rendered to increase useful target observation and directional diversity without moving the visible Editor Camera.  
_Avoid_: source capture, camera animation

**User-added View**  
An AI View created from a user-chosen CameraBinding. It remains target-local and is discarded on Restart Current Target.  
_Avoid_: persistent project camera

**AI View**  
A target-local authoritative observation record containing CameraBinding, gsplat RGB identity, source, render status, Participation, Mask versions, and optional derived Evidence reference. A View may be Render Ready without a Mask or Evidence.  
_Avoid_: inseparable Camera+RGB+Mask+Evidence tuple

**AI View Dock**  
The bottom editing surface for authoritative RGB, Gallery navigation, Mask prompting/brush editing, Mask version state, View assessment, Participation, and next-step actions.  
_Avoid_: separate AI workspace

**Camera Inspection**  
An explicit mode that saves the Scene View Camera, moves the Editor Camera to an observer pose, and exposes the Anchor/selected View Frustum. Manipulation changes only the View CameraBinding. A final authoritative RGB is requested when manipulation ends. The observer pose is never silently adopted as the Anchor.  
_Avoid_: normal scene navigation

**RGB Ready**  
The AI View has valid authoritative gsplat RGB bound to its exact CameraBinding and target dependency identity. RGB Ready does not imply Mask Ready, Evidence Ready, or Candidate Ready.  
_Avoid_: complete lifting input

**Render Attempt ID**  
The identity of one actual render execution attempt. Replaying the same attempt may be idempotent; explicit Retry creates a new attempt for the same semantic CameraBinding rather than replaying a cached failure.  
_Avoid_: changing CameraBinding to bypass cache

## Mask Vocabulary

**MaskAnnotation**  
A versioned 2D annotation bound to one AI View and the RGB digest from which it was authored/generated. It may originate from SAM, propagation, manual authoring, or a hybrid workflow.  
_Avoid_: Gaussian Selection, 3D mask

**Stable Mask**  
The published MaskAnnotation version permitted to participate in assessment, Evidence production, Observation Coverage, and Gaussian Lifting.  
_Avoid_: current brush canvas, draft mask

**Editing Mask**  
An unpublished MaskAnnotation version being generated or edited. It does not replace the Stable Mask or invalidate current Evidence/Candidate until Confirm Mask.  
_Avoid_: stable lifting input

**Confirm Mask**  
The atomic publication that promotes the current Editing Mask to the new Stable Mask. It makes dependent per-view Evidence stale and may make the Candidate stale; it does not modify Native Selection.  
_Avoid_: Selection Commit

**Mask Quality / View Assessment**  
The automatic quality state attached to an automatic Mask/View, typically Auto Good, Auto Review, or Failed. It is separate from Participation and is not a calibrated universal confidence probability.  
_Avoid_: participation flag, unified confidence percentage

**Review Reason**  
A structured evidence-backed reason explaining why an automatic Mask/View needs inspection. It must be supported by measurable mask, propagation, Gaussian Evidence/visibility, or cross-view data.  
_Avoid_: free-form AI guess

**ViewAssessmentPolicy**  
The Companion-side versioned policy deriving Good/Review/Failed plus Review Reasons. It does not override a user-confirmed Stable Mask.  
_Avoid_: SAM confidence passthrough

**Participation**  
Whether one AI View's Stable Mask participates in Coverage/Lifting: Included or Excluded. Participation is independent from Mask Quality.  
_Avoid_: quality score

**Included Stable View Annotation**  
An AI View with Render Ready authoritative RGB, Included participation, and a Stable Mask. It is the effective per-view input unit for Evidence production and Gaussian Lifting.  
_Avoid_: every generated view, every mask draft

## Evidence and Lifting Vocabulary

**Mask-Conditioned Gaussian Evidence**  
Per-view, per-Gaussian measurements accumulated from the Stable Mask and authoritative alpha-compositing contribution `w = alpha × incoming transmittance`. The required channels are Positive Mass (P), Negative Mass (N), and Visible Mass (V).  
_Avoid_: binary membership vote, screen-space overlap only

**Positive Mass (P)**  
The Gaussian's alpha-composited contribution inside strong target-positive Mask regions.

**Negative Mass (N)**  
The Gaussian's alpha-composited contribution inside explicit local background/context regions. Far-away Mask-exterior pixels are not automatically negative.

**Visible Mass (V)**  
The Gaussian's valid visible contribution inside the Evidence observation region, independent of whether that region is positive, negative, or boundary/ignore.

**Boundary / Ignore Evidence**  
Evidence from uncertain Mask boundary regions. It is neutral or low-weight for P/N and may be retained in an optional Boundary Mass channel for mixed-primitive diagnostics.  
_Avoid_: forced foreground/background label

**Direct Evidence Production**  
The production path that accumulates P/N/V from the same authoritative raster decision source as RGB, sharing ordering, alpha, transmittance, validity, and termination decisions. It does not require normal publication of complete per-pixel Contributor lists.  
_Avoid_: independent approximate re-rasterization

**Same Decision Source**  
The invariant that RGB and production Evidence consume the same accepted Gaussian sequence and the same `alpha × T` values. It does not require one literal CUDA launch, but later passes may not independently re-decide boundary-sensitive acceptance/termination.  
_Avoid_: same formula in separate kernels as proof of equivalence

**GaussianEvidenceArtifact**  
A versioned per-view artifact containing Stable Gaussian IDs and P/N/V arrays, bound to target dependency, CameraBinding, RGB digest, Stable Mask digest, Evidence Policy, Render Working Set, Evidence Working Set, and raster/evidence implementation identity.  
_Avoid_: unbound float arrays, global mutable accumulator

**Evidence Ready**  
The current Included Stable View has a valid GaussianEvidenceArtifact matching all current dependencies. Evidence Ready is independent from RGB Ready.  
_Avoid_: View Render Ready

**Selection Evidence**  
The per-Gaussian raw and aggregated positive, negative, visible, boundary, and cross-view consistency measurements used by the Evidence Policy. Missing/unusable observation remains unobserved rather than automatically negative.  
_Avoid_: final Candidate, majority vote

**Evidence Policy**  
A versioned, replayable, benchmark-calibrated rule that interprets per-view and aggregated Evidence into Selected, Rejected, Uncertain, and Out of Scope states. Policy changes require explicit versioning and calibration.  
_Avoid_: magic threshold, hidden confidence rule

**Reference Contributor Backend**  
The complete per-pixel Contributor IDs/weights path retained only for diagnostics, fixtures, rasterizer validation, and reference comparison. Its failure does not invalidate otherwise valid RGB or successful production Direct Evidence.  
_Avoid_: production View readiness requirement

**Observation Coverage**  
The measured extent of relevant Core Target Gaussian evidence actually observed through valid Visible Mass from Included Stable Views. It is not raw View count, frustum inclusion, or whole-scene Gaussian count.  
_Avoid_: cameras generated, whole-scene coverage

**View Diversity**  
A separate measure of useful directional/viewpoint diversity. More Views do not automatically imply higher diversity.  
_Avoid_: View count

**Lift Readiness**  
The derived state Not Ready, Limited, or Ready based on usable observation, diversity, and required identities/artifacts rather than a universal fixed View count.  
_Avoid_: fixed N-view gate

**Adaptive View Planner**  
The planner that incrementally generates useful CameraBindings based on target observation, directional diversity, and marginal gain under bounded budgets.  
_Avoid_: fixed 4/8 view schedule

**Gaussian Lifting**  
The explicit operation that resolves/reuses per-view Evidence, recomputes stale/missing Evidence, aggregates across Included Stable Views, applies the Evidence Policy, and atomically publishes Candidate plus Uncertain.  
_Avoid_: direct 3D mask painting

**Selected Gaussian**  
A Gaussian with sufficient, consistent target-positive Evidence under the current Evidence Policy. Selected Gaussians form the AI Candidate.

**Rejected Gaussian**  
A sufficiently observed Gaussian with consistent local-background Evidence under the current Evidence Policy. Unobserved Gaussians are not Rejected.

**Uncertain Gaussian**  
A Gaussian whose observation is absent, insufficient, materially conflicting, or mixed across target/background regions. It is diagnostic and excluded from Candidate application.  
_Avoid_: rejected/background Gaussian

**Out of Scope Gaussian**  
A Gaussian outside the current Evidence Working Set or declared target scope. It is not forced into Selected, Rejected, or Uncertain product overlays unless policy requires it.

## Candidate and Dependency Vocabulary

**Candidate Stale**  
The Candidate no longer corresponds to current stable lifting inputs. It remains inspectable but cannot be applied until explicit Re-Lift succeeds.  
_Avoid_: scene suspension

**Suspended Context**  
A Current Target Context whose underlying scene/render/geometry/identity dependency no longer matches its artifacts. It is preserved for inspection and exact Undo recovery but cannot be edited, lifted, or applied.  
_Avoid_: Candidate stale, destroyed session

**TargetDependencyToken**  
A semantic identity covering the target dependencies relevant to rendering/lifting, including render state, geometry, Gaussian identity/membership, and world/target transform as required. Exact Undo may restore the same semantic token.  
_Avoid_: monotonic global scene counter only

**AIRequestBinding**  
The minimum async identity carried by AI requests/results: targetContextId, contextRevision, and dependencyToken. Non-matching results are stale and discarded regardless of cancellation success.  
_Avoid_: request ID alone

**Restart Current Target / 重新选择对象**  
The action that disposes all target-local Anchor/View/Mask/Evidence/Candidate state, retains Native Selection/EditHistory and reusable runtime caches, and starts a new target from the current saved Scene View.  
_Avoid_: exit AI Select, clear native selection

**Native Candidate Operation**  
One of Set, Add, Remove, or Intersect, applying the current valid Candidate through existing Native Selection/EditHistory semantics.  
_Avoid_: inference mode, Prompt operation

**Set** — `S' = C`  
**Add** — `S' = S ∪ C`  
**Remove** — `S' = S − C`  
**Intersect** — `S' = S ∩ C`

**Transient AI Selection State**  
Anchor/Views/Masks/Evidence/Candidate state that exists only for the Current Target Context/runtime. v1.1 does not persist or reopen previous target contexts as semantic project data.  
_Avoid_: object annotation database, persistent AI session

## Selection Service and Runtime Vocabulary

**Selection Service**  
The single-user inference service used by the editor on the same machine or a trusted local network. It is not a public authenticated multi-tenant backend.

**Selection Service Companion**  
The separately installed local Python runtime/package implementing rendering, SAM, view planning, assessment, Evidence, and lifting dependencies outside the browser distribution.

**Selection Service Endpoint**  
The explicitly configured loopback or trusted-LAN address. It is not automatically discovered.

**Selection Service Readiness**  
The condition in which a reachable Companion has passed compatibility checks for required protocol, renderer, Evidence implementation/policy, model adapter/checkpoint, Model Manifest, and locked runtime. Reachable alone is not Ready.

**Companion Process Ownership**  
The operator starts, stops, and upgrades the Companion. The browser owns target/request resources, not the Companion process.

**Model Manifest**  
The immutable identity of the mask model adapter, model artifact/checkpoint, source revision, license metadata, and material runtime configuration.

**Model Installation**  
An operator-initiated, manifest-verified acquisition of separately distributed model weights. Weights are not embedded in the browser/editor distribution.

**Companion Upgrade**  
Operator-initiated replacement of a stopped Companion runtime with a locked version. Live AI contexts are not silently migrated across incompatible runtime identities.

**Trusted-LAN Mode**  
Opt-in deployment on a private operator-managed network under explicit endpoint/origin/security policy. It is not an Internet service.

**Companion Session Capacity**  
The maximum concurrently admitted execution contexts. Runtime capacity is distinct from the user-visible single Current Target Context model.

**Selection Service Transport Baseline**  
The browser-compatible secure-context policy for reaching the Companion. Loopback is the default; trusted-LAN requirements remain explicit and fail closed.

**Standalone Gaussian Scene**  
An already reconstructed Gaussian scene used as the sole scene input to AI Select. Original capture images, camera trajectories, sparse reconstructions, and reconstruction-time metadata are not required inputs.

## Legacy / Reference Vocabulary

The following terms may appear in old implementation, fixtures, issues, or benchmarks. They are not the target v1.1 product architecture.

**Complete Contributor Production Path (v1.0 legacy)**  
The former normal path that published complete per-pixel Contributor IDs/weights and required mass alignment with RGB raster alpha before View readiness/lifting. In v1.1 it is retained only as the Reference Contributor Backend.

**Contributor Alpha Reconciliation (reference/debug)**  
The bounded fail-closed logic that attempts to explain boundary differences between separately executed RGB and complete Contributor kernels. It remains useful for diagnosing the reference backend but is not a production Direct Evidence requirement.

**Object Selection Session (legacy)**  
The old user-visible lifetime bundling prompting, preview correction, Candidate state, and one final commit. Replaced by Current Target Context plus independent View/Mask/Evidence/Candidate lifecycles.

**Prompt Log (legacy product role)**  
The old chronological product source of truth for point prompts and New/Add/Remove/Refine operations. Prompt data may still exist inside MaskAnnotation provenance, compatibility code, or frozen benchmarks.

**Frame Set (legacy product role)**  
The old immutable ordered batch of Anchor plus Generated Views processed as one unit. Current Views are independent records with progressive publication.

**Mask Track / Mask Set (legacy product role)**  
The old top-level include/exclude mask orchestration and complete publication unit. Current MaskAnnotations are independent and versioned per View.

**New / Add / Remove / Refine (legacy inference modes)**  
Old AI workflow modes. Add and Remove now mean native Candidate application operations together with Set and Intersect.

**Correction Round (legacy)**  
The old bounded inference-preview refresh count. Current workflows use Mask confirmation, Repropagate, Re-Lift, Generate More, and explicit correction.

**Selection Commit / Cancel (legacy session semantics)**  
Old one-shot session actions. Current semantics use native Candidate operations, Restart Current Target, Exit AI Select, and Native Undo.

## Benchmark Vocabulary

Frozen benchmark records may retain historical vocabulary without overriding the current product model.

**Benchmark Prompt Log**  
A frozen point-only interaction input captured before a historical trial.

**PoC Technical Specification**  
The decision-ready description of a controlled experiment, its interfaces, methods, scenes, gates, and risks. It is not the current Final Spec.

**PoC Acceptance Criteria**  
Predeclared replayable conditions used to judge a frozen PoC. Do not tune gates after observing trial scores merely to obtain a pass.

**PoC Trial**  
One replay of a frozen benchmark input under its declared configuration/seed.

**PoC Run Record**  
An immutable version-bound record of one trial and its inputs, outputs, diagnostics, timing/VRAM, artifact hashes, and scoring evidence.

**Blind Prediction**  
A prediction phase that cannot access Benchmark Ground Truth before the Candidate artifact is persisted/sealed.

**Overlap Safety Gate**  
A controlled gate limiting wrongly selected distractor Stable Gaussian IDs independently of aggregate precision.

**Benchmark Ground Truth**  
A frozen method-independent Selected/Rejected/Ambiguous Gaussian classification used only for evaluation.

## Naming Rules

Use the Current Product Vocabulary for Final Spec v1.1 code and documentation.

Qualify historical concepts with `legacy`, `reference`, or `debug` when ambiguity is possible.

Do not use `Contributor` as a generic synonym for production Evidence. In v1.1:

```text
Contributor = complete per-pixel reference/debug attribution
Evidence    = production per-Gaussian P/N/V measurements
```

Do not call AI workflow behavior `Add` or `Remove`; those names are reserved for native Candidate application operations.

Do not conflate:

```text
RGB Ready
Mask Ready
Evidence Ready
Candidate Ready
```

Do not conflate Render Working Set with Evidence Working Set.