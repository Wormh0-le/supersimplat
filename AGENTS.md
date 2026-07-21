# SuperSimPlat Project Contract

## Relationship to the Global Contract

This file extends the global `AGENTS.md`.

The global contract already defines generic reasoning, evidence, unknown handling, scope control, the Inspect → Protect → Change → Verify → Report loop, and reporting requirements. Do not restate or weaken those rules here.

This file adds repository-specific sources of truth, ownership boundaries, invariants, migration constraints, commands, and validation requirements.

## Current Product Baseline

SuperSimPlat extends the upstream SuperSplat browser editor with **AI Select** for object-aware Gaussian selection.

The current implementation target is **AI Select Final Spec v1.0**. It supersedes the older product workflow centered on `ObjectSelectionSession`, `PromptLog`, `New/Add/Remove/Refine`, one-shot preview confirmation, and `Selection Commit` wherever those concepts conflict with the Final Spec.

Repository migration baseline:

```text
branch: ai-select-v1
forked from: 42f6013438f1271fcd35a4bfdc9ba5a3eb719c06
```

Do not reintroduce superseded behavior merely because old implementation or tests encode it.

## Sources of Truth

Before changing non-trivial AI Select behavior, inspect these sources in order:

1. `docs/specs/ai-select-final-spec-v1.0.md`
2. `docs/adr/0012-adopt-ai-select-final-spec-v1.md`
3. `CONTEXT.md`
4. Relevant **non-superseded** ADRs under `docs/adr/`
5. The associated GitHub issue and comments, when applicable
6. The nearest implementation and tests
7. Dependency/runtime declarations when the change affects installation or inference

The Final Spec is authoritative for current product, interaction, lifecycle, and domain semantics.

Frozen benchmark fixtures, manifests, and records remain authoritative for the benchmark data they describe. Their legacy vocabulary does **not** override the current product model.

When a durable domain concept changes, update `CONTEXT.md`. When an architectural decision is replaced, add or supersede an ADR rather than silently diverging.

## Product Model

The required high-level flow is:

```text
Camera View
    ↓
gsplat RGB / Contributor
    ↓
Independent Versioned Mask
    ↓
Included Stable View Annotations
    ↓
Gaussian Lifting
    ↓
AI Candidate
    ↓
Set / Add / Remove / Intersect
    ↓
Native SuperSplat Selection
```

The following boundaries are deliberate:

- AI Select is a SuperSplat selection tool, not a separate semantic-object workspace.
- AI Candidate is derived state and is not directly patched with a second 3D editing system.
- Structural AI corrections happen through Views / Masks / Participation followed by explicit Re-Lift.
- Small final corrections happen through existing native SuperSplat selection tools after applying the Candidate.
- Cross-target persistent truth is Native Selection and Native EditHistory, not an AI target-session stack.

## Runtime Ownership

The system deliberately separates two runtimes.

### Browser editor owns

- scene and splat state;
- Stable Gaussian IDs and their mapping to current splat indices;
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
- same-rasterization RGB / alpha / contributor attribution;
- SAM inference and automatic mask production / propagation;
- Generated View planning and rendering;
- evidence-backed View/Mask assessment;
- Selection Evidence and Gaussian Lifting policy;
- renderer/model/runtime readiness;
- disposable runtime caches and service-side execution state.

The Companion may cache scene tensors, renders, contributors, and model state. Runtime cache reuse is not user-visible AI View or target-context persistence.

Do not turn the Companion into a public backend, multi-user platform, reconstruction pipeline, or persistent semantic-object database without an explicit architectural decision.

## Repository Map and Migration Seams

### Current editor composition

- `src/main.ts` — editor composition root, command queue, event registration, UI construction, Companion readiness wiring.
- `src/scene-snapshot.ts` — immutable Scene Snapshot and Stable Gaussian ID contracts. Preserve and extend rather than replace casually.
- `src/selection-service-fetch-adapter.ts` — browser/Companion transport, registration, retries, response validation.
- `src/selection-service-readiness*.ts` — readiness and capability gating.
- `src/selection.ts`, `src/edit-history.ts`, `src/edit-ops.ts`, `src/tools/` — native SuperSplat selection/edit behavior; authoritative for final editor mutations.

### AI Select v1 target domain

New Final Spec work should converge under a dedicated AI Select domain seam such as:

```text
src/ai-select/
```

Prefer explicit modules for durable concepts such as:

- Current Target Context;
- CameraBinding;
- TargetDependencyToken;
- AIRequestBinding;
- AI View registry;
- Mask annotation/version lifecycle;
- Candidate lifecycle;
- Participation/readiness.

Do not force these concepts into the old session state machine merely to minimize file churn.

### Legacy PoC implementation

The following areas encode useful PoC work but also contain superseded product semantics:

- `src/object-selection-session.ts`
- `src/object-selection-session-factory.ts`
- `src/ui/object-selection-*`
- Prompt Log / Mask Track orchestration
- `New / Add / Remove / Refine` inference-mode workflow
- preview-confirm-close session lifecycle

Treat them as **migration/reference code**, not as the target product architecture.

Reuse validated primitives and trust-boundary checks where they remain correct. Replace old workflow tests when they assert behavior explicitly superseded by Final Spec v1.0. Do not preserve a superseded abstraction solely to keep legacy tests green.

### Companion

- `selection-service-companion/src/selection_service_companion/` — control plane, rendering, masking, Generated Views, evidence/lifting, session/runtime state.
- `selection-service-companion/tests/` — Companion contract and behavior tests.
- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- `selection-service-companion/README.md`

### External sources

- `thirdparty/sam3`
- `thirdparty/gsplat`
- `thirdparty/splat_analyzer`

Treat `thirdparty/` as pinned upstream source, not ordinary project code.

## Core Invariants

### Stable identity

- The editor owns Stable Gaussian IDs.
- Stable IDs remain stable within one immutable Target Splat content state.
- File order, draw order, renderer order, and Companion tensor row do not cross the protocol boundary as identity.
- Stable Gaussian IDs crossing the boundary are unique unsigned 32-bit integers unless a future versioned schema explicitly changes this.
- AI Select v1 targets one Active Splat at a time.

### Single Current Target Context

- At most one user-visible `CurrentTargetContext` is active.
- Anchor, Generated Views, User-added Views, Mask versions, Participation, Coverage/Readiness, Candidate, and Uncertain are target-local.
- `Restart Current Target` disposes the old target context and creates a new `targetContextId`.
- Restart preserves Native Selection, Native EditHistory, AI Select activation, tool/policy settings, and reusable runtime caches.
- Previous target AI contexts are not restored or browsed in v1.0.

### Authoritative AI rendering

- **All AI observation RGB comes from gsplat**, including Anchor Preview, Anchor Final, Generated Views, and User-added Views.
- PlayCanvas/SuperSplat remains the interactive editor renderer.
- Do not use `canvas.toDataURL()` or equivalent PlayCanvas framebuffer capture as the authoritative AI Anchor input.
- Contributor attribution must come from the same gsplat rasterization semantics as the corresponding AI RGB/alpha.
- Do not substitute nearest-Gaussian, visible-only, top-k, or unrelated screen-space attribution for complete contributor support.

### CameraBinding

- `CameraBinding` is the shared source of truth for AI rasterization and its 3D frustum.
- It must uniquely determine pose, intrinsics, resolution, clipping, and camera convention.
- AI Select activation copies the Current Editor Camera into the Anchor `CameraBinding`; it does not move the Editor Camera.
- Generated Views never move the visible Editor Camera.
- Camera Inspection may move the Editor Camera to an observer pose, but that observer pose must never silently become the Anchor.

### AI View and Mask independence

- An `AIView` may exist with RGB/Contributor and no mask.
- View render failure and Mask generation/quality failure are distinct states.
- `stableMaskId` is the version allowed to participate in Coverage/Lifting.
- `editingMaskId` is an unpublished replacement and does not invalidate the stable mask until Confirm Mask.
- Confirm Mask atomically publishes the editing mask as the new stable mask.
- Manual masks and automatic masks obey the same validation/publication rules.

### Quality and Participation

- Mask/View Quality and Lift Participation are separate dimensions.
- Auto Good defaults to Included.
- Auto Review defaults to Excluded.
- User Confirmed defaults to Included.
- Failed / no stable mask is Excluded.
- User confirmation is authoritative for participation; an old machine review reason must not secretly down-weight a user-confirmed mask.
- Review Reason must be evidence-backed. Do not fabricate a unified `Confidence XX%` when the metric is not a calibrated probability.

### Candidate lifecycle

- Candidate is derived from the current Included Stable View Annotations and lifting policy.
- Candidate is not directly 3D-patched as part of AI Select v1.
- Editing only an unpublished Editing Mask does not stale the Candidate.
- Publishing a new stable upstream input, changing Participation, or otherwise changing the stable lifting input makes the Candidate stale.
- Stale Candidate remains inspectable but Set/Add/Remove/Intersect are disabled until explicit Re-Lift succeeds.
- Re-Lift publishes atomically; a failed replacement must not destroy the previous inspectable result.

### Native selection authority

- Candidate does not modify Native Selection until the user explicitly chooses `Set`, `Add`, `Remove`, or `Intersect`.
- These operations preserve native SuperSplat set semantics and go through existing `SelectOp` / `EditHistory` behavior.
- Applying a Candidate does not exit AI Select and does not destroy the current target context.
- Native Selection-only changes, including Undo/Redo of selection operations, do not by themselves stale the AI Candidate.
- Existing delete, duplicate, separate, transform, undo, and redo behavior remains editor-owned.
- Locked/deleted Gaussian mutation rules remain governed by native editor behavior at the point of application.

### Scene dependency and suspension

- AI artifacts are bound to semantic target dependencies, not merely a monotonically increasing global scene counter.
- The dependency model must cover render state, geometry, Gaussian identity/membership, and target/world transform as relevant to AI rendering/lifting.
- A scene mutation that changes an actual AI dependency suspends the Current Target Context; it does not immediately destroy it.
- Suspended context is inspectable but not editable, liftable, or applicable.
- If Undo restores the exact semantic dependency token, the previous AI state may automatically become valid again without recomputation.
- Unrelated scene edits outside the actual target/render dependency scope must not invalidate AI Select merely because “the scene changed.”

### Async identity and stale-result protection

All asynchronous AI requests/results must bind at least:

```text
targetContextId
contextRevision
dependencyToken
```

Any result whose binding does not match the current context is discarded.

Correctness must not depend on cancellation succeeding. Cancellation is a resource optimization; binding validation is the correctness boundary.

Treat transport responses as untrusted data. Validate structure, identity, finite numeric values, Stable IDs, camera semantics, artifact digests/revisions, and publication completeness before updating editor state.

### Atomic publication

- Do not expose partially version-bound products as stable user state.
- Stable Mask publication is atomic.
- Candidate replacement is atomic.
- Progressive View publication is allowed only when each published `AIView` is independently valid and version-bound.
- Late or racing results must never overwrite newer target/context state.

### Evidence semantics

- Missing, unusable, excluded, or unobserved evidence is not automatically negative evidence.
- Evidence Policy remains versioned and benchmark-calibrated.
- Observation Coverage is based on actual contributor evidence over the relevant target/core set, not raw whole-scene Gaussian count.
- View Diversity is distinct from view count.
- Lift Readiness is a derived product state (`Not Ready`, `Limited`, `Ready`) rather than a raw number of generated cameras.
- `Uncertain` is a diagnostic classification and is not included in native Set/Add/Remove/Intersect Candidate membership.

## Explicitly Deferred from v1.0

DG-14 is deferred to the next version. Do not expand v1.0 scope to include:

- user-facing Candidate provenance browser;
- Candidate source-inspection UI;
- Gaussian-level evidence inspector;
- persistent Candidate history browser;
- reopen/restore previous target AI contexts.

Minimal internal revision/fingerprint metadata required for stale detection and correctness is still allowed and required.

## Companion Ownership and Readiness

The Companion is operator-owned.

The browser does not:

- install it;
- start or stop it;
- upgrade or roll it back;
- install model weights;
- automatically discover an endpoint;
- silently substitute an unavailable renderer/model.

Reachability alone is not readiness. Readiness requires compatible endpoint/transport, protocol, renderer, model adapter, Model Manifest/checkpoint, and locked runtime.

Loopback is the default deployment. Trusted-LAN deployment remains explicit, private-network scoped, origin-restricted, and HTTPS-only where required by the browser security model.

Preserve capacity, idempotent admission, cleanup, and compatibility semantics unless an ADR explicitly changes them.

## Locked Runtime

The production Companion runtime is reproducible and exact.

Treat these together as the runtime contract:

- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- relevant source submodule pins
- renderer runtime validation constants
- capability/readiness output
- Companion installation documentation
- GPU/integration fixtures

Do not:

- use floating upstream branches;
- substitute a nearby CUDA/PyTorch build;
- weaken checks to fit the current machine;
- use `thirdparty/sam3/.venv` as the production Companion environment;
- commit model weights or local operator state.

## Change Routing

Determine the authority boundary before editing.

### Editor-only changes

Typical areas:

- CurrentTargetContext lifecycle;
- CameraBinding construction and frustum UI;
- AI View Dock/Gallery state;
- Mask version state and manual editing interaction;
- Candidate presentation;
- Native SelectOp/EditHistory integration;
- Stable ID mapping;
- dependency-token integration with editor mutations.

Preserve upstream SuperSplat behavior outside the requested seam.

### Companion-only changes

Typical areas:

- control-plane validation/readiness;
- gsplat rendering;
- SAM adapter behavior;
- Generated View planning;
- ViewAssessmentPolicy;
- Selection Evidence / Gaussian Lifting;
- runtime caches/capacity/cleanup.

Do not change the editor-facing contract unless the slice requires it.

### Cross-runtime changes

When the editor/Companion contract changes, update the complete affected vertical slice:

1. TypeScript request/response/domain binding types;
2. editor-side runtime validation;
3. browser transport;
4. Python route parsing/validation;
5. Companion state/orchestration;
6. response/artifact construction;
7. TypeScript tests;
8. Python tests;
9. protocol/domain documentation and ADRs when semantics change.

Do not make one side temporarily permissive to compensate for the other.

## Migration Discipline

Prefer tracer-bullet migration over a big-bang rewrite.

Retain and reuse validated foundations where compatible:

- Stable Gaussian ID mapping;
- SceneSnapshot content serialization;
- locked gsplat renderer and same-rasterization contributor path;
- SAM runtime/model adapter;
- Generated View camera/planning primitives that remain policy-compatible;
- Evidence Policy mathematics where it matches the new Included Stable View inputs;
- native `SelectOp` / `EditHistory` integration;
- benchmark fixtures and reproducibility infrastructure.

Reframe or replace superseded product orchestration:

- `ObjectSelectionSession` as the user-visible lifecycle;
- Prompt Log as product source of truth;
- Mask Track as the top-level mask model;
- `New/Add/Remove/Refine` as AI workflow modes;
- PlayCanvas-captured Anchor RGB;
- one-shot Preview → Confirm → Close semantics;
- fixed Correction Round UX;
- whole-scene raw view-count/coverage assumptions.

Do not cherry-pick a large legacy workflow commit wholesale when only a narrow renderer, benchmark, or algorithmic primitive is still valid. Port the compatible slice explicitly.

## Code Conventions

### TypeScript

Follow repository style:

- four-space indentation;
- single quotes;
- semicolons;
- explicit interfaces/discriminated unions for protocol and lifecycle state;
- `readonly` for immutable protocol data;
- type-only imports where appropriate.

At trust boundaries, prefer explicit runtime validation over unchecked casts or `any`.

Copy/freeze externally supplied mutable data before retaining it.

Keep lifecycle transitions explicit. Use the shared `CommandQueue` for work ordered with GPU readbacks or edit-history mutations. Route history-changing selection operations through `EditHistory`. Put user-visible text through localization.

Do not perform unrelated TypeScript strictness migrations.

### Python

Follow versions/dependency sources declared by the Companion project.

Use four-space indentation, type annotations, focused validation helpers, immutable dataclasses for registered/published records where appropriate, `snake_case` internally, and established `camelCase` protocol fields.

Use atomic replacement for persistent operator state. Keep locks narrowly scoped and do not hold state locks across expensive GPU/render/model inference work.

Keep invalid request, incompatibility, unavailable runtime, missing model, capacity, cancellation, and inference errors distinguishable.

### Documentation and comments

Comments should explain authority, ownership, trust boundaries, protocol identity, atomicity, and non-obvious failure behavior—not narrate straightforward implementation.

Use ADRs for durable architectural trade-offs.

## Commands

### Install

```sh
npm ci
```

Initialize submodules only when required:

```sh
git submodule update --init --recursive
```

Use the Node version declared in `package.json`. Use the Python and dependency versions declared by the Companion project.

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

`npm test` is the integrated repository test entry point. Use narrow checks while iterating, then the broader checks required by the affected boundary.

### Companion-only tests

```sh
npm run test:companion
```

### Locked renderer / SAM3 environment

For renderer, CUDA, Generated View, Evidence/Lifting, or SAM3 work, follow the locked installation/validation procedure in:

```text
selection-service-companion/README.md
```

Do not claim production renderer validation from an unverified or approximate environment.

## Validation Matrix

### Documentation-only changes

Check:

- terminology against `CONTEXT.md`;
- compatibility with Final Spec v1.0 and ADR 0012;
- compatibility with any relevant non-superseded ADR;
- executable commands/schemas/examples when documentation changed them.

### TypeScript domain/lifecycle changes

Run:

```sh
npm test
npm run lint
```

Cover affected lifecycle transitions, including restart, stale-response discard, mask publication, Candidate stale state, suspension/restoration, cancellation, cleanup, and retry as applicable.

### Transport/protocol changes

Run:

```sh
npm test
npm run lint
npm run build
```

Test applicable malformed input, missing/duplicate IDs, binding mismatch, stale `targetContextId`/revision/dependency token, Scene Snapshot cache misses, incomplete/partial publication, cancellation races, and idempotent retries.

### UI changes

Run:

```sh
npm run lint
npm run lint:locales
npm run build
```

Also render and inspect the affected UI. Exercise applicable states such as Companion unavailable/incompatible, Anchor rendering, Mask editing vs stable state, Review/Excluded, progressive Generated Views, Candidate Ready/Stale/Applied, Restart Current Target, Suspended context, Undo recovery, and native selection tool interoperability.

### Companion changes

Run:

```sh
npm run test:companion
```

Also run `npm test` when the editor-facing contract is affected.

### Renderer, SAM3, Generated View, assessment, or evidence/lifting changes

Use the exact locked runtime and required GPU.

Validate applicable behavior including:

- runtime identity;
- camera/convention binding;
- authoritative gsplat RGB;
- complete same-rasterization contributor attribution;
- contributor mass conservation;
- Anchor parity where still applicable;
- Generated View planning/preflight;
- evidence-backed View Assessment;
- cancellation/stale-result handling;
- measured out-of-memory behavior.

A mocked, reference-adapter, CPU-only, or structurally validated path does not establish production GPU correctness.

### Dependency/submodule changes

Verify lockfile consistency, pinned source identity, clean installation, capability output, Model Manifest/license metadata where applicable, and affected CPU/GPU tests.

## Project-Specific Completion Evidence

In addition to global reporting requirements, state:

- whether the change affected editor, Companion, protocol, or multiple layers;
- which validation path ran;
- whether production GPU validation actually ran;
- whether Final Spec, ADR, runtime lock, protocol version, Evidence/Assessment policy, or calibration changed;
- which legacy path, if any, was retired or still remains;
- any project-specific invariant still unverified.

Do not describe a mocked, partial, reference-only, or unverified GPU path as production-complete.

@.codex/codebase-memory-mcp.md

@.codex/RTK.md
