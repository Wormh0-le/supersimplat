# Architecture and Change Routing

Read this file for runtime ownership, cross-runtime contracts, repository seams, vendored code, or migration work.

## Runtime baseline

Final Spec v2.0 is the target architecture. The code remains the implemented v1.3 runtime until V2 tickets land through explicit capability, schema, policy, and production-identity cutovers.

## Runtime ownership

### Browser editor

The Browser owns user-visible product state and orchestration:

- scene/splat state, Stable Gaussian IDs, and current-index mapping;
- Current Target Context, AI Views, Mask versions, Participation, Candidate, and Uncertain presentation;
- editor-authored CameraBindings and validation/registration of planner-produced bindings;
- the future acquisition-loop state machine, progress/cancel presentation, and per-step request driving;
- Native Selection, EditHistory, and explicit Candidate application.

The Browser may consume Companion-computed readiness and stop reasons, but it does not compute or publish a Candidate independently.

### Selection Service Companion

The Companion owns computation and disposable runtime state:

- locked authoritative gsplat rendering and same-decision Direct Evidence;
- SAM inference, TargetGeometryHint, Generated-View planning/rendering, and assessment;
- v2 seed, provisional consensus, reliability, weighted aggregation, View Utility, and Lift Readiness computation after their tickets land;
- loop-scoped caches/journals keyed by exact target/dependency/policy identity;
- capacity, cleanup, and reference Contributor diagnostics.

Companion caches never become user-visible target persistence. No V2 ticket may introduce a Companion-autonomous product session without a new accepted decision.

## Repository seams

- New browser product work converges under `src/ai-select/`.
- Existing generated-view control is a migration source, not proof that the v2 loop contract is already implemented.
- `src/ai-select/mask-service.ts` remains the only compatibility boundary for the retained proposal wire envelope.
- Native mutation remains in existing selection/tool/edit-history paths.
- Companion implementation and tests live under `selection-service-companion/`.
- `thirdparty/sam3`, `thirdparty/gsplat`, and `thirdparty/splat_analyzer` are pinned upstream sources.

Use code discovery before writing paths into durable guidance.

## Cross-runtime changes

When a Browser/Companion contract changes, inspect and update the complete vertical slice:

1. TypeScript domain/wire types;
2. editor-side runtime validation and transport;
3. Python route parsing and validation;
4. Companion orchestration/state/artifact construction;
5. schema and production-identity migration;
6. TypeScript, Python, replay, and failure tests;
7. current spec/ADR/ticket/traceability only when their owned semantics change.

Both sides must fail closed. Do not make one side permissive to compensate for the other.

## Migration discipline

- Use tracer-bullet stages; do not implement an umbrella V2 ticket as one large change.
- Preserve v1.3 production behavior behind explicit gates until the replacement stage is calibrated and promoted.
- Experimental policy IDs do not satisfy production readiness.
- Calibration, policy freeze, production-identity rotation, and final cutover require explicit ownership in the reviewed graph.
- Reuse Stable IDs, SceneSnapshot, authoritative RGB, Direct Evidence, model adapters, generated-view primitives, native selection/history, and benchmark infrastructure only after checking the current code contract.
