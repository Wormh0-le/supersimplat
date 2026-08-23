# AI Select Specification Index

## Current normative stack

Read in this order:

1. [`ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`](./ai-select-final-spec-v2.0-amendment-001-expert-recovery.md)
2. [`ai-select-final-spec-v2.0.md`](./ai-select-final-spec-v2.0.md), except where amended
3. [`../adr/0022-automation-default-with-expert-recovery.md`](../adr/0022-automation-default-with-expert-recovery.md)
4. [`../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md`](../adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md)
5. [`../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md`](../adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md)
6. carried-over non-conflicting ADR 0019, residual ADR 0018, and ADRs 0016/0017/0013/0015
7. [`../ai-select/CURRENT-TICKET-SPEC-MAPPING.md`](../ai-select/CURRENT-TICKET-SPEC-MAPPING.md)
8. [`../ai-select/V2-REVIEW-STATUS.md`](../ai-select/V2-REVIEW-STATUS.md)

Final Spec v2.0 remains the target architecture. Amendment 001 changes the product orientation from fully automatic-only to automation-default with expert recovery:

```text
Anchor
→ automatic acquisition by default
→ terminal Candidate/readiness
→ optional Expert Recovery:
   Add Observation / Use Current View
   or Continue Acquisition
```

Runtime behavior remains the implemented v1.3 baseline until reviewed V2 tickets perform explicit cutovers.

## Domain vocabulary

- [`../../CONTEXT.md`](../../CONTEXT.md) — base glossary
- [`../ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md`](../ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md) — current override for User-added View and recovery terms

## Historical specifications

Final Spec v1.3 and earlier specifications remain historical provenance. Their implemented mapping, traceability, graph, audit, and manifest are retained under [`../ai-select/history/v1/`](../ai-select/history/v1/).

Historical material must not override the current amended v2 target.
