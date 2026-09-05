# SuperSimPlat Project Contract

SuperSimPlat extends the upstream SuperSplat browser editor with AI Select, an object-aware 3D Gaussian selection workflow split between the browser and an operator-run Selection Service Companion.

This file adds repository-specific constraints to the global operating contract. Keep general execution, authorization, reasoning, and test-authoring policy in the global guidance.

## AI Select work

Read [Domain authority](docs/agents/domain.md) before changing AI Select behavior or planning. Issue #37 owns the current product contract and rolling queue. Its accepted simplification supersedes the old blanket v2 stage graph; archived tickets are not executable merely because their retained body says ready. Documentation maintenance, investigation, and other authorized work do not require a new implementation ticket.

## Guidance

Resolve these links from the repository root. Read the guides matching the affected scope; a task may cross several branches.

- [Domain authority](docs/agents/domain.md) — behavior, terminology, specification, scope, or implementation eligibility.
- [Lifecycle and protocol](docs/agents/lifecycle-and-protocol.md) — observations, acquisition, cancellation, staleness, or Candidate publication/application.
- [Architecture](docs/agents/architecture.md) — runtime ownership, cross-runtime contracts, repository seams, or migration.
- [Code discovery](docs/agents/code-discovery.md) — ownership or impact that direct inspection cannot establish.
- [Editor and TypeScript](docs/agents/editor-typescript.md) — browser state, UI, transport validation, or native integration.
- [Companion and Python](docs/agents/companion-python.md) — service runtime, capacity, models, dependencies, or Python.
- [Renderer and Evidence](docs/agents/renderer-and-evidence.md) — gsplat, CUDA, authoritative RGB, P/N/V, working sets, or lifting.
- [Project verification](docs/agents/execution-and-verification.md) — choosing checks and making validation claims.
- [Documentation and traceability](docs/agents/documentation.md) — guidance, glossary, Issue authority, or historical records.
- [Chinese product and technical writing](docs/agents/chinese-writing.md) — Chinese UI copy, documentation, or issue/PR prose.
- [GitHub workflow](docs/agents/issue-tracker.md) — issues, labels, claims, or roadmap operations.
