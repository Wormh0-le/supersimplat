# SuperSimPlat Domain Vocabulary

SuperSimPlat adds object-aware AI selection to the existing Gaussian editor. This glossary names concepts; it does not establish shipped features, runtime versions, thresholds, or implementation order. The current product contract and queue are in [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37); task guidance starts in [AGENTS.md](AGENTS.md). Historical glossary wording is preserved at [b76aa99](https://github.com/Wormh0-le/supersimplat/blob/b76aa99c0545988f3807677105052260e476cbce/CONTEXT.md).

## Product and scene

**AI Select** — Object-aware selection inside the existing editor, not a separate application, reconstruction pipeline, or persistent object database. One target is worked on at a time; original capture trajectories are not required scene inputs.

**Native Selection / Gaussian Selection** — The editor's actual selection state. Only explicit native operations change it and its EditHistory.

**Current Target Context** — Transient state for one target, including Views, masks, Evidence, derived computation, and Candidate. It is distinct from reusable runtime caches and does not promise cross-reload target history.

**Target Splat** — The active Gaussian asset within which an object is being selected. The asset is not identical to the target object.

**Stable Gaussian ID** — Identity surviving supported row/upload reordering. A tensor row or current editor index is not a substitute for it.

**Scene Snapshot** — An immutable, identity-bound representation of the relevant Gaussian scene, including geometry, appearance, render state, and transforms. Packed arrays and chunk uploads are transport representations, not semantic ownership.

**Snapshot Content Digest** — Integrity identity of a concrete snapshot's content. It is distinct from request identity, cache residency, and a semantic dependency token.

**TargetDependencyToken** — Semantic identity of rendering/lifting dependencies. Exact Undo may restore compatibility; a monotonic scene counter alone cannot express that restoration.

**Spatial Scene Manifest / Chunk** — Versioned spatial indexing and bounded scene payload units. Chunk presence or AABB inclusion is not visibility proof. Missing required chunks cannot be treated as a complete render.

**Render Working Set** — Gaussians required to preserve the complete compatible scene's occlusion, transmittance, and termination behavior, including non-target occluders.

**Evidence Working Set** — Explicit IDs and roles receiving semantic Evidence writes. It is not the Render Working Set and not Candidate membership. New Frontier roles must not be smuggled into a legacy Context field.

**Working Set Token** — Canonical logical membership/role identity, not upload order or a promise that a device cache still holds the data. Begin/chunk/commit registration must not publish partial scene state.

## Views and space

**CameraBinding** — One exact pose, intrinsics, image size, clipping configuration, and coordinate convention associated with a View/render. The inspection camera does not silently replace it.

**Editor / Scene Camera** — The navigational viewpoint used to inspect the scene. Automatic observation generation does not move it.

**Anchor View** — The reference View created from the chosen initial Editor Camera and authoritative Companion rendering. It is not a browser screenshot. Its confirmed mask establishes target identity, not all target membership.

**Generated View** — A planner-authored observation with a fixed CameraBinding. Its frustum is read-only outside explicitly authorized authoring behavior.

**User-added View / Expert Observation** — An explicitly user-authored camera observation for recovery. It follows ordinary render, mask, Participation, and Evidence validation; it does not move the Anchor or patch Candidate membership directly.

**AI View** — A stable View identity whose RGB, Mask, Participation, and Evidence progress independently. RGB Ready alone is not a usable semantic observation.

**TargetGeometryHint** — Geometric localization/framing and prompt support derived for the target. It is neither a semantic label nor a permanent discovery boundary.

**Prompt Support** — Validated geometric input used to synthesize a View's prompt. Hint geometry, prompt feasibility, mask quality, and lifting support are separate assessments.

**Local Key-View Plan** — A bounded family of camera proposals. A candidate pool is not a fixed product-level requirement to acquire a particular number of Views.

**Camera Inspection** — Navigation to an existing View/frustum with a separately retained Scene Camera. Hover, selection, jump, and Return change inspection, not the View's semantic input.

**Draft Frustum / Staged Render** — Local camera authoring state versus a complete render of one frozen draft revision. Moving the draft invalidates use of a mismatching staged result. Staged content is not authoritative Evidence until explicit commit.

**Use Current View / Add Observation** — Capture the accepted current camera or adjust an independent draft camera, respectively. Both create a new observation through stable publication boundaries, not through per-frame remote preview.

## Masks and Participation

**Prompt State** — Point/box inputs to the instance-mask adapter, separate from manual pixel edits. Supported prompt forms come from the actual adapter contract; a UI label cannot invent a capability.

**Prompt Compiler / Synthesis** — Versioned conversion from validated authoring or geometric support into the model's instance prompt. It produces no Gaussian ownership.

**Single Mask Result** — One instance result exposed by an inference request, not a proposal carousel. A retained proposal wire envelope is compatibility syntax, not a second product workflow.

**Previous Logits Reference** — Opaque Companion-local iterative-inference state bound to the relevant image, model, and process. It is not a Browser-owned logit tensor or an identity that survives arbitrary cache loss.

**MaskAnnotation** — A versioned per-View mask and its provenance. Image dimensions, Camera/RGB identity, and prompt/manual origin remain bound.

**Editing Mask** — An unpublished inference/manual draft. Paint/Erase modify pixels; Point/Box change inference input. Draft edits do not replace Stable Evidence or stale a Candidate until the authoritative commit.

**Stable Mask** — The published mask version eligible for observation processing. Stable means accepted and identity-bound, not infallible semantic Ground Truth.

**Confirm Mask** — Atomic publication of the Editing Mask as Stable, invalidating dependent work as required. It does not apply Native Selection.

**Automatic Mask Publication** — Publication of a reviewed automatic single-mask result without requiring an Editing draft. Later correction uses a separate draft and preserves the prior Stable version until confirmation. User-confirmed authority is not silently overwritten.

**Mask Quality / View Assessment / Review Reason** — An evidence-backed automatic quality assessment and reason, separate from Participation and 3D lifting quality. It is not a universal calibrated confidence percentage.

**Participation** — Included or Excluded for one View's Stable Mask. Auto Good defaults Included; Auto Review/failed or unavailable review defaults Excluded; User Confirmed defaults Included unless explicitly excluded. Derived Reliability does not silently change Participation.

**Included Stable View Annotation** — An Included Stable Mask with matching authoritative RGB. It becomes usable Evidence only when matching production Direct Evidence is available.

## Evidence and derived scope

**Direct Evidence / P/N/V** — Immutable per-View, per-Gaussian contribution measurements. P is positive-region mass; N is explicit local negative-context mass, not all pixels outside the mask; V is realized visible mass independent of semantic weight. Production single-N and experimental depth-classified N are distinct.

**Boundary / Ignore Evidence** — Ambiguous mask-edge contribution, neutral or policy-controlled low semantic weight; it is not forced foreground/background.

**Same Decision Source** — Authoritative RGB and Evidence use the same accepted sequence and alpha times incoming-transmittance decisions. One literal kernel launch is not required; independently repeating similar formulas is not sufficient proof.

**GaussianEvidenceArtifact** — Stable IDs and raw arrays bound to target/dependency, Camera/RGB/Stable Mask, Working Sets, policy, and actual renderer/runtime identity. It is not an unbound mutable accumulator.

**Evidence Ready** — A complete artifact matches the current observation and computation dependencies. It is not synonymous with RGB Ready or Mask Ready.

**Reference Contributor Backend** — Complete per-pixel attribution for reference/debugging and parity fixtures. It is not the production readiness prerequisite.

**Conservative Seed Support** — A deliberately incomplete high-precision bootstrap prior, not ownership, Candidate, or the target's full discoverable extent. Core/satellite/filtered/unevaluated outcomes remain diagnosable; low visibility is not background.

**S0 / S1** — Evidence-and-connectivity Seed versus an optional soft depth-consistency variant. Their names do not imply production adoption. A failed or unscorable depth feature must not erase plausible seed-external discovery.

**Contribution-Weighted Expected Depth (CWED)** — An internal statistic from accepted contribution moments M0, M1, and M2: mean M1/M0 with validity and variance. It is not first-hit depth, a guaranteed physical surface, or Gaussian ownership. Invalid/low-mass or high-variance support cannot become a hard semantic rejection by itself.

**TargetScopeState / Scope Revision** — One immutable target-local snapshot of Core, discovery support, active Frontier, and required Context, with policy/provenance identity. Computation binds one exact revision; changing it invalidates dependent results.

**Scope Epoch** — The compatibility interval within which Core is monotone. Authoritative corrections/removal or incompatible inputs can rotate it. Adding an observation alone does not authorize Core shrinkage. Exact restoration is not approximate remapping.

**Core** — Current high-confidence support used for target observation coverage. It is neither Candidate membership nor proof of complete target discovery.

**Discovery Envelope** — Bounded, target-local potential support with actual source provenance, including seed-external discoveries. It may contain background. An initial Seed or fixed spatial boundary must not silently make legitimate later discoveries unreachable.

**Frontier** — Plausible support outside Core that remains unresolved and reversible. Retention, rejection, and reopening are not ownership. Rejected Frontier does not automatically become Context; unchanged input is not new reopening authority.

**Context** — Explicitly required local comparison support. It is not a dumping ground for missing, rejected, or unobserved target support.

**Component / Lineage** — Deterministic spatial grouping and traceable group change under the applicable Scope policy. Consumers use the owning interface rather than reconstructing their own incompatible histories.

**Scope Delta** — A proposed change of scope. Committing a material change requires fresh dependent computation before any result can claim current roles and membership together.

**Consensus / q / s** — Derived 3D hypothesis, membership tendency, and support/knownness. q is not a calibrated probability or Candidate. Similar intermediate q can mean unknown at low s or conflicting observations at high s. The previous hypothesis is not new raw Evidence.

**Observation Reliability** — An optional derived observation weight affecting P/N only, never raw V or Participation. User-confirmed/manual masks are exempt from automatic downweighting; insufficient comparison support is unknown reliability, not a reason to discard an observation.

**Unresolved Support / Frontier Debt** — An explanation of material plausible support that is insufficiently observed or conflicting. Rich debt families and hysteresis are mechanisms, not vocabulary-implied implementation prerequisites. Gaussian count alone does not establish materiality.

**Selected / Rejected / Uncertain / Out of Scope** — Sufficient positive support; sufficiently observed negative support; absent/weak/conflicting support; or outside the declared semantic solve scope. Missing observation does not mean Rejected, and Uncertain is excluded from native Candidate application.

## Coverage, acquisition, and outcomes

**Observation Coverage** — Realized relevant support from Included Views' unweighted V. Repeated or duplicate Views cannot manufacture novel coverage. High Core Coverage alone does not establish target completeness.

**View Diversity** — Useful directional differences between actual observations, not simply the number of cameras.

**View Utility / ViewUtilityProbe** — Prospective value of a candidate camera versus an occlusion-aware planning approximation used to estimate it. Probe output is not authoritative RGB, Mask, Evidence, realized Coverage, or publication permission. Only the selected camera proceeds to full acquisition.

**Lift Readiness** — Not Ready, Limited, or Ready under an adopted quality policy and complete current inputs. It is distinct from technical service readiness and publication eligibility; no universal View count or physical-object-completeness guarantee is implied.

**Acquisition Attempt / Iteration** — One bounded Browser-driven run versus one observation/planning step within it. Solver iterations and Scope revisions are separate concepts, not excuses to grant unbounded work.

**Acquisition Series** — Related attempts sharing target-local cumulative protections. This concept does not require a generic accounting framework or a persistent session database.

**Stop Reason** — A structured explanation of success, insufficient gain, exhausted limits, no feasible view, failure, cancellation, or incompatibility. Actual active schemas own exact enum values; a glossary is not a wire definition.

**Pause / Resume / Continue** — Pause reaches a safe boundary; explicit Resume continues compatible unchanged retained work; explicit Continue creates a fresh attempt from current compatible inputs. Editing completion never implicitly chooses either. New computation after incompatible cache loss is not an exact Resume.

**Cancel** — Immediately closes the old run's acceptance/automatic-publication gates. Completed independent artifacts survive; late work cannot gain authority. Only an already complete compatible pre-Cancel snapshot may support a later explicit use.

**Request/Result Identity / Event Log** — Actual binding and duplicate-detection state versus diagnostic history. A hash-chained journal and cross-restart exact replay are stronger mechanisms, not inherent requirements of these terms.

## Candidate and recovery

**Candidate Publication Snapshot** — Complete immutable inputs/result eligible to be judged for publication; not yet a Candidate. A development/shadow result does not qualify merely because its arrays and hashes are complete.

**Publication Eligibility / Consent** — Current valid qualified computation versus permission to publish that snapshot. Normal eligible Ready-low-gain can auto-publish; forced Ready and eligible Limited require their distinct explicit use actions. Not Ready, incomplete, stale, or incompatible results remain forbidden. An enabled iterative solver must converge; another method cannot fake that status.

**Use Ready / Use Limited Candidate** — Explicit acceptance of the already computed exact snapshot, without rerunning inference, aggregation, or acquisition. Publication is atomic and never self-applies.

**Re-Lift / Gaussian Lifting** — Recompute from exact current Stable inputs and Evidence. It is neither old-snapshot consent nor Continue. Limited still needs separate consent under the adopted product contract.

**Candidate** — A complete identity-bound Selected result plus separate Uncertain diagnostics, inspectable before explicit Native application. Failed replacement preserves the previous Candidate.

**Candidate Overlay** — Non-destructive visualization separate from native SplatState and EditHistory.

**Candidate Stale / Temporarily Blocked** — Bound inputs no longer match versus a still-current Candidate whose application is temporarily unsafe during running work. Starting acquisition alone does not stale it; a real bound-input change can.

**Suspended Context / Undo Scene Change** — A target whose scene dependencies no longer match, retained for inspection and exact recovery. Ordinary Native Undo restores use only if the effective dependency matches; no partial artifact repair is implied.

**AIRequestBinding / Explicit Recompute State** — Target/context revision/dependency plus relevant endpoint and artifact identity, and the derived dirty/stale dependencies. Request ID alone is insufficient. Unpublished drafts do not create automatic inference or lifting authority.

**Restart Current Target / 选择另一个对象** — Dispose target-local AI work, retain Native Selection/EditHistory and permitted runtime caches, and start a fresh target. It is distinct from Exit AI Select and from clearing native selection.

**Native Candidate Operation** — Explicit Set (`S'=C`), Add (`S'=S∪C`), Remove (`S'=S−C`), or Intersect (`S'=S∩C`) through Native EditHistory. Add/Remove are not inference modes.

## Interface responsibilities

**AI View Dock** — Navigator, Work Area, and Inspector for rendered evidence, 2D authoring, and workflow explanation. Gallery filters/sorting affect presentation only.

**Session Strip** — A compact single-line workflow explanation with at most one contextual action, not a permanent title, second toolbar, or algorithm dashboard.

**Spatial Authoring / Main Viewport Toolbar** — The owner of Adjust Anchor, Use Current View, Add Observation, and draft manipulation/render/confirm controls. The same viewport toolbar owns the distinct Candidate/native operation group.

**Spatial Edit HUD** — Read-only local feedback near the active draft, with no buttons or independent state machine. Draft motion is local; Dock authoritative images change only at stable render/publication boundaries.

**Navigator ↔ Frustum ↔ Dock** — Shared View identity for hover/selection/inspection, not a second spatial-selection model. Returning to Scene View changes navigation, not mask or View authority.

**Expert Recovery** — User-authored observations and explicit continuation after a safe pause or stop. One-click auto-Pause precedes authoritative edits; passive inspection does not pause. Layout and visual rules live in [.interface-design/system.md](.interface-design/system.md), not in algorithm state.

## Runtime and evaluation

**Selection Service Companion** — Operator-installed local/trusted-LAN Python computation service. The Browser does not install/start/upgrade it, silently substitute models, or discover arbitrary endpoints. It is not a public multi-tenant backend.

**Availability / Readiness / Capacity** — User-facing connection compatibility, technical initialization/required capability validity, and ability to admit work. Reachable is not Ready; busy or task failure is not automatically globally unavailable.

**Runtime Profile / Production Identity Record** — Required mutually compatible renderer, model, protocol, policy, and implementation identities for the adopted product path. Optional research is not automatically a required Browser capability.

**Active Model Manifest / Model Installation** — Operator-resolved immutable model/checkpoint/source/license/configuration identity, versus separately installing verified weights. The Browser does not select from a model catalog or carry weights in its distribution.

**Companion Instance ID** — One process lifetime, not a model/runtime/artifact digest. Process replacement can invalidate local RGB/logit/cache references while independently persisted masks keep their own identity.

**Trusted-LAN Mode / Transport Baseline** — Explicit operator endpoint/origin/security policy for private deployment. Simplified orchestration does not weaken transport or runtime compatibility checks.

**Reference / Shadow / Production** — An oracle or diagnostic computation, an isolated experimental path, and an explicitly qualified active product path. These categories are not interchangeable because tests pass.

**Benchmark Manifest / Run Record / Ground Truth** — Immutable declared input/configuration; actual results, hashes, environment and measurements; and separate evaluation labels. Held-out predictions are sealed before scoring. Synthetic/CPU fixtures do not prove real-scene/GPU success. Development tuning is not permission to tune held-out acceptance after seeing scores.

**Qualified Envelope** — Measured supported hardware and execution bounds, not an untested claim for all scenes or devices. Integrity of a saved artifact is distinct from numerical equivalence of recomputation.

Historical terms such as complete-Contributor production, Mask Track, Frame Set, Multiplex static adapter, and New/Add/Remove inference modes remain historical/reference terminology. They do not revive removed product workflows. Keep RGB Ready, Mask Ready, Evidence Ready, Candidate eligibility, and Native application distinct.
