# AI Select v2 Ticket Envelopes

Status: **pre-implementation review; no ticket is agent-ready**

Current parent capability envelopes:

- [V2A — projected depth, CWED moments, and depth-Evidence experiment](V2A-depth-moments-and-depth-evidence-experiment.md)
- [V2B — Conservative Seed, Core Target, and Discovery Frontier](V2B-conservative-seed-discovery-frontier.md)
- [V2C — q+s Provisional Consensus and canonical bounded solve](V2C-provisional-consensus-softmask-readout.md)
- [V2D — lagged Observation Reliability](V2D-observation-reliability.md)
- [V2E — weighted aggregation, q/s update, and two-phase scope revision](V2E-weighted-aggregation-revision.md)
- [V2F — View Utility, exploration, and candidate pool](V2F-view-utility-layered-candidate-pool.md)
- [V2G — budgets/failure/termination](V2G-budgets-failure-termination.md)
- [V2H — terminal publication](V2H-terminal-publication-semantics.md)
- [V2I — loop orchestration/attempt semantics](V2I-loop-orchestration-attempt-semantics.md)
- [V2J — Acquisition UI + Expert Recovery](V2J-acquisition-ui-expert-recovery.md)

Accepted cross-ticket recurrence decision:

```text
continuous q+s
→ deterministic bounded canonical batch solve
→ lagged Reliability
→ weighted P/N with raw V
→ one atomic Consensus Revision
→ post-solve Scope Delta
```

Q5 must still define the consensus readout and Reliability residual before V2C/V2D/V2E can be decomposed.

V2A's later implementation decomposition must include a nonblocking `V2AX` depth-classified Negative Evidence experiment. V2AX is not a production Ticket and does not block V2C/D/E.

Do not implement parent envelopes directly. Each must be split into small TDD stages and jointly marked `agent-ready` by the current mapping and review-status documents.
