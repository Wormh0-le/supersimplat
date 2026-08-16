# Architecture and Change Routing

Read this file for runtime ownership, repository seams, cross-runtime changes, or migration work.

## Migration baseline

```text
branch: ai-select-v1
forked from: 42f6013438f1271fcd35a4bfdc9ba5a3eb719c06
```

## Runtime ownership

### Browser editor

The browser owns:

- scene and splat state;
- Stable Gaussian IDs and their mapping to current splat indices;
- Current Editor Camera and Anchor or user-added `CameraBinding` construction;
- validation, registration, and presentation of planner-produced Generated-View CameraBindings;
- 3D Frustum presentation and manipulation;
- the single user-visible `CurrentTargetContext`;
- AI View Dock interaction, Gallery state, and the `AIView` registry;
- target-local lifecycle state, Mask versions, user confirmation, and Participation;
- Candidate and Uncertain visualization;
- Native Selection, Native EditHistory, and explicit Candidate application.

The browser owns product state even when the Companion computes an artifact used by that state.

### Selection Service Companion

The Companion owns:

- locked authoritative gsplat AI observation rendering;
- same-decision Mask-Conditioned Evidence production;
- SAM 3 Image inference and automatic static Mask production;
- TargetGeometryHint derivation;
- bounded local Generated-View planning and rendering;
- evidence-backed View and Mask assessment;
- per-view Gaussian Evidence artifacts;
- multi-view Evidence aggregation and Gaussian Lifting policy;
- renderer, model, Evidence, and runtime readiness;
- disposable runtime caches and service-side execution state;
- complete Contributor only as an explicit debug/reference backend.

Legacy Multiplex or video-tracker behavior may remain only behind historical benchmark or compatibility seams unless a later measured ADR adopts an ordered video workload.

Companion caches may include scene tensors, RGB, Evidence, reference Contributor data, and model state. Cache reuse never becomes user-visible AI View or target-context persistence.

## Repository seams

### Browser editor

- `src/main.ts` — composition root, command queue, event registration, UI construction, and Companion readiness wiring
- `src/scene-snapshot.ts` and related modules — immutable Scene Snapshot and Stable Gaussian ID contracts
- `src/selection-service-fetch-adapter.ts` — browser/Companion transport, registration, retries, and response validation
- `src/ai-select/mask-service.ts` — the singular product Mask result and the
  only compatibility adapter allowed to consume the retained internal
  ProposalSet / ProposalDecision wire envelope
- `src/selection-service-readiness*.ts` — readiness and capability gating
- `src/selection.ts`, `src/edit-history.ts`, `src/edit-ops.ts`, and `src/tools/` — native selection/edit behavior and final mutation authority

New Final Spec work should converge under `src/ai-select/`. Prefer explicit modules for durable concepts such as Current Target Context, CameraBinding and attempts, dependency and request identity, AI Views, Mask versions, Evidence status, Candidate lifecycle, Participation, Coverage, Diversity, and Readiness.

### Companion

- `selection-service-companion/src/selection_service_companion/` — control plane, rendering, masking, Generated Views, assessment, Evidence/Lifting, and runtime state
- `selection-service-companion/tests/` — Companion contracts and behavior tests
- `selection-service-companion/pyproject.toml`, `uv.lock`, and `README.md` — runtime, dependency, and operator contract

### Pinned external sources

- `thirdparty/sam3`
- `thirdparty/gsplat`
- `thirdparty/splat_analyzer`

Treat `thirdparty/` as pinned upstream source. Changes to vendored runtime code require explicit ownership, pinning, build/runtime identity, validation, and a record of maintenance consequences.

### Legacy PoC seams

The following contain reusable primitives but superseded product semantics:

- `src/object-selection-session.ts`
- `src/object-selection-session-factory.ts`
- `src/ui/object-selection-*`
- Prompt Log and Mask Track orchestration
- New/Add/Remove/Refine inference workflow
- preview-confirm-close session lifecycle
- complete Contributor as the normal lifting representation

Reuse compatible trust-boundary checks and validated primitives. Replace tests that explicitly assert superseded behavior; do not preserve an obsolete abstraction solely to keep those tests green.

## Change routing

### Editor-only changes

Typical editor-owned areas include CurrentTargetContext lifecycle, CameraBinding and attempts, Frustum and Gallery UI, Mask version state, Evidence references, Candidate presentation, Native SelectOp/EditHistory integration, Stable ID mapping, and dependency-token integration.

Keep upstream SuperSplat behavior outside the requested seam unchanged.

### Companion-only changes

Typical Companion-owned areas include control-plane validation, readiness, gsplat rendering, Direct Evidence and reference Contributor backends, SAM adapters, Generated-View planning, ViewAssessmentPolicy, Evidence aggregation, Gaussian Lifting, caches, capacity, and cleanup.

Keep the editor-facing contract unchanged unless the requested slice requires a contract change.

### Cross-runtime changes

When the browser/Companion contract changes, update the complete vertical slice:

1. TypeScript request, response, and domain types
2. Editor-side runtime validation
3. Browser transport
4. Python route parsing and validation
5. Companion state and orchestration
6. Response and artifact construction
7. TypeScript tests
8. Python tests
9. Protocol/domain docs, ADRs, issues, and traceability when semantics change

Both sides must enforce the same contract; do not make one side permissive to compensate for the other.

## Migration discipline

Use tracer-bullet slices rather than wholesale legacy workflow ports. Retain compatible foundations:

- Stable Gaussian ID mapping;
- SceneSnapshot serialization and spatial working-set controls;
- locked authoritative gsplat RGB;
- complete Contributor reference/debug infrastructure;
- SAM runtime and model adapters;
- Generated-View camera and planning primitives;
- compatible Evidence Policy mathematics;
- native `SelectOp` and `EditHistory` integration;
- benchmark and reproducibility infrastructure.

Port compatible slices explicitly; do not cherry-pick large legacy workflow commits wholesale. The required lifting migration sequence is documented in [Renderer and Evidence](renderer-and-evidence.md).
