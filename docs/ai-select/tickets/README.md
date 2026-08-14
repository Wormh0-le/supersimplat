# AI Select Ticket Contracts

This directory is the durable Ticket control plane for AI Select v1.

- Parent Ticket count remains 31 as tracked by `../manifest.json`.
- `14A`–`14D` are execution stages under parent Ticket 14; they do not create a separate normative product graph.
- Final Spec v1.3 remains the top authority.

Current implemented chain and frontier:

```text
14A → 14B → 14C → 14D → 13 → 15 → 16 → 17 (current)
```

14A through 14D, parent Ticket 14 and Tickets 13 through 16 are implemented.
Ticket 17 is the current execution frontier.

Do not add active Ticket contracts under `.scratch/ai-select-v1/issues/`.
