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
│   └── 14D-atomic-candidate-publication-validation.md
├── TRACEABILITY.md
├── WALKTHROUGHS.md
├── FOUR-PASS-AUDIT.md
├── MIGRATION-STATUS.md
├── contracts/
├── benchmarks/
└── walkthroughs/
```

Repository-wide specifications and ADRs remain canonical under `docs/specs/` and `docs/adr/`.

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
14A → 14B → 14C → 14D → 13
```

14A and 14B are implemented. Compatibility remains `next_implementation_ticket = 14`; the stage-level frontier is `next_implementation_subticket = 14C`.
