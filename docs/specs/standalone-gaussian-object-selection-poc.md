# Standalone Gaussian Object Selection PoC Technical Specification

Status: implementation-ready behavior and data-contract specification. The local Selection Service lifecycle follows [Choose local Selection Service packaging and lifecycle](https://github.com/Wormh0-le/supersimplat/issues/11) and its [Selection Service Lifecycle Decision](../prototypes/selection-service-lifecycle.md), without changing the editor-facing seam.

## Problem Statement

A SuperSplat user needs to select a whole intended object from one already reconstructed Gaussian scene so that existing editor operations can act on it. Ordinary screen-space selection only exposes the currently visible surface. It cannot reliably distinguish a front object from an overlapping rear object, retain back-facing geometry, explain missing evidence, or safely correct an initial selection.

The PoC must work from exactly one loaded Standalone Gaussian Scene. It may not require original images, camera poses, sparse reconstruction data, retraining, persistent object labels, or a second loaded splat. It must give a beginner a recoverable New, Add, Remove, and Refine workflow while preserving SuperSplat's existing Gaussian selection, history, delete, duplicate, separate, undo, and redo behavior.

## Solution

Add an Object Selection Session to the editor. The session owns a transient Candidate Object Selection for one Target Splat. It accepts point-only prompts, obtains a complete atomic Evidence Snapshot from a local Selection Service, presents selected and Uncertain Gaussian states, and performs exactly one Selection Commit only when the user confirms.

The highest test and editor seam is one deep ObjectSelectionSession Module. The toolbar and panel call its Interface; they do not call rendering, mask propagation, lifting, or CUDA logic directly. The Module receives an injected Selection Service Adapter, so tests can substitute a deterministic adapter. The only transition from the session into normal editor state is Selection Commit through the existing selection operation.

The editor remains authoritative for Target Splat identity, Stable Gaussian IDs, Scene Snapshot versions, Candidate Object Selection presentation, locked-Gaussian filtering, and history. The Selection Service owns inference rendering, Generated Views, promptable masks, contributor attribution, Selection Evidence, and version-keyed caches. Generated View RGB and contributor attribution always come from the same service-side rasterization.

## User Stories

1. As a beginner editor user, I want to enter a dedicated Object Selection tool, so that I can begin an object-level selection without learning renderer or model controls.
2. As a user, I want the first valid New prompt to bind one Target Splat, so that prompts cannot silently collect Gaussian IDs from another loaded splat.
3. As a user, I want to place point prompts and explicitly choose Update Preview, so that an accidental click does not immediately change the candidate.
4. As a user, I want New to start a fresh Object Selection Session, so that I can replace an earlier candidate deliberately rather than merge it by accident.
5. As a user, I want Add to include another region in chronological order, so that I can restore a part that an earlier Remove excluded.
6. As a user, I want Remove to exclude an unwanted region in chronological order, so that I can correct contact or rear-object contamination.
7. As a user, I want Refine to use explicit Include and Exclude point prompts on the primary track, so that I can improve a candidate without creating an unrelated selection.
8. As a user, I want pending prompts to be editable and removable before submission, so that prompt correction does not consume my correction budget.
9. As a user, I want selected and Uncertain Gaussian states to have distinct visual treatment and text counts, so that I know what will and will not commit.
10. As a user, I want to inspect the visible editor camera while a preview updates, so that hidden Generated Views do not take control of my camera.
11. As a user, I want a failed or cancelled preview update to preserve the last usable candidate, prompts, and correction count, so that a transient service problem is recoverable.
12. As a user, I want an actionable limited-coverage message when parts of the scene cannot be observed reliably, so that I do not mistake missing evidence for rejected geometry.
13. As a user, I want confirmation with Uncertain Gaussian states to require acknowledgement, so that I understand only selected Gaussian IDs will enter the editor selection.
14. As a user, I want Cancel to restore the entry-time Gaussian selection exactly, so that abandoning a session has no hidden edit or history side effect.
15. As a user, I want Confirm to create one ordinary selection history operation, so that existing delete, duplicate, separate, undo, and redo continue to work normally.
16. As an editor, I want stale service results rejected after scene content changes, so that evidence for an old Gaussian arrangement cannot be applied to a new one.
17. As a local operator, I want model, renderer, and evidence-policy versions recorded for every accepted preview, so that a result can be reproduced and diagnosed.
18. As a benchmark operator, I want point-only Benchmark Prompt Logs frozen before scoring, so that manual effort and method comparisons are fair.
19. As a benchmark operator, I want prediction isolated from Benchmark Ground Truth, so that reported correctness cannot be influenced by the answer key.
20. As a maintainer, I want the default contributor-weighted three-state path evaluated separately from optional soft-mask fitting, so that a quality experiment cannot hide a deficient core contract.
21. As an open-source integrator, I want core code and model metadata separated from downloadable weights, so that licensing and deployment constraints remain auditable.
22. As a future service-packaging maintainer, I want the editor-facing Selection Service Interface fixed independently of process discovery or installation details, so that packaging can change without rewriting the session workflow.

## Implementation Decisions

### Scope and ownership

The PoC accepts one already reconstructed Target Splat from one loaded Standalone Gaussian Scene. A session never combines splats. Original capture inputs, reconstruction-time metadata, named object persistence, cross-session object IDs, and scene-sidecar annotations are not inputs or outputs.

| Owner                         | Responsibilities                                                                                                                                                                                            | Must not own                                                              |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Editor                        | Target Splat identity, Stable Gaussian ID mapping, immutable Scene Snapshot creation, session UI, Candidate Object Selection, locked-ID filtering, Selection Commit, existing history and editor operations | CUDA rendering, mask-model continuation state, service tensor ordering    |
| Selection Service             | Same-renderer RGB and contributor attribution, Generated Views, point-mask propagation, Mask Set production, Coverage Report, Selection Evidence, inference caches                                          | Editor history, committed Gaussian Selection, persistent object semantics |
| ObjectSelectionSession Module | Session state, prompt staging, request ordering, preview replacement, recovery, confirmation and cancellation                                                                                               | Service process installation or model-specific UI                         |

The editor sends a Scene Snapshot once per scene content version. It contains the effective current Gaussian geometry and appearance after deletion and editor transforms, together with Stable Gaussian IDs. Original PLY row numbers, service tensor rows, render order, and tile identifiers are never result identities.

| Scene Snapshot field | Required rule                                                                                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scene identity       | Include an opaque scene ID, immutable scene version, Gaussian count, coordinate convention, attribute schema, Stable Gaussian ID schema, and appearance policy.   |
| Stable identity      | Include one unique unsigned 32-bit Stable Gaussian ID per Gaussian. An optional source-row value is diagnostic only and never returns from inference as identity. |
| Geometry             | Include means, rotations, logarithmic scales, and logit opacities after the editor's effective transforms and deletion filtering.                                 |
| Appearance           | Include DC or spherical-harmonic appearance at the declared band count, plus every background or alpha semantic needed for inference rendering.                   |
| Version semantics    | Hash all content that can alter inference RGB or contributor attribution. Exclude display names, ordinary selection, locked bits, and cameras.                    |

A Scene Snapshot version changes whenever a change can affect service-side RGB or contributor attribution, including Gaussian deletion, geometry, appearance, transform, animation-frame replacement, or Stable Gaussian ID remapping. Camera movement, ordinary selection, and locked state do not change the version. Deleted IDs are absent from the snapshot. The editor filters locked IDs before preview and commit, and reports any filtered count.

### Primary editor seam

ObjectSelectionSession is the only Interface crossed by the Object Selection toolbar, panel, browser-level workflow tests, and editor integration tests. It exposes user-intent operations rather than rendering steps.

| Session command               | Required behavior                                                                                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Enter and start New           | Preserve the entry Gaussian Selection, create a session for one Target Splat after a valid prompt, and begin a new candidate only on successful preview.  |
| Stage prompts and choose mode | Store point-only prompts in the authoritative Prompt Log without mutating editor selection or consuming a Correction Round.                               |
| Update Preview                | Submit the complete current Prompt Log and version bindings; publish a complete new Candidate Object Selection only after a successful complete response. |
| Cancel update                 | Abort only the pending request and retain the preceding usable candidate, prompts, and round count.                                                       |
| Confirm                       | Validate current versions and commit selected Stable Gaussian IDs as one normal editor selection operation.                                               |
| Cancel session                | Discard transient state, restore the entry selection and ordinary tool, and create no history operation.                                                  |

The Module receives a Selection Service Adapter as a dependency. The Adapter is an internal dependency of the Module, not a UI contract. It supports capability discovery, immutable Scene Snapshot registration, Frame Set registration, mask-session opening, preview update, update cancellation, session closure, and Frame Set release. The Adapter hides the Companion's Fetch-over-HTTP(S) transport and its operator-owned lifecycle, as specified in the [Selection Service Lifecycle Decision](../prototypes/selection-service-lifecycle.md); the toolbar and session never install, start, stop, or upgrade the process.

### Editor workflow and state rules

Object Selection is a dedicated bottom-toolbar tool with a compact session panel. Before a candidate exists, only New is available. Confirm becomes available only after a successful preview. The visible camera locks after the first pending prompt and unlocks after preview submission, clearing all pending prompts, or undoing the final pending prompt. Generated Views never move the visible editor camera and are never shown as thumbnails or model diagnostics.

New, Add, Remove, and Refine use explicit Update Preview submission. Add and Remove retain their own include and exclude semantics. Refine exposes explicit Include and Exclude point polarity. The Prompt Log is chronological: later Add can restore an earlier removal and later Remove can exclude it again. Refine updates the primary include track while preserving separately created Add and Remove tracks.

One successful inference-and-preview refresh after the initial New result is one Correction Round. A session permits at most five successful Correction Rounds after New. Prompt placement, movement, clearing, local rejection, service failure, and cancelled update do not consume a round. The UI displays the current budget and disables further updates after it is exhausted, while retaining inspection, Start New, Cancel, and Confirm Current behavior.

The Candidate Object Selection is a reversible three-state preview. A complete successful Evidence Snapshot atomically replaces all prior selected, rejected, and Uncertain classifications. No incremental mutation of evidence is visible. Failure, cancellation, stale result, or incomplete Mask Set leaves the preceding candidate intact.

Selected Gaussian states use the editor's normal stable selection treatment. Uncertain Gaussian states use a visually distinct non-color-only treatment and count. Rejected Gaussian states retain normal scene appearance. When coverage is insufficient, the panel reports that some Gaussian IDs remain unobserved and offers a user-facing corrective action without revealing internal camera or model details.

### Selection Commit and history compatibility

Selection Commit is the only Object Selection action that changes the editor's ordinary Gaussian Selection or history. It applies only the current selected Stable Gaussian IDs to the Target Splat through the existing selection operation, producing exactly one history entry. Rejected and Uncertain IDs never commit.

Confirm with remaining Uncertain Gaussian states requires acknowledgement that the committed selection may be incomplete. After Commit, the session closes, the previous ordinary editor tool resumes, and all later delete, duplicate, separate, undo, and redo behavior remains editor-owned.

Cancel restores the entry-time Gaussian Selection and prior ordinary tool. It adds no history entry. Starting a new candidate while one exists requires explicit discard confirmation. Escape removes only the latest pending prompt and never silently discards a session.

### Versioned request and response contract

Every preview request binds a request ID, session ID, scene ID, Scene Snapshot version, operation, correction round, deterministic seed, Prompt Log revision, Frame Set version, Model Manifest digest, and render configuration version. Each view carries exact camera extrinsics, intrinsics, dimensions, near and far values, projection convention, and point prompts bound to that view. The Anchor View may include the exact editor RGB that the user saw; the service still rerenders contributor attribution from the same camera.

Every response echoes all version bindings and contains a terminal status, model identity, stage timing, peak VRAM, mask outcomes, Coverage Report, evidence summary, selected IDs, Uncertain IDs, warnings, and an opaque cache token when applicable. Stable Gaussian IDs are unique, sorted, and mutually exclusive across selected and Uncertain output. The editor rejects a response if any version differs from the current session, an ID no longer exists, state sets overlap, required Anchor behavior is missing, or the result arrives after cancellation.

Service cache miss is explicit and causes the editor to resend the required immutable Scene Snapshot. The service may cache scene tensors, rendered contributor summaries, and model embeddings only under complete versioned keys. Caches are performance mechanisms, not identity mechanisms.

### Promptable masks and Mask Sets

Prompt Logs are point-only and replayable. A Benchmark Prompt Log is frozen before a PoC Trial and includes point count, order, operation, camera, and correction sequence. Existing box or text fixtures may remain diagnostic inputs for lifting comparison but cannot substitute for final editor-interaction benchmark logs.

The Selection Service preserves one primary include Mask Track and any independent include or exclude tracks. It replays the full Prompt Log when a Frame Set changes or model continuation state cannot be safely reused. Every completed update emits a complete immutable Mask Set before lifting begins.

Each track/view outcome is one of accepted, not found, rejected, or technical error. Only accepted masks can contribute observed evidence. Not found, rejected, blocked, unusable, and error views are neutral observation states, not all-zero negative masks. Partial propagation output, streamed progress, model logits, or adapter confidence never directly changes the Candidate Object Selection.

Mask publication is transactional. Stale versions, required-frame failure, cancellation, or service error discard partial output and preserve the earlier candidate. Repeating a request ID is idempotent and must not apply prompts twice. The Model Manifest records the adapter, model artifact, source revision, license, checkpoint identity, and material runtime configuration for every accepted Mask Set.

### Generated Views and coverage

Generated Views start from a two-stage Seed Region: a prompt-ray intersection followed by a robust region derived from accepted Anchor contributors. The Seed Region is a framing aid, never the final object boundary or selection.

The normal candidate layout is the visible Anchor View, an approximately thirty-degree azimuth orbit, and upper obliques, for sixteen planned views at 1008 by 1008. The policy may attempt up to eight safe replacements and twenty-four cameras total, permits one quality-driven Frame Set rebuild inside a Correction Round, and stops early after three accepted views add less than two percent new contributor coverage. Resolution may fall back to 768 then 512 only after measured out-of-memory behavior; each resolution is a different render configuration and never mixes within a Frame Set or trial.

Camera preflight rejects blocked, inside-geometry, near-plane-cut, clipped, non-finite, low-transmittance, or otherwise unsafe cameras. The policy moves outward or makes small safe angular substitutions; it never passes through walls, hides geometry, or manufactures unseen surfaces. Accepted masks also pass structural and neighbor-anomaly quality gates. The Anchor View uses the editor RGB for promptable masking and the service rerender for attribution. Moderate parity mismatch disables Anchor negative evidence; severe geometric mismatch fails safely.

Coverage is contributor-based rather than view-count-based. A Coverage Report records attempted, accepted, and rejected views; reasons; coverage summaries; incremental contribution; effective angular coverage; and sufficient or insufficient status. Insufficient coverage is not itself a technical failure and never converts unobserved geometry to negative evidence.

### Same-renderer lifting and Evidence Policy

The required default lifting path is same-renderer contributor-weighted three-state evidence. The service-side renderer that produced an accepted view's RGB also supplies alpha-times-transmittance contributor mass for that view. Only Stable Gaussian IDs within an accepted view's contributor support can receive evidence.

For each Gaussian, contribution inside the final composite mask adds positive evidence P. Contribution inside bounded support but outside the composite mask adds negative evidence N. Absence from support, out-of-support pixels, not-found views, quality-rejected views, blocked directions, and technical failures are neutral.

An Evidence Snapshot records P, N, effective observation P plus N, posterior, uncertainty reason, and selected, rejected, or Uncertain classification. Evidence Policy v1 applies a Beta(1,1) prior, with posterior equal to (1 + P) divided by (2 + P + N):

| Condition                                                             | Classification |
| --------------------------------------------------------------------- | -------------- |
| Effective observation is at least 0.10 and posterior is at least 0.80 | selected       |
| Effective observation is at least 0.10 and posterior is at most 0.20  | rejected       |
| Any other condition                                                   | Uncertain      |

There is no universal minimum accepted-view gate. One strong consistent accepted observation may resolve an ID; many weak or conflicting observations may remain Uncertain. Uncertainty reasons distinguish unobserved, insufficient observation, and undecided or conflicting evidence.

The renderer configuration, contributor semantics, evidence scale, and policy revision are one calibration unit. A change to any of them requires a new policy revision and benchmark calibration. Optional soft-mask fitting is a project-owned quality A/B only. It may run against identical frozen inputs and report a separate result, but it is not a default contract, an external SA3D or FlashSplat dependency, or a substitute for a failed required path.

### Service deployment and licensing constraints

The PoC is single-user on the same machine or a trusted local network, with an RTX 4090D as the default GPU target. It is not a public, authenticated, multi-user, internet-hosted, or production-operated service.

Core additions remain open-source-ready. SuperSplat's editor core remains MIT and the reviewed default CUDA contributor renderer is gsplat under Apache-2.0. Model weights are downloaded separately and never bundled. The promptable-mask adapter remains isolated behind the Selection Service Adapter and records its license in the Model Manifest. Research-only or non-commercial dependencies may exist only behind isolated experimental adapters. A non-equivalent renderer backend with different license constraints is not silently treated as the default CUDA deployment.

The lifecycle uses a separately installed, locked Python Companion with separately installed model weights. The operator explicitly starts and stops it; the editor uses a configured loopback endpoint by default, or an explicitly configured trusted-LAN HTTPS endpoint. Health distinguishes a reachable process from compatible capabilities. One Companion admits one active Object Selection Session and returns `busy` rather than scheduling another. Companion and model upgrades are explicit stop-install-restart operations with protocol checks and operator-controlled rollback; no active session migrates and no browser action installs, starts, stops, upgrades, or silently substitutes the service. The full browser security, CORS, local-network permission, and certificate requirements are normative in the [Selection Service Lifecycle Decision](../prototypes/selection-service-lifecycle.md). These rules do not change Scene Snapshot identity, the Selection Service Interface, model-weight separation, or the editor seam established here.

### PoC run records and benchmark execution

Each PoC Trial creates a version-bound PoC Run Record. It identifies the Scene Snapshot, Frame Set, Mask Set, Benchmark Prompt Log, Model Manifest, Companion build and dependency-lock identity, protocol version, reference browser/version, non-secret transport profile, render configuration, Evidence Policy revision, seed, Coverage Report, correction outcomes, Candidate Object Selection artifact, failure or cancellation reason, per-stage timing, peak VRAM, and later independent score.

Prediction is blind to Benchmark Ground Truth. The candidate artifact and prediction-phase manifest are persisted and hashed before the scorer opens Ground Truth. Any leakage, missing record, or missing required hash invalidates the trial regardless of score.

The required benchmark contains the exact controlled front/back-overlap fixture and the frozen simple, contact, and difficult office targets. The default path is evaluated after the blind Ready judgment. If the default path has stochastic behavior, all three prescribed fixed-seed trials independently satisfy every hard gate; best-run, average-only, or two-of-three success does not pass.

## Testing Decisions

Tests target externally visible behavior at the ObjectSelectionSession Seam rather than private renderer, model, or cache implementation details. The primary automated test surface injects a deterministic Selection Service Adapter and observes session state, emitted preview, editor selection, history behavior, and user-facing recovery messages.

Existing editor tool activation, selection operations, and history operations are integration prior art. New tests reuse those behaviors rather than duplicating delete, duplicate, separate, undo, or redo implementation inside Object Selection.

| Test level               | Required behavior                                                                                                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Session workflow         | New, Add, Remove, Refine, prompt staging, correction budget, retry, cancellation, Start New confirmation, and Cancel produce the documented state transitions without mutating ordinary selection before Confirm.                                                              |
| Preview recovery         | Failed, stale, incomplete, and cancelled updates retain the preceding Candidate Object Selection and do not consume a Correction Round.                                                                                                                                        |
| Display and disclosure   | Selected and Uncertain states are distinguishable without color alone; limited coverage presents counts and an actionable message while Generated View internals remain hidden.                                                                                                |
| Commit integration       | Confirm produces one selection history operation with selected IDs only; Cancel restores the entry selection; delete, duplicate, separate, undo, and redo work after commit.                                                                                                   |
| Stable-ID protocol       | Snapshot upload, renderer return, deleted-ID exclusion, transform correctness, sorted result IDs, cache miss, and stale-result rejection pass a golden front/back-overlap scenario.                                                                                            |
| Prompt and mask contract | Point-only Prompt Logs replay deterministically; request retry is idempotent; track composition obeys chronological Add and Remove; partial masks never reach lifting; neutral view states never become negative evidence.                                                     |
| View policy              | Safe framing, quality rejection, Anchor parity handling, bounded replacements, early stopping, Frame Set invalidation, and insufficient coverage behave as specified.                                                                                                          |
| Evidence policy          | Contributor support bounds P and N; neutral observations remain neutral; Beta thresholds classify selected, rejected, and Uncertain correctly; a later complete snapshot may move an ID between all three states.                                                              |
| Companion lifecycle      | A locked isolated install, separately verified model installation, loopback default, explicit trusted-LAN HTTPS profile, readiness gate, CORS/local-network-permission failures, one-session `busy`, graceful cleanup, and incompatible upgrade rejection behave as specified. |
| Benchmark integrity      | Prediction artifacts and manifests exist before Ground Truth scoring; required hashes and version bindings are present; stochastic trials use all prescribed seeds.                                                                                                            |

The benchmark acceptance gates are:

| Gate                               | Required outcome                                                                                                                                                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Office correctness                 | The required default path reaches Gaussian-index IoU of at least 0.80 after correction on each frozen office target. Scoring uses non-ambiguous scope IDs and counts Uncertain truth-selected IDs as not selected. |
| Controlled completeness and safety | Gaussian-index IoU, Precision, Recall, and rear-surface Recall are each at least 0.90 on the exact overlap fixture. At most 81 of its 8,192 distractor IDs may appear in the final selected set.                   |
| Manual effort                      | Each target uses its frozen point-only Benchmark Prompt Log and receives a blind Ready judgment within five successful Correction Rounds after New.                                                                |
| Honest coverage                    | Insufficient coverage leaves unsupported IDs Uncertain, discloses the limitation, and requires selected-only acknowledgement on Confirm.                                                                           |
| Compatibility                      | Preview updates create no history; Confirm creates exactly one history operation; Cancel creates none; the existing selection-operation chain succeeds.                                                            |
| Observability                      | Every required trial has a complete PoC Run Record, including timing and peak VRAM. Timing and VRAM have no numerical pass/fail threshold.                                                                         |

Current conservative one-view and two-view lifting comparisons are diagnostic method evidence, not final Ready outcomes. They must not be used to declare the PoC passed or failed before the complete session, benchmark, and acceptance sequence runs.

## Out of Scope

- Original images, camera poses, sparse reconstructions, reconstruction-time segmentation, retraining, or Segment-then-Splat-style workflows.
- Persistent named objects, semantic labels, object sidecars, cross-session object libraries, or a session spanning more than one loaded splat.
- Reimplementation of ordinary delete, duplicate, separate, undo, redo, scene loading, or the normal SuperSplat renderer.
- Public hosting, authentication, multi-user coordination, job scheduling across remote GPUs, and production operations.
- Browser-local CUDA or model inference, renderer migration, performance optimization, and a production latency service-level objective.
- A native-3D model as default back-side completion or refinement. It is reconsidered only if the evidence benchmark isolates a measurable gap that multi-view evidence cannot close.
- Automatic acceptance of low-quality masks, manufacture of missing surfaces, or conversion of unobserved evidence into rejection.
- Bundling model weights or treating research-only dependencies as required open-source core functionality.

## Further Notes

The concrete Selection Service lifecycle is resolved in the [Selection Service Lifecycle Decision](../prototypes/selection-service-lifecycle.md). It preserves the Editor-owned identity, Service-owned inference render, and ObjectSelectionSession seam defined above.

The specification preserves a narrow default path. It does not promise that the current contributor-weighted method already meets all quality gates. If the frozen benchmark shows a measurable remaining back-side or completeness gap after the specified workflow, that result graduates the existing native-3D fog into a new decision rather than silently expanding this PoC.

This specification synthesizes the resolved decisions in [Define the standalone object-selection benchmark and ground truth](https://github.com/Wormh0-le/supersimplat/issues/2), [Prototype the New/Add/Remove/Refine selection workflow](https://github.com/Wormh0-le/supersimplat/issues/3), [Choose the editor-to-Selection-Service scene boundary](https://github.com/Wormh0-le/supersimplat/issues/4), [Define the promptable-mask service contract](https://github.com/Wormh0-le/supersimplat/issues/5), [Define the Generated View policy for complete coverage](https://github.com/Wormh0-le/supersimplat/issues/6), [Compare 2D-to-Gaussian lifting methods on shared masks](https://github.com/Wormh0-le/supersimplat/issues/7), [Define Selection Evidence and uncertainty semantics](https://github.com/Wormh0-le/supersimplat/issues/8), [Set evidence-based PoC acceptance criteria](https://github.com/Wormh0-le/supersimplat/issues/9), and [Choose local Selection Service packaging and lifecycle](https://github.com/Wormh0-le/supersimplat/issues/11).
