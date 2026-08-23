# SuperSimPlat Agent Guide

SuperSimPlat extends the upstream SuperSplat browser editor with AI Select, an object-aware 3D Gaussian selection workflow split between the browser and an operator-run Selection Service Companion.

## Essentials

- Prefix every agent-run external shell command with `rtk`, including each command in a chain.
- `rtk npm test` is the integrated TypeScript typecheck and repository test entry point, including Companion tests; there is no standalone typecheck script.
- Before implementing any Final Spec v2.0 ticket, read `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md` and `docs/ai-select/V2-REVIEW-STATUS.md`. A V2 ticket is not agent-ready unless both documents explicitly say so.

## Progressive guidance

Read only the branch relevant to the task:

- [Domain authority](docs/agents/domain.md) — AI Select behavior, terminology, current specification, product scope, or legacy semantics.
- [Lifecycle and protocol](docs/agents/lifecycle-and-protocol.md) — target, View, Mask, Evidence, Candidate, acquisition-loop, identity, retry, suspension, or native-selection behavior.
- [Architecture](docs/agents/architecture.md) — runtime ownership, repository seams, cross-runtime contracts, vendored code, or migration.
- [Code discovery](docs/agents/code-discovery.md) — non-trivial symbol ownership, call chains, registration paths, dependencies, or impact analysis.
- [Editor and TypeScript](docs/agents/editor-typescript.md) — browser state, UI, transport validation, or native editor integration.
- [Companion and Python](docs/agents/companion-python.md) — service runtime, readiness, capacity, models, dependencies, or Python implementation.
- [Renderer and Evidence](docs/agents/renderer-and-evidence.md) — gsplat, CUDA, authoritative RGB, P/N/V Evidence, working sets, lifting, or reference Contributor.
- [Project verification](docs/agents/execution-and-verification.md) — project commands, validation scope, builds, GPU evidence, or completion claims.
- [Documentation and traceability](docs/agents/documentation.md) — `CONTEXT.md`, specs, ADRs, feature documents, tickets, comments, or traceability.
- [Chinese product and technical writing](docs/agents/chinese-writing.md) — Chinese UI copy, product documentation, release notes, runbooks, or issue/PR prose.
- [GitHub workflow](docs/agents/issue-tracker.md) — issues, triage labels, PR identification, or Wayfinder operations.
