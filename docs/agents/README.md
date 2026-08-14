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
├── verification.md
├── documentation.md
├── issue-tracker.md
└── triage-labels.md
.codex/
├── codebase-memory-mcp.md
└── RTK.md
```

## Placement rules

- Keep only the project description, mandatory cross-task commands, and context pointers in root `AGENTS.md`.
- Put a rule in exactly one task-specific file; link across files instead of repeating it.
- Write every root pointer as a trigger: name the kind of task that requires the linked file.
- Prefer repository configuration and `--help` output over copied command catalogs unless the copy records a project-specific constraint.
- Put stable domain vocabulary in `CONTEXT.md`, durable decisions in `docs/adr/`, and current product requirements in the Final Spec.
- Add a new guidance file only when a distinct task branch cannot be routed clearly to an existing file.
