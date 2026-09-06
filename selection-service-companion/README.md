# Selection Service Companion

This is the operator-owned control plane for AI Select. It is a separate
Python 3.12 package and is never bundled into the browser editor or its npm
distribution. It intentionally contains no model weights. The product server
exposes only Final Spec v1.3 routes; frozen Object Selection helpers remain
in-process for controlled historical benchmarks and have no HTTP surface.

## Install the Companion environment

Use `uv` to create an isolated environment from the repository's lock file. The
renderer and SAM3 extras are installed into this Companion-owned `.venv`; do
not activate or search `thirdparty/sam3/.venv`:

```sh
cd selection-service-companion
uv sync --python 3.12.12 --locked --extra renderer --extra sam3
```

`pyproject.toml` and `uv.lock` are the installation source of truth. The
renderer dependency declared there is gsplat `1.6.0`. The first `uv sync` may
compile gsplat's CUDA extension from source and can take a long time,
especially on a low-resource machine. Keep the Companion `.venv` and uv's
build cache so later installs can reuse them; a slow build is not a runtime
qualification result.

For CPU-only development or documentation checks, installation may defer the
CUDA extension build:

```sh
BUILD_NO_CUDA=1 uv sync --python 3.12.12 --locked --extra renderer
```

This CPU setup is not a GPU renderer or #115 acceptance run. A GPU operator
should use the normal locked command above and record the actual GPU/runtime
facts when performing a real check.

`uv` consumes `pyproject.toml` and `uv.lock` during installation. The Companion
does not download or register a model, modify the editor, or compare dependency
versions, source revisions, or lock-file digests with values embedded in runtime
code. Renderer availability checks CUDA, importability, and Companion-local
package ownership. Availability does not qualify a runtime for production
Evidence or aggregation; record actual runtime facts with input exports.

## Render authoritative RGB with optional reference Contributor diagnostics

The production Companion registers its gsplat renderer by default, but
advertises it as ready only after the current process passes the availability
checks above. The renderer accepts only
protocol-1 SuperSplat
snapshots using `playcanvas-gsplat-classic`, opaque background, right-handed
world coordinates, XYZW quaternions, the declared effective DC/SH schema, and
render configuration `supersplat-effective-rgb-v1`.
Malformed or unsupported values fail before the snapshot enters the immutable
service cache.

Renderer-owned reference View entries bind a pinhole camera with
`convention: "opencv-world-to-camera"`, a row-major 4x4 `worldToCamera`
matrix, a row-major 3x3 `intrinsics` matrix, and finite `nearPlane` and
`farPlane` values. One gsplat call produces service RGB and raster alpha, then
the complete contributor-ID operation consumes that call's projection and tile
data. Tensor row IDs map directly through the immutable Scene Snapshot order to
Stable Gaussian IDs; padded `-1`/zero entries are discarded. Every pixel must
conserve contributor mass against raster alpha within
`2e-6 + 1e-5 * abs(alpha)`. Missing support, invalid IDs or weights, and mass
mismatch abort the preview; there is no nearest, visible-only, top-k, or custom
backend attribution fallback.

AI Select v1 registers its immutable effective Scene Snapshot through the
versioned Binary SceneSnapshot begin/chunk/commit protocol, then creates an
Anchor through `POST /ai-select/anchor-renders`. The payload is bounded raw
typed binary chunks, not a PLY path, base64 payload, or per-Gaussian JSON graph;
the Companion only publishes its mmap-backed snapshot after commit succeeds.
The Anchor request carries the editor-owned `AIRequestBinding`, Target Splat ID,
render-configuration version, `CameraBinding`, and a `renderAttemptId`.
`CameraBinding` is an OpenCV camera-to-world affine matrix plus pinhole
intrinsics, resolution, clipping, and convention revision. The Companion
derives its row-major `opencv-world-to-camera` matrix, then publishes PNG RGB
with its SHA-256 digest and the `gsplat-rgb/v1` renderer version. Replaying
the same `renderAttemptId` is idempotent; a normal changed/reset-pose render
intent mints a new attempt and actually reruns instead of replaying a cached
result or failure. No identical-input Render Retry is exposed. The editor verifies the PNG
SHA-256 digest before displaying it. No PlayCanvas framebuffer/canvas capture
is accepted as AI Anchor observation truth. See [Binary SceneSnapshot Registration v1](../docs/protocols/binary-scene-snapshot-registration-v1.md).

The production Anchor response is RGB-only: it never invokes, allocates,
hashes, serializes, caches, or waits for complete per-pixel Contributor
IDs/weights. The complete Contributor backend is reachable only through the
explicit `referenceContributor: true` debug/reference opt-in (advertised as
`aiSelectAnchorReferenceContributor`), which adds a
`referenceContributorDigest` to the response. Its failure degrades to the
diagnostic-only `referenceContributorError` field and never converts a
successful authoritative RGB render into a Preview Failure.

The legacy PoC route's editor-registered Anchor PNG parity policy remains
limited to legacy fixture/session compatibility. It is not used by AI Select
v1 and must not be extended as an alternate Anchor RGB path.

## Compute reference per-View P/N/V Evidence

Ticket 14B keeps a trusted complete-Contributor reference backend behind the
explicit `GsplatContributorRenderer.compute_reference_evidence` boundary. It
rerenders the exact CameraBinding and full conservative Render Working Set,
verifies the admitted token against the exact full/packed SceneSnapshot content
or spatial Working Set, validates complete `alpha × incoming-transmittance`
mass and Stable Gaussian ID mapping, then writes raw P/N/V (plus separate
Boundary Mass) only for the Evidence Working Set. Its versioned pixel policy separates strong positive
interior, boundary/ignore, local negative context and far-neutral regions;
the three weights are independent and `P + N = V` is never assumed.

The companion-side discrepancy report compares every available trusted
reference artifact pair (Contributor and stock-gsplat autograd when an
autograd producer is supplied) using max/p95/p99 absolute and relative error,
support differences and threshold-near differences. It never retunes Evidence
thresholds to hide disagreement. This is a reference/debug path for Tickets
14C/14D and later production comparison; it is not Ticket 20 same-decision
production Evidence and it adds no browser route or Candidate publication.

The locked gsplat build evaluates the shared per-Gaussian alpha in separate
CUDA translation units, so the RGB and contributor kernels can disagree by a
few float32 ulps exactly at the `1/255` validity cut, the `1e-4` transmittance
termination cut, or sigma zero. When a pixel fails the mass check only because
of such a boundary flip, the renderer replays that pixel's tile from the same
projection/tile preparation, keeps the unique decision variant that reproduces
the RGB rasterization's own alpha, and rebuilds that pixel's contributor IDs
and weights from the matched chain. This reconciliation runs only inside the
explicit reference Contributor path, where an unexplained mismatch becomes the
diagnostic `referenceContributorError` rather than an RGB failure; the legacy
evidence consumers keep their fail-closed abort. See ADR 0010 under `docs/adr/`.

## Aggregate and classify reference multi-View Evidence

Ticket 14C consumes the independently published 14B per-View artifacts through
`aggregate_reference_gaussian_evidence`. Every Included View must carry exact
current target/dependency, Camera, RGB, Stable Mask, Working Set, policy,
renderer, backend and runtime identity; missing or stale Included Evidence
fails before a result is returned. Included artifacts must also share Evidence
policy, raster implementation, backend and runtime identity. Excluded Views
are omitted and never become negative Evidence.

The default versioned policy caps each View's Visible Mass contribution per
Gaussian and scales that View's P/N channels by the same factor. A declared
raw-mass mode remains available for benchmark comparison. The result preserves
the source artifacts, raw and effective per-View P/N/V, supporting/conflicting
View IDs, policy/artifact-set/backend identities and a deterministic digest.
It classifies the declared universe against an explicit classification scope
into Selected, Rejected, Uncertain and Out of Scope; only Selected IDs enter
the handoff set for Ticket 14D. The classification scope is independent of a
TargetGeometryHint-seeded Evidence Working Set, so an unwritten ID inside that
scope remains Uncertain instead of becoming Rejected or Out of Scope.
When the Working Set records a TargetGeometryHint seed, the Companion rejects
any classification scope narrower than the declared universe, preventing the
geometry seed from becoming an ownership boundary. Unobserved, insufficient,
mixed or conflicting support remains Uncertain.

This is CPU reference aggregation/classification. It adds no browser route,
does not publish a Candidate or mutate Native Selection, and is not Ticket 20
production same-decision GPU Evidence.

## Run the issue #115 Bonsai diagnostic

The operator-only harness consumes the tracked A/B/C input archives and the
current Companion process. It validates the shared binary Scene Snapshot,
recomputes production Direct Evidence from the exported user-confirmed A/B
masks, evaluates the frozen S0 shadow policy, creates the existing EWS
Core/Context binding, performs one raw-mass A+B aggregation, and renders C for
inspection only:

```sh
uv run --no-sync python scripts/run_issue_115_bonsai.py \
  --input-directory ../data/issue-115-bonsai \
  --output /secure/issue-115-bonsai-diagnostic.json
```

The command requires the real CUDA renderer and the SAM 3 checkpoint to be
present in the ModelScope cache. It never generates replacement masks, uses C
as fusion Evidence, publishes a Candidate, or changes editor state. The
result records the input identities, policy, counts, timings, host/GPU peak
resource readouts, and C's new/contamination/unknown inspection categories.
The full historical TargetScopeState ledger is not run by this 1.24M-row
diagnostic; the result marks that Scope/Domain acceptance item as incomplete
and must not be read as a production qualification.

## Publish a reference Candidate atomically

Ticket 14D's `create_reference_candidate_artifact` replays the exact current
aggregation input before constructing one complete `reference-pre-production`
Candidate artifact. It binds target/context/dependency, the Stable Mask and
Participation input set, Evidence and aggregation policies, Working Set,
source Evidence artifacts, raster implementation, trusted reference backend
and locked runtime. Candidate contains Selected Stable IDs only; Uncertain is a
separate diagnostic set.

Diagnostics and fixtures validate the full artifact and current binding before
one atomic replacement. Failed or stale replacement leaves the previous
reference Candidate inspectable. Stable Mask or Participation changes make it
stale until an explicit reference Re-Lift succeeds. The product composition
root neither requests nor applies reference Candidates; Native Selection and
EditHistory remain production-owned.

Ticket 21 adds the production path. Candidate Re-Lift consumes only exact
current `production-direct` per-View artifacts, aggregates them atomically and
publishes a `production-ready` Candidate. Native application additionally
requires the checksum-bound Runtime Profile production identity joining the
renderer, SAM 3 Image manifest, Prompt, geometry, Mask Review, Evidence and
Lift Readiness policies. Failed or stale replacement preserves the prior
Candidate and all Views/Stable Masks.

The Ticket 14D quality record is an archived historical artifact generated by
a GPU Contributor backend on a deterministic synthetic scene. It is not a
current #115 acceptance gate. The repository has no independent stock-gsplat
autograd Evidence producer, so the historical record declares that backend
unavailable instead of synthesizing a labeled artifact.

## Use the ModelScope-cached SAM 3 model

ModelScope owns model acquisition. The Companion only checks for an existing
SAM 3 checkpoint at
`~/.cache/modelscope/models/facebook--sam3/snapshots/<revision>/sam3.pt` and
passes that path to the official runtime. It never downloads, copies,
registers, hashes, or otherwise qualifies the model file. There is no model
installation command and no operator-selected model path.

The prepared #115 input bundle already contains the exported RGB/mask
artifacts, so installing SAM3 or rerunning mask generation is not required to
inspect that bundle. The required joint A/B human review remains an operator
gate before the bundle can be treated as #115 acceptance input.

For `adapterId: "sam3-image-instance/v1"` (the current static instance
adapter), `runtimeConfigDigest` must be
`sha256:7105a575a8c72d6fafc8117917ad30edb9364f336851e6e86dd3ee357428857f`.
It binds the Companion's fixed SAM 3 Image baseline: the official
`build_sam3_image_model(enable_inst_interactivity=True)` builder, the
`sam3-image-instance-compiler/v1` Prompt contract, fixed single-result
inference for every Prompt shape, 288×288 low-resolution
previous-prediction logits behind opaque references, rejection of degenerate
full-frame candidates, and bf16 autocast without Hugging Face downloads or
compilation. A changed runtime configuration needs a new adapter baseline and
Model Manifest digest.

For the legacy `adapterId: "sam3.1"`, `runtimeConfigDigest` must be
`sha256:6e1475abaee95d1ae97a8986494fba6ac7d3f440625f945b3ca0d258c6934c09`.
It binds the historical SAM 3.1 multiplex baseline retained for frozen
benchmark fixtures; it is not a current static instance adapter and never
advertises Ready for the current Runtime Profile.

## Acquire Generated View Masks

Generated Views use three independent endpoints after authoritative RGB is
Ready:

```text
POST /ai-select/generated-view-prompts
POST /ai-select/image-instance-masks
POST /ai-select/image-instance-mask-reviews
```

Prompt synthesis projects the exact `TargetGeometryHintArtifact` through the
accepted local View `CameraBinding`, verifies the browser's CameraBinding
digest, and binds the active model, runtime digest, and Companion Instance. It
returns either a bounded artifact with one Positive Instance Box, 1–3 Positive
Points, at most two Negative Points, and `multimaskOutput: false`, or a
structured `limited` result. Fully off-image or materially clipped support is
limited rather than inflated into a frame-edge Box. It never creates a
Negative Box, brush/mask constraint, text prompt, tracker state, or previous
logits.

The inference endpoint receives exact RGB bytes (or a current
Companion-resolvable RGB reference), verifies digest and dimensions, and runs
one independent official SAM 3 Image call with `multimask_output=false`.
It returns one usable bitset Mask at most; an empty valid result is the
semantic `unavailable` outcome, while transport/model/capacity errors remain
technical failures. Raw logits never cross the browser boundary.

Only a returned Mask from the current Companion-held inference record
reaches `local-view-assessment/v2` on the Review endpoint. It emits `good`,
`review`, or `failed` with evidence-backed Mask quality reasons;
`propagation-uncertain` and `weak-gaussian-support` are not Review vocabulary.
The Companion never publishes Stable state, Participation, P/N/V, or a Lift
from these endpoints. The browser atomically publishes Auto Good/Auto Review
Stable Masks, preserves User Confirmed authority, and keeps technical failures
separate from valid RGB and prior Stable state.

`/ai-select/generated-view-masks` and its Multiplex/propagation execution are
retired from the public route and capability contract. The historical source
remains private only for frozen migration fixtures.

## Start the control plane

The default profile listens only on loopback. The endpoint is deployment-owned;
ordinary editor UI does not expose endpoint or model controls. At startup the
process resolves the fixed current SAM 3 Image adapter when its ModelScope
checkpoint is present.

```sh
uv run --locked --extra renderer --extra sam3 selection-service start \
  --endpoint http://127.0.0.1:8787 \
  --allow-origin https://editor.example
```

Trusted-LAN use must be explicit and HTTPS-only:

```sh
uv run --locked --extra renderer --extra sam3 selection-service start \
  --profile trusted-lan \
  --endpoint https://192.168.1.20:8787 \
  --allow-origin https://editor.example \
  --cert /secure/certs/selection.lan.pem \
  --key /secure/certs/selection.lan-key.pem
```

The process stays in the operator's terminal and stops with `Ctrl+C`. The
browser never starts, stops, upgrades, installs, or rolls back this process.
Trusted-LAN hosts must resolve only to private-network addresses; public,
unspecified, and loopback listeners are rejected.

This release exposes a lightweight `/health` heartbeat with one opaque
process-lifetime `companionInstanceId`. `/capabilities` performs the heavier
readiness protocol v2 Runtime Profile validation and returns the singular
fixed `activeModelManifest`; a missing ModelScope checkpoint reports the
Companion as unavailable. The browser runs `/capabilities` on first
connection, recovery, or Instance replacement rather than on every heartbeat.

The current static instance adapter is `sam3-image-instance/v1`, built on the
official SAM 3 Image instance-interaction path
(`build_sam3_image_model(enable_inst_interactivity=True)` →
`Sam3Processor.set_image` → `predict_inst`). It never instantiates the
Multiplex video predictor or calls private tracker-head methods. The
historical SAM 3.1 Multiplex-backed static shim is retired; its adapter
remains only for frozen in-process benchmark fixtures and never advertises
Ready for the current `ai-select-static-image-instance/v1` profile.

The current control plane exposes `/scene-snapshot-uploads/v1`, the AI Select
Anchor route `/ai-select/anchor-renders`, the Anchor proposal route
`/ai-select/mask-proposals`, and the three Generated View endpoints
above. The Runtime Profile must advertise `aiSelectMaskProposals`,
`aiSelectGeneratedViewPromptSynthesis`, `aiSelectImageInstanceMasks`,
`aiSelectImageInstanceMaskReview`, `aiSelectAnchorRender`,
`aiSelectProductionDirectEvidence`, `aiSelectProductionCandidateReLift`, and
`binarySceneSnapshotRegistrationV1` before the browser enables the relevant
AI Select actions. The v1 Prompt surface is exactly positive/negative
Point and at most one Positive Instance Box in authoritative-image pixel
XYXY; Negative Box, Prompt Brush, Mask Constraints, and Text are removed from
the schema, capability record, and compiler, and old artifacts carrying them
fail closed by version/capability identity. Every Point, Box, or
previous-logits request fixes `multimaskOutput: false` and retains at most one
result, which the browser automatically adopts as the Editing Mask.
Paint/Erase remain Editing Mask operations and never enter a model request.

Every inference request carries either the exact authoritative RGB artifact or
a Companion-resolvable immutable RGB reference whose digest matches the
request identity; digest-only input without resolvable bytes fails before
inference. Low-resolution previous-prediction logits stay Companion-local;
the browser receives only an opaque digest-bound reference that resolves
inside the exact Companion Instance for the same View/RGB/adapter lineage and
chosen candidate, forces single-mask refinement linked to the source attempt,
and falls back to a fresh Point/Box prediction when expired or unresolvable.
The capability record binds `sam3-image-instance-compiler/v1`; changing
support or compilation semantics rotates its digest so incompatible prompt
replay fails closed.

The compiler preserves authoritative RGB pixel coordinates and orders each
prompt family by `promptId`. Every structurally valid raw Point/Box SAM
alternative is forwarded in source order with its adapter-local IoU
prediction semantics and per-prompt diagnostics; a raw model score orders the
preview but never auto-confirms a Mask. The existing Ticket 07A seam performs
any later ranking and publishes the bound `ProposalDecision`.

## Historical internal CWED qualification

Issue #53's CWED qualification is an archived internal GPU/envelope record. It
is not a #115 acceptance gate, and its historical dependency-version, source,
and lock-file fields are not read by the current runtime. Keep the checked
record for traceability; do not use it as evidence that the current operator
environment or #115 input has passed.

If #53 is deliberately rerun later, generate a new record from the repository
root with:

```sh
uv run --project selection-service-companion --locked --extra renderer \
  --python 3.12 python \
  selection-service-companion/scripts/benchmark_v2a4_cwed_qualification.py \
  --output /secure/qualification-runs/depth-moment-cwed-current.json
```

The current helper compares the actual process's operating system, GPU,
driver, compute capability, Direct Evidence identity, and measured envelope.
The frozen minimum M0 is `1/255`; this internal readout does not enter
`/capabilities`, the Browser Runtime Profile, Gaussian Evidence, Production
Identity, or Candidate identity. Work outside a newly measured envelope stays
on ordinary single-N production Direct Evidence without a CWED readout.

Run the opt-in locked real-model check with the ModelScope-cached SAM 3 Image
checkpoint and CUDA:

```sh
uv run --locked --extra sam3 python -m unittest discover \
  -s tests -p test_sam3_image_instance_gpu.py
```

`/scene-snapshots/...` remains a JSON fixture-registration compatibility
endpoint; the product browser uses Binary SceneSnapshot Registration v1.
Object Selection Session and Frame Set routes are absent. Renderer readiness
checks the gsplat/CUDA runtime from the current Companion process. The
Anchor route is bound by `targetContextId`, context revision, and dependency
token; late browser results are discarded editor-side rather than relying on
request cancellation for correctness.

## Run the sealed depth-classified Negative Evidence experiment

V2AX is a benchmark-only, nonblocking experiment. It first seals the unchanged
production single-`negativeMass` baseline, then writes separate
`experimental/reference` front/near/behind sidecars and Candidate replays. It
never changes production Evidence, readiness, Runtime Profile, Candidate
binding, or orchestration.

Prediction opens only the configuration's allowlisted
`depth_classified_negative_evidence_prediction_input.json`: a label-free PLY,
inline CameraBindings, and a masks-only NPZ. The Evidence Working Set is the
validated whole Scene Snapshot with no `targetCount` split. The production
baseline executes Direct Evidence with depth moments disabled. A separate
qualified CWED acquisition and the reference Contributor stage must prove the
same RGB identity, Stable-ID row mapping, and exact pinned gsplat
`meta["depths"]` tensor digest before classification; mass channels must remain
within the production conservation tolerance.

Costs are recorded as audited GPU sums of per-View medians (with maxima of
identically reset per-View start/peak/end allocation boundaries), whole-stage
Candidate-replay medians, and logical output-element writes: production baseline,
baseline Candidate replay, shared CWED/readout acquisition, reference
Contributor plus sidecar classification, and variant Candidate replay. The
reported method total is explicitly derived (sum of component medians, maximum
component peak), not presented as a paired end-to-end sample. The prediction
seal indexes the prediction-input manifest, baseline bundle, every sidecar, and
every Candidate replay by relative path and file SHA-256; canonical artifact
digests and source bindings are revalidated before the scorer first opens
Ground Truth.

From the repository root, run the locked-GPU prediction without a Ground Truth
argument:

```sh
uv run --project selection-service-companion --locked --python 3.12.12 \
  --extra renderer python \
  selection-service-companion/scripts/benchmark_depth_classified_negative_evidence.py \
  predict \
  --scene-id controlled-front-back-overlap/v2 \
  --seed controlled-overlap-seed-1 \
  --output /secure/v2ax-runs/controlled-overlap-seed-1
```

Only after the prediction seal exists, invoke the independent scorer:

```sh
uv run --project selection-service-companion --locked --python 3.12.12 \
  --extra renderer python \
  selection-service-companion/scripts/benchmark_depth_classified_negative_evidence.py \
  score \
  --prediction /secure/v2ax-runs/controlled-overlap-seed-1 \
  --ground-truth \
  selection-service-companion/tests/fixtures/ai-select-v1/controlled-overlap/controlled_front_back_overlap_ground_truth.json \
  --output /secure/v2ax-scores/controlled-overlap-seed-1.json
```

Generate the final recommendation after every declared scene/seed score is
available:

```sh
uv run --project selection-service-companion --locked --python 3.12.12 \
  --extra renderer python \
  selection-service-companion/scripts/benchmark_depth_classified_negative_evidence.py \
  report \
  --scores /secure/v2ax-scores/controlled-overlap-seed-1.json \
  --output /secure/v2ax-scores/report.md
```

The sealed configuration is
`tests/fixtures/ai-select-v1/depth-classified-negative-evidence-v1.json`. Any
future promotion requires a new reviewed schema, policy, reference-parity, and
production-identity migration Issue.
