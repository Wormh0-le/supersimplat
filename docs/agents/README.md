# Agent Guidance Structure

The root `AGENTS.md` routes repository-specific guidance. General operating policy belongs in the global contract; task-specific project rules live here.

## Layout

```text
AGENTS.md
docs/agents/
├── README.md
├── domain.md
├── architecture.md
├── code-discovery.md
├── lifecycle-and-protocol.md
├── editor-typescript.md
├── companion-python.md
├── renderer-and-evidence.md
├── execution-and-verification.md
├── documentation.md
├── chinese-writing.md
├── issue-tracker.md
└── triage-labels.md
```

## Placement rules

- Keep the project description, essential scope boundaries, and task triggers in root `AGENTS.md`.
- Keep guidance model-independent. Align with the global contract through project-specific constraints rather than copying its defaults or adding model-specific rituals.
- Put a rule in exactly one task-specific file; link across files instead of repeating it.
- Write every root pointer as a trigger: name the kind of task that requires the linked file.
- Prefer repository configuration and `--help` output over copied command catalogs unless the copy records a project-specific constraint.
- Follow [Documentation and traceability](documentation.md) for artifact ownership and [Domain authority](domain.md) for specification precedence and implementation eligibility. Keep mutable status in the owning Issues.
- `docs/agents/**` is the only retained `docs/**` subtree. Add a new guidance file only when a distinct task branch cannot be routed clearly to an existing file.

When changing guidance, check the affected task routes, local link targets, and consistency with the global contract. Preserve project invariants and distinguish a required gate from workflow advice.
