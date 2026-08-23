# AI Select Specification Index

## Current normative stack

Read in this order:

1. [`ai-select-final-spec-v2.0-amendment-003-deterministic-bounded-consensus-recurrence.md`](./ai-select-final-spec-v2.0-amendment-003-deterministic-bounded-consensus-recurrence.md)
2. [`ai-select-final-spec-v2.0-amendment-002-seed-discovery-depth-staging.md`](./ai-select-final-spec-v2.0-amendment-002-seed-discovery-depth-staging.md)
3. [`ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`](./ai-select-final-spec-v2.0-amendment-001-expert-recovery.md)
4. [`ai-select-final-spec-v2.0.md`](./ai-select-final-spec-v2.0.md), except where amended
5. [`../adr/0024-deterministic-bounded-consensus-recurrence.md`](../adr/0024-deterministic-bounded-consensus-recurrence.md)
6. [`../adr/0023-stage-depth-support-and-require-seed-independent-discovery.md`](../adr/0023-stage-depth-support-and-require-seed-independent-discovery.md)
7. [`../adr/0022-automation-default-with-expert-recovery.md`](../adr/0022-automation-default-with-expert-recovery.md)
8. [`../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md`](../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md) — partially superseded
9. [`../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md`](../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md)
10. carried-over non-conflicting ADR 0019, residual ADR 0018, and ADRs 0016/0017/0013/0015
11. [`../ai-select/CURRENT-TICKET-SPEC-MAPPING.md`](../ai-select/CURRENT-TICKET-SPEC-MAPPING.md)
12. [`../ai-select/V2-REVIEW-STATUS.md`](../ai-select/V2-REVIEW-STATUS.md)

Amendment 001 adopts automation-default Expert Recovery. Amendment 002 adopts CWED terminology, S0/S1 shadow Seed evaluation, seed-independent Discovery Envelope/Frontier, separate Core Coverage/Frontier Debt, and nonblocking classified-N experimentation. Amendment 003 adopts continuous q+s consensus and a deterministic bounded canonical recurrence with post-solve two-phase scope commit.

Runtime behavior remains the implemented v1.3 baseline until reviewed V2 stages perform explicit cutovers.

## Domain vocabulary

- [`../../CONTEXT.md`](../../CONTEXT.md) — base glossary
- [`../ai-select/CONTEXT-AMENDMENT-003-CONSENSUS-RECURRENCE.md`](../ai-select/CONTEXT-AMENDMENT-003-CONSENSUS-RECURRENCE.md) — consensus recurrence override
- [`../ai-select/CONTEXT-AMENDMENT-002-SEED-DISCOVERY-DEPTH.md`](../ai-select/CONTEXT-AMENDMENT-002-SEED-DISCOVERY-DEPTH.md) — Seed/discovery/depth override
- [`../ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md`](../ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md) — Expert Recovery override

## Historical specifications

Final Spec v1.3 and earlier specifications remain historical provenance under [`../ai-select/history/v1/`](../ai-select/history/v1/). Historical material and superseded clauses do not override the current amended v2 target.
