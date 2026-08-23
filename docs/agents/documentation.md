# Project Documentation and Traceability

Read this file when changing `CONTEXT.md`, GitHub Issue authority, accepted decisions, comments, historical links, or traceability.

## Artifact ownership

- Root `CONTEXT.md` owns stable domain vocabulary. It does not own implementation status, readiness, counts, paths, numeric calibration, or active decomposition.
- GitHub [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) owns the current AI Select v2.0 authority index, decision status, parent dependency frontier, implementation gate, and immutable links to the accepted specification record.
- Parent Issues #38–#47 own reviewed capability envelopes and their decomposition frontiers. They are not agent-ready implementation tickets.
- Exact child Issues own active TDD stages, inputs/outputs, dependencies, migration boundary, validation, and readiness. Only a child explicitly linked from #37 and labeled `ready-for-agent` may authorize implementation.
- Explicitly accepted Issue comments may record a new decision; reconcile the owning Issue body and #37 when the durable status or graph changes.
- Commit [`aacad57`](https://github.com/Wormh0-le/supersimplat/tree/aacad57fc534acc43522ca4d51d41149b5ee9692) is the immutable migration snapshot for removed specifications, ADRs, feature documents, tickets, reviews, benchmarks, and `.scratch` evidence.
- `docs/agents/**` owns agent guidance only. Do not recreate a second current spec/ticket/ADR control plane under `docs/**`.

Update only the artifact whose owned claim changed. Do not edit #37 or a capability Issue for a code-only detail that leaves its contract, graph, calibration, or readiness unchanged.

## Feature and decision lifecycle

- New product or architectural decisions belong in the narrowest owning Issue and must be linked from #37 when they change the global map.
- Stable terminology may be consolidated into `CONTEXT.md`; do not copy active decomposition or mutable status into the glossary.
- Preserve historical acceptance records through immutable commit links rather than restoring deleted planning files.
- At feature closeout, close the exact child Issue with evidence, update the parent checklist/frontier, and update #37 only when parent/global status changed.
- If implementation reveals a contract conflict, stop at the fail-closed boundary and reopen the decision in the owning Issue instead of silently changing code or glossary text.

For local comments, use comments only for non-obvious authority, identity, atomicity, fail-closed behavior, or trust boundaries. Link to the owning Issue rather than duplicating broad rationale.

## Validation

Check terminology against `CONTEXT.md` and current Issue authority, then verify changed links, commands, schemas, examples, issue relationships, labels, and acceptance evidence. Documentation-only cleanup does not require runtime suites unless executable behavior or generated artifacts changed.
