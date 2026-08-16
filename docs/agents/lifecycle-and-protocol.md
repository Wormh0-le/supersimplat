# Lifecycle and Protocol Invariants

Read this file for target lifecycle, Mask or Candidate state, identity, retries, suspension, asynchronous work, or native selection application.

## Stable identity

- The editor owns Stable Gaussian IDs.
- Stable IDs remain stable within one compatible immutable Target Splat content state.
- File, draw, renderer, chunk, and Companion tensor order never cross the protocol boundary as identity.
- Stable IDs crossing the boundary are unique unsigned 32-bit integers unless a versioned schema changes the contract.
- AI Select targets one Active Splat at a time.

## Current Target Context

- At most one user-visible `CurrentTargetContext` is active.
- Anchor, Views, Masks, Participation, Evidence dependencies, Coverage, Readiness, Candidate, and Uncertain are target-local.
- `Restart Current Target` rotates `targetContextId` and disposes target-local state.
- Restart preserves Native Selection, Native EditHistory, AI Select activation, tool and policy settings, and reusable runtime caches.
- Final Spec v1.3 does not restore or browse previous target AI contexts.

## Rendering and readiness states

- All AI observation RGB comes from locked gsplat, including Anchor Preview/Final, Generated Views, and User-added Views.
- PlayCanvas/SuperSplat remains the interactive editor renderer; canvas or framebuffer capture is not authoritative AI input.
- A View may be Render Ready without a Mask or Evidence.
- `RGB Ready != Mask Ready != Evidence Ready != Candidate Ready`.
- Render, Mask, Evidence, and Lift failures remain distinguishable and have separate recovery paths.
- Stable Mask is required before formal per-view Evidence production.
- Evidence failure preserves valid RGB, the View, its Stable Mask, and the previous inspectable Candidate.

## CameraBinding and execution attempts

- `CameraBinding` is the shared truth for AI rasterization and the corresponding 3D Frustum; it determines pose, intrinsics, resolution, clipping, and convention.
- AI Select activation copies the Current Editor Camera into the Anchor CameraBinding without moving the Editor Camera.
- Generated Views never move the visible Editor Camera.
- Camera Inspection observer pose never becomes the Anchor implicitly.
- Semantic render identity and execution-attempt identity are distinct.
- A lost-response replay may reuse the same attempt idempotently.
- A normal new user intent creates a distinct attempt. Product surfaces do not
  expose identical-input Render, Prompt, Mask or Evidence retry commands.
- The only product retry exception is initial planning failure recovery; it
  creates a fresh bounded planning attempt.
- Replay or a new attempt does not jitter or mutate CameraBinding to bypass a
  cached failure.

## AI Views and Mask publication

- An `AIView` may have RGB without a Mask.
- Operator-authored Point, Box and refinement input produces exactly one usable
  Mask with Review or semantic unavailable. A usable result automatically
  becomes Editing; multiple or malformed compatibility results fail closed.
- Proposal choice, preview and acceptance are not product lifecycle states.
- `stableMaskId` identifies the Mask version allowed to participate in Evidence, Coverage, and Lifting.
- `editingMaskId` is unpublished and does not replace the Stable Mask until Confirm Mask.
- Confirm Mask atomically publishes an edited or manually corrected Mask and invalidates dependent Evidence and Candidate state by identity.
- A reviewed automatic Generated-View Mask may publish directly as a Stable Mask without an Editing Mask or user confirmation.
- Automatic publication validates the exact RGB, Prompt/result, review policy, current target identity, and Stable authority.
- Automatic publication never silently replaces a User Confirmed Stable Mask.
- Stable-without-Editing is a valid confirmed state. Entering later correction
  creates an independent Editing draft and retains the Stable revision until
  explicit Confirm Mask.
- The internal proposal wire envelope is compatibility-only. Review,
  refinement fallback and previous-logits lineage must survive its collapse at
  the browser boundary.

## Quality and Participation

- Mask/View Quality and Lift Participation are separate dimensions.
- Auto Good defaults Included.
- Auto Review defaults Excluded.
- User Confirmed defaults Included unless explicitly excluded.
- Failed, unavailable, or no Stable Mask defaults Excluded.
- A user's explicit Participation choice overrides automatic defaults.
- Review Reasons must be evidence-backed; do not invent a unified confidence percentage.

## Candidate lifecycle and native selection

- Candidate derives from current Included Stable View Annotations, matching Evidence, and the versioned Evidence Policy.
- Candidate is not directly patched in 3D.
- Publishing stable upstream input or changing Participation makes Candidate stale.
- A stale Candidate remains inspectable but cannot run Set, Add, Remove, or Intersect.
- Explicit Re-Lift resolves or reuses per-view Evidence, aggregates, classifies, and atomically publishes a replacement.
- Failed replacement preserves the previous inspectable Candidate.
- Candidate never changes Native Selection until explicit Set, Add, Remove, or Intersect.
- Candidate application uses native set semantics through `SelectOp` and `EditHistory`.
- Applying Candidate does not exit AI Select or destroy Current Target Context.
- Native Selection-only changes and Undo/Redo do not stale Candidate.
- Existing delete, duplicate, separate, transform, lock, undo, and redo behavior remains editor-owned.

## Scene dependency and suspension

- AI artifacts bind semantic target dependencies rather than only a monotonic global counter.
- Dependency identity covers render state, geometry, Gaussian identity or membership, and target/world transform as required.
- A material dependency mutation suspends Current Target Context instead of destroying it.
- Suspended context remains inspectable but cannot be edited, lifted, or applied.
- Exact Undo may restore the prior semantic token and AI state.
- Scene edits outside the target dependency scope do not invalidate the target.

## Async identity and stale-result rejection

Target-local asynchronous work binds at least:

```text
targetContextId
contextRevision
dependencyToken
```

Artifact-producing work also binds every applicable Camera, RGB, Mask, Prompt, policy, working-set, runtime, and attempt identity. Health checks, readiness, model initialization, and other operations that can run without a Current Target Context use their own versioned operation identity instead of inventing a target binding.

Discard non-matching results. Cancellation is a resource optimization; stale-result correctness cannot depend on cancellation succeeding.

Treat transport responses as untrusted. Validate structure, finite values, Stable IDs, camera semantics, dimensions, digests, policy and runtime identity, and publication completeness before updating state.

## Atomic publication

- Stable Mask publication is atomic.
- Per-view Evidence publication is atomic.
- Candidate replacement is atomic.
- Progressive View publication is allowed only when every published View is independently valid and bound.
- Partial products never become stable user state.
- Late or racing results never overwrite newer state.

## Coverage and Readiness

- Observation Coverage uses valid Visible Mass over the relevant Core Target set, not whole-scene Gaussian count or frustum membership.
- View Diversity is distinct from View count.
- Lift Readiness is `Not Ready`, `Limited`, or `Ready`, not a raw camera count.
- Unobserved Gaussians remain Uncertain rather than Rejected.
