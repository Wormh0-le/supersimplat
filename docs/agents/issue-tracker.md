# GitHub Issue Workflow

Read this file for issue operations, triage labels, PR identification, or Wayfinder work. Issues and PRDs live as GitHub issues. Prefer `gh` from the repository clone when available; otherwise use an exposed GitHub integration or read public authority through the browser. Reading authority and workflow guidance does not itself authorize publishing or changing tracker state.

## Repository conventions

- GitHub issues, not pull requests, are the feature-request, planning, and triage surface.
- When a skill says to publish to the issue tracker, create an issue.
- When a skill says to fetch a ticket, read the issue body, comments, labels, assignees, and blockers.
- GitHub shares issue and PR numbers. For an ambiguous `#<n>`, try `gh pr view <n>` and fall back to `gh issue view <n>`.
- Use CLI help for ordinary create/read/comment/edit/close syntax instead of maintaining a command catalog here.

Use the canonical triage labels in [Triage labels](triage-labels.md).

## AI Select v2.0

- [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) is the current specification/Wayfinder entry point.
- Apply the [Domain authority implementation gate](domain.md#implementation-gate); parent capability maps organize child execution regardless of their labels.
- Decomposition creates small child Issues linked from #37 and their parent. The child body owns exact scope, dependencies, identities, migration, tests, evidence, and non-goals.
- When GitHub native sub-issues or dependency edges are unavailable, retain `Part of #<map>` and `Blocked by: #<n>` in the body and keep #37's task list/dependency spine current.

## Wayfinder

- A map is one issue; its body owns Notes, Decisions-so-far, Fog, and the ordered frontier index.
- A child ticket is a GitHub sub-issue. If sub-issues are unavailable, link it from the map task list and put `Part of #<map>` at the top of the child.
- Use native issue dependencies for blocking. If unavailable, record `Blocked by: #<n>`.
- Choose an open, unblocked, unassigned child from the owning map's current frontier; preserve any explicitly supported parallel frontiers.
- Claim a ticket by assigning it to yourself.
- For authorized closeout, follow [Documentation and traceability](documentation.md#feature-and-decision-lifecycle) and record durable evidence in the owning Issue.
