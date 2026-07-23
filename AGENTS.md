# SuperSimPlat Project Contract

## Relationship to the Global Contract

This file extends the global `AGENTS.md`.

The global contract already defines generic reasoning, evidence, unknown handling, scope control, the Inspect → Protect → Change → Verify → Report loop, and reporting requirements. Do not restate or weaken those rules here.

This file adds repository-specific sources of truth, ownership boundaries, invariants, migration constraints, commands, and validation requirements.

## Current Product Baseline

SuperSimPlat extends the upstream SuperSplat browser editor with **AI Select** for object-aware Gaussian selection.

The current implementation target is **AI Select Final Spec v1.1**. It retains the v1.0 product/lifecycle model and replaces complete per-pixel Contributor artifacts as the production lifting representation with **Mask-Conditioned Direct Gaussian Evidence**.

Repository migration baseline:

```text
branch: ai-select-v1
forked from: 42f6013438f1271fcd35a4bfdc9ba5a3eb719c06
```

Do not reintroduce superseded behavior merely because old implementation, fixtures, or tests encode it.

## Sources of Truth

Before changing non-trivial AI Select behavior, inspect these sources in order:

1. `docs/specs/ai-select-final-spec-v1.1.md`
2. `docs/adr/0013-adopt-mask-conditioned-direct-gaussian-evidence.md`
3. `docs/adr/0012-adopt-ai-select-final-spec-v1.md` where not superseded by ADR 0013
4. `CONTEXT.md`
5. Relevant non-superseded ADRs under `docs/adr/`
6. The associated implementation issue under `.scratch/ai-select-v1/issues/` and its audit/traceability artifacts
7. The nearest implementation and tests
8. Dependency/runtime declarations when installation, rendering, inference, CUDA, or calibration is affected

Final Spec v1.1 is authoritative for current product, interaction, lifecycle, lifting semantics, and engineering boundaries.

Frozen benchmark fixtures, manifests, and records remain authoritative only for the benchmark data they describe. Their legacy vocabulary does not override the current product model.

When a durable domain concept changes, update `CONTEXT.md`. When an architectural decision is replaced, add or supersede an ADR rather than silently diverging. When a specification change affects implementation scope, update the local issue graph and rerun traceability/audit before declaring it ready for agents.

## Product Model

The required high-level flow is:

```text
Camera View
    ↓
Authoritative gsplat RGB
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Mask-Conditioned Gaussian Evidence (P / N / V)
    ↓
Multi-view Evidence Aggregation
    ↓
Gaussian Lifting
    ↓
AI Candidate + Uncertain
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

The following boundaries are deliberate:

- AI Select is a SuperSplat Selection Tool, not a separate semantic-object workspace.
- AI Candidate is derived state and is not directly patched with a second 3D editing system.
- Structural corrections happen through Views, Stable Masks, and Participation followed by explicit Re-Lift.
- Small final corrections happen through native SuperSplat selection tools after applying the Candidate.
- Cross-target persistent truth is Native Selection and Native EditHistory, not an AI target-session stack.
- RGB Ready, Mask Ready, Evidence Ready, and Candidate Ready are distinct states.
- Complete per-pixel Contributor is a debug/reference capability, not the production lifting contract.

## Runtime Ownership

The system deliberately separates two runtimes.

### Browser editor owns

- scene and splat state;
- Stable Gaussian IDs and mapping to current splat indices;
- Current Editor Camera and editor-side `CameraBinding` construction;
- 3D frustum presentation/manipulation;
- the single user-visible `CurrentTargetContext`;
- AI View Dock interaction and Gallery state;
- `AIView` registry and target-local lifecycle state;
- Mask version lifecycle (`editingMaskId` / `stableMaskId`) and user confirmation;
- View Participation (`included` / `excluded`);
- Candidate / Uncertain visualization;
- Native Selection and Native EditHistory;
- explicit Candidate application through existing selection/edit-history operations.

### Selection Service Companion owns

- locked authoritative gsplat AI observation rendering;
- same-decision Mask-Conditioned Evidence production;
- SAM inference and automatic Mask production/propagation;
- Generated View planning and rendering;
- evidence-backed View/Mask assessment;
- per-view Gaussian Evidence artifacts;
- multi-view Evidence aggregation and Gaussian Lifting policy;
- renderer/model/Evidence/runtime readiness;
- disposable runtime caches and service-side execution state;
- complete Contributor only as an explicit debug/reference backend.

The Companion may cache scene tensors, RGB, Evidence, reference Contributor data, and model state. Runtime cache reuse is not user-visible AI View or target-context persistence.

Do not turn the Companion into a public backend, multi-user platform, reconstruction pipeline, or persistent semantic-object database without an explicit architectural decision.

## Repository Map and Migration Seams

### Current editor composition

- `src/main.ts` — editor composition root, command queue, event registration, UI construction, Companion readiness wiring.
- `src/scene-snapshot.ts` and related snapshot modules — immutable Scene Snapshot and Stable Gaussian ID contracts.
- `src/selection-service-fetch-adapter.ts` — browser/Companion transport, registration, retries, response validation.
- `src/selection-service-readiness*.ts` — readiness and capability gating.
- `src/selection.ts`, `src/edit-history.ts`, `src/edit-ops.ts`, `src/tools/` — native selection/edit behavior and final editor mutation authority.

### AI Select target domain

New Final Spec work should converge under:

```text
src/ai-select/
```

Prefer explicit modules for durable concepts such as:

- Current Target Context;
- CameraBinding and render-attempt identity;
- TargetDependencyToken and AIRequestBinding;
- AI View registry;
- Mask annotation/version lifecycle;
- per-view Evidence identity/status;
- Candidate lifecycle;
- Participation, Coverage, Diversity, and Readiness.

Do not force these concepts into the old session state machine merely to minimize file churn.

### Companion

- `selection-service-companion/src/selection_service_companion/` — control plane, rendering, masking, Generated Views, assessment, Evidence/Lifting, runtime state.
- `selection-service-companion/tests/` — Companion contracts and behavior tests.
- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- `selection-service-companion/README.md`

### External sources

- `thirdparty/sam3`
- `thirdparty/gsplat`
- `thirdparty/splat_analyzer`

Treat `thirdparty/` as pinned upstream source, not ordinary project code. A production CUDA path must have explicit ownership, pinning, build/runtime identity, and validation; do not casually edit vendored upstream code without recording the architectural and maintenance consequences.

### Legacy PoC implementation

The following areas encode useful PoC work but superseded product semantics:

- `src/object-selection-session.ts`
- `src/object-selection-session-factory.ts`
- `src/ui/object-selection-*`
- Prompt Log / Mask Track orchestration
- `New / Add / Remove / Refine` inference workflow
- preview-confirm-close session lifecycle
- complete Contributor as the normal product lifting representation

Treat them as migration/reference code. Reuse validated primitives and trust-boundary checks where compatible. Replace tests that assert explicitly superseded behavior. Do not preserve an obsolete abstraction solely to keep legacy tests green.

## Core Invariants

### Stable identity

- The editor owns Stable Gaussian IDs.
- Stable IDs remain stable within one compatible immutable Target Splat content state.
- File order, draw order, renderer order, chunk order, and Companion tensor row do not cross the protocol boundary as identity.
- Stable Gaussian IDs crossing the boundary are unique unsigned 32-bit integers unless a versioned schema explicitly changes this.
- AI Select targets one Active Splat at a time.

### Single Current Target Context

- At most one user-visible `CurrentTargetContext` is active.
- Anchor, Views, Masks, Participation, Evidence dependencies, Coverage/Readiness, Candidate, and Uncertain are target-local.
- `Restart Current Target` rotates `targetContextId` and disposes target-local state.
- Restart preserves Native Selection, Native EditHistory, AI Select activation, tool/policy settings, and reusable runtime caches.
- Previous target AI contexts are not restored or browsed in v1.1.

### Authoritative AI rendering

- All AI observation RGB comes from locked gsplat, including Anchor Preview/Final, Generated Views, and User-added Views.
- PlayCanvas/SuperSplat remains the interactive editor renderer.
- Do not use canvas/framebuffer capture as authoritative AI observation input.
- A successful authoritative RGB render is not invalidated by later Mask, Evidence, or reference Contributor failure.
- A View can be Render Ready without a Mask or Evidence.

### RGB / Mask / Evidence / Candidate separation

- `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Render failure, Mask failure, Evidence failure, and Lift failure are distinct states and recovery paths.
- Stable Mask is required before formal per-view Evidence production.
- Evidence failure must preserve the valid RGB/View/Stable Mask and the previous inspectable Candidate.
- Candidate publication remains atomic and fail-closed.

### Same-decision Direct Evidence

Production Evidence must use actual alpha-compositing contribution:

```text
w = alpha × incoming transmittance
```

RGB and production Evidence must share the same authoritative decision source for:

- projected Gaussian data;
- front-to-back ordering;
- sigma/alpha evaluation;
- validity threshold;
- incoming transmittance;
- `alpha × T` weight;
- early termination.

One literal CUDA launch is not required. Multiple passes are allowed only when later passes reuse authoritative decisions rather than independently re-deciding boundary-sensitive acceptance or termination.

Do not claim that identical mathematical source code in separate kernels proves same-decision behavior.

### Evidence semantics

- The required production channels are per-view, per-Gaussian Positive Mass (P), Negative Mass (N), and Visible Mass (V).
- Positive Evidence comes from strong target regions.
- Negative Evidence comes from explicit local background/context regions, not the entire image exterior by default.
- Boundary/ignore regions are neutral or low-weight and may produce a separate diagnostic channel.
- Missing, unusable, excluded, or unobserved Evidence is not automatically negative.
- A Gaussian with material positive and negative support is Uncertain/Mixed, not forced binary.
- Evidence Policy is versioned, replayable, and benchmark-calibrated.
- `Uncertain` is diagnostic and excluded from native Candidate application.

### Render Working Set versus Evidence Working Set

- Render Working Set contains every Gaussian/chunk required to reproduce complete-scene RGB, occlusion, transmittance, and termination for the CameraBinding.
- Evidence Working Set contains only Stable Gaussian IDs that receive P/N/V writes, normally Core Target plus Context.
- Gaussians outside the Evidence Working Set may still be required in the Render Working Set as occluders.
- Never rasterize only the Evidence Working Set when this changes visibility or transmittance.
- Spatial reduction must be conservative and validated against a full-scene/reference path.
- Scene Chunk Miss must fail closed; never publish a Ready View from a partial Render Working Set.

### Per-view Evidence artifact

A formal per-view Evidence artifact must bind at least:

```text
target/context/dependency identity
CameraBinding digest
authoritative RGB digest
Stable Mask digest
Evidence Policy digest
Render Working Set token
Evidence Working Set token
Stable Gaussian IDs
P / N / V arrays
raster/evidence implementation identity
```

Any material dependency change invalidates the artifact. Editing an unpublished Mask does not invalidate the current artifact until Confirm Mask publishes a new Stable Mask.

### Complete Contributor reference backend

- Complete per-pixel Contributor IDs/weights are retained only for diagnostics, fixtures, and reference comparison.
- Contributor alpha reconciliation and mass-conservation checks remain valid for that backend.
- Reference Contributor failure must not turn valid RGB into Render Failed.
- Production must not silently fall back to nearest-Gaussian, top-k, distance, center projection, or visibility-only attribution.

### Retry and admission identity

- Semantic render identity and execution attempt identity are distinct.
- Same attempt may replay idempotently for lost-response recovery.
- Explicit user Retry creates a new attempt for the same CameraBinding and must actually rerun the render path.
- Do not jitter or mutate CameraBinding merely to bypass cached failure.

### CameraBinding

- `CameraBinding` is the shared truth for AI rasterization and the corresponding 3D Frustum.
- It uniquely determines pose, intrinsics, resolution, clipping, and convention.
- AI Select activation copies Current Editor Camera into Anchor CameraBinding without moving the Editor Camera.
- Generated Views never move the visible Editor Camera.
- Camera Inspection observer pose never silently becomes the Anchor.

### AI View and Mask independence

- An `AIView` may exist with RGB and no Mask.
- `stableMaskId` is the Mask version allowed to participate in Evidence/Coverage/Lifting.
- `editingMaskId` is unpublished and does not replace Stable Mask until Confirm Mask.
- Confirm Mask atomically publishes the replacement and invalidates dependent Evidence/Candidate by identity.
- Manual and automatic Masks obey the same publication rules.

### Quality and Participation

- Mask/View Quality and Lift Participation are separate dimensions.
- Auto Good defaults Included; Auto Review defaults Excluded; User Confirmed defaults Included; Failed/no Stable Mask is Excluded.
- User confirmation is authoritative for Participation.
- Review Reasons must be evidence-backed. Do not fabricate a unified confidence percentage.

### Candidate lifecycle

- Candidate derives from current Included Stable View Annotations, matching per-view Evidence, and the versioned Evidence Policy.
- Candidate is not directly 3D-patched.
- Publishing stable upstream input or changing Participation makes Candidate stale.
- Stale Candidate remains inspectable but cannot execute Set/Add/Remove/Intersect.
- Explicit Re-Lift resolves/reuses per-view Evidence, aggregates, classifies, and atomically publishes.
- Failed replacement does not destroy the previous inspectable result.

### Native selection authority

- Candidate does not modify Native Selection until explicit Set, Add, Remove, or Intersect.
- Operations preserve native set semantics and go through `SelectOp` / `EditHistory`.
- Applying Candidate does not exit AI Select or destroy Current Target Context.
- Native Selection-only changes and Undo/Redo do not stale Candidate.
- Existing delete, duplicate, separate, transform, lock, undo, and redo behavior remains editor-owned.

### Scene dependency and suspension

- AI artifacts bind semantic target dependencies, not merely a monotonic global counter.
- The dependency model covers render state, geometry, Gaussian identity/membership, and target/world transform as required.
- A material dependency mutation suspends the Current Target Context; it does not immediately destroy it.
- Suspended context is inspectable but not editable, liftable, or applicable.
- Exact Undo may restore the previous semantic token and AI state.
- Unrelated scene edits outside the dependency scope must not invalidate the target.

### Async identity and stale-result protection

All asynchronous work binds at least:

```text
targetContextId
contextRevision
dependencyToken
```

Artifact-specific work also binds the relevant Camera/RGB/Mask/Policy/Working-Set identities.

Discard any non-matching result. Correctness must not depend on cancellation succeeding; cancellation is a resource optimization.

Treat transport responses as untrusted. Validate structure, finite values, Stable IDs, camera semantics, dimensions, digests, policy/runtime identity, and publication completeness before updating state.

### Atomic publication

- Do not expose partially bound products as stable user state.
- Stable Mask publication is atomic.
- Per-view Evidence publication is atomic.
- Candidate replacement is atomic.
- Progressive View publication is allowed only when each View is independently valid and bound.
- Late/racing results never overwrite newer state.

### Coverage and Readiness

- Observation Coverage is based on valid Visible Mass over the relevant Core Target set, not whole-scene Gaussian count or frustum membership.
- View Diversity is distinct from View count.
- Lift Readiness is `Not Ready`, `Limited`, or `Ready`, not a raw camera count.
- Unobserved Gaussians remain Uncertain rather than Rejected.

## Explicitly Deferred from v1.1

DG-14 remains deferred. Do not expand current scope to include:

- user-facing Candidate provenance browser;
- Candidate source-inspection UI;
- Gaussian-level Evidence inspector;
- persistent Candidate history browser;
- reopen/restore previous target AI contexts.

Minimal internal revision/fingerprint metadata required for correctness remains required.

## Companion Ownership and Locked Runtime

The Companion is operator-owned. The browser does not install, start, stop, upgrade, discover, or silently substitute it or its model weights.

Reachability alone is not readiness. Readiness requires compatible transport, protocol, renderer, Evidence implementation/policy, model adapter/checkpoint, Model Manifest, and locked runtime.

Treat these together as the runtime contract:

- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- relevant submodule/source pins
- renderer/Evidence runtime validation constants
- capability/readiness output
- installation documentation
- GPU/integration fixtures

Do not:

- use floating upstream branches;
- substitute a nearby CUDA/PyTorch build;
- weaken checks to fit the current machine;
- describe a reference/autograd implementation as the production same-decision path;
- use `thirdparty/sam3/.venv` as the production Companion environment;
- commit model weights or operator-local state.

## Change Routing

Determine the authority boundary before editing.

### Editor-only changes

Typical areas:

- CurrentTargetContext lifecycle;
- CameraBinding, render-attempt identity, and Frustum UI;
- AI View Dock/Gallery state;
- Mask version state and manual editing;
- Evidence status/reference identity in product state;
- Candidate presentation;
- Native SelectOp/EditHistory integration;
- Stable ID mapping;
- dependency-token integration.

Preserve upstream SuperSplat behavior outside the requested seam.

### Companion-only changes

Typical areas:

- control-plane validation/readiness;
- gsplat rendering;
- Direct Evidence/reference Contributor backends;
- SAM adapter behavior;
- Generated View planning;
- ViewAssessmentPolicy;
- Evidence artifacts/aggregation/Gaussian Lifting;
- runtime caches/capacity/cleanup.

Do not change the editor-facing contract unless the slice requires it.

### Cross-runtime changes

When the editor/Companion contract changes, update the complete vertical slice:

1. TypeScript request/response/domain types;
2. editor-side runtime validation;
3. browser transport;
4. Python route parsing/validation;
5. Companion state/orchestration;
6. response/artifact construction;
7. TypeScript tests;
8. Python tests;
9. protocol/domain docs, ADRs, issues, and traceability when semantics change.

Do not make one side temporarily permissive to compensate for the other.

## Migration Discipline

Prefer tracer-bullet migration over a big-bang rewrite.

Retain and evolve validated foundations where compatible:

- Stable Gaussian ID mapping;
- SceneSnapshot serialization and spatial working-set controls;
- locked authoritative gsplat RGB;
- complete Contributor as reference/debug infrastructure;
- SAM runtime/model adapter;
- Generated View camera/planning primitives;
- existing Evidence Policy mathematics where compatible with P/N/V and Included Stable Views;
- native `SelectOp` / `EditHistory` integration;
- benchmark/reproducibility infrastructure.

Reframe or replace superseded behavior:

- ObjectSelectionSession as user-visible lifecycle;
- Prompt Log as product source of truth;
- Mask Track as top-level mask model;
- New/Add/Remove/Refine as AI modes;
- PlayCanvas-captured Anchor RGB;
- complete Contributor on the normal RGB/Anchor/Lift critical path;
- one-shot Preview → Confirm → Close;
- fixed Correction Round UX;
- whole-scene raw count coverage.

Do not cherry-pick large legacy workflow commits wholesale. Port compatible slices explicitly.

The implementation sequence for the new lifting architecture is:

```text
reference P/N/V PoC
→ policy and quality validation
→ same-decision production Evidence path
→ artifact/cache integration
→ calibration and OOM/cancellation hardening
```

Do not remove the reference Contributor backend or fixtures before the new path passes declared equivalence and quality gates.

## Code Conventions

### TypeScript

Follow repository style:

- four-space indentation;
- single quotes;
- semicolons;
- explicit interfaces/discriminated unions for protocol/lifecycle state;
- `readonly` for immutable protocol data;
- type-only imports where appropriate.

At trust boundaries, prefer explicit runtime validation over unchecked casts or `any`. Copy/freeze externally supplied mutable data before retaining it.

Keep lifecycle transitions explicit. Use the shared `CommandQueue` for work ordered with GPU readbacks or edit-history mutations. Route history-changing selection operations through `EditHistory`. Localize user-visible text.

Do not perform unrelated strictness migrations.

### Python

Follow versions/dependency sources declared by the Companion project.

Use four-space indentation, type annotations, focused validation helpers, immutable dataclasses for registered/published records where appropriate, `snake_case` internally, and established `camelCase` protocol fields.

Use atomic replacement for operator state. Keep locks narrowly scoped and do not hold state locks across expensive GPU/render/model work.

Keep invalid request, incompatibility, unavailable runtime, missing model, capacity, cancellation, render, Evidence, and Lift errors distinguishable.

### CUDA / renderer code

- Pin source, compiler/runtime assumptions, and supported GPU architecture.
- Preserve front-to-back order and Stable ID mapping.
- Never silently truncate Evidence or Contributor output.
- Detect overflow/capacity failure explicitly.
- Measure register pressure, global writes, atomic contention, latency, and VRAM.
- Treat atomic FP32 accumulation as numerically non-associative; validate classification stability rather than claiming bit-exact sums.
- A separate kernel using the same formula is not automatically equivalent to the authoritative RGB decision chain.

### Documentation and comments

Comments should explain authority, ownership, trust boundaries, identity, atomicity, and non-obvious failure behavior—not narrate straightforward implementation.

Use ADRs for durable architectural trade-offs. Use `CONTEXT.md` for stable domain vocabulary, not implementation diaries.

## Commands

### Install

```sh
npm ci
```

Initialize submodules only when required:

```sh
git submodule update --init --recursive
```

Use the Node version declared in `package.json` and Python/dependency versions declared by the Companion project.

### Development server

```sh
npm run develop
```

Open:

```text
http://localhost:3000
```

Disable browser network/service-worker caching when manually validating rebuilt frontend code.

### Standard checks

```sh
npm run lint
npm run lint:locales
npm test
npm run build
```

`npm test` is the integrated repository test entry point. Use narrow checks while iterating, then broader checks required by the affected boundary.

### Companion-only tests

```sh
npm run test:companion
```

### Locked renderer / SAM / Evidence environment

For renderer, CUDA, Generated View, Evidence/Lifting, or SAM work, follow:

```text
selection-service-companion/README.md
```

Do not claim production validation from an approximate or unverified environment.

## Validation Matrix

### Documentation-only changes

Check:

- terminology against `CONTEXT.md`;
- compatibility with Final Spec v1.1, ADR 0013, and non-superseded ADR 0012 rules;
- issue graph/traceability consistency when scope changed;
- executable commands, schemas, and examples.

### TypeScript domain/lifecycle changes

Run:

```sh
npm test
npm run lint
```

Cover applicable transitions including restart, stale-response discard, true Retry attempts, Mask publication, Evidence dirty/failed state, Candidate stale state, suspension/restoration, cancellation, and cleanup.

### Transport/protocol changes

Run:

```sh
npm test
npm run lint
npm run build
```

Test malformed input, missing/duplicate IDs, binding mismatch, stale context/revision/dependency identity, stale Camera/RGB/Mask/Policy/Working-Set identity, Scene Snapshot/chunk misses, incomplete publication, cancellation races, and idempotent versus new-attempt Retry semantics.

### UI changes

Run:

```sh
npm run lint
npm run lint:locales
npm run build
```

Render and inspect affected states, including Companion unavailable/incompatible, RGB rendering, RGB Ready without Mask/Evidence, Mask editing versus Stable Mask, Evidence failed/stale, Review/Excluded, progressive Views, Candidate Ready/Stale/Applied, Restart, Suspended, Undo recovery, and native tool interoperability.

### Companion changes

Run:

```sh
npm run test:companion
```

Also run `npm test` when editor-facing contracts are affected.

### Renderer, Generated View, assessment, or Evidence/Lifting changes

Use the exact locked runtime and required GPU.

Validate applicable behavior including:

- runtime/build/source identity;
- CameraBinding and coordinate convention;
- authoritative gsplat RGB;
- RGB readiness independent from reference Contributor/Evidence failure;
- true same-CameraBinding new-attempt Retry;
- Render Working Set full-reference parity;
- Evidence Working Set Stable ID mapping;
- P/N/V reference correctness;
- same-decision production Evidence semantics;
- complete Contributor reference equivalence where applicable;
- mixed/boundary and unobserved classification;
- multi-view aggregation and per-view invalidation;
- repeat-run classification stability under atomic accumulation;
- Generated View planning/preflight;
- evidence-backed View Assessment;
- cancellation/stale-result handling;
- measured latency, VRAM, and OOM behavior;
- atomic publication and preservation of the previous Candidate on failure.

A mocked, CPU-only, autograd/reference, or structurally validated path does not establish production GPU correctness.

### Dependency/submodule changes

Verify lockfile consistency, pinned source identity, clean installation, capability output, model/license metadata, CUDA build identity, and affected CPU/GPU tests.

## Project-Specific Completion Evidence

In addition to global reporting requirements, state:

- whether the change affected editor, Companion, protocol, docs/issues, or multiple layers;
- which validation path ran;
- whether production GPU validation actually ran;
- whether Final Spec, ADR, runtime lock, protocol, Evidence/Assessment policy, or calibration changed;
- whether the result is reference PoC, production same-decision path, or debug backend work;
- which legacy/reference path remains or was retired;
- any project invariant still unverified.

Do not describe a mocked, partial, reference-only, approximate, or unverified GPU path as production-complete.

@.codex/codebase-memory-mcp.md

@.codex/RTK.md