# AI Select Domain Authority

Read this file when work changes AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Current authority

Read sources in this order:

1. `docs/specs/ai-select-final-spec-v2.0-amendment-001-expert-recovery.md`
2. `docs/specs/ai-select-final-spec-v2.0.md`, except where amended
3. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
4. ADR 0022, ADR 0021, ADR 0020
5. carried-over ADR 0019, residual ADR 0018, and unconflicted ADRs 0016/0017/0013/0015
6. `docs/ai-select/CONTEXT-AMENDMENT-001-EXPERT-RECOVERY.md`, then root `CONTEXT.md`
7. `docs/ai-select/TICKET-GRAPH-V2.md`
8. `docs/ai-select/V2-REVIEW-STATUS.md`
9. the affected ticket, implementation, tests, runtime declarations, and benchmark records

Surface conflicts instead of silently choosing one source.

## Runtime versus target

- Final Spec v2.0 as amended is the normative target.
- Shipped behavior remains the implemented v1.3 baseline until explicit V2 cutovers land.
- V2A–V2J are accepted scope but are not agent-ready unless both current mapping and review status say so.

## Product orientation

- Automatic acquisition is the default post-Anchor workflow.
- Expert Recovery is secondary and available only when no loop is running and the target is active.
- Expert Recovery retains User-added View as `Add Observation / Use Current View` and adds `Continue Acquisition`.
- Expert recovery never bypasses Stable Mask, Participation, Direct Evidence, Candidate identity, or explicit Native Set/Add/Remove/Intersect.
- Persistent planning controls and camera management during a running loop remain out of scope.

## Product boundaries

AI Select is a native SuperSplat Selection Tool, not a semantic-object workspace. The Browser owns user-visible target state and Native Selection. Provisional consensus, reliability, View Utility, and Candidate are derived state and never mutate Native Selection by themselves. Complete per-pixel Contributor remains reference/debug only.

## Historical material

Final Spec v1.3 and its ticket graph remain provenance for the shipped baseline under `docs/ai-select/history/v1/`. The old root glossary definition `User-added View (superseded)` is deprecated by the current context amendment.
