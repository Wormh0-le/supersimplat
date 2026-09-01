# Agent Guidance Structure

The root `AGENTS.md` is a small routing index. Task-specific rules live here so an agent loads only the branch relevant to its work.

## Layout

```text
AGENTS.md
docs/agents/
├── README.md
├── domain.md
├── architecture.md
├── lifecycle-and-protocol.md
├── editor-typescript.md
├── companion-python.md
├── renderer-and-evidence.md
├── execution-and-verification.md
├── documentation.md
├── chinese-writing.md
├── issue-tracker.md
└── triage-labels.md
.codex/
└── codebase-memory-mcp.md
```

## Placement rules

- Keep only the project description, mandatory cross-task commands, and context pointers in root `AGENTS.md`.
- Put a rule in exactly one task-specific file; link across files instead of repeating it.
- Write every root pointer as a trigger: name the kind of task that requires the linked file.
- Prefer repository configuration and `--help` output over copied command catalogs unless the copy records a project-specific constraint.
- Put stable domain vocabulary in root `CONTEXT.md`.
- Put current AI Select v2.0 authority, status, dependencies, decomposition, and readiness in GitHub [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) and its exact child Issues.
- Treat the pre-migration specifications, ADRs, feature documents, tickets, reviews, benchmarks, and `.scratch` records as immutable Git history at merge commit [`504e888`](https://github.com/Wormh0-le/supersimplat/tree/504e8885b87575761dc2e367e520b7dfba46884b), reached through links in #37. Do not restore them as a second current control plane.
- `docs/agents/**` is the only retained `docs/**` subtree. Add a new guidance file only when a distinct task branch cannot be routed clearly to an existing file.
