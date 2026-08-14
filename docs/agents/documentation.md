# Documentation, ADRs, and Traceability

Read this file when changing comments, domain vocabulary, specifications, architectural decisions, tickets, or traceability.

## Durable project knowledge

- Update `CONTEXT.md` when a durable domain concept or project term changes.
- Add or supersede an ADR when an architectural decision changes; do not silently diverge from the recorded decision.
- Update the local issue graph when a specification change affects implementation scope, then rerun the relevant traceability or audit before declaring the work agent-ready.
- Keep Final Spec v1.3 terminology consistent with [Domain and sources of truth](domain.md).
- Preserve legacy vocabulary only in historical or benchmark records, qualified where ambiguity is possible.

## Comments

Use comments to explain authority, ownership, trust boundaries, identity, atomicity, and non-obvious failure behavior. Omit comments that only narrate straightforward implementation.

Use ADRs for durable architectural trade-offs and `CONTEXT.md` for stable domain vocabulary rather than implementation diaries.

## Documentation validation

For documentation-only changes:

- check terminology against `CONTEXT.md`;
- check compatibility with Final Spec v1.3, ADR 0016 and ADR 0017 where applicable, and non-superseded ADR 0013 and ADR 0015 rules;
- check issue graph and traceability consistency when scope changes;
- verify executable commands, schemas, links, and examples.

Use [Issue tracker](issue-tracker.md) for GitHub operations and [triage labels](triage-labels.md) for repository label vocabulary.
