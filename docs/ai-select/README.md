# AI Select Documentation

Stable, long-lived AI Select planning and validation documentation lives here.

## Control plane

```text
docs/ai-select/
├── README.md
├── manifest.json
├── CURRENT-TICKET-SPEC-MAPPING.md
├── TICKET-GRAPH.md
├── TICKET-14-SPLIT.md
├── tickets/
│   ├── 01-...md
│   ├── ...
│   ├── 14-gaussian-lifting-candidate.md
│   ├── 14A-evidence-contract-working-set.md
│   ├── 14B-reference-per-view-pnv-evidence.md
│   ├── 14C-multiview-aggregation-classification.md
│   ├── 14D-atomic-candidate-publication-validation.md
│   └── 16A-candidate-viewport-presentation.md
├── TRACEABILITY.md
├── WALKTHROUGHS.md
├── FOUR-PASS-AUDIT.md
├── MIGRATION-STATUS.md
├── contracts/
├── benchmarks/
└── walkthroughs/
```

Repository-wide specifications and ADRs remain canonical under `docs/specs/` and `docs/adr/`.

## Accepted designs

- [AI View Dock layout](ai-view-dock-layout.md) — accepted responsive Dock layout and interaction contract for Ticket 16A.
- [AI View Dock visual](show-me-ai-view-dock-layout.html) — visual companion for the accepted layout.
- [AI Select Toolbar layout](ai-select-toolbar-layout.md) — accepted Candidate Overlay, Toolbar, Status Bar and cross-surface state contract for Ticket 16A.
- [Ticket 16A](tickets/16A-candidate-viewport-presentation.md) — current implementation stage combining both accepted designs.

## Scratch policy

Executable and disposable investigation material lives under:

```text
.scratch/experiments/ai-select-v1/
```

This includes repro probes, cross-check scripts, benchmark harnesses and browser/GPU validation harnesses.

`.scratch/ai-select-v1/` is compatibility-only after the migration. It must not become a second source of truth.

## Current frontier

Parent Ticket 14 is decomposed into:

- 14A — Evidence Contract & Working Set;
- 14B — Reference Per-View P/N/V Evidence;
- 14C — Multi-view Aggregation & Classification;
- 14D — Atomic Candidate Publication & Reference Validation.

Execution order is:

```text
14A → 14B → 14C → 14D → 13 → 15 → 16 → 16A → 17
```

14A through 14D, parent Ticket 14, Tickets 13 through 15 and Ticket 16's native
application core are implemented. Ticket 16A is the current post-closure
presentation stage (`next_implementation_ticket = 16`,
`next_implementation_subticket = 16A`); Ticket 17 follows it.
