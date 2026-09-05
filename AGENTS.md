# SuperSimPlat Project Contract

SuperSimPlat extends the upstream SuperSplat browser editor with AI Select, an object-aware 3D Gaussian selection workflow split between the browser and an operator-run Selection Service Companion.

This file adds repository-specific constraints to the global operating contract. Keep general execution, authorization, reasoning, and test-authoring policy in the global guidance.

## AI Select v2.0 implementation

Before implementing a v2 stage, read [Domain authority](docs/agents/domain.md) for the current Issue authority and implementation gate. Parent capability maps are not implementation units. This gate applies to v2 implementation; documentation maintenance, investigation, and other authorized work do not require a new v2 child Issue.

## Guidance

Resolve these links from the repository root. Read the guides matching the affected scope; a task may cross several branches.

- [Domain authority](docs/agents/domain.md) — AI Select behavior, terminology, specification, or scope.
- [Lifecycle and protocol](docs/agents/lifecycle-and-protocol.md) — observation/Mask state, acquisition, identity, replay, suspension, staleness, or Candidate publication/application.
- [Architecture](docs/agents/architecture.md) — runtime ownership, repository seams, cross-runtime contracts, vendored code, or migration.
- [Code discovery](docs/agents/code-discovery.md) — ownership, call chains, registrations, or impact that direct inspection cannot establish.
- [Editor and TypeScript](docs/agents/editor-typescript.md) — browser state, UI, transport validation, or native editor integration.
- [Companion and Python](docs/agents/companion-python.md) — service runtime, readiness, capacity, models, dependencies, or Python implementation.
- [Renderer and Evidence](docs/agents/renderer-and-evidence.md) — gsplat, CUDA, authoritative RGB, P/N/V Evidence, working sets, lifting, or reference Contributor.
- [Project verification](docs/agents/execution-and-verification.md) — before choosing checks or making validation claims; includes the integrated `npm test` gate and GPU requirements.
- [Documentation and traceability](docs/agents/documentation.md) — agent guidance, `CONTEXT.md`, Issue authority, historical records, or comments.
- [Chinese product and technical writing](docs/agents/chinese-writing.md) — Chinese UI copy, product documentation, release notes, runbooks, or issue/PR prose.
- [GitHub workflow](docs/agents/issue-tracker.md) — issues, triage labels, PR identification, or Wayfinder operations.
