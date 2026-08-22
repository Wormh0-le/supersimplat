# Selection Service Companion and Python

Read this file for Companion runtime, readiness, capacity, models, dependencies, installation, or Python implementation.

## Operator-owned runtime

The Companion is operator-owned. The browser does not install, start, stop, upgrade, discover, or silently substitute the service or its model weights. It connects only to an explicitly configured loopback or trusted-LAN endpoint.

Do not expand the Companion into a public backend, multi-user platform, reconstruction pipeline, or persistent semantic-object database without an architectural decision.

Reachability is not readiness. Readiness requires compatible transport, protocol, renderer, Evidence implementation/policy, model adapter/checkpoint, Model Manifest, and locked runtime.

The runtime authority is the Companion's `pyproject.toml`, `uv.lock`, relevant source/submodule pins, validation constants, capability/readiness output, installation documentation, and GPU fixtures. Use the declared CUDA/PyTorch environment. Fail closed on incompatibility rather than weakening checks to fit the current machine. `thirdparty/sam3/.venv` is not the production environment. Never commit model weights or operator-local state.

Reference or autograd implementations must remain identified as such; they do not establish production same-decision behavior.

## Python boundaries

- Follow the declared Python version and configured project tooling.
- Use established `camelCase` wire fields and `snake_case` internally.
- Keep validation helpers focused and published/registered records immutable where practical.
- Replace operator state atomically.
- Keep locks narrow; release state locks before expensive GPU, rendering, or model work.
- Preserve distinct failure categories for invalid requests, incompatibility, unavailable runtime, missing model, capacity, cancellation, rendering, Evidence, and lifting.

For GPU or renderer work, also read [Renderer and Evidence](renderer-and-evidence.md). For contract changes, follow [Architecture](architecture.md).
