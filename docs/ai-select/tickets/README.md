# AI Select Ticket Contracts

This directory is the durable Ticket control plane for AI Select v1.

- Parent Ticket count remains 31 as tracked by `../manifest.json`.
- `14A`–`14D` are execution stages under parent Ticket 14. `16A` is the
  implemented post-closure presentation baseline under parent Ticket 16, and
  `16B`–`16G` are its operator-visual-review follow-up stages. They do not
  create a separate normative product graph or increase the parent Ticket
  count.
- Final Spec v1.3 remains the top authority.

Current implemented chain and frontier:

```text
14A → 14B → 14C → 14D → 13 → 15 → 16 → 16A
                                             │
                                             ▼
                                            16B
                                  ┌──────────┼──────────┐
                                  ▼          ▼          ▼
                                 16C        16D        16F
                                  └────┬─────┘          │
                                       ▼                │
                                      16E───────────────┘
                                       │
                                       ▼
                                      16G → 17
```

14A through 14D, parent Ticket 14, Tickets 13 through 15, Ticket 16's
application core and Ticket 16A are implemented. The 16A operator visual
walkthrough is complete and produced the accepted follow-up contracts in
16B–16G. Ticket 16B is the current execution stage; Ticket 17 follows 16G.

Do not add active Ticket contracts under `.scratch/ai-select-v1/issues/`.
