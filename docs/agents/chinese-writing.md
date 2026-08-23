# Chinese Product and Technical Writing

Read this file only when drafting, rewriting, proofreading, or reviewing Chinese human-facing prose in this repository.

## Scope

- Apply this guidance to UI text, product documentation, release notes, operator and developer runbooks, Issue and pull-request prose, and user-visible errors.
- Do not make style-only changes to root [`CONTEXT.md`](../../CONTEXT.md), [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37), parent/child capability Issues, accepted decision comments, immutable historical snapshots, frozen benchmark artifacts, or code comments unless they are explicitly in scope.
- Preserve code, protocol fields, enum values, Stable IDs, commands, paths, logs, Issue numbers, and quoted external text exactly.

## Authority and terminology

- Use root [`CONTEXT.md`](../../CONTEXT.md) for stable domain vocabulary where it does not conflict with current accepted authority.
- Follow [Issue #37](https://github.com/Wormh0-le/supersimplat/issues/37) to the amended v2.0 snapshot, current capability Issue, exact child stage, and accepted user-facing labels.
- Surface conflicts between current authority, glossary, and implementation instead of silently rewriting any of them.
- Preserve formal names such as `SuperSimPlat`, `SuperSplat`, `AI Select`, and `Selection Service Companion`.
- Do not maintain a second glossary in this file or invent Chinese aliases for identity-bearing lifecycle and protocol terms.

## Audience and product copy

- Separate end-user UI and product copy from operator and developer documentation.
- Use the exact operation and state labels defined by the current owning Issue; do not introduce synonyms merely for stylistic variety.
- Do not expose internal terms such as P/N/V Evidence, Contributor internals, transport details, CUDA details, or model-capacity mechanics unless the current user-facing contract requires them.
- State and error copy must reflect the actual lifecycle state. Distinguish unavailable, not ready, stale, capacity-limited, suspended, and failed states only when the implementation and accepted contract make that distinction.
- Error text should state what happened, its user-visible effect, and an available recovery action. Do not invent retry guarantees, completion times, or automatic recovery behavior.
