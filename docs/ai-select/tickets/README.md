# AI Select Ticket Contracts

This directory is the durable Ticket control plane for AI Select v1.

- Parent Ticket count remains 31 as tracked by `../manifest.json`.
- `14A`–`14D` are execution stages under parent Ticket 14; they do not create a separate normative product graph.
- Final Spec v1.3 remains the top authority.

Current execution order:

```text
14A → 14B → 14C → 14D → 13
```

14A is implemented; 14B is the current execution stage.

Do not add active Ticket contracts under `.scratch/ai-select-v1/issues/`.
