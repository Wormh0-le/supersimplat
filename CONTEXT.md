# SuperSimPlat AI Select — Domain Context

This context defines the current **AI Select Final Spec v1.3** vocabulary for turning a user's object-level intent into a native SuperSplat Gaussian Selection.

Final Spec v1.3 retains the mask-conditioned direct-Evidence product/lifecycle model while standardizing the official SAM 3 Image static instance workflow, retained-support TargetGeometryHint semantics, and bounded local Key-View acquisition. Final Spec v1.1, its Amendments, and Final Spec v1.2 are historical where superseded. Historical v1.0 Contributor terminology remains valid only for migration, reference fixtures, diagnostics, and the explicit debug/reference backend.

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
The one Active Splat currently targeted by AI Select, bound to the scene/splat dependency state required by rendering and lifting. AI Select Final Spec v1.3 does not combine Candidate IDs across multiple Target Splats in one Current Target Context.  
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

**TargetGeometryHint**
One compact, non-ownership geometry artifact derived by the Companion from the exact confirmed Anchor Camera/RGB/Stable Mask: bounded reliable first-hit visible points, robust center/extent, geometry quality, Prompt support, and evidence-backed reasons. Its formal visible points are the retained support after the separated-support filter; geometry quality remains a diagnostic independent from Prompt support. It is localization, framing, and later Prompt-synthesis context only — never Stable Gaussian IDs, weights, or ownership, and it may seed but never hard-bound the Evidence Working Set.
_Avoid_: Gaussian ownership record, Candidate seed

**Prompt Support**
The independent eligibility state for turning a TargetGeometryHint's retained visible points into a Route B Image Instance Prompt. Global support is `usable` only when at least four distinct retained first-hit 3D support samples remain and there is no disqualifying geometry reason; when geometry is `limited`, the only promotable reason is `separatedSupportFiltered`. Each Generated View must additionally project at least two distinct points into its authoritative image. `limited` means no Prompt or Mask inference may be issued for that View, even when its RGB is Ready. Geometry warnings remain visible and do not by themselves change Participation.
_Avoid_: geometry quality, model confidence, Participation

**Local Key View**  
A planner-owned Generated View from the bounded local Key-View policy: left/right azimuth and modest elevation offsets around the TargetGeometryHint center with framing from its extent, validated for projection size, clipping, visibility, and nonblank authoritative RGB. The default batch is 2–4 Views; Generate More appends another bounded batch; Stop preserves completed Views; Regenerate replaces planner-owned Views but preserves user-owned Views and exact-identity artifacts.  
_Avoid_: room-scale orbit, adaptive marginal-gain schedule

**User-added View**  
An AI View created from a user-chosen CameraBinding. It remains target-local and is discarded on Restart Current Target.  
_Avoid_: persistent project camera

**AI View**  
A target-local authoritative observation record containing CameraBinding, gsplat RGB identity, source, render status, Participation, Mask versions, and optional derived Evidence reference. A View may be Render Ready without a Mask or Evidence.  
_Avoid_: inseparable Camera+RGB+Mask+Evidence tuple

**AI View Dock**  
The bottom editing surface for authoritative RGB, Gallery navigation, Mask prompting/brush editing, Mask version state, View assessment, Participation, and Candidate-production context. It does not own Native Candidate Operations that act on the main 3D viewport.  
_Avoid_: separate AI workspace

**AI Select Toolbar**  
The main-viewport subtoolbar active for AI Select. It owns 3D viewport interactions and Native Candidate Operations, while the AI View Dock owns View review and 2D Prompt/Mask authoring.  
_Avoid_: Candidate application controls inside the AI View Dock

**Camera Inspection**  
An explicit mode that saves the Scene View Camera, moves the Editor Camera to an observer pose, and exposes the Anchor/selected View Frustum. Inspection has an explicit target: the Anchor remains the only manipulable target (a final authoritative RGB is requested when Anchor manipulation ends), while a Generated View camera is planner-owned and observed read-only. The observer pose is never silently adopted as the Anchor.  
_Avoid_: normal scene navigation

**Gallery Filter**  
A presentation-only projection over Gallery cards (All / Included / Excluded / Needs Review). Applying or changing a filter never mutates Prompt, Mask, Participation, Evidence, or Candidate state.  
_Avoid_: state mutation, trust signal

**RGB Ready**  
The AI View has valid authoritative gsplat RGB bound to its exact CameraBinding and target dependency identity. RGB Ready does not imply Mask Ready, Evidence Ready, or Candidate Ready.  
_Avoid_: complete lifting input

**Render Attempt ID**  
The identity of one actual render execution attempt. Replaying the same attempt may be idempotent; explicit Retry creates a new attempt for the same semantic CameraBinding rather than replaying a cached failure.  
_Avoid_: changing CameraBinding to bypass cache

**RGB Renderer Version**  
The versioned identity of the authoritative RGB implementation bound to every AI observation response (currently `gsplat-rgb/v1`). It is the explicit seam that lets a later same-decision FlashSplat-style kernel replace the RGB implementation without silently changing observation semantics.  
_Avoid_: implicit renderer swap

## Mask Vocabulary

**Prompt Authoring**
The pre-Stable interaction layer that records explicit model constraints on one exact authoritative RGB. Positive Point, Negative Point, and at most one Positive Instance Box tools revise PromptState; they do not directly change Editing Mask pixels. Negative Box, Prompt Brush / Mask Constraint, and Text are removed from the v1 Prompt surface.
_Avoid_: Paint/Erase, implicit long-press brush

**PromptState**
An immutable-by-revision, per-View set of positive/negative Point prompts and at most one Positive Instance Box (authoritative-image pixel XYXY) bound to one exact authoritative RGB digest. PromptState has its own digest and history and is neither an Editing Mask nor a Stable Mask. The current schema is v2; artifacts carrying removed v1 families fail closed by version/capability identity.
_Avoid_: legacy Prompt Log, bitmap edit history

**Prompt Adapter Capabilities**
The versioned, digest-bound declaration of which positive/negative prompt families and multi-candidate output an installed model adapter supports. The editor never infers these capabilities from a model name; unsupported tools are disabled or rejected explicitly.
_Avoid_: best-effort ignored prompts, model-name feature detection

**Prompt Compiler Policy**
The versioned deterministic mapping from one exact PromptState into adapter-native Point, Box, and previous-logits inputs. Its identity covers ordering, coordinate conventions, and prompt-family composition; capability identity rotates when these semantics change. The current `sam3-image-instance-compiler/v1` policy routes Points and the Positive Instance Box through the official SAM 3 Image instance-interaction path (`build_sam3_image_model` → `Sam3Processor.set_image` → `predict_inst`). Prompt Brush is never compiled into SAM `mask_input`: that field accepts only Companion-local previous-prediction logits behind an opaque reference.
_Avoid_: implicit coordinate conversion, silently ignored prompt, model-name default

**Image Instance Mask Contract**
The compact versioned per-View boundary shared by Anchor, Generated, and User-added View acquisition. It binds a canonical pixel Prompt artifact, one resolvable authoritative RGB payload or current-Companion RGB reference, exact request identity, bounded inference-only Mask result, and opaque logits metadata. A completed empty result is semantic unavailable; transport, runtime, OOM, and cancellation failures publish no partial result. Mask Review, Stable publication, Participation, Evidence, and Candidate remain outside the provider result.
_Avoid_: digest-only RGB, raw logits payload, backend registry, route fallback, provider-side Stable publication

**PreviousPredictionLogitsRef**
An opaque, digest-bound browser-held reference to Companion-local low-resolution previous-prediction logits. Raw logits never cross the protocol or enter PromptState/persistence. The reference resolves only inside the exact Companion Instance that minted it, for the same View/RGB/adapter lineage and chosen candidate, and forces single-mask refinement linked to the source inference attempt. An expired or unresolvable reference falls back to a fresh Point/Box prediction without `mask_input`.
_Avoid_: binary brush as mask input, cross-session logits cache

**Generated View Image Instance Prompt**
A deterministic Route B `ImageInstancePromptArtifact` synthesized from the exact TargetGeometryHint's retained visible points, accepted Local Key View plan, authoritative View RGB, View CameraBinding, and locked SAM 3 Image runtime identity. It contains one positive instance Box, 1–3 positive points, at most two local negative points, and `multimaskOutput: false`; `Prompt Support: limited` yields no inference request even when geometry quality is limited for a separately disclosed reason. Regenerate Prompt publishes only a new Prompt artifact; explicit Auto Mask Refresh/Retry separately consumes that current Prompt and authoritative RGB.
_Avoid_: propagation/tracker state, Negative Box, text/brush/mask-constraint prompt, previous logits

**AutoMaskProposalSet**
A deterministic bounded set of structurally valid model Mask alternatives bound to exact target/context, Camera/RGB, PromptState, model, adapter capability, policy, and attempt identities. Exactly one Positive Point with no Box and no refinement yields at most three candidates; Box, multiple Points, or previous-logits refinement yields at most one. A proposal may seed Editing Mask but is never Stable without Confirm Mask. Raw adapter scores retain their declared semantics and are not correctness confidence.
_Avoid_: Stable Mask, highest-score auto-confirm, ProposalDecision

**Proposal Ranking Features**
A versioned per-proposal 2D record reduced by Ticket 07A to exactly what candidate choice consumes: hard prompt consistency, eligibility, area fraction, connected component count, and the echoed raw model score. Pairwise containment/IoU, material-distinctness clustering, compactness, decision-margin features, and Gaussian support sanity are removed; Gaussian readiness belongs to Lift Readiness, never to Anchor candidate selection. Each candidate also carries its own Mask Review record under the shared `local-view-assessment/v2` policy.
_Avoid_: calibrated confidence, Gaussian ownership, candidate clustering/ranking pipelines

**ProposalDecision**
The versioned pre-Stable result that binds one exact AutoMaskProposalSet and classifies it as Selected, Ambiguous, or Unavailable. It enumerates exactly the eligible candidates in deterministic default-preview order — highest raw model score, ties broken by source order — and carries no ranking reason codes; Mask-quality claims live on the per-candidate Mask Review record. The default preview is never auto-confirmed; explicit user choice resolves one-point ambiguity, and explicit acceptance or manual replacement creates the Editing Mask.
_Avoid_: ViewAssessment, Stable Mask, highest-score auto-confirm, margin calibration

**Pixel Editing**
Explicit Paint/Erase mutation of the unpublished Editing Mask. Pixel edits use Mask-local history and never rewrite PromptState or silently rerun proposal ranking.
_Avoid_: Prompt Brush, model constraint

**MaskAnnotation**  
A versioned 2D annotation bound to one AI View and the RGB digest from which it was authored/generated. It may originate from a single-frame SAM Image result, manual authoring, or a hybrid workflow.
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

**Automatic Mask Publication**  
The browser-owned atomic publication of one reviewed, single-frame SAM Image Mask directly as a Stable Mask for a Generated View, without an Editing Mask or user confirmation. The Companion returns inference and Review separately; the browser publishes only Good or Review results. Auto Good defaults Included, Auto Review defaults Excluded, Failed/semantic-unavailable publish no new automatic Stable Mask, and technical failure preserves RGB plus any prior Stable revision. User Confirmed authority is never silently replaced.
_Avoid_: auto-confirm, hidden Lift participation

**Mask Quality / View Assessment**  
The automatic quality state attached to an automatic Mask/View, typically Auto Good, Auto Review, or Failed. It is separate from Participation and is not a calibrated universal confidence probability.  
_Avoid_: participation flag, unified confidence percentage

**Review Reason**  
A structured evidence-backed reason explaining why an automatic Mask/View needs inspection. The Final Spec v1.3 vocabulary is `prompt-inconsistent`, `target-materially-clipped`, `severely-fragmented`, `box-spill-or-neighbour-leak`, and `empty-or-degenerate-mask`, each supported by measurable Mask geometry or, when the Prompt family exists, Point/Box consistency. Tracker propagation and Gaussian visibility/support are not Mask-quality inputs: `propagation-uncertain` is deleted, and `weak-gaussian-support` belongs to Lift Readiness.  
_Avoid_: free-form AI guess

**ViewAssessmentPolicy**  
The Companion-side versioned (`local-view-assessment/v2`) Mask Review policy deriving Good/Review/Failed plus Review Reasons from the exact RGB, returned Mask, and instance Prompt family. Boundary Review requires a meaningful ratio/margin, fragmentation requires material disconnected mass, and missing optional diagnostics never fabricate a reason. It returns no publication and does not override a user-confirmed Stable Mask.
_Avoid_: SAM confidence passthrough

**Participation**  
Whether one AI View's Stable Mask participates in Coverage/Lifting: Included or Excluded. Participation is independent from Mask Quality and View role. Its defaults are centralized: Auto Good defaults Included; Auto Review, Failed, or unavailable review defaults Excluded; User Confirmed defaults Included unless the user explicitly excludes.  
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
The measured extent of relevant Core Target Gaussian evidence actually observed through valid Visible Mass from Included Stable Views. The current reference policy uses each Core Target Gaussian's maximum normalized effective Visible Mass across exact Included Evidence Views, then averages over the Core Target; duplicating a View therefore cannot manufacture coverage. Low-cost support diagnostics may report formal Evidence pending but never a numeric Observation Coverage. It is not raw View count, frustum inclusion, or whole-scene Gaussian count.  
_Avoid_: cameras generated, whole-scene coverage

**View Diversity**  
A separate measure of useful directional/viewpoint diversity. The current reference policy uses maximum angular separation between V-backed useful OpenCV camera-forward directions. More or duplicate Views do not automatically imply higher diversity.  
_Avoid_: View count

**Lift Readiness**  
The versioned, target-local derived state Not Ready, Limited, or Ready based on exact Included Evidence, Observation Coverage, useful directional diversity, generation state, and required identities/artifacts rather than a universal fixed View count. `lift-readiness/reference-v1` is the current reference/calibration policy; its thresholds do not claim production calibration until Ticket 21 closes. Stable input changes keep the last result inspectable but stale.  
_Avoid_: fixed N-view gate

**Adaptive View Planner**  
Deferred v1 concept: a planner that incrementally generates useful CameraBindings based on target observation, directional diversity, and marginal gain under bounded budgets. v1 instead uses the bounded local Key-View policy (see Local Key View); adaptive marginal-gain optimization remains explicitly out of scope.  
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

**Explicit Recompute State**
The target-local dependency record for the simplified static-image pipeline: `targetGeometryDirty`, `localKeyViewPlanDirty`, `promptDirtyViewIds`, `maskInferenceDirtyViewIds`, `evidenceDirtyViewIds`, `liftDirty`, and `candidateStale`. An Anchor Stable change dirties geometry, planning, and only bound View Prompt/Mask work; a View Camera/RGB change dirties that View plus downstream Evidence/Lift; Stable Mask publication or Participation change dirties that View's Evidence and marks Lift/Candidate stale. Unpublished Editing Mask changes never dirty Evidence or Candidate, and no dirty transition starts inference, Evidence, or Re-Lift automatically.
_Avoid_: propagation state, sequence state, reference state, automatic Re-Lift

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
Anchor/Views/Masks/Evidence/Candidate state that exists only for the Current Target Context/runtime. Final Spec v1.3 does not persist or reopen previous target contexts as semantic project data.  
_Avoid_: object annotation database, persistent AI session

## Selection Service and Runtime Vocabulary

**Selection Service**  
The single-user inference service used by the editor on the same machine or a trusted local network. It is not a public authenticated multi-tenant backend.

**Selection Service Companion**  
The separately installed local Python runtime/package implementing rendering, SAM, view planning, assessment, Evidence, and lifting dependencies outside the browser distribution.

**Selection Service Endpoint**  
The explicitly configured loopback or trusted-LAN address. It is not automatically discovered.

**AI Select Availability**
The user-facing Connecting, Available, or Unavailable projection of automatic Selection Service connection and compatibility validation. It excludes task success and current execution capacity and exposes no endpoint, manifest, or runtime details.
The first check begins after UI mount. Available uses lightweight foreground heartbeats; first connection, recovery, and Companion Instance replacement run full Runtime Profile validation. Busy and task-local failures do not change Availability.
_Avoid_: Ping status, model picker, task progress

**AI Select Runtime Profile**
The versioned set of protocol, renderer, Active Model, backend, and policy capabilities required by one editor build before AI Select Availability may become Available. Optional future capabilities do not enter the Profile until the product workflow requires them.
_Avoid_: process reachability, unversioned feature checklist

**Selection Service Readiness**  
The technical condition in which a reachable Companion has satisfied the current AI Select Runtime Profile, including successful initialization of its Active Model and required locked runtime. Readiness is distinct from user-facing Availability, task outcome, and execution capacity.

**Active Model Manifest**
The single operator-resolved Model Manifest initialized for one Companion process and bound automatically by browser requests. One compatible installed manifest may activate automatically; multiple compatible manifests require an explicit operator choice.
Only this singular manifest crosses the current readiness protocol; the browser does not receive an installed-model catalog or select a model.
_Avoid_: browser-selected model, first installed model

**Companion Instance ID**
An opaque identity minted for one Companion process lifetime and returned by lightweight health checks. A changed Instance ID triggers full compatibility validation but is not an artifact, model, or runtime identity.
Replacement invalidates Companion-local RGB and previous-logits references; independently persisted User Confirmed Stable Masks retain their own artifact identity.
_Avoid_: service build, Model Manifest digest, persistent server ID

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

The following terms may appear in old implementation, fixtures, issues, or benchmarks. They are not the target Final Spec v1.3 product architecture.

**Complete Contributor Production Path (v1.0 legacy)**  
The former normal path that published complete per-pixel Contributor IDs/weights and required mass alignment with RGB raster alpha before View readiness/lifting. In the current Final Spec v1.3 architecture it is retained only as the Reference Contributor Backend.

**Contributor Alpha Reconciliation (reference/debug)**  
The bounded fail-closed logic that attempts to explain boundary differences between separately executed RGB and complete Contributor kernels. It remains useful for diagnosing the reference backend but is not a production Direct Evidence requirement.

**Object Selection Session (legacy)**  
The old user-visible lifetime bundling prompting, preview correction, Candidate state, and one final commit. Replaced by Current Target Context plus independent View/Mask/Evidence/Candidate lifecycles.

**SAM 3.1 Multiplex Static Adapter (legacy/reference)**  
The retired static segmentation path built from the Multiplex video predictor and private tracker-head methods (`sam3.1-interactive-image/v1`). It remains only as a non-current benchmark fixture and never advertises Ready for current static instance segmentation; the current path is the official SAM 3 Image instance adapter (`sam3-image-instance/v1`).

**Prompt Log (legacy product role)**  
The old chronological product source of truth for point prompts and New/Add/Remove/Refine operations. Prompt data may still exist inside MaskAnnotation provenance, compatibility code, or frozen benchmarks.

**Frame Set (legacy product role)**  
The old immutable ordered batch of Anchor plus Generated Views processed as one unit. Current Views are independent records with progressive publication.

**Mask Track / Mask Set (legacy product role)**  
The old top-level include/exclude mask orchestration and complete publication unit. Current MaskAnnotations are independent and versioned per View.

**New / Add / Remove / Refine (legacy inference modes)**  
Old AI workflow modes. Add and Remove now mean native Candidate application operations together with Set and Intersect.

**Correction Round (legacy)**  
The old bounded inference-preview refresh count. Current workflows use Mask confirmation, Prompt regeneration, Re-Lift, Generate More, and explicit correction.

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

Use the Current Product Vocabulary for Final Spec v1.3 code and documentation.

Qualify historical concepts with `legacy`, `reference`, or `debug` when ambiguity is possible.

Do not use `Contributor` as a generic synonym for production Evidence. In Final Spec v1.3:

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
