# Browser Editor and TypeScript

Read this file when changing browser state, UI, TypeScript domain models, transport validation, or native selection integration.

- Follow configured lint and formatting rules; do not perform unrelated formatting or strictness migrations.
- Model protocol and lifecycle state with explicit types and discriminated unions. Keep retained protocol records immutable where practical.
- Validate untrusted wire data explicitly; do not rely on unchecked casts or `any` at trust boundaries.
- Copy or freeze externally supplied mutable data before retaining it.
- Keep lifecycle transitions explicit.
- Use the shared `CommandQueue` for work ordered with GPU readbacks or edit-history mutations.
- Route history-changing selection operations through native `EditHistory`.
- Localize user-visible text.

For identity, publication, Candidate application, or stale-result behavior, also read [Lifecycle and protocol](lifecycle-and-protocol.md). For browser/Companion contract changes, follow [Architecture](architecture.md).
