# GitHub Issue Workflow

Issues are the product-planning and implementation-tracking surface. Prefer `gh` from a clone when available; otherwise use the exposed GitHub integration. Reading guidance does not itself authorize writes.

## Current queue

Read [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) and the exact active slice, including comments, labels, inputs, and blockers. Follow [Domain authority](domain.md). The retired V2A–V2J parent/child graph is not an executable queue.

`ready-for-agent` means fully specified AND currently unblocked with the necessary inputs available. Only a few near-term slices receive it. Prepared/blocked work records its concrete blocker without this label. Do not label roadmap tracks or conditional experiments ready.

Claim one open, ready, unassigned slice listed in the current queue. A slice should explain the observable outcome, why it matters now, minimal end-to-end behavior, exclusions, evidence, and real blockers. Keep TDD and PRs small; do not create an issue for each constructor, reducer, or red/green step.

## Dependencies and closeout

Use native dependencies when available; otherwise state `Blocked by: #n` and any data/runtime prerequisite in the active issue. Avoid inferring implementation readiness merely because a predecessor was closed as superseded.

For authorized closeout, attach exact implementation/review/test evidence and update the current #37 queue. Use `completed` only for accepted delivery. Use `not_planned` for superseded plans, retain their history, route their titles to #37, and remove ready labels. See [Documentation and traceability](documentation.md).

GitHub shares issue/PR numbers; resolve an ambiguous number before writing. Preserve in-flight work and unrelated labels/state. When an implementation reveals a research question, record the concrete counterexample and smallest comparison in #37 rather than resurrecting every old research ticket.

Follow [Triage labels](triage-labels.md). New scopes or tracker writes must be authorized by the user or current accepted workflow.
