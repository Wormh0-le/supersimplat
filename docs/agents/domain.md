# AI Select Domain Authority

Read this file when work changes AI Select behavior, terminology, product scope, current specification authority, or legacy semantics.

## Authority

Use `docs/ai-select/CURRENT-TICKET-SPEC-MAPPING.md` as the current entry point. Follow it to the authoritative Final Spec, active non-superseded ADRs, implementation ticket, and traceability artifacts for the affected scope.

Then inspect, as relevant:

1. `CONTEXT.md` for stable domain vocabulary;
2. the nearest implementation and tests;
3. dependency and runtime declarations when rendering, inference, CUDA, installation, calibration, or model identity is affected.

Current specifications and active ADRs govern product behavior. Old implementations, fixtures, tests, tickets, and historical specifications do not restore superseded semantics. Frozen benchmark artifacts are authoritative only for the benchmark data they record.

Surface conflicts among the mapping, current spec, active ADRs, and implementation instead of silently choosing one.

## Product boundaries

- AI Select is a SuperSplat Selection Tool, not a separate semantic-object workspace.
- The browser owns one user-visible Current Target Context; Companion-computed artifacts do not transfer product-state ownership.
- Authoritative AI observation RGB comes from locked gsplat, not a PlayCanvas or framebuffer capture.
- Operator interaction produces one usable Mask or semantic unavailable; Included Stable Masks drive production P/N/V Evidence and lifting.
- AI Candidate is derived state. It mutates Native Selection only through explicit Set, Add, Remove, or Intersect operations backed by native edit history.
- Cross-target persistent truth is Native Selection and Native EditHistory, not a restorable AI target-session stack.
- RGB Ready, Mask Ready, Evidence Ready, and Candidate Ready are distinct states.
- Complete per-pixel Contributor is a reference/debug capability, not the production lifting contract.
- Do not add user-facing Candidate provenance, Gaussian-level Evidence inspection, persistent Candidate history, or restoration of previous target contexts without a new specification decision.

## Legacy semantics

Treat ObjectSelectionSession, Prompt Log, Mask Track/Mask Set, New/Add/Remove/Refine inference modes, ordered video-tracker orchestration, PlayCanvas-captured Anchor RGB, and preview-confirm-close session flow as legacy or reference concepts.

Reuse validated primitives only when they satisfy the current contract. Qualify historical terms as `legacy`, `reference`, or `debug` when ambiguity is possible. `Add` and `Remove` in current product language refer to native Candidate application operations.
