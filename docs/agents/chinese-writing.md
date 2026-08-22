# Chinese Product and Technical Writing

Read this file only when drafting, rewriting, proofreading, or reviewing Chinese human-facing prose in this repository.

## Scope

- Apply this guidance to UI text, product documentation, release notes, operator and developer runbooks, issue and pull-request prose, and user-visible errors.

- Do not make style-only changes to [`CONTEXT.md`](http://CONTEXT.md), the current Final Spec, active ADRs, ticket mappings, traceability artifacts, historical specifications, frozen benchmark artifacts, or code comments unless they are explicitly in scope.

- Preserve code, protocol fields, enum values, Stable IDs, commands, paths, logs, and quoted external text exactly.

## Authority and terminology

- Use [`CONTEXT.md`](http://CONTEXT.md) for stable domain vocabulary.

- Follow `docs/ai-select/[CURRENT-TICKET-SPEC-MAPPING.md](http://CURRENT-TICKET-SPEC-MAPPING.md)` to the current Final Spec and active ADRs for product behavior and user-facing labels.

- Surface conflicts between current authority and implementation instead of silently rewriting either one.

- Preserve formal names such as `SuperSimPlat`, `SuperSplat`, `AI Select`, and `Selection Service Companion`.

- Do not maintain a second glossary in this file or invent Chinese aliases for identity-bearing lifecycle and protocol terms.

## Audience and product copy

- Separate end-user UI and product copy from operator and developer documentation.

- Use the exact operation and state labels defined by the current product authority; do not introduce synonyms merely for stylistic variety.

- Do not expose internal terms such as P/N/V Evidence, Contributor internals, transport details, CUDA details, or model-capacity mechanics unless the current user-facing contract requires them.

- State and error copy must reflect the actual lifecycle state. Distinguish unavailable, not ready, stale, capacity-limited, and failed states only when the implementation and specification make that distinction.

- Error text should state what happened, its user-visible effect, and an available recovery action. Do not invent retry guarantees, completion times, or automatic recovery behavior.
