# AI Select Domain Authority

Read this file when work changes AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Current authority

The current normative target is **Final Spec v2.0**. The shipped runtime remains the implemented v1.3 baseline until each V2 cutover ticket lands.

Read sources in this order:

1. `docs/specs/ai-select-final-spec-v2.0.md`
2. `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`
3. `docs/adr/0021-kernel-internal-depth-readouts-and-depth-classified-negative-mass.md`
4. `docs/adr/0020-auto-publish-candidate-at-ready-low-gain-terminal.md`
5. carried-over ADR 0019, then residual ADR 0018 and unconflicted ADRs 0016/0017/0013/0015
6. `CONTEXT.md` for stable vocabulary only
7. `docs/ai-select/TICKET-GRAPH-V2.md`
8. `docs/ai-select/V2-REVIEW-STATUS.md`
9. the affected V2 ticket, implementation, tests, runtime declarations, and benchmark records

Surface conflicts instead of silently choosing one source.

## Implementation gate

V2A–V2J are accepted product scope but are under pre-implementation review. Do not implement a V2 ticket merely because its file exists. It becomes agent-ready only when the current mapping and review-status document both say so.

## Product boundaries carried into v2.0

- AI Select is a native SuperSplat Selection Tool, not a separate semantic-object workspace.
- The browser owns one user-visible Current Target Context and all user-visible product state.
- Authoritative AI observation RGB comes from locked gsplat.
- Stable Masks and Participation remain distinct from P/N/V Evidence, provisional consensus, Candidate, and Native Selection.
- AI Candidate is derived state. It changes Native Selection only through explicit Set, Add, Remove, or Intersect backed by native EditHistory.
- Complete per-pixel Contributor remains reference/debug only.
- RGB Ready, Mask Ready, Evidence Ready, and Candidate Ready remain distinct.
- Provisional consensus, reliability, and View Utility are not ownership authorities and cannot mutate Native Selection.

## Historical material

Final Spec v1.3 and its implemented ticket graph remain historical provenance for the shipped baseline. Historical mapping, traceability, manifest, and graph live under `docs/ai-select/history/v1/`. Root-level v1 ticket files and old acceptance evidence are retained only as implemented-history records unless a current document explicitly references them.
