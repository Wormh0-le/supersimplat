# AI Select Documentation Migration Status

Status: **substantive migration complete; historical scratch paths are compatibility-only**

## Completed

- Stable AI Select planning root established at `docs/ai-select/`.
- Full 31-parent-ticket Final Spec v1.3 mapping restored and promoted.
- Ticket graph promoted and synchronized to v2.25.
- Parent Ticket 14 decomposed into executable 14A–14D stage contracts without changing normative product scope.
- Active Ticket control plane promoted to `docs/ai-select/tickets/`.
- Planning manifest promoted to `docs/ai-select/manifest.json` and updated with parent/stage frontier fields.
- Durable traceability, walkthrough, audit, protocol-contract, benchmark-result and browser-walkthrough evidence promoted to `docs/ai-select/`.
- Executable cross-check/repro, benchmark and browser/GPU harnesses moved to `.scratch/experiments/ai-select-v1/`.
- `AGENTS.md` source routing updated to stable docs/Ticket locations.
- Historical `.scratch/ai-select-v1` planning paths reduced to compatibility pointers/readmes rather than duplicate normative content.
- CI is configured for `ai-select-v1` pushes with integrated `npm test`, build, lint and locale-lint jobs; locked-GPU validation remains a separate environment-specific gate.

## Directory ownership

```text
docs/ai-select/
  durable planning, Tickets, mappings, manifest, traceability and acceptance evidence

.scratch/experiments/ai-select-v1/
  executable/disposable experiments, repros and validation harnesses

.scratch/ai-select-v1/
  compatibility redirects only; no new normative content
```

## Remaining compatibility cleanup

Old scratch compatibility pointers may be removed in a future cleanup only after any external tooling or local agent configuration that still hardcodes those paths has migrated. They are not authoritative.

## Current execution frontier

```text
next_implementation_ticket = 17
next_implementation_subticket = null

14A Evidence Contract & Working Set (implemented)
→ 14B Reference Per-View P/N/V Evidence (implemented)
→ 14C Multi-view Aggregation & Classification (implemented)
→ 14D Atomic Candidate Publication & Reference Validation (implemented)
→ 13 Lift Readiness (implemented)
→ 15 Candidate correction / Re-Lift (implemented)
→ 16 Native Candidate operations (implemented)
→ 17 Applied Undo-and-Fix / Restart / multi-target lifecycle (current)
```
