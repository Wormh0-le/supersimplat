# SuperSimPlat Agent Guide

SuperSimPlat extends the upstream SuperSplat browser editor with AI Select for object-aware 3D Gaussian selection.

## Essentials

- Prefix every shell command with `rtk`, including each command in a chain.
- The integrated TypeScript typecheck and repository test entry point is `rtk npm test`; there is no standalone typecheck script.

## Progressive guidance

Read only the guidance relevant to the task:

- **AI Select behavior, terminology, current specification, or legacy semantics:** [Domain and sources of truth](docs/agents/domain.md)
- **Runtime ownership, repository seams, cross-runtime changes, or migration:** [Architecture and change routing](docs/agents/architecture.md)
- **Target lifecycle, Mask or Candidate state, identity, retries, suspension, or native selection:** [Lifecycle and protocol invariants](docs/agents/lifecycle-and-protocol.md)
- **Browser editor or TypeScript implementation:** [Editor and TypeScript](docs/agents/editor-typescript.md)
- **Selection Service Companion or Python implementation:** [Companion and Python](docs/agents/companion-python.md)
- **gsplat, CUDA, P/N/V Evidence, working sets, lifting, or reference Contributor:** [Renderer and Evidence](docs/agents/renderer-and-evidence.md)
- **Tests, builds, validation, or completion reporting:** [Execution and verification](docs/agents/execution-and-verification.md)
- **Comments, domain documentation, ADRs, specs, tickets, or traceability:** [Documentation](docs/agents/documentation.md)
- **Structural code discovery, call chains, dependencies, or impact analysis:** [Codebase Memory](.codex/codebase-memory-mcp.md)
- **RTK command forms or output filtering:** [RTK reference](.codex/RTK.md)
- **GitHub issue operations:** [Issue tracker](docs/agents/issue-tracker.md) and [triage labels](docs/agents/triage-labels.md)

The human-facing layout and maintenance rationale are recorded in [Agent guidance structure](docs/agents/README.md).
