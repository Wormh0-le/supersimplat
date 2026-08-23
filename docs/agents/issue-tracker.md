# GitHub Issue Workflow

Read this file for issue operations, triage labels, PR identification, or Wayfinder work. Issues and PRDs live as GitHub issues; use `rtk gh` from the repository clone.

## Repository conventions

- GitHub issues, not pull requests, are the feature-request, planning, and triage surface.
- When a skill says to publish to the issue tracker, create an issue.
- When a skill says to fetch a ticket, read the issue body, comments, labels, assignees, and blockers.
- GitHub shares issue and PR numbers. For an ambiguous `#<n>`, try `rtk gh pr view <n>` and fall back to `rtk gh issue view <n>`.
- Use CLI help for ordinary create/read/comment/edit/close syntax instead of maintaining a command catalog here.

Use only these canonical triage labels:

- `needs-triage`
- `needs-info`
- `ready-for-agent`
- `ready-for-human`
- `wontfix`

## AI Select v2.0

- [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) is the current specification/Wayfinder entry point.
- Issues #38–#47 are reviewed parent capability envelopes. Never assign `ready-for-agent` to a parent envelope and never implement one directly.
- Decomposition creates small child Issues linked from #37 and their parent. The child body owns exact scope, dependencies, identities, migration, tests, evidence, and non-goals.
- A v2 child becomes executable only when its blockers are closed or declared nonblocking, #37 places it at the current frontier, and it carries `ready-for-agent`.
- When GitHub native sub-issues or dependency edges are unavailable, retain `Part of #<map>` and `Blocked by: #<n>` in the body and keep #37's task list/dependency spine current.

## Wayfinder

- A map is one issue; its body owns Notes, Decisions-so-far, Fog, and the ordered frontier index.
- A child ticket is a GitHub sub-issue. If sub-issues are unavailable, link it from the map task list and put `Part of #<map>` at the top of the child.
- Use native issue dependencies for blocking. If unavailable, record `Blocked by: #<n>`.
- The frontier is the map's first open child, in map order, that is unblocked and unassigned.
- Claim a ticket by assigning it to yourself.
- Resolve by posting durable evidence, closing the child, and adding a context pointer to the map's Decisions-so-far.
