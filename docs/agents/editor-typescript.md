# Browser Editor and TypeScript

Read this file when changing the browser editor, TypeScript domain state, UI, transport validation, or native selection integration.

## Style

- Use four-space indentation, single quotes, and semicolons.
- Prefer explicit interfaces and discriminated unions for protocol and lifecycle state.
- Mark immutable protocol data `readonly` and use type-only imports where appropriate.
- Follow the repository's configured lint and formatting rules; do not perform unrelated strictness migrations.

## Trust and state boundaries

- Validate untrusted protocol data explicitly rather than relying on unchecked casts or `any`.
- Copy or freeze externally supplied mutable data before retaining it.
- Keep lifecycle transitions explicit.
- Use the shared `CommandQueue` for work ordered with GPU readbacks or edit-history mutations.
- Route history-changing selection operations through `EditHistory`.
- Localize user-visible text.

For target identity, publication, Candidate application, and stale-result behavior, also read [Lifecycle and protocol invariants](lifecycle-and-protocol.md). For browser/Companion contract changes, follow the vertical-slice rules in [Architecture and change routing](architecture.md).
