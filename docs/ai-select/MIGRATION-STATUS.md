# AI Select Documentation Migration Status

## Completed

- Added stable documentation root: `docs/ai-select/`.
- Added Ticket 14 decomposition.
- Restored the complete 31-parent-ticket Final Spec v1.3 mapping after an accidental simplified replacement.
- Promoted the current ticket mapping and implementation graph to `docs/ai-select/`.
- Promoted durable traceability, walkthrough and audit records to `docs/ai-select/`.
- Promoted the 04C protocol contract to `docs/ai-select/contracts/`.
- Split benchmark material: durable result records under `docs/ai-select/benchmarks/`, executable harnesses under `.scratch/experiments/ai-select-v1/benchmarks/`.
- Split browser validation material: durable walkthrough evidence under `docs/ai-select/walkthroughs/`, executable browser/GPU harnesses under `.scratch/experiments/ai-select-v1/browser-validation/`.
- Moved 04C cross-check/repro tooling to `.scratch/experiments/ai-select-v1/04c/`.
- Historical scratch locations for promoted durable documents retain small compatibility pointers where useful.

## Pending migration

The remaining `.scratch/ai-select-v1` control-plane content is:

- `issues/` — active Ticket contracts;
- `manifest.json` — ticket/planning manifest;
- compatibility pointers for historical paths.

`issues/` and `manifest.json` are intentionally handled as the final migration stage because repository guidance currently routes agents through `.scratch/ai-select-v1/issues/` and may parse the manifest directly.

## Rule

`docs/ai-select/` owns durable planning, traceability and release/acceptance knowledge. `.scratch/experiments/ai-select-v1/` owns executable/disposable investigation artifacts. Compatibility stubs may remain at historical scratch paths until inbound references are migrated.
