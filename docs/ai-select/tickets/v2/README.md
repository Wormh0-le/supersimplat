# AI Select v2 Ticket Envelopes

Status: **pre-implementation review; no ticket is agent-ready**

Current parent capability envelopes:

- [V2A — projected depth, CWED moments, and depth-Evidence experiment](V2A-depth-moments-and-depth-evidence-experiment.md)
- [V2B — Conservative Seed, Core Target, and Discovery Frontier](V2B-conservative-seed-discovery-frontier.md)
- [V2C — q+s Consensus, canonical solve, and multi-channel readout](V2C-provisional-consensus-softmask-readout.md)
- [V2D — lagged regional Reliability + LOO reference](V2D-observation-reliability.md)
- [V2E — weighted aggregation, q/s update, and scope revision](V2E-weighted-aggregation-revision.md)
- [V2F — View Utility, exploration, and candidate pool](V2F-view-utility-layered-candidate-pool.md)
- [V2G — budgets/failure/termination](V2G-budgets-failure-termination.md)
- [V2H — terminal publication](V2H-terminal-publication-semantics.md)
- [V2I — loop orchestration/attempt semantics](V2I-loop-orchestration-attempt-semantics.md)
- [V2J — Acquisition UI + Expert Recovery](V2J-acquisition-ui-expert-recovery.md)

Accepted cross-ticket decisions:

```text
Q4-B:
continuous q+s → deterministic bounded recurrence

Q5-D:
same-decision multi-channel readout
→ trusted asymmetric regional residual
→ production full-set lagged Reliability
+ offline leave-one-out reference
```

Q6 must still define q/s transforms, robust residual-to-weight normalization, and convergence before V2C/V2D/V2E can be decomposed.

Nonblocking sidecars:

- `V2AX` depth-classified Negative Evidence experiment;
- leave-one-out Reliability reference benchmark.

Do not implement parent envelopes directly. Each must be split into small TDD stages and jointly marked `agent-ready` by current mapping and review status.
