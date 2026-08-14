# Verification

Read this file for installation, development, testing, builds, validation scope, or completion reporting. Prefix every shell command with `rtk`.

## Commands

Install browser dependencies:

```sh
rtk npm ci
```

Initialize submodules only when the affected work requires them:

```sh
rtk git submodule update --init --recursive
```

Use the Node version declared in `package.json` and the Python/dependency versions declared by the Companion project.

Run the development server:

```sh
rtk npm run develop
```

Open `http://localhost:3000`. Disable browser network and service-worker caching when manually validating rebuilt frontend code.

The standard repository checks are:

```sh
rtk npm run lint
rtk npm run lint:locales
rtk npm test
rtk npm run build
```

`rtk npm test` is the integrated TypeScript typecheck and repository test entry point; it also runs Companion tests. There is no separate typecheck script.

Run Companion tests directly with:

```sh
rtk npm run test:companion
```

For renderer, CUDA, Generated View, Evidence/Lifting, or SAM work, use the locked environment documented in `selection-service-companion/README.md`.

## Validation matrix

### Documentation-only changes

Follow the documentation checks in [Documentation, ADRs, and Traceability](documentation.md). A link and Markdown consistency check is sufficient when content semantics and commands did not change.

### TypeScript domain or lifecycle changes

Run:

```sh
rtk npm test
rtk npm run lint
```

Cover applicable transitions including restart, stale-response discard, true Retry attempts, Mask publication, Evidence dirty or failed state, Candidate stale state, suspension and restoration, cancellation, and cleanup.

### Transport or protocol changes

Run:

```sh
rtk npm test
rtk npm run lint
rtk npm run build
```

Test malformed input, missing or duplicate IDs, binding mismatch, stale target/revision/dependency identity, stale Camera/RGB/Mask/Policy/Working-Set identity, Scene Snapshot or chunk misses, incomplete publication, cancellation races, and idempotent replay versus new-attempt Retry.

### UI changes

Run:

```sh
rtk npm run lint
rtk npm run lint:locales
rtk npm run build
```

Render and inspect affected states, including Companion unavailable or incompatible, RGB rendering, RGB Ready without Mask or Evidence, Editing versus Stable Mask, Evidence failed or stale, Review or Excluded, progressive Views, Candidate Ready/Stale/Applied, Restart, Suspended, Undo recovery, and native tool interoperability.

### Companion changes

Run:

```sh
rtk npm run test:companion
```

Also run `rtk npm test` when editor-facing contracts are affected.

### Renderer, Generated View, assessment, or Evidence/Lifting changes

Use the exact locked runtime and required GPU. Validate applicable behavior including:

- runtime, build, and source identity;
- CameraBinding and coordinate convention;
- authoritative gsplat RGB;
- RGB readiness independent from reference Contributor or Evidence failure;
- true same-CameraBinding new-attempt Retry;
- Render Working Set full-reference parity;
- Evidence Working Set Stable ID mapping;
- P/N/V reference correctness;
- same-decision production Evidence semantics;
- complete Contributor reference equivalence where applicable;
- mixed, boundary, and unobserved classification;
- multi-view aggregation and per-view invalidation;
- repeat-run classification stability under atomic accumulation;
- Generated-View planning and preflight;
- evidence-backed View Assessment;
- cancellation and stale-result handling;
- measured latency, VRAM, and OOM behavior;
- atomic publication and preservation of the previous Candidate after failure.

A mocked, CPU-only, autograd/reference, or structurally validated path does not establish production GPU correctness.

### Dependency or submodule changes

Verify lockfile consistency, pinned source identity, clean installation, capability output, model and license metadata, CUDA build identity, and affected CPU/GPU tests.

## Completion evidence

Report:

- whether the change affected editor, Companion, protocol, docs/issues, or multiple layers;
- which validation path ran;
- whether production GPU validation actually ran;
- whether Final Spec, ADR, runtime lock, protocol, Evidence/Assessment policy, or calibration changed;
- whether the result is a reference PoC, production same-decision path, or debug backend change;
- which legacy/reference path remains or was retired;
- every project invariant still unverified.

Never describe mocked, partial, reference-only, approximate, or unverified GPU work as production-complete.
