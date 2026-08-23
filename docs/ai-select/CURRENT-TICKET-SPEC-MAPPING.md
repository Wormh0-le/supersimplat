# Final Spec v2.0 → Current Planning Mapping

Status: **current control-plane entry point — pre-implementation review**

Updated: 2026-08-23  
Branch: `ai-select-v1`

## Authority

1. `docs/specs/ai-select-final-spec-v2.0.md`
2. this mapping
3. ADR 0021
4. ADR 0020
5. carried-over ADR 0019
6. residual ADR 0018 and unconflicted ADRs 0016/0017/0013/0015
7. `CONTEXT.md` for stable vocabulary only
8. `docs/ai-select/TICKET-GRAPH-V2.md`
9. `docs/ai-select/V2-REVIEW-STATUS.md`
10. affected ticket, implementation, tests, runtime declarations, and benchmark evidence

Final Spec v1.3 is historical provenance for the shipped baseline. Its exact mapping, traceability, manifest, and graph are preserved under `docs/ai-select/history/v1/`.

## Runtime and planning status

```text
normative target          = Final Spec v2.0
shipped runtime baseline  = implemented Final Spec v1.3
v2 implementation status  = not started
planning phase            = pre-implementation review
ticket in flight          = none
agent-ready V2 tickets    = none
review frontier           = V2A, then V2C
```

Accepted product scope does not make a ticket agent-ready. An implementation ticket becomes agent-ready only after its design/implementation blockers are closed here and in `V2-REVIEW-STATUS.md`.

## Current v2 mapping

| Ticket | Final Spec v2.0 scope | Current lifecycle | Key review gate |
|---|---|---|---|
| V2A | §5, ADR 0021 | review-required | depth data path, traversal, classified-N schema/identity |
| V2B | §4 | review-required | seed representation, connectivity, fallback and denominator ownership |
| V2C | §5, §7.1 | review-required | consensus state, initialization and recurrence |
| V2D | §7.2 | review-required | reliability equation, guardrails and provenance exemptions |
| V2E | §7.3 | review-required | recurrence integration, denominator expansion and incremental equivalence |
| V2F | §6.1–§6.2 | review-required | ViewUtilityProbe, approximation/cost and candidate-pool contract |
| V2G | §6.3–§6.4 | review-required | outcome taxonomy, deterministic cost accounting and stop reasons |
| V2H | §6.4, ADR 0020 | review-required | complete Readiness × StopReason publication matrix and consent |
| V2I | §3, §8 | review-required | loop/iteration/request identity hierarchy, journal, replay and cancel |
| V2J | §10 | review-required | recovery UX and whether/when User-added View is removed |

The dependency graph in `TICKET-GRAPH-V2.md` is provisional until these review gates close.

## Carry-over implementation

The following remain implemented v1.3 foundations and must stay green throughout v2 work:

- official SAM 3 Image single-result authoring;
- Anchor, Prompt/Edit, TargetGeometryHint and Stable Mask lifecycle;
- Participation and User Confirmed authority;
- authoritative gsplat RGB and same-decision Direct P/N/V;
- Stable Gaussian IDs, SceneSnapshot, Render/Evidence Working Sets;
- Lift Readiness authority, atomic Candidate replacement and Native operations;
- dirty/stale/suspend/replay/failure isolation;
- production identity and locked-GPU benchmark infrastructure.

## Documentation lifecycle

### Current

- `docs/specs/ai-select-final-spec-v2.0.md`
- ADR 0020/0021 and carried-over non-conflicting ADRs
- this mapping
- `docs/ai-select/TICKET-GRAPH-V2.md`
- `docs/ai-select/TRACEABILITY.md`
- `docs/ai-select/manifest.json`
- `docs/ai-select/V2-REVIEW-STATUS.md`
- `docs/ai-select/tickets/v2/`

### Historical, retained for provenance

- `docs/specs/ai-select-final-spec-v1.3.md`
- `docs/ai-select/history/v1/`
- root-level implemented v1 ticket files under `docs/ai-select/tickets/`
- v1 audits, walkthroughs, contracts, and benchmark records

### Deprecated as current authority

- root `docs/ai-select/TICKET-GRAPH.md` is a compatibility entry point only;
- v1 files must not advertise a current frontier or override v2;
- `.scratch/ai-select-v1/` remains compatibility-only.

## Machine-readable frontier

```text
review_frontier = V2A, V2C
next_review_item = V2A
next_implementation_ticket = none
next_implementation_subticket = none
implementation_blocker = pre-implementation review
```
