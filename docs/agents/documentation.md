# Project Documentation and Traceability

Read this file when changing agent guidance, `CONTEXT.md`, GitHub Issue authority, accepted decisions, comments, historical links, or traceability. For guidance placement and maintenance, also read [Agent guidance structure](README.md).

## Artifact ownership

- Root `CONTEXT.md` owns stable domain vocabulary. It does not own implementation status, readiness, counts, paths, numeric calibration, or active decomposition.
- GitHub [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) owns the current AI Select v2.0 authority index, decision status, parent dependency frontier, implementation gate, and immutable links to the accepted specification record.
- Parent Issues #38–#47 own capability maps and their decomposition frontiers.
- Exact child Issues own active TDD stages, inputs/outputs, dependencies, migration boundary, validation, and readiness. [Domain authority](domain.md) defines implementation eligibility.
- Explicitly accepted Issue comments may record a new decision; reconcile the owning Issue body and #37 when the durable status or graph changes.
- Commit [`504e888`](https://github.com/Wormh0-le/supersimplat/tree/504e8885b87575761dc2e367e520b7dfba46884b) is the immutable migration snapshot for removed specifications, ADRs, feature documents, tickets, reviews, benchmarks, and `.scratch` evidence.
- `docs/agents/**` owns agent guidance only. Do not recreate a second current spec/ticket/ADR control plane under `docs/**`.

Update only the artifact whose owned claim changed. Do not edit #37 or a capability Issue for a code-only detail that leaves its contract, graph, calibration, or readiness unchanged.

## Feature and decision lifecycle

- New product or architectural decisions belong in the narrowest owning Issue and must be linked from #37 when they change the global map.
- Stable terminology may be consolidated into `CONTEXT.md`; do not copy active decomposition or mutable status into the glossary.
- Preserve historical acceptance records through immutable commit links rather than restoring deleted planning files.
- For authorized feature closeout, close the exact child Issue with evidence, update the parent checklist/frontier, and update #37 only when parent/global status changed.
- If implementation reveals a contract conflict, stop at the fail-closed boundary and reopen the decision in the owning Issue instead of silently changing code or glossary text.

For local comments, use comments only for non-obvious authority, identity, atomicity, fail-closed behavior, or trust boundaries. Link to the owning Issue rather than duplicating broad rationale.

## Validation

Check affected domain terminology against `CONTEXT.md` and current Issue authority; for guidance-only changes, check rule ownership, task routing, and consistency with the global contract. Verify changed links, commands, schemas, examples, Issue relationships, labels, and acceptance evidence as applicable. Follow [Project verification](execution-and-verification.md) for validation scope.
