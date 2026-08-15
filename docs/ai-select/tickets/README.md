# AI Select Ticket Contracts

This directory is the durable Ticket control plane for AI Select v1.

- Parent Ticket count remains 31 as tracked by `../manifest.json`.
- `14A`–`14D` are execution stages under parent Ticket 14; `16A` is the post-closure presentation stage under parent Ticket 16. They do not create a separate normative product graph.
- Final Spec v1.3 remains the top authority.

Current implemented chain and frontier:

```text
14A → 14B → 14C → 14D → 13 → 15 → 16 → 16A (current) → 17
```

14A through 14D, parent Ticket 14, Tickets 13 through 15 and Ticket 16's
application core are implemented. Ticket 16A is the current execution stage;
Ticket 17 follows it.

Do not add active Ticket contracts under `.scratch/ai-select-v1/issues/`.
