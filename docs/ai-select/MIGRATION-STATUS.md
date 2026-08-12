# AI Select Documentation Migration Status

## Completed

- Added stable documentation root: `docs/ai-select/`.
- Added Ticket 14 decomposition.
- Restored the complete 31-parent-ticket Final Spec v1.3 mapping after an accidental simplified replacement.
- Promoted the current ticket mapping to `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md`.
- Promoted the implementation graph to `docs/ai-select/TICKET-GRAPH.md` and synchronized it to v2.18 / 14A stage frontier.
- Promoted durable traceability, walkthrough and audit records to `docs/ai-select/`.
- Replaced old scratch copies of promoted documents with compatibility pointers rather than duplicate sources of truth.
- Defined scratch usage boundary.

## Pending migration

The following investigation-oriented content still needs classification or relocation under `.scratch/experiments/ai-select-v1/`:

- benchmark scripts and temporary benchmark records;
- browser/GPU validation scripts and temporary walkthrough captures;
- issue investigation notes that are not active durable Ticket contracts;
- repro/probe scripts in the `.scratch/ai-select-v1` root.

Active Ticket contracts under `.scratch/ai-select-v1/issues/` must be classified before bulk movement because repository guidance currently references that path.

## Rule

`docs/ai-select/` owns durable planning, traceability and release/acceptance knowledge. `.scratch` owns disposable investigation artifacts. Compatibility stubs may remain at historical scratch paths until all inbound references are migrated.
