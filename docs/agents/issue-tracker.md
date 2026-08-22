# GitHub Issue Workflow

Read this file for issue operations, triage labels, PR identification, or Wayfinder work. Issues and PRDs live as GitHub issues; use `rtk gh` from the repository clone.

## Repository conventions

- GitHub issues, not pull requests, are the feature-request and triage surface.
- When a skill says to publish to the issue tracker, create an issue.
- When a skill says to fetch a ticket, read the issue body, comments, and labels.
- GitHub shares issue and PR numbers. For an ambiguous `#<n>`, try `rtk gh pr view <n>` and fall back to `rtk gh issue view <n>`.
- Use CLI help for ordinary create/read/comment/edit/close syntax instead of maintaining a command catalog here.

Use only these canonical triage labels:

- `needs-triage`
- `needs-info`
- `ready-for-agent`
- `ready-for-human`
- `wontfix`

## Wayfinder

- A map is one issue labeled `wayfinder:map`; its body owns Notes, Decisions-so-far, and Fog.
- A child ticket is a GitHub sub-issue. If sub-issues are unavailable, link it from the map task list and put `Part of #<map>` at the top of the child.
- Use native issue dependencies for blocking. If unavailable, record `Blocked by: #<n>`.
- The frontier is the map's first open child, in map order, that is unblocked and unassigned.
- Claim a ticket by assigning it to yourself.
- Resolve by posting the durable answer/evidence, closing the child, and adding a context pointer to the map's Decisions-so-far.
