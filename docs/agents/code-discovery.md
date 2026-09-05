# Code Discovery

Read this file when direct inspection cannot establish non-trivial symbol ownership, call relationships, registration paths, cross-runtime dependencies, or impact.

Use `codebase-memory-mcp` when the current host exposes it and its project/index generation are current. Prefer graph queries for symbols, callers/callees, routes, registrations, and bounded impact analysis. When unavailable, use `rg` and direct source inspection; discovery does not require installing or configuring an optional graph tool.

Treat graph results as candidate evidence. Confirm material findings in source, tests, or runtime behavior, especially for dynamic dispatch, event wiring, plugin registration, protocol validation, and browser/Companion boundaries.

Use `rg` and direct reads for:

- literals, errors, logs, configuration keys, comments, and documentation;
- shell scripts and other non-code files;
- known paths or files already being edited;
- areas missing from, skipped by, or stale in the graph index;
- insufficient graph results.

Before negative or exhaustive claims, establish source coverage for the bounded scope. If using a graph, check its coverage and inspect every material missing or stale range directly. A clean graph coverage result means no recorded gap, not proof of completeness.

If discovery findings are handed off, include the graph project/generation when used, qualified symbols and paths, decisive source evidence, and coverage gaps.
