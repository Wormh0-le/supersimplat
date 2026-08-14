# Selection Service Companion and Python

Read this file for Selection Service Companion, Python, runtime ownership, installation, readiness, capacity, or model/runtime changes.

## Operator-owned runtime

The Companion is operator-owned. The browser does not install, start, stop, upgrade, discover, or silently substitute the Companion or its model weights. The browser connects only to an explicitly configured loopback or trusted-LAN endpoint.

Do not expand the Companion into a public backend, multi-user platform, reconstruction pipeline, or persistent semantic-object database without an explicit architectural decision.

Reachability alone is not readiness. Readiness requires compatible transport, protocol, renderer, Evidence implementation and policy, model adapter and checkpoint, Model Manifest, and locked runtime.

The runtime contract includes:

- `selection-service-companion/pyproject.toml`;
- `selection-service-companion/uv.lock`;
- relevant submodule and source pins;
- renderer and Evidence runtime validation constants;
- capability and readiness output;
- installation documentation;
- GPU and integration fixtures.

Use pinned upstream sources and the exact declared CUDA/PyTorch environment. Runtime checks must fail closed rather than being weakened to fit the current machine. `thirdparty/sam3/.venv` is not the production Companion environment. Model weights and operator-local state are never committed.

A reference or autograd implementation must be identified as such; it is not the production same-decision path.

## Python conventions

- Use the Python and dependency versions declared by the Companion project.
- Use four-space indentation, type annotations, focused validation helpers, and immutable dataclasses for registered or published records where appropriate.
- Use `snake_case` internally and established `camelCase` protocol fields.
- Replace operator state atomically.
- Keep locks narrowly scoped and release state locks before expensive GPU, render, or model work.
- Keep invalid request, incompatibility, unavailable runtime, missing model, capacity, cancellation, render, Evidence, and Lift failures distinguishable.

For renderer, Evidence, or GPU work, also read [Renderer and Evidence](renderer-and-evidence.md). For contract changes, follow [Architecture and change routing](architecture.md).
