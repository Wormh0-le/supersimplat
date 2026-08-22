# Project Commands and Verification

Read this file for project commands, validation scope, builds, GPU evidence, or completion claims. Apply the global test-authoring policy; this file adds only SuperSimPlat-specific checks.

## Commands

Install browser dependencies:

```sh
rtk npm ci
```

Initialize submodules only when affected work requires them:

```sh
rtk git submodule update --init --recursive
```

Run the development server with `rtk npm run develop`, then open `http://localhost:3000`. Disable browser network and service-worker caching when manually validating rebuilt frontend code.

Available repository gates are:

```sh
rtk npm run lint
rtk npm run lint:locales
rtk npm test
rtk npm run build
rtk npm run test:companion
```

`rtk npm test` is the repository-level TypeScript typecheck/test gate and includes Companion tests. Use runner-supported targeting when available; do not invent unsupported scripts. For renderer, CUDA, Generated View, Evidence/Lifting, or SAM work, use the locked environment documented in `selection-service-companion/README.md`.

## Choose validation by affected seam

The following paths are alternatives unless a change spans multiple seams; they are not a cumulative checklist for every edit.

- **Documentation:** validate affected terminology, links, commands, mapping, and traceability. Do not run code suites for content-only changes unless executable behavior or generated artifacts changed.
- **Browser TypeScript:** run the nearest existing check that exercises the changed state or boundary. Use repository-level `rtk npm test` for broad type/domain/protocol changes or when repository-level confidence is required.
- **Transport/protocol:** exercise both TypeScript and Python validation for the changed contract, including malformed input and applicable identity, replay, cancellation, or stale-result cases. Build when bundling or serialized browser behavior is affected.
- **UI/localization:** run lint/locales/build only as relevant, then inspect the affected user-visible states in the browser. Do not replay every lifecycle state for a local visual change.
- **Companion:** use targeted Python tests where supported; use `rtk npm run test:companion` for broader Companion confidence. Run `rtk npm test` when editor-facing contracts also changed.
- **Dependencies/submodules:** verify affected lockfiles, source pins, clean installation, capability output, model/license metadata, build identity, and relevant CPU/GPU paths.

## Renderer and GPU evidence

Production renderer, Generated-View, assessment, or Evidence/Lifting claims require the declared locked runtime and required GPU. Validate only applicable risks, such as:

- runtime/build/source and CameraBinding identity;
- authoritative RGB and readiness separation;
- full/reference render parity and Stable ID mapping;
- P/N/V reference correctness and same-decision semantics;
- mixed, boundary, and unobserved classification;
- per-view invalidation, aggregation, cancellation, and stale-result rejection;
- repeat-run classification stability;
- measured latency, VRAM, capacity, and OOM behavior;
- atomic publication and preservation of the prior Candidate after failure.

Mocked, CPU-only, autograd/reference, or structural validation does not establish production GPU correctness.

## Completion claims

In addition to the global change report, state when material:

- which runtime or contract seam changed;
- whether production GPU validation actually ran;
- whether current spec, ADR, runtime lock, protocol, policy, or calibration changed;
- whether the result is a reference PoC, production same-decision path, or debug backend change;
- which project invariant remains unverified.

Never describe mocked, partial, approximate, reference-only, or unverified GPU work as production-complete.
