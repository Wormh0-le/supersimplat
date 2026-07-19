# Object-aware Gaussian Editing

This context defines how a user's object-level intent becomes an editable subset of an existing Gaussian scene.

## Language

**Object Selection**:
The process that turns one or more user prompts into a proposed Gaussian Selection representing the intended object or object part.
_Avoid_: 3D segmentation, object detection

**Gaussian Selection**:
The set of Gaussian indices targeted by an editor operation, independent of how those indices were inferred.
_Avoid_: Object mask, 3D mask

**Complete Object Selection**:
A Gaussian Selection intended to cover the whole target object, including back-facing and temporarily occluded regions rather than only the surface visible from the prompting view. Regions not observed in any generated view remain explicitly uncertain until resolved or accepted by the user.
_Avoid_: Visible selection, screen-space selection

**Object Selection Session**:
The interactive lifetime in which a user prompts, reviews, and corrects one intended target before committing its Gaussian Selection. It does not imply an automatically discovered object-part hierarchy.
_Avoid_: Object group, semantic instance

**Candidate Object Selection**:
The transient selected, rejected, and uncertain classification previewed during an Object Selection Session. A complete successful Evidence Snapshot atomically replaces it; any Gaussian may move among those states until Selection Commit. It does not change the editor's Gaussian Selection until Selection Commit.
_Avoid_: Current selection, committed selection, object mask

**Target Splat**:
The single loaded splat asset hit by the prompt and owned by an Object Selection Session. A session never combines Gaussian indices across loaded splat assets.
_Avoid_: Scene, all splats

**Stable Gaussian ID**:
An editor-owned identity that refers to the same Gaussian throughout one immutable content version of a Target Splat, independent of file row, renderer ordering, or service tensor position.
_Avoid_: PLY row, render index, tensor row

**Scene Snapshot**:
An immutable, versioned representation of one Target Splat's effective Gaussian geometry and appearance supplied to the Selection Service. It is a transient inference input, not a saved scene or persistent object sidecar.
_Avoid_: Source PLY, project save, object cache

**Generated View**:
A system-rendered view used to gather Selection Evidence without changing the editor's visible camera. It is not an original capture image or a user-facing camera transition.
_Avoid_: Source image, camera animation

**Seed Region**:
The provisional target center and extent estimated from the user's seed hit and the current-view mask's contributing Gaussians. It guides Generated View framing but is not an Object Selection or object boundary.
_Avoid_: Object box, final bounds, selected object

**Anchor View**:
The visible editor view in which the user submits prompts for a preview update. It is a required member of that update's Frame Set, while the system never moves the visible editor camera.
_Avoid_: Generated View, seed frame, active camera

**Coverage Report**:
A record of which candidate Gaussians produced reliable visible contribution across accepted views, plus unobserved regions and rejected-view reasons. It reports observation coverage without deciding the final Gaussian classification; an insufficient result requires a limited-coverage disclosure rather than an inferred negative classification.
_Avoid_: Complete selection, view count, confidence score

**Frame Set**:
An immutable, ordered collection containing the current prompting view and Generated Views used together for promptable masking. A changed view, order, or rendered frame creates a different Frame Set.
_Avoid_: Video, source frames, camera path

**Mask Track**:
The masks and prompts that follow one included or excluded region across a Frame Set. An Object Selection Session has one primary include track and may add include or exclude tracks.
_Avoid_: Object ID, Gaussian Selection, final mask

**Prompt Log**:
The authoritative, replayable sequence of accepted point prompts and operations for an Object Selection Session. Each successful preview derives a complete Evidence Snapshot from it; model-internal continuation state is a disposable cache derived from it.
_Avoid_: Model state, click history, tracker token

**Benchmark Prompt Log**:
The point-only Prompt Log frozen before a PoC Trial. Its ordered points and operations bound that trial's manual effort; adding an interaction outside it requires a new benchmark revision. A frozen source may represent one initial multi-point `New` interaction as several `New` point entries. Its sealed `sessionMaterialization` then records the deterministic replay mapping: the first point is session `New` and remaining initial points are primary-track `Refine` entries. That mapping is not a Correction Round or additional interaction; the run record retains both the frozen source and materialized session entries.
_Avoid_: Box/text fixture, ad-hoc correction

**Mask Set**:
A versioned collection of per-view masks and acceptance states for every Mask Track in one completed preview update. Partial propagation output is not a Mask Set.
_Avoid_: Candidate Object Selection, composite mask, streaming result

**Model Manifest**:
The immutable identity of the promptable-mask adapter, model artifact, source revision, license, and material runtime configuration used by an Object Selection Session.
_Avoid_: Model name, latest model, server version

**New**:
An interaction mode that starts a new Object Selection Session and replaces the current candidate selection.
_Avoid_: Reset, clear

**Add**:
An interaction mode that segments another prompted region or part and unions it with the current candidate selection at its chronological position in the Prompt Log. A later Add may intentionally restore a region previously removed.
_Avoid_: Positive click, refine

**Remove**:
An interaction mode that segments an unwanted prompted region or part and subtracts it from the current candidate selection at its chronological position in the Prompt Log. A later Remove may intentionally exclude a region again.
_Avoid_: Negative click, erase

**Refine**:
An interaction mode that adds positive or negative prompts to the current Object Selection Session and recomputes that target's masks and Selection Evidence. It does not create a separate selection to union or subtract, and remains a single pending edit until the user confirms it.
_Avoid_: Add, Remove, commit

**Cancel**:
An action that ends an Object Selection Session without applying its Candidate Object Selection. It restores the editor's entry Gaussian Selection and creates no editor history operation.
_Avoid_: Undo, clear prompt

**Selection Commit**:
The single handoff that applies the confirmed candidate's selected Stable Gaussian IDs as one editor history operation. Preview updates create no editor history operation; rejected and uncertain Gaussians are excluded. Subsequent delete, duplicate, separate, undo, and redo behavior remains owned by the editor's existing operations.
_Avoid_: Object edit, delete, separate

**Transient Object Selection**:
An Object Selection that exists only in the current editor session and its existing history. It does not create a named object, persistent object ID, semantic label, or sidecar asset.
_Avoid_: Object annotation, object library

**Correction Round**:
One inference-and-preview cycle that recomputes the current candidate from one or more newly placed positive or negative prompts. Camera inspection and editing unsubmitted prompts do not count as rounds.
_Avoid_: Mouse click, camera move

**Ready Object Selection**:
A Complete Object Selection that an operator, without seeing Benchmark Ground Truth scores, considers safe for an existing editor operation after no more than five successful Correction Rounds following the initial New result.
_Avoid_: Automatic selection, first-click result

**Selection Evidence**:
Per-Gaussian observations accumulated from accepted rendered views, distinguishing positive, negative, and unobserved states before a Gaussian Selection is committed. It records positive and negative evidence, effective observation, posterior, and uncertainty under a versioned Evidence Policy. Only a contributor within a quality-accepted view's support may gain positive or negative evidence; missing or unusable observation remains unobserved. A sufficiently strong, consistent accepted observation may resolve a Gaussian on its own; view count is diagnostic rather than a universal hard gate.
_Avoid_: Vote, final mask

**Evidence Policy**:
The versioned, replayable rule that interprets Selection Evidence into selected, rejected, and uncertain states for a particular rendering configuration. A changed interpretation requires a new policy version and benchmark calibration.
_Avoid_: Magic threshold, hidden confidence rule

**Uncertain Gaussian**:
A Gaussian for which generated observations are absent, insufficient, or materially conflicting, so it cannot be classified as selected or rejected. It is shown separately during preview and excluded from Selection Commit unless later evidence resolves it; committing while any remain requires acknowledgement that only selected Gaussians will be handed off.
_Avoid_: Background Gaussian, selected Gaussian

**Standalone Gaussian Scene**:
An already reconstructed Gaussian scene that is the sole scene input to Object Selection. Original capture images, camera poses, sparse reconstructions, and reconstruction-time metadata are neither required nor accepted as optional inputs.
_Avoid_: Dataset, reconstruction project

**Selection Service**:
A single-user companion to the editor that performs object-selection inference on the same machine or a trusted local network. It is not a public, authenticated, or multi-tenant backend.
_Avoid_: Public API, backend platform

**Selection Service Companion**:
The separately installed local Python runtime and package that realizes the Selection Service for an editor instance. It isolates the CUDA runtime, model adapters, and separately acquired weights from the browser/editor distribution.
_Avoid_: Browser plugin, bundled model

**Selection Service Endpoint**:
The explicitly configured local or trusted-LAN address through which an editor reaches a Selection Service Companion. Its default binds only to loopback; a LAN address is opt-in and never automatically discovered.
_Avoid_: Public URL, automatic service discovery

**Selection Service Readiness**:
The condition in which a reachable Selection Service Companion has passed capability compatibility for a new Object Selection Session, including its renderer, required model adapter, and independently acquired weights. A merely reachable process is not ready, and the editor does not silently substitute an unavailable dependency.
_Avoid_: Liveness, fallback mode

**Companion Process Ownership**:
The separation in which an operator controls the start and stop of a Selection Service Companion while an editor owns only its Object Selection Session resources. Losing or closing an editor never authoritatively stops the Companion, but its session state is reclaimed.
_Avoid_: Browser-owned daemon, persistent selection state

**Model Installation**:
An operator-initiated, manifest-verified acquisition of separate model weights into a Selection Service Companion runtime. It makes a model eligible for readiness without embedding weights in the editor or Companion distribution.
_Avoid_: Bundled checkpoint, implicit download

**Companion Upgrade**:
An operator-initiated replacement of a stopped Selection Service Companion runtime with a locked version. Existing Object Selection Sessions never migrate, and Model Installations remain addressable by manifest digest for manual rollback and reproducibility.
_Avoid_: Automatic update, in-place migration

**Trusted-LAN Mode**:
An opt-in deployment of a Selection Service Companion on a private, operator-managed network through a configured endpoint and editor-origin allowlist. It is neither an Internet service nor a user-authenticated or multi-user deployment.
_Avoid_: Public API, remote platform

**Companion Session Capacity**:
The maximum concurrently active Object Selection Sessions that a Selection Service Companion admits. The PoC capacity is one, so a second editor receives busy rather than queuing, preempting, or sharing the first session.
_Avoid_: Job scheduler, shared session

**Selection Service Transport Baseline**:
The Chromium-compatible secure-context policy for reaching a Selection Service Companion: loopback is the default with an exact editor-origin allowlist and local-network permission, while Trusted-LAN Mode requires a browser-trusted HTTPS endpoint under the same origin policy. A denied permission, invalid certificate, or unsupported browser leaves the service unavailable rather than silently falling back.
_Avoid_: Private-network HTTP fallback, browser bypass

**PoC Technical Specification**:
The decision-ready description of the first object-selection experiment, including its interfaces, comparison methods, test scenes, success criteria, and unresolved implementation risks. It may be supported by disposable prototypes but is not the completed editor feature.
_Avoid_: Final implementation, production release

**PoC Acceptance Criteria**:
The predeclared, replayable conditions used to judge the Object Selection PoC on frozen benchmarks after its allowed Correction Rounds. They distinguish the required default evidence path from optional quality A/B results; recorded timing and VRAM are observations rather than success gates.
_Avoid_: Demo impression, benchmark tuning

**PoC Trial**:
One replay of a frozen benchmark input under its declared configuration and fixed seed. When the required default path is stochastic, every prescribed PoC Trial independently satisfies the PoC Acceptance Criteria.
_Avoid_: Best run, average-only score

**PoC Run Record**:
The immutable, version-bound record emitted for a PoC Trial. Its blind prediction record preserves inputs, Evidence Snapshot output, coverage state, correction outcome, diagnostic reason, timing, VRAM, and artifact hashes before Ground Truth opens. A separately sealed scored final record copies that blind record and hashes the independent score while binding both to the canonical target, scene, execution profile, and seed registry; assessment re-verifies the copied prediction and recomputes registered scores. Its formal gate report uses only pass or fail; missing evidence may retain an `unassessed` diagnostic state but formally fails the trial. Their absence is an observability failure; timing values are not performance gates.
_Avoid_: Console-only result, latency SLA

**Blind Prediction**:
The prediction phase of a PoC Trial, which cannot read Benchmark Ground Truth. It persists and hashes its candidate artifact before an independent scoring phase opens that Ground Truth; a breach invalidates the trial regardless of its score.
_Avoid_: Ground-Truth-assisted inference, score-tuned prediction

**Overlap Safety Gate**:
A PoC Acceptance Criterion for the controlled front/back-overlap scene that bounds wrongly committed distractor Stable Gaussian IDs independently of aggregate precision. It protects against a visually significant back-layer leak that a broad accuracy metric can conceal.
_Avoid_: Precision alone, background heuristic

**Benchmark Ground Truth**:
A frozen, method-independent Gaussian classification used to evaluate an Object Selection, with each relevant Gaussian classified as selected, rejected, or ambiguous. Ambiguous truth is excluded from accuracy calculations rather than forced into either class.
_Avoid_: Perfect mask, algorithm output, visual reference
