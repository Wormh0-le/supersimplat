# Project Commands and Verification

Read this file for project commands, validation scope, builds, GPU evidence, or completion claims. Apply the global test-authoring policy; this file adds only SuperSimPlat-specific checks.

## Command authority

Use [`package.json`](../../package.json) for repository scripts and [`selection-service-companion/README.md`](../../selection-service-companion/README.md) for the locked renderer/CUDA/SAM environment and installation procedure.

`npm test` is the integrated TypeScript typecheck and repository test gate, including Companion tests; there is no standalone typecheck script. Use runner-supported targeting when available. Install dependencies or initialize submodules only when affected work requires them. Disable browser network and service-worker caching when manually validating rebuilt frontend code.

### CPU CI prerequisites

The base Companion package intentionally has no dependencies. The full test suite nevertheless exercises CPU tensor, binary snapshot, image, and spatial validation paths that require the existing locked `renderer` extra (including torch, NumPy, and Pillow). A fresh base-only environment is not a valid full-suite test environment.

On a CPU-only CI/development host, reproduce the workflow from the repository root:

```sh
npm ci
BUILD_NO_CUDA=1 uv sync --project selection-service-companion --locked --python 3.12.12 --extra renderer
npm test
```

`BUILD_NO_CUDA=1` applies only to installation on that CPU host: it defers gsplat extension compilation, without changing the pinned source, torch wheel, or `uv.lock`. It does not make a CPU run a renderer qualification. Do not carry this CPU setup over as the operator's GPU installation procedure; use the Companion README for that procedure. Keep GPU/model prerequisites and existing optional skips explicit; never skip an applicable required GPU test to turn a qualification green.

The CI workflow records the actual checkout SHA (the merge SHA for a PR), head/base identities, lock hashes, installed Python packages, raw integrated test output, and exit code in its `cpu-test-*` artifact. Read that artifact when a log summary disagrees with the checked-out source. A missing exit-code file means the Test step did not finish or was not reached, not that it passed. Test failures remain failures through `pipefail`; Build and Lint/locales are separate jobs. Do not claim branch protection or locked-GPU success from these CPU checks.

## Choose validation by affected seam

The following paths are alternatives unless a change spans multiple seams; they are not a cumulative checklist for every edit.

- **Documentation/Issues:** validate affected terminology, immutable snapshot links, Issue bodies/comments, dependencies, labels, commands, and acceptance evidence. Do not run code suites for content-only changes unless executable behavior or generated artifacts changed.
- **Browser TypeScript:** run the nearest existing check that exercises the changed state or boundary. Use repository-level `npm test` for broad type/domain/protocol changes or when repository-level confidence is required.
- **Transport/protocol:** exercise both TypeScript and Python validation for the changed contract, including malformed input and applicable identity, replay, cancellation, or stale-result cases. Build when bundling or serialized browser behavior is affected.
- **UI/localization:** run lint/locales/build only as relevant, then inspect the affected user-visible states in the browser. Do not replay every lifecycle state for a local visual change.
- **Companion:** use targeted Python tests where supported; use `npm run test:companion` for broader Companion confidence. Run `npm test` when editor-facing contracts also changed.
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
- which exact child Issue authorized the work and whether its acceptance criteria are satisfied;
- whether production GPU validation actually ran;
- whether runtime lock, protocol, policy, calibration, production identity, or current Issue authority changed;
- whether the result is a reference PoC, shadow/experimental path, production same-decision path, or debug backend change;
- which project invariant remains unverified.

Never describe mocked, partial, approximate, reference-only, shadow-only, or unverified GPU work as production-complete.
