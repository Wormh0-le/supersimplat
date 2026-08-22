# Architecture and Change Routing

Read this file for runtime ownership, cross-runtime contracts, repository seams, vendored code, or migration work.

## Runtime ownership

### Browser editor

The browser owns user-visible product state:

- scene and splat state, Stable Gaussian IDs, and current-index mapping;
- editor-authored CameraBindings and validation/registration of planned bindings;
- Current Target Context, AI Views, Mask versions, Participation, Candidate, and Uncertain presentation;
- native Selection, EditHistory, and explicit Candidate application.

The browser remains the product-state authority even when the Companion computes an artifact.

### Selection Service Companion

The Companion owns computation and disposable runtime state:

- locked authoritative gsplat rendering and same-decision P/N/V Evidence;
- SAM inference, TargetGeometryHint, Generated-View planning/rendering, and assessment;
- Evidence aggregation, Gaussian Lifting, readiness, capacity, caches, and cleanup;
- complete Contributor only as an explicit reference/debug backend.

Companion caches never become user-visible View or target-context persistence. Legacy multiplex or video-tracker behavior may remain only behind historical benchmark or compatibility seams unless a later ADR adopts it.

## Repository seams

- New current-product browser work converges under `src/ai-select/`.
- `src/ai-select/mask-service.ts` is the only compatibility boundary allowed to consume the retained internal proposal wire envelope.
- Native mutations remain owned by existing selection, tool, and edit-history paths.
- Companion implementation and tests live under `selection-service-companion/`.
- `thirdparty/sam3`, `thirdparty/gsplat`, and `thirdparty/splat_analyzer` are pinned upstream sources. Modify vendored code only when the task explicitly requires it, and account for source pin, build/runtime identity, licensing, validation, and maintenance consequences.

Use code discovery rather than extending this file with a path inventory that can be derived from the repository.

## Change routing

For editor-only or Companion-only work, preserve the other runtime's contract unless the requested slice requires a contract change.

For a browser/Companion contract change, inspect and update every affected layer of the vertical slice:

1. TypeScript domain and wire types;
2. editor-side runtime validation and browser transport;
3. Python route parsing and validation;
4. Companion orchestration, state, and artifact construction;
5. affected tests;
6. current specifications, ADRs, tickets, and traceability only when their owned semantics change.

Both sides must enforce the same fail-closed contract. Do not make one side permissive to compensate for the other.

## Migration discipline

Port tracer-bullet slices, not wholesale legacy workflows or large historical commits. Reuse compatible foundations such as Stable ID mapping, SceneSnapshot serialization, locked gsplat RGB, model adapters, Generated-View primitives, Evidence mathematics, native selection/history integration, and benchmark infrastructure only after validating them against the current contract.

Legacy object-selection modules may supply primitives and trust-boundary checks, but their product lifecycle is superseded. Replace tests that assert obsolete behavior rather than preserving obsolete abstractions to keep them green.
