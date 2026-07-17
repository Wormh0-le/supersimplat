# SuperSplat Project Contract

## Relationship to the Global Contract

This file extends the global [`AGENTS.md`](http://AGENTS.md).

The global contract already defines:

- reasoning and evidence standards;
- unknown handling;
- generic scope and approval boundaries;
- the Inspect → Protect → Change → Verify → Report loop;
- generic reporting requirements.

Do not restate or weaken those rules here.

This file adds only repository-specific context, invariants, commands, and validation requirements. A closer child [`AGENTS.md`](http://AGENTS.md) may further specialize its subtree.

## Project Purpose

This repository extends the upstream SuperSplat browser editor with object-aware Gaussian editing.

The system deliberately separates two runtimes:

### Browser editor

The TypeScript and PlayCanvas editor owns:

- scene and splat state;
- Stable Gaussian IDs and their mapping to current splat indices;
- user interaction;
- candidate preview presentation;
- edit history;
- final Selection Commit.

### Selection Service Companion

The local Python Companion owns:

- locked gsplat rendering;
- SAM3 inference;
- Generated Views;
- Mask Sets;
- Selection Evidence;
- renderer, model, and runtime readiness.

Preserve this ownership boundary.

Do not turn the Object Selection system into a public backend, multi-user service, reconstruction pipeline, or persistent semantic-object database unless an explicit architectural decision requires it.

## Sources of Truth

Before changing non-trivial behavior, inspect:

1. [`CONTEXT.md`](http://CONTEXT.md)
2. Relevant ADRs under `docs/adr/`
3. The associated GitHub issue and comments, when applicable
4. The nearest implementation and tests
5. Dependency and runtime declarations when the change affects installation or inference

Repository workflow references:

- `docs/agents/[issue-tracker.md](http://issue-tracker.md)`
- `docs/agents/[triage-labels.md](http://triage-labels.md)`
- `docs/agents/[domain.md](http://domain.md)`

Use the domain vocabulary defined in [`CONTEXT.md`](http://CONTEXT.md).

In particular:

- Object Selection is not a generic synonym for “3D segmentation”.
- Gaussian Selection is not a “3D mask”.
- Stable Gaussian ID is not a PLY row, renderer index, draw order, or tensor row.
- Candidate Object Selection is not committed editor selection.
- Generated View is not an original capture image or visible camera movement.
- Selection Commit is the specific handoff into existing editor history.

When changing a durable domain concept, update [`CONTEXT.md`](http://CONTEXT.md).

When contradicting or replacing an architectural decision, update or supersede the relevant ADR rather than silently diverging from it.

## Repository Map

### Editor composition and state

- `src/main.ts`  
Editor composition root, shared command queue, event registration, UI construction, and Companion readiness wiring.
- `src/object-selection-session.ts`  
Object Selection state machine, request identity, candidate validation, cancellation, and commit lifecycle.
- `src/object-selection-session-factory.ts`  
Construction of editor and service dependencies for a session.
- `src/scene-snapshot.ts`  
Immutable Scene Snapshot and Stable Gaussian ID contracts.

### Editor and Companion boundary

- `src/selection-service-fetch-adapter.ts`  
Browser transport, snapshot and Frame Set registration, retries, and response validation.
- `src/selection-service-readiness.ts`
- `src/selection-service-fetch-readiness-probe.ts`
- `src/selection-service-readiness-events.ts`  
Configuration and readiness gating.

### UI and existing editor behavior

- `src/ui/object-selection-*`
- `src/selection.ts`
- `src/edit-history.ts`
- `src/edit-ops.ts`
- `src/tools/`

Existing SuperSplat selection and edit-history behavior remains authoritative outside the Object Selection inference seam.

### Companion

- `selection-service-companion/src/selection_service_companion/`  
Control plane, runtime verification, rendering, masking, Generated Views, evidence, and session state.
- `selection-service-companion/tests/`  
Companion protocol and behavior tests.
- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- `selection-service-companion/[README.md](http://README.md)`  
Locked runtime and operator installation sources of truth.

### External sources

- `thirdparty/sam3`
- `thirdparty/gsplat`
- `thirdparty/splat_analyzer`

Treat `thirdparty/` directories as pinned upstream sources, not ordinary project code.

## Project Invariants

### Stable identity

- The editor owns Stable Gaussian IDs.
- Stable IDs remain stable within one immutable Target Splat content version.
- File order, renderer order, draw order, and service tensor order do not cross the protocol boundary as identity.
- Stable Gaussian IDs crossing the boundary are unique unsigned 32-bit integers.
- One Object Selection Session targets exactly one Target Splat.

### Editor authority

- Candidate Object Selection is transient.
- Preview updates do not create editor history operations.
- Selection Commit is the only operation that applies candidate Stable Gaussian IDs to editor selection.
- Selection Commit uses the existing `SelectOp` and `EditHistory` path.
- One commit creates one editor history operation.
- Cancel restores the entry Gaussian Selection without creating history.
- Existing delete, duplicate, separate, undo, and redo behavior remains editor-owned.
- Rejected and uncertain Gaussians are excluded from Selection Commit.
- Locked and deleted Gaussians are not modified.
- Evaluate current mutable state immediately before publication and commit rather than embedding it permanently in a Scene Snapshot.

### Atomic preview publication

A usable preview is published only when all required results are complete and mutually version-bound:

- Frame Set
- Mask Set
- Coverage Report
- Evidence Snapshot
- selected, rejected, and uncertain Stable Gaussian IDs

Partial output must not replace the previous usable candidate.

Stale, cancelled, mismatched, or racing responses must not update editor state.

A successful preview atomically replaces the preceding Candidate Object Selection.

Generated Views must not move the visible editor camera.

### Immutable protocol bindings

A Scene Snapshot is immutable for its `(sceneId, sceneVersion)` identity.

Requests, cached artifacts, and terminal responses must preserve the applicable identity tuple, including:

- session ID;
- request ID;
- Target Splat ID;
- scene ID and version;
- operation;
- correction round;
- deterministic seed;
- Prompt Log revision;
- Frame Set version;
- render-configuration version;
- Model Manifest digest.

Treat all transport responses as untrusted data.

Validate structure, identity, finite numeric values, and complete classifications before updating editor state.

Do not infer undeclared conversions for:

- coordinates;
- quaternion order;
- camera convention;
- alpha semantics;
- background composition;
- spherical harmonics;
- rasterizer behavior.

Unsupported semantics fail compatibility checks rather than selecting an approximate fallback.

### Evidence semantics

Missing, rejected, or unusable observation remains unobserved. It is not automatically negative evidence.

Contributor attribution must remain tied to the same rasterization that produced service RGB and alpha.

Do not replace complete contributor support with:

- nearest-Gaussian attribution;
- visible-only attribution;
- top-k truncation;
- unrelated screen-space approximations.

Changes to any of the following require an explicit policy or render-configuration revision:

- contributor semantics;
- Evidence Policy thresholds;
- observation requirements;
- Generated View quality gates;
- Anchor parity thresholds;
- renderer appearance behavior.

Update the affected contract tests, calibration fixtures, documentation, and ADRs with the revision.

### Companion ownership and readiness

The Companion is operator-owned.

The browser does not:

- install it;
- start or stop it;
- upgrade or roll it back;
- install model weights;
- automatically discover an endpoint;
- silently substitute an unavailable renderer or model.

Reachability alone is not readiness.

Readiness requires compatible:

- endpoint and transport;
- protocol;
- renderer;
- model adapter;
- Model Manifest;
- checkpoint;
- locked runtime.

Every Object Selection Session passes through the readiness gate.

Loopback is the default deployment.

Trusted-LAN deployment remains explicit, private-network scoped, origin-restricted, and HTTPS-only.

Preserve the configured session-capacity and idempotent admission and cleanup semantics unless an ADR changes them.

### Locked runtime

The production Companion runtime is reproducible and exact.

Treat these files together as the runtime contract:

- `selection-service-companion/pyproject.toml`
- `selection-service-companion/uv.lock`
- relevant source submodule pins
- renderer runtime validation constants
- capability and readiness output
- Companion installation documentation
- GPU and integration fixtures

When changing a runtime dependency or source pin, update every affected part of that contract together.

Do not:

- use floating upstream branches;
- substitute a nearby CUDA or PyTorch build;
- weaken runtime checks to match the current machine;
- use `thirdparty/sam3/.venv` as the production Companion environment;
- commit model weights or local operator state.

## Change Routing

Determine which boundary the requested behavior crosses before editing.

### Editor-only changes

Typical areas:

- UI presentation;
- state-machine behavior;
- editor-side validation;
- history integration;
- Stable ID mapping.

Preserve existing SuperSplat behavior outside the requested seam.

### Companion-only changes

Typical areas:

- control-plane validation;
- runtime readiness;
- rendering;
- SAM3 adapter behavior;
- Generated View planning;
- evidence construction;
- capacity and cleanup state.

Do not change the editor-facing contract unless the task requires it.

### Cross-runtime changes

When the editor/Companion contract changes, update the complete affected vertical slice:

1. TypeScript request and response types
2. Editor-side validation
3. Browser transport
4. Python route parsing and validation
5. Companion state or orchestration
6. Response construction
7. TypeScript tests
8. Python tests
9. Protocol documentation, glossary, or ADRs when semantics changed

Do not make one side temporarily permissive to compensate for an inconsistent other side.

## Code Conventions

### TypeScript

Follow the existing repository style:

- four-space indentation;
- single quotes;
- semicolons;
- explicit interfaces and discriminated unions for protocol and lifecycle state;
- `readonly` for immutable protocol data;
- type-only imports where appropriate.

At trust boundaries, prefer explicit runtime validation over unchecked casts or `any`.

Copy or freeze externally supplied mutable data before retaining it.

Keep Object Selection state transitions explicit.

Use the shared `CommandQueue` for work ordered with GPU readbacks or edit-history mutations.

Route history-changing selection operations through `EditHistory`.

Put user-visible text through localization.

Do not perform an unrelated TypeScript strictness migration.

### Python

Follow the versions and dependency sources declared by the Companion project.

Use:

- four-space indentation;
- type annotations;
- focused validation helpers;
- immutable dataclasses for registered or published records where appropriate;
- `snake_case` internally;
- established `camelCase` protocol fields.

Use atomic file replacement for persistent operator state.

Keep locks scoped to the state they protect.

Do not hold state locks across expensive GPU, rendering, or model-inference work.

Keep invalid request, incompatibility, unavailable runtime, missing model, capacity, cancellation, and inference errors distinguishable.

### Documentation and comments

Comments should explain:

- authority and ownership;
- trust boundaries;
- protocol identity;
- atomicity;
- non-obvious failure behavior.

Do not narrate straightforward implementation.

Use an ADR for durable architectural trade-offs.

## Commands

### Install

```sh
npm ci

```

Initialize submodules only when required by the task:

```sh
git submodule update --init --recursive

```

Use the Node version declared in `package.json`.

Use the Python and dependency versions declared by the Companion project. Do not improvise substitutes.

### Development server

```sh
npm run develop

```

Open:

```text
http://localhost:3000

```

Disable browser network and service-worker caching when manually validating rebuilt frontend code.

### Standard checks

```sh
npm run lint
npm run lint:locales
npm test
npm run build

```

`npm test` is the integrated repository test entry point.

Use the narrowest relevant check while iterating, then run the broader checks required by the affected boundary.

### Companion-only tests

```sh
npm run test:companion

```

### Locked renderer and SAM3 environment

For renderer, CUDA, Generated View, evidence, or SAM3 work, follow the locked installation procedure in:

```text
selection-service-companion/README.md

```

Do not claim production renderer validation from an unverified or approximate environment.

## Validation Matrix

### Documentation-only changes

Check:

- terminology against [`CONTEXT.md`](http://CONTEXT.md);
- compatibility with relevant ADRs;
- commands, schemas, and examples when executable documentation changed.

### TypeScript domain or lifecycle changes

Run:

```sh
npm test
npm run lint

```

Cover affected state transitions, including relevant failure, cancellation, stale-response, cleanup, and retry cases.

### Transport or protocol changes

Run:

```sh
npm test
npm run lint
npm run build

```

Test applicable cases such as:

- malformed input;
- missing or duplicate IDs;
- identity-binding mismatches;
- Scene Snapshot cache misses;
- incomplete publication;
- cancellation races;
- idempotent retries.

### UI changes

Run:

```sh
npm run lint
npm run lint:locales
npm run build

```

Also render and inspect the affected UI.

Exercise applicable states:

- Companion unavailable;
- Companion incompatible;
- session opening;
- previewing;
- preview replacement;
- cancellation;
- confirmation;
- cleanup failure;
- undo.

Check that existing SuperSplat selection tools still behave correctly when the change can affect them.

### Companion changes

Run:

```sh
npm run test:companion

```

Also run `npm test` when the editor-facing contract is affected.

### Renderer, SAM3, Generated View, or evidence changes

Use the exact locked runtime and required GPU.

Validate the affected behavior and applicable fixtures, including:

- runtime identity;
- deterministic protocol bindings;
- atomic publication;
- complete contributor attribution;
- contributor mass conservation;
- Anchor parity;
- Generated View acceptance and rejection;
- cancellation;
- measured out-of-memory behavior.

A mocked, reference-adapter, CPU-only, or structurally validated path does not establish that the production GPU path works.

### Dependency or submodule changes

Verify:

- lockfile consistency;
- pinned source identity;
- clean installation;
- runtime capability reporting;
- Model Manifest and license metadata where applicable;
- affected CPU and GPU tests.

## Project-Specific Completion Evidence

In addition to the global reporting requirements, state:

- whether the change affected the editor, Companion, protocol, or multiple layers;
- which validation path was run;
- whether production GPU validation was actually performed;
- whether an ADR, runtime lock, protocol version, or calibration policy changed;
- any project-specific invariant that remains unverified.

Do not describe a mocked, partial, reference-only, or unverified GPU path as production-complete.

@.codex/codebase-memory-mcp.md

@.codex/RTK.md