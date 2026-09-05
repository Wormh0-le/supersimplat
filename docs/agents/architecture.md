# Architecture and Change Routing

Read this file for runtime ownership, cross-runtime contracts, repository seams, vendored code, or migration work.

## Runtime baseline

Follow [Domain authority](domain.md) for the target specification, implementation gate, and production baseline. Use current stage evidence and code to establish active capability, schema, policy, production-identity, calibration, and cutover gates.

## Runtime ownership

### Browser editor

The Browser owns user-visible product state and orchestration:

- scene/splat state, Stable Gaussian IDs, and current-index mapping;
- Current Target Context, AI Views, Mask versions, Participation, Candidate, and Uncertain presentation;
- editor-authored CameraBindings and validation/registration of planner-produced bindings;
- acquisition Series/Attempt/Iteration state, Decision Journal, progress/cancel presentation, and per-step request driving after their exact stages land;
- Native Selection, EditHistory, and explicit Candidate application.

The Browser may consume Companion-computed readiness and stop reasons, but it does not compute or publish a Candidate independently.

### Selection Service Companion

The Companion owns computation and disposable runtime state:

- locked authoritative gsplat rendering and same-decision Direct Evidence;
- SAM inference, TargetGeometryHint, Generated-View planning/rendering, and assessment;
- v2 Seed, Consensus, Reliability, weighted aggregation, View Utility, and Lift Readiness computation after their child stages land;
- request-scoped or loop-scoped derived caches keyed by exact target/dependency/policy identity;
- capacity, cleanup, and reference Contributor diagnostics.

Companion caches never become user-visible target persistence. No stage may introduce a Companion-autonomous product session without a new accepted decision in the owning Issue.

## Repository seams

- New browser product work converges under `src/ai-select/`.
- Existing generated-view control is a migration source, not proof that the v2 loop contract is already implemented.
- `src/ai-select/mask-service.ts` remains the compatibility boundary for the retained proposal wire envelope until an exact migration stage changes it.
- Native mutation remains in existing selection/tool/edit-history paths.
- Companion implementation and tests live under `selection-service-companion/`.
- `thirdparty/sam3`, `thirdparty/gsplat`, and `thirdparty/splat_analyzer` are pinned upstream sources.

Use code discovery before writing paths into durable guidance or an executable child Issue.

## Cross-runtime changes

When a Browser/Companion contract changes, inspect and update the complete vertical slice:

1. TypeScript domain/wire types;
2. editor-side runtime validation and transport;
3. Python route parsing and validation;
4. Companion orchestration/state/artifact construction;
5. schema and production-identity migration;
6. TypeScript, Python, replay, and failure tests;
7. the owning child Issue and #37 only when their contract, graph, calibration, or readiness changed.

Both sides must fail closed. Do not make one side permissive to compensate for the other.

## Migration discipline

- Use tracer-bullet stages; do not implement a parent V2 capability Issue as one large change.
- Preserve v1.3 production behavior behind explicit gates until the replacement stage is calibrated and promoted.
- Experimental policy IDs do not satisfy production readiness.
- Calibration, policy freeze, production-identity rotation, final cutover, rollback, and release qualification require explicit owners in #37 and the exact child graph.
- Reuse Stable IDs, SceneSnapshot, authoritative RGB, Direct Evidence, model adapters, generated-view primitives, native selection/history, and benchmark infrastructure only after checking the current code contract.
