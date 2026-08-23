# AI Select Documentation

This directory separates the current v2.0 target control plane from implemented v1.3 history.

## Current control plane

```text
docs/ai-select/
├── CURRENT-TICKET-SPEC-MAPPING.md
├── TICKET-GRAPH-V2.md
├── TRACEABILITY.md
├── manifest.json
├── V2-REVIEW-STATUS.md
├── tickets/
│   ├── README.md
│   ├── v2/                 # accepted v2 capability umbrellas; review-required
│   └── *.md                # implemented v1 ticket records; historical
└── history/
    └── v1/                 # exact v1 mapping/traceability/manifest/graph snapshots
```

The normative product target is `docs/specs/ai-select-final-spec-v2.0.md`. The shipped runtime remains the implemented v1.3 baseline until reviewed V2 cutovers land.

## Start here

1. [`CURRENT-TICKET-SPEC-MAPPING.md`](CURRENT-TICKET-SPEC-MAPPING.md)
2. [`V2-REVIEW-STATUS.md`](V2-REVIEW-STATUS.md)
3. [`TICKET-GRAPH-V2.md`](TICKET-GRAPH-V2.md)
4. [`TRACEABILITY.md`](TRACEABILITY.md)
5. [`manifest.json`](manifest.json)

No V2 ticket is currently agent-ready.

## Document lifecycle

### Current

Current spec, ADRs, mapping, review gate, graph, traceability, manifest, and V2 ticket contracts may direct future work.

### Historical

- Final Spec v1.3;
- exact v1 control-plane snapshots under `history/v1/`;
- root-level implemented v1 ticket files;
- `TICKET-14-SPLIT.md`, v1 audits, walkthroughs, protocol records, and v1 benchmark evidence.

Historical files remain useful for provenance and regression but cannot override v2.0.

### Deprecated compatibility entry points

- `TICKET-GRAPH.md` redirects to current v2 and historical v1 graphs.
- `.scratch/ai-select-v1/` is compatibility-only.
- Old external links may be retained as redirects; do not add new normative content there.

### Disposable

Executable experiments, repros and temporary validation harnesses belong under `.scratch/experiments/ai-select-v1/`. Delete them when no longer needed unless promoted to durable benchmark evidence.

## Review before implementation

The immediate work is not coding. Follow the ordered review in `V2-REVIEW-STATUS.md`, amend the design where needed, split capability umbrellas into small stages, and assign calibration/promotion/release ownership before marking a ticket agent-ready.
