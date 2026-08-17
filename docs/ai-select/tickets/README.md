# AI Select Ticket Contracts

This directory is the durable Ticket control plane for AI Select v1.

- Parent Ticket count remains 31 as tracked by `../manifest.json`.
- `14A`–`14D` are execution stages under parent Ticket 14. `16A` is the
  implemented post-closure presentation baseline under parent Ticket 16, and
  `16B`–`16G` are its operator-visual-review follow-up stages. They do not
  create a separate normative product graph or increase the parent Ticket
  count.
- Final Spec v1.3 remains the top authority.
- Completed Tickets retain historical implementation evidence. Their
  user-facing Retry/Generate More/Regenerate/Stop/3D Restart controls and the
  universal "automatic result becomes Editing" wording are superseded where
  Tickets 16B–16G and 17 state the accepted current product contract; retained
  attempt/replay, planner protocol and automatic Generated-View publication
  infrastructure is not removed by that supersession.

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
                                      16G → 17 → 18 → 19 → 20 → 21
```

14A through 14D, parent Ticket 14, Tickets 13 through 15, Ticket 16's
application core and Tickets 16A–16G are implemented. The 16A operator visual
walkthrough is complete and produced the accepted follow-up contracts in
16B–16G. Tickets 17–20 are implemented and Ticket 21 is the current execution
frontier.

Do not add active Ticket contracts under `.scratch/ai-select-v1/issues/`.
