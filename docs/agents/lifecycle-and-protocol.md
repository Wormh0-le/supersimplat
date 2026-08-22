# Lifecycle and Protocol Invariants

Read this file for target, View, Mask, Evidence, Candidate, identity, retries, suspension, asynchronous work, or native selection application.

## Identity and target context

- The editor owns Stable Gaussian IDs. They remain stable within one compatible immutable Target Splat content state.
- File, draw, renderer, chunk, and Companion tensor order never cross the protocol boundary as identity.
- Boundary IDs are unique unsigned 32-bit integers unless a versioned schema changes the contract.
- AI Select targets one Active Splat and exposes at most one Current Target Context.
- Anchor, Views, Masks, Participation, Evidence dependencies, Coverage, Readiness, Candidate, and Uncertain are target-local.
- Restart Current Target rotates `targetContextId` and disposes target-local state while preserving Native Selection/EditHistory, AI Select activation, tool/policy settings, and reusable runtime caches.
- Previous target AI contexts are not restored or browsed.

## Rendering and readiness

- All AI observation RGB uses locked gsplat. The interactive PlayCanvas/SuperSplat renderer remains editor presentation, not authoritative AI input.
- A View may be Render Ready without a Mask or Evidence. `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Render, Mask, Evidence, and Lift failures remain distinct and recover independently.
- Stable Mask is required for formal per-view Evidence.
- Evidence failure preserves valid RGB, the View, its Stable Mask, and the prior inspectable Candidate.

## CameraBinding and attempts

- `CameraBinding` is the shared truth for AI rasterization and its 3D Frustum: pose, intrinsics, resolution, clipping, and convention.
- Activation copies the Current Editor Camera into the Anchor binding without moving the Editor Camera. Generated Views also never move it; Camera Inspection pose never becomes Anchor implicitly.
- Semantic render identity and execution-attempt identity are separate.
- A lost-response replay may reuse the same attempt idempotently; a new user intent creates a new attempt.
- Product surfaces do not expose identical-input Render, Prompt, Mask, or Evidence retry commands. Initial planning failure is the sole product retry exception and creates a fresh bounded planning attempt.
- Replay or retry never mutates CameraBinding merely to bypass cached failure.

## Views and Mask publication

- An `AIView` may have RGB without a Mask.
- Operator-authored Point/Box/refinement input yields exactly one usable Mask or semantic unavailable. Multiple or malformed compatibility results fail closed.
- Proposal choice, preview, and acceptance are not product lifecycle states.
- `stableMaskId` identifies the version allowed in Evidence, Coverage, and Lifting. `editingMaskId` remains unpublished until Confirm Mask.
- Confirm Mask atomically publishes the corrected Mask and invalidates dependent Evidence/Candidate state by identity.
- A reviewed automatic Generated-View Mask may publish directly as Stable only after validating exact RGB, prompt/result, review policy, target identity, and Stable authority. It never silently replaces a User Confirmed Stable Mask.
- Stable-without-Editing is valid. Later correction creates an independent Editing draft while the Stable revision remains authoritative until explicit confirmation.
- The proposal wire envelope is compatibility-only. Review, refinement fallback, and previous-logits lineage must survive its collapse at the browser boundary.

## Quality, Participation, and Candidate

- Mask/View Quality and Lift Participation are separate.
- Auto Good defaults Included; Auto Review defaults Excluded; User Confirmed defaults Included unless explicitly excluded; failed/unavailable/no-Stable-Mask defaults Excluded.
- Explicit user Participation overrides automatic defaults. Review Reasons must be evidence-backed; do not invent a unified confidence percentage.
- Candidate derives from current Included Stable View Annotations, matching Evidence, and the versioned Evidence Policy; it is not directly patched in 3D.
- Publishing stable upstream input or changing Participation makes Candidate stale. A stale Candidate remains inspectable but cannot be applied.
- Explicit Re-Lift resolves/reuses per-view Evidence, aggregates, classifies, and atomically replaces Candidate. Failure preserves the prior inspectable Candidate.
- Candidate changes Native Selection only through explicit Set/Add/Remove/Intersect using native `SelectOp` and `EditHistory` semantics.
- Applying Candidate does not exit AI Select or destroy the target context. Native Selection-only changes and Undo/Redo do not stale Candidate.
- Existing delete, duplicate, separate, transform, lock, undo, and redo remain editor-owned.

## Scene dependencies, async work, and publication

- AI artifacts bind semantic target dependencies, including render state, geometry, Gaussian identity/membership, and target/world transform as applicable.
- A material target-dependency mutation suspends rather than destroys the context. Suspended state is inspectable but cannot be edited, lifted, or applied.
- Exact Undo may restore the prior semantic token and AI state. Edits outside target dependency scope do not invalidate it.
- Target-local async work binds at least `targetContextId`, `contextRevision`, and `dependencyToken`, plus every applicable Camera, RGB, Mask, Prompt, policy, working-set, runtime, and attempt identity.
- Operations that legitimately run without a target use their own versioned operation identity.
- Treat responses as untrusted. Validate structure, finite values, Stable IDs, camera semantics, dimensions, digests, policy/runtime identity, and publication completeness before state mutation.
- Discard non-matching results. Cancellation is only a resource optimization; stale-result correctness cannot depend on cancellation succeeding.
- Stable Mask, per-view Evidence, and Candidate replacement publish atomically. Progressive View publication is allowed only when each View is independently valid and bound.
- Partial products never become stable state; late or racing results never overwrite newer state.

## Coverage and readiness

- Observation Coverage uses valid Visible Mass over the relevant Core Target set, not whole-scene count or frustum membership.
- View Diversity is distinct from View count.
- Lift Readiness is `Not Ready`, `Limited`, or `Ready`, not a raw camera count.
- Unobserved Gaussians remain Uncertain rather than Rejected.
