# Code Discovery

Read this file when direct inspection cannot establish non-trivial symbol ownership, call relationships, registration paths, cross-runtime dependencies, or impact.

Use `codebase-memory-mcp` when its project and index generation are available and current. Prefer graph queries for symbols, callers/callees, routes, registrations, and bounded impact analysis.

Treat graph results as candidate evidence. Confirm material findings in source, tests, or runtime behavior, especially for dynamic dispatch, event wiring, plugin registration, protocol validation, and browser/Companion boundaries.

Use `rtk rg` and direct reads for:

- literals, errors, logs, configuration keys, comments, and documentation;
- shell scripts and other non-code files;
- known paths or files already being edited;
- areas missing from, skipped by, or stale in the graph index;
- insufficient graph results.

Before negative or exhaustive claims, check graph coverage for the bounded scope and inspect every material missing or stale range directly. A clean coverage result means no recorded gap, not proof of completeness.

When delegating, pass the graph project/generation, bounded scope, qualified symbols, paths, call-chain findings, coverage limitations, source fallback already performed, and unresolved questions. Do not assume a subagent inherits MCP access.
