# Project Documentation and Traceability

Read this file when changing `CONTEXT.md`, current specifications, ADRs, feature documents, tickets, comments, or traceability.

## Artifact ownership

- `CONTEXT.md` owns stable domain vocabulary, not implementation status, counts, paths, constants, or feature scratch notes.
- `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md` points to the current product authority and implementation scope.
- The current Final Spec owns product behavior; active ADRs own durable architectural decisions and trade-offs.
- Implementation tickets and traceability artifacts own active work decomposition and coverage.
- Historical specs, ADRs, audits, and benchmarks remain history; qualify them so they cannot be mistaken for current authority.

Update only the artifact whose owned claim changed. Do not edit current specs, ADRs, or traceability for a code-only implementation detail that leaves their contract unchanged.

## Feature-document lifecycle

Planning and feature documents are temporary unless they contain durable authority. At feature closeout, classify each affected artifact:

- promote stable terminology to `CONTEXT.md`;
- update current behavior in the Final Spec;
- accept or supersede a qualifying ADR rather than rewriting history;
- reconcile ticket mapping and traceability when implementation scope changed;
- archive only material historical evidence; delete intermediate implementation narratives by default.

For local comments, follow the global durable-comment rule. Use comments for non-obvious authority, identity, atomicity, fail-closed behavior, or trust boundaries; link to the owning spec/ADR instead of duplicating broad rationale.

## Validation

Check affected terminology against `CONTEXT.md` and the current mapping, then verify changed links, commands, schemas, examples, ticket relationships, and traceability. Do not hard-code a separate list of current ADR numbers in this guide.
