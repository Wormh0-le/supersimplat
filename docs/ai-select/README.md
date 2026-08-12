# AI Select Documentation

Stable, long-lived AI Select planning and validation documentation lives here.

## Stable documents

```text
docs/ai-select/
├── README.md
├── CURRENT-TICKET-SPEC-MAPPING.md
├── TICKET-GRAPH.md
├── TICKET-14-SPLIT.md
├── TRACEABILITY.md
├── WALKTHROUGHS.md
├── FOUR-PASS-AUDIT.md
├── MIGRATION-STATUS.md
├── contracts/
│   └── 04C-protocol-contract.md
├── benchmarks/
│   └── 02b-real-sh3-result.md
└── walkthroughs/
    ├── 08-local-key-views-walkthrough.md
    ├── 08B-route-b-production-acquisition-walkthrough.md
    └── 11-user-added-ai-view-walkthrough.md
```

Repository-wide specifications and ADRs remain in their existing canonical locations under `docs/specs/` and `docs/adr/`.

## Scratch policy

Executable and disposable investigation material lives under:

```text
.scratch/experiments/ai-select-v1/
```

This includes repro probes, cross-check scripts, benchmark harnesses and browser/GPU validation harnesses.

Normative mapping, ticket graph, protocol contracts, traceability, audits, durable benchmark results and durable walkthrough evidence must not live only under `.scratch`.

## Current frontier

Parent Ticket 14 is decomposed into:

- 14A Evidence Aggregation Layer;
- 14B Gaussian Projection Scoring;
- 14C Candidate Artifact;
- 14D Candidate Review Surface.

Execution order is `14A → 14B → 14C → 14D → 13`.

Compatibility remains `next_implementation_ticket = 14`; the stage-level frontier is `next_implementation_subticket = 14A`.
