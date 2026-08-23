# AI Select Documentation Migration Status

Status: **v2 control plane current; v1 history separated; pre-implementation review active**

## Completed

- Final Spec v2.0 is the target architecture.
- Amendment 001 and ADR 0022 change the product orientation to automation-default with Expert Recovery.
- Current mapping, traceability, manifest, review gate, graph, and agent guidance point to the amended v2 target.
- Exact implemented v1 control-plane snapshots are preserved under `docs/ai-select/history/v1/`.
- Root v1 graph/audit/walkthrough files are compatibility pointers rather than competing authority.
- User-added View is retained as a migration foundation; obsolete V2J removal documentation is deleted.
- The old root glossary term `User-added View (superseded)` is explicitly deprecated by the current context amendment.

## Current planning state

```text
runtime baseline       = implemented v1.3
normative target       = amended v2.0
planning phase         = pre-implementation review
agent-ready tickets    = none
next review item       = V2A
```

## Remaining work

- review V2A depth/Negative Evidence implementation seam;
- close consensus recurrence, View Utility, loop identity/budgets, terminal matrix, and Expert Recovery lifecycle;
- split parent tickets into small TDD stages;
- assign calibration, policy freeze, production promotion, cutover, and release qualification;
- fold context amendments into root `CONTEXT.md` only when the broader glossary is safely consolidated, then delete the superseded definitions rather than retaining duplicates.

No production code changed in this documentation decision.
